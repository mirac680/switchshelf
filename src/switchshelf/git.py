from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .models import GitChange, GitCommit, GitState
from .privacy import is_sensitive_path, normalize_relative


GIT_TIMEOUT_SECONDS = 4


def _git(root: Path, *args: str, timeout: int = GIT_TIMEOUT_SECONDS) -> bytes | None:
    executable = shutil.which("git")
    if executable is None:
        return None
    environment = os.environ.copy()
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    environment["GIT_TERMINAL_PROMPT"] = "0"
    try:
        result = subprocess.run(
            [executable, "-c", "core.fsmonitor=false", "-C", str(root), *args],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
            shell=False,
            env=environment,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def discover_git_root(path: Path) -> Path | None:
    raw = _git(path, "rev-parse", "--show-toplevel")
    if raw is None:
        return None
    try:
        return Path(os.fsdecode(raw.strip())).resolve()
    except (OSError, RuntimeError):
        return None


def list_git_files(root: Path) -> list[str] | None:
    raw = _git(
        root,
        "ls-files",
        "-z",
        "--cached",
        "--others",
        "--exclude-standard",
        timeout=10,
    )
    if raw is None:
        return None
    result: list[str] = []
    for raw_path in raw.split(b"\0"):
        if not raw_path:
            continue
        path = normalize_relative(os.fsdecode(raw_path))
        if path:
            result.append(path)
    return result


def _parse_status(raw: bytes | None) -> list[GitChange]:
    if raw is None:
        return []
    records = raw.split(b"\0")
    changes: list[GitChange] = []
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if not record or record.startswith(b"##"):
            continue
        if len(record) < 4:
            continue

        status_bytes = record[:2]
        raw_path = record[3:]
        status = status_bytes.decode("ascii", "replace")
        path = normalize_relative(os.fsdecode(raw_path))

        # Porcelain -z emits a second NUL field for a rename/copy source path.
        if b"R" in status_bytes or b"C" in status_bytes:
            index += 1
        if path and not is_sensitive_path(path):
            changes.append(GitChange(status=status, path=path))
    return changes


def collect_git_state(root: Path) -> GitState:
    top = discover_git_root(root)
    if top is None:
        return GitState(is_repo=False)

    branch_raw = _git(top, "symbolic-ref", "--quiet", "--short", "HEAD")
    head_raw = _git(top, "rev-parse", "--verify", "HEAD")
    status_raw = _git(top, "status", "--porcelain=v1", "-z", "--untracked-files=normal")
    log_raw = _git(
        top,
        "log",
        "-n",
        "8",
        "--format=%h%x09%ad",
        "--date=short",
    )

    branch = os.fsdecode(branch_raw).strip() if branch_raw else "detached HEAD"
    head = os.fsdecode(head_raw).strip() if head_raw else None
    commits: list[GitCommit] = []
    if log_raw:
        for line in os.fsdecode(log_raw).splitlines():
            fields = line.split("\t", maxsplit=1)
            if len(fields) == 2:
                commits.append(GitCommit(short_hash=fields[0][:20], date=fields[1][:20]))

    read_error = None
    if status_raw is None:
        read_error = "Git status could not be read."

    all_dirty = _parse_status(status_raw)
    return GitState(
        is_repo=True,
        branch=branch or "detached HEAD",
        head=head or None,
        dirty=all_dirty[:1_000],
        dirty_count=len(all_dirty),
        dirty_truncated=len(all_dirty) > 1_000,
        recent_commits=commits,
        read_error=read_error,
    )


def commits_between(root: Path, old_head: str | None, new_head: str | None) -> list[GitCommit]:
    if not old_head or not new_head or old_head == new_head:
        return []
    raw = _git(
        root,
        "log",
        "-n",
        "30",
        "--format=%h%x09%ad",
        "--date=short",
        f"{old_head}..{new_head}",
    )
    if raw is None:
        return []
    commits: list[GitCommit] = []
    for line in os.fsdecode(raw).splitlines():
        fields = line.split("\t", maxsplit=1)
        if len(fields) == 2:
            commits.append(GitCommit(short_hash=fields[0][:20], date=fields[1][:20]))
    return commits
