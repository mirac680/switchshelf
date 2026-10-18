# SwitchShelf

**SwitchShelf** is a local-first Python work-continuity tool built to reduce the hidden cost of switching projects. Capture a goal, the next concrete action, a blocker, and a visible completion condition. On return, review what changed and turn the same evidence into a portable briefing for any AI assistant.

SwitchShelf does not copy source code, store diff contents, or run project commands. It gives your future self a compact, privacy-conscious answer to “where was I?”

**The difference:** SwitchShelf does not watch agent conversations or activity. It separates a human-authored continuation contract from repository signals; if you choose, you can also record how long it took you to get moving again. Over time, see whether your handoff habits are working for you.

See the [worked example](docs/EXAMPLE.md) for the full flow and a sample reflection record.

## Why SwitchShelf?

Git records code history, but it rarely captures the unfinished thought behind a work session or tells you what changed while you were away. SwitchShelf adds a small local checkpoint for that gap:

- Save an optional note before switching tasks.
- List pending work across repositories in one local queue.
- Create a handoff contract with a goal, next action, blocker, and done condition.
- Generate a model-agnostic continuation brief that separates your notes from observed signals.
- Optionally record return time and perceived friction, then compare your own handoff results.
- Compare a file inventory with the previous checkpoint.
- Summarize branch, commit ID, working tree, and recent commit dates.
- Record only the path, line number, and tag for TODO, FIXME, HACK, and BUG markers.
- Store no source text, diff content, commit messages, or remote Git URLs.
- Work offline with no runtime dependencies.

## Quick start

Install Python 3.11 or newer and change to the project directory. In Windows PowerShell, run without installing the package:

    $env:PYTHONPATH = "$PWD\src"
    python -m switchshelf --help

This setting lasts only for the current PowerShell window. To install the console command, use a Python distribution that includes `pip`:

    python -m pip install .

On macOS/Linux, the interpreter is commonly named `python3`:

    python3 -m pip install .

Then use the commands:

    python -m switchshelf pause . --goal "Finish cache invalidation safely" --next "Inspect eviction at full capacity" --done-when "Boundary and error cases are documented and verified"
    python -m switchshelf resume .
    python -m switchshelf last .
    python -m switchshelf queue
    python -m switchshelf prompt . --export handoff.md

If the console command is not available, invoke the package as a module:

    python -m switchshelf pause . --note "Next: inspect the error path."
    python -m switchshelf resume .

To invoke the module without installation, set `PYTHONPATH` first and use `python -m switchshelf`. After installing with `pip`, you can instead call `switchshelf` directly.

No checkpoint is created until you run `pause` for the first time.

## Commands

### Save a checkpoint

    switchshelf pause C:\work\my-project --goal "Finish the cache API safely" --next "Inspect full-capacity eviction" --blocker "None" --done-when "Boundary and error cases are documented and verified"

The project inventory is saved in your local user data directory. A new checkpoint replaces the previous one. All four contract fields are optional; goal, next action, and done condition make the most useful continuation brief.

### Resume later

    switchshelf resume C:\work\my-project

Resume does not update the checkpoint, so you can run it again and compare against the same starting point. Run `pause` when you want a new baseline.

### Show the last checkpoint without scanning

    switchshelf last C:\work\my-project

### Queue paused projects

    switchshelf queue

This lists local checkpoints from newest to oldest, with project name, branch, last recorded dirty-path count, number of handoff fields filled in, and the next action (or a short note when no next action is set). Add `--export FILE` to write a Markdown queue report.

The short ID in the queue helps identify a checkpoint if its folder has moved or multiple projects share a name.

### Give any AI assistant a continuation brief

    switchshelf prompt C:\work\my-project --export handoff.md

The brief separates your goal and next action from observed branch, changed path names, and task markers. It contains no source or diff contents. Review the portable Markdown and paste it into the assistant you choose. It asks the assistant to verify observed signals against its current environment.

### Measure the cost of switching context

After returning and taking your first meaningful action, record how long that took and how difficult it felt:

    switchshelf reflect C:\work\my-project --minutes 7 --friction 2
    switchshelf insights

This is entirely optional. SwitchShelf never starts a timer or watches your activity. `insights` compares complete and partial handoffs only after enough personal observations, and labels the result as observational rather than causal. Reflection records contain no project name, note, file path, or source content.

### Delete the local checkpoint

    switchshelf forget C:\work\my-project --yes
    switchshelf forget --id a1b2c3d4 --yes

Either form removes only SwitchShelf's local record for the selected project and requires the confirmation flag.

### Export a Markdown report

    switchshelf resume . --export return-report.md

Existing report files are protected from accidental replacement. Add `--overwrite` when you deliberately want to replace one.

### Exclude paths

    switchshelf pause . --exclude "fixtures/**" --exclude "customer-data/*"

Patterns are matched relative to the project root. Git’s standard ignore rules are honored in Git repositories. Outside Git, common build/cache directories and sensitive names are skipped; add more patterns with `--exclude`.

### Choose a local state directory

    switchshelf pause . --state-dir D:\private\switchshelf-state
    switchshelf resume . --state-dir D:\private\switchshelf-state

Use the same state directory for `pause`, `resume`, `last`, `queue`, `forget`, `prompt`, `reflect`, and `insights`.

### Bound larger scans

    switchshelf pause . --max-files 5000 --max-todos 40

The inventory is capped at 20,000 files and 300 task markers. Narrow large repositories with `--exclude`.

## Local data

Checkpoint JSON is stored in a per-user state directory:

- Windows: `%LOCALAPPDATA%\SwitchShelf`
- macOS: `~/Library/Application Support/SwitchShelf`
- Linux: `$XDG_STATE_HOME/switchshelf` or `~/.local/state/switchshelf`

A checkpoint may contain the project name, relative paths, file size and modification time, common project landmark names, language counts, task-marker locations, Git branch/commit/working-tree paths, your note, and the handoff fields you supplied. The optional yearly reflection log contains timestamps, self-reported minutes/friction, and a handoff-field count; it does not identify which project was resumed.

The inventory keeps file names and metadata for comparison. It does not contain source text, but it can still reveal details about a private project. Review exported reports before sharing them.

## Privacy and safety boundaries

- Source contents, Git diff contents, commit messages, and remote URLs are not written to reports or checkpoints.
- TODO scanning reads eligible text files in memory. Only the marker name, relative path, and line number are retained; the surrounding comment is discarded.
- Common environment files, private-key extensions, credential-like names, and generated/cache directories are omitted by name-based rules. This heuristic cannot identify every custom sensitive filename.
- Relative paths, branch names, and your note may contain sensitive details. Review before sharing.
- `prompt` sends nothing to an external service on its own; if you paste the generated Markdown elsewhere, that service receives the brief.
- `reflect` writes only when you run it; it stores no project name, note, path, or source content. Reflection records are unencrypted local data.
- Symbolic links are not followed. Git is invoked with `shell=False` and read-only commands.
- Project test, build, install, and run commands are never executed.
- File changes are inferred from size and modification time; content is not hashed. A content change that preserves both values may be missed. Git commit IDs are compared separately.
- No network requests are made; runtime uses only the Python standard library.

## License

MIT. See `LICENSE`.
