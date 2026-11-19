# 0018. Chain output format and the "In short" line

## Status
Accepted (2026-11-19). Fills in SPEC.md §3.3.1 and the `short` fields in §5 and §5.1.

## Context
SPEC.md §3.3.1 gave one example of chain output, and its text didn't settle several details:
- Should chain blocks show "Common options", warnings, or shell notes? The text said "the format above but without the example line", but the example was a compact one-line header.
- How is the "In short" line built? The example ("list all files, then keep only the lines containing 'txt'") depends on the flags and arguments, which static data can't produce.
- What happens when a chain contains a real command this version doesn't cover (`ls | sort`)?

## Decision
- **Short blocks.** Each command in a chain is shown as:
  - the words as typed (after any accepted spelling fixes),
  - `name — plain name: summary`,
  - the typed flags and the `argument:` lines.

  There is no "Common options" and no example. **Warnings and shell notes are kept**, because combined commands like `sudo rm -rf x ; ...` are exactly where safety notes matter. sudo's inner command is explained inside the same block.
- **"In short" from static phrases.** Every command has a 2–4 word `short` verb phrase ("list files"). Every operator has a `short` phrase ("then pass the output to"; for redirects, "and save the output to {file}"). The line joins them in order, for example: "In short: make a folder, and if that works, change folder." A command run by sudo adds "(using sudo)". If any command has no phrase, the line is left out instead of being half-built.
- **Not-covered commands in a chain** don't reject the input. Their block shows the not-covered message, the rest is still explained, and the "In short" line is left out. An unknown command with no suggestion still rejects the whole chain, as a typo most likely caused it.

- **Declining the other-shell question in a chain** (`ls ; setopt x` in bash, answered no) prints `OK, I won't explain it. Please re-enter the command.` and drops the input. That way the user always gets feedback; a silent drop could look like the program froze. A single command still just returns to the prompt.
- **No "In short" when saved output is piped on** (`ls > out.txt | wc`), **or saved to two files** (`ls > a > b`). bash sends the output only to the last place, and zsh sends it to all of them. One generic sentence can't be true for both.
- **No "In short" when sudo runs a builtin** (`sudo cd /tmp ; ls`). sudo can't run `cd`, so "change folder (using sudo)" wouldn't be true.
- **Headers keep names as typed.** `LS -A` and `. ~/.bashrc` are shown that way. Only an accepted spelling fix changes a word in the header.

## Consequences
- Chains stay readable, and nothing important (warnings) is lost.
- The "In short" line is generic. It doesn't mention arguments like "txt", but it is always grammatical and always true.
- Every new command needs a `short` phrase, and a data test enforces this.
