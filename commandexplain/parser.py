"""Split a single typed command into its command name, flags, and arguments.

Pipes and chains (|, &&, ...) are handled in Phase 4. This module only deals with
one command at a time (SPEC.md §3.2, steps 3-7).
"""

from __future__ import annotations

import shlex
from collections.abc import Collection, Iterable
from dataclasses import dataclass


class ParseError(Exception):
    """Raised when the typed text can't be split into words.

    `reason` says what went wrong, so the CLI can show the right message:
    UNCLOSED_QUOTE (echo "hi), TRAILING_BACKSLASH (echo hi\\), or
    EMPTY_COMMAND ('' -l). Deliberately not a ValueError, so callers can't mix
    it up with blank input.
    """

    UNCLOSED_QUOTE = "unclosed_quote"
    TRAILING_BACKSLASH = "trailing_backslash"
    EMPTY_COMMAND = "empty_command"

    def __init__(self, reason: str, message: str) -> None:
        """Store the reason code alongside the human-readable message."""
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True)
class ParsedInput:
    """A typed command split into its name and the raw words after it."""

    command: str
    args: tuple[str, ...]


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


def parse_input(text: str) -> ParsedInput | None:
    """Split typed text into a command and its raw arguments. Returns None for blank input."""
    tokens = tokenize(text)
    if not tokens:
        return None
    if not tokens[0]:
        raise ParseError(ParseError.EMPTY_COMMAND, "the command name is empty")
    return ParsedInput(command=tokens[0], args=tuple(tokens[1:]))


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
