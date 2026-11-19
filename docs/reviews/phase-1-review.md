# Phase 1 review — Key-value data

**Date:** 2026-11-19
**Commits reviewed:** 081b21f (HEAD) + uncommitted changes. All Phase 1 work is still untracked: `commandexplain/`, `conftest.py`, `tests/`.
**Verdict:** PASS WITH FIXES

## Test results
- `pytest -q` → **418 passed in 0.11s** (Python 3.13.7, macOS).
- Done-when check: `python3 -c "from commandexplain.lookup import load_commands; print(load_commands()['rm']['flags']['-r'])"` → `Delete folders and everything inside them.` ✅
- Loader edge cases, checked by hand with temporary files:
  - empty file → `DataFileError` ✅
  - file with a UTF-8 BOM → `DataFileError` ✅
  - top level is not an object → `DataFileError` ✅
  - **file that isn't UTF-8 (Latin-1 `é`) → uncaught `UnicodeDecodeError`** ❌
  - **duplicate key → silently keeps the last one** ❌
- Flag accuracy: checked against the macOS (BSD) man pages on this machine for `ps -e/-f/-u`, `touch -a/-c/-m`, `cp -n/-p/-r`, `rm -d`, `mkdir -v`, `chmod -v`, `chown -v`, `which -a`, `grep -o/-w/-E`, `ls -A/-F/-1`, `less -i/-F`, `head -c`, `wc -m`, `man -f/-k`, `top -o`, `ln -f`, and `mv -n/-f`. All are correct for BSD. I also confirmed the zsh `echo` note: `zsh -fc 'echo "a\tb"'` prints a tab, and bash 3.2 prints `\t`.
- Fuzzy matching against the real names with `cutoff=0.75`: `cdd→cd`, `grpe→grep`, `mkdri→mkdir`, `tial→tail`, `ehco→echo` work. **`sl`, `cta`, and `pdw` get no suggestion** (see Should fix #8).
- No root-level `__pycache__/`, `.pytest_cache/`, or other unwanted files are tracked, and `.gitignore` covers them. No AI attribution in any commit message.

## Acceptance criteria
| # | Criterion | Status | Evidence |
|---|---|---|---|
| 12 | Every entry in `commands.json` and `operators.json` passes the §5 schema test | ✅ | `tests/test_data.py`: `test_command_has_required_fields_with_right_types`, `test_command_optional_fields_have_right_types`, `test_command_has_no_unknown_fields`, `test_operator_schema` |
| — | Required fields have the right types | ✅ | `test_command_has_required_fields_with_right_types` |
| — | `shells` only contains `bash`/`zsh` | ✅ | `test_shells_are_valid` |
| — | Every `common_flags` item is a key in `flags` | ✅ | `test_common_flags_exist_in_flags` |
| — | Aliases don't clash | ✅ | `test_aliases_do_not_clash` |
| — | Summaries are at most 2 sentences | ✅ | `test_summary_is_at_most_two_sentences` (+ `test_count_sentences`) |
| — | All §6 commands and §5.1 operators present | ✅ | `test_all_spec_commands_present`, `test_all_spec_operators_present` (35 commands, 7 operators) |
| — | Missing or broken file raises a clear error (§9) | ⚠️ partial | `tests/test_lookup.py` covers missing, invalid JSON, non-object, and a directory. A non-UTF-8 file isn't covered (Should fix #1). |
| — | Done when: `load_commands()["rm"]["flags"]["-r"]` returns the explanation | ✅ | `test_load_commands_returns_dict_keyed_by_name` + manual run |

## Findings

### Blockers
None.

### Should fix
1. **A non-UTF-8 data file crashes with a raw `UnicodeDecodeError`.** `commandexplain/lookup.py:21-26`
   - Problem: `read_text(encoding="utf-8")` raises `UnicodeDecodeError`, which is a `ValueError`, not an `OSError`, so neither `except` catches it. I reproduced this with a Latin-1 file containing `café`.
   - Why it matters: the phase deliverable says "a missing or broken file raises a clear error". The Phase 3 CLI will catch `DataFileError` only, so this case would show the user a traceback, which §9 forbids. It can happen if someone edits the JSON in an editor that saves as Latin-1 or cp1252.
   - Suggested fix: add `except UnicodeDecodeError as err: raise DataFileError(f"Data file {path} is not UTF-8 text: {err}") from None`, plus a test next to `test_invalid_json_raises_clear_error`.

2. **Duplicate keys in the JSON are silently dropped.** `commandexplain/lookup.py:30`
   - Problem: `json.loads('{"ls": {...a}, "ls": {...b}}')` keeps only `b`, and no test can notice because the duplicate is already gone by the time the dict exists. The real file has no duplicates today (checked with `object_pairs_hook`).
   - Why it matters: the whole point of the key-value design (ADR 0001) is that people add commands by editing the file by hand. Pasting a second `"cp"` entry would silently replace the first one.
   - Suggested fix: pass `object_pairs_hook` to `json.loads` and raise `DataFileError("duplicate key 'cp' in …")` when a key repeats. Add a test with a duplicate key.

3. **`find`'s flags can never be matched under the §3.2 parsing rules.** `commandexplain/data/commands.json` (`find` entry) and §3.2 step 5
   - Problem: §3.2 step 5 says a single-dash token with more than one letter is split into short flags, so `-name` becomes `-n -a -m -e`. All 8 `find` flag keys (`-name`, `-iname`, `-type`, `-size`, `-mtime`, `-maxdepth`, `-exec`, `-delete`) are multi-letter single-dash keys, so a typed `find . -name "*.txt"` (the entry's own `example`) will show four "I don't have an explanation" lines. `test_flags_are_well_formed` allows these keys, so the conflict goes unnoticed.
   - Why it matters: this will surface as wrong output in Phase 2. It's a spec inconsistency that needs a decision, not a quiet workaround.
   - Suggested fix: decide before Phase 2 and record it in an ADR. One option: "if the whole token is a key in the command's `flags`, keep it whole; otherwise split it". Another: drop `find`'s tests from `flags`. Then add a data test that enforces whichever rule is chosen.

4. **`common_flags` doesn't follow §3.3's "3–5 most common flags".**
   - Problem: 12 entries have 3 or more flags but list fewer than 3 common ones: `touch`, `mv`, `ln`, `cat`, `less`, `tail`, `wc`, `find`, `sudo`, `ps`, `kill`, `shopt`. Five entries have flags but list none: `cd`, `pwd`, `rmdir`, `top`, `history`. Typing just `cat` will show a "Common options" list with only `-n`.
   - Why it matters: this differs quietly from the spec. Leaving out `cd -P` for beginners is a reasonable choice, but it's a spec change.
   - Suggested fix: either fill `common_flags` up to `min(3, len(flags))`, or change §3.3 to "up to 5" (and say what to print when the list is empty) with an ADR. Add a test for whichever rule is chosen.

5. **`find` has no `warning`, even though `-delete` and `-exec` can destroy files.** `commandexplain/data/commands.json` (`find`)
   - Problem: the only caution is the text "Careful: there is no undo." inside the `-delete` flag explanation. The formatter will only show `⚠ Careful:` (and color it red in Phase 5) for the `warning` field. `find` is also missing from `DANGEROUS_COMMANDS` in `tests/test_data.py:32`.
   - Why it matters: `find . -name "*.txt" -delete` is as destructive as `rm`, and beginners copy it from the internet.
   - Suggested fix: add a command-level warning, for example "With -delete or -exec, find can delete or change every file it finds. Run it without them first to see what matches.", and add `find` to `DANGEROUS_COMMANDS`. Optionally, raise per-flag warnings as a spec question, since `rm -rf` is named in §3.3 as a flag-level warning.

6. **The `ps` explanation overstates what plain `ps` shows.** `commandexplain/data/commands.json` (`ps`)
   - Problem: the summary says it "Shows the programs (processes) that are running right now", and `-e` says "not just yours", which implies plain `ps` lists all of your processes. Both the BSD man page ("all of your processes that have controlling terminals") and GNU (same user *and* same terminal) say plain `ps` only shows processes tied to your terminal. A beginner running `ps` sees 1–2 lines and gets confused.
   - Suggested fix: summary: "Shows programs (processes) that are running. By itself it only shows the ones started from this terminal window." `-e`: "Show every process on the computer, including other users' and background ones."

7. **The BSD/GNU difference for `cp -r` / `-R` isn't mentioned.** `commandexplain/data/commands.json` (`cp`)
   - Problem: on macOS, `cp -R photos/ backup` (with a trailing slash, which tab completion adds) copies the folder's *contents* into `backup`. On Linux it copies the folder itself. The macOS man page also says `-r` is "strongly discouraged as the behavior is implementation-dependent" (it means `-RL` there). The entry presents `-r` and `-R` as identical and lists `-r` as the common flag.
   - Why it matters: the checklist says that where macOS and Linux differ, the entry should say so. This difference leads to files ending up in surprising places.
   - Suggested fix: make `-R` the common flag, and add a note to `-R`, for example: "On macOS, a slash at the end of the folder name (photos/) copies only what's inside the folder."

8. **(Spec issue for later phases) `sl` → `ls` can't work with `cutoff=0.75`.** SPEC §4, acceptance criteria 4 and 10, Phase 2 Done-when
   - Problem: `difflib.SequenceMatcher(None, "sl", "ls").ratio()` is **0.5**, so `get_close_matches("sl", names, cutoff=0.75)` returns `[]`. I checked this against the real command list. Other short swaps also fail: `cta` → `cat` (0.667) and `pdw` → `pwd` (0.667). Longer typos work fine.
   - Why it matters: Phase 2's Done-when (`suggest("sl")` returns `"ls"`) and acceptance criteria 4 and 10 can't pass as the spec is written. This isn't a Phase 1 defect, but this data is the first point where it can be checked.
   - Suggested fix: decide before Phase 2 and record it in an ADR. Options: also try a transposition check (an adjacent swap gives the same sorted letters), use a lower cutoff for 2–3 letter words, or compare sorted letters as a fallback.

9. **A few explanations use jargon without explaining it.** `commandexplain/data/commands.json`
   - `echo` summary: "show what a variable holds, like echo $HOME". The word "variable" is never explained.
   - `export` summary: "Sets a variable…". Same problem. Something like "a named setting (a variable)" would help.
   - `top` summary: "how much CPU and memory". Could say "how hard each one is working the computer (CPU) and how much memory it uses".
   - `grep -E`: "(extended regular expressions)" gives the jargon name without saying what it does.
   - Suggested fix: reword these per §3.3, writing for someone who has never opened a terminal.

### Nits
1. **`cd`'s `autocd` note is zsh-only, but bash 4+ has `shopt -s autocd` too.** macOS's bash 3.2 doesn't have it, so the note isn't wrong, but it implies bash can't do this. Optionally add a bash note.
2. **`load_commands()` doesn't check that each entry is a dict.** `{"ls": "list"}` loads fine and would raise a `TypeError` later in Phase 2/3. The schema test catches this for the shipped file, and §9 only requires handling missing or invalid JSON, so this is optional hardening.
3. **Some small gaps in the data tests:**
   - operator summaries aren't checked against the 2-sentence limit,
   - aliases aren't checked to be lowercase with no spaces (command keys are),
   - nothing pins the flag-key format (see Should fix #3).
4. **`touch -a` says "the time the file was last opened".** Access time means last *read*, and many systems update it lazily. "last read" would be more precise.
5. **Lines are up to 98 characters long,** over PEP 8's 79. There's no linter config, so either wrap the lines or record a 99-character limit (PEP 8 allows teams to agree on that).

## Other notes
- **Scope:** no scope creep. `lookup.py` only has the two loaders (no `find_command` or `suggest`), there are no `short` fields (Phase 4), and there's no `pyproject.toml` (Phase 3). `conftest.py` isn't in the §7 layout, but it's a harmless test helper.
- **Project rules:** standard library only (`json`, `pathlib`, `typing`). Every function has type hints and a docstring. No command knowledge is hardcoded in Python.
- **Docs:** there's no handoff in `docs/handoffs/` yet, which is expected at this point. No ADRs were added in this phase. Should fix #3, #4, and #8 each need an ADR plus a SPEC update if the spec changes.
- **Git:** all Phase 1 files are still uncommitted. Remember to commit them, including this review, after the fixes and the handoff.

## What went well
- The data is accurate. Every flag I checked against the macOS man pages is correct, and the shell notes (zsh `echo` escapes, `which` in bash vs zsh, zsh's `rm *` prompt, `history 1`) are both correct and useful to beginners.
- The schema tests are thorough and give clear failures. Each entry is a separate parametrized case named after the command, and there's a test for unknown field names that catches typos like `sumary`.
- The loader's errors are clear and traceback-free, and they include line and column numbers, for every case except the encoding gap above.
