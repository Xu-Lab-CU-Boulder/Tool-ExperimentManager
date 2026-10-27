"""Draw slate QR codes into synthetic camera frames and read them back, as ingest does.

Shows `experimentkit.decode.find_codes` (two OpenCV detectors, two scales) and
`experimentkit.payload.parse` (the `pk1:` grammar) on:

1. a slate code, a sync code, and a 4K frame (shrunk to 1280 px before decoding);
2. a QR code that is not the slate's (rejected by the grammar, not guessed at);
3. frames with both a foreign code and the slate in them: every code is collected,
   so the slate is found whichever side the foreign code sits (until 2026-10-27 only
   the first code read was returned, and one arrangement lost the slate).

The symbols are drawn with OpenCV's own QR encoder (level M), not the slate
page's JavaScript encoder, so this needs no Node. Synthetic data only; the
frames are written to a new temporary folder, never into the repository.

    .venv/Scripts/python examples/slate_decode.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import cv2
import numpy as np

from experimentkit.decode import find_codes
from experimentkit.payload import parse

ID = "20260212_hooper1_vertical-swimming"


def qr(text: str, module_px: int) -> np.ndarray:
    """A dark-on-white symbol with a 4-module quiet zone, like the slate draws."""
    params = cv2.QRCodeEncoder.Params()
    params.correction_level = cv2.QRCodeEncoder_CORRECT_LEVEL_M
    code = cv2.QRCodeEncoder.create(params).encode(text)   # includes a quiet zone
    return cv2.resize(code, None, fx=module_px, fy=module_px, interpolation=cv2.INTER_NEAREST)


def frame(size: tuple[int, int], codes: list[tuple[str, int, int, int]], seed: int = 0) -> np.ndarray:
    """A smooth, noisy scene of `size` (w, h) with each (text, module_px, x, y) pasted in."""
    w, h = size
    ys, xs = np.mgrid[0:h, 0:w]
    shade = 90 + 40 * np.sin(xs / 120.0) * np.cos(ys / 90.0)
    noise = np.random.default_rng(seed).normal(0, 6, (h, w))
    image = np.clip(shade + noise, 0, 255).astype(np.uint8)
    for text, module_px, x, y in codes:
        symbol = qr(text, module_px)
        sh, sw = symbol.shape
        image[y:y + sh, x:x + sw] = symbol
    return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)


def report(name: str, image: np.ndarray, out: Path) -> None:
    cv2.imwrite(str(out / f"{name}.png"), image)
    texts = find_codes(image, accept=lambda t: parse(t) is not None)
    parsed = next((p for p in map(parse, texts) if p is not None), None)
    print(f"{name:<22} {image.shape[1]}x{image.shape[0]}  read={texts!r}")
    print(f"{'':<22} parsed={parsed}")


def main() -> None:
    out = Path(tempfile.mkdtemp(prefix="ek_slate_decode_"))
    slate = f"pk1:{ID}:take03"
    sync = f"pk1:{ID}:take03:sync:0007"

    report("slate", frame((1280, 720), [(slate, 8, 400, 100)]), out)
    report("sync", frame((1280, 720), [(sync, 8, 400, 100)]), out)
    report("slate_4k", frame((3840, 2160), [(slate, 20, 1200, 300)]), out)
    report("foreign_code", frame((1280, 720), [("https://example.com/label", 8, 400, 100)]), out)
    # Both in one frame, in both arrangements: the slate is read either way.
    report("foreign_left_slate", frame((1280, 720), [("https://example.com/label", 7, 40, 100),
                                                     (slate, 7, 760, 100)]), out)
    report("slate_left_foreign", frame((1280, 720), [(slate, 7, 40, 100),
                                                     ("https://example.com/label", 7, 760, 100)]), out)
    print(f"\nframes written to {out}")


if __name__ == "__main__":
    main()
