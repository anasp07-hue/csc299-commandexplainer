# 0013. Warn when sudo is used with a shell builtin

## Status
Accepted (2026-11-19). Adds the optional `builtin_only` data field and a rule in SPEC.md §3.3. Builds on ADR 0010.

## Context
After ADR 0010, `sudo cd /root` printed "sudo runs this command:" followed by "cd: Moves you into a different folder". But sudo can only run programs, and `cd` is built into the shell:
- On Linux, it fails with `sudo: cd: command not found`.
- On macOS, it runs `/usr/bin/cd` in a separate process, so your folder never changes.

The same goes for `export`, `source`, `alias`, `history`, `exit`, `shopt`, `setopt`, and `unsetopt`. `sudo cd` is a classic beginner mistake, often tried right after `cd` says "Permission denied", and the tool was confirming the wrong idea.

## Decision
- Add the optional field `builtin_only: true` to the shell builtins that have no separate program. `echo`, `kill`, and `pwd` are builtins too, but they also exist as real programs, so sudo can run them, and they aren't marked.
- When a wrapper's inner command is `builtin_only`, show `⚠ Careful: sudo can't run cd, because cd is built into the shell. It will fail or have no effect.` right after "sudo runs this command:". Then still explain the inner command, so the user learns what it does.

## Consequences
- Beginners are told why `sudo cd` won't work, instead of being told that it does.
- The list of builtins lives in the JSON, and a data test pins it down exactly.
- The warning says "fail or have no effect" so it is true on both Linux and macOS.
