# CommandExplain CLI — Specification

## 1. Overview

CommandExplain is an interactive command-line program, written in Python, that explains terminal commands in plain, beginner-friendly language. The user picks their shell (bash or zsh), types a command such as `rm -rf`, and gets a short explanation of what the command and each of its flags do.

See `problem.md` for the problem statement and initial requirements.

## 2. Goals and non-goals

### Goals
- Explain built-in and standard terminal commands (the ones that come with macOS/Linux) in one or two simple sentences each.
- Explain the common flags for each command (for example `-r`, `-f`, `-a`, `-l`).
- Support **bash** and **zsh**, including commands that exist in only one of them.
- Catch small spelling mistakes ("Did you mean `ls`?").
- Store all command knowledge as **key-value pairs** so that adding a command means adding data, not writing code.

### Non-goals (v1)
- Third-party tools and services (`git`, `brew`, `npm`, `docker`, `python`, and so on).
- Running the command, or checking whether the user's command would succeed.
- Explaining what an argument means (`cd ..`, `chmod 755`). Arguments are listed but not explained.
- Advanced shell syntax: subshells `$( )`, variables `$VAR`, loops, `2>&1`, globs.
- Shells other than bash and zsh (fish, PowerShell, cmd).

## 3. User flow

```
start
  │
  ▼
[1] Detect shell from $SHELL → "Looks like you're using zsh. Is that right? (yes/no)"
  │      no / can't detect → Ask: "Are you using bash or zsh?"
  │      invalid input → show the valid options and ask again
  ▼
[2] Ask: "Enter a command to explain (or 'quit' to leave):"
  │
  ├─ 'quit' / 'q' / Ctrl+D / Ctrl+C ─────────────────► goodbye message, exit 0
  │
  ├─ command found ──────────────────────────────────► [3] explain → back to [2]
  │
  ├─ command not found, close match exists
  │     "Did you mean 'ls'? (yes/no)"
  │        ├─ yes → [3] explain the suggested command → back to [2]
  │        ├─ no  → "Command not found. Please re-enter it." → back to [2]
  │        └─ anything else → "Please type yes or no." → ask again
  │
  └─ command not found, no close match
        "Sorry, I don't know 'xyz'. Check the spelling and try again." → back to [2]
```

### 3.1 Shell selection
- **Auto-detect first:** read the `SHELL` environment variable and take the last part of the path (`/bin/zsh` → `zsh`).
  - If it's `bash` or `zsh`, ask `Looks like you're using zsh. Is that right? (yes/no)`. **yes** picks that shell. **no** falls through to the manual question.
  - If `SHELL` is missing or names some other shell, go straight to the manual question.
- Manual prompt: `Are you using bash or zsh? `
- Accepts `bash` or `zsh`, ignoring case and surrounding spaces. Also accepts `1` (bash) and `2` (zsh).
- Small typos are handled the same way as for commands (`bsh` → "Did you mean bash? (yes/no)").
- If the input is invalid, show a hint and ask again: `Not sure? Run "echo $SHELL" in your terminal.`
- The chosen shell lasts for the rest of the session.

### 3.2 Command input
- The user types a command name, with flags if they want: `ls`, `ls -la`, `rm -rf`, `chmod +x`. They can also type a pipe or chain: `ls -a | grep txt`, `mkdir docs && cd docs`.
- Input is trimmed. Command names are matched without regard to case (`LS` becomes `ls`).
- Parsing:
  1. Tokenize with `shlex.shlex(text, posix=True, punctuation_chars=True)`, so quoted text stays together (`grep "a|b"` isn't treated as a pipe) and operators come out as their own tokens.
  2. Split the tokens into **segments** at these operators: `|`, `&&`, `||`, `;`, `>`, `>>`, `<`. For `>`, `>>`, and `<`, the next token is a filename, not a command.
  3. In each segment, the first token is the **command** and the remaining tokens are **arguments**.
  4. A token that starts with `--` is one long flag (`--all`).
  5. A token that starts with a single `-` and has more than one character is read like this (ADR 0007):
     - **Whole token first.** If the whole token is a key in that command's `flags`, it is one flag. For example, `find`'s `-name` stays `-name`.
     - **Otherwise split.** The token is split into separate short flags: `-rf` becomes `-r` and `-f`.
     - **Numbers stay whole.** A dash followed only by digits stays one flag: `-15` stays `-15` (ADR 0009).
     - **Details** (ADR 0009):
       - `--name=value` counts as the flag `--name`.
       - A lone `-` is an argument (as in `cd -`).
       - `--` means "no more flags": everything after it is an argument.
       - A flag typed twice (`-ll`) is shown once.
       - Flags are case-sensitive (`-r` and `-R` are different), but command names are not.
  6. A token that doesn't start with `-` (a filename, path, and so on) is an **argument**. Each one is listed on its own line as `argument: <word>` and isn't explained further (ADR 0012).
  7. **Commands that run another command** (`sudo`, marked with `runs_command` in the data) stop reading their own flags at the first argument. That word and everything after it are the **inner command**, which is explained in full after the wrapper (ADR 0010):
     - A flag listed in `flags_with_values` takes the next word as its value: in `sudo -u bob ls -l`, `bob` is `-u`'s value and `ls -l` is the inner command.
     - `--` also starts the inner command: `sudo -- rm -rf x`.
     - A value given with `=` (`--user=bob`) doesn't take the next word.
  8. A command marked `keep_flags_whole` (`kill`) never has its single-dash groups split, because `-INT` and `-SIGKILL` are signal names, not letter groups (ADR 0014).
- Empty input re-prompts silently.
- An unclosed quote (`echo "hi`) prints `It looks like a quote (") is missing its partner. Please re-enter it.` and re-prompts.
- An operator with nothing on one side (`| grep`, `ls &&`) prints `Something is missing before/after "|". Please re-enter it.`

### 3.3 Explanation output
The output is short and simple, with no jargon where it can be avoided.

```
ls  —  list
  Shows the files and folders in the current folder.

  -l   Show the list in long form (size, date, permissions).
  -a   Also show hidden files (the ones starting with a dot).

  Example:  ls -la
```

Rules:
- First line: the command and its plain-English name (for example "change directory").
- One or two sentences of summary, written for someone who has never used a terminal.
- If the user typed flags, show **only those flags**. If they typed no flags, show the command's `common_flags` under a "Common options" heading. That is at most 5 flags, and only ones beginners actually use. If the command has no common flags, leave the heading out (ADR 0008).
- If a flag isn't in the data: `-z   I don't have an explanation for this option. Try "man ls" for the full manual.`
- A **warning** line for dangerous commands or flags (for example `rm -rf`, `sudo`, `chmod 777`): `⚠ Careful: this deletes files permanently. There is no trash/undo.`
- A shell-specific note when one exists for the selected shell.
- For a command that runs another command (§3.2 step 7), the inner command's full explanation follows, after a line `sudo runs this command:`. The wrapper's "Common options" are left out in that case, so they don't get mixed up with the inner command's flags (for example, sudo's `-i` and rm's `-i`). If the inner command isn't in the data, a line says so (ADR 0010). If the inner command is marked `builtin_only` (like `cd`), a warning comes first: `⚠ Careful: sudo can't run cd, because cd is built into the shell. It will fail or have no effect.` The inner command is still explained after it (ADR 0013).
- An example of typical use.

### 3.3.1 Pipes and chains
When the input has more than one segment, explain each command in order (using the format above but without the example line), with the operator between them explained in plain English:

```
ls -a
  ls — list: Shows the files and folders in the current folder.
    -a   Also show hidden files (the ones starting with a dot).

|  (pipe)
  Takes what the left command prints and feeds it into the right command.

grep txt
  grep — search text: Shows only the lines that contain the word you give it.
    argument: txt

In short: list all files, then keep only the lines containing "txt".
```

- The "In short" line is optional. Leave it out unless every segment has a `short` phrase in the data (see §5).
- Each command in a chain goes through spelling suggestions on its own. If the user says **no** to any suggestion, the whole input is rejected with "Command not found. Please re-enter it."
- Operator explanations come from `operators.json` (see §5).

### 3.3.2 Colors
- Command names are **bold**, flags are cyan, warnings (`⚠ Careful: ...`) are **red**, "Did you mean" prompts are yellow, and operators are magenta.
- Uses plain ANSI escape codes (no extra library).
- Colors are turned **off** automatically when:
  - output isn't a terminal (`sys.stdout.isatty()` is false), or
  - the `NO_COLOR` environment variable is set, or
  - the program was started with `--no-color`.
- The text is the same with or without colors. Colors are never the only way information is shown (warnings still start with `⚠ Careful:`).

### 3.4 Shell-specific commands
- If the command exists only in the other shell (for example `setopt` while in bash mode):
  `'setopt' is a zsh command and doesn't work in bash. Explain it anyway? (yes/no)`

### 3.5 Exiting
- `quit` or `q` exits. Ctrl+C and Ctrl+D (EOF) also exit cleanly with a goodbye message, with no traceback.
- `exit` is itself a shell command, so it is **explained** rather than used to exit. After the explanation, the program adds a tip: `(Tip: type "quit" to leave this program.)`

## 4. Spelling suggestions ("Did you mean")

- Matching runs against all command names, plus aliases (see §5). It finds the suggestion in two steps, using only the standard library (ADR 0006):
  1. **One edit away.** Find every name that is exactly one edit from the input. An edit is one letter added, removed, or changed, or two neighboring letters swapped (`sl` → `ls`, `cta` → `cat`, `cdd` → `cd`). If more than one name qualifies, pick the one with the highest `difflib.SequenceMatcher` ratio, breaking ties alphabetically.
  2. **Otherwise, close enough.** Use `difflib.get_close_matches(word, names, n=1, cutoff=0.75)`. This catches longer typos like `mkdri` → `mkdir`.
- Input shorter than 2 characters never gets a suggestion, because almost every short name is one edit away from it.
- Only input containing at least one letter gets a suggestion, and only names containing a letter are suggested. So `..` is never turned into `.` (ADR 0011).
- The "not covered" check (§9) runs **before** suggestions. That way, real commands outside §6, such as `unset` or `unalias`, get "not covered" instead of a misleading "Did you mean 'unsetopt'?" (ADR 0011).
- Only the **single best** match is suggested.
- The yes/no prompt accepts `y`, `yes`, `n`, `no`, ignoring case. Anything else re-asks.
- **yes**: explain the suggested command, keeping any flags the user typed (`sl -la` becomes `ls -la`).
- **no**: print `Command not found. Please re-enter it.` and return to the command prompt.
- Typo correction applies to command names and the shell name. It does **not** apply to flags (they are too short for fuzzy matching to be reliable).

## 5. Data model (key-value pairs)

All command knowledge lives in one data file, `commandexplain/data/commands.json`, which is loaded into a Python `dict` at startup. The **key** is the command name and the **value** is a dict that describes it.

```json
{
  "ls": {
    "name": "list",
    "summary": "Shows the files and folders in the current folder.",
    "shells": ["bash", "zsh"],
    "flags": {
      "-l": "Show the list in long form (size, date, permissions).",
      "-a": "Also show hidden files (the ones starting with a dot).",
      "-h": "Show file sizes in easy units like KB and MB (use with -l).",
      "-R": "Also list everything inside sub-folders."
    },
    "common_flags": ["-l", "-a", "-h"],
    "example": "ls -la",
    "warning": null,
    "shell_notes": {},
    "aliases": []
  },
  "rm": {
    "name": "remove",
    "summary": "Deletes files. They do not go to the trash.",
    "shells": ["bash", "zsh"],
    "flags": {
      "-r": "Delete folders and everything inside them.",
      "-f": "Force: don't ask before deleting, and don't complain if a file doesn't exist.",
      "-i": "Ask 'are you sure?' before deleting each file."
    },
    "common_flags": ["-r", "-f", "-i"],
    "example": "rm notes.txt",
    "warning": "This deletes files permanently. There is no undo.",
    "shell_notes": {},
    "aliases": []
  },
  "setopt": {
    "name": "set option",
    "summary": "Turns on a zsh setting that changes how the shell behaves.",
    "shells": ["zsh"],
    "flags": {},
    "common_flags": [],
    "example": "setopt autocd",
    "warning": null,
    "shell_notes": {},
    "aliases": []
  }
}
```

| Field | Type | Required | Meaning |
|---|---|---|---|
| `name` | str | yes | What the command stands for, in plain words |
| `summary` | str | yes | 1–2 sentence beginner explanation |
| `shells` | list[str] | yes | Which shells have it: `"bash"`, `"zsh"`, or both |
| `flags` | dict[str, str] | yes (may be `{}`) | Flag → plain-English explanation. Keys look like `-r`, `-9`, `-name`, or `--all` |
| `common_flags` | list[str] | yes (may be `[]`) | Up to 5 flags beginners actually use, shown when the user typed none; each must be a key in `flags` (ADR 0008) |
| `example` | str | yes | A typical usage |
| `warning` | str or null | no | Shown for dangerous commands |
| `shell_notes` | dict[str, str] | no | Extra note per shell, for example `{"zsh": "..."}` |
| `aliases` | list[str] | no | Other names that map to this entry (for example `"."` → `source`) |
| `short` | str | no | A 2–4 word verb phrase for the "In short" line of a chain (for example `"list all files"`) |
| `runs_command` | bool | no | `true` for commands that run another command, like `sudo` (§3.2 step 7, ADR 0010) |
| `flags_with_values` | list[str] | no | Flags that take the next word as their value, like sudo's `-u`; each must be a key in `flags` (ADR 0010) |
| `builtin_only` | bool | no | `true` for shell builtins with no separate program (`cd`, `export`, ...), which `sudo` can't run (ADR 0013) |
| `keep_flags_whole` | bool | no | `true` when single-dash groups must never be split, like kill's `-INT` (ADR 0014) |

### 5.1 Operators

Operators get their own key-value file, `commandexplain/data/operators.json`:

```json
{
  "|":  { "name": "pipe", "summary": "Takes what the left command prints and feeds it into the right command." },
  "&&": { "name": "and then", "summary": "Runs the right command only if the left one worked." },
  "||": { "name": "or else", "summary": "Runs the right command only if the left one failed." },
  ";":  { "name": "then", "summary": "Runs the left command, then the right one, no matter what." },
  ">":  { "name": "save to file", "summary": "Saves the output into a file, replacing what was in it.", "warning": "This erases the file's old contents." },
  ">>": { "name": "add to file", "summary": "Adds the output to the end of a file." },
  "<":  { "name": "read from file", "summary": "Feeds a file into the command as its input." }
}
```

**Why JSON and not a Python dict in code:** the data stays separate from the logic, it's easy for non-programmers to edit, and it can be validated by a test. It still becomes a plain key-value `dict` in Python.

## 6. Initial command coverage (v1)

About 30 commands that ship with macOS/Linux or are built into the shell:

- **Navigation:** `cd`, `pwd`, `ls`
- **Files and folders:** `mkdir`, `rmdir`, `touch`, `cp`, `mv`, `rm`, `ln`
- **Reading files:** `cat`, `less`, `head`, `tail`, `wc`
- **Searching:** `grep`, `find`, `which`
- **Permissions:** `chmod`, `chown`, `sudo`
- **Processes:** `ps`, `kill`, `top`
- **Shell and session:** `echo`, `clear`, `history`, `man`, `alias`, `export`, `source`, `exit`
- **bash-only:** `shopt`
- **zsh-only:** `setopt`, `unsetopt`

## 7. Project structure

```
csc299-commandexplain-cli/
├── problem.md
├── SPEC.md
├── README.md
├── pyproject.toml           # entry point: `commandexplain`
├── commandexplain/
│   ├── __init__.py
│   ├── __main__.py          # allows `python -m commandexplain`
│   ├── cli.py               # prompts, input loop, yes/no handling
│   ├── parser.py            # split input into segments / operators / flags / args
│   ├── lookup.py            # load data, find command, fuzzy match
│   ├── shell.py             # detect shell from $SHELL
│   ├── formatter.py         # build the explanation text
│   ├── colors.py            # ANSI color helpers + on/off logic
│   └── data/
│       ├── commands.json
│       └── operators.json
└── tests/
    ├── test_parser.py
    ├── test_lookup.py
    ├── test_formatter.py
    ├── test_cli.py          # simulated input/output sessions
    └── test_data.py         # validates commands.json against §5
```

## 8. Technical requirements

- Python 3.10+.
- **Standard library only** at runtime (`json`, `difflib`, `shlex`, `os`, `sys`). No pip installs needed to run it.
- Command-line options: `--no-color` turns off colors, and `--shell bash|zsh` skips the shell question.
- `pytest` for tests (development dependency only).
- Run with `python -m commandexplain`, or `commandexplain` after `pip install -e .`.
- Input and output go through injectable functions (`input_fn`, `print_fn`) so the CLI can be tested without a real terminal.
- Lookup is O(1) dict access. Fuzzy matching only runs on a miss.

## 9. Error handling

| Situation | Behavior |
|---|---|
| `commands.json` missing or invalid JSON | Print a clear error and exit with code 1 (no traceback) |
| Ctrl+C / Ctrl+D at any prompt | Print "Goodbye!" and exit with code 0 |
| Unknown flag | Explain the known parts; for the unknown flag, suggest `man <cmd>` |
| Third-party tool (`git`, `npm`, and so on) | "'git' isn't a built-in terminal command, so it isn't covered." Uses a small list of known non-builtins, kept in the data |
| Real command outside §6 (`unset`, `unalias`, `pkill`, and so on) | "'unset' is a real command, but I don't cover it yet." Also on that list. Checked before spelling suggestions (ADR 0011) |

## 10. Acceptance criteria

1. On launch with `SHELL=/bin/zsh`, the program asks "Looks like you're using zsh. Is that right?". With `SHELL` unset, it asks for bash or zsh and won't continue until it gets a valid answer.
2. `ls` prints the summary and common flags for `ls`.
3. `rm -rf` explains `rm`, `-r`, and `-f`, and shows the warning.
4. `sl` prompts `Did you mean 'ls'? (yes/no)`. `yes` explains `ls`. `no` prints "Command not found. Please re-enter it." and prompts again.
5. `maybe` at the yes/no prompt re-asks instead of crashing.
6. `xyzzy` (no close match) prints the not-found message and prompts again.
7. `setopt` in bash mode warns that it's zsh-only and offers to explain it anyway.
8. `quit`, Ctrl+C, and Ctrl+D all exit cleanly. `exit` gets explained.
9. `ls -a | grep txt` explains `ls -a`, then the pipe, then `grep txt`. `grep "a|b" f` is treated as one command, not a pipe.
10. `sl | grep x` asks "Did you mean 'ls'?" before explaining the chain.
11. Output contains ANSI color codes in a terminal and none when piped (`python -m commandexplain | cat`), with `NO_COLOR` set, or with `--no-color`.
12. Every entry in `commands.json` and `operators.json` passes the schema test in §5.
13. All tests pass with `pytest`.

## 11. Implementation phases

Each phase ends with something that works and passes its tests, so the project is never half-broken between phases. Phases build on each other and are done in order.

### Phase 1 — Key-value data
**Goal:** all command knowledge exists as key-value pairs, loads into Python dicts, and is checked for mistakes. No user interaction yet.

Deliverables:
- `commandexplain/data/commands.json` with every command from §6, filled in using the fields in §5 (summary, flags, common_flags, example, warning, shells, and the optional ones where they apply).
- `commandexplain/data/operators.json` with the 7 operators from §5.1.
- `lookup.py`: `load_commands()` and `load_operators()` return `dict`s. A missing or broken file raises a clear error (see §9).
- `tests/test_data.py` checks that:
  - every entry has all required fields with the right types,
  - `shells` only contains `"bash"` or `"zsh"`,
  - every item in `common_flags` is a key in `flags`, and there are at most 5 of them,
  - aliases don't clash with real command names or with each other,
  - summaries are at most 2 sentences (to keep things simple for beginners).

Done when: acceptance criterion 12 passes. Opening Python and running `load_commands()["rm"]["flags"]["-r"]` returns the explanation.

### Phase 2 — Explain one command (no prompts)
**Goal:** turn a single command string into an explanation, using plain functions that are easy to test.

Deliverables:
- `parser.py`: splits one command into command / flags / arguments, including splitting `-rf` into `-r -f` and finding the command that `sudo` runs (§3.2 steps 3–7, without operators yet).
- `lookup.py`: `find_command(name)` with exact match, case-insensitive match, and alias lookup. `suggest(name)` returns the best match using the two-step rule in §4, or `None`.
- `formatter.py`: builds the explanation text as described in §3.3: typed flags or common flags, unknown flag message, warning, shell note, example. Plain text only.
- Tests for parser, lookup, and formatter.

Done when: `explain("rm -rf", shell="zsh")` returns the text required by acceptance criteria 2–3, and `suggest("sl")` returns `"ls"`.

### Phase 3 — Interactive CLI
**Goal:** the full program a user can run, for single commands.

Deliverables:
- `shell.py`: detect the shell from `$SHELL`, confirm it, fall back to the manual question (§3.1).
- `cli.py`: the main loop (§3), yes/no prompts, "Did you mean" flow (§4), shell-only commands (§3.4), quit / Ctrl+C / Ctrl+D / `exit` behavior (§3.5), and a "not covered" message for tools like `git` and uncovered builtins like `unset`. That check runs before spelling suggestions (§4, §9, ADR 0011).
- `__main__.py` and `pyproject.toml` so `python -m commandexplain` and `commandexplain` both work, plus the `--shell` option.
- `tests/test_cli.py` runs simulated sessions using `input_fn`/`print_fn`.

Done when: acceptance criteria 1–8 pass.

### Phase 4 — Pipes and chains
**Goal:** explain inputs that contain more than one command.

Deliverables:
- `parser.py` gains `shlex` tokenizing with `punctuation_chars=True` and splits input into segments at operators (§3.2 steps 1–2), plus the unclosed-quote and missing-side error messages.
- `formatter.py` gains chain output: commands and operators in order, plus the optional "In short" line (§3.3.1).
- `cli.py` runs spelling suggestions for each segment.
- Add `short` phrases to `commands.json` for the commands that should have them.

Done when: acceptance criteria 9–10 pass.

### Phase 5 — Colors and polish
**Goal:** make the output nicer to read and the project ready to hand in.

Deliverables:
- `colors.py` and color support in `formatter.py`/`cli.py` (§3.3.2), with `--no-color`, `NO_COLOR`, and turning colors off when output isn't a terminal.
- `README.md`: how to install, how to run, an example session, and how to add a new command to `commands.json`.
- A final pass over all explanations for wording and consistency.

Done when: acceptance criteria 11 and 13 pass, which means all criteria pass.

| Phase | Focus | Acceptance criteria |
|---|---|---|
| 1 | Key-value data | 12 |
| 2 | Explain one command | 2, 3 |
| 3 | Interactive CLI | 1–8 |
| 4 | Pipes and chains | 9, 10 |
| 5 | Colors and polish | 11, 13 |

## 12. Decisions

Each decision has an ADR in `docs/adr/` with the full reasoning.

| Question | Decision | ADR |
|---|---|---|
| Data format | JSON key-value files loaded into dicts (§5) | 0001 |
| Pipes and chains | Explain each command and operator (§3.3.1) | 0002 |
| Shell selection | Auto-detect from `$SHELL`, then confirm (§3.1) | 0003 |
| Explaining arguments | No. v1 covers commands and flags only | 0004 |
| Colors | Yes, ANSI, turned off automatically when not a terminal (§3.3.2) | 0005 |
| Spelling suggestions | One-edit check first, then difflib ≥ 0.75 (§4) | 0006 |
| Multi-letter flags (`-name`) | Match the whole token first, split only if unknown (§3.2) | 0007 |
| Common flags | Up to 5, only beginner-useful ones, may be empty (§3.3) | 0008 |
| Flag token details | Numbers stay whole, `--x=y` → `--x`, lone `-` and words after `--` are arguments (§3.2) | 0009 |
| Commands that run commands (`sudo`) | Stop at the inner command and explain it too (§3.2, §3.3) | 0010 |
| Suggestion limits | Letters only, and the "not covered" check comes before suggestions (§4, §9) | 0011 |
| Argument layout | One `argument: x` line each (§3.2) | 0012 |
| `sudo` with a shell builtin | Warn that it can't work, then explain the builtin (§3.3) | 0013 |
| Signal names (`kill -INT`) | `keep_flags_whole` data field; never split (§3.2) | 0014 |

## 13. Open questions

1. **Command list:** is the list in §6 the right size and scope? Anything to add or remove?
2. **Switching shells:** should there be a way to change shell mid-session (for example typing `shell`)?
