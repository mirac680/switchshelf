# Design notes

## Workflow

SwitchShelf supports an explicit continuity cycle:

1. pause scans a project and stores a new checkpoint.
2. resume scans again and compares with that saved checkpoint without changing it.
3. A later pause establishes the next comparison point.
4. prompt produces a model-agnostic brief that separates human intent from observed project signals.
5. reflect optionally records the user's return-time and friction self-report; insights summarizes the local measurements without identifying projects.
6. last displays the saved checkpoint without scanning.
7. forget --yes removes the local record for a project.
8. queue lists saved checkpoints across projects without scanning repositories. A short fingerprint prefix distinguishes duplicate project labels and permits cleanup after a folder has moved.

When the supplied directory is inside a Git repository, SwitchShelf discovers the repository root and scans from there. A non-Git directory is scanned as supplied.

## Comparison

File inventory deltas use relative path, file size, and modification time. File contents are not hashed or compared. This avoids storing content-derived fingerprints, but it can produce a false positive when a timestamp changes without content changes, or miss a change if both size and timestamp are preserved.

Git branch and HEAD identifiers are compared separately. When the branch is unchanged, recent commit references between saved and current HEAD can be listed. Git status records indicate newly dirty, cleared, and status-changed paths.

Task marker deltas compare a relative path, line number, and marker tuple. Moving a marker to a different line is reported as one resolved and one new marker.

## Boundaries

- Git commands run with shell=False, a timeout, optional Git index writes disabled, prompts disabled, and the optional filesystem monitor disabled.
- No hooks, tests, build commands, package scripts, or project entry points are intentionally invoked.
- Symbolic links are skipped and resolved files must remain inside the project root.
- Text scanning is limited to selected source/documentation extensions, 512 KiB per file, 12 MiB total, and at most 300 marker records.
- The file inventory is capped at 20,000 entries. The default is 10,000.
- At most 1,000 Git working-tree paths are retained in a checkpoint.
- Reflection measurements contain no project identity and are written only after an explicit user command.
- Checkpoint schema version 2 reads version 1 records with empty values for newly added handoff fields.
- Unsupported versions fail with an error instead of being guessed or silently rewritten.
- JSON and Markdown outputs are written through temporary files and atomic replacement.

## Package layout

- cli.py parses commands and coordinates the workflow.
- scanner.py creates a bounded metadata inventory and finds task markers.
- git.py invokes the limited read-only Git command set.
- models.py defines the snapshot data shape and validates stored JSON.
- delta.py compares snapshots.
- state.py chooses the per-user store and performs atomic checkpoint writes.
- report.py renders a portable Markdown summary.
- reflections.py stores opt-in, project-agnostic return measurements and summarizes them without causal claims.
- privacy.py centralizes path filtering and output escaping.
