"""What a DaVis project holds on C: right now: every file, and which files make each recording.

Paths are relative to the folder the project sits in, so the project's own
folder and DaVis's `<name>.exp` beside it share one namespace:

    Project_Tomo_Setup.exp
    Project_Tomo_Setup/Properties/Calibration/Calibration.xml
    Project_Tomo_Setup/Working/Full_Mixing_Settling_Time_Dataset/Camera1-0.ims
    Project_Tomo_Setup/Working/Full_Mixing_Settling_Time_Dataset.set

**A recording** is a folder with a `.set` file of the same name beside it
whose folder holds data directly (`StreamSet.xml`, or image and vector files)
-- as opposed to a group such as `Working/`, which only holds recordings.
Processed results are folders *inside* a recording and belong to it. Its
identity is the `SetTime` DaVis writes into the `.set` file, which survives a
rename in DaVis (daviskit.io.read_set_file).

`Properties/` is the project's calibrations and settings: always copied, never
a recording, never "safe to delete". `Properties/Temp/` is scratch and skipped.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

#: Folders never copied, relative to the project folder.
SKIP_DIRS = {"Properties/Temp"}
#: Our own bookkeeping, and half-written copies, are never inventoried.
OWN = (".experimentkit", ".versions")
PARTIAL = ".partial"
#: A folder holding any of these directly is a recording, not a group.
RECORDING_MARKERS = {"StreamSet.xml"}
RECORDING_SUFFIXES = {".ims", ".im7", ".imx", ".vc7", ".set"}


@dataclass(frozen=True)
class FileEntry:
    rel: str  # posix, relative to the project's parent folder
    size: int
    mtime_ns: int


@dataclass
class Recording:
    """One recording: its folder, its .set, its identity, and every file it owns."""

    rel: str  # the folder, e.g. "Project_Tomo_Setup/Working/Full_Mixing_Settling_Time_Dataset"
    set_time: str
    files: list[str] = field(default_factory=list)  # includes the .set file
    size: int = 0
    newest_ns: int = 0

    @property
    def name(self) -> str:
        return self.rel.split("/", 1)[-1]


def set_time(set_file: Path) -> str:
    """The recording time DaVis wrote into a .set file, or '' if it has none."""
    try:
        from daviskit.io.project import read_set_file
    except ImportError:  # daviskit absent: the one line it would parse, parsed here
        text = set_file.read_text(encoding="utf8", errors="replace")
        m = re.search(r'SetTime\s*=\s*"([^"]*)"', text)
        return m.group(1) if m else ""
    return read_set_file(set_file).get("SetTime", "")


def inventory(source: Path) -> dict[str, FileEntry]:
    """Every file of a project -- its folder, the .exp and the .qc folder beside it -- by path.

    Paths are relative to the project's parent folder, so all three share one namespace.
    """
    source = Path(source)
    parent = source.parent
    files: dict[str, FileEntry] = {}
    exp = parent / f"{source.name}.exp"
    if exp.is_file():
        st = exp.stat()
        files[exp.name] = FileEntry(exp.name, st.st_size, st.st_mtime_ns)
    files.update(walk(source, parent))
    qc = parent / f"{source.name}.qc"
    if qc.is_dir():
        files.update(walk(qc, parent))
    return files


def walk(folder: Path, parent: Path) -> dict[str, FileEntry]:
    """Every file under `folder` (skipping scratch, our bookkeeping and half-copies),
    by path relative to `parent`."""
    files: dict[str, FileEntry] = {}
    source = Path(folder)
    for dirpath, dirnames, filenames in os.walk(source):
        here = Path(dirpath)
        rel_dir = here.relative_to(source).as_posix()
        dirnames[:] = [d for d in dirnames if d not in OWN and
                       (f"{rel_dir}/{d}" if rel_dir != "." else d) not in SKIP_DIRS]
        for name in filenames:
            if name.endswith(PARTIAL):
                continue
            path = here / name
            try:
                st = path.stat()
            except OSError:  # vanished or locked mid-walk; the next run sees it
                continue
            rel = path.relative_to(parent).as_posix()
            files[rel] = FileEntry(rel, st.st_size, st.st_mtime_ns)
    return files


def recordings(source: Path, files: dict[str, FileEntry]) -> list[Recording]:
    """The recordings in a project, each with the files it owns (see module docstring)."""
    source = Path(source)
    parent = source.parent
    found: dict[str, Recording] = {}
    for rel in files:
        if not rel.endswith(".set"):
            continue
        folder_rel = rel[: -len(".set")]
        folder = parent / folder_rel
        top = folder_rel.split("/", 2)
        if len(top) < 2 or top[1] == "Properties" or not folder.is_dir():
            continue
        holds_data = any((folder / m).exists() for m in RECORDING_MARKERS) or any(
            Path(n).suffix.lower() in RECORDING_SUFFIXES - {".set"} for n in os.listdir(folder))
        if not holds_data:
            continue
        found[folder_rel] = Recording(rel=folder_rel, set_time=set_time(parent / rel))
    # A processed result has its own .set too, but sits INSIDE its recording
    # (seen 2026-09-18: Power_A90_B85/ParticleSeedingDensity_threshold=10.set) and is
    # deleted with it in DaVis: it is part of the recording, not one of its own.
    for folder_rel in sorted(found, key=len):
        if any(folder_rel.startswith(other + "/") for other in found if other != folder_rel):
            del found[folder_rel]
    # every file under a recording's folder belongs to it, results included
    for rel, entry in files.items():
        owner = None
        for folder_rel in found:
            if rel == f"{folder_rel}.set" or rel.startswith(folder_rel + "/"):
                owner = folder_rel
        if owner:
            r = found[owner]
            r.files.append(rel)
            r.size += entry.size
            r.newest_ns = max(r.newest_ns, entry.mtime_ns)
    return sorted(found.values(), key=lambda r: r.rel)
