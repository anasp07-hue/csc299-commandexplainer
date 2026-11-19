# 0003. Auto-detect the shell, then confirm

## Status
Accepted (2026-11-19)

## Context
The program must know whether the user is on bash or zsh. Many beginners don't know which shell they use, so asking with no hint can confuse them.

## Decision
Read the `SHELL` environment variable. If it is bash or zsh, ask the user to confirm it ("Looks like you're using zsh. Is that right?"). If the user says no, or the variable is missing or names another shell, fall back to asking "bash or zsh?" with a hint to run `echo $SHELL` (SPEC.md §3.1). A `--shell` command-line option skips the question.

## Consequences
- Most users only need to answer "yes".
- `$SHELL` shows the user's login shell, which can differ from the shell they're actually running. The confirmation step covers this.
- Tests must control `SHELL` in their environment.
