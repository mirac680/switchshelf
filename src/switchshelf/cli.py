from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path
from typing import Sequence

from . import __version__
from .delta import compare_snapshots
from .git import discover_git_root
from .models import Snapshot
from .reflections import record_reflection, load_reflections, render_insights
from .report import render_agent_prompt, render_markdown, render_queue
from .scanner import project_id_for_root, scan_project
from .state import (
    default_state_directory,
    delete_checkpoint,
    delete_checkpoint_prefix,
    load_checkpoint,
    list_checkpoints,
    save_checkpoint,
)


def _common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "path",
        nargs="?",
        default=Path.cwd(),
        type=Path,
        help="Project directory (defaults to the current directory).",
    )
    parser.add_argument(
        "--state-dir",
        type=Path,
        help="Use this directory instead of the per-user local checkpoint store.",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        help="Exclude a relative path pattern; may be repeated.",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=10_000,
        metavar="N",
        help="Maximum file records to inspect (1–20,000; default: 10,000).",
    )
    parser.add_argument(
        "--max-todos",
        type=int,
        default=100,
        metavar="N",
        help="Maximum task markers to collect (1–300; default: 100).",
    )
    parser.add_argument(
        "--export",
        type=Path,
        metavar="FILE",
        help="Write the Markdown report to this path.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacing an existing report passed to --export.",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="switchshelf",
        description=(
            "Save a private project checkpoint and see what changed when you return. "
            "No source content is stored."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    pause = subparsers.add_parser(
        "pause",
        help="Save the current project state as your new checkpoint.",
        description="Record a safe project inventory and an optional note for your future self.",
    )
    _common_options(pause)
    pause.add_argument(
        "--note",
        default="",
        help="A short reminder to show when you resume (maximum 2,000 characters).",
    )
    pause.add_argument(
        "--goal",
        default="",
        help="What outcome are you working toward? (max 1,000 characters)",
    )
    pause.add_argument(
        "--next",
        dest="next_step",
        default="",
        help="The smallest concrete next action (max 1,000 characters).",
    )
    pause.add_argument(
        "--blocker",
        default="",
        help="What is blocking progress, if anything? (max 1,000 characters).",
    )
    pause.add_argument(
        "--done-when",
        default="",
        help="How will you recognize that this task is done? (max 1,000 characters).",
    )

    resume = subparsers.add_parser(
        "resume",
        help="Compare the project with its most recent checkpoint.",
        description="Read the last checkpoint and show file, Git, and task-marker changes.",
    )
    _common_options(resume)

    last = subparsers.add_parser(
        "last",
        help="Show the last saved checkpoint without scanning the project.",
    )
    last.add_argument(
        "path",
        nargs="?",
        default=Path.cwd(),
        type=Path,
        help="Project directory (defaults to the current directory).",
    )
    last.add_argument(
        "--state-dir",
        type=Path,
        help="Use this directory instead of the per-user local checkpoint store.",
    )
    last.add_argument(
        "--export",
        type=Path,
        metavar="FILE",
        help="Write the Markdown report to this path.",
    )
    last.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacing an existing report passed to --export.",
    )
    forget = subparsers.add_parser(
        "forget",
        help="Delete this project's local checkpoint.",
        description="Remove the saved note and inventory for one project.",
    )
    forget.add_argument(
        "path",
        nargs="?",
        type=Path,
        help="Project directory (defaults to the current directory).",
    )
    forget.add_argument(
        "--id",
        dest="project_prefix",
        help="Delete by a unique hexadecimal ID prefix shown by switchshelf queue.",
    )
    forget.add_argument(
        "--state-dir",
        type=Path,
        help="Use this directory instead of the per-user local checkpoint store.",
    )
    forget.add_argument(
        "--yes",
        action="store_true",
        required=True,
        help="Confirm deletion of this project's local checkpoint.",
    )

    queue = subparsers.add_parser(
        "queue",
        help="Show saved pause notes across projects in one local queue.",
    )
    queue.add_argument(
        "--state-dir",
        type=Path,
        help="Use this directory instead of the per-user local checkpoint store.",
    )
    queue.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum checkpoints to show (1–500; default: 50).",
    )
    queue.add_argument(
        "--export",
        type=Path,
        metavar="FILE",
        help="Write the Markdown queue to this path.",
    )
    queue.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacing an existing report passed to --export.",
    )

    prompt = subparsers.add_parser(
        "prompt",
        help="Create a portable, evidence-labelled continuation brief for any AI agent.",
        description=(
            "Build a model-agnostic handoff prompt from your saved contract and "
            "current project signals."
        ),
    )
    _common_options(prompt)

    reflect = subparsers.add_parser(
        "reflect",
        help="Record how long it took to get moving after resuming a project.",
        description=(
            "Opt in to a local-only measurement of your personal return time "
            "and perceived friction."
        ),
    )
    reflect.add_argument("path", nargs="?", default=Path.cwd(), type=Path)
    reflect.add_argument(
        "--state-dir",
        type=Path,
        help="Use this directory instead of the per-user local checkpoint store.",
    )
    reflect.add_argument(
        "--minutes",
        type=int,
        required=True,
        help="Minutes until your first meaningful action (0–1440).",
    )
    reflect.add_argument(
        "--friction",
        type=int,
        choices=range(1, 6),
        required=True,
        metavar="1..5",
        help="Your return difficulty: 1 easy, 5 very hard.",
    )

    insights = subparsers.add_parser(
        "insights",
        help="See your personal re-entry time and handoff-completeness comparison.",
    )
    insights.add_argument(
        "--state-dir",
        type=Path,
        help="Use this directory instead of the per-user local checkpoint store.",
    )
    return parser


def _state_directory(args: argparse.Namespace) -> Path:
    return args.state_dir.expanduser() if args.state_dir else default_state_directory()


def _resolve_root(requested: Path) -> Path:
    candidate = requested.expanduser().resolve(strict=True)
    if not candidate.is_dir():
        raise ValueError(f"Project path is not a directory: {requested}")
    return discover_git_root(candidate) or candidate


def _export_report(path: Path | None, text: str, overwrite: bool) -> None:
    if path is None:
        return
    target = path.expanduser()
    if target.exists() and not overwrite:
        raise FileExistsError(
            f"Report already exists: {target}. Choose another path or pass --overwrite."
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=".switchshelf-",
            suffix=".tmp",
            dir=target.parent,
            delete=False,
        ) as handle:
            temporary_name = handle.name
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, target)
        temporary_name = None
    finally:
        if temporary_name:
            try:
                os.unlink(temporary_name)
            except OSError:
                pass


def _scan(args: argparse.Namespace, note: str = "") -> tuple[Path, Snapshot]:
    store = _state_directory(args)
    export_path = getattr(args, "export", None)
    return scan_project(
        args.path,
        note=note,
        excluded_output=store,
        additional_exclusions=[export_path] if export_path is not None else [],
        exclude_patterns=args.exclude,
        max_files=args.max_files,
        max_todos=args.max_todos,
        goal=getattr(args, "goal", ""),
        next_step=getattr(args, "next_step", ""),
        blocker=getattr(args, "blocker", ""),
        done_when=getattr(args, "done_when", ""),
    )


def _run_pause(args: argparse.Namespace) -> int:
    root, current = _scan(args, args.note)
    store = _state_directory(args)
    previous = load_checkpoint(store, current.project_id)
    delta = compare_snapshots(previous, current, root) if previous else None
    report = render_markdown(
        current,
        previous=previous,
        delta=delta,
        view="pause",
    )
    _export_report(args.export, report, args.overwrite)
    save_checkpoint(store, current)
    print(report)
    print("Checkpoint saved in the local SwitchShelf store.")
    return 0


def _run_resume(args: argparse.Namespace) -> int:
    root, current = _scan(args)
    previous = load_checkpoint(_state_directory(args), current.project_id)
    if previous is None:
        report = render_markdown(current, view="resume")
    else:
        current.note = previous.note
        current.goal = previous.goal
        current.next_step = previous.next_step
        current.blocker = previous.blocker
        current.done_when = previous.done_when
        delta = compare_snapshots(previous, current, root)
        report = render_markdown(
            current,
            previous=previous,
            delta=delta,
            view="resume",
        )
    _export_report(args.export, report, args.overwrite)
    print(report)
    return 0


def _run_last(args: argparse.Namespace) -> int:
    root = _resolve_root(args.path)
    project_id = project_id_for_root(root)
    snapshot = load_checkpoint(_state_directory(args), project_id)
    if snapshot is None:
        print("No checkpoint exists for this project yet. Run switchshelf pause.")
        return 0
    report = render_markdown(snapshot, view="last")
    _export_report(args.export, report, args.overwrite)
    print(report)
    return 0


def _run_forget(args: argparse.Namespace) -> int:
    if args.project_prefix and args.path:
        raise ValueError("Choose either a project path or --id, not both.")
    if args.project_prefix:
        removed = delete_checkpoint_prefix(_state_directory(args), args.project_prefix)
    else:
        root = _resolve_root(args.path or Path.cwd())
        removed = delete_checkpoint(_state_directory(args), project_id_for_root(root))
    if removed:
        print("Local SwitchShelf checkpoint deleted.")
    else:
        print("No local checkpoint exists for this project.")
    return 0


def _run_queue(args: argparse.Namespace) -> int:
    snapshots, skipped, truncated = list_checkpoints(
        _state_directory(args),
        limit=args.limit,
    )
    report = render_queue(snapshots, skipped, truncated)
    _export_report(args.export, report, args.overwrite)
    print(report)
    return 0


def _run_prompt(args: argparse.Namespace) -> int:
    root, current = _scan(args)
    previous = load_checkpoint(_state_directory(args), current.project_id)
    delta = None
    if previous is not None:
        current.note = previous.note
        current.goal = previous.goal
        current.next_step = previous.next_step
        current.blocker = previous.blocker
        current.done_when = previous.done_when
        delta = compare_snapshots(previous, current, root)
    prompt = render_agent_prompt(current, previous=previous, delta=delta)
    _export_report(args.export, prompt, args.overwrite)
    print(prompt)
    return 0


def _run_reflect(args: argparse.Namespace) -> int:
    root = _resolve_root(args.path)
    store = _state_directory(args)
    snapshot = load_checkpoint(store, project_id_for_root(root))
    if snapshot is None:
        raise ValueError(
            "No saved checkpoint exists for this project. Run switchshelf pause first."
        )
    path = record_reflection(
        store,
        snapshot,
        minutes=args.minutes,
        friction=args.friction,
    )
    print("Re-entry reflection saved locally.")
    print(f"Return time: {args.minutes} min; self-rated friction: {args.friction}/5.")
    print(
        f"Local log: {path.name} "
        "(project names, notes, and file paths are not recorded)."
    )
    return 0


def _run_insights(args: argparse.Namespace) -> int:
    records, skipped = load_reflections(_state_directory(args))
    print(render_insights(records, skipped))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "pause":
            return _run_pause(args)
        if args.command == "resume":
            return _run_resume(args)
        if args.command == "last":
            return _run_last(args)
        if args.command == "forget":
            return _run_forget(args)
        if args.command == "queue":
            return _run_queue(args)
        if args.command == "prompt":
            return _run_prompt(args)
        if args.command == "reflect":
            return _run_reflect(args)
        if args.command == "insights":
            return _run_insights(args)
        parser.error("Unknown command.")
    except (OSError, ValueError) as exc:
        print(f"switchshelf: {exc}", file=sys.stderr)
        return 2
    return 0
