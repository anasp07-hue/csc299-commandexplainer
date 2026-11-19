# 0004. Explain commands and flags only, not arguments

## Status
Accepted (2026-11-19)

## Context
Arguments like `..`, `~`, `*`, or `755` (in `chmod 755`) have meanings that beginners might want explained. Supporting them means more data, and special-case logic for each command.

## Decision
v1 explains commands and flags only. Any other token is listed as "an argument you gave the command" and is not explained.

## Consequences
- Keeps the data model and the parser simple.
- Some useful explanations (`cd ..`, `chmod 755`) are missing for now. We can revisit this in a later version with a new ADR.
