---
about: Tool-ExperimentManager
from: after-commit check
date: 2026-10-27
---

# After-commit check in Tool-ExperimentManager 2026-10-27

The after-commit check found documentation that no longer matches the code (branch `evidence-plugin`, folder `_wt-ExperimentManager`):

- code-map: docs/code-map.md is stale -- regenerate it with the code-map skill
- algorithm-docs: checksummed-copy.md: STALE -- `experimentkit/storage/ledger.py:copy_hashing` changed since this page was written
- algorithm-docs: clip-filing.md: STALE -- `experimentkit/ingest.py:plan_ingest` changed since this page was written
- algorithm-docs: find-codes.md: STALE -- `experimentkit/decode.py:find_codes` changed since this page was written
- algorithm-docs: ledger-replay.md: STALE -- `experimentkit/storage/ledger.py:Ledger._apply` changed since this page was written
- algorithm-docs: phased-sync.md: STALE -- `experimentkit/storage/sync.py:_phased` changed since this page was written
- algorithm-docs: read-slate.md: STALE -- `experimentkit/slate.py:read_slate` changed since this page was written
- algorithm-docs: recording-matching.md: STALE -- `experimentkit/storage/sync.py:_match` changed since this page was written
- algorithm-docs: safe-to-delete.md: STALE -- `experimentkit/storage/sync.py:classify` changed since this page was written
- algorithm-docs: slate-sync.md: STALE -- `experimentkit/slate.py:SlateReading.sync_range` changed since this page was written
- algorithm-docs: storage-forecast.md: STALE -- `experimentkit/storage/cli.py:cmd_usage` changed since this page was written

Update the documentation (or check it is right and say so), then close this report.
