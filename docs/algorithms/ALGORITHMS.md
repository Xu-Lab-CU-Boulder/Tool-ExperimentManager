# Algorithms: Tool-ExperimentManager

*Generated 2026-10-20 by the `algorithm-docs` skill from the pages beside it; do not edit by hand. Lines are resolved from the code at generation time.*

| Algorithm | Code | Sources | Status |
|---|---|---|---|
| [Checksummed, interruption-safe copy (and when a file is copied at all)](checksummed-copy.md) | [`experimentkit/storage/ledger.py:copy_hashing`](../../experimentkit/storage/ledger.py#L131) | `fips180_4` | draft |
| [Matching a clip to its experiment and filing it (ingest stage 1)](clip-filing.md) | [`experimentkit/ingest.py:plan_ingest`](../../experimentkit/ingest.py#L90) | none yet | draft |
| [Finding the slate's QR code in a frame](find-codes.md) | [`experimentkit/decode.py:find_codes`](../../experimentkit/decode.py#L40) | `opencv_qrcodedetector`, `opencv_qrcodedetectoraruco` (candidate) | draft |
| [The ledger: a file's state as the replay of its events](ledger-replay.md) | [`experimentkit/storage/ledger.py:Ledger._apply`](../../experimentkit/storage/ledger.py#L61) | `jsonlines` | draft |
| [When a sync runs, and in what order (quiet check, phased chain)](phased-sync.md) | [`experimentkit/storage/sync.py:_phased`](../../experimentkit/storage/sync.py#L551) | none yet | draft |
| [Reading the slate out of a clip](read-slate.md) | [`experimentkit/slate.py:read_slate`](../../experimentkit/slate.py#L121) | none yet | draft |
| [README.md](README.md) | `None` (missing) | none yet | code missing |
| [Recognising a recording by its SetTime, wherever it sits](recording-matching.md) | [`experimentkit/storage/sync.py:_match`](../../experimentkit/storage/sync.py#L108) | none yet | draft |
| [Verification, and when a recording is safe to delete from C:](safe-to-delete.md) | [`experimentkit/storage/sync.py:classify`](../../experimentkit/storage/sync.py#L356) | `fips180_4`, `gitignore` | draft |
| [The slate's QR encoder](slate-qr-encoder.md) | `None` (missing) | `iso18004_2015` (candidate), `reed1960` (candidate) | code missing |
| [Sync flips (camera synchronisation from the slate)](slate-sync.md) | `None` (missing) | `whatwg_animation_frames` | code missing |
| [Free-space log and "full in N days"](storage-forecast.md) | [`experimentkit/storage/cli.py:cmd_usage`](../../experimentkit/storage/cli.py#L256) | none yet | draft |

Sources are in [references.bib](references.bib); *candidate* means the source resembles the method but nobody has confirmed it is the one used.
