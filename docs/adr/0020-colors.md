# 0020. How colors are applied and when they turn off

## Status
Accepted (2026-11-19). Fills in SPEC.md §3.3.2 and builds on ADR 0005.

## Context
ADR 0005 decided to use ANSI colors and to turn them off when output isn't a terminal, when `NO_COLOR` is set, or with `--no-color`. Building it raised three questions:
1. Color codes are invisible but still count as characters. If colors were added before wrapping, lines would wrap early and the columns would shift.
2. Does `NO_COLOR=""` (set, but empty) turn colors off?
3. How should tests and the CLI decide whether output is a terminal, without depending on how pytest itself is run?

## Decision
- `colors.py` has a small `Palette` with one method per purpose: `command` (bold), `flag` (cyan), `warning` (red), `suggestion` (yellow), and `operator` (magenta). Callers name what something **is**, not which color it gets. A disabled palette returns text unchanged.
- The formatter lays out and wraps **plain** text first, then colors whole words at known positions (the start of a title, flag labels, operator symbols) and whole warning lines after their indent. So the colored output, with the codes stripped, is exactly the plain output, and tests check this for every command.
- `NO_COLOR` turns colors off only when it's non-empty, following no-color.org.
- `main()` takes an `isatty` function (default `sys.stdout.isatty`). If it fails, or `sys.stdout` is missing because output was closed, colors stay off. When output is closed and the real `input()` is in use, `main()` prints an error to stderr and exits with code 1, because `input()` can't show a prompt. The test helper always passes "not a terminal" unless a test asks for one, so tests don't change when pytest runs in a terminal.
- "Did you mean" is yellow at the shell question too. `ask_shell()` and `choose_shell()` take a `highlight` function.

## Consequences
- Turning colors on or off never changes the words, the wrapping, or the alignment.
- Colors were checked in a real pseudo-terminal. `NO_COLOR=1` and `--no-color` were both checked to give zero color codes.
- `input()` prompts may contain color codes. That's safe, because the program never imports `readline`, which is the module that miscounts the width of prompts containing color codes.
