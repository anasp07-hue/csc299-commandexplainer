"""The interactive program: pick a shell, then explain commands until the user quits."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from commandexplain.colors import PLAIN, Palette, colors_enabled
from commandexplain.formatter import NOT_COVERED_MESSAGES, explain
from commandexplain.lookup import (
    DataFileError,
    default_commands,
    default_not_covered,
    default_operators,
    find_command,
    not_covered_kind,
    suggest,
)
from commandexplain.parser import (
    Chain,
    ChainCommand,
    ParseError,
    chain_to_text,
    parse_chain,
    retype,
    split_flags,
)
from commandexplain.shell import SHELLS, ask_shell, choose_shell, read_shell_answer

PROMPT = "Enter a command to explain (or 'quit' to leave): "
QUIT_WORDS = frozenset({"quit", "q"})
SWITCH_WORD = "shell"

GOODBYE = "Goodbye!"
NOT_FOUND = "Command not found. Please re-enter it."
UNKNOWN = "Sorry, I don't know '{name}'. Check the spelling and try again."
EXIT_TIP = '(Tip: type "quit" to leave this program.)'
SHELL_CHOSEN = 'Using {shell}. (Type "shell" any time to switch.)'
SHELL_SWITCHED = "Switched to {shell}."
WRONG_SHELL = "'{name}' is a {other} command and doesn't work in {shell}. Explain it anyway?"
SKIPPED_IN_CHAIN = "OK, I won't explain it. Please re-enter the command."
PARSE_MESSAGES = {
    ParseError.UNCLOSED_QUOTE: 'It looks like a quote (") is missing its partner. '
    "Please re-enter it.",
    ParseError.TRAILING_BACKSLASH: "Your command ends with a backslash (\\), which needs "
    "something after it. Please re-enter it.",
    ParseError.EMPTY_COMMAND: "The command name is empty. Please re-enter it.",
    ParseError.MISSING_BEFORE: 'Something is missing before "{detail}". Please re-enter it.',
    ParseError.MISSING_AFTER: 'Something is missing after "{detail}". Please re-enter it.',
    ParseError.UNSUPPORTED: 'Sorry, I can\'t explain "{detail}" yet. Try a simpler version '
    "of the command.",
}

InputFn = Callable[[str], str]
PrintFn = Callable[[str], None]


class QuitRequested(Exception):
    """Raised when the user wants to leave: Ctrl+C / Ctrl+D, or 'quit' at a shell question."""

    def __init__(self, interrupted: bool = True) -> None:
        """interrupted=True means Ctrl+C / Ctrl+D, which leaves the prompt line unfinished."""
        super().__init__()
        self.interrupted = interrupted


class Console:
    """Prompts and output, through injectable functions so tests can script a session."""

    def __init__(self, input_fn: InputFn, print_fn: PrintFn) -> None:
        """Use input_fn to read answers and print_fn to show text."""
        self._input = input_fn
        self._print = print_fn

    def ask(self, prompt: str) -> str:
        """Show a prompt and return the answer. Ctrl+C / Ctrl+D raise QuitRequested."""
        try:
            return self._input(prompt)
        except (EOFError, KeyboardInterrupt):
            raise QuitRequested from None

    def ask_or_quit(self, prompt: str) -> str:
        """Like ask(), but typing 'quit' or 'q' also leaves (used for the shell questions)."""
        answer = self.ask(prompt)
        if answer.strip().lower() in QUIT_WORDS:
            raise QuitRequested(interrupted=False)
        return answer

    def say(self, text: str) -> None:
        """Show a line of text."""
        self._print(text)

    def confirm(self, question: str) -> bool:
        """Ask a yes/no question until the answer is y, yes, n, or no (any case)."""
        while True:
            answer = self.ask(f"{question} (yes/no) ").strip().lower()
            if answer in ("y", "yes"):
                return True
            if answer in ("n", "no"):
                return False
            self.say("Please type yes or no.")


class Session:
    """One run of the program: the chosen shell, the data, and the main loop."""

    def __init__(
        self,
        console: Console,
        commands: dict[str, dict[str, Any]],
        not_covered: dict[str, dict[str, Any]],
        operators: dict[str, dict[str, Any]],
        env: Mapping[str, str],
        shell: str | None = None,
        palette: Palette = PLAIN,
    ) -> None:
        """Set up a session. If shell is None, the user is asked for it when run() starts.

        All data is passed in already loaded, so main() can turn a broken data
        file into a clean error message (SPEC.md §9). `palette` decides colors.
        """
        self.console = console
        self.commands = commands
        self.not_covered = not_covered
        self.operators = operators
        self.env = env
        self.shell = shell
        self.palette = palette

    def run(self) -> int:
        """Run until the user quits. Always returns exit code 0."""
        console = self.console
        try:
            if self.shell is None:
                self.shell = choose_shell(
                    console.ask_or_quit,
                    console.confirm,
                    console.say,
                    self.env,
                    highlight=self.palette.suggestion,
                )
            console.say(SHELL_CHOSEN.format(shell=self.shell))
            while True:
                text = console.ask(PROMPT)
                words = text.strip().lower().split()
                if not words:
                    continue
                if len(words) == 1 and words[0] in QUIT_WORDS:
                    break
                if words[0] == SWITCH_WORD and len(words) <= 2:
                    self.switch_shell(words[1] if len(words) == 2 else "")
                    continue
                self.handle_input(text)
        except QuitRequested as quit_request:
            if quit_request.interrupted:
                console.say("")  # move off the half-finished prompt line
        except KeyboardInterrupt:
            console.say("")
        console.say(GOODBYE)
        return 0

    def switch_shell(self, requested: str) -> None:
        """Change shell: 'shell bash' switches at once, plain 'shell' asks (ADR 0016, 0017)."""
        console = self.console
        shell = read_shell_answer(requested)
        if shell is None:
            shell = ask_shell(
                console.ask_or_quit,
                console.confirm,
                console.say,
                highlight=self.palette.suggestion,
            )
        self.shell = shell
        console.say(SHELL_SWITCHED.format(shell=shell))

    def handle_input(self, text: str) -> None:
        """Explain a typed command or chain, fixing typos with the user's OK along the way."""
        try:
            chain = parse_chain(text)
        except ParseError as err:
            self.console.say(PARSE_MESSAGES[err.reason].format(detail=err.detail))
            return
        if chain is None:
            return
        if self.shell is None:
            raise RuntimeError("handle_input() needs a shell; run() chooses one first")

        in_chain = not chain.is_single
        fixed: list[ChainCommand] = []
        for command in chain.commands:
            tokens = self._resolve_tokens(list(command.tokens), in_chain)
            if tokens is None:
                return
            fixed.append(retype(command, tokens))
        fixed_chain = Chain(tuple(fixed), chain.joiners)

        self.console.say(
            explain(
                chain_to_text(fixed_chain),
                self.shell,
                self.commands,
                self.operators,
                self.not_covered,
                self.palette,
            )
        )
        if any(find_command(c.tokens[0], self.commands) == "exit" for c in fixed):
            self.console.say(EXIT_TIP)
        self.console.say("")

    def _resolve_tokens(self, tokens: list[str], in_chain: bool) -> list[str] | None:
        """Check each command in one segment (sudo's inner commands too, ADR 0015).

        Returns the words with any accepted spelling fixes, or None if the whole
        input should be dropped (a message has already been shown).
        """
        index = 0
        is_inner = False
        while True:
            resolved = self._resolve_name(tokens[index], is_inner, in_chain)
            if resolved is None:
                return None
            tokens[index] = resolved
            name = find_command(resolved, self.commands)
            if name is None:  # an unknown inner command; explain() will say so
                return tokens
            entry = self.commands[name]
            if not self._shell_ok(name, entry):
                if in_chain:
                    self.console.say(SKIPPED_IN_CHAIN)
                return None
            if not entry.get("runs_command"):
                return tokens
            split = split_flags(
                tokens[index + 1:],
                entry["flags"],
                runs_command=True,
                flags_with_values=entry.get("flags_with_values", ()),
                keep_flags_whole=entry.get("keep_flags_whole", False),
            )
            if not split.inner:
                return tokens
            index = len(tokens) - len(split.inner)
            is_inner = True

    def _resolve_name(self, typed: str, is_inner: bool, in_chain: bool) -> str | None:
        """Return the command name to use, or None to drop the input (SPEC.md §4, §9).

        Order: known command, then the not-covered list, then a spelling
        suggestion (ADR 0011). An unknown command after sudo is kept, so the
        explanation can say sudo runs something it doesn't know. In a chain, a
        not-covered command is kept quietly; its block in the chain says so
        (ADR 0018).
        """
        if find_command(typed, self.commands) is not None:
            return typed  # keep the name as typed (LS, .); explain() resolves it
        kind = not_covered_kind(typed, self.not_covered)
        if kind is not None:
            if in_chain:
                return typed
            self.console.say(NOT_COVERED_MESSAGES[kind].format(name=typed))
            return typed if is_inner else None
        guess = suggest(typed, self.commands)
        if guess is not None:
            if self.console.confirm(self.palette.suggestion(f"Did you mean '{guess}'?")):
                return guess
            self.console.say(NOT_FOUND)
            return None
        if is_inner:
            return typed
        self.console.say(UNKNOWN.format(name=typed))
        return None

    def _shell_ok(self, name: str, entry: dict[str, Any]) -> bool:
        """For a command from the other shell only, ask before explaining it (SPEC.md §3.4)."""
        if self.shell in entry["shells"]:
            return True
        other = entry["shells"][0]
        return self.console.confirm(WRONG_SHELL.format(name=name, other=other, shell=self.shell))


def build_arg_parser() -> argparse.ArgumentParser:
    """Command-line options for the program."""
    parser = argparse.ArgumentParser(
        prog="commandexplain",
        description="Explains bash and zsh terminal commands in simple language.",
    )
    parser.add_argument(
        "--shell", choices=SHELLS, help="skip the shell question and use this shell"
    )
    parser.add_argument("--no-color", action="store_true", help="turn off colored output")
    return parser


def main(
    argv: Sequence[str] | None = None,
    input_fn: InputFn = input,
    print_fn: PrintFn = print,
    env: Mapping[str, str] | None = None,
    isatty: Callable[[], bool] | None = None,
) -> int:
    """Program entry point. Returns the exit code: 0 normally, 1 if the data can't be loaded.

    `isatty` says whether output goes to a terminal (default: sys.stdout.isatty).
    Colors are used only for a terminal, without NO_COLOR or --no-color.
    """
    args = build_arg_parser().parse_args(argv)
    if sys.stdout is None and input_fn is input:
        # Output was closed (commandexplain >&-), so input() can't show its prompt.
        print("Error: output is closed, so there's nowhere to show explanations.", file=sys.stderr)
        return 1
    try:
        commands = default_commands()
        not_covered = default_not_covered()
        operators = default_operators()
    except DataFileError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1
    console = Console(input_fn, print_fn)
    env = os.environ if env is None else env
    if isatty is None:  # sys.stdout can be None when output is closed (commandexplain >&-)
        isatty = getattr(sys.stdout, "isatty", None) or (lambda: False)
    palette = Palette(enabled=colors_enabled(isatty, env, args.no_color))
    session = Session(
        console, commands, not_covered, operators, env, shell=args.shell, palette=palette
    )
    return session.run()
