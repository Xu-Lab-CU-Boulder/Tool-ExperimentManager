---
title: Checksummed, interruption-safe copy (and when a file is copied at all)
code: experimentkit/storage/ledger.py:copy_hashing
fingerprint: d15066bb4a562c4f
refs: [fips180_4]
status: draft
---

# Checksummed, interruption-safe copy

**Code:** `experimentkit/storage/ledger.py:copy_hashing` (line 131) and `hash_file` (122); the
decision to copy, skip or adopt is in `experimentkit/storage/sync.py:sync_to_work` (134) and
`sync_to_backup` (217), with `_same_time` (48) and `_keep_versions` (61).

**What it does.** Copies one file from C: to the work drive (or from the work drive to the
backup) and returns the SHA-256 of the bytes **as read from the source**. That hash is the file's
*fingerprint*: every later check compares against it. The copy is written to `<name>.partial`,
flushed to disk, given the source's timestamps, and only then renamed into place — so a drive
pulled mid-copy leaves a `.partial`, never a file that looks whole. Reading for the copy and
hashing are one pass, so verification in transit costs no extra reading.

## Method

The file is read in chunks $b_1, b_2, \dots, b_m$ of 8 MiB; each chunk is written and fed to the
hash:

$$
h_\text{src} = \operatorname{SHA\text{-}256}(b_1 \,\|\, b_2 \,\|\, \cdots \,\|\, b_m)
$$

(SHA-256 as defined in [fips180_4], through Python's `hashlib`). The checks that use it:

| check | compares | where |
|---|---|---|
| in transit, C: → work | — (records $h_\text{C:}$ as the fingerprint) | `sync_to_work` |
| in transit, work → backup | $h_\text{work read} = h_\text{C:}$ ⇒ the work copy is intact | `sync_to_backup`, line 285 |
| full re-read | $\operatorname{SHA\text{-}256}(\text{file on drive}) = $ fingerprint | `verify` ([safe-to-delete.md](safe-to-delete.md)) |

**Whether to copy.** For each source file $e$ (size $s_e$, modified time $m_e$) and its ledger
state $L$ on the destination ([ledger-replay.md](ledger-replay.md)):

$$
\text{action}(e) = \begin{cases}
\text{skip} & L \text{ exists},\ L.s = s_e,\ L.m = m_e,\ \text{dest size} = s_e,\ \neg L.\text{mismatch}\\
\text{adopt} & \text{no } L,\ \text{dest size} = s_e,\ |m_\text{dest} - m_e| < 2\text{ s}\\
\text{copy} & \text{otherwise (an existing copy is first moved to } \texttt{.versions/<time>/}\text{)}
\end{cases}
$$

*Adopt* is a copy already made by hand: C:'s bytes are hashed and recorded, nothing is copied. On
the backup leg, skip also requires the backup's recorded hash to equal the work fingerprint when
both are known. `.set` files are copied last, so a half-copied recording never shows up as a
recording in DaVis on the drive.

**Ours:** the 8 MiB chunk; the 2 s modified-time tolerance (copies across file systems can lose
sub-second precision — FAT-family drives store times to 2 s); size + modified time as the
"unchanged" test; `.versions/` instead of overwriting, except in the QC folder, where a larger
new copy replaces the old one and only a JSON Lines database that *shrank* is kept
(`_keep_versions`). SHA-256 itself is **published** [fips180_4].

## Steps

```text
copy_hashing(src, dst):
    partial <- dst + ".partial"
    digest <- SHA-256()
    for each 8 MiB chunk of src: digest.update(chunk); write chunk to partial
    flush; fsync(partial)
    copy timestamps src -> partial
    atomic rename partial -> dst
    return digest

sync_to_work, for each C: file (.set files last):
    skip | adopt (hash C:, ledger "adopt") | move old copy to .versions, copy_hashing, ledger "copy"
    an OSError (DaVis has the file locked, drive pulled) -> a problem; the next run retries
```

## Sources

[fips180_4] for SHA-256. The write-then-rename pattern and the copy rules are the lab's design
(`docs/design/storage-sync.md`, sections 6–7).

## Limits

- **"Unchanged" means same size and modified time.** A file rewritten in place to the same size
  with its timestamp restored would be skipped. DaVis does not do this, as far as is known.
- **The fingerprint is only as good as the first read of C:.** A file corrupted on C: before
  its first copy is faithfully copied, fingerprinted and verified as corrupt.
- **A leftover `.partial`** (from a pulled drive) is ignored by the inventory and overwritten
  next time; it is never cleaned up otherwise.
- **The rename is atomic only within one volume**, which is always the case here (`.partial` sits
  beside its destination).
