# Handoff 001 — Phase 1: Key-value data

**Date:** 2026-11-19
**Status:** Phase 1 complete, waiting for approval to start Phase 2.

## What was done
- `commandexplain/data/commands.json`: all 35 commands from SPEC.md §6 (32 shared, `shopt` bash-only, and `setopt`/`unsetopt` zsh-only). Every entry has a plain-English name, a 1–2 sentence summary, flags, common flags, an example, and a warning where needed. Shell notes and aliases are included where they apply.
- `commandexplain/data/operators.json`: the 7 operators from §5.1.
- `commandexplain/lookup.py`: `load_commands()` and `load_operators()` return dicts. `DataFileError` gives a clear message for each of these cases:
  - a missing or unreadable file,
  - text that isn't UTF-8,
  - invalid JSON (with the line and column),
  - a repeated key,
  - a top level that isn't key-value pairs,
  - an entry that isn't an object.
- `tests/test_data.py` checks the schema of every entry, and more:
  - field names and types,
  - shells,
  - flag key format,
  - common flags (must exist, at most 5),
  - summary length (at most 2 sentences),
  - shell notes,
  - aliases,
  - warnings on dangerous commands,
  - coverage of every command and operator in the spec.
- `tests/test_lookup.py` covers loader behavior and every error case.
- `conftest.py` at the repo root lets `pytest` import the package. It isn't in the §7 layout, but it's a harmless test helper.

## Review
`/phase-review 1` gave **PASS WITH FIXES** (0 blockers, 9 should-fix, 5 nits). The report is `docs/reviews/phase-1-review.md`. The user approved fixing everything, and all of it is done:
- **Loader:** a non-UTF-8 file, a duplicate key, or an entry that isn't an object now raises `DataFileError`, and each case has a test.
- **Data:**
  - `find` gets a warning and is added to the dangerous-commands test.
  - `ps` summary and `-e` corrected.
  - `cp -R` is now the common flag, with a note on how macOS handles a trailing slash.
  - Jargon reworded in `echo`, `export`, `top`, and `grep -E`.
  - `touch -a` now says "last read".
  - Added a bash `autocd` note for `cd`.
- **Tests:**
  - operator summaries are now length-checked,
  - aliases must be lowercase,
  - flag keys must match a format,
  - `common_flags` is capped at 5.
- **Spec changes, each with an ADR:**
  - **ADR 0006:** spelling suggestions check for one-edit typos first, then fall back to difflib ≥ 0.75. This fixes `sl` → `ls`, which could never work before.
  - **ADR 0007:** flags are matched as a whole token first, so `find`'s `-name` works, and split only when unknown.
  - **ADR 0008:** `common_flags` holds up to 5 beginner-useful flags and may be empty.
- **CLAUDE.md:** the line limit is now 99 characters, which PEP 8 allows for teams.

## Current state
- **Works:** loading and validating all command and operator data. `load_commands()["rm"]["flags"]["-r"]` returns "Delete folders and everything inside them."
- **Not built yet (on purpose):** parsing, lookup by name, suggestions, formatting, the CLI, chains, and colors. Those are Phases 2–5.

## Tests
`pytest -q` → **423 passed**.

## Open issues and questions
- SPEC §13 open questions are still open: (1) is the §6 command list the right size? (2) Should users be able to switch shells mid-session?
- **Per-flag warnings:** the spec mentions `rm -rf` and `chmod 777` as warning cases, but `warning` is per command, so `rm` always warns. That's fine for now. A per-flag warning field could be a later spec change.
- The `short` phrases for the "In short" line of a chain are deliberately left out. They belong to Phase 4.

## Next steps (Phase 2, after approval)
- `parser.py`: split one command into command / flags / arguments, matching the whole token first (ADR 0007). The parser needs the command's flag keys, so it parses after the command is looked up.
- `lookup.py`: `find_command()` (exact, case-insensitive, and alias) and `suggest()` using the two-step rule in §4 (ADR 0006). Unit-test the one-edit check against `sl`, `cta`, `pdw`, `cdd`, `mkdri`, and `xyzzy`.
- `formatter.py`: plain-text explanation per §3.3, leaving out "Common options" when the list is empty (ADR 0008).
