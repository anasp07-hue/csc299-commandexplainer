"""Tests for loading the JSON data files (SPEC.md §5 and §9)."""

from __future__ import annotations

from pathlib import Path

import pytest

from commandexplain.lookup import (
    DataFileError,
    default_commands,
    find_command,
    is_one_edit,
    load_commands,
    load_operators,
    suggest,
)


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


# --- find_command ---------------------------------------------------------

FAKE = {
    "ls": {"aliases": []},
    "cd": {"aliases": []},
    "cat": {"aliases": []},
    "source": {"aliases": ["."]},
}


@pytest.mark.parametrize(
    ("typed", "expected"),
    [("ls", "ls"), ("LS", "ls"), ("  cd ", "cd"), (".", "source"), ("Source", "source")],
)
def test_find_command_matches_case_spaces_and_aliases(typed: str, expected: str) -> None:
    """Lookup ignores case and spaces, and aliases resolve to their command."""
    assert find_command(typed, FAKE) == expected


@pytest.mark.parametrize("typed", ["sl", "git", "", "l s"])
def test_find_command_unknown_gives_none(typed: str) -> None:
    """Unknown names give None, not an error."""
    assert find_command(typed, FAKE) is None


def test_find_command_uses_real_data_by_default() -> None:
    """Without a commands dict, the shipped data is used."""
    assert find_command("Grep") == "grep"


# --- is_one_edit ----------------------------------------------------------


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("sl", "ls"),      # neighbors swapped
        ("cta", "cat"),    # neighbors swapped
        ("pdw", "pwd"),    # neighbors swapped
        ("cdd", "cd"),     # one letter extra
        ("mkdr", "mkdir"),  # one letter missing
        ("lx", "ls"),      # one letter changed
        ("mkdri", "mkdir"),  # neighbors swapped near the end
    ],
)
def test_one_edit_pairs(a: str, b: str) -> None:
    """Each kind of single edit is detected, in both directions."""
    assert is_one_edit(a, b)
    assert is_one_edit(b, a)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("ls", "ls"),        # identical is zero edits
        ("abc", "cba"),      # swap of letters that aren't neighbors
        ("mdkri", "mkdir"),  # two separate swaps
        ("ls", "lsxx"),      # two letters extra
        ("grep", "grap1"),   # change plus extra
        ("ab", "xy"),        # two changes
    ],
)
def test_not_one_edit_pairs(a: str, b: str) -> None:
    """Zero edits or two-plus edits are not 'one edit'."""
    assert not is_one_edit(a, b)


# --- suggest --------------------------------------------------------------


@pytest.mark.parametrize(
    ("typo", "expected"),
    [
        ("sl", "ls"),
        ("cta", "cat"),
        ("pdw", "pwd"),
        ("cdd", "cd"),
        ("mkdri", "mkdir"),
        ("histroyy", "history"),  # two edits: found by the difflib step
        ("grpe", "grep"),
        ("ehco", "echo"),
        ("sorce", "source"),
        ("SL", "ls"),         # case doesn't matter
        (" sl ", "ls"),       # spaces don't matter
    ],
)
def test_suggest_real_typos(typo: str, expected: str) -> None:
    """Common beginner typos get the right suggestion from the real data (ADR 0006)."""
    assert suggest(typo) == expected


@pytest.mark.parametrize("typed", ["xyzzy", "banana", "kubectl"])
def test_suggest_nothing_for_unrelated_words(typed: str) -> None:
    """Words that aren't close to any command get no suggestion."""
    assert suggest(typed) is None


@pytest.mark.parametrize("typed", ["", "l", "x", "."])
def test_suggest_nothing_for_short_input(typed: str) -> None:
    """Input under 2 characters never gets a suggestion."""
    assert suggest(typed) is None


@pytest.mark.parametrize("typed", ["ls", "LS", "."])
def test_suggest_nothing_for_known_names(typed: str) -> None:
    """A name that's already known needs no suggestion."""
    assert suggest(typed) is None


def test_suggest_tie_break_is_predictable() -> None:
    """When several names are one edit away, the same one is always picked.

    'cs' is one edit from both 'cd' and 'ls' with equal similarity, so the
    alphabetical tie-break picks 'cd'.
    """
    assert suggest("cs", FAKE) == "cd"


def test_suggest_can_return_an_alias() -> None:
    """Aliases with letters are suggestion candidates too."""
    commands = {"ls": {"aliases": ["dir"]}, "zz": {"aliases": []}}
    assert suggest("dri", commands) == "dir"


@pytest.mark.parametrize("typed", ["..", "...", "-l", "--", "12"])
def test_suggest_nothing_without_letters(typed: str) -> None:
    """Input with no letters gets no suggestion, so '..' isn't turned into '.' (ADR 0011)."""
    assert suggest(typed) is None


def test_suggest_never_returns_a_name_without_letters() -> None:
    """Names like '.' are never suggested, even when they are one edit away."""
    assert suggest("a.", {"source": {"aliases": ["."]}, "zz": {"aliases": []}}) is None


def test_default_commands_is_loaded_once() -> None:
    """The shipped data is read from disk once and then reused."""
    assert default_commands() is default_commands()
