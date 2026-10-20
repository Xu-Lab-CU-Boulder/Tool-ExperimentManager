---
title: Finding the slate's QR code in a frame
code: experimentkit/decode.py:find_codes
fingerprint: 29560fb89398ccb1
refs: [opencv_qrcodedetector, opencv_qrcodedetectoraruco]
status: draft
---

# Finding the slate's QR code in a frame

**Code:** `experimentkit/decode.py:find_codes` (line 40), with `_shrink` (33) and `_get_detectors` (26).

**What it does.** Given one video frame (a NumPy image, BGR or grayscale, any size), returns the
text of a QR code readable in it, as a one-element list, or `[]`. It tries two OpenCV detectors at
two scales and stops at the first that reads anything. The text is not interpreted here
(`payload.parse` does that; see [read-slate.md](read-slate.md)).

## Method

With frame width $W$, the frame is converted to gray and, if wider than $W_\max = 1280$ px, shrunk
by $s = W_\max / W$ (area interpolation). Two candidates are tried, the base image and a copy
shrunk again to half its width:

$$
I_0 = \operatorname{shrink}(I, W_\max), \qquad I_1 = \operatorname{shrink}\!\left(I_0, \lfloor W_0/2 \rfloor\right)
$$

and for each candidate, in order, `cv2.QRCodeDetector().detectAndDecode` [opencv_qrcodedetector]
then `cv2.QRCodeDetectorAruco().detectAndDecode` [opencv_qrcodedetectoraruco]. The first
non-empty text is returned.

**Ours:** $W_\max$ = 1280 px (a 4K frame is slow to search and gains nothing for a code filling a
phone screen); the second scale of one half; the detector order. Why two of each: while testing the
slate's encoder, OpenCV's standard detector missed about **1 in 70** perfectly rendered, valid
symbols at a given scale that another scale or the ArUco-based detector read (the lab's
measurement, `decode.py` docstring and `tests/test_slate.py:decode`; date not recorded). The
detectors themselves are OpenCV's (published software); how they locate a symbol is not
described here.

## Steps

```text
find_codes(image):
    if image empty: return []
    gray <- image if 2-D else BGR -> gray
    base <- gray shrunk to width <= 1280
    for candidate in (base, base shrunk to half width):
        for detector in (QRCodeDetector, QRCodeDetectorAruco):
            text <- detector.detectAndDecode(candidate)   (cv2.error -> try the next)
            if text: return [text]
    return []
```

## Sources

[opencv_qrcodedetector] (verified: the call and its outputs, from its docstring);
[opencv_qrcodedetectoraruco] (candidate). The two-detector, two-scale cascade is the lab's own.

## Limits

- **One code per frame, the first readable.** If another QR code is in the scene (a product
  label, a poster) and a detector reads it first, `find_codes` returns that one and never looks
  for the slate in that frame; `parse` then rejects it, and the frame counts as having no slate.
  `detectAndDecodeMulti` would see both. Which code wins depends on where they sit, so a slate
  moving in the hand may win in another sampled frame — but a foreign code fixed in the scene can
  win in every frame, and the clip is then unsorted with "no slate found". Demonstrated in
  `examples/slate_decode.py`: with the slate on the left and a URL code on the right,
  `find_codes` returns the URL (cv2 4.14.0, 2026-10-20); swapped, it returns the slate.
- **A 4-channel image** (BGRA) goes to `cvtColor(..., COLOR_BGR2GRAY)` outside the `try`, which
  raises; the docstring's "never raises" holds only for 2-D and 3-channel images.
  `read_slate` catches it and reports the clip as unreadable.
- **Small codes.** Shrinking a 4K frame to 1280 px divides module size by three; a code far from
  the camera may drop below what the detectors resolve, and the half-scale retry makes that worse,
  not better. A full-resolution try is not attempted.
- **Light-on-dark codes** are not read; the slate never inverts its QR for that reason.
