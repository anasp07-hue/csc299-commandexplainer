"""Tests for loading the JSON data files (SPEC.md §5 and §9)."""

from __future__ import annotations

from pathlib import Path

import pytest

from commandexplain.lookup import DataFileError, load_commands, load_operators


def test_load_commands_returns_dict_keyed_by_name() -> None:
    """The real data loads into a plain dict, and lookups by key work."""
    commands = load_commands()
    assert isinstance(commands, dict)
    assert commands["rm"]["flags"]["-r"] == "Delete folders and everything inside them."


def test_load_operators_returns_dict_keyed_by_symbol() -> None:
    """The real operator data loads into a plain dict."""
    operators = load_operators()
    assert isinstance(operators, dict)
    assert operators["|"]["name"] == "pipe"


def test_load_from_custom_path(tmp_path: Path) -> None:
    """A different data file can be passed in (used by tests and future tools)."""
    path = tmp_path / "commands.json"
    path.write_text('{"ls": {"name": "list"}}', encoding="utf-8")
    assert load_commands(path) == {"ls": {"name": "list"}}


def test_non_utf8_file_raises_clear_error(tmp_path: Path) -> None:
    """A file saved in another encoding (here Latin-1) gives a DataFileError, not a crash."""
    path = tmp_path / "latin1.json"
    path.write_bytes('{"ls": {"name": "café"}}'.encode("latin-1"))
    with pytest.raises(DataFileError, match="not UTF-8"):
        load_commands(path)


def test_duplicate_top_level_key_raises_clear_error(tmp_path: Path) -> None:
    """A command pasted in twice is reported instead of silently replacing the first."""
    path = tmp_path / "dup.json"
    path.write_text('{"cp": {"name": "a"}, "cp": {"name": "b"}}', encoding="utf-8")
    with pytest.raises(DataFileError, match="'cp' more than once"):
        load_commands(path)


def test_duplicate_nested_key_raises_clear_error(tmp_path: Path) -> None:
    """Repeated keys inside an entry (like two '-r' flags) are caught too."""
    path = tmp_path / "dup.json"
    path.write_text('{"rm": {"flags": {"-r": "a", "-r": "b"}}}', encoding="utf-8")
    with pytest.raises(DataFileError, match="'-r' more than once"):
        load_commands(path)


def test_entry_that_is_not_an_object_raises_clear_error(tmp_path: Path) -> None:
    """Each command's value must itself be key-value pairs."""
    path = tmp_path / "bad_entry.json"
    path.write_text('{"ls": "list"}', encoding="utf-8")
    with pytest.raises(DataFileError, match="entry for 'ls' must be a JSON object"):
        load_commands(path)


def test_missing_file_raises_clear_error(tmp_path: Path) -> None:
    """A missing file gives a DataFileError that names the file."""
    path = tmp_path / "nope.json"
    with pytest.raises(DataFileError, match="not found") as excinfo:
        load_commands(path)
    assert "nope.json" in str(excinfo.value)


def test_invalid_json_raises_clear_error(tmp_path: Path) -> None:
    """Broken JSON gives a DataFileError with the line number, not a raw JSONDecodeError."""
    path = tmp_path / "bad.json"
    path.write_text('{"ls": {"name": "list",}}', encoding="utf-8")
    with pytest.raises(DataFileError, match=r"not valid JSON \(line 1"):
        load_operators(path)


@pytest.mark.parametrize("content", ["[]", '"text"', "42", "null"])
def test_non_object_json_raises_clear_error(tmp_path: Path, content: str) -> None:
    """The top level must be key-value pairs (a JSON object)."""
    path = tmp_path / "list.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(DataFileError, match="JSON object"):
        load_commands(path)


def test_unreadable_path_raises_clear_error(tmp_path: Path) -> None:
    """A path that can't be read as a file (here, a folder) gives a DataFileError."""
    with pytest.raises(DataFileError, match="Could not read"):
        load_commands(tmp_path)
