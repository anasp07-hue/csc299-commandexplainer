# 0012. List each argument on its own line

## Status
Accepted (2026-11-19). Changes SPEC.md §3.2 step 6.

## Context
Arguments were laid out in the same two-column table as flags, with the explanation "An argument you gave the command." The label column grows to fit the longest entry, so a normal file path squeezed that text into a narrow strip. A 120-character path printed one word per line. File paths are the most common arguments.

## Decision
Each argument is listed on its own line as `argument: <word>`, outside the flag table. This matches the chain format in SPEC.md §3.3.1. Argument lines aren't wrapped, because a path can't be broken safely.

## Consequences
- Long paths no longer break the layout of the flags or anything else.
- An argument line can be longer than 80 characters when the argument itself is. That's the only exception to the width limit, and the width test allows it.
