"""Fake cameras, fake cards, a throwaway project.

Ingest cannot be tested against a real camera on every run, so these build the
things a camera leaves behind: short MP4s and folders of numbered PNGs, with a
slate QR code drawn into chosen frames. The QR images come from OpenCV's own
encoder rather than the slate page's, so these tests check the reading side
independently of the page.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest
from projectkit.config import Config
from projectkit.dataset import Dataset

FPS = 30
SIZE = (640, 480)

PROJECT_TOML = """
[project]
name = "Test-Project"
slug = "test"
kind = "paper"

[paths]
data_root_env = "EK_TEST_DATA_ROOT"
bulk = "Test-Project"
raw = "3_experiments/raw"
processed = "3_experiments/processed"
"""


@pytest.fixture()
def project(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / "experiments").mkdir(parents=True)
    (repo / "project.toml").write_text(PROJECT_TOML, encoding="utf-8")
    bulk = tmp_path / "bulk"
    for stage in ("raw", "processed"):
        (bulk / "Test-Project" / "3_experiments" / stage).mkdir(parents=True)
    monkeypatch.setenv("EK_TEST_DATA_ROOT", str(bulk))
    return Config.load(repo)


@pytest.fixture()
def dataset(project):
    ds = Dataset.create(project, "20260212_hooper1_vertical-swimming", "kinematics")
    ds.save()
    return ds


_BACKGROUND: np.ndarray | None = None


def _background() -> np.ndarray:
    """Computed once: building it per frame made test setup the slowest part."""
    global _BACKGROUND
    if _BACKGROUND is None:
        ys, xs = np.mgrid[0:SIZE[1], 0:SIZE[0]]
        shade = (70 + 40 * np.sin(xs / 90.0) * np.cos(ys / 70.0)).astype(np.uint8)
        _BACKGROUND = np.dstack([shade, shade + 10, shade + 20])
    return _BACKGROUND


def slate_frame(text: str | None, seed: int = 0) -> np.ndarray:
    """A camera frame: a smooth scene, and a QR code if `text` is given.

    Smooth rather than random noise: a real tank and background are smooth,
    and noise is the worst case for the detector -- slower, and unrealistic.
    A little per-frame drift keeps consecutive frames from being identical.
    """
    frame = np.roll(_background(), seed % SIZE[0], axis=1).copy()
    if text is not None:
        code = cv2.QRCodeEncoder.create().encode(text)
        code = cv2.resize(code, None, fx=8, fy=8, interpolation=cv2.INTER_NEAREST)
        h, w = code.shape
        y, x = (SIZE[1] - h) // 2, (SIZE[0] - w) // 2
        frame[y:y + h, x:x + w] = cv2.cvtColor(code, cv2.COLOR_GRAY2BGR)
    return frame


def frames_for(seconds: float, head: list[str] | None = None,
               tail: list[str] | None = None, hold: float = 1.0) -> list[np.ndarray]:
    """A clip's frames: codes shown at the start and/or end, each held `hold` s."""
    total = int(seconds * FPS)
    per = int(hold * FPS)
    texts: list[str | None] = [None] * total
    for i, code in enumerate(head or []):
        for f in range(i * per, min(total, (i + 1) * per)):
            texts[f] = code
    for i, code in enumerate(reversed(tail or [])):
        for f in range(max(0, total - (i + 1) * per), total - i * per):
            texts[f] = code
    return [slate_frame(t, seed=n) for n, t in enumerate(texts)]


def write_video(path: Path, frames: list[np.ndarray]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, SIZE)
    assert writer.isOpened(), "OpenCV cannot write mp4v on this machine"
    for frame in frames:
        writer.write(frame)
    writer.release()
    return path


def write_sequence(folder: Path, frames: list[np.ndarray]) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    for i, frame in enumerate(frames):
        cv2.imwrite(str(folder / f"frame_{i:05d}.png"), frame)
    return folder


def label(folder: Path, name: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "CAMERA.txt").write_text(name + "\n", encoding="utf-8")


def snapshot(*roots: Path) -> dict:
    """Every file under `roots` with its size and mtime: proof nothing changed."""
    state = {}
    for root in roots:
        for path in sorted(root.rglob("*")):
            stat = path.stat()
            state[str(path)] = (path.is_dir(), stat.st_size if path.is_file() else 0,
                                stat.st_mtime_ns)
    return state
