---
title: Finding the slate's QR code in a frame
code: experimentkit/decode.py:find_codes
fingerprint: bef7f44b7689f16d
refs: [opencv_qrcodedetector, opencv_qrcodedetectoraruco]
status: draft
---

# Finding the slate's QR code in a frame

**Code:** `experimentkit/decode.py:find_codes` (line 72), with `_decode_all` (54), `_gray` (42),
`_shrink` (35) and `_get_detectors` (28).

**What it does.** Given one video frame (a NumPy image: grayscale, BGR or BGRA, any size), returns
the text of every QR code readable in it, or `[]`; it never raises. It tries two OpenCV detectors
at two scales, collecting every code each one sees, and stops at the first detector and scale that
reads a code the caller's `accept` takes (any code when `accept` is None). `read_slate` passes
"`payload.parse` accepts it", so a foreign code does not end the search. The text is not
interpreted here (`payload.parse` does that; see [read-slate.md](read-slate.md)).

## Method

With frame width $W$, the frame is converted to gray and, if wider than $W_\max = 1280$ px, shrunk
by $s = W_\max / W$ (area interpolation). Two candidates are tried, the base image and a copy
shrunk again to half its width:

$$
I_0 = \operatorname{shrink}(I, W_\max), \qquad I_1 = \operatorname{shrink}\!\left(I_0, \lfloor W_0/2 \rfloor\right)
$$

and for each candidate, in order, `cv2.QRCodeDetector` [opencv_qrcodedetector] then
`cv2.QRCodeDetectorAruco` [opencv_qrcodedetectoraruco], each with `detectAndDecodeMulti` (every
code in the image) and, when that reads nothing, `detectAndDecode` (one code). Texts accumulate,
without repeats, in the order read; the first detector and scale whose texts include an accepted
one ends the search.

**Ours:** $W_\max$ = 1280 px (a 4K frame is slow to search and gains nothing for a code filling a
phone screen); the second scale of one half; the detector order. Why two of each: while testing the
slate's encoder, OpenCV's standard detector missed about **1 in 70** perfectly rendered, valid
symbols at a given scale that another scale or the ArUco-based detector read (the lab's
measurement, `decode.py` docstring and `tests/test_slate.py:decode`; date not recorded). The
detectors themselves are OpenCV's (published software); how they locate a symbol is not
described here.

## Steps

```text
find_codes(image, accept = None):
    if image empty: return []
    gray <- image if 2-D, else its one channel, BGRA -> gray or BGR -> gray
    base <- gray shrunk to width <= 1280                (any error -> return [])
    seen <- []
    for candidate in (base, base shrunk to half width):
        for detector in (QRCodeDetector, QRCodeDetectorAruco):
            texts <- detector.detectAndDecodeMulti(candidate)
            if texts empty: texts <- [detector.detectAndDecode(candidate)] if non-empty
                                                     (cv2.error -> nothing read)
            append each new text to seen
            if any text in texts is accepted (or accept is None): return seen
    return seen
```

## Sources

[opencv_qrcodedetector] (verified: the call and its outputs, from its docstring);
[opencv_qrcodedetectoraruco] (candidate). The two-detector, two-scale cascade is the lab's own.

## Limits

- **Foreign codes cost time, not the slate.** Until 2026-10-27 only the first code read was
  returned, so a foreign code (a label, a poster) could hide the slate: with the slate on the left
  and a URL code on the right, the URL won (cv2 4.14.0, 2026-10-20). Every code is now collected,
  and both arrangements read the slate (`examples/slate_decode.py`, `tests/test_decode.py`; cv2
  4.14.0, 2026-10-27). A frame holding only a foreign code is searched at every detector and scale
  before it returns, so it is the slowest kind of frame to decode.
- **Small codes.** Shrinking a 4K frame to 1280 px divides module size by three; a code far from
  the camera may drop below what the detectors resolve, and the half-scale retry makes that worse,
  not better. A full-resolution try is not attempted.
- **Light-on-dark codes** are not read; the slate never inverts its QR for that reason.
