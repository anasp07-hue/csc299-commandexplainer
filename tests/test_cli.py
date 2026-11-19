"""Simulated sessions for the interactive CLI (SPEC.md §3, acceptance criteria 1-8)."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pytest

from commandexplain import cli, lookup
from commandexplain.cli import PROMPT, main
from commandexplain.shell import (
    HINT,
    MANUAL_PROMPT,
    UNSUPPORTED,
    detect_shell,
    read_shell_answer,
)

ZSH_ENV = {"SHELL": "/bin/zsh"}
BASH_ENV = {"SHELL": "/bin/bash"}
NO_SHELL_ENV: dict[str, str] = {}


class FakeTerminal:
    """Feeds scripted answers to the program and records everything it shows.

    When the answers run out, it behaves like Ctrl+D (EOFError). Setting
    `interrupt_at` makes that answer number behave like Ctrl+C instead.
    """

    def __init__(self, answers: Iterable[str], interrupt_at: int | None = None) -> None:
        """Queue up the answers the 'user' will type."""
        self.answers = list(answers)
        self.interrupt_at = interrupt_at
        self.prompts: list[str] = []
        self.lines: list[str] = []
        self.transcript: list[str] = []

    def input(self, prompt: str) -> str:
        """Record the prompt and return the next scripted answer."""
        self.prompts.append(prompt)
        if self.interrupt_at is not None and len(self.prompts) - 1 == self.interrupt_at:
            raise KeyboardInterrupt
        if not self.answers:
            raise EOFError
        answer = self.answers.pop(0)
        self.transcript.append(prompt + answer)
        return answer

    def print(self, text: str = "") -> None:
        """Record a line of output."""
        self.lines.append(text)
        self.transcript.append(text)

    @property
    def output(self) -> str:
        """Everything printed, as one string."""
        return "\n".join(self.lines)


def run_session(
    answers: Iterable[str],
    env: dict[str, str] | None = None,
    argv: list[str] | None = None,
    interrupt_at: int | None = None,
) -> tuple[int, FakeTerminal]:
    """Run the program with scripted answers and return (exit code, terminal)."""
    terminal = FakeTerminal(answers, interrupt_at)
    code = main(
        argv or [],
        input_fn=terminal.input,
        print_fn=terminal.print,
        env=ZSH_ENV if env is None else env,
    )
    return code, terminal


# --- AC 1: shell selection -----------------------------------------------


def test_ac1_detected_zsh_is_confirmed() -> None:
    """AC 1: with SHELL=/bin/zsh, the program asks to confirm zsh."""
    code, term = run_session(["yes", "quit"], env=ZSH_ENV)
    assert term.prompts[0] == "Looks like you're using zsh. Is that right? (yes/no) "
    assert 'Using zsh. (Type "shell" any time to switch.)' in term.lines
    assert code == 0


def test_ac1_no_shell_asks_until_valid() -> None:
    """AC 1: with SHELL unset, it asks bash or zsh and won't go on until the answer is valid."""
    code, term = run_session(["fish", "", "zsh", "quit"], env=NO_SHELL_ENV)
    assert term.prompts[:3] == [MANUAL_PROMPT] * 3
    assert term.lines.count(HINT) == 2
    assert term.prompts[3] == PROMPT
    assert "Using zsh." in term.output


def test_saying_no_to_detected_shell_asks_manually() -> None:
    """If the detected shell is wrong, the user picks the other one."""
    _, term = run_session(["no", "bash", "quit"], env=ZSH_ENV)
    assert term.prompts[1] == MANUAL_PROMPT
    assert "Using bash." in term.output


@pytest.mark.parametrize(("answer", "shell"), [("1", "bash"), ("2", "zsh"), ("  ZSH ", "zsh")])
def test_manual_shell_accepts_numbers_and_any_case(answer: str, shell: str) -> None:
    """1 means bash, 2 means zsh, and case and spaces don't matter."""
    _, term = run_session([answer, "quit"], env=NO_SHELL_ENV)
    assert f"Using {shell}." in term.output


def test_shell_typo_gets_did_you_mean() -> None:
    """bsh -> 'Did you mean bash?'; yes picks it."""
    _, term = run_session(["bsh", "yes", "quit"], env=NO_SHELL_ENV)
    assert "Did you mean bash? (yes/no) " in term.prompts
    assert "Using bash." in term.output


def test_shell_typo_no_asks_again() -> None:
    """Saying no to a shell suggestion asks the question again."""
    _, term = run_session(["zhs", "no", "zsh", "quit"], env=NO_SHELL_ENV)
    assert term.prompts.count(MANUAL_PROMPT) == 2
    assert "Using zsh." in term.output


def test_shell_flag_skips_the_question() -> None:
    """--shell bash goes straight to the command prompt."""
    _, term = run_session(["quit"], env=ZSH_ENV, argv=["--shell", "bash"])
    assert term.prompts == [PROMPT]
    assert "Using bash." in term.output


@pytest.mark.parametrize(
    ("value", "expected"),
    [("/bin/zsh", "zsh"), ("/usr/local/bin/bash", "bash"), ("/bin/fish", None), ("", None)],
)
def test_detect_shell(value: str, expected: str | None) -> None:
    """The shell name is the last part of SHELL's path, if it's bash or zsh."""
    assert detect_shell({"SHELL": value}) == expected


def test_read_shell_answer_rejects_others() -> None:
    """Only bash, zsh, 1, and 2 are valid answers."""
    assert read_shell_answer("fish") is None


# --- AC 2 and 3: explaining commands -------------------------------------


def test_ac2_ls_is_explained() -> None:
    """AC 2: `ls` prints the summary and common flags."""
    _, term = run_session(["yes", "ls", "quit"])
    assert "Shows the files and folders in the current folder." in term.output
    assert "Common options:" in term.output
    assert not any("Did you mean" in prompt for prompt in term.prompts)


def test_ac3_rm_rf_is_explained_with_warning() -> None:
    """AC 3: `rm -rf` explains rm, -r, -f, and shows the warning."""
    _, term = run_session(["yes", "rm -rf", "quit"])
    assert "rm  —  remove" in term.output
    assert "-r   Delete folders" in term.output
    assert "⚠ Careful: This deletes files permanently." in term.output


def test_blank_input_reprompts_silently() -> None:
    """Pressing Enter on an empty line just asks again."""
    _, term = run_session(["yes", "", "   ", "quit"])
    assert term.prompts.count(PROMPT) == 3
    assert term.lines == ['Using zsh. (Type "shell" any time to switch.)', "Goodbye!"]


def test_command_name_case_is_ignored() -> None:
    """LS works like ls."""
    _, term = run_session(["yes", "LS", "quit"])
    assert "ls  —  list" in term.output


# --- AC 4, 5, 6: spelling suggestions ------------------------------------


def test_ac4_typo_yes_explains_suggestion_with_flags() -> None:
    """AC 4: sl -> 'Did you mean ls?'; yes explains ls, keeping -la."""
    _, term = run_session(["yes", "sl -la", "yes", "quit"])
    assert "Did you mean 'ls'? (yes/no) " in term.prompts
    assert "ls  —  list" in term.output
    assert "-a   Also show hidden files" in term.output


def test_ac4_typo_no_says_not_found_and_reprompts() -> None:
    """AC 4: no prints 'Command not found. Please re-enter it.' and asks again."""
    _, term = run_session(["yes", "sl", "no", "quit"])
    assert "Command not found. Please re-enter it." in term.lines
    assert "ls  —  list" not in term.output
    assert term.prompts[-1] == PROMPT


@pytest.mark.parametrize("answer", ["maybe", "", "yess", "1"])
def test_ac5_unclear_answer_asks_again(answer: str) -> None:
    """AC 5: anything but yes/no re-asks instead of crashing."""
    _, term = run_session(["yes", "sl", answer, "Y", "quit"])
    assert "Please type yes or no." in term.lines
    assert term.prompts.count("Did you mean 'ls'? (yes/no) ") == 2
    assert "ls  —  list" in term.output


def test_ac6_no_close_match_says_unknown() -> None:
    """AC 6: xyzzy prints the not-found message and asks again."""
    _, term = run_session(["yes", "xyzzy", "quit"])
    assert "Sorry, I don't know 'xyzzy'. Check the spelling and try again." in term.lines
    assert term.prompts[-1] == PROMPT


# --- Not covered (SPEC.md §9, ADR 0011) ---------------------------------


def test_third_party_tool_is_not_covered() -> None:
    """git gets the 'isn't a built-in terminal command' message."""
    _, term = run_session(["yes", "git push", "quit"])
    assert "'git' isn't a built-in terminal command, so it isn't covered." in term.lines


def test_uncovered_builtin_is_not_suggested_as_something_else() -> None:
    """unset gets 'not covered yet', not 'Did you mean unsetopt?' (ADR 0011)."""
    _, term = run_session(["yes", "unset FOO", "quit"])
    assert "'unset' is a real command, but I don't cover it yet." in term.lines
    assert not any("Did you mean" in prompt for prompt in term.prompts)


# --- AC 7: shell-specific commands ---------------------------------------


def test_ac7_zsh_command_in_bash_asks_first() -> None:
    """AC 7: setopt in bash mode warns and offers to explain anyway."""
    _, term = run_session(["setopt", "yes", "quit"], argv=["--shell", "bash"])
    question = "'setopt' is a zsh command and doesn't work in bash. Explain it anyway? (yes/no) "
    assert question in term.prompts
    assert "setopt  —  set option" in term.output


def test_ac7_saying_no_skips_explanation() -> None:
    """Saying no to the other-shell question goes back to the prompt."""
    _, term = run_session(["shopt", "no", "quit"], argv=["--shell", "zsh"])
    assert "shopt  —" not in term.output
    assert term.prompts[-1] == PROMPT


def test_command_in_own_shell_is_not_questioned() -> None:
    """setopt in zsh mode is explained straight away."""
    _, term = run_session(["setopt", "quit"], argv=["--shell", "zsh"])
    assert not any("Explain it anyway" in prompt for prompt in term.prompts)
    assert "setopt  —  set option" in term.output


# --- AC 8: exiting --------------------------------------------------------


@pytest.mark.parametrize("word", ["quit", "q", "QUIT", "  q  "])
def test_ac8_quit_words_exit_cleanly(word: str) -> None:
    """AC 8: quit and q (any case) say goodbye and exit with code 0."""
    code, term = run_session(["yes", word])
    assert code == 0
    assert term.lines[-1] == "Goodbye!"


@pytest.mark.parametrize("prompt_number", [0, 1, 2])
def test_ac8_ctrl_c_at_any_prompt_exits_cleanly(prompt_number: int) -> None:
    """AC 8: Ctrl+C at the shell question, the command prompt, or a yes/no prompt exits cleanly."""
    code, term = run_session(["yes", "sl", "yes"], interrupt_at=prompt_number)
    assert code == 0
    assert term.lines[-1] == "Goodbye!"


@pytest.mark.parametrize("answers", [[], ["yes"], ["yes", "sl"]])
def test_ac8_ctrl_d_at_any_prompt_exits_cleanly(answers: list[str]) -> None:
    """AC 8: Ctrl+D (end of input) at any prompt exits cleanly."""
    code, term = run_session(answers)
    assert code == 0
    assert term.lines[-1] == "Goodbye!"


def test_ac8_exit_is_explained_with_tip() -> None:
    """AC 8: `exit` is explained, then a tip says how to leave."""
    _, term = run_session(["yes", "exit", "quit"])
    assert "exit  —  leave the shell" in term.output
    assert '(Tip: type "quit" to leave this program.)' in term.lines
    assert term.prompts[-1] == PROMPT  # still running after exit


# --- Switching shells (ADR 0016) ----------------------------------------


def test_shell_word_switches_shell() -> None:
    """Typing `shell` asks again, and later explanations use the new shell."""
    _, term = run_session(["shell", "bash", "setopt", "no", "quit"], argv=["--shell", "zsh"])
    assert "Switched to bash." in term.lines
    assert any("doesn't work in bash" in prompt for prompt in term.prompts)


# --- Input errors (SPEC.md §3.2) -----------------------------------------


@pytest.mark.parametrize(
    ("typed", "message"),
    [
        ('echo "hi', 'It looks like a quote (") is missing its partner. Please re-enter it.'),
        ("echo hi\\", "Your command ends with a backslash (\\), which needs something after it. "
                      "Please re-enter it."),
        ("'' -l", "The command name is empty. Please re-enter it."),
    ],
)
def test_parse_errors_have_their_own_messages(typed: str, message: str) -> None:
    """Each kind of unreadable input gets its own message, then the prompt again."""
    _, term = run_session(["yes", typed, "quit"])
    assert message in term.lines
    assert term.prompts[-1] == PROMPT


# --- sudo and inner commands (ADR 0015) ----------------------------------


def test_sudo_inner_typo_gets_suggestion() -> None:
    """sudo sl -la -> 'Did you mean ls?'; yes explains sudo ls -la."""
    _, term = run_session(["yes", "sudo sl -la", "yes", "quit"])
    assert "Did you mean 'ls'? (yes/no) " in term.prompts
    assert "sudo runs this command:" in term.output
    assert "ls  —  list" in term.output


def test_sudo_inner_typo_no_drops_whole_input() -> None:
    """Saying no to the inner suggestion drops the whole input."""
    _, term = run_session(["yes", "sudo sl", "no", "quit"])
    assert "Command not found. Please re-enter it." in term.lines
    assert "sudo  —" not in term.output


def test_sudo_inner_value_is_not_treated_as_typo() -> None:
    """sudo -u bob ls: bob is a value, so nothing asks 'Did you mean ...' about it."""
    _, term = run_session(["yes", "sudo -u bob ls", "quit"])
    assert not any("Did you mean" in prompt for prompt in term.prompts)
    assert "ls  —  list" in term.output


def test_sudo_inner_not_covered_still_explains_sudo() -> None:
    """sudo git push: say git isn't covered, and still explain sudo."""
    _, term = run_session(["yes", "sudo git push", "quit"])
    assert "'git' isn't a built-in terminal command, so it isn't covered." in term.lines
    assert "sudo  —  superuser do" in term.output


def test_sudo_inner_unknown_still_explains_sudo() -> None:
    """sudo xyzzy: explain sudo and say it doesn't know xyzzy."""
    _, term = run_session(["yes", "sudo xyzzy", "quit"])
    assert "sudo  —  superuser do" in term.output
    assert "which I don't have an explanation for" in term.output


def test_sudo_outer_typo_is_fixed_too() -> None:
    """sduo rm x -> 'Did you mean sudo?', then rm is explained inside it."""
    _, term = run_session(["yes", "sduo rm x", "yes", "quit"])
    assert "Did you mean 'sudo'? (yes/no) " in term.prompts
    assert "rm  —  remove" in term.output


def test_quoted_arguments_survive_a_spelling_fix() -> None:
    """Fixing the command name keeps quoted arguments intact."""
    _, term = run_session(["yes", 'fnid . -name "my file.txt"', "yes", "quit"])
    assert "argument: my file.txt" in term.output


# --- Data errors (SPEC.md §9) --------------------------------------------


@pytest.mark.parametrize("setting", ["COMMANDS_FILE", "NOT_COVERED_FILE", "OPERATORS_FILE"])
@pytest.mark.parametrize("content", ["{not json", None])
def test_broken_data_file_exits_with_code_1(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    setting: str,
    content: str | None,
) -> None:
    """A broken or missing data file prints a clear error to stderr and exits with code 1."""
    bad = tmp_path / "data.json"
    if content is not None:
        bad.write_text(content, encoding="utf-8")
    monkeypatch.setattr(lookup, setting, bad)
    caches = (lookup.default_commands, lookup.default_not_covered, lookup.default_operators)
    for cache in caches:
        cache.cache_clear()
    try:
        code, term = run_session(["yes", "ls"])
    finally:
        for cache in caches:
            cache.cache_clear()
    assert code == 1
    assert "Error: Data file" in capsys.readouterr().err
    assert term.prompts == []


def test_module_runs_with_python_m(monkeypatch: pytest.MonkeyPatch) -> None:
    """`python -m commandexplain` calls main() and exits with its code."""
    import runpy

    monkeypatch.setattr(cli, "main", lambda: 0)
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("commandexplain", run_name="__main__")
    assert excinfo.value.code == 0


# --- Phase 3 review fixes -------------------------------------------------

# (answers that reach the prompt, text the last prompt must contain, description).
PROMPT_PATHS = [
    ([], "Looks like you're using zsh", "detected-shell question"),
    (["no"], MANUAL_PROMPT, "manual shell question"),
    (["yes"], PROMPT, "command prompt"),
    (["yes", "sl"], "Did you mean 'ls'?", "Did you mean question"),
    (["yes", "shopt"], "doesn't work in zsh", "other-shell question"),
    (["yes", "shell"], MANUAL_PROMPT, "shell switch question"),
    (["yes", "sl | grpe x", "yes"], "Did you mean 'grep'?", "second suggestion in a chain"),
    (["yes", "ls ; shopt -s x"], "doesn't work in zsh", "other-shell question in a chain"),
]
PROMPT_IDS = [where for _, _, where in PROMPT_PATHS]


@pytest.mark.parametrize(("answers", "expected", "where"), PROMPT_PATHS, ids=PROMPT_IDS)
def test_ctrl_c_at_every_prompt_exits_cleanly(
    answers: list[str], expected: str, where: str
) -> None:
    """Ctrl+C at any prompt says goodbye with exit code 0 and no traceback."""
    code, term = run_session(answers, interrupt_at=len(answers))
    assert expected in term.prompts[-1], f"{where}: never reached that prompt"
    assert code == 0, where
    assert term.lines[-1] == "Goodbye!"


@pytest.mark.parametrize(("answers", "expected", "where"), PROMPT_PATHS, ids=PROMPT_IDS)
def test_ctrl_d_at_every_prompt_exits_cleanly(
    answers: list[str], expected: str, where: str
) -> None:
    """Ctrl+D (end of input) at any prompt says goodbye with exit code 0."""
    code, term = run_session(answers)
    assert expected in term.prompts[-1], f"{where}: never reached that prompt"
    assert code == 0, where
    assert term.lines[-1] == "Goodbye!"


@pytest.mark.parametrize(
    "name",
    ["dd", "id", "od", "ed", "rg", "fd", "pgrep", "htop", "cmp", "nc", "zcat", "bash", "sh"],
)
def test_real_commands_are_never_corrected_to_others(name: str) -> None:
    """Real commands outside the data get 'not covered', never 'Did you mean' (ADR 0017)."""
    _, term = run_session(["yes", name, "quit"])
    assert not any("Did you mean" in prompt for prompt in term.prompts)
    assert any(f"'{name}'" in line and "cover" in line for line in term.lines)


@pytest.mark.parametrize("name", sorted(lookup.load_commands()))
def test_correct_spellings_never_get_a_suggestion(name: str) -> None:
    """Every command in the data is explained straight away, with no 'Did you mean'."""
    _, term = run_session([name, "yes", "quit"], argv=["--shell", "zsh"])
    assert not any("Did you mean" in prompt for prompt in term.prompts)
    assert f"{name}  —" in term.output


def test_ac14_switch_changes_shell_notes() -> None:
    """AC 14: after switching, explanations show the new shell's notes."""
    _, term = run_session(["rm x", "shell", "bash", "rm x", "quit"], argv=["--shell", "zsh"])
    before, after = term.output.split("Switched to bash.")
    assert "Note for zsh:" in before
    assert "Note for zsh:" not in after


@pytest.mark.parametrize("other", ["sh", "ksh", "dash", "fish"])
def test_other_real_shells_are_not_corrected(other: str) -> None:
    """sh isn't turned into zsh: it's told only bash and zsh are covered, then the hint."""
    _, term = run_session([other, "bash", "quit"], env=NO_SHELL_ENV)
    assert not any("Did you mean" in prompt for prompt in term.prompts)
    assert UNSUPPORTED.format(name=other) in term.lines
    assert HINT in term.lines
    assert "Using bash." in term.output


def test_hint_follows_a_declined_shell_suggestion() -> None:
    """Saying no to 'Did you mean zsh?' shows the hint before asking again."""
    _, term = run_session(["zhs", "no", "zsh", "quit"], env=NO_SHELL_ENV)
    assert HINT in term.lines


@pytest.mark.parametrize("word", ["quit", "q", "Q"])
def test_quit_at_shell_questions(word: str) -> None:
    """quit works at the manual shell question, with no stray blank line."""
    code, term = run_session([word], env=NO_SHELL_ENV)
    assert code == 0
    assert term.lines == ["Goodbye!"]


def test_quit_at_shell_switch_question() -> None:
    """quit after typing 'shell' by mistake leaves the program."""
    code, term = run_session(["shell", "quit"], argv=["--shell", "zsh"])
    assert code == 0
    assert term.lines[-1] == "Goodbye!"


@pytest.mark.parametrize(("answer", "shell"), [("zsh", "zsh"), ("bash", "bash"), ("2", "zsh")])
def test_detected_question_accepts_a_shell_name(answer: str, shell: str) -> None:
    """Answering 'Is that right?' with a shell name picks that shell."""
    _, term = run_session([answer, "quit"], env=ZSH_ENV)
    assert f"Using {shell}." in term.output
    assert "Please type yes or no." not in term.lines


@pytest.mark.parametrize("typed", ["shell bash", "SHELL BASH", "shell 1"])
def test_shell_with_name_switches_at_once(typed: str) -> None:
    """'shell bash' switches without asking."""
    _, term = run_session([typed, "quit"], argv=["--shell", "zsh"])
    assert "Switched to bash." in term.lines
    assert MANUAL_PROMPT not in term.prompts


def test_shell_with_unknown_name_asks() -> None:
    """'shell fish' asks the bash-or-zsh question."""
    _, term = run_session(["shell fish", "zsh", "quit"], argv=["--shell", "bash"])
    assert MANUAL_PROMPT in term.prompts
    assert "Switched to zsh." in term.lines


# --- Chains (Phase 4) ------------------------------------------------------


def test_ac9_pipe_in_session() -> None:
    """AC 9: a pipe is explained part by part in a real session."""
    _, term = run_session(["yes", "ls -a | grep txt", "quit"])
    assert "|  (pipe)" in term.output
    assert "In short: list files, then pass the output to find matching lines." in term.output


def test_ac10_typo_in_chain_is_asked_about_first() -> None:
    """AC 10: sl | grep x asks "Did you mean 'ls'?" before explaining the chain."""
    _, term = run_session(["yes", "sl | grep x", "yes", "quit"])
    assert "Did you mean 'ls'? (yes/no) " in term.prompts
    assert "ls\n  ls — list:" in term.output
    assert "|  (pipe)" in term.output


def test_typos_in_several_segments_are_each_asked() -> None:
    """Each segment gets its own suggestion."""
    _, term = run_session(["yes", "sl | grpe x", "yes", "yes", "quit"])
    assert "Did you mean 'ls'? (yes/no) " in term.prompts
    assert "Did you mean 'grep'? (yes/no) " in term.prompts
    assert "grep x\n  grep — search text:" in term.output


def test_no_to_any_suggestion_drops_whole_chain() -> None:
    """Saying no to one suggestion drops the whole input (SPEC.md §3.3.1)."""
    _, term = run_session(["yes", "ls | grpe x", "no", "quit"])
    assert "Command not found. Please re-enter it." in term.lines
    assert "(pipe)" not in term.output


def test_unknown_segment_drops_whole_chain() -> None:
    """A segment with no suggestion drops the input with the 'don't know' message."""
    _, term = run_session(["yes", "ls | xyzzy", "quit"])
    assert "Sorry, I don't know 'xyzzy'. Check the spelling and try again." in term.lines
    assert "(pipe)" not in term.output


def test_not_covered_segment_is_explained_in_place() -> None:
    """ls | sort explains ls, and sort's block says it isn't covered, without a separate line."""
    _, term = run_session(["yes", "ls | sort", "quit"])
    assert "ls\n  ls — list:" in term.output
    assert "'sort' is a real command, but I don't cover it yet." in term.output
    assert "'sort' is a real command, but I don't cover it yet." not in term.lines


@pytest.mark.parametrize(
    ("typed", "message"),
    [
        ("| grep x", 'Something is missing before "|". Please re-enter it.'),
        ("ls &&", 'Something is missing after "&&". Please re-enter it.'),
        ("ls 2>/dev/null", 'Sorry, I can\'t explain "2>" yet. Try a simpler version of the '
                           "command."),
        ("sleep 5 &", 'Sorry, I can\'t explain "&" yet. Try a simpler version of the command.'),
    ],
)
def test_chain_errors_have_messages(typed: str, message: str) -> None:
    """Missing sides and unsupported syntax get their own messages (§3.2, ADR 0019)."""
    _, term = run_session(["yes", typed, "quit"])
    assert message in term.lines
    assert term.prompts[-1] == PROMPT


def test_other_shell_command_in_chain_is_asked_about() -> None:
    """A zsh-only command in a chain gets the question; 'no' says so and drops the input."""
    _, term = run_session(["ls ; setopt autocd", "no", "quit"], argv=["--shell", "bash"])
    assert any("doesn't work in bash" in prompt for prompt in term.prompts)
    assert "OK, I won't explain it. Please re-enter the command." in term.lines
    assert "(then)" not in term.output


def test_other_shell_no_for_single_command_stays_quiet() -> None:
    """For a single command, 'no' just goes back to the prompt, as before."""
    _, term = run_session(["setopt", "no", "quit"], argv=["--shell", "bash"])
    assert "OK, I won't explain it. Please re-enter the command." not in term.lines


def test_exit_in_chain_gets_tip() -> None:
    """exit anywhere in a chain still gets the 'type quit' tip."""
    _, term = run_session(["yes", "echo bye ; exit", "quit"])
    assert '(Tip: type "quit" to leave this program.)' in term.lines


def test_quoted_arguments_survive_a_fix_in_a_chain() -> None:
    """Fixing a typo in a chain keeps quoted arguments and redirect files intact."""
    _, term = run_session(["yes", 'ehco "a | b" > "my file.txt"', "yes", "quit"])
    assert "argument: a | b" in term.output
    assert "file: my file.txt" in term.output


def test_chain_header_keeps_the_users_quoting() -> None:
    """Block headers show the text as typed: $HOME isn't turned into '$HOME'."""
    _, term = run_session(["yes", 'echo "a b" $HOME | wc', "quit"])
    assert '\necho "a b" $HOME\n' in "\n" + term.output + "\n"


def test_chain_header_shows_spelling_fix_and_keeps_quoting() -> None:
    """A fixed command name appears in the header, with the rest as typed."""
    _, term = run_session(["yes", 'sl -la "$HOME" | wc', "yes", "quit"])
    assert '\nls -la "$HOME"\n' in "\n" + term.output + "\n"


@pytest.mark.parametrize(
    ("typed", "header"), [("LS -A | wc", "LS -A"), (". ~/.bashrc ; ls", ". ~/.bashrc")]
)
def test_chain_header_keeps_names_as_typed(typed: str, header: str) -> None:
    """Without a spelling fix, the header shows the name exactly as typed."""
    _, term = run_session(["yes", typed, "quit"])
    assert f"\n{header}\n" in "\n" + term.output + "\n"


def test_comment_sign_is_unsupported_in_session() -> None:
    """ls # list | grep x names '#' instead of explaining a pipe."""
    _, term = run_session(["yes", "ls # list | grep x", "quit"])
    assert 'Sorry, I can\'t explain "#" yet. Try a simpler version of the command.' in term.lines
    assert "(pipe)" not in term.output
