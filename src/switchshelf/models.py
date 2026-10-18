from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


SCHEMA_VERSION = 2
MAX_STORED_FILES = 20_000
MAX_STORED_TODOS = 500


@dataclass(slots=True)
class TodoItem:
    path: str
    line: int
    marker: str


@dataclass(slots=True)
class GitChange:
    status: str
    path: str


@dataclass(slots=True)
class GitCommit:
    short_hash: str
    date: str


@dataclass(slots=True)
class GitState:
    is_repo: bool = False
    branch: str | None = None
    head: str | None = None
    dirty: list[GitChange] = field(default_factory=list)
    dirty_count: int = 0
    dirty_truncated: bool = False
    recent_commits: list[GitCommit] = field(default_factory=list)
    read_error: str | None = None


@dataclass(slots=True)
class Snapshot:
    captured_at: str
    project_id: str
    project_name: str
    project_kind: str
    note: str
    git: GitState
    languages: dict[str, int]
    important_files: list[str]
    files: dict[str, dict[str, int]]
    todos: list[TodoItem]
    total_files: int
    total_bytes: int
    truncated: bool
    skipped_sensitive: int
    skipped_unreadable: int
    goal: str = ""
    next_step: str = ""
    blocker: str = ""
    done_when: str = ""
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Any) -> Snapshot:
        if not isinstance(raw, dict):
            raise ValueError("Snapshot JSON must contain an object.")
        source_schema = raw.get("schema_version")
        if type(source_schema) is not int or source_schema not in {1, SCHEMA_VERSION}:
            raise ValueError(
                f"Unsupported snapshot schema: {raw.get('schema_version')!r}."
            )

        files_raw = raw.get("files")
        todos_raw = raw.get("todos")
        git_raw = raw.get("git")
        if not isinstance(files_raw, dict) or len(files_raw) > MAX_STORED_FILES:
            raise ValueError("Snapshot file index is missing or too large.")
        if not isinstance(todos_raw, list) or len(todos_raw) > MAX_STORED_TODOS:
            raise ValueError("Snapshot TODO index is missing or too large.")
        if not isinstance(git_raw, dict):
            raise ValueError("Snapshot Git state is missing.")

        files: dict[str, dict[str, int]] = {}
        for path, details in files_raw.items():
            if not isinstance(path, str) or not isinstance(details, dict):
                continue
            size = details.get("size")
            mtime_ns = details.get("mtime_ns")
            if isinstance(size, int) and isinstance(mtime_ns, int):
                files[path] = {"size": max(0, size), "mtime_ns": max(0, mtime_ns)}

        todos: list[TodoItem] = []
        for item in todos_raw:
            if not isinstance(item, dict):
                continue
            path, line, marker = item.get("path"), item.get("line"), item.get("marker")
            if (
                isinstance(path, str)
                and isinstance(line, int)
                and isinstance(marker, str)
                and marker in {"TODO", "FIXME", "HACK", "BUG"}
            ):
                todos.append(TodoItem(path=path, line=max(1, line), marker=marker))

        dirty: list[GitChange] = []
        dirty_raw = git_raw.get("dirty", [])
        if isinstance(dirty_raw, list):
            for item in dirty_raw[:1_000]:
                if (
                    isinstance(item, dict)
                    and isinstance(item.get("status"), str)
                    and isinstance(item.get("path"), str)
                ):
                    dirty.append(GitChange(status=item["status"][:2], path=item["path"]))

        commits: list[GitCommit] = []
        recent_raw = git_raw.get("recent_commits", [])
        if isinstance(recent_raw, list):
            for item in recent_raw[:20]:
                if (
                    isinstance(item, dict)
                    and isinstance(item.get("short_hash"), str)
                    and isinstance(item.get("date"), str)
                ):
                    commits.append(
                        GitCommit(
                            short_hash=item["short_hash"][:20],
                            date=item["date"][:20],
                        )
                    )

        languages_raw = raw.get("languages", {})
        languages: dict[str, int] = {}
        if isinstance(languages_raw, dict):
            for name, count in languages_raw.items():
                if isinstance(name, str) and isinstance(count, int) and count >= 0:
                    languages[name[:40]] = count

        important_raw = raw.get("important_files", [])
        important_files = (
            [item for item in important_raw[:200] if isinstance(item, str)]
            if isinstance(important_raw, list)
            else []
        )

        def text_value(key: str, limit: int = 500) -> str:
            value = raw.get(key, "")
            return value[:limit] if isinstance(value, str) else ""

        def int_value(key: str) -> int:
            value = raw.get(key, 0)
            return max(0, value) if isinstance(value, int) else 0

        return cls(
            captured_at=text_value("captured_at", 64),
            project_id=text_value("project_id", 64),
            project_name=text_value("project_name", 240),
            project_kind=text_value("project_kind", 120),
            note=text_value("note", 2_000),
            goal=text_value("goal", 1_000),
            next_step=text_value("next_step", 1_000),
            blocker=text_value("blocker", 1_000),
            done_when=text_value("done_when", 1_000),
            git=GitState(
                is_repo=bool(git_raw.get("is_repo", False)),
                branch=(
                    git_raw.get("branch")[:240]
                    if isinstance(git_raw.get("branch"), str)
                    else None
                ),
                head=(
                    git_raw.get("head")[:80]
                    if isinstance(git_raw.get("head"), str)
                    else None
                ),
                dirty=dirty,
                dirty_count=(
                    max(0, git_raw.get("dirty_count"))
                    if isinstance(git_raw.get("dirty_count"), int)
                    else len(dirty)
                ),
                dirty_truncated=bool(git_raw.get("dirty_truncated", False)),
                recent_commits=commits,
                read_error=(
                    git_raw.get("read_error")[:240]
                    if isinstance(git_raw.get("read_error"), str)
                    else None
                ),
            ),
            languages=languages,
            important_files=important_files,
            files=files,
            todos=todos,
            total_files=int_value("total_files"),
            total_bytes=int_value("total_bytes"),
            truncated=bool(raw.get("truncated", False)),
            skipped_sensitive=int_value("skipped_sensitive"),
            skipped_unreadable=int_value("skipped_unreadable"),
            schema_version=SCHEMA_VERSION,
        )
