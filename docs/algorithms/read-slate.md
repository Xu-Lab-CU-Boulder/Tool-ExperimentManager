---
title: Reading the slate out of a clip
code: experimentkit/slate.py:read_slate
fingerprint: 0981ed7ab2ece69e
refs: []
status: draft
---

# Reading the slate out of a clip

**Code:** `experimentkit/slate.py:read_slate` (line 125), `_search` (78),
`SlateReading.identity` (52); the payload grammar `experimentkit/payload.py:parse` (45).

**What it does.** Given one clip (a video file, or a folder of numbered images), searches only its
first and last 10 s for slate codes and returns every sighting: which code, head or tail, which
frame. From these, `SlateReading.identity` gives the one (experiment id, take) the clip belongs
to, or `None` when nothing was found **or when codes disagree**. Never raises; an unreadable clip
comes back with `error` set.

## Method

With frame rate $f$ (fps; 30 when the source reports none), frame count $N$, window
$T_w = 10$ s, sampling rate $r_s = 3$ samples/s and quiet time $T_q = 2$ s:

$$
w = \max\!\big(1, \operatorname{round}(T_w f)\big), \quad
\Delta = \max\!\big(1, \operatorname{round}(f / r_s)\big), \quad
q = \max\!\big(1, \operatorname{round}(T_q r_s)\big)
$$

The head window is frames $[0, \min(w, N))$, the tail window $[\max(h, N - w), N)$ where $h$ is the
end of the head window (so a short clip is not searched twice). Every $\Delta$-th frame is decoded
([find-codes.md](find-codes.md)). Within a window, once a code has been seen, $q$ consecutive
sampled frames without one end that window: the slate has been put down. At 30 fps:
$w = 300$, $\Delta = 10$, $q = 6$.

A decoded text counts only if it matches (after stripping whitespace)

```text
^pk1:(?P<id>[^:]+):take(?P<take>\d{2,3})(?::sync:(?P<sync>\d{4}))?$
```

the id passes projectkit's `validate_id`, and $1 \le$ take $\le 999$. Then

$$
\text{identity} = \begin{cases} (id, take) & \text{if exactly one distinct pair was sighted} \\ \text{None} & \text{otherwise} \end{cases}
$$

A single sighting is enough: Reed–Solomon parity makes a false decode of a damaged symbol
improbable, and the grammar rejects anyone else's code.

**Ours, all of them:** $T_w$ = 10 s (the slate is held up at the start; a tail slate is the
fallback), $r_s$ = 3 samples/s (the slate is held for seconds), $T_q$ = 2 s, 30 fps when unknown,
and the "disagreeing codes are not filed" rule. None is from a publication. Dates are not
recorded in the code.

## Steps

```text
read_slate(clip):
    source <- open (markertracker.videoio.open_source)        failure -> error, return
    f <- fps or 30;  w, Delta, q as above
    search(0, min(w, N), "head")
    if N unknown: tail not searched (reported)
    else if max(h, N - w) < N: search(max(h, N - w), N, "tail")

search(start, stop, where):
    seen <- false; quiet <- 0
    for each Delta-th frame in [start, stop):
        image sequence: seek to it (a still costs the same anywhere)
        video:          read forward from start (seeking lands on keyframes)
        codes <- [parse(t) for t in find_codes(frame, accept = parses)], dropping None
        if codes: record sightings; seen <- true; quiet <- 0
        elif seen: quiet += 1; if quiet >= q: stop this window
```

## Sources

No published method: windowed, sampled search is the lab's own design (`slate.py` docstring). The
payload format is defined by `slate/index.html` ([slate-qr-encoder.md](slate-qr-encoder.md)).

## Limits

- **A slate held up only in the middle of a clip is never found.** By design; the clip goes to
  *unsorted* with "no slate found in the first or last 10 s".
- **No frame count, no tail.** Some containers report none; then only the head is searched, and
  the reason says so.
- **Variable frame rate** makes 10 s a different length of footage than intended (frames, not
  seconds, are counted).
- **The quiet stop is per window.** A second, different slate shown more than 2 s after the first
  was put down, in the same window, is not seen — so a clip that was re-slated within its first
  10 s is filed under the first slate rather than flagged as disagreeing.
- **Every sampled frame is decoded with up to four detector passes**; a clip without a slate costs
  the most, since nothing stops the search early.
