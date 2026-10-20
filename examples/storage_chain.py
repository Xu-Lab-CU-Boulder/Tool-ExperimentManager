"""Run the storage chain C: -> work -> backup on throwaway folders, then forecast free space.

Shows, on a fake two-recording DaVis project:

- docs/algorithms/safe-to-delete.md: every recording's state before and after a
  phased sync, and that "safe to delete" needs both copies and the backup re-read;
- docs/algorithms/checksummed-copy.md and ledger-replay.md: the ledger lines the
  copy wrote, with the SHA-256 fingerprint and the verification level;
- docs/algorithms/recording-matching.md: a recording renamed on C: (same SetTime)
  is matched to its existing copy, not copied again;
- docs/algorithms/storage-forecast.md: `storage usage` on a fabricated free-space log.

Everything lives in a new temporary folder: the "C:", "G:" and "F:" folders, the
registry (EXPERIMENTKIT_STORAGE) and the volume search path
(EXPERIMENTKIT_VOLUME_ROOTS) are pointed there before anything runs, so the real
registry in AppData and the real drives are never touched. QC is not run (it needs
daviskit and real recordings).

    .venv/Scripts/python examples/storage_chain.py
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import tempfile
import time
from pathlib import Path

OLD = time.time() - 3600  # an hour ago: past the 10-minute quiet period


def write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    os.utime(path, (OLD, OLD))


def fake_project(c_drive: Path) -> Path:
    """Properties, and two recordings (folder + .set with a SetTime), one with a result."""
    root = c_drive / "Project_Example" / "Tank"
    write(root.parent / "Tank.exp", b"#GROUP Experiment\n")
    write(root / "Properties.set", b"SetType = 8192;\n")
    write(root / "Properties" / "Calibration" / "Calibration.xml", b"<cal/>")
    for name, when, size in (("Tow_A", "Fri Sep 18 10:24:55 2026", 400_000),
                             ("Tow_B", "Fri Sep 18 11:02:10 2026", 250_000)):
        write(root / name / "StreamSet.xml", b"<stream/>")
        write(root / name / "Camera1-0.ims", os.urandom(size))
        write(root / f"{name}.set", f'SetType = 4352;\nSetTime = "{when}";\n'.encode())
    write(root / "Tow_B" / "PIV_result" / "B00001.vc7", os.urandom(30_000))
    write(root / "Tow_B" / "PIV_result.set", b'SetTime = "Fri Sep 18 12:00:00 2026";\n')
    return root


def show(title: str, st) -> None:
    print(f"\n{title}")
    for rec, state, why in st.recordings:
        print(f"  {rec.name:<10} {state:<28} {why}")


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="ek_storage_chain_"))
    c, g, f = tmp / "C", tmp / "G", tmp / "F"
    for d in (c, g, f):
        d.mkdir()
    os.environ["EXPERIMENTKIT_STORAGE"] = str(tmp / "registry" / "storage.toml")
    os.environ["EXPERIMENTKIT_VOLUME_ROOTS"] = os.pathsep.join(map(str, (g, f)))

    from experimentkit.storage import cli, registry, sync, volumes
    from experimentkit.storage.ledger import Ledger

    source = fake_project(c)
    volumes.init_volume(g, "example-work-01", "work")
    volumes.init_volume(f, "example-backup-01", "backup")
    project = registry.add_project(source, "example-work-01", "example-backup-01")
    drives = volumes.find_volumes()
    print(f"drives found: {sorted(drives)}  (in {tmp})")

    show("before any sync:", sync.status(project, drives))

    # Only the work drive connected: copied and fingerprinted, but nothing is safe yet.
    results, st = sync.sync_project(project, volumes={"example-work-01": drives["example-work-01"]})
    show("after a sync with the backup unplugged:", st)

    results, st = sync.sync_project(project, volumes=drives, phased=True)
    for r in results:
        print(f"  {r.stage}: copied {r.copied}, skipped {r.skipped}" + (f" -- {r.waiting}" if r.waiting else ""))
    show("after a phased sync with both drives (copy, copy, re-read the backup):", st)

    wl = Ledger(g / project.name)
    rel = "Tank/Tow_A/Camera1-0.ims"
    print(f"\nwork-drive ledger state of {rel}:\n  {wl.state(rel)}")
    print("last three ledger lines on the backup:")
    for line in (f / project.name / ".experimentkit" / "ledger.jsonl").read_text().splitlines()[-3:]:
        print("  " + line)

    # Rename a recording on C: (DaVis keeps its SetTime): matched, not re-copied.
    os.replace(source / "Tow_A", source / "Tow_A_renamed")
    os.replace(source / "Tow_A.set", source / "Tow_A_renamed.set")
    results, st = sync.sync_project(project, volumes=drives)
    for r in results:
        print(f"  {r.stage}: copied {r.copied}, skipped {r.skipped}, matched {r.matched}")
    show("after renaming Tow_A on C: and syncing again:", st)

    # A fabricated free-space log: the work drive loses 50 GB a day for six days.
    log = sync.usage_path(project)
    start = dt.datetime(2026, 10, 1, 9, 0)
    with log.open("w", encoding="utf8") as fh:
        for day in range(7):
            free = 2_000e9 - 50e9 * day
            fh.write(json.dumps({"at": (start + dt.timedelta(days=day)).isoformat(),
                                 "drives": {"example-work-01": {"total": 7_300e9,
                                                                "used": 7_300e9 - free,
                                                                "free": free}}}) + "\n")
    print("\nstorage usage on a fabricated log (expect 50 GB/day, full in ~34 days):")
    cli.cmd_usage(argparse.Namespace(project=None, plot=None))


if __name__ == "__main__":
    main()
