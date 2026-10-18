from __future__ import annotations

import fnmatch
import hashlib
import os
import re
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable

from .git import collect_git_state, discover_git_root, list_git_files
from .models import Snapshot, TodoItem
from .privacy import SKIPPED_DIRECTORIES, is_sensitive_path, normalize_relative


MAX_FILES_LIMIT = 20_000
MAX_TODOS_LIMIT = 300
MAX_TODO_FILE_BYTES = 512 * 1024
MAX_TODO_TOTAL_BYTES = 12 * 1024 * 1024

EXTENSION_LANGUAGE = {
    ".py": "Python",
    ".pyi": "Python",
    ".pyx": "Python",
    ".js": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "CSS",
    ".sass": "CSS",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".xml": "XML",
    ".md": "Markdown",
    ".rst": "reStructuredText",
    ".txt": "Text",
    ".sh": "Shell",
    ".bash": "Shell",
    ".ps1": "PowerShell",
    ".bat": "Batch",
    ".cmd": "Batch",
    ".c": "C",
    ".h": "C/C++",
    ".cc": "C++",
    ".cpp": "C++",
    ".hpp": "C++",
    ".cs": "C#",
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".m": "Objective-C",
    ".mm": "Objective-C++",
    ".sql": "SQL",
    ".r": "R",
    ".R": "R",
    ".jl": "Julia",
    ".lua": "Lua",
    ".dart": "Dart",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".erl": "Erlang",
    ".hs": "Haskell",
    ".scala": "Scala",
    ".vue": "Vue",
    ".svelte": "Svelte",
}

TEXT_EXTENSIONS = {
    ".py", ".pyi", ".pyx", ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx",
    ".html", ".htm", ".css", ".scss", ".sass", ".json", ".yaml", ".yml",
    ".toml", ".xml", ".md", ".rst", ".txt", ".sh", ".bash", ".ps1", ".bat",
    ".cmd", ".c", ".h", ".cc", ".cpp", ".hpp", ".cs", ".java", ".kt", ".kts",
    ".go", ".rs", ".rb", ".php", ".swift", ".m", ".mm", ".sql", ".r", ".R",
    ".jl", ".lua", ".dart", ".ex", ".exs", ".erl", ".hs", ".scala", ".vue",
    ".svelte",
}

IMPORTANT_NAMES = {
    "readme",
    "readme.md",
    "readme.rst",
    "agents.md",
    "contributing.md",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "requirements.txt",
    "pipfile",
    "poetry.lock",
    "uv.lock",
    "package.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "cargo.toml",
    "cargo.lock",
    "go.mod",
    "go.sum",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "makefile",
    "justfile",
    "dockerfile",
    "compose.yaml",
    "compose.yml",
    "taskfile.yml",
    "manage.py",
    "main.py",
    "app.py",
    "index.js",
    "index.ts",
    "main.go",
    "main.rs",
}

KIND_MARKERS = {
    "Python": {"pyproject.toml", "setup.py", "requirements.txt", "pipfile"},
    "Node.js": {"package.json"},
    "Rust": {"cargo.toml"},
    "Go": {"go.mod"},
    "Java": {"pom.xml", "build.gradle", "build.gradle.kts"},
    ".NET": {"*.csproj", "*.sln"},
    "Ruby": {"gemfile"},
    "PHP": {"composer.json"},
    "Swift": {"package.swift"},
}

_TODO_PATTERN = re.compile(r"\b(TODO|FIXME|HACK|BUG)\b", re.IGNORECASE)


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except (OSError, ValueError, RuntimeError):
        return False


def _matches_exclude(relative: str, patterns: Iterable[str]) -> bool:
    candidate = relative.casefold()
    for pattern in patterns:
        normalized = normalize_relative(pattern).casefold()
        if fnmatch.fnmatchcase(candidate, normalized):
            return True
        if normalized.endswith("/**") and candidate.startswith(normalized[:-3]):
            return True
    return False


def _walk_files(root: Path, on_skip: Callable[[], None]) -> list[str]:
    paths: list[str] = []

    def record_error(_error: OSError) -> None:
        on_skip()

    for current, directory_names, file_names in os.walk(
        root, topdown=True, followlinks=False, onerror=record_error
    ):
        current_path = Path(current)
        kept_directories: list[str] = []
        for directory in sorted(directory_names, key=str.casefold):
            directory_path = current_path / directory
            relative = normalize_relative(directory_path.relative_to(root).as_posix())
            if directory.casefold() in SKIPPED_DIRECTORIES:
                continue
            if directory_path.is_symlink():
                continue
            if is_sensitive_path(relative):
                continue
            kept_directories.append(directory)
        directory_names[:] = kept_directories

        for file_name in sorted(file_names, key=str.casefold):
            path = normalize_relative((current_path / file_name).relative_to(root).as_posix())
            paths.append(path)
    return paths


def _language_counts(paths: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for relative in paths:
        suffix = Path(relative).suffix
        language = EXTENSION_LANGUAGE.get(suffix) or EXTENSION_LANGUAGE.get(suffix.casefold())
        if language:
            counts[language] = counts.get(language, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _important_files(paths: Iterable[str]) -> list[str]:
    matches: list[str] = []
    kind_names = set().union(*KIND_MARKERS.values())
    wanted = IMPORTANT_NAMES | kind_names
    for relative in paths:
        name = PurePosixPath(relative).name.casefold()
        if name in wanted or name.endswith((".csproj", ".sln")):
            matches.append(relative)
    return matches[:200]


def _project_kind(paths: Iterable[str]) -> str:
    names = {PurePosixPath(path).name.casefold() for path in paths}
    detected = [
        label
        for label, markers in KIND_MARKERS.items()
        if any(
            fnmatch.fnmatchcase(name, marker)
            for name in names
            for marker in markers
        )
    ]
    return ", ".join(detected[:5]) if detected else "Unknown"


def _scan_todos(
    root: Path,
    file_index: dict[str, dict[str, int]],
    max_todos: int,
) -> tuple[list[TodoItem], int]:
    todos: list[TodoItem] = []
    total_read = 0
    skipped_unreadable = 0

    for relative, details in file_index.items():
        if len(todos) >= max_todos or total_read >= MAX_TODO_TOTAL_BYTES:
            break
        suffix = Path(relative).suffix
        if suffix.casefold() not in TEXT_EXTENSIONS or details["size"] > MAX_TODO_FILE_BYTES:
            continue
        remaining_budget = MAX_TODO_TOTAL_BYTES - total_read
        if details["size"] > remaining_budget:
            continue

        path = root.joinpath(*PurePosixPath(relative).parts)
        try:
            if path.is_symlink() or not _is_within(path.resolve(strict=True), root):
                continue
            with path.open("rb") as handle:
                raw_content = handle.read(
                    min(MAX_TODO_FILE_BYTES, remaining_budget) + 1
                )
            if len(raw_content) > min(MAX_TODO_FILE_BYTES, remaining_budget):
                continue
            total_read += len(raw_content)
            content = raw_content.decode("utf-8", errors="replace")
        except OSError:
            skipped_unreadable += 1
            continue

        for line_number, line in enumerate(content.splitlines(), start=1):
            match = _TODO_PATTERN.search(line)
            if match:
                todos.append(
                    TodoItem(
                        path=relative,
                        line=line_number,
                        marker=match.group(1).upper(),
                    )
                )
                if len(todos) >= max_todos:
                    break
    return todos, skipped_unreadable


def _project_id(root: Path) -> str:
    normalized = os.path.normcase(str(root.resolve()))
    return hashlib.sha256(normalized.encode("utf-8", errors="surrogatepass")).hexdigest()[:24]


def project_id_for_root(root: Path) -> str:
    return _project_id(root)


def _display_name(root: Path) -> str:
    name = root.name or root.anchor or "Project"
    return name[:240]


def scan_project(
    requested_root: Path,
    *,
    note: str = "",
    goal: str = "",
    next_step: str = "",
    blocker: str = "",
    done_when: str = "",
    excluded_output: Path | None = None,
    additional_exclusions: Iterable[Path] = (),
    exclude_patterns: Iterable[str] = (),
    max_files: int = 10_000,
    max_todos: int = 100,
) -> tuple[Path, Snapshot]:
    if max_files < 1 or max_files > MAX_FILES_LIMIT:
        raise ValueError(f"max_files must be between 1 and {MAX_FILES_LIMIT}.")
    if max_todos < 1 or max_todos > MAX_TODOS_LIMIT:
        raise ValueError(f"max_todos must be between 1 and {MAX_TODOS_LIMIT}.")
    if len(note) > 2_000:
        raise ValueError("The note cannot exceed 2,000 characters.")
    for label, value in (
        ("goal", goal),
        ("next step", next_step),
        ("blocker", blocker),
        ("definition of done", done_when),
    ):
        if len(value) > 1_000:
            raise ValueError(f"The {label} cannot exceed 1,000 characters.")

    requested = requested_root.expanduser().resolve(strict=True)
    if not requested.is_dir():
        raise ValueError(f"Project path is not a directory: {requested_root}")

    root = discover_git_root(requested) or requested
    if not root.is_dir():
        raise ValueError(f"Could not read project directory: {root}")
    excluded_paths = [
        path.expanduser()
        for path in (excluded_output, *additional_exclusions)
        if path is not None
    ]

    skipped_errors = 0

    def count_skip() -> None:
        nonlocal skipped_errors
        skipped_errors += 1

    raw_paths = list_git_files(root)
    if raw_paths is None:
        raw_paths = _walk_files(root, count_skip)

    files: dict[str, dict[str, int]] = {}
    sensitive_count = 0
    truncated = False
    for relative in raw_paths:
        relative = normalize_relative(relative)
        if not relative:
            continue
        if is_sensitive_path(relative):
            sensitive_count += 1
            continue
        if _matches_exclude(relative, exclude_patterns):
            continue

        path = root.joinpath(*PurePosixPath(relative).parts)
        if any(_is_within(path, excluded) for excluded in excluded_paths):
            continue
        try:
            if path.is_symlink() or not path.is_file():
                continue
            resolved = path.resolve(strict=True)
            if not _is_within(resolved, root):
                continue
            stat = path.stat()
        except (OSError, RuntimeError):
            count_skip()
            continue

        files[relative] = {
            "size": max(0, int(stat.st_size)),
            "mtime_ns": max(0, int(stat.st_mtime_ns)),
        }
        if len(files) >= max_files:
            truncated = len(raw_paths) > len(files)
            break

    files = dict(sorted(files.items(), key=lambda item: item[0].casefold()))
    languages = _language_counts(files.keys())
    important = _important_files(files.keys())
    todos, todo_read_errors = _scan_todos(root, files, max_todos)

    snapshot = Snapshot(
        captured_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        project_id=_project_id(root),
        project_name=_display_name(root),
        project_kind=_project_kind(files.keys()),
        note=note.strip(),
        goal=goal.strip(),
        next_step=next_step.strip(),
        blocker=blocker.strip(),
        done_when=done_when.strip(),
        git=collect_git_state(root),
        languages=languages,
        important_files=important,
        files=files,
        todos=todos,
        total_files=len(files),
        total_bytes=sum(item["size"] for item in files.values()),
        truncated=truncated,
        skipped_sensitive=sensitive_count,
        skipped_unreadable=skipped_errors + todo_read_errors,
    )
    return root, snapshot
