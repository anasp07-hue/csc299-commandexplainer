# 0006. Check for one-edit typos before using difflib

## Status
Accepted (2026-11-19). Changes the matching rule in SPEC.md §4.

## Context
SPEC.md §4 used `difflib.get_close_matches(..., cutoff=0.75)` on its own. The Phase 1 review found that it misses the most common beginner typo, swapped letters in short commands:
- `sl` scores 0.5 against `ls`,
- `cta` and `pdw` score 0.67 against `cat` and `pwd`.

With that rule, acceptance criteria 4 and 10, and Phase 2's "Done when" check (`suggest("sl")` returns `"ls"`), could never pass. Lowering the cutoff would fix those cases, but it would also suggest commands for unrelated words.

## Decision
Find a suggestion in two steps (standard library only):
1. **One edit away.** Collect every command name or alias that is exactly one edit from the input. An edit is one letter added, removed, or changed, or two neighboring letters swapped. If several names qualify, pick the one with the highest `difflib.SequenceMatcher` ratio, breaking ties alphabetically.
2. **Otherwise, use difflib.** Fall back to `difflib.get_close_matches(word, names, n=1, cutoff=0.75)` for longer typos.

Input shorter than 2 characters never gets a suggestion.

## Consequences
- `sl`, `cta`, `pdw`, and `cdd` all get the right suggestion, and longer typos still work the way they did.
- Two-letter inputs can be one edit away from several commands (`cs` could be `cd` or `ls`). The ratio-then-alphabetical tie-break keeps the result predictable, and the user always confirms with yes/no, so a wrong guess costs one "no".
- A small one-edit check (about 20 lines) needs its own unit tests in Phase 2.
