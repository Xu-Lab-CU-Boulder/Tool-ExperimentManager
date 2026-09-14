"""Finding the slate's QR codes in a frame.

Two OpenCV detectors, and a smaller copy of the frame when the full one yields
nothing. While testing the slate's encoder, OpenCV's standard detector missed
about 1 in 70 perfectly rendered symbols at a given scale that another scale or
the ArUco-based detector read. Real footage is worse than a clean render, so
one detector at one scale is not enough.

Candidate to move into markertracker, which already owns detection in images.
It lives here for now because it is small and the slate protocol is this
project's; the frames themselves already come from markertracker.
"""

from __future__ import annotations

import cv2
import numpy as np

#: Frames wider than this are shrunk before decoding. A 4K frame is slow to
#: search and gains nothing for a code that fills a phone screen.
MAX_WIDTH = 1280

_detectors: list | None = None


def _get_detectors() -> list:
    global _detectors
    if _detectors is None:
        _detectors = [cv2.QRCodeDetector(), cv2.QRCodeDetectorAruco()]
    return _detectors


def _shrink(image: np.ndarray, width: int) -> np.ndarray:
    if image.shape[1] <= width:
        return image
    scale = width / image.shape[1]
    return cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)


def find_codes(image: np.ndarray) -> list[str]:
    """Every QR payload readable in `image`, most likely first. Never raises.

    Stops at the first detector and scale that reads anything: the slate shows
    one code at a time, so there is nothing further to find in the same frame.
    """
    if image is None or image.size == 0:
        return []
    gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    base = _shrink(gray, MAX_WIDTH)

    for candidate in (base, _shrink(base, base.shape[1] // 2)):
        for detector in _get_detectors():
            try:
                text, _, _ = detector.detectAndDecode(candidate)
            except cv2.error:
                continue
            if text:
                return [text]
    return []
