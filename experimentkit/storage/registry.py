"""Which projects on this PC are kept, and on which drives. One small TOML file per PC.

    %APPDATA%\\experimentkit\\storage.toml     (EXPERIMENTKIT_STORAGE overrides the path)

    [[project]]
    name = "Project_Tomo_Setup"
    source = "C:/Users/LaVision/Documents/Project_Hula_Hoop/Project_Tomo_Setup"
    work = "xulab-work-01"
    backup = "xulab-backup-01"
    qc_mirror = "C:/.../Paper-Hula-Hooping-Jellyfish/3_experiments/qc"

Per PC because the source paths are this PC's paths (design doc, open question 1).
On each drive a project lives at `<drive>/<name>/`, with DaVis's `<name>.exp`
beside it -- the same layout DaVis uses on C:, so the copy opens in DaVis.

**The QC database** (daviskit's validation and calibration history, and the
trend figures) lives beside the project too, in `<name>.qc/` -- outside the
DaVis folder, since daviskit never writes inside one -- so a snapshot of the
project includes it. `qc_mirror` is a second home for the QC database alone,
on OneDrive (decided 2026-09-19).
"""

from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SyncProject:
    """One DaVis project and the drives it is kept on."""

    name: str
    source: Path
    work: str
    backup: str | None = None
    qc_mirror: Path | None = None

    @property
    def exp_file(self) -> Path:
        """DaVis's project descriptor, which sits BESIDE the project folder."""
        return self.source.parent / f"{self.source.name}.exp"

    @property
    def qc_dir(self) -> Path:
        """The QC database, beside the project folder (never inside it)."""
        return self.source.parent / f"{self.source.name}.qc"

    @property
    def keep_file(self) -> Path:
        """Recordings to keep on C: whatever the drives hold (storage.keep)."""
        return self.source.parent / f"{self.source.name}.keep"


def registry_path() -> Path:
    override = os.environ.get("EXPERIMENTKIT_STORAGE")
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "experimentkit" / "storage.toml"


def load_projects() -> list[SyncProject]:
    """Every registered project; none if the registry does not exist yet."""
    path = registry_path()
    if not path.exists():
        return []
    data = tomllib.loads(path.read_text(encoding="utf8"))
    return [SyncProject(name=p["name"], source=Path(p["source"]), work=p["work"],
                        backup=p.get("backup") or None,
                        qc_mirror=Path(p["qc_mirror"]) if p.get("qc_mirror") else None)
            for p in data.get("project", [])]


def add_project(source: str | Path, work: str, backup: str | None = None,
                name: str | None = None, qc_mirror: str | Path | None = None) -> SyncProject:
    """Register a DaVis project. Its folder must contain Properties/ (a DaVis project root)."""
    source = Path(source).resolve()
    if not (source / "Properties").is_dir():
        raise ValueError(f"{source} has no Properties folder, so it is not a DaVis project root")
    project = SyncProject(name=name or source.name, source=source, work=work, backup=backup,
                          qc_mirror=Path(qc_mirror).resolve() if qc_mirror else None)
    projects = [p for p in load_projects() if p.name != project.name] + [project]
    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Projects experimentkit keeps on the work and backup drives. One PC's view.\n"]
    for p in projects:
        lines.append(f'\n[[project]]\nname = "{p.name}"\nsource = "{p.source.as_posix()}"\n'
                     f'work = "{p.work}"\n'
                     + (f'backup = "{p.backup}"\n' if p.backup else "")
                     + (f'qc_mirror = "{p.qc_mirror.as_posix()}"\n' if p.qc_mirror else ""))
    path.write_text("".join(lines), encoding="utf8")
    return project
