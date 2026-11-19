# Handoff 003 — Phase 3: Interactive CLI

**Date:** 2026-11-19
**Status:** Phase 3 complete, waiting for approval to start Phase 4.

## What was done
- **`commandexplain/shell.py`:**
  - Detects bash or zsh from `$SHELL` and confirms it. The confirmation also accepts a shell name.
  - Falls back to "Are you using bash or zsh?", which accepts `1`/`2`, ignores case, and offers "Did you mean" for typos.
  - Other real shells (`sh`, `fish`, ...) get "only covers bash and zsh". The hint follows every answer that isn't accepted.
- **`commandexplain/cli.py`:**
  - The main loop, through injectable `input_fn` and `print_fn`. `Console` handles prompts and yes/no questions.
  - `Session` resolves each command in a sudo chain in this order: known command, then the not-covered list, then a suggestion (ADRs 0011 and 0015).
  - It asks before explaining a command from the other shell (§3.4).
  - Typing `exit` gets its explanation plus a tip.
  - `quit`/`q` and Ctrl+C/Ctrl+D work at every prompt.
  - `shell` and `shell bash` switch shells (ADRs 0016 and 0017).
  - Each `ParseError.reason` has its own message.
  - A broken or missing data file prints an error to stderr and exits with code 1.
- **`commandexplain/__main__.py` and `pyproject.toml`:** `python -m commandexplain` works, and `pip install -e .` installs a working `commandexplain` command (tested in a throwaway environment). The `--shell bash|zsh` option skips the shell question.
- **`commandexplain/data/not_covered.json`:** 95 names. `tool` covers things like git, brew, rg, and htop. `uncovered` covers things like unset, sort, dd, and bash.
- **`lookup.py`:** `load_not_covered()`, `default_not_covered()`, and `not_covered_kind()`.
- **Spec:**
  - Closed both open questions: keep 35 commands, and add shell switching.
  - Added acceptance criteria 14 and 15, the §5.2 data format, and the wording for two input errors.
  - Added ADRs 0015–0017.

## Review
`/phase-review 3` gave **PASS WITH FIXES** (0 blockers, 4 should-fix, 4 nits). The report is `docs/reviews/phase-3-review.md`. Everything was fixed, as approved:
- **Real commands miscorrected:** `dd`/`id`/`rg`/`htop`/`bash` and others were being "corrected" into other commands. They're now on the not-covered list.
- **Shell question:** the hint now follows every rejected answer, other real shells aren't corrected, and `quit` works there.
- **ADR 0017** records the error wording, the not-covered format, the command-list decision, and the shell-question conveniences.
- **Missing tests added:** Ctrl+C and Ctrl+D at all 6 kinds of prompt, both data files broken or missing, all 35 correct spellings never getting a suggestion, and AC 14 checked through a shell note.
- **Nits:**
  - `SHELLS` is defined once.
  - The dead fallback is replaced by an explicit error.
  - `readme` is dropped from `pyproject.toml` until Phase 5 adds a README.
  - `shell bash` works.
  - The detected-shell question accepts a shell name.

## Current state
- **Works:** the full interactive program for single commands, including sudo chains. Acceptance criteria 1–8, 12, 14, and 15 pass, along with all earlier ones.
- **Expected until Phase 4:** pipes and chains aren't parsed yet. `ls -a|grep x` is read as `ls` with odd flags (the reviewer saw a made-up `-r`), and `ls | grep x` lists `|` as an argument. Phase 4 fixes this.
- **Not built yet:** colors, `--no-color`, and the README (Phase 5).

## Tests
`pytest -q` → **809 passed**.

## Open issues and questions
- No open spec questions.
- `ll`/`la` → "Did you mean 'ln'?" is still an accepted limitation (ADR 0011).
- The not-covered list will need to grow as people try more commands. Adding to it is a data change only.

## Next steps (Phase 4, after approval)
- `parser.py`: switch to `shlex.shlex(..., punctuation_chars=True)`, split the input into segments at `|`, `&&`, `||`, `;`, `>`, `>>`, and `<`, and treat the word after `>`, `>>`, or `<` as a filename. Add the "Something is missing before/after" message (§3.2).
- `formatter.py`: the chain output from §3.3.1, with operators from `operators.json` and the optional "In short" line.
- `cli.py`: resolve each segment with the same steps as now. A **no** to any suggestion drops the whole input (§3.3.1). Reuse `_resolve_tokens` for each segment.
- Add `short` phrases to `commands.json`.
- Acceptance criteria 9 and 10.
