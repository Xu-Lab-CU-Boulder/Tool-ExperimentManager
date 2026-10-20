---
title: Recognising a recording by its SetTime, wherever it sits
code: experimentkit/storage/sync.py:_match
fingerprint: 5640ef2354071bf3
refs: []
status: draft
---

# Recognising a recording by its SetTime

**Code:** `experimentkit/storage/sync.py:_match` (line 108), `_to_drive` (126), `_follow_layout`
(192); what a recording is: `experimentkit/storage/inventory.py:recordings` (114) and `set_time` (61).

**What it does.** The work drive's layout is the user's to arrange (decided 2026-09-19): a
recording on C: may sit somewhere else on G:, under another name. So recordings are matched **by
the `SetTime` DaVis writes into the recording's `.set` file** — which survives a rename in DaVis —
never by path. `_match` answers "where on the work drive is this C: recording's copy?";
`_to_drive` maps each C: file through that answer; `_follow_layout` moves the backup's copies so
the backup follows the work drive's layout. Nothing is re-copied because of a move.

## Method

**A recording** (`inventory.recordings`) is a folder $F$ with a sibling `F.set`, not under
`Properties/`, holding data directly — a `StreamSet.xml`, or a file ending `.ims`, `.im7`, `.imx`
or `.vc7`. A recording nested inside another (a processed result has its own `.set`) is dropped:
it belongs to its parent. Every file under $F$, and `F.set`, belongs to it.

**The match.** For C: recording $r$ with path $p_r$ and SetTime $t_r$, ledger $L$ of the work drive,
and $D$ = the recordings found by scanning the drive (used only when the ledger has no C: mapping
yet):

$$
\operatorname{match}(r) = \begin{cases}
L.\text{source\_map}[p_r] & \text{if known}\\
p_r & \text{if } p_r \in K \\
k & \text{if } K = \{k\}\\
k & \text{if exactly one } k \in K \text{ has the same last path component as } p_r\\
p_r & \text{otherwise (a recording new to the drive lands at C:'s path)}
\end{cases}
$$

with $K = \{k : L.\text{recordings}[k] = t_r\}$, or, if that is empty, $\{k \in D : t_k = t_r\}$; and
$K = \varnothing$ when $t_r$ is empty.

**Mapping files.** Recordings are matched deepest path first, and a C: file $f$ under $p_r$ maps to
$\operatorname{match}(r) + f[\,|p_r|:\,]$.

**The backup follows** (`_follow_layout`): for each work-drive recording at $n$ with SetTime $t$ that
the backup does not have at $n$, if exactly one backup recording $o$ has SetTime $t$ and $o$ is not
itself a work-drive path, move $o \to n$ (and `o.set` → `n.set`), and record a `rename`.

**Ours, all of it:** SetTime as identity, the tie-breaks, and the "new recordings land at C:'s path"
rule (decided 2026-09-19, `docs/design/storage-sync.md` §15). No published method.

## Steps

```text
_match(r):
    if r's C: path already mapped in the ledger: return that
    if r has a SetTime:
        K <- drive folders the ledger knows with that SetTime, else those found on the drive
        if r's own path in K: return it
        if |K| = 1: return the one
        if exactly one in K has r's folder name: return it
    return r's C: path

sync_to_work: for r in recordings, deepest first:
    dst <- _match(r); owners[r] <- dst
    if the ledger does not already say so: ledger "recording {rel: dst, set_time, source_rel: r}"
```

## Limits

- **A `.set` with no `SetTime`** (or daviskit absent and a format the fallback regex does not
  read) falls back to matching by path, so a rename on C: then looks like a new recording and is
  copied again to the new path.
- **Two copies of one recording on the drive** with different folder names give $|K| > 1$ and no
  unique leaf: the C: path is used, which may create a third copy. `status` reports recordings
  with one SetTime in several places as *duplicates*.
- **Two different recordings with the same SetTime** (to the resolution DaVis writes it) would be
  taken for one. Not seen; SetTime is a timestamp of the recording's start.
- **Once mapped, always mapped.** `source_map` is consulted first, and the drive is scanned only
  while the ledger has no mapping at all. Read from the code (not tested): if the user moves a
  recording on the work drive *after* it was first matched, the next `sync_to_work` still maps C:'s
  files to the old path, finds nothing there, and copies the recording again to the old path —
  the design's "a recording reorganised on G: is recognised where it sits" then holds only for
  reorganisations made before the first sync.
