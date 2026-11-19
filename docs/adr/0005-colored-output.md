# 0005. Use colored output with automatic fallback

## Status
Accepted (2026-11-19)

## Context
Color makes the explanations easier to scan: bold command names, red warnings, and so on. However, color codes make a mess when output is piped or saved to a file, and some users turn color off.

## Decision
Use plain ANSI escape codes, with no extra library, as listed in SPEC.md §3.3.2. Turn colors off automatically when stdout is not a TTY, when `NO_COLOR` is set, or when the program is started with `--no-color`. Color never carries meaning on its own: warnings still start with "⚠ Careful:".

## Consequences
- More readable in a terminal, and still works with the standard library only.
- Tests must check output both with and without color, or turn color off by default.
- Windows terminals without ANSI support aren't a target (the program targets bash/zsh users).
