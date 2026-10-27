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

from collections.abc import Callable

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


def _gray(image: np.ndarray) -> np.ndarray:
    """One channel, whatever came in: gray, BGR, BGRA or a single-channel stack."""
    if image.ndim == 2:
        return image
    channels = image.shape[2]
    if channels == 1:
        return image[:, :, 0]
    if channels == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def _decode_all(detector, image: np.ndarray) -> list[str]:
    """Every payload one detector reads in one image, in the order it found them."""
    try:
        ok, texts, _, _ = detector.detectAndDecodeMulti(image)
    except cv2.error:
        ok, texts = False, ()
    found = [t for t in texts if t] if ok else []
    if not found:
        # The multi-code search can miss a lone symbol the single one reads.
        try:
            text, _, _ = detector.detectAndDecode(image)
        except cv2.error:
            text = ""
        if text:
            found = [text]
    return found


def find_codes(
    image: np.ndarray, accept: Callable[[str], bool] | None = None
) -> list[str]:
    """Every QR payload readable in `image`, most likely first. Never raises.

    Every code a detector sees in the frame is collected, not just the first,
    so a foreign code (a product label, a poster behind the slate) cannot hide
    the slate's. The search stops at the first detector and scale that reads a
    payload `accept` takes -- any payload when `accept` is None -- since the
    slate shows one code at a time. Otherwise it tries every detector and scale
    and returns everything it read.
    """
    if image is None or getattr(image, "size", 0) == 0:
        return []
    try:
        base = _shrink(_gray(image), MAX_WIDTH)
        candidates = (base, _shrink(base, base.shape[1] // 2))
    except (cv2.error, ValueError, IndexError):
        return []

    seen: list[str] = []
    for candidate in candidates:
        for detector in _get_detectors():
            texts = _decode_all(detector, candidate)
            for text in texts:
                if text not in seen:
                    seen.append(text)
            if any(accept is None or accept(t) for t in texts):
                return seen
    return seen
