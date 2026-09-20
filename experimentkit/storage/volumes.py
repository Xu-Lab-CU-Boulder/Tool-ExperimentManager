"""Drives, known by what they say they are, not by the letter Windows gave them today.

Each drive carries a `VOLUME.toml` at its root:

    [volume]
    id = "xulab-work-01"        # also written on a sticker on the drive
    purpose = "work"            # or "backup"
    usual_host = "LaVision DaVis PC"
    created = "2026-09-19"

The drives are portable (design doc, section 2): G: today may be E: next week,
and either may be unplugged. So a drive is found by looking for its id on
whatever is connected, and a drive that is not connected is simply absent --
never an error, never "missing data".
"""

from __future__ import annotations

import datetime as dt
import os
import re
import string
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

VOLUME_FILE = "VOLUME.toml"
_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
PURPOSES = ("work", "backup")


@dataclass(frozen=True)
class Volume:
    """A drive that identified itself: its id, what it is for, and where it is mounted now."""

    id: str
    purpose: str
    root: Path
    usual_host: str = ""


def read_volume(root: str | Path) -> Volume | None:
    """The volume whose root this is, or None if it has no readable VOLUME.toml."""
    root = Path(root)
    try:
        data = tomllib.loads((root / VOLUME_FILE).read_text(encoding="utf8"))["volume"]
        return Volume(id=data["id"], purpose=data.get("purpose", ""), root=root,
                      usual_host=data.get("usual_host", ""))
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        return None


def init_volume(root: str | Path, volume_id: str, purpose: str, usual_host: str = "") -> Volume:
    """Write VOLUME.toml at a drive's root. Refuses to relabel a drive that already has an id."""
    root = Path(root)
    if not _ID.match(volume_id):
        raise ValueError(f"volume id {volume_id!r}: lowercase letters, digits and hyphens, "
                         "e.g. 'xulab-work-01'")
    if purpose not in PURPOSES:
        raise ValueError(f"purpose must be one of {PURPOSES}")
    if not root.is_dir():
        raise FileNotFoundError(f"{root} is not a connected drive or folder")
    existing = read_volume(root)
    if existing and existing.id != volume_id:
        raise FileExistsError(f"{root} is already volume {existing.id!r}; "
                              "a drive keeps its id for life (it is on the sticker)")
    text = (f'[volume]\nid = "{volume_id}"\npurpose = "{purpose}"\n'
            f'usual_host = "{usual_host}"\ncreated = "{dt.date.today().isoformat()}"\n')
    (root / VOLUME_FILE).write_text(text, encoding="utf8")
    return read_volume(root)


def candidate_roots() -> list[Path]:
    """Where drives may be mounted. EXPERIMENTKIT_VOLUME_ROOTS (os.pathsep-separated) overrides."""
    override = os.environ.get("EXPERIMENTKIT_VOLUME_ROOTS")
    if override is not None:
        return [Path(p) for p in override.split(os.pathsep) if p]
    if sys.platform == "win32":
        return [Path(f"{letter}:/") for letter in string.ascii_uppercase
                if os.path.exists(f"{letter}:/")]
    # macOS mounts at /Volumes/<name>; Linux at /media/<user>/<name> or /mnt/<name>
    patterns = (("/Volumes", "*"), ("/media", "*/*"), ("/mnt", "*"))
    return [p for base, pattern in patterns if Path(base).is_dir()
            for p in Path(base).glob(pattern) if p.is_dir()]


def find_volumes() -> dict[str, Volume]:
    """Every connected drive that has a VOLUME.toml, by id."""
    found: dict[str, Volume] = {}
    for root in candidate_roots():
        vol = read_volume(root)
        if vol:
            found.setdefault(vol.id, vol)
    return found
