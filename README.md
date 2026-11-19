# CommandExplain

A friendly command-line program that explains bash and zsh terminal commands in plain, simple language. Type a command like `rm -rf old` or `ls -a | grep txt`, and it tells you what each part does, warns you about anything dangerous, and points out where bash and zsh behave differently.

It's built for people who are new to the terminal.

## Install

You need **Python 3.10 or newer**. The program has no other requirements.

```bash
git clone https://github.com/anasp07-hue/csc299-commandexplainer.git
cd csc299-commandexplainer
python3 -m venv .venv          # a private Python just for this project
source .venv/bin/activate      # turn it on (do this again in each new terminal)
pip install -e .
```

The virtual environment (`.venv`) matters on some setups, such as Homebrew's Python, which refuse to install packages without one.

## Run

```bash
commandexplain
```

Or, without installing:

```bash
python3 -m commandexplain
```

Options:

| Option | What it does |
|---|---|
| `--shell bash` / `--shell zsh` | Skip the "which shell?" question |
| `--no-color` | Turn off colors (they also turn off when output isn't a terminal or `NO_COLOR` is set) |

While it's running:

- Type any command to have it explained.
- Type `shell` (or `shell bash`) to switch shells.
- Type `quit` or `q`, or press Ctrl+C or Ctrl+D, to leave.

## Example

```text
Looks like you're using zsh. Is that right? (yes/no) yes
Using zsh. (Type "shell" any time to switch.)
Enter a command to explain (or 'quit' to leave): rm -rf old
rm  —  remove
  Deletes files. They do not go to the Trash.

  -r   Delete folders and everything inside them.
  -f   Force: don't ask before deleting, and don't complain if a file doesn't
       exist.

  argument: old

  ⚠ Careful: This deletes files permanently. There is no undo.
  Note for zsh: zsh asks you to confirm before running rm with * (everything in
    a folder). bash does not ask.

  Example:  rm notes.txt

Enter a command to explain (or 'quit' to leave): sl -a | grep txt
Did you mean 'ls'? (yes/no) yes
ls -a
  ls — list: Shows the files and folders in the current folder.
    -a   Also show hidden files (the ones whose names start with a dot).

|  (pipe)
  Takes the output of the left command (what it would show on screen) and feeds
  it into the right command.

grep txt
  grep — search text: Searches for text inside files and shows the lines that
    match.
    argument: txt

In short: list files, then pass the output to find matching lines.

Enter a command to explain (or 'quit' to leave): quit
Goodbye!
```

## What it covers

- **35 commands** that come with macOS and Linux or are built into the shell: `cd`, `ls`, `cp`, `mv`, `rm`, `grep`, `find`, `chmod`, `sudo`, `kill`, and more. See `SPEC.md` §6 for the full list.
- **Flags**, including grouped ones (`-rf` is `-r` and `-f`) and word flags like `find -name`.
- **`sudo`**: it explains the command that sudo runs, too, and warns when sudo can't run something (`sudo cd`).
- **Pipes, chains, and redirects**: `|`, `&&`, `||`, `;`, `>`, `>>`, and `<`.
- **Typos**: `sl` → "Did you mean 'ls'?", even after `sudo` and inside chains.
- **Honest limits**:
  - Tools like `git` or `brew` get "not covered".
  - Real commands that aren't explained yet (`sort`, `curl`) get "I don't cover it yet".
  - Advanced syntax (`2>&1`, `&`, `$(...)`) gets "I can't explain that yet" instead of a wrong answer.

## Adding a command

All command knowledge lives in JSON files in `commandexplain/data/`. Adding a command means adding data, not code.

1. Add an entry to `commands.json`. The key is the command name:

   ```json
   "sort": {
     "name": "sort lines",
     "short": "sort lines",
     "summary": "Puts the lines of a file in order, like A to Z.",
     "shells": ["bash", "zsh"],
     "flags": {
       "-r": "Sort in reverse order (Z to A).",
       "-n": "Sort by number, so 10 comes after 9."
     },
     "common_flags": ["-r", "-n"],
     "example": "sort names.txt",
     "warning": null,
     "shell_notes": {},
     "aliases": []
   }
   ```

   - `summary`: 1–2 short sentences, written for someone who has never used a terminal.
   - `short`: a 2–4 word phrase used in the "In short" line of chains.
   - `common_flags`: up to 5 flags beginners actually use.
   - `SPEC.md` §5 lists every field, including the optional ones: `warning`, `shell_notes`, `aliases`, `runs_command`, `flags_with_values`, `builtin_only`, and `keep_flags_whole`.

2. If the command is on the "not covered" list in `not_covered.json`, remove it from there. A name can't be in both files.

3. Run the tests. The data tests check every entry for missing fields, wrong types, long summaries, and similar mistakes:

   ```bash
   pytest
   ```

## Development

```bash
pip install -e ".[dev]"   # installs pytest
pytest                    # runs the full test suite
```

The project layout:

```text
commandexplain/
  cli.py         interactive loop, prompts, "Did you mean", quitting
  shell.py       detects and asks for bash or zsh
  parser.py      splits input into commands, operators, flags, and arguments
  lookup.py      loads the data, finds commands, suggests spellings
  formatter.py   builds the explanation text
  colors.py      colors and when to turn them off
  data/          commands.json, operators.json, not_covered.json
tests/           one test file per module, plus the data checks
docs/
  adr/           design decisions (why things work the way they do)
  handoffs/      notes at the end of each build phase
  reviews/       code reviews for each phase
SPEC.md          the full specification
```
