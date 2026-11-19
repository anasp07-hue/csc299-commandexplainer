"""Build the plain-text explanation for one command (SPEC.md §3.3)."""

from __future__ import annotations

import textwrap
from collections.abc import Sequence
from typing import Any

from commandexplain.lookup import default_commands, find_command
from commandexplain.parser import ParsedInput, parse_input, split_flags

WIDTH = 80
INDENT = "  "
MAX_LABEL = 16
SHELLS = ("bash", "zsh")

UNKNOWN_FLAG = (
    "I don't have an explanation for this option. "
    'Try "man {name}" for the full manual.'
)


class UnknownCommandError(LookupError):
    """Raised by explain() when the typed command isn't in the data."""


class EmptyInputError(ValueError):
    """Raised by explain() when there is nothing to explain."""


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


def _rows(items: Sequence[tuple[str, str]], indent: str) -> list[str]:
    """Lay out flag/explanation pairs in two aligned columns.

    A label longer than MAX_LABEL (like a made-up 80-character flag) goes on its
    own line, with its text below, so it can't squeeze the column for the others.
    """
    fitting = [len(label) for label, _ in items if len(label) <= MAX_LABEL]
    width = (max(fitting) if fitting else 0) + 3
    pad = indent + " " * width
    lines: list[str] = []
    for label, text in items:
        if len(label) <= MAX_LABEL:
            lines += _wrap(text, indent + label.ljust(width), pad)
        else:
            lines.append(indent + label)
            lines += _wrap(text, pad, pad)
    return lines


def format_explanation(
    name: str,
    entry: dict[str, Any],
    flags: Sequence[str],
    arguments: Sequence[str],
    shell: str,
    show_common: bool = True,
) -> str:
    """Return the explanation text for a known command.

    If the user typed flags, only those are explained. Otherwise the command's
    common flags are shown under "Common options", or nothing if it has none
    (ADR 0008). show_common=False leaves them out, which is used for sudo when
    it runs another command (ADR 0010). Each argument is listed on its own line
    (ADR 0012).
    """
    title = f"{name}  —  {entry['name']}"
    blocks: list[list[str]] = [[title, *_wrap(entry["summary"], INDENT, INDENT)]]

    if flags:
        unknown = UNKNOWN_FLAG.format(name=name)
        blocks.append(_rows([(flag, entry["flags"].get(flag, unknown)) for flag in flags], INDENT))
    elif show_common and entry["common_flags"]:
        common = [(flag, entry["flags"][flag]) for flag in entry["common_flags"]]
        blocks.append([f"{INDENT}Common options:", *_rows(common, INDENT * 2)])

    if arguments:
        blocks.append([f"{INDENT}argument: {argument}" for argument in arguments])

    notes: list[str] = []
    if entry.get("warning"):
        notes += _wrap(f"⚠ Careful: {entry['warning']}", INDENT, INDENT * 2)
    shell_note = entry.get("shell_notes", {}).get(shell)
    if shell_note:
        notes += _wrap(f"Note for {shell}: {shell_note}", INDENT, INDENT * 2)
    if notes:
        blocks.append(notes)

    blocks.append([f"{INDENT}Example:  {entry['example']}"])
    return "\n\n".join("\n".join(block) for block in blocks)


def _explain_parsed(parsed: ParsedInput, shell: str, commands: dict[str, dict[str, Any]]) -> str:
    """Explain an already-parsed command, plus any commands it runs (like sudo rm ...).

    Uses a loop, not recursion, so a long chain like 'sudo sudo sudo ... ls'
    can't hit Python's recursion limit.
    """
    parts: list[str] = []
    current = parsed
    wrapper: str | None = None
    while True:
        name = find_command(current.command, commands)
        if name is None:
            if wrapper is None:
                raise UnknownCommandError(current.command)
            note = f'{wrapper} runs "{current.command}", which I don\'t have an explanation for.'
            parts.append("\n".join(_wrap(note, INDENT, INDENT)))
            break

        entry = commands[name]
        if wrapper is not None:
            parts.append(f"{wrapper} runs this command:")
            if entry.get("builtin_only"):
                warning = (
                    f"⚠ Careful: {wrapper} can't run {name}, because {name} is built into "
                    "the shell. It will fail or have no effect."
                )
                parts.append("\n".join(_wrap(warning, INDENT, INDENT * 2)))

        split = split_flags(
            current.args,
            entry["flags"],
            runs_command=entry.get("runs_command", False),
            flags_with_values=entry.get("flags_with_values", ()),
            keep_flags_whole=entry.get("keep_flags_whole", False),
        )
        has_inner = bool(split.inner)
        parts.append(
            format_explanation(
                name, entry, split.flags, split.arguments, shell, show_common=not has_inner
            )
        )
        if not has_inner:
            break
        wrapper = name
        current = ParsedInput(command=split.inner[0], args=split.inner[1:])
    return "\n\n".join(parts)


def explain(text: str, shell: str, commands: dict[str, dict[str, Any]] | None = None) -> str:
    """Parse one typed command and return its explanation.

    For a command that runs another command (like sudo), the inner command is
    explained after it (ADR 0010).

    Raises EmptyInputError for blank input, ValueError for an unsupported shell,
    ParseError for text that can't be split (like an unclosed quote), and
    UnknownCommandError if the typed command isn't in the data.
    """
    if shell not in SHELLS:
        raise ValueError(f"shell must be one of {SHELLS}, not {shell!r}")
    commands = default_commands() if commands is None else commands

    parsed = parse_input(text)
    if parsed is None:
        raise EmptyInputError("there is no command to explain")
    return _explain_parsed(parsed, shell, commands)
