"""Split typed text into commands, operators, flags, and arguments (SPEC.md §3.2).

parse_chain() splits a whole line at pipes and chains (|, &&, ||, ;) and
redirects (>, >>, <). split_flags() then sorts one command's words into flags,
arguments, and the command that sudo runs.
"""

from __future__ import annotations

import shlex
from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass, field


class ParseError(Exception):
    """Raised when the typed text can't be split into words.

    `reason` says what went wrong, so the CLI can show the right message:
    UNCLOSED_QUOTE (echo "hi), TRAILING_BACKSLASH (echo hi\\), EMPTY_COMMAND
    ('' -l), MISSING_BEFORE / MISSING_AFTER (| grep, ls &&), or UNSUPPORTED
    (&, 2>, $( ...), ADR 0019). `detail` holds the operator involved, if any.
    Deliberately not a ValueError, so callers can't mix it up with blank input.
    """

    UNCLOSED_QUOTE = "unclosed_quote"
    TRAILING_BACKSLASH = "trailing_backslash"
    EMPTY_COMMAND = "empty_command"
    MISSING_BEFORE = "missing_before"
    MISSING_AFTER = "missing_after"
    UNSUPPORTED = "unsupported"

    def __init__(self, reason: str, message: str, detail: str = "") -> None:
        """Store the reason code and detail alongside the human-readable message."""
        super().__init__(message)
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True)
class SplitArgs:
    """The words after a command, sorted into flags, plain arguments, and an inner command.

    `inner` is only filled for commands that run another command, like sudo
    (ADR 0010): sudo -u bob ls -l gives flags ('-u',), arguments ('bob',),
    and inner ('ls', '-l').
    """

    flags: tuple[str, ...]
    arguments: tuple[str, ...]
    inner: tuple[str, ...] = ()


def _normalize_spaces(text: str) -> str:
    """Turn any Unicode space (like the non-breaking spaces web pages use) into a plain space."""
    return "".join(" " if char.isspace() else char for char in text)


def tokenize(text: str) -> list[str]:
    """Split text into words the way a shell would, keeping quoted text together."""
    try:
        return shlex.split(_normalize_spaces(text))
    except ValueError as err:
        message = str(err)
        if "escaped" in message:
            reason = ParseError.TRAILING_BACKSLASH
        else:
            reason = ParseError.UNCLOSED_QUOTE
        raise ParseError(reason, message) from None


def _is_plain(token: str) -> bool:
    """True for words that aren't flags: anything not starting with '-', a lone '-', or '--=x'."""
    return not token.startswith("-") or token == "-" or token.split("=", 1)[0] == "--"


def _flags_in_token(token: str, known_flags: Collection[str], keep_whole: bool) -> list[str]:
    """Return the flag(s) a single dash-token stands for (SPEC.md §3.2 step 5, ADR 0009).

    keep_whole=True never splits a group (used for kill, whose -INT and -SIGKILL
    are signal names, not letter groups; ADR 0014).
    """
    if token.startswith("--"):
        return [token.split("=", 1)[0]]
    if keep_whole or token in known_flags or token[1:].isdigit():
        return [token]
    return [f"-{letter}" for letter in token[1:]]


def _unique(items: Iterable[str]) -> tuple[str, ...]:
    """Remove repeats while keeping the original order."""
    return tuple(dict.fromkeys(items))


def split_flags(
    args: Iterable[str],
    known_flags: Collection[str],
    *,
    runs_command: bool = False,
    flags_with_values: Collection[str] = (),
    keep_flags_whole: bool = False,
) -> SplitArgs:
    """Sort a command's words into flags and arguments.

    - A word matching a known flag exactly (like find's -name) is one flag (ADR 0007).
    - Other single-dash groups are split: -rf becomes -r and -f.
    - Numbers like -15 stay whole, and --name=value counts as --name (ADR 0009).
    - A lone - is an argument, and everything after -- is an argument.
    - Repeated flags (-ll) are listed once.
    - For a command that runs another command (runs_command, like sudo), flag
      reading stops at the first plain word, and that word plus everything after
      it becomes `inner`. A flag in flags_with_values takes the next word as its
      value, which is listed as an argument (ADR 0010).
    - keep_flags_whole never splits single-dash groups (ADR 0014).
    """
    tokens = list(args)
    flags: list[str] = []
    arguments: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == "--":
            rest = tuple(tokens[index + 1:])
            if runs_command:
                return SplitArgs(_unique(flags), tuple(arguments), rest)
            arguments.extend(rest)
            break
        if _is_plain(token):
            if runs_command:
                return SplitArgs(_unique(flags), tuple(arguments), tuple(tokens[index:]))
            arguments.append(token)
        else:
            found = _flags_in_token(token, known_flags, keep_flags_whole)
            flags.extend(found)
            has_value = "=" in token  # --user=bob already carries its value
            if found[-1] in flags_with_values and not has_value and index + 1 < len(tokens):
                index += 1
                arguments.append(tokens[index])
        index += 1
    return SplitArgs(flags=_unique(flags), arguments=tuple(arguments))


# --- Pipes, chains, and redirects (SPEC.md §3.2 steps 1-2, Phase 4) -------

JOINERS = ("|", "&&", "||", ";")
REDIRECTS = (">", ">>", "<")
# Longest first, so '>>' isn't read as two '>'.
_OPERATORS = (">>", "&&", "||", "|", ";", ">", "<")
# Shell syntax this version doesn't explain (ADR 0019). Checked before _OPERATORS.
_UNSUPPORTED = ("<<<", "<<", ">&", ">|", "&>", "|&", "&", "(", ")", "`", "$(")
# Characters after which a number starts a new word (so '2>' is a numbered redirect).
_WORD_BREAKS = " |;&<>"


@dataclass(frozen=True)
class Redirect:
    """A redirect attached to a command: '> out.txt' is Redirect('>', 'out.txt')."""

    operator: str
    target: str


@dataclass(frozen=True)
class ChainCommand:
    """One command in a chain: its words, any redirects, and the text as the user typed it.

    `text` keeps the user's own quoting ($HOME stays $HOME, not '$HOME'), so it
    can be shown back to them. It isn't part of equality checks.
    """

    tokens: tuple[str, ...]
    redirects: tuple[Redirect, ...] = ()
    text: str = field(default="", compare=False)

    def display(self) -> str:
        """The command as the user typed it, or rebuilt from its words if that's unknown."""
        if self.text:
            return self.text
        parts = [shlex.join(self.tokens)]
        for redirect in self.redirects:
            parts += [redirect.operator, shlex.quote(redirect.target)]
        return " ".join(parts)


@dataclass(frozen=True)
class Chain:
    """A whole typed line: commands in order, and the joiners (|, &&, ||, ;) between them.

    There is always exactly one fewer joiner than commands.
    """

    commands: tuple[ChainCommand, ...]
    joiners: tuple[str, ...] = ()

    @property
    def is_single(self) -> bool:
        """True for a plain single command with no operators at all."""
        return len(self.commands) == 1 and not self.commands[0].redirects


def _unsupported_at(text: str, index: int) -> str | None:
    """Return the unsupported syntax starting at index (outside quotes), if any."""
    for syntax in _UNSUPPORTED:
        if text.startswith(syntax, index):
            if syntax == "&" and text.startswith("&&", index):
                return None
            return syntax
    char = text[index]
    starts_word = index == 0 or text[index - 1] in _WORD_BREAKS
    if char == "#" and starts_word:
        return "#"  # a comment in bash, a plain word in zsh (ADR 0019)
    if char.isdigit() and starts_word:
        end = index
        while end < len(text) and text[end].isdigit():
            end += 1
        if end < len(text) and text[end] in "<>":
            return text[index:end + 1]  # a numbered redirect like 2> (ADR 0019)
    return None


def split_operators(text: str) -> list[str]:
    """Split raw text at operators that aren't quoted or escaped.

    Returns pieces that alternate between command text and operators, always
    starting and ending with command text (which may be empty): 'ls | wc' gives
    ['ls ', '|', ' wc']. Raises ParseError for unclosed quotes, a trailing
    backslash, or unsupported syntax.
    """
    text = _normalize_spaces(text)
    pieces: list[str] = []
    current: list[str] = []
    quote = ""
    index = 0
    while index < len(text):
        char = text[index]
        if char == "\\" and quote != "'":
            if index + 1 >= len(text):
                raise ParseError(ParseError.TRAILING_BACKSLASH, "No escaped character")
            current.append(text[index:index + 2])
            index += 2
            continue
        if quote:
            if char == quote:
                quote = ""
            elif quote == '"' and (char == "`" or text.startswith("$(", index)):
                syntax = "`" if char == "`" else "$("
                raise ParseError(ParseError.UNSUPPORTED, f"unsupported: {syntax}", syntax)
            current.append(char)
            index += 1
            continue
        if char in "'\"":
            quote = char
            current.append(char)
            index += 1
            continue
        syntax = _unsupported_at(text, index)
        if syntax:
            raise ParseError(ParseError.UNSUPPORTED, f"unsupported: {syntax}", syntax)
        operator = next((op for op in _OPERATORS if text.startswith(op, index)), None)
        if operator:
            pieces += ["".join(current), operator]
            current = []
            index += len(operator)
            continue
        current.append(char)
        index += 1
    if quote:
        raise ParseError(ParseError.UNCLOSED_QUOTE, "No closing quotation")
    pieces.append("".join(current))
    return pieces


def _missing(where: str, operator: str) -> ParseError:
    """Build the error for an operator with nothing on one side."""
    reason = ParseError.MISSING_BEFORE if where == "before" else ParseError.MISSING_AFTER
    return ParseError(reason, f"something is missing {where} {operator!r}", operator)


def parse_chain(text: str) -> Chain | None:
    """Split a typed line into commands, joiners, and redirects. Returns None for blank input.

    - Joiners (|, &&, ||, ;) separate commands. A ';' at the very end is allowed.
    - After a redirect (>, >>, <), the first word is the file. Any words after
      it still belong to the command before the redirect, as in a real shell.
    - An operator with nothing on one side raises ParseError (MISSING_BEFORE or
      MISSING_AFTER), as does a command name that is empty.
    """
    pieces = split_operators(text)
    if len(pieces) == 1 and not pieces[0].strip():
        return None
    if len(pieces) > 1 and not pieces[0].strip():
        raise _missing("before", pieces[1])
    if len(pieces) >= 3 and pieces[-2] == ";" and not pieces[-1].strip():
        pieces = pieces[:-2]  # 'ls;' is fine in a shell

    commands: list[ChainCommand] = []
    joiners: list[str] = []
    redirects: list[Redirect] = []
    tokens = tokenize(pieces[0])
    raw = pieces[0]
    for operator, piece in zip(pieces[1::2], pieces[2::2]):
        words = tokenize(piece)
        if not words:
            raise _missing("after", operator)
        if operator in REDIRECTS:
            redirects.append(Redirect(operator, words[0]))
            tokens += words[1:]
            raw += operator + piece
            continue
        commands.append(ChainCommand(tuple(tokens), tuple(redirects), raw.strip()))
        joiners.append(operator)
        tokens, redirects, raw = words, [], piece
    commands.append(ChainCommand(tuple(tokens), tuple(redirects), raw.strip()))

    for command in commands:
        if not command.tokens[0]:
            raise ParseError(ParseError.EMPTY_COMMAND, "the command name is empty")
    return Chain(tuple(commands), tuple(joiners))


def chain_to_text(chain: Chain) -> str:
    """Turn a Chain back into text that parse_chain() reads the same way.

    Uses each command's own typed text where it's known, so the user's quoting
    is kept.
    """
    parts: list[str] = []
    for index, command in enumerate(chain.commands):
        if index:
            parts.append(chain.joiners[index - 1])
        parts.append(command.display())
    return " ".join(parts)


def _word_spans(text: str) -> list[tuple[int, int]]:
    """Start and end of each command word in one command's typed text.

    Redirect operators and their file names are skipped, so the spans line up
    one-to-one with ChainCommand.tokens.
    """
    spans: list[tuple[int, int]] = []
    index = 0
    skip_next = False
    while index < len(text):
        if text[index] == " ":
            index += 1
            continue
        if text[index] in "<>":
            index += 2 if text.startswith(">>", index) else 1
            skip_next = True
            continue
        start = index
        quote = ""
        while index < len(text):
            char = text[index]
            if char == "\\" and quote != "'":
                index += 2
                continue
            if quote:
                quote = "" if char == quote else quote
            elif char in "'\"":
                quote = char
            elif char == " " or char in "<>":
                break
            index += 1
        if skip_next:
            skip_next = False
        else:
            spans.append((start, min(index, len(text))))
    return spans


def retype(command: ChainCommand, tokens: Sequence[str]) -> ChainCommand:
    """Return the command with new words, changing only those words in its typed text.

    Used for accepted spelling fixes: 'sl -la "$HOME"' with 'ls' becomes
    'ls -la "$HOME"', keeping the user's own quoting everywhere else.
    """
    tokens = tuple(tokens)
    spans = _word_spans(command.text)
    if not command.text or len(spans) != len(command.tokens):
        return ChainCommand(tokens, command.redirects)
    text = command.text
    for (start, end), old, new in reversed(list(zip(spans, command.tokens, tokens))):
        if old != new:
            text = text[:start] + shlex.quote(new) + text[end:]
    return ChainCommand(tokens, command.redirects, text)
