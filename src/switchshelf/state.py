from __future__ import annotations

import json
import os
import platform
import re
import tempfile
from pathlib import Path

from .models import Snapshot


PROJECT_ID_PATTERN = re.compile(r"^[0-9a-f]{24}$")
PROJECT_ID_PREFIX_PATTERN = re.compile(r"^[0-9a-f]{6,24}$")
MAX_STATE_FILE_BYTES = 24 * 1024 * 1024


def default_state_directory() -> Path:
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("LOCALAPPDATA")
        return Path(base) / "SwitchShelf" if base else Path.home() / "AppData" / "Local" / "SwitchShelf"
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "SwitchShelf"
    state_home = os.environ.get("XDG_STATE_HOME")
    if state_home and Path(state_home).is_absolute():
        return Path(state_home) / "switchshelf"
    return Path.home() / ".local" / "state" / "switchshelf"


def checkpoint_path(state_directory: Path, project_id: str) -> Path:
    if not PROJECT_ID_PATTERN.fullmatch(project_id):
        raise ValueError("Invalid project fingerprint.")
    return state_directory.expanduser() / f"{project_id}.json"


def load_checkpoint(state_directory: Path, project_id: str) -> Snapshot | None:
    path = checkpoint_path(state_directory, project_id)
    if not path.exists():
        return None
    if path.is_symlink():
        raise ValueError(f"Checkpoint must not be a symbolic link: {path.name}")
    if path.stat().st_size > MAX_STATE_FILE_BYTES:
        raise ValueError("Checkpoint is larger than the supported safety limit.")

    try:
        with path.open("r", encoding="utf-8") as handle:
            snapshot = Snapshot.from_dict(json.load(handle))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read checkpoint {path.name}: {exc}") from exc

    if snapshot.project_id != project_id:
        raise ValueError("Checkpoint fingerprint does not match this project.")
    return snapshot


def save_checkpoint(state_directory: Path, snapshot: Snapshot) -> Path:
    path = checkpoint_path(state_directory, snapshot.project_id)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=".switchshelf-",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as handle:
            temporary_name = handle.name
            json.dump(snapshot.to_dict(), handle, ensure_ascii=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

        try:
            os.chmod(temporary_name, 0o600)
        except OSError:
            pass
        os.replace(temporary_name, path)
        temporary_name = None
        return path
    finally:
        if temporary_name:
            try:
                os.unlink(temporary_name)
            except OSError:
                pass


def delete_checkpoint(state_directory: Path, project_id: str) -> bool:
    path = checkpoint_path(state_directory, project_id)
    if not path.exists():
        return False
    if path.is_symlink():
        raise ValueError(f"Checkpoint must not be a symbolic link: {path.name}")
    path.unlink()
    return True


def delete_checkpoint_prefix(state_directory: Path, prefix: str) -> bool:
    normalized = prefix.casefold()
    if not PROJECT_ID_PREFIX_PATTERN.fullmatch(normalized):
        raise ValueError("Project ID must be a hexadecimal prefix of at least 6 characters.")
    directory = state_directory.expanduser()
    if not directory.exists():
        return False
    matches = [
        path
        for path in directory.glob(f"{normalized}*.json")
        if PROJECT_ID_PATTERN.fullmatch(path.stem)
    ]
    if not matches:
        return False
    if len(matches) > 1:
        raise ValueError("Project ID prefix is ambiguous; provide more characters.")
    return delete_checkpoint(directory, matches[0].stem)


def list_checkpoints(
    state_directory: Path,
    *,
    limit: int = 100,
) -> tuple[list[Snapshot], int, bool]:
    if limit < 1 or limit > 500:
        raise ValueError("Checkpoint queue limit must be between 1 and 500.")
    directory = state_directory.expanduser()
    if not directory.exists():
        return [], 0, False
    if not directory.is_dir():
        raise ValueError("The checkpoint store path is not a directory.")

    entries = [
        path
        for path in directory.glob("*.json")
        if PROJECT_ID_PATTERN.fullmatch(path.stem)
    ]

    def modified_at(path: Path) -> int:
        try:
            return path.lstat().st_mtime_ns
        except OSError:
            return 0

    entries.sort(key=modified_at, reverse=True)
    truncated = len(entries) > limit
    entries = entries[:limit]
    snapshots: list[Snapshot] = []
    skipped = 0

    for path in entries:
        try:
            if path.is_symlink() or path.stat().st_size > MAX_STATE_FILE_BYTES:
                skipped += 1
                continue
            with path.open("r", encoding="utf-8") as handle:
                snapshot = Snapshot.from_dict(json.load(handle))
            if snapshot.project_id != path.stem:
                skipped += 1
                continue
            snapshots.append(snapshot)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            skipped += 1

    snapshots.sort(key=lambda item: item.captured_at, reverse=True)
    return snapshots, skipped, truncated
