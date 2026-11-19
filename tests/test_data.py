"""Validate commands.json and operators.json against the schema in SPEC.md §5."""

from __future__ import annotations

import re
from typing import Any

import pytest

from commandexplain.lookup import load_commands, load_not_covered, load_operators

COMMANDS = load_commands()
OPERATORS = load_operators()

VALID_SHELLS = {"bash", "zsh"}

# The v1 command list from SPEC.md §6.
SPEC_COMMANDS = {
    "cd", "pwd", "ls",
    "mkdir", "rmdir", "touch", "cp", "mv", "rm", "ln",
    "cat", "less", "head", "tail", "wc",
    "grep", "find", "which",
    "chmod", "chown", "sudo",
    "ps", "kill", "top",
    "echo", "clear", "history", "man", "alias", "export", "source", "exit",
    "shopt", "setopt", "unsetopt",
}

SPEC_OPERATORS = {"|", "&&", "||", ";", ">", ">>", "<"}

# Commands that can destroy data or break the system, so they must carry a warning.
DANGEROUS_COMMANDS = {"rm", "sudo", "chmod", "kill", "find"}

# Max number of common flags shown when the user types none (ADR 0008).
MAX_COMMON_FLAGS = 5

# A flag key is - or -- followed by letters, digits, or dashes: -r, -9, -name, --all.
FLAG_KEY_PATTERN = re.compile(r"^--?[A-Za-z0-9][A-Za-z0-9-]*$")

REQUIRED_FIELDS: dict[str, type | tuple[type, ...]] = {
    "name": str,
    "summary": str,
    "shells": list,
    "flags": dict,
    "common_flags": list,
    "example": str,
}

OPTIONAL_FIELDS: dict[str, type | tuple[type, ...]] = {
    "warning": (str, type(None)),
    "shell_notes": dict,
    "aliases": list,
    "short": str,
    "runs_command": bool,
    "flags_with_values": list,
    "builtin_only": bool,
    "keep_flags_whole": bool,
}


def count_sentences(text: str) -> int:
    """Count sentences: '.', '!' or '?' right after a word (or closing bracket/quote).

    The punctuation must be followed by a space or the end of the text, so dots inside
    file names (script.sh) and lone symbols ('Type ! and', '(. file)') don't count.
    """
    return len(re.findall(r"(?<=[\w)\"'])[.!?](?=\s|$)", text.strip()))


def command_params() -> list[Any]:
    """One pytest param per command, labelled by name so failures say which entry broke."""
    return [pytest.param(name, entry, id=name) for name, entry in COMMANDS.items()]


# --- Coverage -------------------------------------------------------------


def test_all_spec_commands_present() -> None:
    """Every command listed in SPEC.md §6 has an entry."""
    missing = SPEC_COMMANDS - COMMANDS.keys()
    assert not missing, f"missing commands: {sorted(missing)}"


def test_all_spec_operators_present() -> None:
    """Every operator listed in SPEC.md §5.1 has an entry."""
    missing = SPEC_OPERATORS - OPERATORS.keys()
    assert not missing, f"missing operators: {sorted(missing)}"


@pytest.mark.parametrize("name", sorted(DANGEROUS_COMMANDS))
def test_dangerous_commands_have_warning(name: str) -> None:
    """Commands that can destroy data or break the system always warn the user."""
    assert COMMANDS[name].get("warning"), f"{name} should have a warning"


# --- Command schema -------------------------------------------------------


@pytest.mark.parametrize(("name", "entry"), command_params())
def test_command_key_is_lowercase_and_has_no_spaces(name: str, entry: dict) -> None:
    """Keys are what the user types, so they must be plain lowercase command names."""
    assert name == name.strip().lower()
    assert " " not in name


@pytest.mark.parametrize(("name", "entry"), command_params())
def test_command_has_required_fields_with_right_types(name: str, entry: dict) -> None:
    """Every required field from SPEC.md §5 is present and has the right type."""
    for field, expected in REQUIRED_FIELDS.items():
        assert field in entry, f"{name}: missing required field '{field}'"
        assert isinstance(entry[field], expected), f"{name}: '{field}' has the wrong type"


@pytest.mark.parametrize(("name", "entry"), command_params())
def test_command_optional_fields_have_right_types(name: str, entry: dict) -> None:
    """Optional fields, when present, have the right type."""
    for field, expected in OPTIONAL_FIELDS.items():
        if field in entry:
            assert isinstance(entry[field], expected), f"{name}: '{field}' has the wrong type"


@pytest.mark.parametrize(("name", "entry"), command_params())
def test_command_has_no_unknown_fields(name: str, entry: dict) -> None:
    """Catches typos in field names, like 'sumary' or 'flag'."""
    unknown = entry.keys() - REQUIRED_FIELDS.keys() - OPTIONAL_FIELDS.keys()
    assert not unknown, f"{name}: unknown fields {sorted(unknown)}"


@pytest.mark.parametrize(("name", "entry"), command_params())
def test_text_fields_are_not_blank(name: str, entry: dict) -> None:
    """Name, summary, and example must say something."""
    for field in ("name", "summary", "example"):
        assert entry[field].strip(), f"{name}: '{field}' is blank"


@pytest.mark.parametrize(("name", "entry"), command_params())
def test_shells_are_valid(name: str, entry: dict) -> None:
    """shells is a non-empty list of 'bash' and/or 'zsh', with no repeats."""
    shells = entry["shells"]
    assert shells, f"{name}: shells is empty"
    assert set(shells) <= VALID_SHELLS, f"{name}: invalid shells {shells}"
    assert len(shells) == len(set(shells)), f"{name}: repeated shells {shells}"


@pytest.mark.parametrize(("name", "entry"), command_params())
def test_flags_are_well_formed(name: str, entry: dict) -> None:
    """Flag keys look like -r, -9, -name, or --all, and every explanation is non-empty.

    Multi-letter single-dash keys (find's -name) are allowed: the parser matches the
    whole token before splitting -rf style groups (ADR 0007).
    """
    for flag, explanation in entry["flags"].items():
        assert FLAG_KEY_PATTERN.match(flag), f"{name}: bad flag key '{flag}'"
        assert isinstance(explanation, str) and explanation.strip(), (
            f"{name}: flag '{flag}' has no explanation"
        )


@pytest.mark.parametrize(("name", "entry"), command_params())
def test_common_flags_exist_in_flags(name: str, entry: dict) -> None:
    """Common flags exist in 'flags', don't repeat, and there are at most 5 (ADR 0008)."""
    common = entry["common_flags"]
    missing = [flag for flag in common if flag not in entry["flags"]]
    assert not missing, f"{name}: common_flags not in flags: {missing}"
    assert len(common) == len(set(common)), f"{name}: repeated common_flags"
    assert len(common) <= MAX_COMMON_FLAGS, f"{name}: more than {MAX_COMMON_FLAGS} common_flags"


@pytest.mark.parametrize(("name", "entry"), command_params())
def test_summary_is_at_most_two_sentences(name: str, entry: dict) -> None:
    """Keeps summaries short and simple for beginners (SPEC.md §3.3)."""
    sentences = count_sentences(entry["summary"])
    assert 1 <= sentences <= 2, f"{name}: summary has {sentences} sentences"


@pytest.mark.parametrize(("name", "entry"), command_params())
def test_shell_notes_use_valid_shells(name: str, entry: dict) -> None:
    """shell_notes keys are 'bash' or 'zsh', and only for shells the command exists in."""
    notes = entry.get("shell_notes", {})
    for shell, note in notes.items():
        assert shell in VALID_SHELLS, f"{name}: shell_notes has invalid shell '{shell}'"
        assert shell in entry["shells"], f"{name}: note for '{shell}' but command isn't in it"
        assert isinstance(note, str) and note.strip(), f"{name}: empty note for '{shell}'"


@pytest.mark.parametrize(("name", "entry"), command_params())
def test_warning_is_not_blank_when_present(name: str, entry: dict) -> None:
    """A warning is either null or real text, never an empty string."""
    warning = entry.get("warning")
    assert warning is None or warning.strip(), f"{name}: warning is an empty string"


def test_aliases_do_not_clash() -> None:
    """An alias can't be a real command name or belong to two commands."""
    seen: dict[str, str] = {}
    for name, entry in COMMANDS.items():
        for alias in entry.get("aliases", []):
            assert isinstance(alias, str) and alias.strip(), f"{name}: blank alias"
            assert alias == alias.lower() and " " not in alias, (
                f"{name}: alias '{alias}' must be lowercase with no spaces"
            )
            assert alias not in COMMANDS, f"{name}: alias '{alias}' is also a command"
            assert alias not in seen, f"alias '{alias}' used by both {seen.get(alias)} and {name}"
            seen[alias] = name


# --- Operator schema ------------------------------------------------------


@pytest.mark.parametrize(
    ("symbol", "entry"),
    [pytest.param(symbol, entry, id=symbol) for symbol, entry in OPERATORS.items()],
)
def test_operator_schema(symbol: str, entry: dict) -> None:
    """Operators have a name and summary, an optional warning, and nothing else."""
    assert isinstance(entry.get("name"), str) and entry["name"].strip()
    assert isinstance(entry.get("summary"), str) and entry["summary"].strip()
    if "warning" in entry:
        assert isinstance(entry["warning"], str) and entry["warning"].strip()
    unknown = entry.keys() - {"name", "summary", "warning"}
    assert not unknown, f"{symbol}: unknown fields {sorted(unknown)}"
    sentences = count_sentences(entry["summary"])
    assert 1 <= sentences <= 2, f"{symbol}: summary has {sentences} sentences"


def test_overwrite_operator_warns() -> None:
    """'>' erases a file's contents, so it must warn."""
    assert OPERATORS[">"].get("warning")


# --- The sentence counter itself ------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("One sentence.", 1),
        ("One. Two.", 2),
        ("Run chmod +x script.sh to allow it.", 1),
        ("Show ~/.zshrc settings.", 1),
        ("Type a dot (. file) to do it.", 1),
        ("Type ! and a number to run it.", 1),
        ("Use it (like this). Then stop.", 2),
        ("Really? Yes! Done.", 3),
    ],
)
def test_count_sentences(text: str, expected: int) -> None:
    """File names and paths with dots don't count as sentence endings."""
    assert count_sentences(text) == expected


@pytest.mark.parametrize(("name", "entry"), command_params())
def test_flags_with_values_exist_in_flags(name: str, entry: dict) -> None:
    """A flag that takes a value must be one of the command's flags (ADR 0010)."""
    missing = [flag for flag in entry.get("flags_with_values", []) if flag not in entry["flags"]]
    assert not missing, f"{name}: flags_with_values not in flags: {missing}"


def test_sudo_runs_another_command() -> None:
    """sudo is marked as running another command, and -u takes a user name (ADR 0010)."""
    assert COMMANDS["sudo"]["runs_command"] is True
    assert set(COMMANDS["sudo"]["flags_with_values"]) == {"-u", "--user", "-g", "--group"}


# Shell builtins with no separate program, so sudo can't run them (ADR 0013).
BUILTIN_ONLY = {
    "cd", "alias", "export", "source", "exit", "history", "shopt", "setopt", "unsetopt",
}


def test_builtin_only_commands_are_marked() -> None:
    """Exactly the shell-only builtins carry builtin_only (echo, kill, pwd have real programs)."""
    marked = {name for name, entry in COMMANDS.items() if entry.get("builtin_only")}
    assert marked == BUILTIN_ONLY


def test_kill_keeps_flags_whole() -> None:
    """kill's -INT and -SIGKILL are signal names, so they must not be split (ADR 0014)."""
    assert COMMANDS["kill"]["keep_flags_whole"] is True


# --- not_covered.json (SPEC.md §5.2, §9) ----------------------------------

NOT_COVERED = load_not_covered()


def test_not_covered_entries_are_well_formed() -> None:
    """Each name is lowercase with no spaces, and its kind is 'tool' or 'uncovered'."""
    for name, entry in NOT_COVERED.items():
        assert name == name.strip().lower() and " " not in name, f"bad name '{name}'"
        assert entry.keys() == {"kind"}, f"{name}: unexpected fields {sorted(entry)}"
        assert entry["kind"] in {"tool", "uncovered"}, f"{name}: bad kind {entry['kind']}"


def test_not_covered_does_not_overlap_commands() -> None:
    """A name can't be both explained and 'not covered'."""
    aliases = {alias for entry in COMMANDS.values() for alias in entry.get("aliases", [])}
    overlap = NOT_COVERED.keys() & (COMMANDS.keys() | aliases)
    assert not overlap, f"both covered and not covered: {sorted(overlap)}"


@pytest.mark.parametrize("name", ["git", "unset", "unalias"])
def test_review_examples_are_on_not_covered_list(name: str) -> None:
    """The examples from the spec and ADR 0011 are on the list."""
    assert name in NOT_COVERED
