"""Build the explanation text for a command or a chain (SPEC.md §3.3, §3.3.1).

Text is laid out and wrapped first, and colors (SPEC.md §3.3.2) are added
afterwards, so color codes never affect line widths.
"""

from __future__ import annotations

import textwrap
from collections.abc import Callable, Sequence
from typing import Any

from commandexplain.colors import PLAIN, Palette
from commandexplain.lookup import (
    default_commands,
    default_not_covered,
    default_operators,
    find_command,
    not_covered_kind,
)
from commandexplain.parser import Chain, ChainCommand, SplitArgs, parse_chain, split_flags
from commandexplain.shell import SHELLS

Data = dict[str, dict[str, Any]]

WIDTH = 80
INDENT = "  "
MAX_LABEL = 16

UNKNOWN_FLAG = (
    "I don't have an explanation for this option. "
    'Try "man {name}" for the full manual.'
)
NOT_COVERED_MESSAGES = {
    "tool": "'{name}' isn't a built-in terminal command, so it isn't covered.",
    "uncovered": "'{name}' is a real command, but I don't cover it yet.",
}


class UnknownCommandError(LookupError):
    """Raised by explain() when a typed command isn't in the data."""


class EmptyInputError(ValueError):
    """Raised by explain() when there is nothing to explain."""


# --- Shared layout helpers -----------------------------------------------


def _wrap(text: str, first_prefix: str, next_prefix: str) -> list[str]:
    """Wrap text to WIDTH columns, starting the first line and the rest with the given prefixes."""
    return textwrap.wrap(
        text,
        width=WIDTH,
        initial_indent=first_prefix,
        subsequent_indent=next_prefix,
        break_on_hyphens=False,
        break_long_words=False,
    )


def _paint_start(line: str, prefix: str, word: str, paint: Callable[[str], str]) -> str:
    """Color `word` where it sits right after `prefix` at the start of an already-wrapped line."""
    start = prefix + word
    if not line.startswith(start):
        return line
    return prefix + paint(word) + line[len(start):]


def _paint_lines(lines: list[str], paint: Callable[[str], str]) -> list[str]:
    """Color whole wrapped lines (after their indent), for warnings."""
    painted: list[str] = []
    for line in lines:
        body = line.lstrip(" ")
        painted.append(line[: len(line) - len(body)] + paint(body))
    return painted


def _rows(
    items: Sequence[tuple[str, str]], indent: str, palette: Palette = PLAIN
) -> list[str]:
    """Lay out flag/explanation pairs in two aligned columns, with the flags colored.

    A label longer than MAX_LABEL (like a made-up 80-character flag) goes on its
    own line, with its text below, so it can't squeeze the column for the others.
    """
    fitting = [len(label) for label, _ in items if len(label) <= MAX_LABEL]
    width = (max(fitting) if fitting else 0) + 3
    pad = indent + " " * width
    lines: list[str] = []
    for label, text in items:
        if len(label) <= MAX_LABEL:
            row = _wrap(text, indent + label.ljust(width), pad)
        else:
            row = [indent + label, *_wrap(text, pad, pad)]
        row[0] = _paint_start(row[0], indent, label, palette.flag)
        lines += row
    return lines


def _typed_flag_rows(
    name: str, entry: dict[str, Any], flags: Sequence[str], indent: str, palette: Palette
) -> list[str]:
    """Rows for the flags the user typed, with a pointer to man for unknown ones."""
    unknown = UNKNOWN_FLAG.format(name=name)
    rows = [(flag, entry["flags"].get(flag, unknown)) for flag in flags]
    return _rows(rows, indent, palette)


def _argument_lines(arguments: Sequence[str], indent: str) -> list[str]:
    """One 'argument:' line per argument (ADR 0012)."""
    return [f"{indent}argument: {argument}" for argument in arguments]


def _warning_lines(text: str, palette: Palette) -> list[str]:
    """A '⚠ Careful:' warning, wrapped and colored."""
    return _paint_lines(_wrap(f"⚠ Careful: {text}", INDENT, INDENT * 2), palette.warning)


def _notes(entry: dict[str, Any], shell: str, palette: Palette) -> list[str]:
    """The warning and the shell note for the user's shell, if the command has them."""
    lines: list[str] = []
    if entry.get("warning"):
        lines += _warning_lines(entry["warning"], palette)
    shell_note = entry.get("shell_notes", {}).get(shell)
    if shell_note:
        lines += _wrap(f"Note for {shell}: {shell_note}", INDENT, INDENT * 2)
    return lines


def _builtin_warning(wrapper: str, name: str, palette: Palette) -> list[str]:
    """Warning that sudo can't run a shell builtin like cd (ADR 0013)."""
    text = (
        f"{wrapper} can't run {name}, because {name} is built into "
        "the shell. It will fail or have no effect."
    )
    return _warning_lines(text, palette)


def _split(entry: dict[str, Any], args: Sequence[str]) -> SplitArgs:
    """Split a command's words using the flag rules from its data entry."""
    return split_flags(
        args,
        entry["flags"],
        runs_command=entry.get("runs_command", False),
        flags_with_values=entry.get("flags_with_values", ()),
        keep_flags_whole=entry.get("keep_flags_whole", False),
    )


# --- Single command (SPEC.md §3.3) ---------------------------------------


def format_explanation(
    name: str,
    entry: dict[str, Any],
    flags: Sequence[str],
    arguments: Sequence[str],
    shell: str,
    show_common: bool = True,
    palette: Palette = PLAIN,
) -> str:
    """Return the full explanation text for a known command.

    If the user typed flags, only those are explained. Otherwise the command's
    common flags are shown under "Common options", or nothing if it has none
    (ADR 0008). show_common=False leaves them out, which is used for sudo when
    it runs another command (ADR 0010). Each argument is listed on its own line
    (ADR 0012).
    """
    title = f"{palette.command(name)}  —  {entry['name']}"
    blocks: list[list[str]] = [[title, *_wrap(entry["summary"], INDENT, INDENT)]]

    if flags:
        blocks.append(_typed_flag_rows(name, entry, flags, INDENT, palette))
    elif show_common and entry["common_flags"]:
        common = [(flag, entry["flags"][flag]) for flag in entry["common_flags"]]
        blocks.append([f"{INDENT}Common options:", *_rows(common, INDENT * 2, palette)])

    if arguments:
        blocks.append(_argument_lines(arguments, INDENT))
    notes = _notes(entry, shell, palette)
    if notes:
        blocks.append(notes)

    blocks.append([f"{INDENT}Example:  {entry['example']}"])
    return "\n\n".join("\n".join(block) for block in blocks)


def _explain_single(
    tokens: Sequence[str], shell: str, commands: Data, palette: Palette = PLAIN
) -> str:
    """Explain one command, plus any commands it runs (like sudo rm ...).

    Uses a loop, not recursion, so a long chain like 'sudo sudo sudo ... ls'
    can't hit Python's recursion limit.
    """
    parts: list[str] = []
    current = list(tokens)
    wrapper: str | None = None
    while True:
        name = find_command(current[0], commands)
        if name is None:
            if wrapper is None:
                raise UnknownCommandError(current[0])
            note = f'{wrapper} runs "{current[0]}", which I don\'t have an explanation for.'
            parts.append("\n".join(_wrap(note, INDENT, INDENT)))
            break

        entry = commands[name]
        if wrapper is not None:
            parts.append(f"{wrapper} runs this command:")
            if entry.get("builtin_only"):
                parts.append("\n".join(_builtin_warning(wrapper, name, palette)))

        split = _split(entry, current[1:])
        has_inner = bool(split.inner)
        parts.append(
            format_explanation(
                name,
                entry,
                split.flags,
                split.arguments,
                shell,
                show_common=not has_inner,
                palette=palette,
            )
        )
        if not has_inner:
            break
        wrapper = name
        current = list(split.inner)
    return "\n\n".join(parts)


# --- Chains (SPEC.md §3.3.1) ---------------------------------------------


def _chain_command_block(
    command: ChainCommand,
    shell: str,
    commands: Data,
    not_covered: Data,
    palette: Palette = PLAIN,
) -> tuple[list[str], str | None]:
    """Explain one command inside a chain, in the short chain format (ADR 0018).

    Returns the lines and the command's "In short" phrase (None if it has none,
    for example because the command isn't covered).
    """
    lines = [command.display()]
    current = list(command.tokens)
    wrappers: list[str] = []
    while True:
        name = find_command(current[0], commands)
        if name is None:
            kind = not_covered_kind(current[0], not_covered)
            if kind is not None:
                if wrappers:
                    lines.append(f"{INDENT}{wrappers[-1]} runs this command:")
                message = NOT_COVERED_MESSAGES[kind].format(name=current[0])
            elif wrappers:
                message = (
                    f'{wrappers[-1]} runs "{current[0]}", '
                    "which I don't have an explanation for."
                )
            else:
                raise UnknownCommandError(current[0])
            lines += _wrap(message, INDENT, INDENT)
            return lines, None

        entry = commands[name]
        if wrappers:
            lines.append(f"{INDENT}{wrappers[-1]} runs this command:")
            if entry.get("builtin_only"):
                lines += _builtin_warning(wrappers[-1], name, palette)
        split = _split(entry, current[1:])
        summary = _wrap(f"{name} — {entry['name']}: {entry['summary']}", INDENT, INDENT * 2)
        summary[0] = _paint_start(summary[0], INDENT, name, palette.command)
        lines += summary
        lines += _typed_flag_rows(name, entry, split.flags, INDENT * 2, palette)
        lines += _argument_lines(split.arguments, INDENT * 2)
        lines += _notes(entry, shell, palette)
        if not split.inner:
            phrase = entry.get("short")
            if wrappers and entry.get("builtin_only"):
                phrase = None  # sudo can't run it, so "cd (using sudo)" wouldn't be true
            elif phrase and wrappers:
                phrase = f"{phrase} (using {wrappers[0]})"
            return lines, phrase
        wrappers.append(name)
        current = list(split.inner)


def _operator_block(
    symbol: str, operators: Data, target: str | None = None, palette: Palette = PLAIN
) -> list[str]:
    """Explain one operator, with the file it uses if it's a redirect."""
    entry = operators[symbol]
    header = f"{palette.operator(symbol)}  ({entry['name']})"
    lines = [header, *_wrap(entry["summary"], INDENT, INDENT)]
    if target is not None:
        lines.append(f"{INDENT}file: {target}")
    if entry.get("warning"):
        lines += _warning_lines(entry["warning"], palette)
    return lines


def _in_short(chain: Chain, phrases: Sequence[str | None], operators: Data) -> str | None:
    """Build the one-line "In short" summary, or None if it can't be said truthfully (ADR 0018).

    It's left out if any command has no phrase, or if output saved with > or >>
    is also piped on or saved to a second file, because bash and zsh behave
    differently there.
    """
    if any(phrase is None for phrase in phrases):
        return None
    for index, command in enumerate(chain.commands):
        saves = sum(redirect.operator in (">", ">>") for redirect in command.redirects)
        piped_on = index < len(chain.joiners) and chain.joiners[index] == "|"
        if saves > 1 or (saves and piped_on):
            return None
    pieces: list[str] = []
    for index, (command, phrase) in enumerate(zip(chain.commands, phrases)):
        piece = str(phrase)
        if index:
            piece = f"{operators[chain.joiners[index - 1]]['short']} {piece}"
        pieces.append(piece)
        for redirect in command.redirects:
            pieces.append(operators[redirect.operator]["short"].format(file=redirect.target))
    return f"In short: {', '.join(pieces)}."


def _explain_chain(
    chain: Chain,
    shell: str,
    commands: Data,
    operators: Data,
    not_covered: Data,
    palette: Palette = PLAIN,
) -> str:
    """Explain each command and operator in order, then the "In short" line (SPEC.md §3.3.1)."""
    blocks: list[list[str]] = []
    phrases: list[str | None] = []
    for index, command in enumerate(chain.commands):
        if index:
            blocks.append(_operator_block(chain.joiners[index - 1], operators, palette=palette))
        lines, phrase = _chain_command_block(command, shell, commands, not_covered, palette)
        blocks.append(lines)
        phrases.append(phrase)
        for redirect in command.redirects:
            blocks.append(
                _operator_block(redirect.operator, operators, redirect.target, palette)
            )

    summary = _in_short(chain, phrases, operators)
    if summary:
        blocks.append(_wrap(summary, "", INDENT))
    return "\n\n".join("\n".join(block) for block in blocks)


# --- Entry point ---------------------------------------------------------


def explain(
    text: str,
    shell: str,
    commands: Data | None = None,
    operators: Data | None = None,
    not_covered: Data | None = None,
    palette: Palette = PLAIN,
) -> str:
    """Parse typed text and return its explanation, colored with `palette` (plain by default).

    A single command gets the full format (SPEC.md §3.3). Anything with an
    operator (|, &&, ||, ;, >, >>, <) gets the chain format (SPEC.md §3.3.1).
    A command run by sudo is explained after it (ADR 0010).

    Raises EmptyInputError for blank input, ValueError for an unsupported shell,
    ParseError for text that can't be split, and UnknownCommandError if a
    command isn't in the data or on the not-covered list.
    """
    if shell not in SHELLS:
        raise ValueError(f"shell must be one of {SHELLS}, not {shell!r}")
    commands = default_commands() if commands is None else commands

    chain = parse_chain(text)
    if chain is None:
        raise EmptyInputError("there is no command to explain")
    if chain.is_single:
        return _explain_single(chain.commands[0].tokens, shell, commands, palette)
    operators = default_operators() if operators is None else operators
    not_covered = default_not_covered() if not_covered is None else not_covered
    return _explain_chain(chain, shell, commands, operators, not_covered, palette)
