# Handoff 005 — Phase 5: Colors and polish

**Date:** 2026-11-19
**Status:** Phase 5 complete. **All five phases are done.** Every acceptance criterion (1–16) passes.

## What was done
- **`commandexplain/colors.py`:**
  - `Palette` has one method per purpose: command (bold), flag (cyan), warning (red), suggestion (yellow), and operator (magenta).
  - `colors_enabled()` turns colors off when output isn't a terminal, when `NO_COLOR` is non-empty, or with `--no-color`.
  - `strip_colors()` is mainly for tests.
- **`formatter.py`:** colors are added *after* wrapping (ADR 0020), so the colored output with codes stripped is identical to the plain output.
- **`cli.py`:**
  - The `--no-color` option, plus an injectable `isatty`.
  - Yellow "Did you mean" questions, at the shell question too, through `shell.py`'s `highlight` parameter.
  - A clean error and exit code 1 when output is closed.
- **`README.md`:** what the program does, install (with a virtual environment), run, an example session (checked to match real output), what it covers, how to add a command (checked by following it in a scratch copy), and development. `pyproject.toml` points at it.
- **Wording pass:**
  - "Print" became "Show" across the data, since beginners may think of a printer.
  - Explained "path", "shell", "signal", and "function".
  - Reworded `ls -t`, and made the `mkdir -p`/`rmdir -p` examples match.
  - Clarified the pipe's explanation ("the output of the left command (what it would show on screen)").
- **Cleanup:** removed the unused `parse_input()` and `ParsedInput`. Their tests now use `parse_chain()`.
- **Spec:** §3.3.2 colors detail, a §9 row for closed output, and ADR 0020.

## Review
`/phase-review 5` gave **PASS WITH FIXES** (0 blockers, 2 should-fix, 5 nits). The report is `docs/reviews/phase-5-review.md`. The reviewer checked colors in a real terminal, all three ways of turning them off, and the README example. All findings were fixed, as approved:
- **README walkthrough:** following its "Adding a command" steps broke 2 tests. Those tests no longer depend on the real data. Re-checked by following the README in a scratch copy: 1104 passed.
- **Jargon:** "signal" is now explained in kill's summary, and "function" in which's zsh note.
- **Nits:**
  - The `mkdir`/`rmdir -p` wording is consistent.
  - The parser docstring is updated, and the dead `parse_input()` is removed.
  - Closed stdout no longer crashes. Testing it for real found a second crash, in `input()`, which now gives a clean exit 1.
  - A test checks that `main()` uses the real terminal check and environment by default.
  - The README installs inside a virtual environment.

## Current state
- **The full program works:** shell detection, single commands, sudo, pipes, chains, redirects, typo suggestions everywhere, the not-covered list, honest limits for unsupported syntax, colors, and clean exits.
- `pip install -e .` gives a `commandexplain` command, and `python3 -m commandexplain` also works.

## Tests
`pytest -q` → **1087 passed**.

## Open issues and ideas for later
- More commands. Adding one is data only (README "Adding a command"). Good next candidates are on the not-covered list: `sort`, `uniq`, `curl`, `tar`, `ssh`.
- Per-flag warnings: `rm` always warns, not only with `-rf` (noted since Phase 1).
- The "In short" line is generic. It doesn't mention arguments.
- `ll`/`la` → "Did you mean 'ln'?" is still an accepted limitation (ADR 0011).
- Possible later features: explaining arguments (ADR 0004 left this out), `$(...)` and `2>&1` (ADR 0019 names them as unsupported), and more shells.

## Next steps
None planned. The spec's five phases are complete.
