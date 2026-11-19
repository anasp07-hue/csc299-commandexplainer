# 0001. Store command knowledge as JSON key-value data

## Status
Accepted (2026-11-19)

## Context
The problem statement requires "some type of key value pairs". The program needs a lookup from a command name to its explanation, flags, warnings, and shell support. This data will grow over time, and it should be easy to edit without touching the program logic.

## Decision
Command data lives in `commandexplain/data/commands.json` and operator data lives in `commandexplain/data/operators.json`. Both are loaded into Python `dict`s at startup. The key is the command name or operator, and the value is a dict with the fields defined in SPEC.md §5. A test validates every entry against that schema.

## Consequences
- Adding a command means adding data, not writing code.
- Lookups are simple O(1) dict access.
- JSON has no comments, so field meanings must be documented in SPEC.md §5.
- A typo in the data won't show up when the program runs, so the schema test is required to catch it.
