# Phase 2 review — Explain one command (no prompts)

**Date:** 2026-11-19
**Commits reviewed:** 6c6d034..HEAD (no new commits) + uncommitted changes: `SPEC.md`, `commandexplain/lookup.py`, `tests/test_lookup.py` (modified); `commandexplain/parser.py`, `commandexplain/formatter.py`, `tests/test_parser.py`, `tests/test_formatter.py`, `docs/adr/0009-flag-token-details.md` (new)
**Verdict:** FAIL

## Test results
- `pytest -q` → **585 passed in 0.16s** (Python 3.13.7).
- Manual checks:
  - `explain("rm -rf", shell="zsh")` gives the title, the summary, `-r` and `-f` (and no other flags), the warning, the zsh note, and the example. ✅
  - `explain("ls", shell="zsh")` gives the summary, "Common options:" with `-l -a -h`, and `Example:  ls -la`. ✅
  - `suggest()` on real typos: `sl→ls`, `cdd→cd`, `grpe→grep`, `mkdri→mkdir`, `cta→cat`, `pdw→pwd`, `ehco→echo`, `tuoch→touch`, `chmdo→chmod`, `exti→exit`, `claer→clear`. Correct names (`ls`, `cd`, `mv`, `cp`, `mkdir`, `man`, `less`) give `None`. Unrelated words (`git`, `npm`, `vim`, `ssh`, `quit`, `help`) give `None`. ✅
  - About 35 parser and formatter edge cases run through `explain()`: `-`, `--`, `-ll`, `LS -LA`, `--color=auto`, `-15`, `-la1`, `rm -- -file`, `ls 'a b'`, `ls -é`, tabs, a 120-character argument, a non-breaking space, `sudo rm -rf /`, `sudo -u bob ls -l`, `kill -KILL 123`. The findings below come from these runs.
  - All lines are 99 characters or fewer. No linter is installed (flake8, pycodestyle, and pyflakes are all missing), so I checked line length with `awk`.

## Acceptance criteria
| # | Criterion | Status | Evidence |
|---|---|---|---|
| 2 | `ls` prints the summary and common flags | ✅ | `tests/test_formatter.py::test_ac2_ls_shows_summary_and_common_flags` |
| 3 | `rm -rf` explains `rm`, `-r`, `-f`, and shows the warning | ✅ | `tests/test_formatter.py::test_ac3_rm_rf_explains_command_both_flags_and_warning` |
| Done when | `explain("rm -rf", shell="zsh")` returns the AC 2–3 text | ✅ | Same test, plus a manual run |
| Done when | `suggest("sl")` returns `"ls"` | ✅ | `tests/test_lookup.py::test_suggest_real_typos[sl-ls]` |

Deliverables: `parser.py` ✅, `find_command` / `suggest` in `lookup.py` ✅, `formatter.py` ✅, tests for all three ✅. No scope creep found. `tokenize` uses plain `shlex.split` (no operators), and `ParseError` only wraps shlex's own error. The user-facing quote message is left for Phase 4.

## Findings

### Blockers
1. **`sudo` explains the inner command's flags as if they were sudo's own** (`commandexplain/formatter.py:106`, `commandexplain/parser.py:82`)
   - Problem: everything after `sudo` is parsed against **sudo's** flag table. Verified output:
     - `sudo rm -i old.txt` explains `-i` as "Start an administrator session, so every command you type runs as root until you type exit." In fact, `-i` here makes `rm` ask before each delete.
     - `sudo ls -l` explains `-l` as "List what you are allowed to run with sudo."
     - `sudo rm -rf /` shows `-r` and `-f` as unknown sudo options, lists `rm` and `/` as plain arguments, and never shows rm's explanation or its "deletes files permanently" warning.
   - Why it matters: these are wrong explanations, which is the worst kind of bug for this program, and they come up on a command from §6 that beginners copy and paste all the time (`sudo rm -rf …`). The code follows §3.2 step 3 literally, so this is a **spec gap**, not an implementation slip. It still produces false output.
   - Suggested fix (needs a spec change and an ADR): mark wrapper commands in the data, for example a field like `"runs_command": true` on `sudo`, so the knowledge stays in JSON. For those commands, stop reading flags at the first plain argument and treat everything after it as an argument. That alone removes the wrong explanations. A fuller fix would also explain the inner command (`rm -rf`) as a second block, but that could wait for Phase 4's segment machinery. Add tests for `sudo rm -i x`, `sudo ls -l`, and `sudo -u bob ls -l`.

### Should fix
2. **Long arguments break the layout** (`commandexplain/formatter.py:39-45`, `:72`)
   - Problem: `_rows` makes the label column as wide as the longest argument. A realistic path (`cp ~/Documents/projects/csc299/assignment-final-draft.txt backup/`) squeezes "An argument you gave the command." into a 20-column strip that wraps over two lines per argument. A 120-character argument prints one word per line, starting at column 125. `test_every_real_command_fits_the_width` only types flags, never arguments, so the tests don't catch this.
   - Why it matters: file paths are the most common arguments, and the output becomes hard to read on an 80-column terminal.
   - Suggested fix: don't put arguments in the two-column layout. List them on one wrapped line, such as `Arguments you gave: ~/Documents/…/draft.txt, backup/`, or use one `argument: x` line each (which matches the §3.3.1 chain format). Extend the width test to include a long argument.

3. **Suggestions for punctuation aliases and for real but uncovered builtins can mislead** (`commandexplain/lookup.py:157-162`)
   - Problem (all verified, and all follow ADR 0006 exactly):
     - `..` → `.` (so the user gets an explanation of `source`). In zsh with `autocd`, typing `..` goes up a folder, so a beginner who types it almost certainly meant `cd ..`.
     - `unset` → `unsetopt` and `unalias` → `alias`. `unset` and `unalias` are real builtins in both shells; they're just not in §6.
     - `ll` and `la` → `ln`. These are common `ls` shortcuts, and the alphabetical tie-break picks `ln` over `ls`.
   - Why it matters: the yes/no confirmation limits the damage, but "Did you mean 'unsetopt'?" for `unset` points a beginner at a different command.
   - Suggested fix: decide in an ADR. Options:
     - (a) Leave aliases that aren't letters (`.`) out of the fuzzy candidates, or require the input to contain a letter.
     - (b) Make sure Phase 3's §9 "not covered" list is checked **before** `suggest()`, and add the real builtins that are close to covered names (`unset`, `unalias`, `pkill`, `cal`, `nl`).
     - (c) Optionally, prefer `ls` in a tie.
   - Add `suggest("..")` and `suggest("unset")` tests so the chosen behavior is pinned down.

4. **`kill` signal names are split into made-up letter flags** (`commandexplain/parser.py:50-56`, `commandexplain/data/commands.json` → `kill`)
   - Problem: `kill -KILL 123` shows three unknown options, `-K`, `-I`, and `-L`. The duplicate `L` is dropped, so even the letters don't match what was typed. `kill -TERM` and `kill -HUP` do the same. `kill -15` (the polite version of `-9`) is reported as unknown.
   - Why it matters: the user typed one option and sees three that don't exist. ADR 0009 already says the fix for `-15` is data. Signal names work the same way thanks to whole-token-first (ADR 0007).
   - Suggested fix: add `-15` and `-KILL` (and maybe `-TERM` and `-HUP`) to `kill`'s `flags`, with a parser test for `kill -KILL`.

### Nits
5. **Data is reloaded on every call** (`lookup.py:110,152`, `formatter.py:96`). `find_command`, `suggest`, and `explain` each call `load_commands()` (a disk read plus a JSON parse) when no dict is passed. `_alias_map` is rebuilt on every miss, and twice in `suggest`. §8 asks for O(1) lookup. Phase 3 should load once and pass the dict around, or cache the alias map.
6. **`ParseError` is a `ValueError`, and `explain()` also raises a plain `ValueError` for blank input or a bad shell** (`parser.py:14`, `formatter.py:95,100`). If Phase 3 catches `except ValueError` before `except ParseError`, an unclosed quote will be handled like blank input. Use a distinct exception for blank input, or document the order the handlers need.
7. **A non-breaking space isn't treated as a space.** `rm -rf`, which often comes from copying a command off a web page, raises `UnknownCommandError("rm -rf")`. One `str.replace`/`translate` in `tokenize` would fix it.
8. **Tiny edge cases:** `'' -l` raises `UnknownCommandError` with an empty name (Phase 3 would print "I don't know ''"), and `ls --=x` shows `--` as an unknown flag. Not worth much effort, but Phase 3 should keep an empty command name in mind.

## What went well
- ADR 0009 pins down the tricky flag-token cases (`-15`, `--x=y`, lone `-`, `--`, `-ll`, case). Each one has a focused test in `tests/test_parser.py`, and the spec was updated to match.
- `is_one_edit` and `suggest` implement ADR 0006 exactly. The tests check both directions of each edit type, the negative cases, the tie-break, and real typos against the shipped data.
- `format_explanation` is a pure function, separate from `explain`, so the layout rules are tested with a small fake entry. A parametrized test also renders every real command with all its flags in both shells.
