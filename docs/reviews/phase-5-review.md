# Phase 5 review — Colors and polish

**Date:** 2026-11-19
**Commits reviewed:** 483f5a3 (HEAD, end of Phase 4) + uncommitted changes. All Phase 5 work is uncommitted: `colors.py`, `README.md`, ADR 0020, `tests/test_colors.py`, and edits to `cli.py`, `formatter.py`, `shell.py`, the data files, `SPEC.md`, `pyproject.toml`, and the tests.
**Verdict:** PASS WITH FIXES

## Test results
- `pytest -q` → **1084 passed in 0.39s**.
- The suite also passes with stdout attached to a real pseudo-terminal (`pytest -s`) and with `NO_COLOR=1` exported, so the tests don't depend on the terminal.
- Manual checks:
  - **Real pseudo-terminal** (stdout on a pty, `--shell zsh`, input `rm -rf x | wc`, `sudo cd /`, `sl`/`yes`): 36 escape codes. The command names were bold, the flags cyan, the warnings red (each wrapped line colored separately, indent left plain), `|` magenta, and the `Did you mean 'ls'?` prompt yellow.
  - **Shell question in a pty** (`no`, `zhs`, `yes`): `Did you mean zsh?` was yellow. No other codes.
  - **Same pty with `NO_COLOR=1`**: 0 codes. **With `--no-color`**: 0 codes. **Piped** (`python3 -m commandexplain --shell zsh | cat -v`): 0 codes.
  - **Edge inputs, colored vs plain** (`ls > out.txt`, an over-long unknown flag, `LS -la`, non-ASCII arguments `café ñ`, `sudo -u bob kill -9 1`, `find . -name x -delete`, `. ~/.zshrc`): with the codes stripped, the colored text was identical to the plain text, and the codes sat only on the intended words.
  - **`maybe` at a colored yes/no prompt**: the yellow question is asked again.
  - **README example session**: the output matches the real program word for word. The "honest limits" claims (`sort` and `curl` are uncovered, `brew` is a tool, `2>&1` and `&` are unsupported) all hold.
  - **README "Adding a command" steps**, followed exactly in a scratch copy: **2 tests fail** (see Should fix 1).
  - **Stdout closed** (`python3 -m commandexplain >&-`): a traceback (see Nit 3).

## Acceptance criteria
| # | Criterion | Status | Evidence |
|---|---|---|---|
| 11 | Color codes in a terminal, none when piped, with `NO_COLOR`, or with `--no-color` | ✅ | `tests/test_cli.py::test_ac11_terminal_output_has_colors`, `test_ac11_colors_off[not-a-terminal / NO_COLOR / --no-color]` (output and prompts both checked), plus the manual pty and pipe runs above |
| 13 | All tests pass | ✅ | `pytest -q` → 1084 passed |
| 1–10, 12, 14–16 | Earlier criteria still pass | ✅ | Full suite green. The wording change (`print text` → `show text`) updated `tests/test_formatter.py::test_sudo_inside_chain` to match |

**Deliverables:**
- `colors.py` and color support in `formatter.py`, `cli.py`, and `shell.py`: present and complete.
- `README.md`, with install, run, an example session, and how to add a command: present, but has one issue (Should fix 1).
- The wording pass: done (Print → Show, plus glosses for path, shell, and signals), with gaps (Should fix 2).

**Spec conformance:** §3.3.2 was updated and recorded in ADR 0020 (with the §12 row added). The new pipe summary is in both §3.3.1 and §5.1. No scope creep, and no quiet divergence found.

## Findings

### Blockers
None.

### Should fix
1. **The README's "Adding a command" example breaks the test suite** — `README.md:100-131`
   - Problem: the walkthrough adds `sort` to `commands.json` and removes it from `not_covered.json`, then says "Run the tests". Two tests use `sort` as their example of a not-covered command:
     - `tests/test_cli.py::test_not_covered_segment_is_explained_in_place` (line 579),
     - `tests/test_formatter.py::test_not_covered_command_in_chain_is_named` (line 418).

     When I followed the README exactly in a scratch copy, I got `2 failed, 1100 passed`.
   - Why it matters: the README tells someone adding a command to trust the tests. Their first try will fail for reasons that have nothing to do with their entry. The README's "Honest limits" list (`sort`, `curl`) would also go out of date.
   - Suggested fix: do one of these:
     - make those two tests independent of the real data, by passing a small `not_covered` dict or using a name that will never be covered, or
     - pick a README example that no test relies on, and drop `sort` from the "Honest limits" list or reword it.

     The first is sturdier.
2. **The wording pass left "signal" unexplained everywhere except `kill -l`** — `commandexplain/data/commands.json` (kill: `-15`, `-HUP`, `-s`)
   - Problem: the pass added "(messages to a program)" only to `-l`. These flags still use the word with no explanation:
     - `-15`: "…if you don't give a signal",
     - `-HUP`: "Send a 'hang up' signal",
     - `-s`: "Choose which signal to send".

     Typed flags are shown alone (`kill -HUP 123` shows only `-HUP`), so the one gloss on `-l` is never seen in those cases. In the same way, `which`'s zsh note says "an alias or a function", and "function" is never explained anywhere.
   - Why it matters: §3.3 and CLAUDE.md say "no unexplained jargon", and this phase's deliverable was the final wording pass. A beginner reading `kill -HUP` sees a term they've never met.
   - Suggested fix: explain "signal" where it first appears in each flag's text, or put it in kill's summary (for example "…by sending it a signal, a short message that tells it what to do"). Then the flags can use the word freely. Reword "function" (for example "a shortcut or a saved mini-script") or drop it.

### Nits
1. **`mkdir -p` and `rmdir -p` describe their examples differently** — `commands.json` (mkdir and rmdir `-p`). mkdir says "like a and b in a/b/c". rmdir says "like a/b in a/b/c", which reads like one folder. Use the same form, for example "(like b and then a in a/b/c)".
2. **A stale docstring and dead code** — `commandexplain/parser.py:4`, `:78`. The module docstring still says "parse_input() and split_flags() then handle one command", but `parse_input()` is now used only by tests. Handoff 004 left this to the Phase 5 polish pass, and it wasn't decided. Either remove it, or fix the docstring and note the decision in the handoff.
3. **A traceback when stdout is closed** — `commandexplain/cli.py:320`. `sys.stdout.isatty` is looked up outside the guarded call, so with `sys.stdout is None` (`commandexplain >&-`) the program crashes with `AttributeError`. ADR 0020 says "If it fails, colors stay off". This setup is unusual, and the program couldn't prompt anyway, so the impact is low. Fix: `isatty = getattr(sys.stdout, "isatty", lambda: False)`, or do the lookup inside `colors_enabled`'s try.
4. **The default wiring isn't tested** — `tests/test_cli.py`. Every test passes `isatty=` and `env=`, so nothing checks that `main()` really defaults to `sys.stdout.isatty` and `os.environ`. A swapped default would still pass. AC 11's literal `| cat` case was only checked by hand here. One test that monkeypatches `sys.stdout` with an object whose `isatty()` returns True would cover it.
5. **The README install step and beginners' Python setups** — `README.md:11-15`. `pip install -e .` with no virtual environment is refused by Python installs marked "externally managed" (PEP 668), such as recent Homebrew Python. I couldn't reproduce this here, because this machine uses the python.org build, which isn't marked. To confirm, run the step on a Homebrew `python3`. Consider adding the two venv lines (`python3 -m venv .venv && source .venv/bin/activate`) before the install.

## What went well
- Colors are added after wrapping, and a parametrized test checks that stripped colored output equals plain output for every command, in both shells, plus chain samples. It's a strong guarantee that colors never change the text or layout.
- `NO_COLOR`, `--no-color`, and the not-a-terminal case are each tested against both printed output **and** prompts. Injecting `isatty` makes the suite pass the same way in a pty, under `-s`, and with `NO_COLOR` exported.
- The README example session is accurate word for word, and the project rules hold: stdlib only, ≤99 columns, type hints and docstrings on every function, no tracked junk, no AI attribution.

**Docs:** ADR 0020 covers the spec change. `docs/handoffs/005-phase-5.md` doesn't exist yet, which is expected because this review runs before the handoff.
