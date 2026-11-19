# 0017. Phase 3 CLI details: messages, the not-covered file, and shell questions

## Status
Accepted (2026-11-19). Records decisions made while building Phase 3, for SPEC.md §3.1, §3.2, §3.5, §5.2, §6, and §12.

## Context
Building the interactive CLI and its review raised several small decisions that the spec didn't cover yet:
- Wording for two input errors (a trailing backslash, an empty command name). Only the unclosed-quote message was in the spec.
- The format of the "not covered" list that ADR 0011 called for.
- SPEC §13 open question 1: is the 35-command list right for v1?
- The Phase 3 review found real commands still being "corrected" into other commands (`dd` → `cd`, `rg` → `rm`, `htop` → `top`), and real shells being "corrected" at the shell question (`sh` → `zsh`, `dash` → `bash`).
- The review also found that the shell question could leave a user stuck: there was no hint after a declined suggestion, and no way to type `quit`.

## Decision
- **Messages:**
  - A trailing backslash prints `Your command ends with a backslash (\), which needs something after it. Please re-enter it.`
  - An empty command name prints `The command name is empty. Please re-enter it.`
  - The CLI picks the message from `ParseError.reason`.
- **Not-covered file:** `data/not_covered.json` maps a name to `{"kind": "tool" | "uncovered"}`.
  - `tool` means a separate program (`git`, `rg`, `htop`).
  - `uncovered` means a real terminal command that v1 doesn't explain (`unset`, `dd`, `bash`).
  - A name can't be both covered and not covered, and a data test enforces this.
  - The list includes the real commands the review found being miscorrected.
- **Command list:** keep the 35 commands in §6 for v1. More can be added later as data.
- **Shell questions:**
  - Other real shells (`sh`, `ksh`, `dash`, `csh`, `tcsh`, `fish`, ...) get "this program only covers bash and zsh" instead of a suggestion.
  - Every answer that isn't accepted is followed by the hint.
  - `quit`/`q` leaves at either shell question.
  - The "Is that right?" question also accepts a shell name.
  - `shell bash` switches at once.

## Consequences
- Beginners are no longer sent to a different command or shell than the one they typed, and they always have a way out.
- The not-covered list will need to grow as people try more commands. Adding to it is a data change only.
- Some new conveniences (`shell bash`, answering with a shell name) slightly widen what the CLI accepts. Each one has a test.
