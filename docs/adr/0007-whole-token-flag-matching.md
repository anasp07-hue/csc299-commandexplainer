# 0007. Match the whole flag token before splitting it

## Status
Accepted (2026-11-19). Changes SPEC.md §3.2, step 5.

## Context
SPEC.md §3.2 split every single-dash token with more than one letter into short flags, so `-rf` became `-r -f`. But `find`'s options are words that use a single dash (`-name`, `-type`, `-mtime`). Under that rule, `-name` became `-n -a -m -e`, so none of `find`'s flags could ever be explained, not even in its own example.

## Decision
For a single-dash token with more than one character:
1. If the whole token is a key in that command's `flags`, treat it as one flag.
2. Otherwise, split it into single-letter short flags, as before.

Flag keys in the data may be `-x`, `-9`, multi-letter single-dash words (`-name`), or `--long`. The data test enforces this format.

## Consequences
- `find . -name "*.txt"` explains `-name` correctly, and `rm -rf` still splits into `-r` and `-f`.
- A combined group that happens to spell a known word flag is treated as that word. No current command has both a word flag and single-letter flags that could clash like this. If one is ever added, its data needs checking.
- Phase 2's parser needs the command's flag data to parse flags, so it parses after the command is looked up (or takes the flag keys as input).
