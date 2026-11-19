# 0010. Explain the command that sudo runs

## Status
Accepted (2026-11-19). Adds SPEC.md §3.2 step 7, a rule in §3.3, and two optional data fields in §5.

## Context
The Phase 2 review found a blocker. Every word after `sudo` was read using **sudo's** flags:
- `sudo rm -i old.txt` explained `-i` as "Start an administrator session".
- `sudo ls -l` explained `-l` as "List what you are allowed to run with sudo".
- `sudo rm -rf /` never explained `rm` and never showed its delete warning.

These were wrong explanations, on a command beginners often paste in. The code followed the spec exactly, so the spec had a gap.

## Decision
- Add two optional data fields:
  - `runs_command: true` marks a command that runs another command (only `sudo` for now).
  - `flags_with_values` lists flags that take the next word as their value (sudo's `-u`).
- For such a command, flag reading stops at the first plain word, or right after `--`. That word and everything after it make up the **inner command**. A value for a flag in `flags_with_values` is listed as one of the wrapper's arguments.
- The explanation shows the wrapper, then the line `sudo runs this command:`, then the inner command's full explanation, including its own warnings. The inner command can itself be a wrapper.
- When there is an inner command, the wrapper's "Common options" are left out. They would distract from the inner command and could clash with it (sudo's `-i` vs rm's `-i`).
- If the inner command isn't in the data, a line says so, instead of raising an error.

## Consequences
- `sudo rm -rf /` now shows both sudo's warning and rm's "deletes files permanently" warning.
- The knowledge of which commands wrap others stays in the JSON, not in Python.
- Phase 3 still needs to decide whether to offer spelling suggestions for a misspelled inner command (`sudo sl`). For now, it's reported as unknown.
- Grouped wrapper flags with a value (`sudo -iu bob`) take the value for the last flag in the group, which matches how sudo reads them.
