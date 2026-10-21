---
title: When a sync runs, and in what order (quiet check, phased chain)
code: experimentkit/storage/sync.py:_phased
fingerprint: f7bbcc0b030678ba
refs: []
status: draft
---

# When a sync runs, and in what order

**Code:** `experimentkit/storage/sync.py:_phased` (line 615), the gate in `sync_project` (731,
lines 746–761) and `_sync_locked` (764, lines 770–778), `QUIET_MINUTES` (45), the lock `acquire`,
the newest-change time in `status` (lines 425–428); the schedule
`experimentkit/storage/cli.py:cmd_schedule` (556).

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
file is checked; a recording is skipped if `classify` already finds it safe to delete (or kept):
every file it has on C: now is on the work drive, matches on the backup, and is re-read there in
full (see safe-to-delete.md).

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
    take <project>.sync-lock, or stop ("another sync or re-read is running")
    withdraw the deletable mark of any recording no longer safe (see safe-to-delete.md)
    if not now and not quiet: stop ("changed n min ago")
    mark running; QC of new recordings (at most 3); re-inventory
    if work drive absent: wait
    elif phased: _phased(...)
    else: everything C: -> work, then everything work -> backup
    mark deletable / gone (see safe-to-delete.md); mirror QC; clear running; release the lock

_phased:
    project files: C: -> work, work -> backup
    for r in recordings, least recently changed first:
        if paused: stop ("paused after n of N")
        if classify(r) is safe or kept: next
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
- **The skip test reads both ledgers once per recording.** Until 2026-10-21 it asked whether the
  *work* copies were re-read in full, which copies made by the sync never are (they stay
  `transit`), so it seldom fired and every run carried every recording through both stages. It
  now asks `classify`, as status does.
- **"Oldest first" is by newest file**, so a recording that gained a processed result yesterday
  goes to the back of the queue.
- **One run at a time.** A sync and a re-read each hold `<project>.sync-lock`; a run that finds it
  held waits for the next (2026-10-21). While the nightly re-read runs, the 10-minute syncs wait.
