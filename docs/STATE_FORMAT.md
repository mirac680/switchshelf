# Checkpoint format

The current state format uses schema version 2. Each project has one JSON checkpoint named with a truncated hash of its normalized root path. A new pause operation atomically replaces the previous checkpoint for that project. Readers accept version 1 and fill the new handoff fields with empty values; the next save writes version 2.

Top-level fields:

- schema_version: integer format version.
- captured_at: ISO 8601 UTC timestamp.
- project_id: stable path-derived project fingerprint.
- project_name: root directory label only.
- project_kind: detected manifest families.
- note: optional user-authored pause note.
- goal, next_step, blocker, done_when: optional user-authored re-entry contract fields, each limited to 1,000 characters.
- git: branch, HEAD, safe status paths, and short recent commit references.
- languages: extension-derived file counts.
- important_files: relative paths to common project manifests and guides.
- files: relative path to size and modification-time metadata.
- todos: marker kind, relative path, and line number.
- total_files and total_bytes: inventory totals at capture time.
- truncated: whether the configured file limit was reached.
- skipped_sensitive and skipped_unreadable: scan counters.

The state reader bounds file, marker, and Git path counts. It rejects unsupported schema versions and mismatched project fingerprints. Optional reflection measurements are appended to a separate yearly JSON Lines file. Each record contains a reflection timestamp, self-reported minutes and friction, and a 0–3 handoff-signal count. It contains no project name or fingerprint, checkpoint identifier, note, path, or source content. A future incompatible format must use a new schema version and an explicit migration.
