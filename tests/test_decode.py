"""find_codes: foreign codes beside the slate's, and frames of any channel layout."""

from __future__ import annotations

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2", reason="OpenCV decodes the symbols")

from conftest import SIZE, slate_frame

from experimentkit.decode import find_codes
from experimentkit.payload import parse

SLATE = "pk1:20260212_hooper1_vertical-swimming:take03"


def _qr(text: str, scale: int = 6) -> np.ndarray:
    code = cv2.QRCodeEncoder.create().encode(text)
    return cv2.resize(code, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)


def two_codes(first: str, second: str) -> np.ndarray:
    """A frame with two codes side by side: a foreign one and the slate's."""
    frame = np.full((SIZE[1], SIZE[0]), 200, np.uint8)
    for text, x in ((first, 20), (second, SIZE[0] // 2 + 20)):
        code = _qr(text)
        h, w = code.shape
        y = (SIZE[1] - h) // 2
        frame[y : y + h, x : x + w] = code
    return cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)


@pytest.mark.parametrize("slate_left", [True, False])
def test_foreign_code_does_not_hide_the_slate(slate_left):
    foreign = "https://example.com/product"
    frame = two_codes(SLATE, foreign) if slate_left else two_codes(foreign, SLATE)
    found = find_codes(frame, accept=lambda t: parse(t) is not None)
    assert SLATE in found


def test_only_a_foreign_code_is_returned_but_parses_to_nothing():
    found = find_codes(
        slate_frame("https://example.com/poster"), accept=lambda t: parse(t) is not None
    )
    assert found == ["https://example.com/poster"]
    assert all(parse(t) is None for t in found)


@pytest.mark.parametrize("layout", ["gray", "gray1", "bgr", "bgra"])
def test_any_channel_layout(layout):
    bgr = slate_frame(SLATE)
    image = {
        "gray": cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY),
        "gray1": cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)[:, :, None],
        "bgr": bgr,
        "bgra": cv2.cvtColor(bgr, cv2.COLOR_BGR2BGRA),
    }[layout]
    assert find_codes(image) == [SLATE]


def test_never_raises_on_odd_input():
    assert find_codes(None) == []
    assert find_codes(np.zeros((0, 0), np.uint8)) == []
    assert find_codes(np.zeros((10, 10, 2), np.uint8)) == []
