# Handoff 004 — Phase 4: Pipes and chains

**Date:** 2026-11-19
**Status:** Phase 4 complete, waiting for approval to start Phase 5.

## What was done
- **`commandexplain/parser.py`:**
  - `split_operators()` is a quote- and backslash-aware scanner that splits at unquoted `>>`, `&&`, `||`, `|`, `;`, `>`, and `<` (ADR 0019).
  - `parse_chain()` builds a `Chain` from `ChainCommand`s (words, redirects, and the typed text) and the joiners between them.
  - **Errors:**
    - an operator with nothing on one side (`MISSING_BEFORE` / `MISSING_AFTER`),
    - unsupported syntax (`UNSUPPORTED`): `&`, `2>`, `&>`, `>&`, `>|`, `|&`, `<<`, `<<<`, `( )`, `$(`, backticks, and `#` at the start of a word.
  - `retype()` applies spelling fixes while keeping the user's quoting. `chain_to_text()` rebuilds the line.
- **`commandexplain/formatter.py`:** chain output (ADR 0018).
  - **Command blocks:**
    - The header shows the text as typed.
    - Then `name — plain name: summary`, the typed flags, and the arguments.
    - Warnings and shell notes are kept.
    - No common options and no example.
  - **Operator blocks:** redirects name their file.
  - **"In short":** built from `short` phrases. It's left out when it couldn't be true: a not-covered command, sudo with a builtin, `> … |`, or two output redirects.
  - The shared helpers are reused by the single-command format.
- **`commandexplain/cli.py`:**
  - Each command in a chain is resolved separately: suggestions, the not-covered list, and the other-shell question.
  - A **no** to a suggestion drops the chain. A **no** to the other-shell question in a chain says so.
  - The new parse errors have messages.
  - Data loading, `operators.json` included, happens inside `main()`'s error handling.
- **Data:**
  - Each of the 35 commands has a 2–4 word `short` phrase.
  - Each of the 7 operators has a `short` phrase, using `{file}` for redirects.
  - Added `lookup.default_operators()`.
- **Spec:**
  - §3.2 steps 1–2 rewritten, §3.3.1 filled in, and §5.1 updated.
  - Added a §9 row and acceptance criterion 16.
  - Added ADRs 0018 and 0019. ADR 0019 supersedes the tokenizing part of ADR 0002.

## Review
- **First review** (`docs/reviews/phase-4-review.md`): **FAIL**, 1 blocker, 4 should-fix, 5 nits. The blocker was that a missing `operators.json` crashed with a traceback. All findings were fixed, as approved:
  - The data now loads inside the error handling.
  - Headers show the text as typed.
  - Stale spec text was fixed.
  - Declining the other-shell question in a chain now says so.
  - Added tests for the gaps.
  - Fixed the parser edge cases (`ls;2>x`, a lone `;`, `>|`).
  - Added the sudo lead-in for a not-covered inner command.
  - Fixed the PEP 8 blank lines.
- **Re-review** (`docs/reviews/phase-4-review-2.md`): **PASS WITH FIXES**, 0 blockers, 2 should-fix, 4 nits. A 200,000-input fuzz test found no header or round-trip bugs. All findings were fixed, as approved:
  - `#` is now unsupported.
  - "In short" is left out for sudo with a builtin, and for two output redirects.
  - Headers keep names as typed.
  - The Ctrl+C/D tests now check that the intended prompt was reached.
  - Spec typos are fixed.

## Current state
- **Works:**
  - Single commands, sudo chains, pipes, `&&`, `||`, `;`, and redirects, each with typo suggestions per command.
  - Acceptance criteria 1–10 and 12–16 pass.
- **Not built yet:**
  - colors and `--no-color`, acceptance criterion 11 (Phase 5),
  - the README (Phase 5).

## Tests
`pytest -q` → **961 passed**.

## Open issues and questions
- No open spec questions.
- The "In short" line is deliberately generic. It doesn't mention arguments.
- The not-covered list will keep growing as people try more commands. That's a data change only.
- `parse_input()` is no longer used by the program, only by tests, because `parse_chain()` replaced it. Phase 5's polish pass could remove it or keep it as a small helper.

## Next steps (Phase 5, after approval)
- `colors.py`: ANSI helpers. Turn colors off when stdout isn't a TTY, when `NO_COLOR` is set, or with `--no-color` (§3.3.2).
- Use colors in `formatter.py` and `cli.py`: bold command names, cyan flags, red warnings, yellow "Did you mean", and magenta operators. The text must stay the same with colors on or off.
- `README.md`: install, run, an example session, and how to add a command (`commands.json`, `short`, `not_covered.json`). Point `pyproject.toml`'s `readme` at it.
- A final wording pass over all explanations.
- Acceptance criteria 11 and 13.
