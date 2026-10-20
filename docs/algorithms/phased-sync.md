---
title: When a sync runs, and in what order (quiet check, phased chain)
code: experimentkit/storage/sync.py:_phased
fingerprint: a66a101d74827269
refs: []
status: draft
---

# When a sync runs, and in what order

**Code:** `experimentkit/storage/sync.py:_phased` (line 551), the gate in `sync_project` (663,
lines 679–687), `QUIET_MINUTES` (45), the newest-change time in `status` (lines 422–425); the
schedule `experimentkit/storage/cli.py:cmd_schedule` (541).

**What it does.** Decides whether a sync may run now, and carries the project to the drives in an
order that frees C: as early as possible. A project that changed in the last 10 minutes is left
alone (a recording or processing is probably running: copying then risks a torn copy and dropped
frames). Otherwise, with `--phased` (what the scheduled task runs), the project's own files go
first, then **one recording at a time, least recently changed first, all the way**: C: → work,
work → backup, re-read the backup — so each recording can become deletable before the next starts.

## Method

The quiet test, with $m_f$ the modified time of each file on C: except the lab's own `<project>.qc/`
and `<project>.keep`:

$$
\text{quiet} \iff \frac{t_\text{now} - \max_f m_f}{60\ \text{s}} \;\ge\; Q, \qquad Q = 10\ \text{min}
$$

A run proceeds if it is not paused (`<project>.sync-paused` absent) and (quiet or `--now`).

The phased order: the project files $P$ (those in no recording: `Properties/`, the `.exp`, the QC
folder), then recordings sorted by $\max_{f \in r} m_f$ ascending. Before each recording the pause
file is checked; a recording is skipped if every one of its files' **work-drive** state is
verified `full`.

**Ours, all of it:** $Q$ = 10 min (decided 2026-09-19); the phased order (2026-09-20: with 470 GB
waiting and C: nearly full, the whole-project order meant nothing was deletable until the last
stage finished); project files first (2026-10-02: from 09-20 to 10-02 none of them had left C:);
a run every 10 minutes rather than hourly (an hourly run could miss every quiet gap in a working
day), and a nightly re-read at 02:00 of at most 300 GB.

## Steps

```text
sync_project(project, now, phased):
    files <- inventory(C:); status <- status(project)
    log free space (at most every 30 min; see storage-forecast.md)
    if paused: stop
    if not now and not quiet: stop ("changed n min ago")
    mark running; QC of new recordings (at most 3); re-inventory
    if work drive absent: wait
    elif phased: _phased(...)
    else: everything C: -> work, then everything work -> backup
    mark deletable / gone (see safe-to-delete.md); mirror QC; clear running

_phased:
    project files: C: -> work, work -> backup
    for r in recordings, least recently changed first:
        if paused: stop ("paused after n of N")
        if all of r's work-drive files are verified full: next
        C: -> work (only r's files)
        if no backup: note "waiting"; next
        work -> backup (only r's files, by their work-drive paths)
        re-read r's files on the backup against the work fingerprints
```

## Limits

- **The quiet test is a guess.** A recording paused for more than 10 minutes and then resumed, or
  DaVis writing without changing modified times, is copied mid-write. `.set` last limits the
  damage (a half-copied recording is not a recording on the drive). A firmer "acquisition
  complete" signal is an open question in the design (§15, item 2).
- **The skip test looks at the work drive.** Read from the code: a file copied C: → work → backup
  ends with work state `transit` (as `examples/storage_chain.py` prints), and the work re-read only reads files never verified, so the
  work state rarely reaches `full`. The "already through the whole chain" shortcut then seldom
  fires, and each run calls both copy stages for every recording — each walking the whole
  project on the work drive — although they then skip every file. Correct, but slower than
  intended; the backup ledger may be what was meant.
- **"Oldest first" is by newest file**, so a recording that gained a processed result yesterday
  goes to the back of the queue.
- **No lock.** A second run can start while one is copying (see ledger-replay.md).
