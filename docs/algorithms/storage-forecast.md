---
title: Free-space log and "full in N days"
code: experimentkit/storage/cli.py:cmd_usage
fingerprint: 1deeb665dae72252
refs: []
status: draft
---

# Free-space log and "full in N days"

**Code:** `experimentkit/storage/cli.py:cmd_usage` (line 256) and `_plot_usage` (284); the log is
written by `experimentkit/storage/sync.py:record_usage` (622), `USAGE_EVERY_S` (619).

**What it does.** Every sync appends, at most every 30 minutes, one line of free, used and total
bytes on C: and on every connected labelled drive to
`<registry dir>/<project>.storage_usage.jsonl` (per machine, never on C:'s project side).
`storage usage` reports, per drive, the rate it is filling and when it would be full at that rate;
`--plot` draws free space against time.

## Method

From the first reading $(t_0, F_0)$ and the last $(t_1, F_1)$ of a drive's free bytes:

$$
\rho = \frac{F_0 - F_1}{\max\!\left(\dfrac{t_1 - t_0}{86\,400\ \text{s}},\ 10^{-9}\right)} \quad [\text{bytes/day}],
\qquad
T_\text{full} = \frac{F_1}{\rho} \quad [\text{days}]
$$

$T_\text{full}$ is shown only when $\rho > 0$ and $T_\text{full} < 3650$ days (a flat line has no
useful "full in"). Sizes print in GB = $10^9$ bytes.

**Ours, all of it:** the 30-minute logging interval (asked for 2026-10-02); the two-point rate;
the 10-year cut-off. No published method.

## Steps

```text
record_usage (each sync, not dry-run):
    if the log was written less than 30 min ago: skip
    append {at, drives: {C: and each connected volume id: total, used, free}}   never raises

cmd_usage:
    rows <- the log; first, last <- rows[0], rows[-1]
    days <- (last.at - first.at) in days (at least 1e-9)
    for each drive in the last row (and in the first):
        rate <- (first.free - last.free) / days
        print free, total, rate; and last.free / rate days if rate > 0 and < 3650
```

## Limits

- **Two points, whole history.** The rate is from the first reading ever to the last, not a fit
  and not recent: a day of recording after a quiet month reads as a slow fill, and deleting from
  C: in between makes C: look as if it is filling slowly or emptying (no forecast then).
- **A drive missing from the first row** (connected later) gets no rate at all, however many
  readings it has since.
- **The log's modified time is the clock.** Touching or copying the file postpones the next
  reading.
- **C: is labelled "C:" whatever drive the project is on** (`drives = {"C:": project.source}`).
