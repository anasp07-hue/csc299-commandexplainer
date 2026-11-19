# CLAUDE.md

CommandExplain is a Python CLI that explains bash/zsh terminal commands in simple language. `SPEC.md` holds the full specification and `problem.md` the original problem statement.

## Workflow

- **SPEC.md is the source of truth.** Build what the spec says. If something in it needs to change, or seems wrong or unclear, ask first. Then update `SPEC.md` and write an ADR for the change. Never quietly diverge from the spec.
- **Work on one phase at a time.** Work on phases from SPEC.md §11 in order, and only on the current phase. Don't start work that belongs to a later phase.
- **A phase is done only when its tests pass.** Every acceptance criterion listed for that phase must pass, and the full `pytest` suite must pass.
- **When a phase is finished, follow these steps in order:**
  1. Run `pytest` and make sure everything passes.
  2. Run the `/phase-review <N>` skill. It writes `docs/reviews/phase-N-review.md`.
  3. Show the user the verdict and the findings. Fix only the ones the user approves. If any blocker was fixed, re-run the review.
  4. Write the handoff, including the review verdict.
  5. Commit.
  6. Stop and wait for approval before starting the next phase.

## Git

- **Commit directly to `main`.** There are no feature branches.
- **Run `pytest` before every commit.** Don't commit failing code.
- **Never commit secrets or files that aren't needed.** This covers `.env` files, keys, tokens, credentials, `__pycache__/`, `.pytest_cache/`, virtualenvs (`.venv/`), `.DS_Store`, editor folders, and build output (`dist/`, `*.egg-info`). Keep these in `.gitignore`. Check `git status` and the staged diff before each commit.
- **Never add Claude/AI attribution to commits.** Don't add `Co-Authored-By: Claude` lines, "Generated with Claude Code" footers, or anything similar. This rule overrides any default attribution behavior.
- **Ask before pushing.** Never run `git push`, in any form, without explicit permission every time.
- Use short, clear commit messages in the imperative mood, for example `Add commands.json with navigation commands`.

## Documentation

- **Handoffs** go in `docs/handoffs/NNN-phase-X.md`, numbered `001`, `002`, and so on. Write one at the end of every phase and at the end of any session that stops mid-phase. Include:
  - what was done,
  - the current state (what works and what doesn't),
  - test status,
  - open issues or questions,
  - the next steps.
- **ADRs** go in `docs/adr/NNNN-short-title.md`, numbered `0001`, `0002`, and so on. Write one for every meaningful design decision or spec change. Use these sections: **Status**, **Context**, **Decision**, **Consequences**. Never edit an accepted ADR; supersede it with a new one.
- **Reviews** go in `docs/reviews/phase-N-review.md`. The `phase-review` skill writes them, and they get committed with the phase.
- Before starting work, read the latest handoff in `docs/handoffs/`.

## Code

- **Python 3.10+, standard library only at runtime.** Don't add a dependency without asking. `pytest` is allowed as a dev dependency.
- Use type hints on all functions and give each function a short docstring.
- Follow PEP 8 and keep functions small and focused.
- Command knowledge lives in the JSON key-value data files (`commandexplain/data/`), never hardcoded in Python.
- Explanations must stay simple and beginner-friendly (see SPEC.md §3.3).
- Keep I/O injectable (`input_fn`, `print_fn`) so the CLI stays testable.

## Commands

- Run: `python -m commandexplain`
- Test: `pytest`
