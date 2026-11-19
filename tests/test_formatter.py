"""Tests for building explanation text (SPEC.md §3.3) and the explain() entry point."""

from __future__ import annotations

from typing import Any

import pytest

from commandexplain.formatter import (
    WIDTH,
    EmptyInputError,
    UnknownCommandError,
    explain,
    format_explanation,
)
from commandexplain.lookup import load_commands
from commandexplain.parser import ParseError

COMMANDS = load_commands()


def entry(**overrides: Any) -> dict[str, Any]:
    """A small fake command entry for testing layout rules without the real data."""
    base: dict[str, Any] = {
        "name": "test command",
        "summary": "Does a test thing.",
        "shells": ["bash", "zsh"],
        "flags": {"-a": "Flag a.", "-b": "Flag b.", "-c": "Flag c."},
        "common_flags": ["-a", "-b"],
        "example": "tc -a",
        "warning": None,
        "shell_notes": {},
        "aliases": [],
    }
    base.update(overrides)
    return base


# --- Acceptance criteria 2 and 3 (real data) -----------------------------


def test_ac2_ls_shows_summary_and_common_flags() -> None:
    """AC 2: `ls` prints the summary and the common flags for ls."""
    text = explain("ls", shell="zsh")
    ls = COMMANDS["ls"]
    assert text.startswith("ls  —  list")
    assert ls["summary"] in text
    assert "Common options:" in text
    for flag in ls["common_flags"]:
        assert flag in text
    assert "Example:  ls -la" in text


def test_ac3_rm_rf_explains_command_both_flags_and_warning() -> None:
    """AC 3: `rm -rf` explains rm, -r, and -f, and shows the warning."""
    text = explain("rm -rf", shell="zsh")
    rm = COMMANDS["rm"]
    assert text.startswith("rm  —  remove")
    assert "-r   Delete folders and everything inside them." in text
    assert "-f   Force:" in text
    assert "⚠ Careful: This deletes files permanently." in text
    assert "Common options:" not in text  # typed flags replace the common list
    assert "-i" not in text.split("Example:")[0]  # untyped flags aren't shown


# --- Layout rules (fake entry) --------------------------------------------


def test_typed_flags_only_show_those_flags() -> None:
    """When flags are typed, only they are explained, with no 'Common options'."""
    text = format_explanation("tc", entry(), ["-c"], [], "bash")
    assert "-c   Flag c." in text
    assert "Flag a." not in text
    assert "Common options:" not in text


def test_no_flags_shows_common_options() -> None:
    """With no typed flags, the common flags appear under a heading."""
    text = format_explanation("tc", entry(), [], [], "bash")
    assert "  Common options:\n    -a   Flag a.\n    -b   Flag b." in text
    assert "Flag c." not in text


def test_empty_common_flags_leaves_heading_out() -> None:
    """ADR 0008: no common flags means no 'Common options' heading at all."""
    text = format_explanation("tc", entry(common_flags=[]), [], [], "bash")
    assert "Common options" not in text


def test_unknown_flag_points_to_man() -> None:
    """A flag missing from the data says so and suggests the manual."""
    text = format_explanation("tc", entry(), ["-z"], [], "bash")
    flat = " ".join(text.split())  # the message may wrap onto a second line
    assert "-z I don't have an explanation for this option." in flat
    assert 'Try "man tc" for the full manual.' in flat


def test_arguments_are_listed() -> None:
    """Each argument gets its own 'argument:' line, in the order typed (ADR 0012)."""
    text = format_explanation("tc", entry(), [], ["notes.txt", "backup/"], "bash")
    assert "  argument: notes.txt\n  argument: backup/" in text


def test_long_argument_does_not_squeeze_other_text() -> None:
    """A long path stays on one line and doesn't push the flag column over (ADR 0012)."""
    long_path = "~/Documents/projects/" + "x" * 120 + ".txt"
    text = format_explanation("tc", entry(), ["-a"], [long_path], "bash")
    assert "  -a   Flag a." in text
    assert f"  argument: {long_path}" in text


def test_columns_line_up() -> None:
    """Short and long flags in one list share the same explanation column."""
    flags = {"-a": "Short.", "-name": "Long."}
    text = format_explanation("tc", entry(flags=flags), ["-a", "-name"], [], "bash")
    assert "  -a      Short.\n  -name   Long." in text


def test_warning_shown_when_present() -> None:
    """A command's warning is shown with the 'Careful' marker."""
    text = format_explanation("tc", entry(warning="It bites."), [], [], "bash")
    assert "⚠ Careful: It bites." in text


def test_no_warning_line_without_warning() -> None:
    """Commands without a warning don't show the marker."""
    assert "Careful" not in format_explanation("tc", entry(), [], [], "bash")


def test_shell_note_only_for_selected_shell() -> None:
    """Only the note for the user's shell is shown."""
    notes = {"bash": "Bash thing.", "zsh": "Zsh thing."}
    zsh_text = format_explanation("tc", entry(shell_notes=notes), [], [], "zsh")
    bash_text = format_explanation("tc", entry(shell_notes=notes), [], [], "bash")
    assert "Note for zsh: Zsh thing." in zsh_text and "Bash thing." not in zsh_text
    assert "Note for bash: Bash thing." in bash_text and "Zsh thing." not in bash_text


def test_example_is_last() -> None:
    """The example is the final line."""
    text = format_explanation("tc", entry(), [], [], "bash")
    assert text.splitlines()[-1] == "  Example:  tc -a"


def test_blocks_are_separated_by_blank_lines() -> None:
    """Title/summary, flags, and example are separate blocks."""
    text = format_explanation("tc", entry(), [], [], "bash")
    assert text == (
        "tc  —  test command\n"
        "  Does a test thing.\n"
        "\n"
        "  Common options:\n"
        "    -a   Flag a.\n"
        "    -b   Flag b.\n"
        "\n"
        "  Example:  tc -a"
    )


@pytest.mark.parametrize("name", sorted(COMMANDS))
@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_every_real_command_fits_the_width(name: str, shell: str) -> None:
    """Every command, with all its flags and some arguments typed, wraps within the width.

    Argument lines are the one exception: a long path can't be wrapped, so it's
    shown whole on its own line.
    """
    typed = " ".join([name, *COMMANDS[name]["flags"], "notes.txt", "a" * 100])
    for line in explain(typed, shell=shell).splitlines():
        if line.startswith("  argument: "):
            continue
        assert len(line) <= WIDTH, f"{name}: line too long: {line!r}"


# --- explain() ------------------------------------------------------------


def test_explain_ignores_command_case() -> None:
    """LS is explained as ls; the flags keep their case."""
    assert explain("LS -la", shell="bash").startswith("ls  —  list")


def test_explain_resolves_alias_to_real_command() -> None:
    """'.' is explained as source."""
    assert explain(". ~/.zshrc", shell="zsh").startswith("source  —")


def test_explain_word_flags_for_find() -> None:
    """find's -name is explained as one flag (ADR 0007)."""
    text = explain('find . -name "*.txt"', shell="bash")
    assert "-name   Find things whose name matches a pattern." in text
    assert "-n " not in text


def test_explain_unknown_command_raises() -> None:
    """An unknown command raises UnknownCommandError with the typed name."""
    with pytest.raises(UnknownCommandError, match="sl"):
        explain("sl -la", shell="bash")


@pytest.mark.parametrize("text", ["", "   "])
def test_explain_blank_input_raises(text: str) -> None:
    """Blank input raises EmptyInputError, since there's nothing to explain."""
    with pytest.raises(EmptyInputError):
        explain(text, shell="bash")


def test_explain_bad_shell_raises() -> None:
    """Only bash and zsh are supported."""
    with pytest.raises(ValueError, match="shell"):
        explain("ls", shell="fish")


def test_explain_unclosed_quote_raises_parse_error() -> None:
    """An unclosed quote surfaces as ParseError for the CLI to handle."""
    with pytest.raises(ParseError):
        explain('echo "hi', shell="bash")


def test_explain_uses_given_commands() -> None:
    """A custom commands dict can be passed instead of the shipped data."""
    assert explain("tc -a", shell="bash", commands={"tc": entry()}).startswith("tc  —")


# --- Commands that run other commands (ADR 0010) --------------------------


def test_sudo_inner_flags_belong_to_inner_command() -> None:
    """sudo rm -i x: -i is explained as rm's flag, not sudo's."""
    text = explain("sudo rm -i old.txt", shell="bash")
    sudo_part, rm_part = text.split("sudo runs this command:")
    assert "Start an administrator session" not in sudo_part
    assert rm_part.lstrip().startswith("rm  —  remove")
    assert "-i   Ask 'are you sure?' before deleting each file." in rm_part
    assert "argument: old.txt" in rm_part


def test_sudo_rm_rf_shows_rm_warning() -> None:
    """sudo rm -rf shows both sudo's warning and rm's delete warning."""
    text = explain("sudo rm -rf /tmp/x", shell="zsh")
    assert "Commands run with sudo can change or delete anything" in text
    assert "This deletes files permanently." in text


def test_sudo_user_value_is_not_the_inner_command() -> None:
    """sudo -u bob ls -l: bob is -u's value, and ls -l is explained."""
    text = explain("sudo -u bob ls -l", shell="bash")
    sudo_part, ls_part = text.split("sudo runs this command:")
    assert "-u   Run the command as a different user" in sudo_part
    assert "argument: bob" in sudo_part
    assert ls_part.lstrip().startswith("ls  —  list")
    assert "List what you are allowed to run with sudo" not in ls_part


def test_sudo_unknown_inner_command() -> None:
    """An inner command that isn't in the data is named, not crashed on."""
    text = explain("sudo foo -x", shell="bash")
    assert 'sudo runs "foo", which I don\'t have an explanation for.' in text


def test_sudo_alone_has_no_inner_block() -> None:
    """sudo -l on its own only explains sudo."""
    text = explain("sudo -l", shell="bash")
    assert "runs this command" not in text
    assert "-l   List what you are allowed to run with sudo." in text


@pytest.mark.parametrize("signal", ["-KILL", "-TERM", "-HUP", "-15"])
def test_kill_signal_names_are_explained(signal: str) -> None:
    """kill -KILL is one known flag, not -K -I -L."""
    text = explain(f"kill {signal} 123", shell="bash")
    assert f"  {signal}   " in text
    assert "I don't have an explanation" not in text


def test_sudo_hides_its_common_options_when_running_a_command() -> None:
    """With an inner command, sudo's common options are left out (ADR 0010)."""
    assert "Common options" not in explain("sudo ls", shell="bash").split("sudo runs")[0]
    assert "Common options" in explain("sudo", shell="bash")


def test_show_common_false_leaves_common_options_out() -> None:
    """format_explanation can be told not to list common options."""
    text = format_explanation("tc", entry(), [], [], "bash", show_common=False)
    assert "Common options" not in text


def test_sudo_with_builtin_warns_then_explains() -> None:
    """sudo cd /root: warn that sudo can't run cd, then still explain cd (ADR 0013)."""
    text = explain("sudo cd /root", shell="bash")
    _, inner = text.split("sudo runs this command:")
    flat = " ".join(inner.split())
    assert "⚠ Careful: sudo can't run cd, because cd is built into the shell." in flat
    assert "cd — change directory" in flat


def test_sudo_with_real_program_has_no_builtin_warning() -> None:
    """echo has a real program, so sudo echo gets no builtin warning."""
    assert "built into the shell" not in explain("sudo echo hi", shell="bash")


def test_builtin_alone_has_no_builtin_warning() -> None:
    """The warning is only for builtins run through sudo, not on their own."""
    assert "built into the shell" not in explain("cd /root", shell="bash")


@pytest.mark.parametrize("typed", ["sudo --user bob ls", "sudo --user=bob ls", "sudo -g wheel ls"])
def test_sudo_value_flags_find_the_real_inner_command(typed: str) -> None:
    """Value-taking flags (--user, -g) don't make their value look like the command."""
    text = explain(typed, shell="bash")
    assert "ls  —  list" in text
    assert "which I don't have an explanation for" not in text


def test_sudo_grouped_flags_through_explain() -> None:
    """sudo -iu bob ls explains ls, with bob as -u's value."""
    text = explain("sudo -iu bob ls", shell="bash")
    sudo_part, ls_part = text.split("sudo runs this command:")
    assert "argument: bob" in sudo_part
    assert ls_part.lstrip().startswith("ls  —  list")


def test_sudo_double_dash_through_explain() -> None:
    """sudo -- rm -rf x explains rm with its flags."""
    text = explain("sudo -- rm -rf x", shell="bash")
    assert "rm  —  remove" in text
    assert "-r   Delete folders" in text


def test_nested_sudo_explains_each_level() -> None:
    """sudo sudo ls explains sudo twice, then ls."""
    text = explain("sudo sudo ls", shell="bash")
    assert text.count("sudo runs this command:") == 2
    assert text.rstrip().endswith("Example:  ls -la")


def test_very_long_sudo_chain_does_not_crash() -> None:
    """Thousands of nested sudos don't hit Python's recursion limit."""
    text = explain("sudo " * 2000 + "ls", shell="bash")
    assert text.count("sudo runs this command:") == 2000


def test_kill_unknown_signal_is_one_flag() -> None:
    """kill -INT shows one unknown flag, not -I -N -T (ADR 0014)."""
    flat = " ".join(explain("kill -INT 5", shell="bash").split())
    assert "-INT I don't have an explanation for this option." in flat
    assert "-I " not in flat


def test_long_unknown_flag_goes_on_its_own_line() -> None:
    """A very long label sits on its own line, so the other flags keep their column."""
    long_flag = "--this-is-a-really-long-made-up-option-for-testing"
    text = explain(f"ls {long_flag} -l", shell="bash")
    lines = text.splitlines()
    i = lines.index(f"  {long_flag}")
    assert lines[i + 1].startswith("       I don't have an explanation")
    assert "  -l   Show the list in long form" in text


# --- Chains (SPEC.md §3.3.1, ADR 0018) -----------------------------------


def test_ac9_pipe_explains_each_part_in_order() -> None:
    """AC 9: ls -a | grep txt explains ls -a, then the pipe, then grep txt."""
    text = explain("ls -a | grep txt", shell="zsh")
    ls_at = text.index("ls -a\n  ls — list:")
    pipe_at = text.index("|  (pipe)")
    grep_at = text.index("grep txt\n  grep — search text:")
    assert ls_at < pipe_at < grep_at
    assert "-a   Also show hidden files" in text
    assert "argument: txt" in text


def test_ac9_quoted_pipe_is_one_command() -> None:
    """AC 9: grep "a|b" f is a single command with the full format, not a pipe."""
    text = explain('grep "a|b" f', shell="zsh")
    assert text.startswith("grep  —  search text")
    assert "(pipe)" not in text
    assert "argument: a|b" in text


def test_chain_blocks_have_no_example_or_common_options() -> None:
    """Chain blocks are short: no Example line and no Common options (ADR 0018)."""
    text = explain("ls | wc", shell="zsh")
    assert "Example:" not in text
    assert "Common options" not in text


def test_chain_keeps_warnings_and_shell_notes() -> None:
    """Safety warnings and shell notes still show inside a chain."""
    text = explain("rm -rf old && echo done", shell="zsh")
    assert "⚠ Careful: This deletes files permanently." in text
    assert "Note for zsh:" in text


def test_in_short_line_joins_phrases() -> None:
    """The "In short" line joins each command's phrase with its operator's phrase."""
    text = explain("mkdir docs && cd docs", shell="bash")
    assert text.endswith("In short: make a folder, and if that works, change folder.")


def test_in_short_includes_redirect_files() -> None:
    """Redirects add their file to the "In short" line."""
    text = explain("ls > files.txt", shell="bash")
    assert text.endswith("In short: list files, and save the output to files.txt.")


def test_redirect_block_names_file_and_warns() -> None:
    """A > redirect names its file and warns about erasing it."""
    text = explain("echo hi > out.txt", shell="bash")
    assert ">  (save to file)" in text
    assert "file: out.txt" in text
    assert "⚠ Careful: This erases the file's old contents." in text


def test_not_covered_command_in_chain_is_named() -> None:
    """A not-covered command gets its message as its block, and no "In short" line."""
    text = explain("ls | sort", shell="bash")
    assert "sort\n  'sort' is a real command, but I don't cover it yet." in text
    assert "In short" not in text


def test_unknown_command_in_chain_raises() -> None:
    """A command that's neither known nor not-covered raises UnknownCommandError."""
    with pytest.raises(UnknownCommandError, match="xyzzy"):
        explain("ls | xyzzy", shell="bash")


def test_sudo_inside_chain() -> None:
    """sudo in a chain explains its inner command, and the phrase says 'using sudo'."""
    text = explain("sudo rm -rf x ; echo done", shell="bash")
    assert "  sudo runs this command:\n  rm — remove:" in text
    assert "This deletes files permanently." in text
    assert "In short: delete files (using sudo), then print text." in text


def test_sudo_builtin_warning_inside_chain() -> None:
    """sudo cd in a chain still gets the builtin warning (ADR 0013)."""
    flat = " ".join(explain("sudo cd /root && ls", shell="bash").split())
    assert "sudo can't run cd, because cd is built into the shell." in flat


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_long_chain_fits_the_width(shell: str) -> None:
    """Every line of a long chain wraps within the width (argument lines aside)."""
    typed = "sudo rm -rf old ; find . -name x -delete | grep -i txt >> log.txt && echo done"
    for line in explain(typed, shell=shell).splitlines():
        if not line.lstrip().startswith("argument: "):
            assert len(line) <= WIDTH, line


@pytest.mark.parametrize(
    ("typed", "header"),
    [
        ('echo "hello world" $HOME | wc', 'echo "hello world" $HOME'),
        ("find . -exec rm {} \\; | wc", "find . -exec rm {} \\;"),
        ("sort > out.txt -r | wc", "sort > out.txt -r"),
    ],
)
def test_chain_block_header_is_text_as_typed(typed: str, header: str) -> None:
    """The first line of each block is exactly what the user typed for that command."""
    assert explain(typed, shell="bash").splitlines()[0] == header


def test_no_in_short_when_saved_output_is_piped() -> None:
    """ls > out.txt | wc: bash and zsh differ here, so there's no "In short" line."""
    assert "In short" not in explain("ls > out.txt | wc", shell="bash")


def test_sudo_not_covered_inner_in_chain_has_lead_in() -> None:
    """sudo git push | wc: the block says sudo runs it before saying git isn't covered."""
    text = explain("sudo git push | wc", shell="bash")
    assert "  sudo runs this command:\n  'git' isn't a built-in terminal command" in text


def test_no_in_short_when_sudo_runs_a_builtin() -> None:
    """sudo cd can't work, so the line can't say "change folder (using sudo)"."""
    assert "In short" not in explain("sudo cd /tmp ; ls", shell="bash")


def test_no_in_short_with_two_output_redirects() -> None:
    """ls > a > b differs between bash and zsh, so there's no "In short" line."""
    assert "In short" not in explain("ls > a > b", shell="bash")


def test_in_short_still_shown_for_one_redirect_at_the_end() -> None:
    """A single > at the end of the chain still gets its "In short" line."""
    flat = " ".join(explain("ls | wc > n.txt", shell="bash").split())
    assert flat.endswith(
        "In short: list files, then pass the output to count lines and words, "
        "and save the output to n.txt."
    )
