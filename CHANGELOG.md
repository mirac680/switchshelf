# Changelog

## 2.0.0 — 2026-10-18

- Add a structured re-entry contract: goal, next action, blocker, and done condition.
- Generate a portable, model-agnostic continuation prompt with clearly labelled observed signals.
- Add optional self-reported return-time and friction measurements, with local aggregate insights.
- Compare complete and partial handoffs only when both groups have enough personal observations; label the result as observational.
- Keep reflection records free of project names, notes, file paths, source content, and network activity.
- Read existing schema version 1 checkpoints and migrate them forward when next saved.

## 1.0.0 — 2026-10-14

- Add local project pause and resume checkpoints.
- Add a cross-project queue for saved pause notes and working-tree context.
- Compare project inventories, Git metadata, and task-marker locations.
- Add Markdown report export and configurable path exclusions.
- Add an explicit confirmation command to remove a project's local checkpoint.
- Keep report data privacy-conscious and dependency-free.
