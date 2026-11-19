# Handoff 002 — Phase 2: Explain one command

**Date:** 2026-11-19
**Status:** Phase 2 complete, waiting for approval to start Phase 3.

## What was done
- **`commandexplain/parser.py`:**
  - `tokenize()` and `parse_input()` split text the way a shell would. Quotes keep phrases together, and any Unicode space counts as a space.
  - `split_flags()` sorts words into flags, arguments, and an inner command. It follows SPEC §3.2 steps 3–8:
    - whole-token-first matching (ADR 0007),
    - flag token details (ADR 0009),
    - wrappers like sudo (ADR 0010),
    - `keep_flags_whole` (ADR 0014).
  - `ParseError` has a `reason`: `UNCLOSED_QUOTE`, `TRAILING_BACKSLASH`, or `EMPTY_COMMAND`. It is deliberately not a `ValueError`.
- **`commandexplain/lookup.py`:**
  - `default_commands()` reads the data from disk only once.
  - `find_command()` handles exact matches, case, spaces, and aliases.
  - `is_one_edit()` plus `suggest()` follow the two-step rule (ADR 0006), limited to input with letters (ADR 0011).
- **`commandexplain/formatter.py`:**
  - `format_explanation()` builds the plain-text layout from §3.3:
    - typed flags, or common options (ADR 0008),
    - one `argument:` line each (ADR 0012),
    - warning, shell note, and example,
    - a long label goes on its own line.
  - `explain()` goes from typed text to explanation. It explains sudo's inner command in a loop, adding the builtin warning (ADR 0013). It raises `EmptyInputError`, `ValueError` (bad shell), `ParseError`, or `UnknownCommandError`.
- **Data:**
  - `sudo` gets `runs_command`, `flags_with_values`, and the new flags `--user`, `-g`, and `--group`.
  - `kill` gets `-KILL`, `-15`, `-TERM`, `-HUP`, and `keep_flags_whole`.
  - Nine shell builtins get `builtin_only`.
- **Tests:** `test_parser.py`, `test_formatter.py`, plus additions to `test_lookup.py` and `test_data.py`.

## Review
- **First review** (`docs/reviews/phase-2-review.md`): **FAIL**, 1 blocker, 3 should-fix, 4 nits.
  - The blocker: everything after `sudo` was read as sudo's own flags. `sudo rm -i` explained `-i` as "start an administrator session", and `sudo rm -rf /` never showed rm's warning.
  - All findings were fixed, as approved (ADRs 0010–0012).
- **Re-review** (`docs/reviews/phase-2-review-2.md`): **PASS WITH FIXES**, 0 blockers, 3 should-fix, 5 nits. All were fixed, as approved:
  - `sudo cd` now gets a builtin warning (ADR 0013).
  - Added sudo `--user`/`-g`, and a `--user=bob` value isn't taken twice.
  - Nested sudo is explained in a loop, so 2000 nested `sudo`s don't crash.
  - Signal names like `-INT` stay whole (ADR 0014).
  - Long labels no longer squeeze the column.
  - `ParseError` has a `reason`.
  - Added the missing tests, and fixed the spec's step range.

## Current state
- **Works:**
  - `explain("rm -rf", shell="zsh")` gives the full explanation, with the warning (acceptance criterion 3).
  - `explain("ls", ...)` shows the summary and common options (acceptance criterion 2).
  - `suggest("sl")` returns `"ls"`.
  - `sudo rm -rf /` explains both sudo and rm, with both warnings.
- **Not built yet (on purpose):** the interactive CLI, shell detection, the yes/no flow, the "not covered" list, chains, and colors.

## Tests
`pytest -q` → **670 passed**.

## Open issues and questions
- SPEC §13 open questions are still open: the size of the command list, and switching shells mid-session.
- `unset` → "Did you mean unsetopt?" is still there. ADR 0011 moves the fix to Phase 3's "not covered" list, which must be checked **before** `suggest()`.
- `sudo sl` reports "sudo runs "sl", which I don't have an explanation for" without a suggestion. Phase 3 could offer suggestions for inner commands too. That needs a decision.
- **Phase 3 messages:** map `ParseError.reason` to the right user message. Only `UNCLOSED_QUOTE` has its wording in the spec (§3.2). `TRAILING_BACKSLASH` and `EMPTY_COMMAND` need wording.
- `ll`/`la` → "Did you mean ln?" is a known, accepted limitation (ADR 0011).

## Next steps (Phase 3, after approval)
- `shell.py`: detect the shell from `$SHELL`, confirm with yes/no, and fall back to asking (§3.1).
- `cli.py`:
  - the main loop and the yes/no prompts,
  - "Did you mean" (§4),
  - shell-only commands (§3.4),
  - quit, Ctrl+C, and Ctrl+D (§3.5),
  - the "not covered" list in data, checked before suggestions (§9, ADR 0011),
  - catching `DataFileError` and exiting with code 1.
- `__main__.py`, `pyproject.toml`, and the `--shell` option.
- `tests/test_cli.py` with simulated sessions through `input_fn` and `print_fn`.
