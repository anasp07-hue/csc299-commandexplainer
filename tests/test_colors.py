"""Tests for color handling (SPEC.md §3.3.2, ADR 0020)."""

from __future__ import annotations

import pytest

from commandexplain.colors import PLAIN, Palette, colors_enabled, strip_colors
from commandexplain.formatter import WIDTH, explain
from commandexplain.lookup import load_commands

COLOR = Palette(enabled=True)
COMMANDS = load_commands()


# --- colors_enabled -------------------------------------------------------


@pytest.mark.parametrize(
    ("tty", "env", "flag", "expected"),
    [
        (True, {}, False, True),
        (False, {}, False, False),
        (True, {"NO_COLOR": "1"}, False, False),
        (True, {"NO_COLOR": "anything"}, False, False),
        (True, {"NO_COLOR": ""}, False, True),
        (True, {}, True, False),
    ],
)
def test_colors_enabled_rules(tty: bool, env: dict[str, str], flag: bool, expected: bool) -> None:
    """Colors only in a terminal, without a non-empty NO_COLOR, and without --no-color."""
    assert colors_enabled(lambda: tty, env, flag) is expected


def test_colors_off_if_isatty_fails() -> None:
    """A stream that can't answer isatty() (closed or odd) means no colors."""

    def broken() -> bool:
        raise ValueError("I/O operation on closed file")

    assert colors_enabled(broken, {}, False) is False


# --- Palette ---------------------------------------------------------------


@pytest.mark.parametrize("method", ["command", "flag", "warning", "suggestion", "operator"])
def test_plain_palette_changes_nothing(method: str) -> None:
    """With colors off, every method returns the text unchanged."""
    assert getattr(PLAIN, method)("text") == "text"


@pytest.mark.parametrize(
    ("method", "code"),
    [
        ("command", "1"),
        ("flag", "36"),
        ("warning", "31"),
        ("suggestion", "33"),
        ("operator", "35"),
    ],
)
def test_palette_colors_match_spec(method: str, code: str) -> None:
    """Bold commands, cyan flags, red warnings, yellow suggestions, magenta operators."""
    assert getattr(COLOR, method)("x") == f"\033[{code}mx\033[0m"


def test_empty_text_gets_no_codes() -> None:
    """Coloring an empty string adds nothing."""
    assert COLOR.flag("") == ""


def test_strip_colors_removes_codes() -> None:
    """strip_colors gives back the plain text."""
    assert strip_colors(COLOR.warning("a") + " b " + COLOR.flag("-r")) == "a b -r"


# --- Formatter with colors -------------------------------------------------

SAMPLES = [
    "ls",
    "rm -rf old",
    "sudo cd /root",
    "kill -INT 5",
    "ls --a-really-long-made-up-option-name -l",
    "ls -a | grep txt",
    "sudo rm -rf x ; echo done >> log.txt",
    "cat < in.txt | sort",
]


@pytest.mark.parametrize("typed", SAMPLES + sorted(COMMANDS))
@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_colored_text_matches_plain_text(typed: str, shell: str) -> None:
    """Colors never change the words or the layout (SPEC.md §3.3.2)."""
    colored = explain(typed, shell=shell, palette=COLOR)
    assert strip_colors(colored) == explain(typed, shell=shell)


@pytest.mark.parametrize("typed", SAMPLES)
def test_colored_lines_fit_the_width(typed: str) -> None:
    """Color codes are added after wrapping, so visible widths stay within the limit."""
    for line in explain(typed, shell="zsh", palette=COLOR).splitlines():
        visible = strip_colors(line)
        if not visible.lstrip().startswith(("argument: ", "--a-really")):
            assert len(visible) <= WIDTH, visible


def test_each_element_gets_its_color() -> None:
    """Command name bold, flags cyan, warning red, and operator magenta."""
    text = explain("rm -rf x | wc", shell="bash", palette=COLOR)
    assert "\033[1mrm\033[0m — remove" in text
    assert "\033[36m-r\033[0m" in text and "\033[36m-f\033[0m" in text
    assert "\033[31m⚠ Careful: This deletes files permanently. There is no undo.\033[0m" in text
    assert "\033[35m|\033[0m  (pipe)" in text


def test_single_command_title_is_bold() -> None:
    """The title of a single command is bold."""
    assert explain("ls", shell="zsh", palette=COLOR).startswith("\033[1mls\033[0m  —  list")


def test_warning_color_does_not_cover_indent() -> None:
    """Wrapped warning lines keep their indent outside the color codes."""
    text = explain("sudo ls", shell="zsh", palette=COLOR)
    warning_lines = [line for line in text.splitlines() if "\033[31m" in line]
    assert len(warning_lines) > 1
    assert all(line.startswith(("  \033[31m", "    \033[31m")) for line in warning_lines)
