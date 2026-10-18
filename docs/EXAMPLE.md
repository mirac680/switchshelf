# A complete return-to-work loop

This example uses a cache task. The names and measurements are illustrative.

## 1. Pause with a contract

```console
switchshelf pause . --goal "Finish cache invalidation safely" --next "Inspect eviction at full capacity" --blocker "Need to confirm whether active entries can be evicted" --done-when "Boundary and error cases are documented and verified"
```

The checkpoint contains the handoff fields and the bounded project signals. It does not read source contents or run the project.

## 2. Return and inspect evidence

```console
switchshelf resume .
```

The report shows the saved contract next to current Git state and metadata changes. File changes are based on paths, size, and modification time; no diff is generated.

## 3. Carry context to another assistant

```console
switchshelf prompt . --export handoff.md
```

The resulting Markdown separates human-authored intent from observed signals and tells the receiving assistant to verify them against its current environment. Review it before sharing: it includes filenames and your handoff text.

## 4. Learn from your own return experience

After taking the first meaningful action:

```console
switchshelf reflect . --minutes 7 --friction 2
switchshelf insights
```

An illustrative reflection record looks like this:

```json
{"schema_version":1,"reflected_at":"2026-10-18T12:30:00+00:00","minutes":7,"friction":2,"handoff_signals":3}
```

The record deliberately contains no project name, project fingerprint, checkpoint ID, note, file path, or source content. Insights only compare complete and partial handoffs after there are at least five observations in each group. The comparison is observational and does not claim that the handoff caused the difference.
