from __future__ import annotations

import html
import re
from collections import Counter
from pathlib import PurePosixPath

from .delta import Delta
from .models import Snapshot
from .privacy import markdown_path


MAX_RENDERED_PATHS = 100
MAX_RENDERED_TODOS = 80
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def _inline(value: object) -> str:
    text = _CONTROL_CHARS.sub(" ", str(value))
    text = html.escape(text, quote=False).replace("|", "&#124;")
    for char in ("\\", chr(96), "*", "_", "{", "}", "[", "]", "(", ")", "#", "+", "-", ".", "!"):
        text = text.replace(char, "\\" + char)
    return text


def _code(value: object) -> str:
    text = _CONTROL_CHARS.sub(" ", str(value))
    text = html.escape(text, quote=False).replace("|", "&#124;").replace(chr(96), "_")
    tick = chr(96)
    return f"{tick}{text}{tick}"


def _path(value: str) -> str:
    safe = markdown_path(value)
    return _code(safe)


def _size(value: int) -> str:
    if value < 1024:
        return f"{value} B"
    if value < 1024**2:
        return f"{value / 1024:.1f} KiB"
    if value < 1024**3:
        return f"{value / 1024**2:.1f} MiB"
    return f"{value / 1024**3:.2f} GiB"


def _list_paths(title: str, paths: list[str], limit: int = MAX_RENDERED_PATHS) -> list[str]:
    if not paths:
        return [f"- {title}: none"]
    lines = [f"- {title} ({len(paths)}):"]
    lines.extend(f"  - {_path(path)}" for path in paths[:limit])
    if len(paths) > limit:
        lines.append(f"  - ... and {len(paths) - limit} more")
    return lines


def _todo_rows(
    title: str,
    items: list[tuple[str, int, str]],
    limit: int = MAX_RENDERED_TODOS,
) -> list[str]:
    if not items:
        return [f"- {title}: none"]
    lines = [f"- {title} ({len(items)}):"]
    for path, line, marker in items[:limit]:
        lines.append(f"  - {_path(path)}:{line} [{_inline(marker)}]")
    if len(items) > limit:
        lines.append(f"  - ... and {len(items) - limit} more")
    return lines


def _main_areas(snapshot: Snapshot) -> list[str]:
    counts: Counter[str] = Counter()
    for path in snapshot.files:
        parts = PurePosixPath(path).parts
        area = parts[0] if len(parts) > 1 else "(root files)"
        counts[area] += 1
    if not counts:
        return ["- No paths were recorded."]
    lines = [f"- {_path(name)}: {count} file(s)" for name, count in counts.most_common(30)]
    if len(counts) > 30:
        lines.append(f"- ... and {len(counts) - 30} more top-level areas")
    return lines


def render_markdown(
    snapshot: Snapshot,
    *,
    previous: Snapshot | None = None,
    delta: Delta | None = None,
    view: str = "pause",
) -> str:
    lines = [
        f"# SwitchShelf — {_inline(snapshot.project_name)}",
        "",
        f"- Captured: {_inline(snapshot.captured_at)} (UTC)",
        f"- Project type: {_inline(snapshot.project_kind)}",
        f"- Inventory: {snapshot.total_files:,} files, {_size(snapshot.total_bytes)}",
    ]
    if snapshot.truncated:
        lines.append("- Inventory reached the configured file limit; the counts are partial.")

    if snapshot.git.is_repo:
        branch = snapshot.git.branch or "detached HEAD"
        head = snapshot.git.head or "unavailable"
        dirty_count = snapshot.git.dirty_count or len(snapshot.git.dirty)
        dirty_summary = (
            "unavailable"
            if snapshot.git.read_error
            else f"{dirty_count} changed path(s)"
        )
        lines.extend(
            [
                f"- Git branch: {_code(branch)}",
                f"- Git commit: {_code(head[:12])}",
                f"- Working tree: {dirty_summary}",
            ]
        )
    else:
        lines.append("- Git: no repository detected")

    if snapshot.note:
        lines.extend(["", "## Last note", ""])
        for note_line in snapshot.note.splitlines() or [snapshot.note]:
            lines.append(f"> {_inline(note_line)}")
    elif view == "pause":
        lines.extend(["", "## Last note", "", "No note was attached to this checkpoint."])

    handoff_fields = (
        ("Goal", snapshot.goal),
        ("Next action", snapshot.next_step),
        ("Blocker", snapshot.blocker),
        ("Done when", snapshot.done_when),
    )
    if any(value for _, value in handoff_fields) or view == "pause":
        core_count = sum(
            bool(value.strip())
            for label, value in handoff_fields
            if label != "Blocker"
        )
        lines.extend(["", "## Re-entry contract", ""])
        lines.append(
            f"Core handoff signals: **{core_count}/3** "
            "(goal, next action, done condition)."
        )
        for label, value in handoff_fields:
            if value:
                lines.append(f"- **{label}:** {_inline(value)}")
            elif view == "pause":
                lines.append(f"- **{label}:** not recorded")

    if previous is not None and delta is not None:
        lines.extend(["", "## Since the previous checkpoint", ""])
        lines.append(f"- Previous checkpoint: {_inline(previous.captured_at)} (UTC)")
        if delta.branch_changed:
            lines.append(
                f"- Branch changed: {_code(previous.git.branch or 'unknown')} → "
                f"{_code(snapshot.git.branch or 'unknown')}"
            )
        if delta.head_changed:
            lines.append(
                f"- Git commit changed: {_code((previous.git.head or 'unknown')[:12])} → "
                f"{_code((snapshot.git.head or 'unknown')[:12])}"
            )

        lines.extend(_list_paths("Added files", delta.added_files))
        lines.extend(_list_paths("Removed files", delta.removed_files))
        lines.extend(_list_paths("Modified files by size or timestamp", delta.modified_files))
        lines.extend(_list_paths("New working tree paths", delta.new_worktree_paths))
        lines.extend(_list_paths("Paths no longer marked dirty", delta.cleared_worktree_paths))
        lines.extend(_list_paths("Working tree status changed", delta.changed_worktree_paths))
        lines.extend(_todo_rows("New task markers", delta.new_todos))
        lines.extend(_todo_rows("Resolved or moved task markers", delta.resolved_todos))

        if delta.commits_since:
            lines.append(f"- Commits since checkpoint ({len(delta.commits_since)}):")
            for commit in delta.commits_since[:30]:
                lines.append(
                    f"  - {_code(commit.short_hash)} ({_inline(commit.date)})"
                )
        if not delta.has_changes:
            lines.append("- No detectable changes since the previous checkpoint.")
        if delta.inventory_incomplete:
            lines.append(
                "- One or both file inventories reached their limit; path deltas may be incomplete."
            )
        if delta.working_tree_incomplete:
            lines.append(
                "- A Git working-tree read failed or a path list reached 1,000 entries; "
                "Git path deltas may be incomplete."
            )
        lines.append(
            "- File modifications are inferred from file size and modification time; "
            "source contents are not compared."
        )
    elif view == "resume":
        lines.extend(
            [
                "",
                "## Since the previous checkpoint",
                "",
                "No checkpoint exists for this project yet. Run switchshelf pause to create one.",
            ]
        )
    elif view == "pause":
        lines.extend(
            [
                "",
                "## Since the previous checkpoint",
                "",
                "This is the first checkpoint for this project.",
            ]
        )
    else:
        lines.extend(["", "## Checkpoint", "", "This is the most recently saved checkpoint."])

    lines.extend(["", "## Languages and file types", ""])
    if snapshot.languages:
        for language, count in list(snapshot.languages.items())[:12]:
            lines.append(f"- {_inline(language)}: {count}")
    else:
        lines.append("- No recognized source or documentation file types.")

    lines.extend(["", "## Project landmarks", ""])
    if snapshot.important_files:
        lines.extend(f"- {_path(path)}" for path in snapshot.important_files[:80])
        if len(snapshot.important_files) > 80:
            lines.append(f"- ... and {len(snapshot.important_files) - 80} more")
    else:
        lines.append("- No common project manifests or guide files were found.")

    lines.extend(["", "## Main areas", ""])
    lines.extend(_main_areas(snapshot))

    lines.extend(["", "## Task markers", ""])
    if snapshot.todos:
        for item in snapshot.todos[:MAX_RENDERED_TODOS]:
            lines.append(f"- {_path(item.path)}:{item.line} [{_inline(item.marker)}]")
        if len(snapshot.todos) > MAX_RENDERED_TODOS:
            lines.append(f"- ... and {len(snapshot.todos) - MAX_RENDERED_TODOS} more")
    else:
        lines.append("- No TODO, FIXME, HACK, or BUG markers were found in scanned text files.")

    if snapshot.git.is_repo:
        lines.extend(["", "## Current working tree", ""])
        if snapshot.git.dirty:
            for change in snapshot.git.dirty[:80]:
                lines.append(f"- {_code(change.status)} {_path(change.path)}")
            if len(snapshot.git.dirty) > 80:
                lines.append(f"- ... and {len(snapshot.git.dirty) - 80} more")
            if snapshot.git.dirty_truncated:
                lines.append("- Dirty-path list was capped at 1,000 entries.")
        elif snapshot.git.read_error:
            lines.append("- Status unavailable")
        else:
            lines.append("- Clean")
        if snapshot.git.read_error:
            lines.append(f"- Git status note: {_inline(snapshot.git.read_error)}")

        if snapshot.git.recent_commits:
            lines.extend(["", "## Recent commit references", ""])
            for commit in snapshot.git.recent_commits[:8]:
                lines.append(
                    f"- {_code(commit.short_hash)} ({_inline(commit.date)})"
                )

    lines.extend(
        [
            "",
            "## Privacy notes",
            "",
            "- No source-file contents, diff contents, commit messages, or Git remote URLs are stored.",
            "- TODO entries contain only a marker, relative path, and line number; "
            "comment text is discarded.",
            f"- At least {snapshot.skipped_sensitive} file path(s) matched sensitive-name "
            "rules and were omitted; generated directories are excluded separately.",
            f"- {snapshot.skipped_unreadable} file or directory read(s) were skipped.",
            "- Relative names, branch names, and your note can still reveal project details; "
            "review before sharing.",
            "",
            "_SwitchShelf is a local-first checkpoint aid. It does not execute project commands._",
            "",
        ]
    )
    if view == "resume":
        lines.extend(
            [
                "",
                "After your first meaningful action, you can optionally record your return "
                "time with `switchshelf reflect . --minutes N --friction 1..5`.",
                "",
            ]
        )
    return "\n".join(lines)


def render_agent_prompt(
    snapshot: Snapshot,
    *,
    previous: Snapshot | None = None,
    delta: Delta | None = None,
) -> str:
    """Create a portable, evidence-labelled continuation prompt for any agent."""
    source = previous or snapshot
    lines = [
        f"# Continue work: {_inline(snapshot.project_name)}",
        "",
        "You are joining an existing project. Treat this brief as a starting point, "
        "not proof of the current filesystem state.",
        "Verify relevant paths and Git state before relying on them. Do not claim that "
        "you ran commands or inspected source files unless you actually did so.",
        "",
        "## Human-authored handoff",
        "",
        f"- Goal: {_inline(source.goal) if source.goal else 'not recorded'}",
        f"- Next action: {_inline(source.next_step) if source.next_step else 'not recorded'}",
        f"- Blocker: {_inline(source.blocker) if source.blocker else 'not recorded'}",
        f"- Done when: {_inline(source.done_when) if source.done_when else 'not recorded'}",
        f"- Free-form note: {_inline(source.note) if source.note else 'not recorded'}",
        "",
        "## Latest observed project signals",
        "",
        f"- Snapshot time: {_inline(snapshot.captured_at)} UTC.",
        f"- Project type: {_inline(snapshot.project_kind)}; "
        f"{snapshot.total_files:,} indexed file(s), {_size(snapshot.total_bytes)}.",
    ]
    if snapshot.git.is_repo:
        lines.extend(
            [
                f"- Git branch: {_inline(snapshot.git.branch or 'detached HEAD')}.",
                f"- Git HEAD: {_code((snapshot.git.head or 'unavailable')[:12])}.",
            ]
        )
        if snapshot.git.read_error:
            lines.append("- Working tree status was unavailable during this scan.")
        else:
            count = snapshot.git.dirty_count or len(snapshot.git.dirty)
            lines.append(f"- Working tree: {count} changed path(s).")
    else:
        lines.append("- No Git repository was detected.")

    if delta is not None:
        lines.extend(["", "## Changes since the saved checkpoint", ""])
        lines.extend(_list_paths("Added paths", delta.added_files, limit=30))
        lines.extend(_list_paths("Removed paths", delta.removed_files, limit=30))
        lines.extend(_list_paths("Modified paths by metadata", delta.modified_files, limit=30))
        lines.extend(_list_paths("New working-tree paths", delta.new_worktree_paths, limit=30))
        lines.extend(_list_paths("Cleared working-tree paths", delta.cleared_worktree_paths, limit=30))
        lines.extend(_list_paths("Working-tree status changes", delta.changed_worktree_paths, limit=30))
        lines.extend(_todo_rows("New task markers", delta.new_todos, limit=30))
        lines.extend(_todo_rows("Resolved or moved task markers", delta.resolved_todos, limit=30))
        if delta.branch_changed:
            lines.append("- Git branch changed since the saved checkpoint.")
        if delta.head_changed:
            lines.append("- Git HEAD changed since the saved checkpoint.")
        if delta.inventory_incomplete:
            lines.append("- The file comparison is partial because a scan reached its file limit.")
        if delta.working_tree_incomplete:
            lines.append("- Git working-tree status could not be compared completely.")
    else:
        lines.extend(["", "No previous checkpoint was available for a before/after comparison."])

    lines.extend(["", "## Nearby task markers", ""])
    if snapshot.todos:
        lines.extend(
            _todo_rows(
                "TODO, FIXME, HACK, and BUG locations",
                [(item.path, item.line, item.marker) for item in snapshot.todos],
                limit=30,
            )
        )
    else:
        lines.append("No task markers were recorded in the scanned text files.")

    lines.extend(
        [
            "",
            "## Working agreement",
            "",
            "Start by checking the stated next action against the current project. If it is "
            "missing or stale, explain the smallest useful discovery step and ask only for "
            "information that cannot be inferred safely. Keep changes within the stated goal "
            "and summarize evidence when finished.",
            "",
            "This brief contains filenames and human-authored notes. Review it before "
            "pasting into an external service.",
            "",
        ]
    )
    return "\n".join(lines)


def render_queue(snapshots: list[Snapshot], skipped: int, truncated: bool) -> str:
    lines = [
        "# SwitchShelf — Paused project queue",
        "",
        f"{len(snapshots)} saved project checkpoint(s).",
        "",
        "| Last paused (UTC) | Project | ID | Branch | Dirty paths | Handoff | Next action / note |",
        "| --- | --- | --- | --- | ---: | ---: | --- |",
    ]
    if not snapshots:
        lines.append("| — | — | — | — | — | — | No saved checkpoints. |")
    else:
        for snapshot in snapshots:
            branch = snapshot.git.branch if snapshot.git.is_repo else "—"
            if not snapshot.git.is_repo:
                dirty_count = "—"
            elif snapshot.git.read_error:
                dirty_count = "?"
            else:
                dirty_count = str(snapshot.git.dirty_count or len(snapshot.git.dirty))
            next_context = snapshot.next_step.strip() or snapshot.note.strip()
            note = next_context.replace("\r", " ").replace("\n", " ")
            note = _inline(note[:160] + ("…" if len(note) > 160 else "")) or "—"
            handoff_count = sum(
                bool(value.strip())
                for value in (snapshot.goal, snapshot.next_step, snapshot.done_when)
            )
            lines.append(
                "| "
                + " | ".join(
                    (
                        _inline(snapshot.captured_at),
                        _inline(snapshot.project_name),
                        _inline(snapshot.project_id[:8]),
                        _inline(branch or "—"),
                        dirty_count,
                        f"{handoff_count}/3",
                        note,
                    )
                )
                + " |"
            )
    if truncated:
        lines.extend(["", "More checkpoints exist than the requested queue limit; output is partial."])
    if skipped:
        lines.extend(
            ["", f"{skipped} unreadable, oversized, or mismatched checkpoint(s) were skipped."]
        )
    lines.extend(
        [
            "",
            "The queue contains saved notes and project labels. Review before sharing it.",
            "",
        ]
    )
    return "\n".join(lines)
