# Design: project storage sync — C: → G: → F:, and knowing when C: can be cleared

**Status:** 2026-09-19 — decisions recorded (section 15); **stages A–D built** in
`experimentkit/storage/` with tests (`tests/test_storage.py`), not yet run against the real
drives. Stage E (the sidecar `locations` block, in projectkit) is not built. Remaining open
questions are at the end.

**In one sentence:** point a command at each DaVis project on the acquisition PC, and it keeps an
accumulating snapshot of the whole project on the working drive (G:) and the backup drive (F:),
records which copy of which recording is where and whether it is verified, waits quietly for drives
that are unplugged, and tells you which recordings are safe to delete from C: — which you then do by
hand, in DaVis.

---

## 1. The problem

Tomographic PIV fills the acquisition PC's disk faster than anything else in the lab:

| Measured on 2026-09-19 | |
|---|---|
| `Project_Tomo_Setup` on C: | **427 GB**, 1,444 files, 34 recordings |
| Largest single file | **65 GB** (one camera's image stream, `Camera3-1.ims`) |
| Calibrations and project settings (`Properties/`) | 18 GB |
| C: free | **72 GB** (93 % full) — about one more recording |
| G: (working) and F: (backup) | 7.3 TB each, portable USB drives |

Copies are made by hand today. Three things went wrong or nearly did in the last three days:

- On 2026-09-18 `G:\Project_Tomo_Setup` "disappeared" mid-afternoon. It was almost certainly the
  drive being unplugged — but nothing could say whether the data existed anywhere else.
- Recordings were deleted from C: after copying, with no record of which copies had been checked.
- Processing adds result folders *inside* recordings after they have been copied, so a copy made
  on Monday is silently incomplete by Wednesday.

## 2. Requirements (from the 2026-09-19 discussion)

1. **The unit is a project.** Each DaVis project on C: gets its own folder on G: and on F:, holding
   everything: recordings, processed results, calibrations, settings.
2. **The chain is C: → G: → F:.** G: is copied from C:; F: is copied from G:.
3. **A command, and later an hourly background task** doing the same thing.
4. **Either drive may be unplugged at any time.** A missing drive is normal, not an error: its step
   waits and catches up when the drive reappears.
5. **Nothing is ever deleted automatically.** The tool says what is *safe* to delete from C:; the
   deletion is done by hand in DaVis (which keeps its project index consistent).
6. **Full verification is optional and runs in the background**, so that when C: fills up the
   answer to "can I delete this?" is already known.
7. **Each recording links to its experiment record** — its `dataset.json` and its notebook day.

## 3. Where the code lives

Three repositories each own a piece. The rule used is the one in the README's boundary section:
*would I need this to read and verify my data five years from now, with ExperimentManager
uninstalled?*

| Piece | Repo | Why there |
|---|---|---|
| Drive identity (`VOLUME.toml`), the dataset sidecar's **location** block, `check` that understands "drive not connected" | **ProjectManager** (projectkit) | Needed to *find and verify* data in five years. Already proposed in WORKFLOW-PLAN §5 item 7. |
| What a DaVis project is: recordings as folder + `.set` pairs, recording identity from `SetTime`, "has DaVis finished writing?", which folders are processed results | **Tool-DaVisKit** (daviskit) | DaVis-specific knowledge, reusable by anything that touches DaVis data. `audit_sets`, `verify_copy` and `read_settings` already live there. |
| The sync itself: registry of projects, copy engine, ledger, scheduling, waiting for drives, "safe to delete" | **ExperimentManager** (this repo) | Workflow and policy — "from *I'm about to record* to *the data is filed and checked*". |

**This differs from WORKFLOW-PLAN item 7**, which suggested daviskit do the copying. daviskit is a
library: it should know what a DaVis project *is*, not decide which drives to copy it to, when, or
how often. Keeping the policy here also means the same engine can later back up non-DaVis capture
folders (camera SD cards, Triton image folders) without daviskit growing a scheduler.

## 4. The pieces, named

| Term | Meaning |
|---|---|
| **Source** | A DaVis project on the acquisition PC, e.g. `C:\...\Project_Hula_Hoop\Project_Tomo_Setup`, plus its `.exp` file |
| **Volume** | A physical drive, identified by a `VOLUME.toml` at its root (id, purpose), never by its letter |
| **Target** | A source's copy on a volume, e.g. `Project_Tomo_Setup` on volume `xulab-work-01` (today's G:) |
| **Role** | `work` (copied from the source) or `backup` (copied from the `work` target) |
| **Recording** | One DaVis dataset: a folder and its `.set` file, identified by the `.set` file's `SetTime` so it survives renaming. Its processed results are the folders inside it. |
| **Ledger** | The append-only record of every copy and every check, kept on each volume and summarised in the project's sidecars |

## 5. What is in a DaVis project (inspected 2026-09-18/19)

```
Project_Hula_Hoop/
├── Project_Tomo_Setup.exp            ← DaVis's project descriptor, BESIDE the folder: must be copied too
└── Project_Tomo_Setup/
    ├── Properties/ + Properties.set  ← calibrations, calibration history, processing jobs (18 GB)
    │   └── Temp/                     ← scratch: do not copy
    ├── <Recording>/ + <Recording>.set    ← one recording: Camera*-N.ims streams, StreamSet.xml,
    │   │                                   Settings_Acquisition_*.xml (Dt, laser power, rates)
    │   └── <Result>/                 ← processed results, added any time later: JobHistory.xml, B*.im7/.vc7
    └── Working/ + Working.set        ← a group: recordings can nest inside other folders
```

Facts the design depends on:

- **A recording is two things**: the folder and the `.set` beside it. Copy one without the other and
  DaVis drops the recording from its project list (the fault `daviskit.io.Project.audit_sets` catches).
- **`SetTime` inside the `.set` survives a rename in DaVis**, so it is the recording's identity.
- **Processed results appear inside recordings long after they were recorded.** A recording is never
  "finished" for good; the sync copies what is new.
- **DaVis writes a recording as it streams** — files grow for tens of minutes. Copying during that
  risks both a torn copy and dropped frames on the recording itself.
- **`Temp/`** holds scratch files and is excluded.

## 6. How a sync runs

```
for each registered source:
    1. quiet check     skip if any file changed in the last QUIET minutes (a recording or
                       processing is probably running) -- unless run by hand with --now
    2. inventory       walk the source; for each file: path, size, modified time
    3. C: -> work      if the work volume is connected: copy what is new or changed
    4. work -> backup  if the backup volume is connected: copy from the work target what
                       the backup lacks
    5. reconcile       renames (by SetTime), recordings gone from C:, safe-to-delete list
    6. report          one screen of status (section 9)
```

**Copy rules.**

- **Accumulate, never mirror.** A file deleted on C: stays on G: and F: — deleting from C: after
  archiving is the whole point.
- **A changed file keeps its previous version** in `.versions/<date>/` on the target, rather than
  being overwritten (DaVis rewrites `Calibration.xml` on every calibration, for instance).
- **Write to `name.partial`, then rename.** A drive yanked mid-copy leaves a `.partial`, never a
  file that looks complete; the next run starts that file again.
- **Recordings are matched by `SetTime`**, not by path: the work drive's layout is the user's
  (decided 2026-09-19), so a rename on C: only updates the match, and a recording reorganised on
  G: is recognised where it sits. The backup moves its copies to follow G:'s layout. Nothing is
  re-copied.
- **Recordings are copied whole or not at all per run**, `.set` last: a half-copied recording never
  shows up as a recording on the target.
- **Low priority.** The copy runs at low CPU and I/O priority so an acquisition started mid-sync is
  not starved.

## 7. Verification — cheap by design

Every byte copied is read once anyway, so its checksum can be computed as it streams past:

| Step | What is checked | Extra reading |
|---|---|---|
| C: → G: | SHA-256 of each file **as read from C:** — this becomes the recording's fingerprint | none |
| G: → F: | SHA-256 **as read from G:**, compared with the fingerprint — this proves the G: copy intact | none |
| Background | re-read F:'s copy and compare | one read of F:, idle time only |
| Quick check | size and modified time against the ledger | none (metadata only) |

So a recording becomes **fully verified on both drives** with a single extra read (of F:), done in
the background. Requirement 6 is met without making the command slow. projectkit's `sha256-sample`
hashing (head and tail of files over 256 MB) remains for `dataset check` by hand; the sync records
full hashes because it gets them for free.

**Cost.** Over USB 3 to an SSD, copying runs at roughly 400–900 MB/s: a 65 GB camera file takes one
to three minutes per hop; a whole 427 GB project on first sync, 10–20 minutes per hop. Later syncs
copy only what is new.

## 8. Per-recording states, and when C: may be cleared

```
recording ─▶ on C: only ─▶ on work ─▶ on backup ─▶ SAFE TO DELETE ─▶ archived (gone from C:)
(writing)                   (G:)       (F:)          from C:
```

A recording is **safe to delete from C:** when every file it has on C: right now — including
processed results added since — has a copy on the work volume **and** on the backup volume whose
checksum matches the fingerprint, **and the backup copy has been re-read in full** (decided
2026-09-19). Checksums taken while copying ("verified in transit") are shown in the report but do
not make a recording deletable on their own.

The cost of the stricter rule is small: the re-read adds a few minutes per recording (a 65 GB
camera file reads in 1–3 minutes over USB), done in idle time. The one catch: if F: is unplugged
right after its copy, the recording stays "not yet safe" until F: is back and the re-read has run.
When C: is nearly full and a recording is waiting on only that re-read, the report says so, so it
can be run on demand (`storage verify --full --project P`).

**When a recording leaves C:**

- **It was safe to delete** → state becomes *archived*. Quiet.
- **It was not safe to delete** → a loud warning naming what exists only on C: and where the partial
  copies are. This is real data loss, or a folder moved outside DaVis.
- **It was renamed** (same `SetTime`, new name) → targets renamed to match. Quiet.

## 9. The report

```
$ experimentkit storage status

Project_Tomo_Setup   C: 427 GB (72 GB free)   work: xulab-work-01 (G:) ✓   backup: xulab-backup-01 — not connected, 1 day behind
  safe to delete from C:   6 recordings, 312 GB
      Working/Full_Mixing_Settling_Time_Dataset      186 GB   verified on both (F: re-read 2026-09-18)
      ...
  waiting for F: re-read   1 recording, 48 GB    (Power_A90_B85_19.5ms_Dt -- copied, verified in transit)
  on work only             2 recordings, 97 GB   (waiting for xulab-backup-01)
  on C: only               1 recording, 18 GB    (Squeeze_Bottle_Vortex -- still being written? last change 3 min ago)
  new since last sync      Gripper_Disturbance_Towing_Test/ParticleSeedingDensity_threshold=10 (2 files, 1.3 GB)
```

`--json` gives the same facts, as projectkit's read-only commands do.

## 10. Where the records live

| Record | Where | Why |
|---|---|---|
| **Registry**: which sources, which volumes in which role | `%APPDATA%\experimentkit\storage.toml` on the acquisition PC | source paths are machine-specific |
| **Volume identity** | `VOLUME.toml` at each drive's root: id, purpose, usual host (as WORKFLOW-PLAN item 7) | a drive letter is not an identity |
| **Ledger** | `<volume>/<target>/.experimentkit/ledger.jsonl`, append-only, one line per copy or check | lives with the data; readable with any text editor |
| **Summary per recording** | the recording's `dataset.json` (through projectkit): a `locations` list — volume, path, role, verified how and when | what git remembers; answers "where is it?" years later |

The ledger is JSON Lines for the reasons daviskit's QC database is: appending a line cannot damage
earlier lines, and a crash costs at most the last one.

**Proposed sidecar addition** (projectkit schema 1.1 — WORKFLOW-PLAN item 7 proposed a single
`location`; a recording has several copies, so this generalises it to a list):

```json
"locations": [
  {"volume": "xulab-acq-pc",    "path": "Project_Hula_Hoop/Project_Tomo_Setup/Working/Full_Mixing_Settling_Time_Dataset",
   "role": "source",  "present": false, "removed": "2026-09-22"},
  {"volume": "xulab-work-01",   "path": "Project_Tomo_Setup/Working/Full_Mixing_Settling_Time_Dataset",
   "role": "work",    "verified": "in-transit", "at": "2026-09-19T14:02"},
  {"volume": "xulab-backup-01", "path": "Project_Tomo_Setup/Working/Full_Mixing_Settling_Time_Dataset",
   "role": "backup",  "verified": "full", "at": "2026-09-19T18:40"}
]
```

## 11. Linking recordings to experiments

On first sight of a recording, the sync can fill most of a `tomo-piv` sidecar from what DaVis
already wrote, via daviskit: `dt_us`, laser power per pulse and image rate from the acquisition
snapshot (`read_settings`), the recording time from `SetTime`, the calibration in force from
`Properties/`. It also records the QC key (`daviskit validate`) and the notebook day (from the
recording date). The human fields — subject, what the run was for — stay for you to fill, and a
recording without them shows as "undescribed" in the report rather than blocking the copy.

## 12. Failure modes

| What happens | What the sync does |
|---|---|
| Drive unplugged mid-copy | leaves `.partial` files; next run restarts those files; ledger never claims them |
| Drive letter changes | found by its `VOLUME.toml`, wherever it is mounted |
| C: completely full | irrelevant to the sync (it only reads C:), but the report leads with the safe-to-delete list |
| DaVis is recording | quiet check skips the project; the hourly task tries again next hour |
| A file is locked by DaVis | skipped with a note; retried next run |
| A target file differs from the ledger (edited, corrupted) | reported, never overwritten; the source copy is kept and the old one moved to `.versions/` |
| Two PCs sync to one drive | each source is its own target folder; volume ids keep them apart |
| The ledger is lost | rebuilt from the targets' files and the sidecars (slower, same result) |

## 13. Commands (sketch)

```
experimentkit storage add <DaVis project>      register a source (asks which volumes, roles)
experimentkit storage volume init <drive>      write VOLUME.toml to a new drive
experimentkit storage sync [--project P] [--dry-run] [--now]
experimentkit storage status [--json]
experimentkit storage verify [--full]           background re-read, resumable
experimentkit storage schedule install          hourly Windows scheduled task (low priority)
```

## 14. Stages

| Stage | Delivers | Safe because |
|---|---|---|
| A | `storage status` and `sync --dry-run`: inventory, what would be copied, what is safe to delete *if* copies were verified | copies nothing |
| B | C: → G: with in-transit checksums and the ledger | only writes to G: |
| C | G: → F:, the safe-to-delete list, following renames | still never deletes |
| D | background `verify --full`, the hourly scheduled task | read-only on C: |
| E | sidecar `locations` via projectkit (schema 1.1), pre-filled `tomo-piv` fields | projectkit's contract tests |

A is useful the day it lands: it answers "what on C: is already on G: and F:?" for the copies made by
hand so far.

## 15. Decisions and open questions

**Decided 2026-09-19:**

- **Chain:** C: → G: (work) → F: (backup). Either drive may be unplugged; its step waits quietly.
- **Trigger:** a command first, then an hourly background task.
- **Unit:** a whole DaVis project, snapshotted into its own folder on each drive.
- **Safe to delete** requires the full re-read of the backup copy (section 8), not just the
  checksums taken in transit.
- **Quiet period:** 10 minutes without a file change before a recording counts as finished.
- **Drive names:** `xulab-work-01` (today's G:) and `xulab-backup-01` (today's F:), numbered on,
  with a matching physical sticker on each drive.
- **Linking:** each recording's record points to its `dataset.json` and notebook day.
- **The work drive's layout is the user's** (G: had been reorganised by hand, e.g.
  `Settlings_Time/` vs C:'s `Working/`). Recordings are matched by `SetTime` wherever they sit;
  only a recording new to the drive lands at C:'s path; a rename on C: updates the match and moves
  nothing. The backup follows the work drive's layout, moving its own copies to match.
- **Everything on the work drive is backed up**, including recordings already deleted from C:
  (their only copy was on G:); those are fingerprinted from the work drive.
- **QC runs with every sync** (daviskit's `validate` and `record_calibrations`), measuring new
  recordings while they are still on C: and before anyone deletes them; at most a few per hourly
  run, the rest next time; `storage qc --backfill` measures recordings that live only on the work
  drive. The QC database's home is `<project>.qc/` beside the DaVis project on C: -- snapshotted
  to both drives with the project -- and it is mirrored to OneDrive
  (`3_experiments/qc`). Its append-only databases replace their older copies on the drives
  rather than filling `.versions/`.

**Still open:**

1. **Registry location:** per-PC (`%APPDATA%`), or committed in the project repo alongside the list
   of the project's volumes? Source paths differ between machines, which argues for per-PC.
2. **A more reliable "acquisition complete" signal** than the quiet period: DaVis writes
   recording-rate statistics into the `.set` file when it finishes — worth checking whether that
   can confirm a finished recording.
3. **Versions kept on change:** all of them, or the last N? Calibration files are small; a
   re-recorded 65 GB stream would not be.
4. **What else counts as a source?** Only DaVis projects for now, or also the notes/raw folders and
   camera capture folders later?
5. **WORKFLOW-PLAN item 7** says daviskit copies; this design moves the copying here. Agree?
6. **Make it simple enough to forget about** (asked by the user 2026-09-21, after getting it
   working): "the current user interface and experience getting sync to work is quite complex and
   hard to use ... we should make it so this uses much simpler commands and does most of this
   backing up automatically, but the user is able to view status, pause." Getting it running took
   a volume label per drive, a registry entry run from the right shell, two `schtasks` lines, a
   keep list, and knowledge of `--phased`. What that suggests:
   - **One setup command** that labels the drives, registers the project and installs the
     scheduled tasks, run once from the user's own shell (an agent's sandbox cannot see `AppData`).
   - **Phased, ten-minute, background syncing as the only mode**, not a flag to remember.
   - **Three everyday verbs**: see what is happening (`status`/`watch`), `pause`, `resume`.
     Everything else is set-up or diagnosis.
   - **A tray icon or a notification** when something is safe to delete or a drive is needed,
     instead of a command to go and look.
   Not started; the current commands are fine for now.

