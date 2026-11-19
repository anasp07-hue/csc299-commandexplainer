# Phase 4 review — Pipes and chains

**Date:** 2026-11-19
**Commits reviewed:** f960fe4..HEAD (no Phase 4 commits yet) + uncommitted changes to `SPEC.md`, `cli.py`, `formatter.py`, `parser.py`, `lookup.py`, `commands.json`, `operators.json`, four test files, and new ADRs 0018 and 0019
**Verdict:** FAIL

## Test results
`python3 -m pytest -q` → **925 passed in 0.34s**.

Manual checks (scripted with `explain()` and with `run_session()` from `tests/test_cli.py`):
- `ls -a | grep txt` prints the ls block, the pipe, the grep block, then `In short: list files, then pass the output to find matching lines.` ✅
- `grep "a|b" f` uses the full single-command format. `a|b` is one argument. ✅
- `ls | sort` explains ls, and sort's block says it isn't covered, with no "In short" line. ✅
- `ls 2>/dev/null`, `sleep 5 &`, `ls &`, `ls &&& ls`, `diff <(ls) <(ls)`: each names the unsupported syntax. ✅
- `| grep`, `ls &&`, `ls ;;`: each names the operator and the side that is missing. ✅
- `sl | grpe x`: asks about ls, re-asks on `maybe`, asks about grep, and **no** drops the whole input. ✅ Ctrl+C and Ctrl+D at the second "Did you mean" both exit with `Goodbye!` and code 0. ✅
- `LS -A | GREP x` and `mkdri d && cd d` (answering yes) both work. ✅
- `find . -exec rm {} \; | wc` keeps the escaped `;` as an argument. ✅
- A long 20-command pipe and non-ASCII text (`echo 'héllo wörld' | wc -l > ü.txt`) both work. ✅
- **Missing `operators.json` → uncaught `DataFileError` traceback.** ❌ (see Blocker 1)
- `echo "hello world" $HOME | wc` shows the header `echo 'hello world' '$HOME'`. ❌ (see Should fix 1)

## Acceptance criteria
| # | Criterion | Status | Evidence |
|---|---|---|---|
| 9 | `ls -a \| grep txt` explains ls, pipe, grep in order; `grep "a\|b" f` is one command | ✅ | `tests/test_formatter.py::test_ac9_pipe_explains_each_part_in_order`, `::test_ac9_quoted_pipe_is_one_command`, `tests/test_cli.py::test_ac9_pipe_in_session`, `tests/test_parser.py::test_quoted_or_escaped_operators_are_not_operators` |
| 10 | `sl \| grep x` asks "Did you mean 'ls'?" before explaining | ✅ | `tests/test_cli.py::test_ac10_typo_in_chain_is_asked_about_first` |
| 16 | Unsupported syntax named; missing side named; `ls \| sort` explains ls and says sort isn't covered | ✅ | `tests/test_cli.py::test_chain_errors_have_messages`, `::test_not_covered_segment_is_explained_in_place`, `tests/test_parser.py::test_unsupported_syntax_is_named`, `::test_operator_with_a_missing_side` |
| 12 | (regression) data schema, now with `short` | ✅ | `tests/test_data.py::test_operator_schema`, `::test_every_command_has_a_short_phrase`, `::test_operator_short_phrase_mentions_file_only_for_redirects` |
| 13 | (regression) all tests pass | ✅ | 925 passed |

## Findings

### Blockers
1. **A missing or broken `operators.json` crashes with a traceback.** See `commandexplain/cli.py:120` and `commandexplain/cli.py:285-293`.
   - Problem: Phase 4 is the first phase that loads `operators.json` at runtime. `main()` loads the commands and not-covered files inside `try/except DataFileError`. The operators file is loaded later, in `Session.__init__` (`default_operators()`), which runs **outside** that `try`. I confirmed this by pointing `lookup.OPERATORS_FILE` at a missing path and running `main(["--shell", "bash"], ...)`. It raised an uncaught `DataFileError: Data file not found: .../operators.json` before the first prompt.
   - Why it matters: SPEC §9 and the review checklist both require a clear message and exit code 1, not a traceback. Phase 3 made this work for the other two files, and Phase 4 broke it for the new one.
   - Suggested fix: load `default_operators()` inside the existing `try` in `main()` and pass the result to `Session(..., operators=operators)`. Then add `"OPERATORS_FILE"` to the `setting` parametrization of `tests/test_cli.py::test_broken_data_file_exits_with_code_1`, and clear `default_operators` in its setup and teardown.

### Should fix
1. **The chain block header doesn't show the words "as typed". It re-quotes them, and that can change their meaning.** See `commandexplain/formatter.py:209`.
   - Problem: the first line of each block is `shlex.join(command.tokens)`, so the original quoting is lost and the words are quoted again. I saw these results:
     - `echo "hello world" $HOME | wc` → `echo 'hello world' '$HOME'`
     - `find . -exec rm {} \; | wc` → `find . -exec rm '{}' ';'`
     - `ls # | grep x` → `ls '#'`
   - Why it matters: SPEC §3.3.1 and ADR 0018 say the block shows "the words as typed". For a beginner, `'$HOME'` means something different from `$HOME`: single quotes stop the variable from being expanded. So the program shows them a command that would behave differently from the one they typed. The `argument:` lines below the header are correct.
   - Suggested fix: keep the raw segment text from `split_operators()` on each `ChainCommand` (for example, a `text` field). In the header, show that text with the command word swapped in when a spelling fix was accepted. Add a test that pins the header for `echo "a b" $HOME | wc`.

2. **Spec text was left stale after ADRs 0018 and 0019.** See `SPEC.md:419` and `SPEC.md:142`, plus ADR 0019.
   - Problem:
     - The §11 Phase 4 deliverable still says "`parser.py` gains `shlex` tokenizing with `punctuation_chars=True`". That contradicts the updated §3.2 step 1 and ADR 0019.
     - The §3.3.1 example still ends with `In short: list all files, then keep only the lines containing "txt".` The ADR 0018 design can't produce that line. The real output is `In short: list files, then pass the output to find matching lines.`
     - ADR 0019 replaces the tokenizing decision in ADR 0002 but doesn't say it supersedes that part.
   - Why it matters: SPEC.md is the source of truth (CLAUDE.md). Someone reading §11 or the example will expect behavior the code doesn't have.
   - Suggested fix: reword the §11 Phase 4 deliverable to "a quote-aware operator scanner (ADR 0019)", and update the §3.3.1 example to the real output. Add a line to ADR 0019's Status: "Supersedes the tokenizing part of ADR 0002." This edits ADR 0019, which isn't committed yet, so it doesn't break the "never edit an accepted ADR" rule for 0002.

3. **Declining the other-shell question inside a chain drops the whole input without saying anything.** See `commandexplain/cli.py:212-213`.
   - Problem: `ls ; setopt autocd` in bash, answered **no**, goes straight back to the prompt. Nothing is printed, and `ls` isn't explained either. For a single command, silence is fine, because the user only asked about that command. For a chain, the user gets no feedback at all. The spec (§3.3.1: "the other-shell question applies to every command in a chain") doesn't say what **no** should do. The test `test_other_shell_command_in_chain_is_asked_about` pins the silent drop.
   - Why it matters: beginners may think the program froze or ignored them. It's also a behavior the spec doesn't define and no ADR records.
   - Suggested fix: decide what should happen and write it down in SPEC §3.3.1 and ADR 0018. Either print a short line (for example, "OK, I won't explain it. Please re-enter the command.") or explain the rest of the chain with a "skipped" note.

4. **Test gaps for new chain paths.** See `tests/test_cli.py`.
   - Problem:
     - `PROMPT_PATHS` (Ctrl+C and Ctrl+D at every prompt) has no prompt reached mid-chain, such as the second "Did you mean" in `sl | grpe x` or the other-shell question inside a chain. I checked by hand that both exit cleanly, but nothing protects this from regressions.
     - No test covers the missing or broken operators file (Blocker 1).
     - No test covers the header's exact text (Should fix 1).
   - Suggested fix: add `(["yes", "sl | grpe x", "yes"], "second suggestion in a chain")` and `(["yes", "ls ; setopt x"], "other-shell question in a chain")` to `PROMPT_PATHS` (run with `argv=["--shell", "bash"]` for the second). Add the two tests named above.

### Nits
1. **The parser misses some edge cases.** See `commandexplain/parser.py:209` and `:288`.
   - A numbered redirect right after an operator with no space (`ls;2>x`, `ls|2>x`) isn't detected, because the check only looks for a space before the digit. Instead, `2` becomes a command ("Sorry, I don't know '2'"). Treat the start of a segment (after `|`, `;`, `&`, `<`, `>`) the same as a space.
   - A lone `;` prints "The command name is empty." instead of `Something is missing before ";"`.
   - `ls >| out` prints `Something is missing after ">"`. Consider adding `>|` to `_UNSUPPORTED`.
2. **`ls > out.txt | wc` gives a misleading "In short".** The line says "save the output to out.txt, then pass the output to count lines and words". In bash, the pipe receives nothing. In zsh, which turns on MULTIOS by default, the output goes to both. It's rare for beginners, but the "In short" line isn't true for bash here. Consider leaving "In short" out when a `>` or `>>` redirect is followed by `|`.
3. **A not-covered command after sudo in a chain has no lead-in.** For `sudo git push | wc`, the git message comes right after sudo's warning, with no `sudo runs this command:` line. The single-command format does say "sudo runs "git"…". See `formatter.py:214-226`.
4. **PEP 8 E303:** there are three blank lines before the new test sections, at `tests/test_cli.py:523`, `tests/test_data.py:310`, and `tests/test_formatter.py:362`.
5. **The §5 JSON example** (`SPEC.md:191-235`) doesn't show the now-required `short` field on `ls`, `rm`, or `setopt`.

## What went well
- The quote-aware scanner is a real improvement over the spec's original `shlex` plan. ADR 0019 explains why, and the lookalike tests (`echo '$(date)'`, `head -2>x`, `echo 2 > f`) and the round-trip tests pin the tricky cases.
- Naming unsupported syntax (`2>`, `&`, `$(`) instead of guessing avoids a whole class of wrong explanations, which matters most for beginners.
- The `short` phrases are accurate, plain, and grammatical when joined. Warnings (`rm`, `sudo`, `kill`, `chmod 777`, `>`) are kept inside chain blocks.
