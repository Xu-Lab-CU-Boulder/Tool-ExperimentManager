# Algorithms

One page per method in ExperimentManager: what it does, its formula, its steps, where it comes
from, and when it gives a wrong answer without complaining. Sources are in
[references.bib](references.bib); each entry names the code it supports and whether the match is
**verified** (the source was read far enough to know it describes what the code does) or a
**candidate** (check it before citing it in a paper). Format: the Lab Handbook's
`skills/algorithm-docs`. Python pages carry a `code:` header and a fingerprint, so the skill's
`check` reports them stale when their code changes; the two slate pages describe JavaScript and
are kept by hand. [ALGORITHMS.md](ALGORITHMS.md) is the generated index of the Python pages, with
lines resolved fresh.

Almost every number here is **ours** — a choice the lab made, with its reason on the page. The
published parts are the QR Code standard's constants (in the slate's encoder), SHA-256, and the
file formats and libraries the code relies on.

## The slate and ingest — which experiment a frame belongs to

| page | code | what it is |
|---|---|---|
| [slate-qr-encoder.md](slate-qr-encoder.md) | `slate/index.html` `QR.encode` | the page's own QR encoder: versions 1–10, Reed–Solomon, masks |
| [slate-sync.md](slate-sync.md) | `slate/index.html` `step`; `slate.py:SlateReading.sync_range` | numbered black/white flips for lining cameras up (the aligning itself is not built) |
| [find-codes.md](find-codes.md) | `experimentkit/decode.py:find_codes` | every QR code in one frame: two OpenCV detectors, two scales |
| [read-slate.md](read-slate.md) | `experimentkit/slate.py:read_slate` | the slate in a clip: sampled head and tail windows, the payload grammar, one identity or none |
| [clip-filing.md](clip-filing.md) | `experimentkit/ingest.py:plan_ingest` | where each clip would be filed, and file / already-filed / conflict / unsorted |

## Storage — copying, verifying, and when C: may be cleared

| page | code | what it is |
|---|---|---|
| [checksummed-copy.md](checksummed-copy.md) | `experimentkit/storage/ledger.py:copy_hashing` | SHA-256 while copying, `.partial` then rename; skip / adopt / copy |
| [ledger-replay.md](ledger-replay.md) | `experimentkit/storage/ledger.py:Ledger._apply` | each drive's append-only ledger, and state as its replay |
| [recording-matching.md](recording-matching.md) | `experimentkit/storage/sync.py:_match` | a recording recognised by its `SetTime`, wherever it sits |
| [safe-to-delete.md](safe-to-delete.md) | `experimentkit/storage/sync.py:classify` | **the rule to quote**: verified on both drives and re-read in full; the keep list |
| [phased-sync.md](phased-sync.md) | `experimentkit/storage/sync.py:_phased` | the 10-minute quiet check, and one recording at a time through the chain |
| [storage-forecast.md](storage-forecast.md) | `experimentkit/storage/cli.py:cmd_usage` | free space logged every 30 min; fill rate and "full in N days" |

Left out as plumbing: camera and laser readings (`cameras.py`, `laser.py` only read and log what
the hardware reports), the QC step (`storage/qc.py` decides *when*; the measuring is daviskit's,
documented there), copy-progress percentages, and the command line.

Design and every decision behind the storage pages: [../design/storage-sync.md](../design/storage-sync.md).
The slate's own documentation: [../../slate/README.md](../../slate/README.md).
Runnable examples on synthetic data: [../../examples/](../../examples/).

To check the pages against the code:

```
python ../Lab-Code-Guide/skills/algorithm-docs/scripts/algorithm_docs.py check --root .
```

It reports three files as having no `code:` header every time — this README (the checker
takes every `.md` here for a page) and the two slate pages (they describe JavaScript) — and so
always exits 1; anything else it reports is real. The same three show as "code missing" in
ALGORITHMS.md.
