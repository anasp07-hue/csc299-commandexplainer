# 0002. Explain pipes and chained commands

## Status
Accepted (2026-11-19)

## Context
Beginners often copy commands such as `ls -a | grep txt` or `mkdir d && cd d` from tutorials. We had two options: reject anything with more than one command, or explain each part.

## Decision
Split the input at the operators `|`, `&&`, `||`, `;`, `>`, `>>`, and `<`. Then explain each command, and the operator between commands, in plain English (SPEC.md §3.3.1). Tokenize with `shlex.shlex(..., posix=True, punctuation_chars=True)` so that quoted text like `grep "a|b"` is not treated as a pipe. Each command in a chain goes through spelling suggestions on its own.

## Consequences
- More useful for real-world commands that beginners paste in.
- The parser is more complex, and new error cases need handling (an unclosed quote, an operator missing a command on one side).
- Advanced syntax (`$( )`, `2>&1`, loops) is still out of scope.
- This is built in its own phase, after the single-command CLI works.
