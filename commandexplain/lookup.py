"""Load command and operator data from the JSON key-value files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).parent / "data"
COMMANDS_FILE = DATA_DIR / "commands.json"
OPERATORS_FILE = DATA_DIR / "operators.json"


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
