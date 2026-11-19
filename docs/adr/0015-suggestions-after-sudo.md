# 0015. Offer spelling suggestions for the command after sudo

## Status
Accepted (2026-11-19). Changes SPEC.md §4. Builds on ADRs 0006, 0010, and 0011.

## Context
After ADR 0010, `sudo sl -la` explained sudo and then said `sudo runs "sl", which I don't have an explanation for.` A top-level `sl` gets "Did you mean 'ls'?", so treating the same typo differently after `sudo` was inconsistent. It was also unhelpful, because beginners often type `sudo` in front of commands.

## Decision
The CLI checks each command in a sudo chain with the same steps as a top-level command: a known name, then the not-covered list, then a spelling suggestion.
- **yes** to a suggestion replaces that word and explains the corrected input (`sudo ls -la`).
- **no** drops the whole input with "Command not found. Please re-enter it.", the same as for chains (SPEC.md §3.3.1).
- An inner command on the not-covered list shows that message, and sudo is still explained.
- An inner command with no suggestion is kept, and the explanation says sudo runs something it doesn't know.

The words after a value-taking flag (`sudo -u bob`) are never checked, because the parser knows `bob` is a value.

## Consequences
- Typos behave the same everywhere.
- The CLI rebuilds the corrected input with `shlex.join` and passes it to `explain()`, so quoted arguments survive a spelling fix.
- The same per-segment check will work for chains in Phase 4.
