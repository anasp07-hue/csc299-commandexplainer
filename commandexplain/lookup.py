"""Load command and operator data from the JSON key-value files."""

from __future__ import annotations

import difflib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).parent / "data"
COMMANDS_FILE = DATA_DIR / "commands.json"
OPERATORS_FILE = DATA_DIR / "operators.json"
NOT_COVERED_FILE = DATA_DIR / "not_covered.json"


class DataFileError(Exception):
    """Raised when a data file is missing or can't be read as a JSON object."""


class _DuplicateKeyError(ValueError):
    """Internal: a JSON object repeats a key. Turned into DataFileError by the loader."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build a dict from JSON key-value pairs, refusing repeated keys.

    Plain json.loads keeps only the last of two identical keys, which would let a
    hand-edited data file silently lose an entry.
    """
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError(key)
        result[key] = value
    return result


def _read_text(path: Path) -> str:
    """Read a UTF-8 text file, raising DataFileError on any problem."""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise DataFileError(f"Data file not found: {path}") from None
    except UnicodeDecodeError as err:
        raise DataFileError(f"Data file {path} is not UTF-8 text: {err}") from None
    except OSError as err:
        raise DataFileError(f"Could not read data file {path}: {err}") from None


def _load_json_object(path: Path) -> dict[str, dict[str, Any]]:
    """Read a JSON file of entries and return it as a dict of dicts.

    Raises DataFileError if the file is missing, unreadable, not valid JSON,
    repeats a key, or isn't an object whose values are all objects.
    """
    text = _read_text(path)
    try:
        data = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except json.JSONDecodeError as err:
        raise DataFileError(
            f"Data file {path} is not valid JSON "
            f"(line {err.lineno}, column {err.colno}: {err.msg})"
        ) from None
    except _DuplicateKeyError as err:
        raise DataFileError(f"Data file {path} has the key '{err}' more than once") from None

    if not isinstance(data, dict):
        raise DataFileError(
            f"Data file {path} must contain a JSON object (key-value pairs) "
            "at the top level"
        )
    for key, entry in data.items():
        if not isinstance(entry, dict):
            raise DataFileError(f"Data file {path}: the entry for '{key}' must be a JSON object")
    return data


def load_commands(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Return all command entries, keyed by command name."""
    return _load_json_object(path or COMMANDS_FILE)


def load_operators(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Return all operator entries (|, &&, >, ...), keyed by the operator symbol."""
    return _load_json_object(path or OPERATORS_FILE)


def load_not_covered(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Return names that are known but not explained (git, unset, ...), keyed by name.

    Each entry's "kind" is "tool" (a separate program, not part of the terminal)
    or "uncovered" (a real terminal command this version doesn't explain yet).
    """
    return _load_json_object(path or NOT_COVERED_FILE)


@lru_cache(maxsize=1)
def default_operators() -> dict[str, dict[str, Any]]:
    """The shipped operator data, read from disk only once per run (read-only)."""
    return load_operators()


@lru_cache(maxsize=1)
def default_not_covered() -> dict[str, dict[str, Any]]:
    """The shipped not-covered list, read from disk only once per run (read-only)."""
    return load_not_covered()


@lru_cache(maxsize=1)
def default_commands() -> dict[str, dict[str, Any]]:
    """The shipped command data, read from disk only once per run.

    Callers must treat the result as read-only, since every caller shares it.
    """
    return load_commands()


# --- Finding commands -----------------------------------------------------

MIN_SUGGEST_LENGTH = 2
SUGGEST_CUTOFF = 0.75


def _alias_map(commands: dict[str, dict[str, Any]]) -> dict[str, str]:
    """Map every alias to the command it belongs to ('.' -> 'source')."""
    return {
        alias: name
        for name, entry in commands.items()
        for alias in entry.get("aliases", [])
    }


def find_command(
    name: str, commands: dict[str, dict[str, Any]] | None = None
) -> str | None:
    """Return the data key for a typed command name, or None if it isn't known.

    Matching ignores case and surrounding spaces, and aliases resolve to their
    command ('.' -> 'source').
    """
    commands = default_commands() if commands is None else commands
    key = name.strip().lower()
    if key in commands:
        return key
    return _alias_map(commands).get(key)


def is_one_edit(a: str, b: str) -> bool:
    """True if b is exactly one edit away from a (ADR 0006).

    An edit is one letter added, removed, or changed, or two neighboring
    letters swapped (sl -> ls).
    """
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        diffs = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
        if len(diffs) == 1:
            return True
        if len(diffs) == 2:
            i, j = diffs
            return j == i + 1 and a[i] == b[j] and a[j] == b[i]
        return False
    shorter, longer = sorted((a, b), key=len)
    for i, (x, y) in enumerate(zip(shorter, longer)):
        if x != y:
            return shorter[i:] == longer[i + 1:]
    return True


def _similarity(a: str, b: str) -> float:
    """How alike two words are, from 0.0 to 1.0 (difflib's ratio)."""
    return difflib.SequenceMatcher(None, a, b).ratio()


def _has_letter(text: str) -> bool:
    """True if the text contains at least one letter."""
    return any(char.isalpha() for char in text)


def suggest(name: str, commands: dict[str, dict[str, Any]] | None = None) -> str | None:
    """Return the closest known command name or alias for a typo, or None (SPEC.md §4).

    Step 1: names one edit away, best difflib ratio first, ties alphabetical.
    Step 2: otherwise difflib.get_close_matches with cutoff 0.75.
    Only input with a letter gets a suggestion, and only names with a letter are
    suggested, so '..' doesn't turn into '.' (ADR 0011). Names that are already
    known, and input shorter than 2 characters, get None.
    """
    commands = default_commands() if commands is None else commands
    aliases = _alias_map(commands)
    word = name.strip().lower()
    if len(word) < MIN_SUGGEST_LENGTH or not _has_letter(word):
        return None
    if word in commands or word in aliases:
        return None

    names = sorted(candidate for candidate in [*commands, *aliases] if _has_letter(candidate))
    close = [candidate for candidate in names if is_one_edit(word, candidate)]
    if close:
        return min(close, key=lambda candidate: (-_similarity(word, candidate), candidate))
    matches = difflib.get_close_matches(word, names, n=1, cutoff=SUGGEST_CUTOFF)
    return matches[0] if matches else None


def not_covered_kind(
    name: str, not_covered: dict[str, dict[str, Any]] | None = None
) -> str | None:
    """Return "tool" or "uncovered" if the name is on the not-covered list, else None.

    The CLI checks this before suggesting spellings, so 'unset' isn't turned
    into 'unsetopt' (ADR 0011).
    """
    not_covered = default_not_covered() if not_covered is None else not_covered
    entry = not_covered.get(name.strip().lower())
    return entry["kind"] if entry else None
