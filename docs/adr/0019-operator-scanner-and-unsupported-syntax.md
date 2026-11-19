# 0019. Find operators with a quote-aware scanner, and name unsupported syntax

## Status
Accepted (2026-11-19). Changes SPEC.md §3.2 steps 1–2 and adds a row to §9. Supersedes the tokenizing part of ADR 0002 (`shlex.shlex` with `punctuation_chars`). The rest of ADR 0002 still stands.

## Context
SPEC.md §3.2 said to tokenize with `shlex.shlex(text, posix=True, punctuation_chars=True)`. Testing showed that it can't tell a quoted operator from a real one: `echo "|"` and `echo |` both produce the token `|`. So `echo "|"` would have been read as a pipe.

Also, beginners paste in shell syntax that the spec lists as out of scope (`2>/dev/null`, `&`, `$(date)`). Without special handling, `ls 2>/dev/null` would be read as `ls` with the argument `2`, redirected to `/dev/null`, which is a wrong explanation.

## Decision
- A small scanner walks the raw text, tracking single quotes, double quotes, and backslashes. It splits only at **unquoted, unescaped** operators: `>>`, `&&`, `||`, `|`, `;`, `>`, `<` (longest first). Each piece is then split into words by the existing `tokenize()` (`shlex.split`), so the Phase 3 quote, backslash, and empty-name errors still work.
- When the scanner meets syntax this version doesn't explain, it raises `ParseError(UNSUPPORTED)` naming it. This covers a single `&`, a numbered redirect (`2>`, `2>&1`), `&>`, `>&`, `|&`, `<<`, `<<<`, `(`, `)`, `$(` (also inside double quotes), and backticks. The CLI prints `Sorry, I can't explain "2>" yet. Try a simpler version of the command.`
- An operator with nothing on one side raises `MISSING_BEFORE` or `MISSING_AFTER`, naming the operator. A `;` at the very end is allowed.
- Words after a redirect's file belong to the command before it, as in a real shell.
- Each command keeps its **typed text**, so block headers show exactly what the user typed (`$HOME`, not `'$HOME'`). `retype()` swaps in only the words changed by a spelling fix. `chain_to_text()` joins the typed texts back into a line that parses to the same chain.
- A number right after an operator (`ls;2>x`) also counts as a numbered redirect. A lone `;` is "missing before". `>|` is unsupported.
- An unquoted `#` at the start of a word is unsupported. bash treats it as the start of a comment (so the rest of the line is ignored), but in zsh it's a plain word unless `interactive_comments` is on. Any single explanation would be wrong for one of the two shells. `#` inside a word (`a#b`) or in quotes is fine.

## Consequences
- Quoted and escaped operators are handled correctly.
- Unsupported syntax gets an honest message instead of a wrong explanation.
- The scanner is about 60 lines of code. A round-trip test and a set of lookalike tests (`echo '$(date)'`, `head -2>x`) pin its behavior.
