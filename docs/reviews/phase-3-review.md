# Phase 3 review — Interactive CLI

**Date:** 2026-11-19
**Commits reviewed:** none yet. Phase 3 is all uncommitted work on top of `2d486ee` (end of Phase 2): `cli.py`, `shell.py`, `__main__.py`, `pyproject.toml`, `data/not_covered.json`, `tests/test_cli.py`, ADRs 0015–0016, and changes to `SPEC.md`, `lookup.py`, and `tests/test_data.py`.
**Verdict:** PASS WITH FIXES

## Test results
- `pytest -q` → **729 passed in 0.26s**. With `-W error` there are no warnings.
- Manual checks, all with the expected result unless noted:
  - **Real process:** `printf 'yes\nrm -rf\nquit\n' | SHELL=/bin/zsh python3 -m commandexplain` explains rm with its warning and exits 0. Empty stdin gives "Goodbye!" and exit 0. A real `SIGINT` sent to a waiting process prints "Goodbye!" with exit 0 and an empty stderr (no traceback). `--shell fish` gives argparse's usage error with exit 2.
  - **Entry point:** `pip install .` into a scratch venv ships all three JSON files, and the `commandexplain` script runs. I deleted the `build/` folder this created.
  - **Data errors:** a broken or missing `not_covered.json` prints `Error: Data file ...` and exits 1.
  - **Typos:** `sl`, `cdd`, `grpe`, `mkdri`, `cta`, `pdw`, `claer`, `histroy`, `sduo`, `tial`, `toch`, `chmdo`, `whcih`, `fnid`, `expotr`, `sorce`, and `alais` are all corrected to the right command.
  - **Correct input:** correctly spelled names and `LS` never prompt.
  - **Edge cases:** `-la`, `--help`, `-`, and `--` as a command all give the "Sorry, I don't know" message. `ls -ll` shows `-l` once. `Sudo SL` asks "Did you mean 'ls'?". `sudo -- sl` asks too. `sudo setopt` in bash asks the other-shell question. `exit 1` is explained and followed by the tip.
  - **Robustness:** 3000 nested `sudo`s followed by `sl` finish in 0.13 s without a crash.
  - **EOF:** EOF at every kind of prompt (detected-shell confirm, manual shell question, command prompt, "Did you mean", other-shell question, `shell` switch) prints "Goodbye!" with exit 0.

## Acceptance criteria
| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | `SHELL=/bin/zsh` asks to confirm zsh. With no `SHELL`, it asks until the answer is valid | ✅ | `tests/test_cli.py::test_ac1_detected_zsh_is_confirmed`, `::test_ac1_no_shell_asks_until_valid` |
| 2 | `ls` prints summary and common flags | ✅ | `tests/test_cli.py::test_ac2_ls_is_explained` |
| 3 | `rm -rf` explains rm, `-r`, `-f`, and the warning | ✅ | `tests/test_cli.py::test_ac3_rm_rf_is_explained_with_warning`, plus a manual run through a real process |
| 4 | `sl` → "Did you mean 'ls'?". yes explains it. no prints "Command not found..." | ✅ | `tests/test_cli.py::test_ac4_typo_yes_explains_suggestion_with_flags`, `::test_ac4_typo_no_says_not_found_and_reprompts` |
| 5 | `maybe` at yes/no re-asks | ✅ | `tests/test_cli.py::test_ac5_unclear_answer_asks_again` (4 cases) |
| 6 | `xyzzy` prints the not-found message | ✅ | `tests/test_cli.py::test_ac6_no_close_match_says_unknown` |
| 7 | `setopt` in bash warns and offers to explain | ✅ | `tests/test_cli.py::test_ac7_zsh_command_in_bash_asks_first`, `::test_ac7_saying_no_skips_explanation` |
| 8 | `quit`, Ctrl+C, and Ctrl+D exit cleanly. `exit` is explained | ✅ | `tests/test_cli.py::test_ac8_*` (quit words, Ctrl+C at 3 prompts, Ctrl+D at 3 prompts, exit tip). A real SIGINT was also checked by hand |
| 12 | (now also covers `not_covered.json`) passes the schema test | ✅ | `tests/test_data.py::test_not_covered_entries_are_well_formed`, `::test_not_covered_does_not_overlap_commands` |
| 14 | `shell` asks again, and later explanations use the new shell | ✅ | `tests/test_cli.py::test_shell_word_switches_shell` |
| 15 | `unset` shows "not covered" and never "Did you mean 'unsetopt'?". `sudo sl` asks "Did you mean 'ls'?" | ✅ | `tests/test_cli.py::test_uncovered_builtin_is_not_suggested_as_something_else`, `::test_sudo_inner_typo_gets_suggestion` |

**Deliverables:** all present.
- `shell.py` ✅
- `cli.py`: main loop, yes/no, "Did you mean", other-shell question, quit/exit, and the not-covered check before suggestions ✅
- `__main__.py` and `pyproject.toml` with the `--shell` option ✅
- `tests/test_cli.py` ✅

**Scope:** no scope creep. Pipes are not handled yet, which is correct for Phase 3. One thing to know until Phase 4: the CLI is runnable now, and it reads `ls -a|grep x` as `ls` with the flags `-a -| -g -r -e -p`, so `-r` gets explained as "Reverse the order of the list." This is expected for this phase, but it's worth a line in the handoff.

## Findings

### Blockers
None.

### Should fix
1. **Real commands that aren't in the data still get misleading "Did you mean" suggestions** — `commandexplain/data/not_covered.json`
   - Problem: ADR 0011 added the not-covered list so that real commands aren't "corrected" into other commands. But many common real commands aren't on the list and still are. I checked each of these with `suggest()`. None of them is in `commands.json` or `not_covered.json`:
     - `dd`, `id`, `od`, `ed`, `fd` → `cd`
     - `rg` → `rm`
     - `pgrep`, `egrep`, `fgrep` → `grep`
     - `htop` → `top`
     - `cmp`, `ip` → `cp`
     - `fc`, `nc` → `wc`
     - `zcat` → `cat`
     - `zless` → `less`
     - `lsd`, `cls` → `ls`
     - `dir` → `rmdir`
     
     Separately, `bash`, `zsh`, and `sh` get "Sorry, I don't know 'bash'. Check the spelling and try again." That tells a beginner a correctly spelled real command is misspelled, in a tool that is about bash and zsh.
   - Why it matters: `dd` → "Did you mean 'cd'?" and `rg` → "Did you mean 'rm'?" send a beginner from one command to an unrelated, different one. `pgrep` is the partner of `pkill`, which is already on the list. The yes/no step limits the damage, but a beginner may well answer "yes".
   - Suggested fix (data only):
     - Add `dd`, `id`, `od`, `ed`, `pgrep`, `cmp`, `fc`, `nc`, `zcat`, `zless`, `ip`, `bash`, `zsh`, and `sh` as `"uncovered"`.
     - Add `rg`, `fd`, and `htop` as `"tool"`. They aren't preinstalled on macOS or most Linux systems.
     - You decide whether `egrep`/`fgrep` → `grep` is acceptable, since they are grep variants.
     - Add a parametrized test asserting that `not_covered_kind()` finds them, or a CLI test showing that `dd` never prompts "Did you mean".

2. **The shell question skips the hint after a declined suggestion, and suggests the wrong shell for real shell names** — `commandexplain/shell.py:41-45`
   - Problem: `HINT` is only shown when there is no suggestion. In a scripted run with no `SHELL`:
     - `sh` → "Did you mean zsh?"
     - `ksh` → "Did you mean zsh?"
     - `dash` → "Did you mean bash?"
     
     After **no**, the bare question repeats with no hint. A user whose shell really is `sh` (common on minimal Linux and in Docker) is never told that only bash and zsh are supported, and never told to run `echo $SHELL`.
   - Why it matters: SPEC §3.1 says "If the input is invalid, show a hint and ask again". A declined suggestion is invalid input, so this is a small divergence from the spec. Accepting the suggestion is worse: an `sh` user is quietly switched to zsh.
   - Suggested fix: call `say(HINT)` whenever the answer isn't accepted, including after a declined suggestion. Optionally, don't suggest for known other shells (`sh`, `ksh`, `dash`, `csh`, `tcsh`, `fish`). Show the hint for them instead (the spec already says "bash or zsh only"). Add a test for `sh` → no → the hint is shown.

3. **Some spec changes have no ADR** — `SPEC.md` §3.2 (lines 95–96), §5.2 (lines 262–275), §12 (line 451)
   - Problem: CLAUDE.md requires an ADR for every spec change, and §12 itself says "Each decision has an ADR".
     - The new §3.2 wording for the trailing-backslash and empty-command messages has no ADR.
     - The new §5.2 `not_covered.json` format (one file, a `kind` field with the values `tool` and `uncovered`) has no ADR. ADR 0011 only says the list "is kept in the data".
     - The new §12 row "Command list size" has `—` in the ADR column.
   - Why it matters: these are small, already-agreed decisions. The handoff asked for the message wording, and ADR 0011 called for the list. But the record is incomplete, and §12 now contradicts itself. I rate this should-fix rather than blocker because nothing here departs from an earlier decision.
   - Suggested fix: one short ADR 0017, "Phase 3 messages and the not-covered file", covering all three: the two §3.2 messages, the §5.2 schema, and keeping the 35-command list. Then point the §12 row at it.

4. **Some edge cases have no test** — `tests/test_cli.py`
   - Problem: these work when checked by hand but aren't pinned:
     - Ctrl+C/Ctrl+D at the manual "bash or zsh?" prompt, at the other-shell "Explain it anyway?" prompt, and at the `shell` switch prompt. Today's tests cover only the detected-shell confirm, the command prompt, and "Did you mean".
     - A broken or missing `not_covered.json` → exit 1. Only `commands.json` is tested.
     - A correctly spelled command never shows "Did you mean". `test_ac2` doesn't assert that no prompt appears.
     - AC 14's "later explanations use the new shell" is only shown through the other-shell question, not through a `shell_notes` line (for example `rm` shows "Note for zsh" before the switch and not after it).
   - Why it matters: every prompt goes through `Console.ask` today, so these pass. But a later refactor (Phase 4 adds prompts per segment) could break one path without any test failing.
   - Suggested fix: extend `test_ac8_ctrl_c_at_any_prompt_exits_cleanly` and the Ctrl+D test with sessions that reach those prompts. Parametrize `test_broken_data_file_exits_with_code_1` over both files. Add `assert not any("Did you mean" in p for p in term.prompts)` to the AC 2 test. Add one switch test that checks for the rm zsh note.

### Nits
5. **Duplicate constant and a dead fallback.** `SHELLS` is defined in both `formatter.py:15` and `shell.py:10`. `cli.py:140` passes `self.shell or SHELLS[0]`, but `self.shell` is always set by then, so the fallback can never be used and only hides a bug if one appears.
6. **`pyproject.toml:9` uses `readme = "SPEC.md"`**, so the package description is the full spec. Switch it to `README.md` when Phase 5 adds that file, or drop the line for now.
7. **`shell bash` isn't understood.** `cli.py:117` matches only the exact word, so `shell bash` gives "Sorry, I don't know 'shell'. Check the spelling and try again." Accepting `shell <name>`, or at least opening the switch question, would be friendlier.
8. **Plausible answers are rejected at the shell prompts.**
   - `quit`/`q` at "Are you using bash or zsh?" just shows the hint. A beginner who doesn't know Ctrl+C has no way out, including after typing `shell` by mistake.
   - Answering `zsh` to "Looks like you're using zsh. Is that right?" gives "Please type yes or no."
   
   The spec doesn't require either one, so changing this would need a spec line.

## What went well
- `Console.ask` turns `EOFError`/`KeyboardInterrupt` into one `QuitRequested`. That covers every prompt in one place, so no yes/no loop can spin on EOF, and a real SIGINT exits with code 0 and no traceback.
- The not-covered list is data, it is checked before `suggest()` exactly as ADR 0011 requires, and a schema test stops it from overlapping `commands.json` or the aliases.
- Spelling fixes rebuild the input with `shlex.join` and hand it back to `explain()`. That reuses the Phase 2 code instead of duplicating it, and quoted arguments survive (`fnid . -name "my file.txt"` is tested).
