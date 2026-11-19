# Phase 4 review (re-review) — Pipes and chains

**Date:** 2026-11-19
**Commits reviewed:** f960fe4..HEAD (no Phase 4 commits yet) + uncommitted changes to `SPEC.md`, `cli.py`, `formatter.py`, `parser.py`, `lookup.py`, `commands.json`, `operators.json`, four test files, and new ADRs 0018 and 0019
**Verdict:** PASS WITH FIXES

This is a re-review after the fixes for `docs/reviews/phase-4-review.md`.

## Status of earlier findings
| Earlier finding | Status | Evidence |
|---|---|---|
| Blocker 1: missing or broken `operators.json` gives a traceback | ✅ Fixed | `cli.py:293-299` loads all three files inside the `try`. `tests/test_cli.py::test_broken_data_file_exits_with_code_1` now covers `OPERATORS_FILE`. A manual run gives `Error: Data file not found: …/operators.json`, exit 1, and no prompt. |
| Should fix 1: block header re-quotes the words (`'$HOME'`) | ✅ Fixed | `ChainCommand.text` and `retype()` (`parser.py:179-199`, `:386-400`). `echo "hello world" $HOME`, `find . -exec rm {} \;`, and `ls #` now show exactly as typed. Pinned by `test_chain_header_keeps_the_users_quoting`, `test_chain_header_shows_spelling_fix_and_keeps_quoting`, and `test_chain_block_header_is_text_as_typed`. |
| Should fix 2: stale spec text after ADRs 0018/0019 | ✅ Fixed | The §11 deliverable, the §3.3.1 example's "In short" line, and ADR 0019's "Supersedes the tokenizing part of ADR 0002" are all updated. |
| Should fix 3: "no" to the other-shell question in a chain is silent | ✅ Fixed | It prints `OK, I won't explain it. Please re-enter the command.` (`cli.py:219-221`). This is recorded in SPEC §3.3.1 and ADR 0018. Pinned by `test_other_shell_command_in_chain_is_asked_about` and `test_other_shell_no_for_single_command_stays_quiet`. |
| Should fix 4: test gaps | ✅ Fixed (see Nit 3) | Two chain entries were added to `PROMPT_PATHS`, plus the operators-file test and the header tests. |
| Nit 1: `ls;2>x`, lone `;`, `>|` | ✅ Fixed | `_WORD_BREAKS` (`parser.py:168`) and `>|` in `_UNSUPPORTED`. `tests/test_parser.py:409-428`. |
| Nit 2: `ls > out.txt \| wc` "In short" | ✅ Fixed | `formatter.py:267-270`, `test_no_in_short_when_saved_output_is_piped`. See Nit 2 below for the related case `> a > b`. |
| Nit 3: sudo plus a not-covered command in a chain has no lead-in | ✅ Fixed | `formatter.py:216-217`, `test_sudo_not_covered_inner_in_chain_has_lead_in`. |
| Nit 4: E303 triple blank lines | ✅ Fixed | No runs of 3 or more blank lines remain in `tests/` or `commandexplain/`. |
| Nit 5: §5 example is missing `short` | ✅ Fixed | `SPEC.md` §5 now shows `short` on `ls`, `rm`, and `setopt`. |

## Test results
`python3 -m pytest -q` → **950 passed in 0.35s** (up from 925).

Manual checks (with `explain()`, scripted `run_session()` sessions, and piped input into `python3 -m commandexplain`):
- `ls -a | grep txt` matches the §3.3.1 example, including `In short: list files, then pass the output to find matching lines.` ✅
- Missing `operators.json` → `Error: Data file not found`, exit 1, and no prompt shown. ✅
- `ls ; setopt autocd` in bash, answered **no** → prints the "OK, I won't explain it" line. ✅
- `sl | grpe x`: re-asks on `maybe`, then asks about grep. Ctrl+C at the second "Did you mean" → `Goodbye!`, exit 0. ✅
- `mkdri d && cd d` (yes) → a correct chain with the cd bash note. ✅
- `ls &&& ls`, `ls 2>&1`, `echo $(date) | wc` name the unsupported syntax. `ls ;; ls` → missing after `;`. `echo '$(date)' | wc` is explained correctly. ✅
- `sudo rm -rf / ; ls` keeps both the sudo and rm warnings inside the block. ✅
- A fuzz test of 200,000 random inputs built from quotes, escapes, `$HOME`, `#`, non-ASCII, every operator, and sudo found **0** cases where `_word_spans()` disagreed with `ChainCommand.tokens`. It also found **0** cases where `parse_chain(chain_to_text(retyped))` failed to round-trip. ✅
- `sudo cd /tmp ; ls` → `In short: change folder (using sudo), then list files.` ❌ (Should fix 1)
- `ls # list | grep x` in bash explains a pipe to grep. ❌ (Should fix 2)
- `. ~/.bashrc ; ls` shows the header `source ~/.bashrc`. (Nit 1)

## Acceptance criteria
| # | Criterion | Status | Evidence |
|---|---|---|---|
| 9 | `ls -a \| grep txt` explains ls, pipe, grep in order; `grep "a\|b" f` is one command | ✅ | `tests/test_formatter.py::test_ac9_pipe_explains_each_part_in_order`, `::test_ac9_quoted_pipe_is_one_command`, `tests/test_cli.py::test_ac9_pipe_in_session` |
| 10 | `sl \| grep x` asks "Did you mean 'ls'?" before explaining | ✅ | `tests/test_cli.py::test_ac10_typo_in_chain_is_asked_about_first` |
| 16 | Unsupported syntax named; missing side named; `ls \| sort` explains ls and says sort isn't covered | ✅ | `tests/test_cli.py::test_chain_errors_have_messages`, `::test_not_covered_segment_is_explained_in_place`, `tests/test_parser.py` unsupported/missing-side tests |
| 12 | (regression) data schema, now with `short` | ✅ | `tests/test_data.py::test_operator_schema`, `::test_every_command_has_a_short_phrase`, `::test_operator_short_phrase_mentions_file_only_for_redirects` |
| 13 | (regression) all tests pass | ✅ | 950 passed |

## Findings

### Blockers
None.

### Should fix
1. **"In short" says sudo runs a shell builtin that it can't run.** See `commandexplain/formatter.py:239-243`.
   - Problem: `sudo cd /tmp ; ls` gives `In short: change folder (using sudo), then list files.` The block right above it correctly warns: "sudo can't run cd … It will fail or have no effect." `sudo exit ; ls` gives "leave the shell (using sudo), …" in the same way. So the summary contradicts the warning.
   - Why it matters: ADR 0018 promises that the "In short" line is "always grammatical and always true". `sudo cd` is a common beginner mistake, and the one-line summary is the part they're most likely to read. `test_sudo_builtin_warning_inside_chain` checks the warning but not the summary.
   - Suggested fix: in `_chain_command_block`, return `None` as the phrase when `wrappers` is non-empty and `entry.get("builtin_only")` is set. This leaves the "In short" line out, the same way a not-covered command does. Add `assert "In short" not in text` to `test_sudo_builtin_warning_inside_chain`, and add one line about this to ADR 0018 (still uncommitted) and SPEC §3.3.1.

2. **A `#` comment is explained as real arguments and operators.** See `commandexplain/parser.py:166` (`_UNSUPPORTED`) and `parser.py:234-283`.
   - Problem: `ls # list | grep x` is explained as `ls` with the arguments `#` and `list`, piped to grep, and gets an "In short" line about the pipe. In bash, interactive comments are on by default, so everything after `#` is ignored and nothing is piped. In zsh, `INTERACTIVE_COMMENTS` is off by default in an interactive shell, so the `#` is a plain word there. The correct explanation depends on the shell, and right now it's wrong for bash.
   - Why it matters: beginners often paste tutorial lines with trailing comments (`cd project  # go to the project`). In a chain, the program can describe operators that won't run. Single commands had the same gap before Phase 4. But Phase 4's scanner is now the place that decides what is unsupported, and ADR 0019 doesn't mention `#`.
   - Suggested fix: the simplest option consistent with ADR 0019 is to treat an unquoted `#` at the start of a word as unsupported (`Sorry, I can't explain "#" yet…`). A `#` inside a word (`a#b`) or in quotes would stay a plain character. Record the choice in ADR 0019 (still uncommitted) and in the §3.2 list. Add tests for `ls # x | wc` → unsupported, and for `echo a#b | wc` and `echo "#" | wc` → explained.

### Nits
1. **The header swaps in canonical names even when there was no spelling fix.** See `cli.py:213` and `parser.py:386-400`. `LS -A | GREP x` shows `ls -A`, and `. ~/.bashrc ; ls` shows `source ~/.bashrc`. SPEC §3.3.1 says "only words changed by an accepted spelling fix are swapped in". The lowercase change is harmless. Showing `source` when the user typed `.` is a small mismatch. Either retype only when a suggestion was accepted, or reword the spec to say that names are normalized.
2. **`ls > a > b` gives an "In short" line that's wrong for bash.** It says "and save the output to a, and save the output to b". In bash, `a` is emptied and only `b` gets the output. zsh (with MULTIOS) writes to both. This is the same reasoning as the excluded `> … |` case. Leaving "In short" out when a command has more than one `>`/`>>` redirect would cover it (`formatter.py:267-270`). It's rare.
3. **The new `PROMPT_PATHS` entries don't prove that the intended prompt was reached.** See `tests/test_cli.py:422-423`. Ctrl+D also exits cleanly at the main prompt, so these tests would still pass if the chain never asked the second question. Add a check on `term.prompts[-1]` (for example, `"Did you mean 'grep'? (yes/no) "`, or that it contains `"doesn't work in"`).
4. **Spec text tidy-ups.**
   - `SPEC.md:147` has the typo "Then comes then".
   - `SPEC.md:154` repeats what line 148 already says (sudo inner commands in a chain), and the two could be merged.
   - The `-a` text in the examples (`SPEC.md:112`, `:133`, `:202`) is "the ones starting with a dot", but the data says "the ones whose names start with a dot". The lines at 112 and 202 predate this phase.

## Docs
- No `docs/handoffs/004-phase-4.md` yet. That's expected, because the handoff comes after this review.
- Every spec change in this phase is covered by ADR 0018 or 0019. Both are still uncommitted, so the Should fix items above can be added to them without breaking the "never edit an accepted ADR" rule.
- Git hygiene: no tracked junk files, `.gitignore` covers the usual set, runtime imports are standard library only, there are no lines over 99 characters, and there are no Phase 4 commits yet that could carry attribution.

## What went well
- All earlier findings were fixed properly, not patched over. The typed-text header plus `retype()` held up against a 200,000-input fuzz test of quoting, escapes, redirects, and sudo.
- Each fix came with a test that pins it (operators-file error, header quoting, silent drop, lead-in, `ls;2>x`, `>|`), and the spec and ADRs were updated in step.
- Chain output is still safety-first. sudo, rm, `>` and builtin warnings all show inside the blocks.
