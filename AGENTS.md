# AGENTS.md — Tool-ExperimentManager

Capture at the bench: the slate, ingest, and keeping DaVis projects on the work and backup
drives with quality control on the way past.

**This is an orchestrator** in the lab's library/orchestrator split. It knows where things live
and in what order work happens, and leaves the heavy lifting to libraries: it imports
`projectkit` (the record), `daviskit` (DaVis files, QC measurements) and `markertracker` (frames).
No library imports it.

The lab's conventions live in the **Lab Handbook**:
https://github.com/Xu-Lab-CU-Boulder/Lab-Code-Guide — read `conventions/` before writing code and
`practices/` before touching data or the rig. Only what is specific to *this* repository is below.

```toml
# lab-repo
name = "experimentkit"
kind = "orchestrator"
summary = "Bench capture: slate, ingest, and syncing DaVis projects to work and backup drives with QC."
answers = [
    "Is this recording backed up, and is it safe to delete from C:?",
    "What is the sync doing right now, and may I unplug a drive?",
    "Has the rig drifted? (QC runs with every sync)",
    "How do I file a slate-labelled take into the project?",
]
siblings = ["projectkit", "daviskit", "markertracker"]
```

## Design rules

1. **It never deletes experimental data.** Storage says what is safe to delete; a person deletes
   it, in DaVis. "Safe" means both drives hold it *and* the backup's copy has been re-read.
2. **It never writes into a DaVis project.** Everything it keeps sits beside the project:
   `<project>.qc/`, `<project>.keep`, `<project>.sync-running.json`, `<project>.sync-paused`.
3. **Every copy is resumable and safe to interrupt**: checksum in transit, write to `.partial`
   and rename, one append-only ledger per drive. `storage pause` stops cleanly at a recording
   boundary.
4. **Recordings are matched by DaVis's `SetTime`, never by path** — the work drive's layout is
   the user's to arrange.
5. **An alarm must be able to clear.** Status judges a recording that left C: against the drives
   as they are now, not against the flag it carried when it vanished (2026-09-20).

## Layout

```
experimentkit/
├── storage/        sync.py (the chain), ledger.py, inventory.py, volumes.py, registry.py,
│                   keep.py, qc.py, cli.py
├── (slate, ingest) the bench-capture side
docs/design/        storage-sync.md -- the design and every decision behind it
tests/              test_storage.py runs the whole chain on throwaway folders for C:, G: and F:
```

## Before you commit

```
pytest && ruff check . && ruff format --check .
```

Design and decisions: [docs/design/storage-sync.md](docs/design/storage-sync.md).
