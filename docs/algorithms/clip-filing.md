---
title: Matching a clip to its experiment and filing it (ingest stage 1)
code: experimentkit/ingest.py:plan_ingest
fingerprint: 1db0ca220e6e4d9d
refs: []
status: draft
---

# Matching a clip to its experiment and filing it

**Code:** `experimentkit/ingest.py:plan_ingest` (line 90), `_unsorted_reason` (77),
`_mark_existing` (159), `_mark_collisions` (175); clips and cameras from
`experimentkit/clips.py:find_clips`, `camera_for`, `home_folder`.

**What it does.** For every clip on a card or in a capture folder, decides where it would be filed
— `<stage dir>/<experiment id>/takeNN/<camera>/<clip name>` — and whether that is certain enough
to act on. It writes nothing. Each clip ends in one of four states: **file**, **already-filed**,
**conflict**, or **unsorted** (with the reason). The rule throughout is *never guess*: a wrong
guess puts footage in the wrong dataset, and nothing downstream would notice.

## Method

For a clip $c$ with slate identity $\iota(c)$ ([read-slate.md](read-slate.md)), camera name
$\kappa(c)$ and the project's dataset records:

$$
\text{dest}(c) = \operatorname{stage\_dir}\big(\operatorname{stage}(id)\big) \,/\, id \,/\, \texttt{take}NN \,/\, \kappa(c) \,/\, \operatorname{name}(c),
\qquad (id, NN) = \iota(c)
$$

$$
\text{status}(c) = \begin{cases}
\text{unsorted} & \iota(c) = \text{None, or no dataset } id \text{, or its sidecar is unreadable, or bulk storage unreachable}\\
\text{already-filed} & \text{dest exists and } \operatorname{size}(\text{dest}) = \operatorname{size}(c)\\
\text{conflict} & \text{dest exists with another size, or } |\{c' : \text{dest}(c') = \text{dest}(c)\}| > 1\\
\text{file} & \text{otherwise}
\end{cases}
$$

**The camera** $\kappa(c)$: the `--camera` override if given; else the contents of the nearest
`CAMERA.txt` at or above the clip, searching no higher than the folder ingest was pointed at; else
`unknown-1`, `unknown-2`, … numbered per distinct *home folder* (the folder a video sits in, or the
folder holding an image sequence's folder), in the order clips are met.

**A clip** is a video file, or a folder holding at least 2 images (`MIN_SEQUENCE`); a folder of
images is one clip.

**Ours, all of it:** the folder layout, the four states, size as the stage-1 identity test
(stage 2 is to compare hashes before trusting a match — not built), `MIN_SEQUENCE = 2`, the
camera-label grammar `^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$`. No published method is involved.

## Steps

```text
plan_ingest(source, project, camera = None, window = 10 s):
    raw_root <- project's raw stage dir   (unreachable -> a whole-run problem)
    clips, ignored <- find_clips(source)
    for clip in clips:
        camera name <- override | CAMERA.txt label | unknown-k by home folder
        reading <- read_slate(clip, window)
        if reading.identity is None: unsorted (error | no slate | codes disagree: names them)
        stage <- the dataset's stage from its sidecar     missing/unreadable -> unsorted
        if raw_root unreachable: unsorted
        destination <- stage_dir(stage)/id/takeNN/camera/clip name;  status <- file
    for each clip to be filed whose destination exists:
        same size -> already-filed, else conflict
    for each destination claimed by more than one clip: all of them -> conflict
```

## Sources

None: this is the lab's own filing rule.

## Limits

- **Size is not identity.** Two different recordings of the same length in bytes (two fixed-size
  raw image sequences, say) are reported "already filed". Stage 2 is to check hashes; until then
  "already-filed" means only "something the same size is there".
- **Unlabelled cameras are told apart by folder only.** Two cameras writing to one folder become
  one `unknown-1` camera and then collide (reported as conflicts, so nothing is lost); one camera
  writing to two folders becomes two cameras.
- **`unknown-k` numbering depends on walk order**, so the same card can produce different numbers
  if its folders change.
- **The stage, not always `raw`.** A dataset whose sidecar says it is in another stage is filed
  under that stage's folder; `raw_root` is only checked for reachability.
- The `bulk_required` parameter is accepted but not used.
