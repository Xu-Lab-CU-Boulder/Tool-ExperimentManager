---
title: Verification, and when a recording is safe to delete from C:
code: experimentkit/storage/sync.py:classify
fingerprint: 71beb227cb33ce2b
refs: [fips180_4, gitignore]
status: draft
---

# Verification, and when a recording is safe to delete from C:

**Code:** `experimentkit/storage/sync.py:classify` (line 359), `verify` (297), `safely_backed_up`
(343), `_withdraw_deletable`, the bookkeeping at the end of `_sync_locked` (lines 800–815); the keep list
`experimentkit/storage/keep.py:matches` (42).

**What it does.** Says, for each recording on C:, where it stands — *on C: only*, *new or changed
on C:*, *on work only*, *waiting for backup re-read*, *kept on C:*, or **safe to delete** — and
the first reason it is not yet safe. Nothing deletes anything: a person deletes in DaVis. "Safe"
is the strict rule decided 2026-09-19: both drives hold every file the recording has on C: *now*
(processed results added later included), the copies match the fingerprint, **and the backup copy
has been re-read in full** — checksums taken in transit alone are not enough.

## Method

For recording $r$ with files $F(r)$ on C:, work-ledger state $w_f$ and backup-ledger state $b_f$
of the mapped path of $f$ ([recording-matching.md](recording-matching.md)), and $v(\cdot)$ the
verification level ([ledger-replay.md](ledger-replay.md)):

$$
\operatorname{safe}(r) \iff \forall f \in F(r):\;
\underbrace{w_f \wedge w_f.s = s_f \wedge w_f.m = m_f}_{\text{on work, current}}
\;\wedge\;
\underbrace{b_f \wedge (b_f.h = \varnothing \vee b_f.h = w_f.h)}_{\text{on backup}}
\;\wedge\;
\underbrace{v(w_f) \in \{\text{transit}, \text{full}\} \wedge v(b_f) = \text{full}}_{\text{verified}}
$$

and $r$ is not matched by the `.keep` file (then it is *kept on C:* instead). The checks run in
that order, so the state reported is the first that fails.

**The full re-read** (`verify`) hashes a file on a drive and compares it with its expected
fingerprint (SHA-256 [fips180_4]): on the backup, every file not yet `full`, expected = the work
drive's fingerprint when the work drive is connected, else its own record; on the work drive,
every file not yet verified at all, whose first read becomes its fingerprint if it had none. It
stops after `budget_gb` (the nightly task uses 300 GB, **ours**), and is resumable because each
result is a ledger event.

**The keep list** (`.keep` beside the project) follows three `.gitignore` rules [gitignore]: last
matching pattern wins, a leading `!` negates, a pattern with no `/` matches a folder name at any
depth. A pattern also matches everything under it (`glob/*`). Matching is Python's `fnmatch`, not
git's matcher (no `**`, no leading-`/` anchoring).

**After the sync:** every recording now *safe* or *kept* gets a `deletable` event; a deletable one
no longer safe gets `undeletable` with the files it has on C: (also at the start of a run that
finds the project busy); every mapped recording no longer on C: gets `gone {safe: was it
deletable}`. In `status`, a recording that left C: is judged against the drives as they are
*now*: it is *archived* if it was deletable then **or** `safely_backed_up` now (every file on the
work drive, and every file pending from an `undeletable`, has a `full` re-read on the backup), else it
is reported as lost too early. This is so that an alarm can clear (2026-09-20: three recordings
moved off C: by hand were backed up hours later).

**Ours, all of it:** the states and their order, the strict "re-read in full" rule, the 300 GB
nightly budget, kept recordings still verified but never offered. SHA-256 is published.

## Steps

```text
classify(r):
    if r not mapped in the work ledger, or none of its files there: on C: only
    for f in files(r): if no work state, or size/mtime differ: new or changed on C:
    for f: if no backup state, or backup hash known and != work hash: on work only
    for f: if work not verified: waiting ("work copy not yet verified")
           if backup not re-read in full: waiting ("backup copy not yet re-read")
    if .keep matches r: kept on C:
    safe to delete

verify(drive, role, budget):
    for each file in the drive's ledger that needs it (backup: not full; work: not verified):
        expected <- work fingerprint (backup, work connected) or own record
        backup with no expected hash: skip (the work re-read gives it one first)
        stop when budget exceeded
        ok <- SHA-256(file) == expected (or nothing expected)
        ledger "verify {how: full, ok}"
```

## Limits

- **`safe` means the bytes on both drives match what was first read from C:.** It cannot know
  whether C:'s bytes were right; and it cannot see a drive that fails after its re-read.
- **A backup copy with no hash** (a hand copy adopted while the work drive had no fingerprint)
  passes the "on backup" test, and is held back only by its re-read.
- **`budget_gb` is checked before each file**, so a run can read up to one file (65 GB) past it.
- **The keep list matches `r.name`**, the recording's path inside the project — patterns written
  against the work drive's (possibly different) layout do not apply.
- **Files added and deleted between two runs are never seen.** Since 2026-10-21 a deletable
  recording that gains files loses its mark at the next run, busy or not (`undeletable`), and the
  files it had then must be re-read on the backup before it counts as archived. Before that, one
  deleted before the next sync was counted archived although its new files were never copied.
  What no run inventoried, no run can know about.
