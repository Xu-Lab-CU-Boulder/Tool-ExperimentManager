"""Keep each DaVis project snapshotted on the work drive (from C:) and the backup (from work).

Design: docs/design/storage-sync.md. The rules that matter:

- **Accumulate, never mirror.** Nothing on a drive is deleted to match C:; a
  changed file's older copy is moved to `.versions/<time>/`, not overwritten
  (the QC folder excepted: it only grows, see `_keep_versions`).
- **Nothing on C: is ever written or deleted** by the copy. (The QC step writes
  its own `<name>.qc/` folder beside the project; never inside DaVis's folder.)
- **The work drive's layout is the user's** (decided 2026-09-19). A recording on
  C: is matched to its copy on the work drive by the `SetTime` DaVis wrote into
  its `.set`, wherever that copy sits; only a recording new to the drive is
  placed at C:'s path, and a rename on C: just updates the match. The backup
  follows the work drive's layout, moving its own copies to match.
- **Everything on the work drive is backed up**, including recordings that
  have already left C: (archived by hand before this tool existed): those are
  fingerprinted as they are read from the work drive.
- **A drive that is not connected is not an error.** Its step waits.
- **A project that changed in the last QUIET_MINUTES is left alone** (a
  recording or processing is probably running), unless the run says `now`.
- **`.set` files are copied last**, so a half-copied recording never appears
  as a recording in DaVis on the drive.
- **Safe to delete from C:** every file the recording has on C: now is on both
  drives, matches its fingerprint, and the backup copy has been re-read in full.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import keep
from .inventory import FileEntry, Recording, inventory, recordings, walk
from .ledger import Ledger, copy_hashing, hash_file
from .registry import SyncProject
from .volumes import Volume, find_volumes

QUIET_MINUTES = 10


def _same_time(a_ns: int | None, b_ns: int | None) -> bool:
    """Equal to the second: copies across file systems may lose sub-second precision."""
    return a_ns is not None and b_ns is not None and abs(a_ns - b_ns) < 2_000_000_000


def _stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def _set_last(items):
    return sorted(items, key=lambda kv: kv[0].endswith(".set"))


def _keep_versions(project: SyncProject, rel: str, old_size: int, new_size: int) -> bool:
    """Whether a changed file's older copy is kept. The QC folder only grows (its
    JSON Lines databases are append-only; its CSVs and figures are rebuilt from
    them), so a larger new copy replaces the old one -- except a database that
    SHRANK, which is kept, since that should never happen."""
    if rel.startswith(f"{project.name}.qc/"):
        return new_size < old_size and rel.endswith(".jsonl")
    return True


@dataclass
class StageResult:
    """What one stage (C: -> work, or work -> backup) did, or would do."""

    stage: str
    copied: int = 0
    bytes: int = 0
    skipped: int = 0
    adopted: int = 0
    versioned: int = 0
    matched: list[tuple[str, str]] = field(default_factory=list)  # C: path, drive path
    renamed: list[tuple[str, str]] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    waiting: str = ""  # why the stage did not run


def _replace(base: Path, project: SyncProject, rel: str, ledger: Ledger, stamp: str,
             old_size: int, new_size: int, result: StageResult) -> None:
    """Move an existing copy aside (or drop it, for the QC folder) before copying over it."""
    old = base / rel
    if _keep_versions(project, rel, old_size, new_size):
        keep = base / project.name / ".versions" / stamp / rel
        keep.parent.mkdir(parents=True, exist_ok=True)
        os.replace(old, keep)
        ledger.add("version", rel=rel, moved_to=keep.relative_to(base).as_posix())
        result.versioned += 1


def drive_recordings(root: Path, project: str) -> dict[str, str]:
    """Recordings already on a drive: folder rel -> SetTime, read from their .set files."""
    target = root / project
    if not target.is_dir():
        return {}
    files = walk(target, root)
    return {r.rel: r.set_time for r in recordings(target, files)}


def _match(rec: Recording, ledger: Ledger, on_drive: dict[str, str]) -> str:
    """Where a C: recording lives on the work drive (see module docstring)."""
    if rec.rel in ledger.source_map:
        return ledger.source_map[rec.rel]
    if rec.set_time:
        known = [rel for rel, t in ledger.recordings.items() if t == rec.set_time]
        found = known or [rel for rel, t in on_drive.items() if t == rec.set_time]
        if rec.rel in found:
            return rec.rel
        if len(found) == 1:
            return found[0]
        leaf = rec.rel.rsplit("/", 1)[-1]
        same_name = [rel for rel in found if rel.rsplit("/", 1)[-1] == leaf]
        if len(same_name) == 1:
            return same_name[0]
    return rec.rel


def _to_drive(rel: str, owners: dict[str, str]) -> str:
    """A C: file path as a path on the work drive, through its recording's match."""
    for src, dst in owners.items():
        if rel == f"{src}.set" or rel.startswith(src + "/"):
            return dst + rel[len(src):]
    return rel


def sync_to_work(project: SyncProject, work: Volume, files: dict[str, FileEntry],
                 recs: list[Recording], *, dry_run: bool = False,
                 only: set[str] | None = None) -> StageResult:
    """C: -> work: copy what is new or changed, fingerprinting as it reads C:.

    `only` limits the copy to those source-relative paths, which is how a phased
    sync moves one recording at a time (see `sync_project(phased=True)`).
    """
    result = StageResult("C: -> " + work.id)
    base = work.root
    ledger = Ledger(base / project.name)
    parent = project.source.parent
    on_drive = drive_recordings(base, project.name) if not ledger.source_map else {}
    owners: dict[str, str] = {}
    # deepest recordings first, so a file is mapped by the recording that owns it
    for rec in sorted(recs, key=lambda r: -len(r.rel)):
        dst = _match(rec, ledger, on_drive)
        owners[rec.rel] = dst
        if dst != rec.rel:
            result.matched.append((rec.rel, dst))
        if not dry_run and (ledger.source_map.get(rec.rel) != dst
                            or ledger.recordings.get(dst) != rec.set_time):
            ledger.add("recording", rel=dst, set_time=rec.set_time, source_rel=rec.rel)
    stamp = _stamp()
    for rel, e in _set_last(files.items()):
        if only is not None and rel not in only:
            continue
        drive_rel = _to_drive(rel, owners)
        src, dst = parent / rel, base / drive_rel
        state = ledger.state(drive_rel)
        try:
            dst_stat = dst.stat() if dst.exists() else None
            if (state and state["size"] == e.size and state["source_mtime_ns"] == e.mtime_ns
                    and dst_stat and dst_stat.st_size == e.size and not state.get("mismatch")):
                result.skipped += 1
                continue
            if (not state and dst_stat and dst_stat.st_size == e.size
                    and _same_time(dst_stat.st_mtime_ns, e.mtime_ns)):
                # already there, copied by hand: fingerprint C:'s bytes, keep the copy
                result.adopted += 1
                if not dry_run:
                    ledger.add("adopt", rel=drive_rel, source_rel=rel, size=e.size,
                               source_mtime_ns=e.mtime_ns, sha256=hash_file(src), verified=None)
                continue
            result.copied += 1
            result.bytes += e.size
            if dry_run:
                continue
            if dst_stat:
                _replace(base, project, drive_rel, ledger, stamp, dst_stat.st_size, e.size, result)
            sha = copy_hashing(src, dst)
            ledger.add("copy", rel=drive_rel, source_rel=rel, size=e.size,
                       source_mtime_ns=e.mtime_ns, sha256=sha, verified=None)
        except OSError as exc:  # locked by DaVis, drive pulled: next run retries
            result.problems.append(f"{rel}: {exc}")
    return result


def _follow_layout(backup: Volume, bl: Ledger, work_recs: dict[str, str],
                   result: StageResult, dry_run: bool) -> None:
    """Move the backup's copies to where the work drive keeps them (matched by SetTime)."""
    have = dict(bl.recordings) or drive_recordings(backup.root, bl.target.name)
    by_time: dict[str, list[str]] = {}
    for rel, t in have.items():
        if t and rel not in work_recs:
            by_time.setdefault(t, []).append(rel)
    for new, t in work_recs.items():
        if new in have or not t or len(by_time.get(t, [])) != 1:
            continue
        old = by_time[t][0]
        root = backup.root
        if not (root / old).exists() or (root / new).exists():
            continue
        result.renamed.append((old, new))
        if dry_run:
            continue
        (root / new).parent.mkdir(parents=True, exist_ok=True)
        os.replace(root / old, root / new)
        if (root / f"{old}.set").exists():
            os.replace(root / f"{old}.set", root / f"{new}.set")
        bl.add("rename", old=old, new=new)


def sync_to_backup(project: SyncProject, work: Volume, backup: Volume, *,
                   dry_run: bool = False, only: set[str] | None = None) -> StageResult:
    """work -> backup: copy everything the backup lacks, verifying the work copy as it is read.

    `only` limits it to those work-drive-relative paths, for a phased sync.
    """
    result = StageResult(f"{work.id} -> {backup.id}")
    wl = Ledger(work.root / project.name)
    bl = Ledger(backup.root / project.name)
    work_files = walk(work.root / project.name, work.root)
    qc = work.root / f"{project.name}.qc"
    if qc.is_dir():
        work_files.update(walk(qc, work.root))
    exp = work.root / f"{project.name}.exp"
    if exp.is_file():
        st = exp.stat()
        work_files[exp.name] = FileEntry(exp.name, st.st_size, st.st_mtime_ns)
    work_recs = drive_recordings(work.root, project.name)
    if not dry_run:  # recordings only on the work drive (archived by hand) are recordings too
        for rel, t in work_recs.items():
            if wl.recordings.get(rel) != t:
                wl.add("recording", rel=rel, set_time=t)
    _follow_layout(backup, bl, work_recs, result, dry_run)
    if not dry_run:
        for rel, t in work_recs.items():
            if bl.recordings.get(rel) != t:
                bl.add("recording", rel=rel, set_time=t)
    stamp = _stamp()
    for rel, we in _set_last(work_files.items()):
        if only is not None and rel not in only:
            continue
        ws = wl.state(rel)
        src, dst = work.root / rel, backup.root / rel
        bs = bl.state(rel)
        try:
            dst_stat = dst.stat() if dst.exists() else None
            fingerprint = ws["sha256"] if ws else None
            # already on the backup: skip unless it is known to differ (a mismatch found by a
            # re-read, or a newer copy on the work drive); an unfingerprinted hand copy is
            # left for the re-read to judge rather than copied again
            if (bs and dst_stat and dst_stat.st_size == we.size and not bs.get("mismatch")
                    and (bs["sha256"] is None or fingerprint is None
                         or bs["sha256"] == fingerprint)):
                result.skipped += 1
                continue
            if (not bs and dst_stat and dst_stat.st_size == we.size
                    and _same_time(dst_stat.st_mtime_ns, we.mtime_ns)):
                result.adopted += 1  # a hand copy: the background re-read checks it
                if not dry_run:
                    if not ws:
                        wl.add("adopt", rel=rel, size=we.size, source_mtime_ns=we.mtime_ns,
                               sha256=None, verified=None)
                    bl.add("adopt", rel=rel, size=we.size, source_mtime_ns=we.mtime_ns,
                           sha256=fingerprint, verified=None)
                continue
            result.copied += 1
            result.bytes += we.size
            if dry_run:
                continue
            if dst_stat:
                _replace(backup.root, project, rel, bl, stamp, dst_stat.st_size, we.size, result)
            sha = copy_hashing(src, dst)
            if not ws:  # on the work drive only: this read is its fingerprint
                wl.add("adopt", rel=rel, size=we.size, source_mtime_ns=we.mtime_ns,
                       sha256=sha, verified=None)
                fingerprint = sha
            bl.add("copy", rel=rel, size=we.size, source_mtime_ns=we.mtime_ns,
                   sha256=sha, verified=None)
            ok = sha == fingerprint
            wl.add("verify", rel=rel, sha256=sha, ok=ok, how="transit")
            if ok:
                bl.add("verify", rel=rel, sha256=sha, ok=True, how="transit")
            else:
                result.problems.append(f"{rel}: the work copy does not match its fingerprint "
                                       "from C: -- it will be re-copied from C: on the next sync")
        except OSError as exc:
            result.problems.append(f"{rel}: {exc}")
    return result


def verify(project: SyncProject, volume: Volume, *, role: str, budget_gb: float | None = None,
           only: set[str] | None = None,
           reference: Ledger | None = None) -> tuple[int, int, list[str]]:
    """Re-read copies on a drive and compare with their fingerprints. Resumable.

    On the backup, every file not yet re-read in full, compared with the work
    drive's fingerprint (`reference`, when the work drive is connected); on the
    work drive, every file not yet verified at all (hand copies; files that live
    only there, whose first read becomes their fingerprint). `only` limits it to
    some files; `budget_gb` stops after that much reading. Returns (files
    checked, bytes read, problems).
    """
    ledger = Ledger(volume.root / project.name)
    checked = read = 0
    problems = []
    for rel, st in list(ledger.files.items()):
        if only is not None and rel not in only:
            continue
        needed = st.get("verified") != "full" if role == "backup" else st.get("verified") is None
        path = volume.root / rel
        if not needed or not path.exists():
            continue
        expected = st.get("sha256")
        if reference is not None and (ref := reference.state(rel)) and ref.get("sha256"):
            expected = ref["sha256"]
        if role == "backup" and expected is None:
            continue  # its fingerprint comes from the work drive's re-read first
        if budget_gb is not None and read > budget_gb * 1e9:
            break
        sha = hash_file(path)
        ok = expected is None or sha == expected
        ledger.add("verify", rel=rel, sha256=sha, ok=ok, how="full")
        checked += 1
        read += st["size"] or 0
        if not ok:
            problems.append(f"{rel} on {volume.id} does not match its fingerprint")
    return checked, read, problems


# -- status ------------------------------------------------------------------------------------

SAFE, REREAD, WORK_ONLY, NEEDS_SYNC, C_ONLY, KEPT = (
    "safe to delete", "waiting for backup re-read", "on work only",
    "new or changed on C:", "on C: only", "kept on C:")


def safely_backed_up(wl: Ledger, bl: Ledger | None, rel: str) -> bool:
    """Is every file of this recording on the work drive and re-read on the backup?

    The question `classify` asks of a recording on C:, asked of one that has left it.
    """
    if bl is None:
        return False
    files = [r for r in wl.files if r == rel or r.startswith(rel + "/") or r == f"{rel}.set"]
    if not files:
        return False
    return all((b := bl.state(r)) and b.get("verified") == "full" for r in files)


def classify(rec: Recording, files: dict[str, FileEntry], wl: Ledger | None,
             bl: Ledger | None, patterns: list[str] | None = None) -> tuple[str, str]:
    """Where one recording stands, and the first reason it is not yet safe to delete.

    A recording listed in the project's `.keep` file is backed up and verified
    like any other; it is reported as KEPT rather than as safe to delete.
    """
    if wl is None or rec.rel not in wl.source_map:
        return C_ONLY, ""
    owners = {rec.rel: wl.source_map[rec.rel]}
    mapped = [(rel, _to_drive(rel, owners)) for rel in rec.files]
    if not any(wl.state(d) for _, d in mapped):
        return C_ONLY, ""
    for rel, d in mapped:
        e, w = files[rel], wl.state(d)
        if not w or w["size"] != e.size or w["source_mtime_ns"] != e.mtime_ns:
            return NEEDS_SYNC, f"{rel.rsplit('/', 1)[-1]} not yet on the work drive"
    for _, d in mapped:
        w, b = wl.state(d), bl.state(d) if bl else None
        if not b or (b["sha256"] and b["sha256"] != w["sha256"]):
            return WORK_ONLY, "not yet on the backup"
    for _, d in mapped:
        w, b = wl.state(d), bl.state(d)
        if w.get("verified") not in ("transit", "full"):
            return REREAD, "work copy not yet verified"
        if b.get("verified") != "full":
            return REREAD, "backup copy not yet re-read"
    if patterns and keep.matches(rec.name, patterns):
        return KEPT, "both copies verified; listed in the .keep file"
    return SAFE, ""


@dataclass
class ProjectStatus:
    """One project: its drives, and where each recording stands."""

    project: SyncProject
    work: Volume | None
    backup: Volume | None
    source_bytes: int
    free_bytes: int
    quiet: bool
    minutes_since_change: float
    recordings: list[tuple[Recording, str, str]]  # recording, state, reason
    other_pending: int  # files outside recordings (Properties, .exp, .qc) not yet on work
    gone_unsafe: list[str]
    archived: list[str]
    duplicates: list[list[str]] = field(default_factory=list)  # same recording, several places
    archive_only: int = 0  # recordings on the work drive that have left C:
    backup_pending_files: int = 0  # files on the work drive not yet re-read on the backup

    def by_state(self, state: str) -> list[tuple[Recording, str]]:
        return [(r, why) for r, s, why in self.recordings if s == state]


def status(project: SyncProject, volumes: dict[str, Volume] | None = None,
           files: dict[str, FileEntry] | None = None) -> ProjectStatus:
    """Where a project stands. Reads only; writes nothing anywhere."""
    volumes = find_volumes() if volumes is None else volumes
    files = inventory(project.source) if files is None else files
    recs = recordings(project.source, files)
    work, backup = volumes.get(project.work), volumes.get(project.backup or "")
    wl = Ledger(work.root / project.name) if work else None
    bl = Ledger(backup.root / project.name) if backup else None
    # QC output and the keep list are ours and the user's, not the camera's:
    # touching them must not make a project look like it is still recording.
    ours = (f"{project.name}.qc/", f"{project.name}.keep")
    newest = max((e.mtime_ns for rel, e in files.items()
                  if not rel.startswith(ours)), default=0)
    minutes = (time.time_ns() - newest) / 60e9
    owned = {rel for r in recs for rel in r.files}
    other = sum(1 for rel, e in files.items() if rel not in owned and not
                (wl and (s := wl.state(rel)) and s["size"] == e.size
                 and s["source_mtime_ns"] == e.mtime_ns))
    patterns = keep.read_patterns(project.keep_file)
    current = {wl.source_map.get(r.rel, r.rel) for r in recs} if wl else set()
    # A recording that left C: is judged against the drives *now*, not against the
    # flag it carried when it vanished. On 2026-09-20 three recordings were moved to
    # another disk by hand to free space, and were backed up and re-read hours later;
    # without this they would have kept crying "lost too early" for ever, and an alarm
    # that cannot clear itself is an alarm people learn to ignore.
    gone_unsafe, archived = [], []
    for rel, safe in (wl.gone.items() if wl else []):
        if rel in current:
            continue
        (archived if safe or safely_backed_up(wl, bl, rel) else gone_unsafe).append(rel)
    gone_unsafe, archived = sorted(gone_unsafe), sorted(archived)
    duplicates, archive_only, pending = [], 0, 0
    if wl:
        by_time: dict[str, list[str]] = {}
        for rel, t in wl.recordings.items():
            if t:
                by_time.setdefault(t, []).append(rel)
        duplicates = [sorted(v) for v in by_time.values() if len(v) > 1]
        archive_only = sum(1 for rel in wl.recordings if rel not in current)
        pending = sum(1 for rel in wl.files
                      if not bl or not (s := bl.state(rel)) or s.get("verified") != "full")
    return ProjectStatus(
        project=project, work=work, backup=backup,
        source_bytes=sum(e.size for e in files.values()),
        free_bytes=shutil.disk_usage(project.source).free,
        quiet=minutes >= QUIET_MINUTES, minutes_since_change=minutes,
        recordings=[(r, *classify(r, files, wl, bl, patterns)) for r in recs],
        other_pending=other, gone_unsafe=gone_unsafe, archived=archived,
        duplicates=duplicates, archive_only=archive_only, backup_pending_files=pending)


# -- the whole run ------------------------------------------------------------------------------

def lower_priority() -> None:
    """Run at background CPU and disk priority, so a recording started mid-sync is not starved."""
    if sys.platform == "win32":
        import ctypes

        kernel = ctypes.windll.kernel32
        kernel.SetPriorityClass(kernel.GetCurrentProcess(), 0x00100000)  # BACKGROUND_BEGIN
    else:
        os.nice(10)


def mirror_qc(project: SyncProject) -> int:
    """Copy the QC database to its second home (OneDrive), overwriting what changed."""
    if project.qc_mirror is None or not project.qc_dir.is_dir():
        return 0
    copied = 0
    for rel, e in walk(project.qc_dir, project.qc_dir).items():
        dst = project.qc_mirror / rel
        if dst.exists() and dst.stat().st_size == e.size and _same_time(dst.stat().st_mtime_ns,
                                                                          e.mtime_ns):
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(project.qc_dir / rel, dst)
        copied += 1
    return copied


#: Written while a sync is copying, so anyone can see it is happening and no one
#: unplugs a drive mid-write; removed when the run ends, however it ends.
RUNNING = "sync-running.json"
#: Touch this and the running sync stops cleanly at the next recording boundary.
PAUSED = "sync-paused"


def running_path(project: SyncProject) -> Path:
    return project.source.parent / f"{project.source.name}.{RUNNING}"


def pause_path(project: SyncProject) -> Path:
    return project.source.parent / f"{project.source.name}.{PAUSED}"


def running(project: SyncProject) -> dict | None:
    """What a sync is doing right now, or None. Stale markers (no such process) are ignored."""
    path = running_path(project)
    if not path.is_file():
        return None
    try:
        state = json.loads(path.read_text(encoding="utf8"))
    except (OSError, json.JSONDecodeError):
        return None
    pid = state.get("pid")
    if pid and not _alive(pid):
        state["stale"] = True
    return state


def _alive(pid: int) -> bool:
    """Is that process still running? A crashed sync must not look like a live one."""
    if sys.platform == "win32":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                             capture_output=True, text=True)
        return str(pid) in out.stdout
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    return True


def _mark_running(project: SyncProject, **state) -> None:
    path = running_path(project)
    try:
        path.write_text(json.dumps({"pid": os.getpid(), "at": _stamp(), **state}, indent=2),
                        encoding="utf8")
    except OSError:
        pass


def _clear_running(project: SyncProject) -> None:
    try:
        running_path(project).unlink(missing_ok=True)
    except OSError:
        pass


def _phased(project: SyncProject, work: Volume, backup: Volume | None,
            files: dict[str, FileEntry], recs: list[Recording], *,
            dry_run: bool) -> list[StageResult]:
    """One recording at a time, oldest first: to the work drive, to the backup, re-read.

    The whole-project order (everything to work, then everything to backup, then a
    nightly re-read) means nothing is safe to delete until the last stage finishes.
    With 470 GB waiting and C: nearly full -- 2026-09-20 -- that is the difference
    between freeing space in forty minutes and freeing it tomorrow. Here each
    recording is carried the whole way and marked deletable before the next starts.
    """
    results: list[StageResult] = []
    wl = Ledger(work.root / project.name)
    todo = sorted(recs, key=lambda r: r.newest_ns)
    for n, rec in enumerate(todo, 1):
        if pause_path(project).is_file():
            results.append(StageResult("paused", waiting=(
                f"paused after {n - 1} of {len(todo)} recording(s); "
                f"`experimentkit storage resume` to carry on")))
            break
        owned = set(rec.files)
        if all((s := wl.state(_to_drive(rel, wl.source_map))) and s.get("verified") == "full"
               for rel in owned):
            continue  # already through the whole chain
        if not dry_run:
            _mark_running(project, recording=rec.name, step=f"{n} of {len(todo)}",
                          stage=f"C: -> {work.id}", bytes=rec.size)
        to_work = sync_to_work(project, work, files, recs, dry_run=dry_run, only=owned)
        to_work.stage = f"{rec.name}: C: -> {work.id}"
        results.append(to_work)
        if backup is None:
            results.append(StageResult(f"{rec.name}: {work.id} -> {project.backup}",
                                       waiting="backup drive not connected"))
            continue
        drive = {_to_drive(rel, Ledger(work.root / project.name).source_map) for rel in owned}
        if not dry_run:
            _mark_running(project, recording=rec.name, step=f"{n} of {len(todo)}",
                          stage=f"{work.id} -> {backup.id}", bytes=rec.size)
        to_backup = sync_to_backup(project, work, backup, dry_run=dry_run, only=drive)
        to_backup.stage = f"{rec.name}: {work.id} -> {backup.id}"
        results.append(to_backup)
        if not dry_run:
            _mark_running(project, recording=rec.name, step=f"{n} of {len(todo)}",
                          stage=f"re-reading {backup.id}", bytes=rec.size)
            checked, read, bad = verify(project, backup, role="backup", only=drive,
                                        reference=Ledger(work.root / project.name))
            note = f"{rec.name}: re-read {checked} file(s) on {backup.id}"
            results.append(StageResult(note, waiting="; ".join(bad) if bad else ""))
    return results


def sync_project(project: SyncProject, *, now: bool = False, dry_run: bool = False,
                 volumes: dict[str, Volume] | None = None, run_qc=None,
                 phased: bool = False) -> tuple[list[StageResult], ProjectStatus]:
    """One sync of one project: QC of what is new, both copy stages if their drives are
    here, then bookkeeping. `run_qc(project, files, recs)` is the QC step (qc.run_qc).

    `phased` carries one recording at a time all the way to a verified backup, so
    space can be freed while the rest is still copying.
    """
    volumes = find_volumes() if volumes is None else volumes
    files = inventory(project.source)
    before = status(project, volumes, files)
    results: list[StageResult] = []

    if pause_path(project).is_file():
        # a pause stops everything, scheduled runs included -- not just the copying
        return [StageResult("paused", waiting="paused by the user; "
                            "`experimentkit storage resume` to carry on")], before
    if not now and not before.quiet:
        r = StageResult("C: -> " + project.work)
        r.waiting = (f"project changed {before.minutes_since_change:.0f} min ago "
                     f"(< {QUIET_MINUTES}): a recording or processing may be running")
        return [r], before
    if not dry_run:
        _mark_running(project, stage="starting", recording="", step="")
    if run_qc is not None and not dry_run:
        run_qc(project, files, recordings(project.source, files))
        files = inventory(project.source)  # the QC folder has grown
    recs = recordings(project.source, files)
    work, backup = before.work, before.backup
    if work is None:
        results.append(StageResult("C: -> " + project.work, waiting="work drive not connected"))
    elif phased:
        results += _phased(project, work, backup, files, recs, dry_run=dry_run)
    else:
        results.append(sync_to_work(project, work, files, recs, dry_run=dry_run))
    if project.backup and not phased:
        if backup is None or work is None:
            missing = "backup drive" if backup is None else "work drive"
            results.append(StageResult(f"{project.work} -> {project.backup}",
                                       waiting=f"{missing} not connected"))
        else:
            results.append(sync_to_backup(project, work, backup, dry_run=dry_run))

    after = status(project, volumes, files)
    if not dry_run and work is not None:
        wl = Ledger(work.root / project.name)
        for rec, state, _ in after.recordings:
            target = wl.source_map.get(rec.rel, rec.rel)
            # KEPT means "verified, but the user wants it here": the ledger
            # still records that both copies are good, so a kept recording that
            # is deleted later is not mistaken for one lost too early.
            if state in (SAFE, KEPT) and target not in wl.deletable:
                wl.add("deletable", rel=target)
        current = {wl.source_map.get(r.rel, r.rel) for r in recs}
        for rel in list(wl.source_map.values()):
            if rel not in current and rel not in wl.gone:
                wl.add("gone", rel=rel, safe=rel in wl.deletable)
        after = status(project, volumes, files)
    if not dry_run:
        mirror_qc(project)
        _clear_running(project)
    return results, after
