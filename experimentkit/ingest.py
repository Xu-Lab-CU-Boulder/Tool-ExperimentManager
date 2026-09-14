"""Ingest, stage 1: decide where every clip would go. Copy nothing.

For each clip on a card or in a capture folder:

    which experiment and take   <- the slate, read from the footage
    which camera                <- the CAMERA.txt label, or the folder it came from
    where it would be filed     <- projectkit: <raw>/<id>/take03/<camera>/<name>

and whether that is certain enough to act on. The rule throughout is
**never guess**. A clip with no readable slate, with codes that disagree, or
naming an experiment the project does not have, is *unsorted* with the reason
given. A wrong guess puts footage in the wrong dataset, and nothing downstream
would ever notice.

Nothing here writes to disk. Stage 2 adds the copy, and will act only on what
this plan calls certain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from projectkit.config import Config, ConfigError
from projectkit.dataset import Dataset, SchemaError

from .clips import Clip, LabelError, camera_for, find_clips, home_folder
from .payload import take_folder
from .slate import SlateReading, read_slate

# Statuses a clip can end up with.
FILE = "file"                  # would be copied to `destination`
ALREADY = "already-filed"      # the same file is already there
CONFLICT = "conflict"          # something different is already there, or two clips collide
UNSORTED = "unsorted"          # not certain enough to file; `reason` says why


@dataclass
class ClipPlan:
    clip: Clip
    camera: str
    camera_source: str             # "label", "unlabelled", or "override"
    reading: SlateReading
    status: str = UNSORTED
    reason: str = ""
    destination: Path | None = None
    dataset_id: str = ""
    take: int | None = None


@dataclass
class IngestPlan:
    source: Path
    project: str
    clips: list[ClipPlan] = field(default_factory=list)
    ignored: list[Path] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)   # affect the whole run

    def count(self, status: str) -> int:
        return sum(1 for c in self.clips if c.status == status)


def _dataset_stage(cfg: Config, dataset_id: str) -> tuple[str | None, str]:
    """The stage a dataset's data lives in, or (None, why it cannot be used)."""
    path = Dataset.sidecar_path(cfg, dataset_id)
    if not path.exists():
        return None, (f"no dataset {dataset_id!r} in this project. Create it "
                      f"first: projectkit dataset new {dataset_id}")
    try:
        return Dataset.load(path).stage, ""
    except SchemaError as exc:
        return None, str(exc)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return None, f"sidecar for {dataset_id!r} is unreadable: {exc}"


def _unsorted_reason(reading: SlateReading, window_seconds: float) -> str:
    if reading.error:
        return reading.error
    found = reading.identities
    if not found:
        where = f"the first or last {window_seconds:g} s"
        if not reading.tail_searched:
            where = f"the first {window_seconds:g} s (the file has no frame count, so its end could not be searched)"
        return f"no slate found in {where}"
    names = ", ".join(f"{i} {take_folder(t)}" for i, t in sorted(found))
    return f"slate codes disagree: {names}"


def plan_ingest(source: Path, cfg: Config, camera: str | None = None,
                window_seconds: float = 10.0, bulk_required: bool = True
                ) -> IngestPlan:
    """Work out where every clip under `source` would go. Writes nothing."""
    source = source.resolve()
    plan = IngestPlan(source=source, project=cfg.name)

    try:
        raw_root = cfg.stage_dir("raw")
    except ConfigError as exc:
        plan.problems.append(str(exc))
        raw_root = None

    clips, plan.ignored = find_clips(source)

    # Unlabelled cameras are told apart by the folder they wrote to.
    unlabelled: dict[Path, str] = {}

    for clip in clips:
        if camera:
            name, origin = camera, "override"
        else:
            try:
                label, _ = camera_for(clip, source)
            except LabelError as exc:
                plan.problems.append(str(exc))
                label = None
            if label:
                name, origin = label, "label"
            else:
                home = home_folder(clip)
                if home not in unlabelled:
                    unlabelled[home] = f"unknown-{len(unlabelled) + 1}"
                name, origin = unlabelled[home], "unlabelled"

        entry = ClipPlan(clip=clip, camera=name, camera_source=origin,
                         reading=read_slate(clip, window_seconds))
        plan.clips.append(entry)

        identity = entry.reading.identity
        if identity is None:
            entry.reason = _unsorted_reason(entry.reading, window_seconds)
            continue

        entry.dataset_id, entry.take = identity
        stage, why = _dataset_stage(cfg, entry.dataset_id)
        if stage is None:
            entry.reason = why
            continue
        if raw_root is None:
            entry.reason = "bulk storage is not reachable, so there is nowhere to file it"
            continue

        base = cfg.stage_dir(stage)
        entry.destination = (base / entry.dataset_id / take_folder(entry.take)
                             / name / clip.name)
        entry.status = FILE

    _mark_existing(plan)
    _mark_collisions(plan)
    return plan


def _size_on_disk(path: Path) -> int:
    if path.is_dir():
        return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())
    return path.stat().st_size


def _mark_existing(plan: IngestPlan) -> None:
    """Something already at the destination is either this clip or a clash.

    Size is the stage-1 test. Stage 2 compares hashes before it trusts a match.
    """
    for entry in plan.clips:
        if entry.status != FILE or not entry.destination.exists():
            continue
        if _size_on_disk(entry.destination) == entry.clip.bytes:
            entry.status = ALREADY
            entry.reason = "already filed (same size)"
        else:
            entry.status = CONFLICT
            entry.reason = "something different is already at the destination"


def _mark_collisions(plan: IngestPlan) -> None:
    """Two clips headed for the same path would overwrite each other."""
    by_destination: dict[Path, list[ClipPlan]] = {}
    for entry in plan.clips:
        if entry.status == FILE:
            by_destination.setdefault(entry.destination, []).append(entry)
    for entries in by_destination.values():
        if len(entries) > 1:
            for entry in entries:
                entry.status = CONFLICT
                entry.reason = (f"{len(entries)} clips would be filed to the same "
                                "path: label the cameras apart with CAMERA.txt")
