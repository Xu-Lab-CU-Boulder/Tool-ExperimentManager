# Changelog

What changed in Tool-ExperimentManager, newest first, in the
[Keep a Changelog](https://keepachangelog.com/) shape (handbook `conventions/documentation.md`).
The commit that changes behaviour adds its line under **Unreleased**; a release renames that
heading after its tag. There are no tags yet; the entries below were filled in from the git
history on 2026-10-20.

## Unreleased

### Fixed
- Installing and testing no longer depend on what the TrackAnything clone's folder is called:
  markertracker now comes from GitHub (Xu-Lab-CU-Boulder/Tool-TrackAnything at `a934ab5`), so
  `uv run pytest` works on parker-desktop again. matplotlib is declared for the tests that plot
  (e8a8dfb).

### Added
- Algorithm pages under `docs/algorithms` (slate encoder and sync flips, reading slates, filing
  clips, checksummed copies, ledgers, recording matching, safe-to-delete, phased sync, the
  storage forecast), a `references.bib`, and three examples that run on synthetic data and temp
  folders only (89f0b7d).

## History before the changelog (from git, 2026-09-14 to 2026-10-17)

### October 2026

#### Added
- `cameras temps`: reads the camera temperatures while DaVis is closed and appends JSON-lines
  rows. The Coaxlink CX-16s are read through harvesters with DaVis's own `coaxlink.cti` (the
  standalone eGrabber will not open against the driver DaVis 10.2.1 needs), and the two PCO
  sCMOS cameras through DaVis's `sc2_cam.dll`; a failure on one kind never hides the other. It
  refuses while DaVis is running (d24d486, 6809ea7, dfb27d5, bcc1145).
- `cameras temps --every N`: logs the warm-up from logon until DaVis starts, with `--hours` as a
  cap; `--plot` opens daviskit's live warm-up window beside it (2e7e617, 2a3761e).
- `cameras temps --laser COMx`: reads the EverGreen laser's head and oven temperatures, status,
  state and lamp shots. Queries only: any command outside a fixed list of six is refused before
  it reaches the port (9583ce6).
- `storage drives`, `storage deletable [--paths]`, `storage progress` and
  `storage usage [--plot PNG]`: free space per drive, the recordings both drives hold verified,
  the running copy's progress (also in status and watch), and free space over time with GB/day
  and days to full (1c74229).

#### Fixed
- Phased sync now backs up the project files too. From 2026-09-20 to 2026-10-02 it copied only
  files belonging to a recording, so Properties (every calibration and the Calibration History),
  the `.exp` and the QC folder never left C: (281 files, about 23 GB). **Changes results:** check
  that projects synced in that window now have their calibrations on both the work and backup
  drives before deleting anything from C: (edff851).
- `cameras temps` checks for DaVis before every camera it opens, not only between readings. On
  2026-10-11 a reading still held one sCMOS when DaVis started, and DaVis came up without it
  (8a56527). `--every` waits up to two minutes for DaVis to finish closing instead of exiting
  (25f5171).
- `storage usage` no longer prints "full in" for a drive that is barely filling (more than ten
  years away). **Changes results:** a drive that showed a days-to-full figure may now show none
  (7dac11a).

### September 2026

#### Added
- The slate page and its encoder tests, moved here from ProjectManager, and the README's design:
  the record never depends on ExperimentManager, and files reach a project only through
  projectkit's library API (7ae9167, 1ae0724).
- `ingest --dry-run`: points at an SD card or capture folder and reports where every clip would
  be filed (experiment and take from the slate in the footage, camera from a `CAMERA.txt` label),
  copying nothing. It never guesses: an unclear clip is left unsorted with the reason, and two
  clips headed for one path are a conflict. `--json` for scripts (bbb16e0).
- Storage sync: C: to the work drive to the backup drive, with a ledger on each drive, copies
  hashed in transit, and a recording reported "safe to delete from C:" only once the backup's
  copy has been re-read in full. The tool never deletes anything. Hand-copied files are adopted,
  recordings filed elsewhere on the work drive are matched by SetTime, a recording is left alone
  for ten minutes after its last write, and QC runs with the sync (`qc --backfill` for older
  recordings). Design in `docs/design/storage-sync.md` (80af4ad, afcd0fe).
- `<project>.keep`: a gitignore-style list of recordings a project holds on to. They are still
  copied and verified, but reported as kept, not as safe to delete. Before this, status told the
  user to delete a calibration's self-cal recordings (6258ea0).
- `sync --phased`, `storage watch`, `storage pause` and `storage resume`: one recording at a
  time, oldest first, to a verified backup, so the first one frees space in about forty minutes;
  a screen to leave open; and a pause that also holds the scheduled runs and their QC step
  (59782cc, 5790e55).

#### Changed
- The scheduled sync runs every ten minutes, not hourly: on a day of recording the hourly run
  always found the project busy and never ran (59782cc, a8f4f51).

#### Fixed
- Scheduled tasks start in the repository when the package is not installed; the printed
  `schtasks` lines would otherwise have failed silently from system32 (20f065e).
- The "lost too early" alarm clears once a recording that left C: early is backed up and re-read:
  status now asks the drives, not the flag the recording carried when it left. **Changes
  results:** recordings that status listed as lost too early before 2026-09-21 may no longer be;
  recheck with `storage status` (59782cc).
- The test suite collects on a machine without cv2 or markertracker; the ingest tests skip there
  (8a856c2).
