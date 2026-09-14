# Slate

A clapperboard for experiment video, as one HTML file.

Hold it in front of every camera when a take starts. The QR code says which
experiment and take the footage belongs to, so **the video carries its own
identity**: it survives renamed files, a mixed-up SD card, and a copy to the
wrong folder. **Sync** flips a large bar between black and white and numbers
every flip, so footage from different cameras can be lined up to the frame.

It is the first piece of ExperimentManager. The planned ingest step reads the
slate out of each clip and files it into
`3_experiments/raw/<id>/take03/<camera>/`. That does not exist yet: the page
comes first so it can be tried with real cameras before anything is built
around it.

---

## Using it

Open `index.html` in a browser. With nothing in the URL it shows a form: the
experiment id, take, an optional note, and the sync period. Everything you enter
lives in the URL fragment:

```
index.html#id=20260212_hooper1_vertical-swimming&take=3&note=18+°C
```

so a bookmark or a shared link reopens the same slate. Browsers never send the
fragment to a server, so nothing about your experiment leaves the device, even
though the page is hosted publicly.

| Control | |
|---|---|
| **− take / take +** | Change take. Ends any sync sequence, since a sequence belongs to one take. |
| **Sync** | Start flipping. Tap again to stop. |
| **Full screen** | Hide the browser bars (not on iPhone; see below). |
| **Edit** | Back to the form. |

The top-right corner reports whether the screen is being kept awake and, while
syncing, the display's refresh rate.

### On a phone

A page opened from a file (AirDrop, OneDrive) often won't run its script, so on
a phone use the hosted copy. This repository is public, so GitHub Pages serves it
free once Pages is enabled (Settings → Pages → Deploy from a branch → `main`,
`/ (root)`):

```
https://xu-lab-cu-boulder.github.io/ExperimentManager/slate/
```

Hosting publicly reveals nothing about your experiments: the page's code is
public, but the id, take and note exist only in the fragment on your phone.

- **Turn brightness to maximum.** Phone screens dim by flickering, and flicker
  confuses both the QR decode and the brightness detection of the sync bar. A
  web page cannot set brightness itself.
- **iPhone**: Safari will not let a page go truly full screen. Use Share → Add
  to Home Screen, then open it from there.
- **Don't lock the phone or switch apps during sync.** A hidden page gets no
  screen refreshes, so flipping stops. The page stops sync outright when that
  happens and shows `SYNC WAS INTERRUPTED`, rather than letting you record
  footage you think is synced.
- A **printed slate** is the fallback that always works: no battery, no flicker,
  no trouble with polarizers.

---

## What the codes say

A pointer, never the conditions. The conditions stay in the dataset sidecar,
where they can still be corrected later.

```
slate   pk1:<experiment-id>:take03
sync    pk1:<experiment-id>:take03:sync:0007
```

- `pk1` marks a code this page made and versions the format, so a decoder can
  ignore any other QR code in the scene.
- The id must be a valid dataset id, the same rule projectkit uses, which also
  keeps `:` out of it.
- Error correction level M. A typical payload is a version 4 symbol (33 × 33
  modules), small enough to read from across a room.

### The sync rule

Flip *k* shows counter *k*. **The bar is black when *k* is even, white when *k*
is odd.**

- The **counter** says *which* flip a frame shows, so cameras that started
  recording at different times cannot be misaligned by a whole period.
- The **bar** says *exactly which frame* the flip landed on. It is a large flat
  area whose brightness jumps, detectable even in a frame too blurred to decode.
- The **QR itself never inverts.** Many decoders, OpenCV's among them, cannot
  read a light-on-dark code.

Flips happen on a screen refresh (`requestAnimationFrame`), with the bar and the
QR changing in the same frame. Precision is about one camera frame: roughly
33 ms at 30 fps, 17 ms at 60. That is plenty for a jellyfish bell and not enough
for high-speed work, which needs a hardware trigger.

**Sync at both the start and the end of a take.** Two cameras nominally at the
same frame rate drift apart; two sync points let the drift be measured.

---

## Notes for ingest

- **Use more than one detector.** While testing this page's encoder, OpenCV's
  standard `QRCodeDetector` missed about 1 in 70 perfectly rendered, valid
  symbols at a given image scale. The same symbols decoded at another scale or
  through `QRCodeDetectorAruco`. On real footage, try both, on several frames.
- **Decode only the first and last seconds** of a clip, at reduced resolution.
- **A clip with no readable slate goes to `unsorted/`**, never a best guess.
- **Webcam recordings may have a variable frame rate**, which breaks the mapping
  from frame number to time that sync depends on. Record at a fixed rate.

---

## Tests

`tests/test_slate.py` runs the page's own QR encoder in Node and decodes every
symbol with OpenCV: every version from 1 to 10 at all four error-correction
levels, including the first and last length of each version, where off-by-one
errors hide. The encoder is written into the page so it needs no downloads,
which also makes it the part most worth checking. The tests skip if Node or
OpenCV is missing.
