---
name: phase-review
description: Reviews the code and data for a finished CommandExplain phase against SPEC.md, CLAUDE.md, and general correctness, then writes a review report to docs/reviews/. Use this whenever a phase from SPEC.md §11 is finished or close to finished, before writing the phase handoff, or when the user asks to "review", "check", or "look over" a phase's work, even if they don't say "phase-review" by name.
argument-hint: "[phase number, e.g. 1]"
context: fork
---

# Phase review

You are reviewing one finished phase of CommandExplain, a beginner-friendly Python CLI that explains bash/zsh commands. Review it the way a careful senior reviewer would. The author has already convinced themselves the work is done, so your value comes from finding what they missed. Don't rubber-stamp it.

The phase to review is: **$ARGUMENTS**. If no phase was given, work it out from the latest file in `docs/handoffs/` and from `git log`. Say which phase you assumed.

**This is a review, not a fix.** Don't edit code, data, or tests. Report the findings so the user can decide what gets fixed. The project rule is that the user approves changes phase by phase.

## 1. Gather context

Read these first:
- `SPEC.md`: the §11 section for this phase (deliverables plus "Done when"), and every spec section that phase points to.
- `CLAUDE.md`: the project rules.
- `docs/adr/`: any ADRs, so you don't flag a decision that was made on purpose.
- The changes this phase made. Use `git log --oneline` to find where the phase started, then `git diff <start>..HEAD`, and `git status` for uncommitted work. Read the changed files in full, not only the diff hunks, because bugs hide in the surrounding code.

## 2. Run the checks

Run `pytest -q` and record the exact result. Also try the phase's "Done when" example by hand where you can, for example `python -c "from commandexplain.lookup import load_commands; print(load_commands()['rm']['flags']['-r'])"`, or a scripted CLI session. Passing tests don't prove the behavior is right, so check the behavior directly.

## 3. Review checklist

Go through every area. Skip an item only if it can't apply to this phase.

**Spec conformance**
- Is every deliverable listed for this phase present and complete?
- Does each acceptance criterion assigned to this phase pass? Point to the test that proves it, or say that no such test exists.
- **Scope creep:** did the phase build things that belong to a later phase? Flag it. The rule is one phase at a time.
- Does anything quietly differ from the spec without an ADR?

**Correctness**
- Think through edge cases: empty input, whitespace only, a lone `-` or `--`, uppercase commands, flags repeated (`-ll`), unknown flags, very long input, non-ASCII text.
- Ctrl+C / Ctrl+D (`KeyboardInterrupt` / `EOFError`) at *every* prompt, including the yes/no prompts.
- Yes/no loops must re-ask when the answer isn't yes or no, never crash, and never loop forever when input ends (EOF).
- Fuzzy matching: does `difflib` with cutoff 0.75 give sensible suggestions? Try a few real typos (`sl`, `cdd`, `grpe`, `mkdri`) and make sure correct names don't trigger a suggestion.
- Errors: a missing or broken JSON file must give a clear message, not a traceback (§9).

**Data quality** (most important in Phase 1, but check it in every phase that touches `data/`)
- **Accuracy:** flag explanations must be true for both macOS (BSD) and Linux (GNU) tools. Where they differ (for example `sed -i`, `ls --color`, `stat` flags), the entry should say so or avoid the flag. Wrong explanations are the worst bug this program can have, because the users are beginners who will trust it.
- **Plain language:** a summary is 1–2 sentences, with no unexplained jargon ("stdout", "inode", "recursive" without explanation). Imagine someone who has never opened a terminal reading it.
- `shells` is correct: bash-only (`shopt`) and zsh-only (`setopt`, `unsetopt`) commands are marked properly.
- Dangerous commands and flags have a `warning`: `rm`, `rm -rf`, `sudo`, `chmod 777`, `kill -9`, `>`, and so on.
- The commands listed in §6 are all present.

**Project rules (CLAUDE.md)**
- Standard library only at runtime. Check imports and `pyproject.toml`.
- Every function has type hints and a short docstring. Code follows PEP 8, and functions are small.
- Command knowledge lives in JSON, not hardcoded in Python.
- I/O goes through `input_fn` and `print_fn`, so the CLI can be tested.
- Git hygiene:
  - No secrets or unneeded files are tracked (`git ls-files`). Look for `__pycache__`, `.venv`, `.DS_Store`, `.env`, and build output.
  - `.gitignore` covers them.
  - No commit has Claude/AI attribution (`git log --format=%B <start>..HEAD`).

**Tests**
- Do tests check real behavior, or do they just repeat the implementation (tautological tests)?
- Are edge cases from the correctness checklist covered?
- Do tests depend on the real terminal, the real `$SHELL`, or the order they run in? They shouldn't.

**Docs**
- Is there a handoff for this phase in `docs/handoffs/`? It might not exist yet if this review runs before it. Just note that.
- Does every spec change have an ADR?

## 4. Severity

- **Blocker:** wrong behavior, a failing or missing acceptance criterion, a wrong command explanation, a crash, a leaked secret, or a broken project rule. The phase is not done until this is fixed.
- **Should fix:** a real problem that doesn't break the phase, such as a missed edge case, weak tests, unclear wording, or a missing warning.
- **Nit:** style or naming. Keep these few. If you have more than about 5 nits, list only the most useful ones.

Only report problems you've checked. If you're unsure about something, say so and explain what would confirm it. Don't present a guess as a finding.

## 5. Write the report

Save it to `docs/reviews/phase-N-review.md` (create the folder if needed). If that file already exists, this is a re-review: name the new file `phase-N-review-2.md`, and so on, and note which earlier findings are now fixed.

Use this template:

```markdown
# Phase N review — <phase name>

**Date:** YYYY-MM-DD
**Commits reviewed:** <start>..<end> (+ uncommitted changes, if any)
**Verdict:** PASS | PASS WITH FIXES | FAIL

## Test results
<pytest summary line, plus any manual checks run and what happened>

## Acceptance criteria
| # | Criterion | Status | Evidence |
|---|---|---|---|
| 12 | Data passes schema test | ✅ / ❌ | tests/test_data.py::test_schema |

## Findings

### Blockers
1. **<short title>** — `path/to/file.py:42`
   - Problem: <what is wrong>
   - Why it matters: <impact>
   - Suggested fix: <concrete change>

### Should fix
...

### Nits
...

## What went well
<1–3 short bullets. Only real strengths, no filler.>
```

Verdict rules:
- **FAIL:** there is any blocker.
- **PASS WITH FIXES:** there are no blockers, but at least one should-fix.
- **PASS:** there are only nits, or no findings at all.

## 6. Final message

Finish with a short summary for the main session: the verdict, the number of findings at each severity, the blocker titles, and the report path. The main session will show this to the user, who decides what to fix before the handoff and commit.
