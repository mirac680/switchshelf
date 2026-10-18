# Privacy model

SwitchShelf is a local utility. It has no network client, telemetry, remote service, or runtime dependency.

## What is stored

The latest checkpoint is a JSON file under the current user's SwitchShelf state directory. The default path varies by operating system; see the main README.

| Field | Stored value |
| --- | --- |
| Project identity | A 96-bit prefix of SHA-256 over the normalized absolute project root. The path itself is not stored. |
| Project label | The root directory's final name. |
| File inventory | Relative path, byte size, and modification timestamp for up to the configured file limit. |
| Git | Branch name, full HEAD identifier, up to 1,000 changed paths, and recent short commit IDs/dates. Remote URLs and commit messages are omitted. |
| Task markers | Marker kind, relative file path, and line number. Text surrounding the marker is discarded. |
| User note | The exact note supplied to the pause command, up to 2,000 characters. |
| Re-entry contract | Optional goal, next step, blocker, and done condition supplied by the user (up to 1,000 characters each). |

Checkpoint writes use a temporary file and atomic replacement. On POSIX systems, file permissions are set to owner read/write where supported. On Windows, the checkpoint relies on the ACLs of the per-user application data directory. The checkpoint is not encrypted.

The project fingerprint is stable for the same resolved path, so checkpoints can be found again. The queue displays its first eight hexadecimal characters to distinguish projects with matching folder names. It is not an authentication secret and should not be treated as one.

## What is not stored

SwitchShelf does not persist:

- source or documentation contents;
- Git diff contents or commit subjects;
- Git remotes or credentials;
- command history, environment variables, or process output;
- absolute project paths.

TODO scanning temporarily reads selected text files in memory, then retains only a marker kind, path, and line number.

The optional `reflect` command records a user-entered return time (0–1,440 minutes), a friction rating (1–5), a timestamp, and a count of three handoff fields. It deliberately does not store a project name, project fingerprint, checkpoint identifier, note, or file path, so insights aggregate across all projects. The yearly JSON Lines log contains no source content or automatically collected behavior. Delete `reflections-YYYY.jsonl` in the state directory to remove a year's reflections.

## Path filters

The scanner omits common generated directories and name patterns associated with credentials, private keys, environment files, SSH/Kubernetes configuration, cloud-provider configuration, and Terraform state. Git repositories use Git's standard ignore rules for untracked files. Additional relative path globs can be passed with --exclude.

These are heuristics. New credential formats and custom filenames can evade name-based detection. File and directory names, branch names, and notes may reveal project details even when source contents are absent. Review every exported report before sharing it.

## Deletion

Run the following command to remove one project's saved checkpoint:

    switchshelf forget C:\work\my-project --yes

This deletes only that project's SwitchShelf JSON record. It does not change the project directory or Git repository.
