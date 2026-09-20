"""`experimentkit storage ...` -- the commands over sync.py. Design: docs/design/storage-sync.md.

    experimentkit storage volume <drive> --id xulab-work-01 --purpose work
    experimentkit storage add <DaVis project> --work xulab-work-01 --backup xulab-backup-01 \\
                              [--qc-mirror <OneDrive folder>]
    experimentkit storage status [--json]
    experimentkit storage sync [--project P] [--dry-run] [--now] [--background] [--no-qc]
    experimentkit storage qc [--backfill] [--budget N]
    experimentkit storage verify [--project P] [--budget-gb 200] [--background]
    experimentkit storage schedule          prints the hourly scheduled-task command
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from . import qc as qc_mod
from . import registry, sync, volumes
from .ledger import Ledger


def _gb(n: int) -> str:
    return f"{n / 1e9:,.1f} GB"


def _projects(name: str | None) -> list[registry.SyncProject]:
    projects = registry.load_projects()
    if not projects:
        raise SystemExit(f"No projects registered in {registry.registry_path()}.\n"
                         "Add one: experimentkit storage add <DaVis project> --work <id> "
                         "--backup <id>")
    if name:
        projects = [p for p in projects if p.name == name]
        if not projects:
            raise SystemExit(f"No registered project called {name!r}.")
    return projects


def _drive(vol: volumes.Volume | None, vol_id: str | None) -> str:
    if not vol_id:
        return "none"
    return f"{vol_id} ({vol.root}) connected" if vol else f"{vol_id} -- not connected"


def _qc_summary(project: registry.SyncProject) -> str:
    try:
        from daviskit.qc import latest, read_records
    except ImportError:
        return "QC: daviskit not installed"
    recs = latest(read_records(project.qc_dir / "validation.jsonl"))
    cals = read_records(project.qc_dir / "calibration.jsonl")
    return (f"QC: {len(recs)} recording(s) and {len(cals)} calibration record(s) in "
            f"{project.qc_dir}")


def print_status(st: sync.ProjectStatus) -> None:
    p = st.project
    print(f"{p.name}   C: {_gb(st.source_bytes)} ({_gb(st.free_bytes)} free)")
    print(f"  work:   {_drive(st.work, p.work)}")
    print(f"  backup: {_drive(st.backup, p.backup)}")
    if not st.quiet:
        print(f"  busy:   last change {st.minutes_since_change:.0f} min ago -- the hourly sync "
              "waits for a quiet project")
    for rel in st.gone_unsafe:
        print(f"  !! {rel} left C: before it was safe to delete -- check the drives now")
    safe = st.by_state(sync.SAFE)
    size = sum(r.size for r, _ in safe)
    print(f"  safe to delete from C:   {len(safe)} recording(s), {_gb(size)}"
          + ("   (delete them in DaVis)" if safe else ""))
    for r, _ in safe:
        print(f"      {r.name:<60} {_gb(r.size):>10}")
    for state in (sync.REREAD, sync.WORK_ONLY, sync.NEEDS_SYNC, sync.C_ONLY):
        rows = st.by_state(state)
        if rows:
            print(f"  {state + ':':<24} {len(rows)} recording(s), {_gb(sum(r.size for r, _ in rows))}")
            for r, why in rows:
                print(f"      {r.name:<60} {_gb(r.size):>10}" + (f"   {why}" if why else ""))
    if st.other_pending:
        print(f"  project files (Properties, .exp, .qc) not yet on work: {st.other_pending}")
    if st.work:
        print(f"  on the work drive only (already off C:): {st.archive_only} recording(s)")
    if st.backup_pending_files:
        print(f"  files on the work drive not yet re-read on the backup: {st.backup_pending_files}")
    for group in st.duplicates:
        print(f"  duplicate on the work drive (same recording, {len(group)} places): "
              + ", ".join(group))
    if st.archived:
        print(f"  archived (deleted from C: after both copies were verified): {len(st.archived)}")
    print(f"  {_qc_summary(p)}")


def _status_json(st: sync.ProjectStatus) -> dict:
    return {
        "project": st.project.name, "source": str(st.project.source),
        "source_bytes": st.source_bytes, "free_bytes": st.free_bytes,
        "work": {"id": st.project.work, "connected": bool(st.work)},
        "backup": {"id": st.project.backup, "connected": bool(st.backup)},
        "quiet": st.quiet, "minutes_since_change": round(st.minutes_since_change, 1),
        "recordings": [{"rel": r.rel, "set_time": r.set_time, "bytes": r.size,
                        "state": s, "reason": why} for r, s, why in st.recordings],
        "other_pending": st.other_pending, "archive_only": st.archive_only,
        "backup_pending_files": st.backup_pending_files, "duplicates": st.duplicates,
        "gone_unsafe": st.gone_unsafe, "archived": st.archived,
        "qc_dir": str(st.project.qc_dir),
    }


def _print_qc(name: str, res: qc_mod.QCResult) -> None:
    if res.skipped:
        print(f"{name}: QC skipped -- {res.skipped}")
        return
    if res.calibrations_added:
        print(f"{name}: QC: filed {res.calibrations_added} new calibration record(s)")
    for w in res.calibration_warnings:
        print(f"    ! calibration: {w}")
    for rec, line, warnings in res.validated:
        print(f"{name}: QC: {line}")
        for w in warnings:
            print(f"    ! {w}")
    if res.pending:
        print(f"{name}: QC: {len(res.pending)} recording(s) left for the next run")
    for msg in res.problems:
        print(f"    ! {msg}")


def cmd_volume(args) -> int:
    vol = volumes.init_volume(args.drive, args.id, args.purpose, args.host)
    print(f"{vol.root} is now volume {vol.id} ({vol.purpose}). Put the same name on a sticker.")
    return 0


def cmd_add(args) -> int:
    p = registry.add_project(args.project, args.work, args.backup, args.name, args.qc_mirror)
    print(f"registered {p.name}: {p.source} -> {p.work}" + (f" -> {p.backup}" if p.backup else ""))
    print(f"  QC database: {p.qc_dir}" + (f"  (mirrored to {p.qc_mirror})" if p.qc_mirror else ""))
    print(f"  registry: {registry.registry_path()}")
    return 0


def cmd_status(args) -> int:
    found = volumes.find_volumes()
    states = [sync.status(p, found) for p in _projects(args.project)]
    if args.json:
        json.dump([_status_json(s) for s in states], sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        for st in states:
            print_status(st)
            print()
    return 1 if any(s.gone_unsafe for s in states) else 0


def cmd_sync(args) -> int:
    if args.background:
        sync.lower_priority()
    found = volumes.find_volumes()
    problems = 0
    for p in _projects(args.project):
        qc_results = []

        def run_qc(project, files, recs, _out=qc_results):
            _out.append(qc_mod.run_qc(project, files, recs, budget=args.qc_budget))

        results, st = sync.sync_project(p, now=args.now, dry_run=args.dry_run, volumes=found,
                                        run_qc=None if args.no_qc else run_qc)
        for res in qc_results:
            _print_qc(p.name, res)
            problems += len(res.problems)
        verb = "would copy" if args.dry_run else "copied"
        for r in results:
            if r.waiting:
                print(f"{p.name}: {r.stage}: waiting -- {r.waiting}")
                continue
            extra = []
            if r.adopted:
                extra.append(f"{r.adopted} already there (hand copies), "
                             + ("to be fingerprinted" if args.dry_run else "fingerprinted"))
            if r.versioned:
                extra.append(f"{r.versioned} older copies kept in .versions/")
            if r.renamed:
                extra.append(f"{len(r.renamed)} moved to match the work drive's layout")
            print(f"{p.name}: {r.stage}: {verb} {r.copied} file(s), {_gb(r.bytes)}; "
                  f"{r.skipped} unchanged" + ("; " + "; ".join(extra) if extra else ""))
            for src, dst in r.matched:
                print(f"    matched {src} (C:) -> {dst} (work drive)")
            for old, new in r.renamed:
                print(f"    moved {old} -> {new}")
            for msg in r.problems[:20]:
                print(f"    ! {msg}")
            if len(r.problems) > 20:
                print(f"    ! ... and {len(r.problems) - 20} more")
            problems += len(r.problems)
        print()
        print_status(st)
        print()
    if args.dry_run:
        print("--dry-run: nothing was copied or recorded (QC not run).")
    return 1 if problems else 0


def cmd_qc(args) -> int:
    found = volumes.find_volumes()
    problems = 0
    for p in _projects(args.project):
        if args.backfill:
            work = found.get(p.work)
            if work is None:
                print(f"{p.name}: work drive {p.work} not connected -- nothing to back-fill from")
                continue
            files = sync.inventory(p.source)
            on_c = {Ledger(work.root / p.name).source_map.get(r.rel, r.rel)
                    for r in sync.recordings(p.source, files)}
            only = sorted(rel for rel in sync.drive_recordings(work.root, p.name)
                          if rel not in on_c)
            print(f"{p.name}: {len(only)} recording(s) only on {p.work}; measuring those not "
                  "yet in the QC database (reading the drive) ...")
            res = qc_mod.backfill(p, work.root, only, budget=args.budget)
        else:
            files = sync.inventory(p.source)
            res = qc_mod.run_qc(p, files, sync.recordings(p.source, files), budget=args.budget)
        _print_qc(p.name, res)
        problems += len(res.problems)
        sync.mirror_qc(p)
    return 1 if problems else 0


def cmd_verify(args) -> int:
    if args.background:
        sync.lower_priority()
    found = volumes.find_volumes()
    problems = []
    for p in _projects(args.project):
        work, backup = found.get(p.work), found.get(p.backup or "")
        # the work drive first: files that live only there get their fingerprint from it
        for role, vol_id, vol in (("work", p.work, work), ("backup", p.backup, backup)):
            if vol is None:
                if vol_id:
                    print(f"{p.name}: {vol_id} not connected -- its re-read waits")
                continue
            # Read the work ledger here rather than before the loop: the work
            # re-read just above is what gives a file that lives only there its
            # fingerprint, and a backup copy with nothing to compare against is
            # skipped. Taken too early, the whole backup waits a second run.
            reference = Ledger(work.root / p.name) if role == "backup" and work else None
            n, read, bad = sync.verify(p, vol, role=role, budget_gb=args.budget_gb,
                                       reference=reference)
            print(f"{p.name}: {vol_id}: re-read {n} file(s), {_gb(read)}"
                  + (f"; {len(bad)} MISMATCH" if bad else ""))
            problems += bad
    for msg in problems:
        print(f"  ! {msg}")
    return 1 if problems else 0


def cmd_schedule(args) -> int:
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe") if exe.with_name("pythonw.exe").exists() else exe
    run = f'"{pyw}" -m experimentkit storage sync --background'
    check = f'"{pyw}" -m experimentkit storage verify --background --budget-gb 300'
    print("Hourly sync (with QC), and a nightly re-read of the copies, as Windows scheduled")
    print("tasks. Run these yourself (they change the PC's scheduled tasks):\n")
    print(f'schtasks /Create /SC HOURLY /TN "experimentkit storage sync" /TR "{run}" /F')
    print(f'schtasks /Create /SC DAILY /ST 02:00 /TN "experimentkit storage verify" '
          f'/TR "{check}" /F')
    print("\nRemove with: schtasks /Delete /TN \"experimentkit storage sync\" /F")
    return 0


def add_storage_parser(sub) -> None:
    """Register `storage` and its subcommands on experimentkit's parser."""
    st = sub.add_parser("storage", help="keep DaVis projects on the work and backup drives")
    ssub = st.add_subparsers(dest="storage_cmd", required=True)

    v = ssub.add_parser("volume", help="label a drive: write VOLUME.toml at its root")
    v.add_argument("drive")
    v.add_argument("--id", required=True, help="e.g. xulab-work-01 (also on its sticker)")
    v.add_argument("--purpose", required=True, choices=volumes.PURPOSES)
    v.add_argument("--host", default="", help="the PC it usually lives on")
    v.set_defaults(fn=cmd_volume)

    a = ssub.add_parser("add", help="register a DaVis project on this PC")
    a.add_argument("project", help="the DaVis project folder (holds Properties/)")
    a.add_argument("--work", required=True, help="work drive id")
    a.add_argument("--backup", help="backup drive id")
    a.add_argument("--name", help="folder name on the drives (default: the project's)")
    a.add_argument("--qc-mirror", help="second home for the QC database (e.g. on OneDrive)")
    a.set_defaults(fn=cmd_add)

    s = ssub.add_parser("status", help="what is where, and what is safe to delete from C:")
    s.add_argument("--project")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_status)

    y = ssub.add_parser("sync", help="QC what is new, then copy C: -> work -> backup")
    y.add_argument("--project")
    y.add_argument("--dry-run", action="store_true", help="report what would be copied")
    y.add_argument("--now", action="store_true",
                   help=f"run even if the project changed in the last {sync.QUIET_MINUTES} min")
    y.add_argument("--background", action="store_true", help="low CPU and disk priority")
    y.add_argument("--no-qc", action="store_true", help="copy only; measure nothing")
    y.add_argument("--qc-budget", type=int, default=3,
                   help="new recordings to measure per run (default 3)")
    y.set_defaults(fn=cmd_sync)

    q = ssub.add_parser("qc", help="measure new recordings and calibrations into the QC database")
    q.add_argument("--project")
    q.add_argument("--backfill", action="store_true",
                   help="measure recordings that are only on the work drive now")
    q.add_argument("--budget", type=int, help="at most this many recordings")
    q.set_defaults(fn=cmd_qc)

    r = ssub.add_parser("verify", help="re-read the copies on the drives (resumable)")
    r.add_argument("--project")
    r.add_argument("--budget-gb", type=float, help="stop after reading this much")
    r.add_argument("--background", action="store_true", help="low CPU and disk priority")
    r.set_defaults(fn=cmd_verify)

    c = ssub.add_parser("schedule", help="print the commands for the hourly and nightly tasks")
    c.set_defaults(fn=cmd_schedule)
