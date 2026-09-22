"""Quality control with every sync: new calibrations and new recordings measured and filed.

The measuring is daviskit's (`daviskit.qc`, the library); this only decides
*when*: as part of each sync, so every recording is checked while it is still
on C: (fast to read) and before anyone deletes it, and every calibration is
filed the day it is made. Drift warnings come back in the sync's report.

    <project>.qc/                       beside the DaVis project, never inside it
        validation.jsonl, .csv          one record per recording (daviskit.qc.save_report)
        calibration.jsonl, .csv         one record per calibration (record_calibrations)
        datasets/<recording>/           metrics.json and summary.png per recording
        trends.png, calibration_trends.png

The folder is snapshotted to the drives with the project, and mirrored to
OneDrive (sync.mirror_qc). Its databases are JSON Lines, append-only.

**Budget.** Measuring a recording reads ~10 images and takes a minute or two,
so each sync run measures at most `budget` new recordings and leaves the rest
for the next run. `backfill` measures recordings that have already left C:,
reading them from the work drive.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .inventory import FileEntry, Recording
from .registry import SyncProject


@dataclass
class QCResult:
    """What one QC step did."""

    calibrations_added: int = 0
    calibration_warnings: list[str] = field(default_factory=list)
    validated: list[tuple[str, str, list[str]]] = field(default_factory=list)  # name, line, warnings
    pending: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    skipped: str = ""  # why QC did not run at all


def _set_time(set_file: Path) -> str:
    text = set_file.read_text(encoding="utf8", errors="replace") if set_file.exists() else ""
    m = re.search(r'SetTime\s*=\s*"([^"]*)"', text)
    return m.group(1) if m else ""


def recording_key(folder: Path) -> str:
    """The key daviskit files a recording under: its folder name @ its SetTime."""
    t = _set_time(Path(str(folder) + ".set"))
    return f"{folder.name}@{t}" if t else folder.name


def validated(qc_dir: Path) -> set[str]:
    """Keys of every recording already in the QC database."""
    from daviskit.qc import read_records

    return {r.get("key") for r in read_records(Path(qc_dir) / "validation.jsonl")}


def _measure(folder: Path, qc_dir: Path, images: int) -> tuple[str, list[str]]:
    """Measure one recording with daviskit and file it; returns (summary line, warnings)."""
    from daviskit import qc
    from daviskit.io.project import Project
    from daviskit.io.recording import Recording as DavisRecording

    recording = DavisRecording(folder)
    scale = None
    project = Project.containing(folder)
    if project is not None:
        try:
            scale = {n: c.px_per_mm for n, c in project.calibration().cameras.items()}
        except Exception:  # an unreadable calibration: measure in pixels only
            scale = None
    report = qc.validate(recording, images=images, px_per_mm=scale)
    warnings = qc.save_report(report, qc_dir)
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        from daviskit import plot

        fig, _ = plot.dataset_summary(report)
        fig.savefig(qc.dataset_folder(report, qc_dir) / "summary.png")
        # A backfill measures dozens of recordings in one process; pyplot keeps
        # every figure alive until it is closed.
        plt.close(fig)
    except ImportError:
        pass
    return report.line(), warnings


def _trends(project: SyncProject) -> None:
    """Rebuild the trend figures from the databases (needs matplotlib; skipped without it)."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        from daviskit import plot, qc
    except ImportError:
        return
    qc_dir = project.qc_dir
    records = qc.latest(qc.read_records(qc_dir / "validation.jsonl"))
    if len(records) >= 2:
        fig, _ = plot.metric_trends(records)
        fig.savefig(qc_dir / "trends.png")
        plt.close(fig)
    calibrations = qc.read_records(qc_dir / "calibration.jsonl")
    if calibrations:
        fig, _ = plot.calibration_trends(calibrations)
        fig.savefig(qc_dir / "calibration_trends.png")
        plt.close(fig)


def seed_from_mirror(project: SyncProject) -> int:
    """First run: start the QC folder from the OneDrive copy, if that is where it lived."""
    import shutil

    if project.qc_mirror is None or not project.qc_mirror.is_dir():
        return 0
    if project.qc_dir.is_dir() and any(project.qc_dir.iterdir()):
        return 0
    shutil.copytree(project.qc_mirror, project.qc_dir, dirs_exist_ok=True)
    return sum(1 for p in project.qc_dir.rglob("*") if p.is_file())


def _measure_many(project: SyncProject, folders: list[Path], budget: int | None,
                  images: int, result: QCResult, measure) -> None:
    done = validated(project.qc_dir)
    for folder in folders:
        key = recording_key(folder)
        if key in done:
            continue
        if budget is not None and len(result.validated) >= budget:
            result.pending.append(folder.name)
            continue
        try:
            line, warnings = measure(folder, project.qc_dir, images)
            result.validated.append((folder.name, line, warnings))
            done.add(key)
        except Exception as exc:  # one unreadable recording must not stop the rest
            result.problems.append(f"{folder.name}: could not be measured ({exc})")


def run_qc(project: SyncProject, files: dict[str, FileEntry], recs: list[Recording], *,
           budget: int | None = 3, images: int = 10, measure=None) -> QCResult:
    """File new calibrations, and measure recordings on C: not yet in the database."""
    result = QCResult()
    try:
        from daviskit import qc
        from daviskit.io.project import Project
    except ImportError:
        result.skipped = "daviskit is not installed, so nothing was measured"
        return result
    project.qc_dir.mkdir(parents=True, exist_ok=True)
    seed_from_mirror(project)
    try:
        added, warnings = qc.record_calibrations(Project(project.source), project.qc_dir)
        result.calibrations_added = len(added)
        result.calibration_warnings = warnings
    except Exception as exc:
        result.problems.append(f"calibrations: {exc}")
    folders = [project.source.parent / r.rel for r in recs]
    _measure_many(project, folders, budget, images, result, measure or _measure)
    if result.validated or result.calibrations_added:
        _trends(project)
    return result


def backfill(project: SyncProject, drive_root: Path, drive_recs: list[str], *,
             budget: int | None = None, images: int = 10, measure=None) -> QCResult:
    """Measure recordings that live only on a drive now (they left C: before QC existed)."""
    result = QCResult()
    try:
        import daviskit  # noqa: F401
    except ImportError:
        result.skipped = "daviskit is not installed, so nothing was measured"
        return result
    project.qc_dir.mkdir(parents=True, exist_ok=True)
    seed_from_mirror(project)
    _measure_many(project, [drive_root / rel for rel in drive_recs], budget, images, result,
                  measure or _measure)
    if result.validated:
        _trends(project)
    return result
