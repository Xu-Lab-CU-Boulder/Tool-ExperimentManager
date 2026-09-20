"""Ingest stage 1: where every clip would go, with nothing copied.

The rule under test is *never guess*. Each way a clip can be uncertain -- no
slate, codes that disagree, an experiment the project does not have, two
unlabelled cameras colliding -- must end as unsorted or conflict with a reason,
never as a confident destination. And a dry run must not change a single byte,
on the card or in the project.
"""

from __future__ import annotations

import json
import os

import pytest

pytest.importorskip("cv2", reason="ingest reads frames with OpenCV")
pytest.importorskip("markertracker", reason="ingest reads clips with markertracker")

from conftest import frames_for, label, snapshot, write_sequence, write_video

from experimentkit import ingest as ingest_mod
from experimentkit.__main__ import main
from experimentkit.clips import LabelError, find_clips
from experimentkit.payload import parse

ID = "20260212_hooper1_vertical-swimming"
SLATE3 = f"pk1:{ID}:take03"


# -- payloads -----------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    (SLATE3, (ID, 3, None)),
    (f"pk1:{ID}:take03:sync:0007", (ID, 3, 7)),
    (f"pk1:{ID}:take120", (ID, 120, None)),
])
def test_slate_payloads_parse(text, expected):
    code = parse(text)
    assert (code.dataset_id, code.take, code.sync) == expected


@pytest.mark.parametrize("text", [
    "https://example.com/product",       # somebody else's QR code in the scene
    f"pk2:{ID}:take03",                    # a format this version does not know
    f"pk1:{ID}:take3",                     # the slate always pads to two digits
    f"pk1:{ID}:take00",
    "pk1:../escape:take01",                # not a usable dataset id
    f"pk1:{ID}:take03:sync:7",
])
def test_anything_else_is_ignored_not_guessed(text):
    assert parse(text) is None


# -- finding clips ---------------------------------------------------------------

def test_videos_and_image_folders_are_clips_and_labels_are_not(tmp_path):
    card = tmp_path / "card"
    write_video(card / "DCIM" / "100GOPRO" / "GX010001.MP4", frames_for(1))
    write_sequence(card / "triton" / "take", frames_for(0.2))
    label(card, "cam-left")
    (card / "DCIM" / "notes.txt").write_text("x", encoding="utf-8")
    (card / "System Volume Information").mkdir()
    (card / "System Volume Information" / "junk.mp4").write_text("x", encoding="utf-8")

    clips, ignored = find_clips(card)
    kinds = {c.path.name: (c.kind, c.files) for c in clips}
    assert kinds == {"GX010001.MP4": ("video", 1), "take": ("sequence", 6)}
    assert [p.name for p in ignored] == ["notes.txt"], "reported, not silently dropped"


# -- the plan --------------------------------------------------------------------

def plan(project, card, **kw):
    kw.setdefault("window_seconds", 1.0)
    return ingest_mod.plan_ingest(card, project, **kw)


def test_a_slated_clip_is_filed_by_experiment_take_and_camera(project, dataset, tmp_path):
    card = tmp_path / "card"
    label(card, "cam-left")
    write_video(card / "DCIM" / "GX010001.MP4", frames_for(3, head=[SLATE3]))

    [entry] = plan(project, card).clips
    assert entry.status == ingest_mod.FILE
    assert entry.destination == (project.stage_dir("raw") / ID / "take03"
                                 / "cam-left" / "GX010001.MP4")


def test_a_tail_slate_is_found_when_the_start_was_forgotten(project, dataset, tmp_path):
    card = tmp_path / "card"
    label(card, "cam-top")
    write_video(card / "clip.mp4", frames_for(4, tail=[SLATE3]))

    [entry] = plan(project, card).clips
    assert entry.status == ingest_mod.FILE
    assert {s.where for s in entry.reading.sightings} == {"tail"}


def test_an_image_sequence_is_filed_as_one_folder(project, dataset, tmp_path):
    card = tmp_path / "capture"
    label(card, "triton-1")
    write_sequence(card / "run_0001", frames_for(2, head=[SLATE3]))

    [entry] = plan(project, card).clips
    assert entry.status == ingest_mod.FILE
    assert entry.destination.name == "run_0001"
    assert entry.destination.parent.name == "triton-1"


def test_sync_codes_identify_the_take_and_are_reported(project, dataset, tmp_path):
    card = tmp_path / "card"
    label(card, "cam-left")
    codes = [f"{SLATE3}:sync:{k:04d}" for k in range(3)]
    write_video(card / "clip.mp4", frames_for(4, head=codes, hold=0.5))

    # Three codes held 0.5 s each span 1.5 s, so the window must be wider.
    [entry] = plan(project, card, window_seconds=2.0).clips
    assert entry.status == ingest_mod.FILE
    assert entry.reading.sync_range("head") == (0, 2)


# -- never guess -------------------------------------------------------------------

def test_no_slate_is_unsorted(project, dataset, tmp_path):
    card = tmp_path / "card"
    write_video(card / "clip.mp4", frames_for(3))
    [entry] = plan(project, card).clips
    assert entry.status == ingest_mod.UNSORTED
    assert "no slate found" in entry.reason
    assert entry.destination is None


def test_codes_that_disagree_are_unsorted(project, dataset, tmp_path):
    """A clip naming two takes -- the operator re-slated mid-clip -- is not
    certain enough to file."""
    card = tmp_path / "card"
    write_video(card / "clip.mp4",
                frames_for(4, head=[SLATE3], tail=[f"pk1:{ID}:take04"]))
    [entry] = plan(project, card).clips
    assert entry.status == ingest_mod.UNSORTED
    assert "disagree" in entry.reason and "take03" in entry.reason and "take04" in entry.reason


def test_an_experiment_the_project_does_not_have_is_unsorted(project, tmp_path):
    card = tmp_path / "card"
    write_video(card / "clip.mp4", frames_for(3, head=[SLATE3]))
    [entry] = plan(project, card).clips
    assert entry.status == ingest_mod.UNSORTED
    assert "projectkit dataset new" in entry.reason


def test_a_sidecar_from_a_newer_projectkit_is_unsorted(project, dataset, tmp_path):
    document = json.loads(dataset.path.read_text(encoding="utf-8"))
    document["schema_version"] = "2.0"
    dataset.path.write_text(json.dumps(document), encoding="utf-8")

    card = tmp_path / "card"
    write_video(card / "clip.mp4", frames_for(3, head=[SLATE3]))
    [entry] = plan(project, card).clips
    assert entry.status == ingest_mod.UNSORTED
    assert "newer projectkit" in entry.reason


def test_unlabelled_cameras_are_told_apart_by_folder(project, dataset, tmp_path):
    """Two GoPros write the same filename. Different folders are different
    cameras, so they must not land on one path."""
    card = tmp_path / "cards"
    write_video(card / "gopro-a" / "GX010001.MP4", frames_for(3, head=[SLATE3]))
    write_video(card / "gopro-b" / "GX010001.MP4", frames_for(3, head=[SLATE3], ), )

    entries = plan(project, card).clips
    assert {e.camera for e in entries} == {"unknown-1", "unknown-2"}
    assert all(e.status == ingest_mod.FILE for e in entries)
    assert len({e.destination for e in entries}) == 2


def test_clips_that_would_land_on_one_path_are_a_conflict(project, dataset, tmp_path):
    """--camera forces one name onto two identically named files."""
    card = tmp_path / "cards"
    write_video(card / "a" / "GX010001.MP4", frames_for(3, head=[SLATE3]))
    write_video(card / "b" / "GX010001.MP4", frames_for(3, head=[SLATE3]))
    entries = plan(project, card, camera="cam-left").clips
    assert all(e.status == ingest_mod.CONFLICT for e in entries)


def test_a_clip_already_filed_is_recognised(project, dataset, tmp_path):
    card = tmp_path / "card"
    label(card, "cam-left")
    clip = write_video(card / "clip.mp4", frames_for(3, head=[SLATE3]))
    target = project.stage_dir("raw") / ID / "take03" / "cam-left" / "clip.mp4"
    target.parent.mkdir(parents=True)
    target.write_bytes(clip.read_bytes())

    [entry] = plan(project, card).clips
    assert entry.status == ingest_mod.ALREADY


def test_something_different_at_the_destination_is_a_conflict(project, dataset, tmp_path):
    card = tmp_path / "card"
    label(card, "cam-left")
    write_video(card / "clip.mp4", frames_for(3, head=[SLATE3]))
    target = project.stage_dir("raw") / ID / "take03" / "cam-left" / "clip.mp4"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"not the same recording")

    [entry] = plan(project, card).clips
    assert entry.status == ingest_mod.CONFLICT


def test_a_bad_camera_label_is_reported(project, dataset, tmp_path):
    card = tmp_path / "card"
    card.mkdir()
    (card / "CAMERA.txt").write_text("left camera, the good one\n", encoding="utf-8")
    write_video(card / "clip.mp4", frames_for(3, head=[SLATE3]))
    result = plan(project, card)
    assert any("CAMERA.txt" in p for p in result.problems)


def test_an_unreadable_clip_is_unsorted_not_fatal(project, dataset, tmp_path):
    card = tmp_path / "card"
    card.mkdir()
    (card / "broken.mp4").write_bytes(b"\x00" * 2048)
    write_video(card / "good.mp4", frames_for(3, head=[SLATE3]))
    entries = {e.clip.name: e for e in plan(project, card).clips}
    assert entries["broken.mp4"].status == ingest_mod.UNSORTED
    assert entries["good.mp4"].status == ingest_mod.FILE


# -- a dry run changes nothing -----------------------------------------------------

def test_a_dry_run_changes_nothing_on_the_card_or_in_the_project(project, dataset, tmp_path):
    card = tmp_path / "card"
    label(card, "cam-left")
    write_video(card / "DCIM" / "GX010001.MP4", frames_for(3, head=[SLATE3]))
    write_video(card / "DCIM" / "GX010002.MP4", frames_for(3))

    before = snapshot(card, project.root, project.bulk())
    plan(project, card)
    run_cli(project, ["ingest", str(card), "--dry-run", "--seconds", "1"])
    run_cli(project, ["ingest", str(card), "--dry-run", "--seconds", "1", "--json"])
    assert snapshot(card, project.root, project.bulk()) == before


# -- the command -------------------------------------------------------------------

def run_cli(project, argv):
    here = os.getcwd()
    os.chdir(project.root)
    try:
        return main(argv)
    finally:
        os.chdir(here)


def test_without_dry_run_it_refuses_and_says_why(project, tmp_path, capsys):
    card = tmp_path / "card"
    card.mkdir()
    assert run_cli(project, ["ingest", str(card)]) == 2
    assert "stage 2" in capsys.readouterr().err


def test_json_reports_every_clip_and_exits_1_when_anything_is_unsorted(
        project, dataset, tmp_path, capsys):
    card = tmp_path / "card"
    label(card, "cam-left")
    write_video(card / "slated.mp4", frames_for(3, head=[SLATE3]))
    write_video(card / "blank.mp4", frames_for(3))

    code = run_cli(project, ["ingest", str(card), "--dry-run", "--seconds", "1", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload["copied"] == 0
    assert payload["counts"]["file"] == 1 and payload["counts"]["unsorted"] == 1
    assert any("blank.mp4" in p for p in payload["problems"])


def test_text_output_ends_by_saying_nothing_was_copied(project, dataset, tmp_path, capsys):
    card = tmp_path / "card"
    label(card, "cam-left")
    write_video(card / "slated.mp4", frames_for(3, head=[SLATE3]))
    assert run_cli(project, ["ingest", str(card), "--dry-run", "--seconds", "1"]) == 0
    out = capsys.readouterr().out
    assert "take03" in out and "cam-left" in out
    assert out.rstrip().endswith("nothing was copied.")
