"""The slate page and ingest agree: what the page draws, ingest reads.

The other ingest tests draw QR codes with OpenCV's encoder, so they check the
reading side on its own. This is the one link that matters in the lab: codes
drawn by `slate/index.html`'s own encoder, in the page's own layout (dark on
white with a quiet zone), put through ingest end to end.

Skipped without Node, which runs the page's encoder.
"""

from __future__ import annotations

import shutil

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2", reason="the page's codes are decoded with OpenCV")
pytest.importorskip("markertracker", reason="ingest reads clips with markertracker")
from conftest import FPS, SIZE, _background, label, write_video

from experimentkit import ingest as ingest_mod

ID = "20260212_hooper1_vertical-swimming"

pytestmark = pytest.mark.skipif(shutil.which("node") is None,
                                reason="Node runs the slate page's encoder")


def page_symbol_frame(rows: list[str], module_px: int = 9) -> np.ndarray:
    """A camera frame showing the page's symbol the way the page renders it."""
    modules = np.array([[c == "1" for c in row] for row in rows])
    image = np.where(modules, 0, 255).astype(np.uint8)
    image = np.pad(image, 4, constant_values=255)            # the page's quiet zone
    image = np.kron(image, np.ones((module_px, module_px), np.uint8))
    frame = _background().copy()
    h, w = image.shape
    y, x = (SIZE[1] - h) // 2, (SIZE[0] - w) // 2
    frame[y:y + h, x:x + w] = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    return frame


def test_a_slate_and_sync_run_drawn_by_the_page_are_filed(project, dataset, tmp_path):
    from test_slate import run_encoder

    payloads = [f"pk1:{ID}:take03"] + [f"pk1:{ID}:take03:sync:{k:04d}" for k in range(4)]
    symbols = run_encoder(tmp_path, [{"text": p, "ecl": "M"} for p in payloads])

    # Slate held 1 s, then four sync flips at 0.5 s each, then plain footage.
    frames = [page_symbol_frame(symbols[0]["rows"])] * FPS
    for symbol in symbols[1:]:
        frames += [page_symbol_frame(symbol["rows"])] * (FPS // 2)
    frames += [_background().copy()] * FPS

    card = tmp_path / "card"
    label(card, "cam-left")
    write_video(card / "take03.mp4", frames)

    [entry] = ingest_mod.plan_ingest(card, project, window_seconds=3.5).clips
    assert entry.status == ingest_mod.FILE, entry.reason
    assert (entry.dataset_id, entry.take) == (ID, 3)
    assert entry.reading.sync_range("head") == (0, 3)
