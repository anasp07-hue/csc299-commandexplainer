# 0016. Type "shell" to switch shells mid-session

## Status
Accepted (2026-11-19). Answers SPEC.md's former open question 2 and changes §3 and §3.1.

## Context
The shell was fixed for the whole session. A user who picked the wrong shell, or who wanted to compare how a command differs in bash and zsh, had to quit and start again.

## Decision
- At the command prompt, typing `shell` (in any case) asks "Are you using bash or zsh?" again, with the same typo handling, and then shows `Switched to bash.`.
- After the shell is first chosen, the program shows `Using zsh. (Type "shell" any time to switch.)` so users can find this feature.
- `shell` isn't a real command, so it can't clash with anything the user wants explained.

## Consequences
- Switching is quick and easy to find.
- The confirmation line shows the chosen shell, which also helps when the shell was auto-detected or set with `--shell`.
