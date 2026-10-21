---
title: Sync flips (camera synchronisation from the slate)
source: slate/index.html:step (JavaScript; kept by hand) and experimentkit/slate.py:SlateReading.sync_range
code: experimentkit/slate.py:SlateReading.sync_range
fingerprint: 23f43863a4f4986d
refs: [whatwg_animation_frames]
status: draft
---

# Sync flips

**Code:** `slate/index.html` — `step` (line 606), `syncFrame` (626), `startSync` (632),
`applyFlip` (593), the `visibilitychange` handler (673), `showDiag` (682). Reading side:
`experimentkit/slate.py:SlateReading.sync_range` (line 62).

**What it does.** While the operator holds **Sync**, the page shows a numbered sequence of flips,
one every period $P$ (500, 1000 or 2000 ms; default 1000). Flip $k$ shows the QR code
`pk1:<id>:takeNN:sync:KKKK` with $K = k$ and a large bar that is **black when $k$ is even, white
when $k$ is odd**. Every camera that films it records, frame by frame, which flip it was showing.
The counter says *which* flip a frame belongs to (so cameras that started at different times
cannot be misaligned by a whole period); the bar's brightness jump says *on which frame* the flip
landed, even when the frame is too blurred to decode.

## Method

The schedule, with $t_0$ = the time Sync was pressed and $\tau$ the timestamp of each display
refresh (`requestAnimationFrame` [whatwg_animation_frames]):

$$
\text{show flip } k \text{ at the first refresh with } \tau \ge t_k, \qquad
t_{k+1} = \begin{cases}
t_k + P & \text{if } \tau - (t_k + P) \le P \\
\tau + P & \text{otherwise (a stall: skip ahead, never burst)}
\end{cases}
$$

$$
\text{bar}(k) = \begin{cases}\text{black} & k \text{ even}\\ \text{white} & k \text{ odd}\end{cases}
$$

The bar and the QR change in the same refresh: the next QR is drawn ahead of time on an
off-screen canvas (`stageFlip`) and copied in by `applyFlip`. A flip is therefore late by at most
one display refresh (≈ 17 ms at 60 Hz), and a camera sees it on its next exposure: the alignment
resolution is about one camera frame, $1/f_\text{cam}$ (33 ms at 30 fps). The page reports the
display rate as $1000 / \operatorname{median}(\Delta\tau)$ Hz over the last 120 refresh intervals.

On the reading side, `sync_range(where)` returns $(\min K, \max K)$ of the sync counters decoded in
the clip's head or tail window.

**Ours:** the period choices 500/1000/2000 ms and default 1000 ms (line 514); even = black; the
skip-ahead rule; the 120-interval window for the display rate; stopping sync outright when the
page is hidden (a hidden page gets no refreshes, so flipping would stop silently). None of these
is from a publication. The ~1-camera-frame precision is a consequence, stated in
`slate/README.md`; it has not been measured.

## Steps

```text
startSync: k <- 0; next <- now(); stage QR for flip 0; request a refresh callback
on each refresh at time tau (step):
    record tau - previous tau (keep the last 120)
    if tau < next: nothing this refresh
    else:
        bar <- black if k even else white; copy the staged QR in; label "SYNC kkkk"
        k <- k + 1
        next <- next + P;  if tau - next > P: next <- tau + P
        stage QR for flip k
on page hidden: stop sync, show "SYNC WAS INTERRUPTED"
on take change: stop sync (a sequence belongs to one take)

reading a clip (Python): sync_range(where) = (min, max) of the sync counters sighted there
```

## What is not built yet

No code yet **uses** the flips: ingest records the sync counters it happens to decode while looking
for the slate, but nothing detects the bar's brightness transitions, pairs flips across cameras,
or fits a clock offset and drift from a head and a tail sync (which `slate/README.md` recommends
recording, "two sync points let the drift be measured"). This page should gain that method when
it exists.

## Limits

- **Variable frame rate** (common in webcams) breaks the frame-number-to-time mapping that
  alignment relies on; record at a fixed rate (`slate/README.md`).
- **Screen flicker.** Phones dim by pulse-width modulation; at low brightness the bar's brightness
  per frame is unreliable. Brightness to maximum.
- **The flip schedule is the browser's clock, not a hardware clock.** Fine for a jellyfish bell;
  not for high-speed work, which needs a hardware trigger.
- **Sampling misses flips.** Ingest decodes ~3 frames per second, so with $P = 500$ ms it may
  see only some counters; `sync_range` is a range, not a complete list.
