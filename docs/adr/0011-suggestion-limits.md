# 0011. Limit spelling suggestions to letters, and check "not covered" first

## Status
Accepted (2026-11-19). Adds to ADR 0006 (it does not replace it) and changes SPEC.md §4 and §9.

## Context
The Phase 2 review found that ADR 0006's suggestions can point beginners at the wrong command:
- `..` was one edit from the alias `.`, so it suggested `source`. In zsh, `..` usually means "go up a folder".
- `unset` → `unsetopt` and `unalias` → `alias`, even though `unset` and `unalias` are real builtins of their own, just not covered in v1.
- `ll` and `la` → `ln`, because the alphabetical tie-break picks `ln` over `ls`.

## Decision
- Only input containing at least one letter gets a suggestion, and only names containing a letter can be suggested.
- In Phase 3, the §9 "not covered" list is checked **before** spelling suggestions. That list includes real builtins that aren't in §6 (`unset`, `unalias`, `pkill`, and so on) as well as third-party tools, and it is kept in the data.
- `ll`/`la` → `ln` is left alone. Choosing between equally close names needs popularity data the project doesn't have, and the yes/no confirmation makes a wrong guess cheap.

## Consequences
- `..`, `-l`, and similar inputs no longer produce strange suggestions.
- `unset` still suggests `unsetopt` until Phase 3 adds the "not covered" list. That is expected for now.
- The "not covered" list becomes a Phase 3 data deliverable.
