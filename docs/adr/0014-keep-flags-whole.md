# 0014. Never split flag groups for kill

## Status
Accepted (2026-11-19). Adds the optional `keep_flags_whole` data field and SPEC.md §3.2 step 8. Builds on ADR 0007.

## Context
For `kill`, words like `-INT`, `-SIGKILL`, and `-USR1` are signal names, not groups of single-letter flags. ADR 0007's whole-token-first rule handles the signals in the data (`-KILL`, `-TERM`, `-HUP`). Any other signal was still split into letters: `kill -INT 5` showed three made-up options, `-I`, `-N`, and `-T`.

## Decision
Add the optional field `keep_flags_whole: true`. For a command with this field, single-dash groups are never split into letters. An unknown word like `-INT` becomes one unknown flag, with the usual "I don't have an explanation… try man kill" line. Only `kill` uses it for now.

## Consequences
- `kill -INT 5` shows one honest "unknown option" line instead of three made-up ones.
- Combined letter flags for kill (like `kill -ls`) aren't split. kill doesn't use combined flags in practice.
- Any other command whose flags are words can opt in through its data.
