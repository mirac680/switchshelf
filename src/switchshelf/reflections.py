"""Opt-in, local-only measurement of the cost of returning to paused work."""

from __future__ import annotations

import json
import os
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

from .models import Snapshot


SCHEMA_VERSION = 1
MAX_REFLECTION_FILE_BYTES = 16 * 1024 * 1024
MAX_REFLECTIONS_TO_READ = 50_000


def _reflection_path(state_directory: Path, year: int) -> Path:
    return state_directory.expanduser() / f"reflections-{year}.jsonl"


def record_reflection(
    state_directory: Path,
    snapshot: Snapshot,
    *,
    minutes: int,
    friction: int,
) -> Path:
    """Append a deliberately small measurement without notes or path names."""
    if not 0 <= minutes <= 1_440:
        raise ValueError("Return time must be between 0 and 1,440 minutes.")
    if not 1 <= friction <= 5:
        raise ValueError("Friction must be between 1 (easy) and 5 (very hard).")

    now = datetime.now(timezone.utc)
    path = _reflection_path(state_directory, now.year)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise ValueError(f"Reflection log must not be a symbolic link: {path.name}")
    if path.exists() and path.stat().st_size >= MAX_REFLECTION_FILE_BYTES:
        raise ValueError(
            f"Reflection log {path.name} reached its size limit; archive or remove it first."
        )

    core_signals = (snapshot.goal, snapshot.next_step, snapshot.done_when)
    record = {
        "schema_version": SCHEMA_VERSION,
        "reflected_at": now.isoformat(timespec="seconds"),
        "minutes": minutes,
        "friction": friction,
        "handoff_signals": sum(bool(value.strip()) for value in core_signals),
    }
    payload = (json.dumps(record, ensure_ascii=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )

    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        remaining = memoryview(payload)
        while remaining:
            written = os.write(descriptor, remaining)
            if written <= 0:
                raise OSError("Could not append the reflection record.")
            remaining = remaining[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path


def _is_valid_record(raw: Any) -> bool:
    return (
        isinstance(raw, dict)
        and type(raw.get("schema_version")) is int
        and raw.get("schema_version") == SCHEMA_VERSION
        and isinstance(raw.get("reflected_at"), str)
        and type(raw.get("minutes")) is int
        and 0 <= raw["minutes"] <= 1_440
        and type(raw.get("friction")) is int
        and 1 <= raw["friction"] <= 5
        and type(raw.get("handoff_signals")) is int
        and 0 <= raw["handoff_signals"] <= 3
    )


def load_reflections(state_directory: Path) -> tuple[list[dict[str, Any]], int]:
    """Load valid local measurements; malformed lines are counted and skipped."""
    directory = state_directory.expanduser()
    if not directory.exists():
        return [], 0
    paths = sorted(directory.glob("reflections-20??.jsonl"))
    records: deque[dict[str, Any]] = deque(maxlen=MAX_REFLECTIONS_TO_READ)
    skipped = 0
    truncated = False
    for path in paths:
        try:
            if path.is_symlink() or path.stat().st_size > MAX_REFLECTION_FILE_BYTES:
                skipped += 1
                continue
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    try:
                        raw = json.loads(line)
                    except json.JSONDecodeError:
                        skipped += 1
                        continue
                    if _is_valid_record(raw):
                        if len(records) == MAX_REFLECTIONS_TO_READ:
                            truncated = True
                        records.append(raw)
                    else:
                        skipped += 1
        except (OSError, UnicodeError):
            skipped += 1
    return list(records), skipped + int(truncated)


def _summary(records: list[dict[str, Any]]) -> tuple[int, float, float]:
    return (
        len(records),
        float(median(record["minutes"] for record in records)),
        float(median(record["friction"] for record in records)),
    )


def render_insights(records: list[dict[str, Any]], skipped: int = 0) -> str:
    """Render personal re-entry metrics without implying causal certainty."""
    if not records:
        lines = [
            "# SwitchShelf — Re-entry insights",
            "",
            "No return measurements have been recorded yet.",
            "",
            "After a `resume`, run `switchshelf reflect . --minutes 8 --friction 3`.",
            "Minutes means time until your first meaningful action. Friction is your own 1–5 rating.",
        ]
        if skipped:
            lines.extend(["", f"{skipped} invalid or oversized log item(s) were skipped."])
        return "\n".join(lines) + "\n"

    count, typical_minutes, typical_friction = _summary(records)
    now = datetime.now(timezone.utc)
    recent = [
        record
        for record in records
        if _age_in_days(record["reflected_at"], now) <= 30
    ]
    lines = [
        "# SwitchShelf — Re-entry insights",
        "",
        f"Based on **{count}** voluntary self-reports stored on this device.",
        "",
        "## Your baseline",
        "",
        f"- Median time to first meaningful action: **{_format_minutes(typical_minutes)}**.",
        f"- Median self-rated friction: **{typical_friction:g}/5**.",
        f"- Reports in the last 30 days: **{len(recent)}**.",
    ]
    if recent:
        recent_minutes = median(record["minutes"] for record in recent)
        recent_friction = median(record["friction"] for record in recent)
        lines.append(
            f"- Last-30-day median: **{_format_minutes(float(recent_minutes))}**, "
            f"friction **{recent_friction:g}/5**."
        )

    complete = [record for record in records if record["handoff_signals"] == 3]
    incomplete = [record for record in records if record["handoff_signals"] < 3]
    lines.extend(["", "## Handoff comparison", ""])
    minimum_group_size = 5
    if len(complete) >= minimum_group_size and len(incomplete) >= minimum_group_size:
        complete_summary = _summary(complete)
        incomplete_summary = _summary(incomplete)
        lines.extend(
            [
                f"- Complete handoff (goal + next step + done condition), "
                f"n={complete_summary[0]}: **{_format_minutes(complete_summary[1])}** "
                f"median, friction **{complete_summary[2]:g}/5**.",
                f"- Partial handoff, n={incomplete_summary[0]}: "
                f"**{_format_minutes(incomplete_summary[1])}** median, "
                f"friction **{incomplete_summary[2]:g}/5**.",
                "",
                "This is a personal observational comparison, not evidence that handoff "
                "completeness caused the difference.",
            ]
        )
    else:
        lines.append(
            f"Need at least {minimum_group_size} reports in both groups to compare. "
            f"Current groups: {len(complete)} complete and {len(incomplete)} partial."
        )

    lines.extend(
        [
            "",
            "## Make the next pause easier",
            "",
            "Capture a concrete next action and a visible done condition with "
            "`switchshelf pause --next \"...\" --done-when \"...\"`.",
            "",
            "Measurements are optional, never collected automatically, and never sent "
            "over the network.",
        ]
    )
    if skipped:
        lines.extend(["", f"{skipped} invalid or oversized log item(s) were skipped."])
    return "\n".join(lines) + "\n"


def _age_in_days(value: str, now: datetime) -> float:
    try:
        captured = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if captured.tzinfo is None:
            captured = captured.replace(tzinfo=timezone.utc)
        return max(0.0, (now - captured.astimezone(timezone.utc)).total_seconds() / 86_400)
    except (TypeError, ValueError):
        return float("inf")


def _format_minutes(value: float) -> str:
    if value == int(value):
        return f"{int(value)} min"
    return f"{value:.1f} min"
