from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .git import commits_between
from .models import GitCommit, Snapshot


@dataclass(slots=True)
class Delta:
    added_files: list[str] = field(default_factory=list)
    removed_files: list[str] = field(default_factory=list)
    modified_files: list[str] = field(default_factory=list)
    new_todos: list[tuple[str, int, str]] = field(default_factory=list)
    resolved_todos: list[tuple[str, int, str]] = field(default_factory=list)
    new_worktree_paths: list[str] = field(default_factory=list)
    cleared_worktree_paths: list[str] = field(default_factory=list)
    changed_worktree_paths: list[str] = field(default_factory=list)
    branch_changed: bool = False
    head_changed: bool = False
    inventory_incomplete: bool = False
    working_tree_incomplete: bool = False
    commits_since: list[GitCommit] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return any(
            (
                self.added_files,
                self.removed_files,
                self.modified_files,
                self.new_todos,
                self.resolved_todos,
                self.new_worktree_paths,
                self.cleared_worktree_paths,
                self.changed_worktree_paths,
                self.branch_changed,
                self.head_changed,
                self.inventory_incomplete,
                self.working_tree_incomplete,
                self.commits_since,
            )
        )


def compare_snapshots(previous: Snapshot, current: Snapshot, root: Path) -> Delta:
    old_paths = set(previous.files)
    new_paths = set(current.files)
    added = sorted(new_paths - old_paths, key=str.casefold)
    removed = sorted(old_paths - new_paths, key=str.casefold)
    modified: list[str] = []

    for path in sorted(old_paths & new_paths, key=str.casefold):
        old_meta = previous.files[path]
        new_meta = current.files[path]
        if (
            old_meta.get("size") != new_meta.get("size")
            or old_meta.get("mtime_ns") != new_meta.get("mtime_ns")
        ):
            modified.append(path)

    old_todos = {(item.path, item.line, item.marker) for item in previous.todos}
    new_todos = {(item.path, item.line, item.marker) for item in current.todos}
    previous_dirty = {item.path: item.status for item in previous.git.dirty}
    current_dirty = {item.path: item.status for item in current.git.dirty}

    branch_changed = (
        previous.git.is_repo
        and current.git.is_repo
        and previous.git.branch != current.git.branch
    )
    head_changed = (
        previous.git.is_repo
        and current.git.is_repo
        and previous.git.head != current.git.head
    )

    commits: list[GitCommit] = []
    if (
        previous.git.is_repo
        and current.git.is_repo
        and previous.git.branch == current.git.branch
    ):
        commits = commits_between(root, previous.git.head, current.git.head)

    return Delta(
        added_files=added,
        removed_files=removed,
        modified_files=modified,
        new_todos=sorted(new_todos - old_todos),
        resolved_todos=sorted(old_todos - new_todos),
        new_worktree_paths=sorted(current_dirty.keys() - previous_dirty.keys(), key=str.casefold),
        cleared_worktree_paths=sorted(previous_dirty.keys() - current_dirty.keys(), key=str.casefold),
        changed_worktree_paths=sorted(
            path
            for path in current_dirty.keys() & previous_dirty.keys()
            if current_dirty[path] != previous_dirty[path]
        ),
        branch_changed=branch_changed,
        head_changed=head_changed,
        inventory_incomplete=previous.truncated or current.truncated,
        working_tree_incomplete=(
            previous.git.dirty_truncated
            or current.git.dirty_truncated
            or previous.git.read_error is not None
            or current.git.read_error is not None
        ),
        commits_since=commits,
    )
