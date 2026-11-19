"""Work out which shell (bash or zsh) the user is using (SPEC.md §3.1, ADR 0003)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import PurePosixPath

from commandexplain.lookup import suggest

SHELLS = ("bash", "zsh")
SHELL_ANSWERS = {"bash": "bash", "1": "bash", "zsh": "zsh", "2": "zsh"}
# Real shells this program doesn't support. Never "corrected" to bash or zsh (ADR 0017).
OTHER_SHELLS = frozenset(
    {"sh", "ksh", "dash", "csh", "tcsh", "fish", "pwsh", "powershell", "cmd", "nu"}
)
# suggest() takes command-style entries, so the two shells are given in that shape.
_SHELL_NAMES = {name: {"aliases": []} for name in SHELLS}

MANUAL_PROMPT = "Are you using bash or zsh? "
HINT = 'Please type bash or zsh. Not sure? Run "echo $SHELL" in your terminal.'
UNSUPPORTED = "Sorry, this program only covers bash and zsh, not {name}."


def detect_shell(env: Mapping[str, str]) -> str | None:
    """Return 'bash' or 'zsh' from the SHELL environment variable, or None if it's neither."""
    name = PurePosixPath(env.get("SHELL", "").strip()).name.lower()
    return name if name in SHELLS else None


def read_shell_answer(text: str) -> str | None:
    """Turn an answer like ' ZSH ' or '1' into 'bash' or 'zsh', or None if it's neither."""
    return SHELL_ANSWERS.get(text.strip().lower())


def _plain(text: str) -> str:
    """Leave text unchanged (the default when no color is wanted)."""
    return text


def ask_shell(
    ask: Callable[[str], str],
    confirm: Callable[[str], bool],
    say: Callable[[str], None],
    highlight: Callable[[str], str] = _plain,
) -> str:
    """Ask "bash or zsh?" until the answer is valid.

    Small typos get "Did you mean ...?". Other real shells (sh, fish, ...) are
    told they aren't supported. Every answer that isn't accepted is followed by
    the hint (SPEC.md §3.1). `highlight` colors the "Did you mean" question.
    """
    while True:
        answer = ask(MANUAL_PROMPT)
        shell = read_shell_answer(answer)
        if shell:
            return shell
        word = answer.strip().lower()
        if word in OTHER_SHELLS:
            say(UNSUPPORTED.format(name=word))
        else:
            guess = suggest(word, _SHELL_NAMES)
            if guess and confirm(highlight(f"Did you mean {guess}?")):
                return guess
        say(HINT)


def confirm_detected(
    detected: str, ask: Callable[[str], str], say: Callable[[str], None]
) -> str | None:
    """Ask whether the detected shell is right.

    Returns the chosen shell, or None to fall back to the manual question.
    Besides yes/no, the user can answer with a shell name ('bash').
    """
    while True:
        answer = ask(f"Looks like you're using {detected}. Is that right? (yes/no) ")
        word = answer.strip().lower()
        if word in ("y", "yes"):
            return detected
        if word in ("n", "no"):
            return None
        shell = read_shell_answer(word)
        if shell:
            return shell
        say("Please type yes or no.")


def choose_shell(
    ask: Callable[[str], str],
    confirm: Callable[[str], bool],
    say: Callable[[str], None],
    env: Mapping[str, str],
    highlight: Callable[[str], str] = _plain,
) -> str:
    """Detect the shell and confirm it, or ask the user if it can't be detected or is wrong."""
    detected = detect_shell(env)
    if detected:
        chosen = confirm_detected(detected, ask, say)
        if chosen:
            return chosen
    return ask_shell(ask, confirm, say, highlight)
