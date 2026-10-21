---
title: The ledger: a file's state as the replay of its events
code: experimentkit/storage/ledger.py:Ledger._apply
fingerprint: 758418ac350d9434
refs: [jsonlines]
status: draft
---

# The ledger

**Code:** `experimentkit/storage/ledger.py:Ledger._apply` (line 66), `Ledger.__init__` (50),
`Ledger.add` (118).

**What it does.** Each drive keeps, beside its copy of a project,
`<drive>/<project>/.experimentkit/ledger.jsonl`: one JSON object per line [jsonlines], appended
and never rewritten. Nothing about a copy is stored anywhere else as state. The state of every
file — size, source modified time, fingerprint, how well verified — and of every recording
(which folder holds which `SetTime`, which C: folder it copies, whether it was declared safe to
delete, whether it has left C:) is **the result of replaying the events in order**.

## Method

The state is a left fold over the events, $S_n = \operatorname{apply}(S_{n-1}, e_n)$, $S_0 = \varnothing$.
For a file's verification level, ranked $\text{none} = 0 < \text{transit} = 1 < \text{full} = 2$:

$$
\text{verified} \leftarrow \begin{cases}
\text{how} & \text{verify ok and } \operatorname{rank}(\text{how}) \ge \operatorname{rank}(\text{verified}) \\
\text{verified} & \text{verify ok, lower rank} \\
\text{none, and } \text{mismatch} \leftarrow h & \text{verify failed}
\end{cases}
$$

| event | effect on the state |
|---|---|
| `copy`, `adopt` | the file's state is replaced: size, source mtime, sha256, verified (any mismatch forgotten) |
| `verify` | as above; a file with no fingerprint takes the first good full read as its fingerprint |
| `version` | the file's state is dropped (its old copy was moved to `.versions/`) |
| `rename {old, new}` | every file under `old` (and `old.set`), the recording, its C: mapping, its deletable flag and its pending files move to `new` |
| `recording {rel, set_time, source_rel}` | folder `rel` holds that `SetTime`; it copies C: folder `source_rel` (an older C: path mapped to `rel` is dropped) |
| `deletable {rel}` | was reported safe to delete from C: (clears its pending files) |
| `undeletable {rel, why, files}` | no longer safe: it gained or changed files on C:. `files`, its paths on this drive then, are kept as pending and must be re-read on the backup before it counts as archived |
| `gone {rel, safe}` | left C:, and whether it was safe when it did |

Each `add` appends one line, flushes and `fsync`s it, then applies it. On reading, a line that is
not valid JSON (half a line from a crash) or lacks a field is skipped.

**Ours:** the event vocabulary, the rank order, and "a fresh copy forgets a mismatch". JSON Lines
is a **published** format [jsonlines]; the lab's reasons for it are in `PhD-Thesis/DATA-FORMATS.md`
(cited in the module docstring, not in this repository).

## Steps

```text
Ledger(target):
    for each line of ledger.jsonl: try apply(json(line)) except bad line: skip
add(kind, fields):
    event <- {kind, at: now, fields}; append one line; flush; fsync; apply(event)
```

## Sources

[jsonlines] for the format. Replaying an append-only log into state is a general technique; no
specific source is claimed for it here.

## Limits

- **A crash costs at most the last line** — but that line may be the record of a copy that did
  complete. The next run then sees a destination file with no state, and adopts it (hashing C:
  again) if size and time agree.
- **The whole file is read and replayed every time** a `Ledger` is constructed. A sync constructs
  several per recording in a phased run; on a ledger of hundreds of thousands of lines this is the
  cost to watch.
- **A `mismatch` survives later good verifies** of the same file: only a fresh `copy` or `adopt`
  clears it, which is what forces a re-copy.
- **One writer at a time is kept by the callers, not the ledger.** `sync_project` and
  `storage verify` hold `<project>.sync-lock` (2026-10-21). Before that, a re-read that hashed a
  file just before a sync replaced it could append "verified in full" to the new copy. Code that
  writes a ledger outside those two must take the lock too.
