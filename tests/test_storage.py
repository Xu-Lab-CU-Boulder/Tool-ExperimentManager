"""Project storage sync, end to end on throwaway folders standing in for C:, G: and F:.

Each test checks one promise of docs/design/storage-sync.md: nothing on C: is
written or deleted; a disconnected drive waits; nothing is deletable until
both copies exist and the backup has been re-read; the work drive's own layout
is matched by SetTime and the backup follows it; recordings only on the work
drive are backed up too; a busy project is left alone; older copies are kept;
QC runs with the sync and its folder is snapshotted and mirrored.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from experimentkit.__main__ import main
from experimentkit.storage import registry, sync, volumes
from experimentkit.storage.ledger import Ledger

OLD = time.time() - 3600  # an hour ago: past the quiet period


def _write(path: Path, data: bytes, when: float = OLD) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    os.utime(path, (when, when))
    return path


def _set_file(path: Path, set_time: str) -> Path:
    return _write(path, f'SetType = 4352;\nSetTime = "{set_time}";\n'.encode())


def make_project(c_drive: Path) -> Path:
    """A small DaVis project: calibrations, scratch, a group, two recordings, one result."""
    parent = c_drive / "Project_Hula_Hoop"
    root = parent / "Tank"
    _write(parent / "Tank.exp", b"#GROUP Experiment\n")
    _write(root / "Properties.set", b"SetType = 8192;\n")
    _write(root / "Properties" / "Calibration" / "Calibration.xml", b"<cal v='1'/>")
    _write(root / "Properties" / "Temp" / "scratch.tmp", b"scratch")
    rec = root / "Tow_A"
    _write(rec / "StreamSet.xml", b"<stream/>")
    _write(rec / "Camera1-0.ims", os.urandom(300_000))
    _set_file(root / "Tow_A.set", "Fri Sep 18 10:24:55 2026")
    _write(root / "Working.set", b"SetType = 4352;\n")
    grp = root / "Working" / "Settle"
    _write(grp / "StreamSet.xml", b"<stream/>")
    _write(grp / "Camera1-0.ims", os.urandom(200_000))
    _set_file(root / "Working" / "Settle.set", "Fri Sep 18 09:07:00 2026")
    _write(grp / "PSD_threshold=10" / "JobHistory.xml", b"<JobSequence/>")
    _write(grp / "PSD_threshold=10" / "B00001.im7", os.urandom(50_000))
    _set_file(grp / "PSD_threshold=10.set", "Fri Sep 18 11:00:00 2026")  # results get one too
    return root


def snapshot(root: Path) -> dict[str, tuple[int, int]]:
    return {p.relative_to(root).as_posix(): (p.stat().st_size, p.stat().st_mtime_ns)
            for p in root.rglob("*") if p.is_file()}


@pytest.fixture()
def rig(tmp_path, monkeypatch):
    """C:, a work drive and a backup drive, labelled, and one registered project."""
    c, g, f = tmp_path / "C", tmp_path / "G", tmp_path / "F"
    for d in (c, g, f):
        d.mkdir()
    source = make_project(c)
    monkeypatch.setenv("EXPERIMENTKIT_STORAGE", str(tmp_path / "storage.toml"))
    monkeypatch.setenv("EXPERIMENTKIT_VOLUME_ROOTS", os.pathsep.join(map(str, (g, f))))
    volumes.init_volume(g, "xulab-work-01", "work")
    volumes.init_volume(f, "xulab-backup-01", "backup")
    project = registry.add_project(source, "xulab-work-01", "xulab-backup-01")

    class Rig:
        pass

    r = Rig()
    r.c, r.g, r.f, r.source, r.project = c, g, f, source, project
    r.unplug = lambda *drives: monkeypatch.setenv(
        "EXPERIMENTKIT_VOLUME_ROOTS",
        os.pathsep.join(str(d) for d in (g, f) if d not in drives))
    return r


def states(project) -> dict[str, str]:
    return {r.name: s for r, s, _ in sync.status(project).recordings}


def test_recordings_own_their_results(rig):
    from experimentkit.storage.inventory import inventory, recordings

    recs = {r.name: r for r in recordings(rig.source, inventory(rig.source))}
    assert sorted(recs) == ["Tow_A", "Working/Settle"], "a result is not a recording of its own"
    settle = recs["Working/Settle"]
    assert "Tank/Working/Settle/PSD_threshold=10.set" in settle.files
    assert "Tank/Working/Settle/PSD_threshold=10/B00001.im7" in settle.files
    assert settle.set_time == "Fri Sep 18 09:07:00 2026"


def test_volumes_are_found_by_id_not_letter(rig, tmp_path, monkeypatch):
    moved = tmp_path / "E"
    rig.g.rename(moved)  # the same drive, mounted under another letter
    monkeypatch.setenv("EXPERIMENTKIT_VOLUME_ROOTS", str(moved))
    assert volumes.find_volumes()["xulab-work-01"].root == moved
    with pytest.raises(FileExistsError):
        volumes.init_volume(moved, "xulab-work-02", "work")  # a drive keeps its id


def test_first_sync_copies_everything_but_scratch_and_never_touches_c(rig):
    before = snapshot(rig.c)
    results, st = sync.sync_project(rig.project)
    assert snapshot(rig.c) == before, "C: must only be read"
    work = rig.g / "Tank"
    assert (rig.g / "Tank.exp").exists(), "the .exp beside the project folder comes too"
    assert (work / "Working" / "Settle" / "PSD_threshold=10" / "B00001.im7").exists()
    assert not (work / "Properties" / "Temp").exists()
    assert (rig.f / "Tank" / "Tow_A" / "Camera1-0.ims").read_bytes() == \
        (rig.source / "Tow_A" / "Camera1-0.ims").read_bytes()
    assert all(r.copied and not r.problems for r in results)
    # copied in transit and verified then, but the backup not yet re-read: not deletable
    assert set(states(rig.project).values()) == {sync.REREAD}
    again, _ = sync.sync_project(rig.project)
    assert [r.copied for r in again] == [0, 0], "a second sync copies nothing"


def test_deletable_only_after_the_backup_is_reread(rig):
    sync.sync_project(rig.project)
    found = volumes.find_volumes()
    n, _, bad = sync.verify(rig.project, found["xulab-backup-01"], role="backup")
    assert n > 0 and not bad
    assert set(states(rig.project).values()) == {sync.SAFE}


def test_a_missing_backup_waits_and_catches_up(rig):
    rig.unplug(rig.f)
    results, _ = sync.sync_project(rig.project)
    assert results[1].waiting == "backup drive not connected"
    assert set(states(rig.project).values()) == {sync.WORK_ONLY}
    rig.unplug()  # plugged back in
    results, _ = sync.sync_project(rig.project)
    assert results[0].copied == 0 and results[1].copied > 0
    assert set(states(rig.project).values()) == {sync.REREAD}


def test_a_busy_project_is_left_alone_unless_asked(rig):
    _write(rig.source / "Tow_A" / "Camera1-1.ims", b"still streaming", when=time.time())
    results, _ = sync.sync_project(rig.project)
    assert "may be running" in results[0].waiting and not (rig.g / "Tank").exists()
    results, _ = sync.sync_project(rig.project, now=True)
    assert results[0].copied > 0


def test_a_new_result_makes_a_recording_not_safe_until_copied(rig):
    sync.sync_project(rig.project)
    sync.verify(rig.project, volumes.find_volumes()["xulab-backup-01"], role="backup")
    _write(rig.source / "Tow_A" / "PSD_threshold=10" / "B00001.im7", b"new result")
    assert states(rig.project)["Tow_A"] == sync.NEEDS_SYNC
    sync.sync_project(rig.project)
    assert states(rig.project)["Tow_A"] == sync.REREAD


def test_changed_files_keep_their_older_copy(rig):
    sync.sync_project(rig.project)
    cal = rig.source / "Properties" / "Calibration" / "Calibration.xml"
    _write(cal, b"<cal v='2'/>", when=OLD + 60)
    results, _ = sync.sync_project(rig.project)
    assert results[0].versioned == 1
    kept = list((rig.g / "Tank" / ".versions").rglob("Calibration.xml"))
    assert kept and kept[0].read_bytes() == b"<cal v='1'/>"
    assert (rig.g / "Tank" / "Properties" / "Calibration" / "Calibration.xml").read_bytes() \
        == b"<cal v='2'/>"


def test_a_rename_on_c_keeps_its_match_and_copies_nothing(rig):
    """The work drive's layout is the user's: a rename on C: updates the match only."""
    sync.sync_project(rig.project)
    os.replace(rig.source / "Tow_A", rig.source / "Tow_A_toy_jellyfish")
    os.replace(rig.source / "Tow_A.set", rig.source / "Tow_A_toy_jellyfish.set")
    results, st = sync.sync_project(rig.project)
    assert results[0].matched == [("Tank/Tow_A_toy_jellyfish", "Tank/Tow_A")]
    assert results[0].copied == 0 and results[1].copied == 0
    assert (rig.g / "Tank" / "Tow_A" / "Camera1-0.ims").exists()
    assert {r.name: s for r, s, _ in st.recordings}["Tow_A_toy_jellyfish"] == sync.REREAD
    assert not st.gone_unsafe, "a renamed recording has not left C:"


def test_the_work_drives_own_layout_is_matched_by_set_time(rig):
    """Recordings reorganised on the drive by hand are recognised, not copied again."""
    import shutil

    shutil.copytree(rig.source, rig.g / "Tank")
    shutil.copy2(rig.source.parent / "Tank.exp", rig.g / "Tank.exp")
    grp = rig.g / "Tank" / "Settling_Time"
    grp.mkdir()
    os.replace(rig.g / "Tank" / "Working" / "Settle", grp / "Settle")
    os.replace(rig.g / "Tank" / "Working" / "Settle.set", grp / "Settle.set")
    results, st = sync.sync_project(rig.project)
    assert ("Tank/Working/Settle", "Tank/Settling_Time/Settle") in results[0].matched
    assert results[0].copied == 0, "nothing re-copied: it was already there, elsewhere"
    assert not (rig.g / "Tank" / "Working" / "Settle").exists()
    assert (rig.f / "Tank" / "Settling_Time" / "Settle" / "Camera1-0.ims").exists(), \
        "the backup follows the work drive's layout"


def test_recordings_only_on_the_work_drive_are_backed_up(rig):
    """Archived by hand before this tool: their only copy is on the work drive."""
    old = rig.g / "Tank" / "Dt_Sweep" / "Power_19.5ms"
    _write(old / "StreamSet.xml", b"<stream/>")
    _write(old / "Camera1-0.ims", os.urandom(120_000))
    _set_file(rig.g / "Tank" / "Dt_Sweep" / "Power_19.5ms.set", "Fri Sep 18 10:24:55 2025")
    sync.sync_project(rig.project)
    copy = rig.f / "Tank" / "Dt_Sweep" / "Power_19.5ms" / "Camera1-0.ims"
    assert copy.read_bytes() == (old / "Camera1-0.ims").read_bytes()
    st = sync.status(rig.project)
    assert st.archive_only == 1
    wl = Ledger(rig.g / "Tank")
    assert wl.state("Tank/Dt_Sweep/Power_19.5ms/Camera1-0.ims")["sha256"], "fingerprinted"


def test_the_backup_follows_the_work_drives_layout(rig):
    sync.sync_project(rig.project)
    # someone reorganised the backup by hand: its copy sits under another name
    os.replace(rig.f / "Tank" / "Tow_A", rig.f / "Tank" / "Tow_A_old_name")
    os.replace(rig.f / "Tank" / "Tow_A.set", rig.f / "Tank" / "Tow_A_old_name.set")
    Ledger(rig.f / "Tank").add("rename", old="Tank/Tow_A", new="Tank/Tow_A_old_name")
    results, _ = sync.sync_project(rig.project)
    assert results[1].renamed == [("Tank/Tow_A_old_name", "Tank/Tow_A")]
    assert results[1].copied == 0


def test_a_recording_in_two_places_on_the_drive_is_flagged(rig):
    import shutil

    sync.sync_project(rig.project)
    shutil.copytree(rig.g / "Tank" / "Tow_A", rig.g / "Tank" / "Copies" / "Tow_A")
    shutil.copy2(rig.g / "Tank" / "Tow_A.set", rig.g / "Tank" / "Copies" / "Tow_A.set")
    _, st = sync.sync_project(rig.project)
    assert ["Tank/Copies/Tow_A", "Tank/Tow_A"] in st.duplicates


def test_deleting_from_c_is_quiet_when_safe_and_loud_when_not(rig):
    sync.sync_project(rig.project)
    sync.verify(rig.project, volumes.find_volumes()["xulab-backup-01"], role="backup")
    sync.sync_project(rig.project)  # records Tow_A and Settle as deletable
    for name in ("Tow_A",):
        for p in sorted((rig.source / name).rglob("*"), reverse=True):
            p.unlink() if p.is_file() else p.rmdir()
        (rig.source / name).rmdir()
        (rig.source / f"{name}.set").unlink()
    _, st = sync.sync_project(rig.project)
    assert st.archived == ["Tank/Tow_A"] and not st.gone_unsafe
    assert (rig.f / "Tank" / "Tow_A" / "Camera1-0.ims").exists(), "the drives keep it"

    # a recording copied only to work, then lost from C:: loud
    _write(rig.source / "Fresh" / "StreamSet.xml", b"<stream/>")
    _set_file(rig.source / "Fresh.set", "Sat Sep 19 09:00:00 2026")
    rig.unplug(rig.f)
    sync.sync_project(rig.project)
    (rig.source / "Fresh" / "StreamSet.xml").unlink()
    (rig.source / "Fresh").rmdir()
    (rig.source / "Fresh.set").unlink()
    _, st = sync.sync_project(rig.project)
    assert st.gone_unsafe == ["Tank/Fresh"]


def test_hand_copies_are_adopted_not_recopied(rig):
    import shutil

    shutil.copytree(rig.source, rig.g / "Tank")  # copied by hand before this tool existed
    shutil.copy2(rig.source.parent / "Tank.exp", rig.g / "Tank.exp")
    results, _ = sync.sync_project(rig.project)
    assert results[0].copied == 0 and results[0].adopted > 0
    work = volumes.find_volumes()["xulab-work-01"]
    assert sync.verify(rig.project, work, role="work")[2] == []


def test_a_corrupted_copy_is_caught_and_recopied(rig):
    sync.sync_project(rig.project)
    target = rig.f / "Tank" / "Tow_A" / "Camera1-0.ims"
    data = bytearray(target.read_bytes())
    data[1000] ^= 0xFF
    target.write_bytes(bytes(data))
    _, _, bad = sync.verify(rig.project, volumes.find_volumes()["xulab-backup-01"], role="backup")
    assert bad and "Camera1-0.ims" in bad[0]
    assert states(rig.project)["Tow_A"] != sync.SAFE


def test_a_half_written_copy_never_counts(rig):
    sync.sync_project(rig.project)
    partial = rig.g / "Tank" / "Tow_A" / "Camera1-0.ims.partial"
    partial.write_bytes(b"torn")
    ledger = Ledger(rig.g / "Tank")
    assert "Tank/Tow_A/Camera1-0.ims.partial" not in ledger.files


def test_one_verify_run_finishes_a_work_only_recording(rig, capsys):
    """A file that lives only on the work drive gets its fingerprint from the work
    re-read, so the backup's copy can only be checked against it afterwards. Read
    the work ledger too early and the backup waits a whole second run -- which on
    the real drives left 1594 files unchecked overnight."""
    data = os.urandom(120_000)
    old = rig.g / "Tank" / "Dt_Sweep" / "Power_19.5ms"
    _write(old / "Camera1-0.ims", data)
    _set_file(rig.g / "Tank" / "Dt_Sweep" / "Power_19.5ms.set", "Fri Sep 18 10:24:55 2025")
    # already copied to the backup by hand too, so the sync reads neither side
    _write(rig.f / "Tank" / "Dt_Sweep" / "Power_19.5ms" / "Camera1-0.ims", data)
    _set_file(rig.f / "Tank" / "Dt_Sweep" / "Power_19.5ms.set", "Fri Sep 18 10:24:55 2025")
    sync.sync_project(rig.project)
    rel = "Tank/Dt_Sweep/Power_19.5ms/Camera1-0.ims"
    assert Ledger(rig.g / "Tank").state(rel)["sha256"] is None, "adopted, not read"
    assert main(["storage", "verify"]) == 0
    assert capsys.readouterr().out.count("MISMATCH") == 0
    assert Ledger(rig.f / "Tank").state(rel)["verified"] == "full", \
        "the backup copy is checked in the same run that fingerprints the work copy"


def test_the_scheduled_task_can_find_the_package(rig, capsys, monkeypatch):
    """A scheduled task starts in system32, where `-m experimentkit` only works
    if the package is installed. It is not, on the PIV workstation."""
    import experimentkit.storage.cli as cli

    root = str(Path(cli.__file__).resolve().parent.parent.parent)
    monkeypatch.setattr(cli, "_installed", lambda: False)
    assert main(["storage", "schedule"]) == 0
    out = capsys.readouterr().out
    assert out.count(f"cmd /c cd /d {root} &&") == 2, "both tasks start in the repo"

    monkeypatch.setattr(cli, "_installed", lambda: True)
    assert main(["storage", "schedule"]) == 0
    assert "cmd /c" not in capsys.readouterr().out


def test_cli_status_and_dry_run(rig, capsys):
    assert main(["storage", "sync", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "would copy" in out and "nothing was copied" in out
    assert not (rig.g / "Tank").exists()
    assert main(["storage", "status"]) == 0
    assert "on C: only" in capsys.readouterr().out


# -- QC with the sync ---------------------------------------------------------------------------

def _fake_measure(calls):
    """Stands in for daviskit's measurement: files a record under daviskit's key."""
    import json

    from experimentkit.storage.qc import recording_key

    def measure(folder, qc_dir, images):
        calls.append(folder.name)
        with (Path(qc_dir) / "validation.jsonl").open("a", encoding="utf8") as fh:
            fh.write(json.dumps({"key": recording_key(folder), "type": "dataset"}) + "\n")
        return f"{folder.name}: ppp 0.0150", ["ppp 5.1 robust SD above earlier recordings"]

    return measure


def test_qc_measures_new_recordings_once_within_a_budget(rig):
    pytest.importorskip("daviskit")
    from experimentkit.storage import qc
    from experimentkit.storage.inventory import inventory, recordings

    calls = []
    files = inventory(rig.source)
    recs = recordings(rig.source, files)
    res = qc.run_qc(rig.project, files, recs, budget=1, measure=_fake_measure(calls))
    assert len(res.validated) == 1 and len(res.pending) == 1
    assert res.validated[0][2], "drift warnings come back to the caller"
    qc.run_qc(rig.project, files, recs, budget=5, measure=_fake_measure(calls))
    assert sorted(calls) == ["Settle", "Tow_A"], "each recording is measured once"
    assert (rig.source.parent / "Tank.qc" / "validation.jsonl").exists()
    assert not (rig.source / "Tank.qc").exists(), "never inside DaVis's folder"


def test_the_qc_folder_is_snapshotted_and_mirrored_without_version_clutter(rig, tmp_path,
                                                                            monkeypatch):
    pytest.importorskip("daviskit")
    from experimentkit.storage import qc

    onedrive = tmp_path / "OneDrive" / "qc"
    _write(onedrive / "calibration.jsonl", b'{"key": "cal:1"}\n')  # where QC lived before
    project = registry.add_project(rig.source, "xulab-work-01", "xulab-backup-01",
                                   qc_mirror=onedrive)
    calls = []

    def run(p, files, recs):
        qc.run_qc(p, files, recs, budget=None, measure=_fake_measure(calls))

    sync.sync_project(project, run_qc=run)
    assert (rig.source.parent / "Tank.qc" / "calibration.jsonl").exists(), "seeded from OneDrive"
    assert (rig.g / "Tank.qc" / "validation.jsonl").exists()
    assert (rig.f / "Tank.qc" / "validation.jsonl").exists()
    assert (onedrive / "validation.jsonl").exists(), "mirrored to OneDrive"
    # a new recording appends to the database: the drives take the longer copy, keep no versions
    _write(rig.source / "Tow_B" / "StreamSet.xml", b"<stream/>")
    _set_file(rig.source / "Tow_B.set", "Sat Sep 19 10:00:00 2026")
    sync.sync_project(project, run_qc=run)
    assert calls.count("Tow_B") == 1
    assert b"Tow_B" in (rig.f / "Tank.qc" / "validation.jsonl").read_bytes()
    assert not list((rig.g / "Tank" / ".versions").rglob("validation.jsonl"))
