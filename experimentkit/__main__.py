#!/usr/bin/env python3
"""experimentkit -- capture at the bench.

    experimentkit ingest <card or folder> --dry-run      where would every clip go?
    experimentkit ingest <card or folder> --dry-run --json
    experimentkit storage status | sync | verify     project snapshots on the work and backup drives

Run from inside a project repo, or pass --project. Nothing is copied: stage 1
of ingest only reports. Copying arrives in stage 2, and will act only on what
the dry run calls certain.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from projectkit.config import Config, ConfigError
from projectkit.util import human_bytes

from .payload import take_folder

#: Version of the --json payload shape. Adding keys is free; renaming bumps it.
JSON_SCHEMA = 1


def _facts(plan: ingest_mod.IngestPlan) -> dict:
    from . import ingest as ingest_mod

    clips = []
    for c in plan.clips:
        r = c.reading
        clips.append({
            "path": c.clip.path.relative_to(plan.source).as_posix(),
            "kind": c.clip.kind,
            "bytes": c.clip.bytes,
            "files": c.clip.files,
            "camera": c.camera,
            "camera_source": c.camera_source,
            "status": c.status,
            "reason": c.reason,
            "dataset_id": c.dataset_id or None,
            "take": c.take,
            "destination": str(c.destination) if c.destination else None,
            "slate": [{"code": f"{s.code.dataset_id}:{s.code.take_folder}"
                               + (f":sync:{s.code.sync:04d}" if s.code.is_sync else ""),
                       "where": s.where, "frame": s.frame} for s in r.sightings],
            "sync_head": r.sync_range("head"),
            "sync_tail": r.sync_range("tail"),
        })
    problems = list(plan.problems)
    problems += [f"{c['path']}: {c['reason']}" for c in clips
                 if c["status"] in (ingest_mod.UNSORTED, ingest_mod.CONFLICT)]
    return {
        "schema": JSON_SCHEMA,
        "command": "ingest --dry-run",
        "ok": not problems,
        "source": str(plan.source),
        "project": plan.project,
        "copied": 0,
        "counts": {s: plan.count(s) for s in (ingest_mod.FILE, ingest_mod.ALREADY,
                                              ingest_mod.CONFLICT, ingest_mod.UNSORTED)},
        "clips": clips,
        "ignored": [p.relative_to(plan.source).as_posix() for p in plan.ignored],
        "problems": problems,
    }


def _print_text(plan: ingest_mod.IngestPlan, cfg: Config) -> None:
    from . import ingest as ingest_mod

    print(f"ingest --dry-run   {plan.source}")
    print(f"into project       {plan.project}\n")

    for problem in plan.problems:
        print(f"! {problem}")
    if plan.problems:
        print()

    if not plan.clips:
        print("No recordings found (video files, or folders of numbered images).")

    for c in plan.clips:
        rel = c.clip.path.relative_to(plan.source).as_posix()
        size = human_bytes(c.clip.bytes)
        kind = f"{c.clip.files} images" if c.clip.kind == "sequence" else "video"
        camera = c.camera if c.camera_source != "unlabelled" else f"{c.camera} (no CAMERA.txt)"
        print(f"  {rel}")
        print(f"      {kind}, {size}, camera {camera}")

        r = c.reading
        if c.dataset_id:
            first = min(r.sightings, key=lambda s: (s.where != "head", s.frame))
            sync = [f"{w} {a:04d}-{b:04d}" for w in ("head", "tail")
                    if (rng := r.sync_range(w)) for a, b in [rng]]
            note = f"; sync {', '.join(sync)}" if sync else ""
            print(f"      slate  {c.dataset_id} {take_folder(c.take)}"
                  f"  ({first.where}, frame {first.frame}{note})")

        if c.status == ingest_mod.FILE:
            try:
                shown = c.destination.relative_to(cfg.bulk()).as_posix()
            except (ConfigError, ValueError):
                shown = str(c.destination)
            print(f"      ->     {shown}")
        else:
            label = {ingest_mod.ALREADY: "ALREADY FILED", ingest_mod.CONFLICT: "CONFLICT",
                     ingest_mod.UNSORTED: "UNSORTED"}[c.status]
            print(f"      {label}  {c.reason}")
        print()

    if plan.ignored:
        print(f"ignored {len(plan.ignored)} file(s) that are not recordings")

    print(f"{len(plan.clips)} clip(s): "
          f"{plan.count(ingest_mod.FILE)} would be filed, "
          f"{plan.count(ingest_mod.ALREADY)} already filed, "
          f"{plan.count(ingest_mod.CONFLICT)} conflict, "
          f"{plan.count(ingest_mod.UNSORTED)} unsorted.")
    print("--dry-run: nothing was copied.")


def cmd_ingest(args) -> int:
    # Imported here: ingest needs OpenCV and markertracker, and `storage` must run
    # on machines (like the DaVis PC) that have neither.
    from . import ingest as ingest_mod

    if not args.dry_run:
        print("error: only --dry-run exists yet. It reports where every clip would "
              "go and copies nothing; copying arrives in stage 2.", file=sys.stderr)
        return 2

    source = Path(args.source)
    if not source.is_dir():
        print(f"error: {source} is not a folder", file=sys.stderr)
        return 2

    try:
        cfg = Config.load(Path(args.project)) if args.project else Config.load()
    except ConfigError as exc:
        print(f"error: {exc}\nRun from inside a project, or pass --project.",
              file=sys.stderr)
        return 2

    plan = ingest_mod.plan_ingest(source, cfg, camera=args.camera,
                                  window_seconds=args.seconds)
    facts = _facts(plan)

    if args.json:
        json.dump(facts, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        _print_text(plan, cfg)
    return 0 if facts["ok"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="experimentkit", description="Capture at the bench.")
    sub = parser.add_subparsers(dest="cmd")

    p = sub.add_parser("ingest", help="file recordings into a project by their slate")
    p.add_argument("source", help="an SD card, or a folder of recordings")
    p.add_argument("--dry-run", action="store_true",
                   help="report where every clip would go; copy nothing")
    p.add_argument("--project", default="", help="project repo (default: the one you are in)")
    p.add_argument("--camera", default=None,
                   help="camera name for every clip, instead of CAMERA.txt labels")
    p.add_argument("--seconds", type=float, default=10.0,
                   help="how far into each end of a clip to look for the slate")
    p.add_argument("--json", action="store_true", help="print one JSON object instead of text")
    p.set_defaults(fn=cmd_ingest)

    from .storage.cli import add_storage_parser

    add_storage_parser(sub)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "cmd", None):
        parser.print_help()
        return 0
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
