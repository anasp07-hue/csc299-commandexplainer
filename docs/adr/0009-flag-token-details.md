# 0009. Details of how flag tokens are read

## Status
Accepted (2026-11-19). Adds to SPEC.md §3.2, step 5. Builds on ADR 0007.

## Context
While building the Phase 2 parser, several real inputs turned out not to be covered by SPEC.md §3.2:
- `kill -15 123` would be split into `-1` and `-5`, which is meaningless.
- `--color=auto` would be looked up as `--color=auto`, so it never matches a `--color` key.
- `cd -` (go back to the previous folder) has a lone `-`, which isn't a flag at all.
- `--` is the standard way to say "no more flags after this" (for example, `rm -- -file`).
- `ls -ll` would list `-l` twice.

## Decision
- A dash followed only by digits stays one flag: `-15`.
- `--name=value` is read as the flag `--name`.
- A lone `-` is an argument.
- `--` ends flag reading. It isn't shown, and every word after it is an argument.
- Repeated flags are shown once, in the order first typed.
- Flags are case-sensitive, because `-r` and `-R` really are different. Command names are not case-sensitive.

## Consequences
- The parser does what a real shell command would do in these cases, so beginners aren't told something wrong.
- `-15` is shown as an unknown flag unless the data adds it. That's honest, and fixing it means adding data, not code.
- Each rule has a unit test in `tests/test_parser.py`.
