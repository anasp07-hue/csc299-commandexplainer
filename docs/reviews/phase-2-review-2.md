# Phase 2 review (2) — Explain one command (no prompts)

**Date:** 2026-11-19
**Commits reviewed:** 6c6d034..HEAD (no new commits) + uncommitted changes: `SPEC.md`, `commandexplain/data/commands.json`, `commandexplain/lookup.py`, `tests/test_data.py`, `tests/test_lookup.py` (modified); `commandexplain/parser.py`, `commandexplain/formatter.py`, `tests/test_parser.py`, `tests/test_formatter.py`, `docs/adr/0009`–`0012` (new)
**Verdict:** PASS WITH FIXES

This is a re-review after the fixes for `docs/reviews/phase-2-review.md`.

## Status of earlier findings
| # | Earlier finding | Status |
|---|---|---|
| 1 | Blocker: `sudo` explains the inner command's flags as its own | ✅ Fixed. ADR 0010, SPEC §3.2 step 7, §3.3, §5. `runs_command` / `flags_with_values` added to the data. Verified `sudo rm -i x`, `sudo ls -l`, `sudo -u bob ls -l`, `sudo rm -rf /`, `sudo -- -rf`, `SUDO rm -i x`. |
| 2 | Long arguments break the layout | ✅ Fixed. ADR 0012: one `argument: x` line each. The width test now types a 100-character argument. |
| 3 | Misleading suggestions (`..`, `unset`, `ll`) | ✅ Resolved by decision. `..` gives `None`. `unset` → `unsetopt` is deferred to Phase 3's "not covered" list (ADR 0011, SPEC §4, §9, §11 Phase 3). `ll`/`la` → `ln` is left as is on purpose (ADR 0011). |
| 4 | `kill` signal names split into made-up flags | ✅ Fixed for `-KILL`, `-TERM`, `-HUP`, `-15` (data plus a test). Other signal names still split; see nit 6. |
| 5 | Data reloaded on every call | ✅ Fixed. `default_commands()` uses `lru_cache`. `_alias_map` is still rebuilt on each miss, which is fine at this size. |
| 6 | `ParseError` was a `ValueError` | ✅ Fixed. `ParseError(Exception)`, plus a new `EmptyInputError`. Tested. |
| 7 | Non-breaking space not treated as a space | ✅ Fixed (`_normalize_spaces`). Tested. |
| 8 | `'' -l` and `ls --=x` | ✅ Fixed. `--=x` is an argument. An empty command name raises `ParseError`; see nit 8. |

## Test results
- `pytest -q` → **650 passed in 0.17s** (Python 3.13.7, via `python3`. There is no `python` on PATH and no `.venv` in this checkout).
- Manual checks:
  - `load_commands()['rm']['flags']['-r']` → `Delete folders and everything inside them.` ✅
  - `explain("rm -rf", shell="zsh")` gives the title, summary, `-r`, `-f`, the warning, the zsh note, and the example. ✅
  - `suggest()`: `sl→ls`, `cdd→cd`, `grpe→grep`, `mkdri→mkdir`, `sudp→sudo`, `kil→kill`, `..→None`. `ls`, `cd`, `git`, and `quit` give `None`. `unset→unsetopt` and `unalias→alias` remain, as ADR 0011 expects until Phase 3. ✅
  - Sudo edge cases through `explain()`: `sudo -iu bob ls` (value goes to `-u`, correct), `sudo sudo ls -l`, `sudo -u` alone, `sudo -s`, `sudo !!`, `sudo cd /root`, `sudo --user bob ls`, `sudo --user=bob ls`, `sudo -g wheel ls`. The findings below come from these runs.
  - `"sudo " * N + "ls"`: works at N=400 and raises `RecursionError` from N=991 on.
  - All lines are ≤ 99 characters (`awk`). Every function in `commandexplain/` and `tests/` has type hints and a docstring (`ast` check). Runtime imports are standard library only.

## Acceptance criteria
| # | Criterion | Status | Evidence |
|---|---|---|---|
| 2 | `ls` prints the summary and common flags | ✅ | `tests/test_formatter.py::test_ac2_ls_shows_summary_and_common_flags` |
| 3 | `rm -rf` explains `rm`, `-r`, `-f`, and shows the warning | ✅ | `tests/test_formatter.py::test_ac3_rm_rf_explains_command_both_flags_and_warning` |
| 12 | Data passes the schema test (new optional fields included) | ✅ | `tests/test_data.py` (`OPTIONAL_FIELDS`, `test_flags_with_values_exist_in_flags`) |
| Done when | `explain("rm -rf", shell="zsh")` returns the AC 2–3 text | ✅ | Same test as AC 3, plus a manual run |
| Done when | `suggest("sl")` returns `"ls"` | ✅ | `tests/test_lookup.py::test_suggest_real_typos[sl-ls]` |

Deliverables: `parser.py` ✅, `find_command` / `suggest` ✅, `formatter.py` ✅, tests ✅. No scope creep. The "not covered" list, CLI messages, and operator splitting are all left for later phases. Every spec change has an ADR (0009–0012), and §12 lists them.

## Findings

### Blockers
None.

### Should fix
1. **`sudo` with a shell builtin is explained as if it works** (`commandexplain/formatter.py:113-119`, data for `cd`, `alias`, `export`, `source`, `exit`, `history`, `shopt`, `setopt`, `unsetopt`)
   - Problem: `sudo cd /root` prints `sudo runs this command:` and then `cd — change directory: Moves you into a different folder.` sudo can only run programs, not shell builtins. On Linux this fails with `sudo: cd: command not found`. On macOS it runs `/usr/bin/cd` in a separate process, so your folder doesn't change. The same applies to `sudo export`, `sudo source`, `sudo alias`, `sudo history`, and so on. This case is new: before ADR 0010, `cd` was only listed as an argument.
   - Why it matters: `sudo cd` is a classic beginner mistake. People try it after `cd /root` says "Permission denied", and the tool now confirms the wrong idea. This is borderline blocker territory (it's a misleading explanation). I rated it should-fix because each block of text is accurate on its own, it needs a spec decision, and it is much less common than `sudo rm -rf`.
   - Suggested fix (needs SPEC + ADR): add an optional data field such as `"builtin": true` to shell builtins. When a `runs_command` wrapper's inner command is a builtin, replace (or follow) the inner block with a line like `sudo can't run cd, because cd is built into the shell. It won't do what you expect.` Add a test for `sudo cd /root`.

2. **Value-taking sudo options outside the data turn their value into the "inner command"** (`commandexplain/data/commands.json` → `sudo`)
   - Problem: `sudo --user bob ls` prints `sudo runs "bob", which I don't have an explanation for.` and never explains `ls`. `sudo -g wheel ls` does the same with `wheel`. (`sudo --user=bob ls` works, because of the `=` rule.) `test_flags_with_values_exist_in_flags` requires every value-taking flag to have an explanation, so an option missing from `flags` can't be marked as taking a value.
   - Why it matters: "sudo runs bob" is a false statement, and `--user` is the spelled-out form of `-u` that some tutorials use.
   - Suggested fix: data only. Add `--user` (and `-g` / `--group` if wanted) to sudo's `flags` and `flags_with_values`. Add an `explain("sudo --user bob ls")` test.

3. **Many nested `sudo`s crash with `RecursionError`** (`commandexplain/formatter.py:115`)
   - Problem: `_explain_parsed` calls itself once per wrapper. `"sudo " * 991 + "ls"` raises `RecursionError`, which would be a traceback in the Phase 3 CLI.
   - Why it matters: a crash on input, although the input is unrealistic. It is cheap to prevent.
   - Suggested fix: explain the chain of wrappers in a loop instead of by recursion, or stop after a small depth (for example 3) with a line like `…and more sudo`. Add a test with a long chain.

### Nits
4. **Untested ADR 0010 claims.** `sudo -iu bob ls` (the value goes to the last flag in the group) and nested `sudo sudo ls` both work, but no test pins them. `sudo -- rm -rf x` is tested only at the parser level, not through `explain()`.
5. **SPEC §11 Phase 2 deliverable still says "§3.2 steps 3–6".** Step 7 (wrappers) is now part of Phase 2. `parser.py`'s docstring already says 3–7.
6. **Signal names not in the data still split into letters.** `kill -INT 123` shows `-I -N -T`, and `kill -SIGKILL 1` shows five fake options. A data-side option is a per-command flag like `"no_split": true` for `kill`, so unknown tokens stay whole and get one "I don't have an explanation" line.
7. **A long unknown flag still squeezes the column.** `ls --this-is-a-really-long-made-up-option…` (80 characters) prints the "I don't have an explanation" text one word per line. This is contrived. A cap on the label width (put the text on the next line when the label is too long) would fix it.
8. **`ParseError` now covers three cases:** unclosed quote, trailing backslash (`echo hi\` → "No escaped character"), and an empty command name (`''`). Phase 3 should not map every `ParseError` to the "quote is missing its partner" message. Separate subclasses or a reason field would make that easy.

## What went well
- The blocker fix keeps the knowledge in JSON (`runs_command`, `flags_with_values`). A schema test guards the new fields, and the inner command keeps its own warnings, so `sudo rm -rf /` now shows rm's delete warning.
- Each earlier finding got either a fix with a focused test or an ADR explaining why it's deferred. Nothing changed silently.
- The width test now types a long argument for every real command in both shells, which closes the gap the first review found.
