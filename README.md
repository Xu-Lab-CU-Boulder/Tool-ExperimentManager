# ExperimentManager

Capture at the bench: everything from "I'm about to record" to "the data is
filed and checked". Source control for how data was collected, the tools to run
a session, and the path from camera to project.

**Status:** stage 0. The repository holds the [slate](slate/README.md), a
one-file web page that puts the experiment id and take into the footage itself,
and this document, which fixes the boundaries before any more code is written.

---

## Where it sits

The research tools split into two roles.

| Role | Tool | Repo | Job |
|---|---|---|---|
| **Library** | `sigshep` | Sensor-Pipeline-GUI | Read and process signals |
| **Library** | `markertracker` | GUI-TrackAnything | Track markers in video |
| **Orchestrator** | `projectkit` | ProjectManager | **The record**: structure, sidecars, git/OneDrive boundary, bibliography |
| **Orchestrator** | ExperimentManager | this repo | **Capture**: slate, ingest, camera identity, sync, QC |

**Libraries do the heavy lifting. Orchestrators pull the strings.**

- **ExperimentManager never reimplements heavy lifting.** Reading frames from
  several cameras, tracking markers and manipulating signals belong in sigshep
  and markertracker, where every project can use them. If ExperimentManager
  needs something a library does not offer yet, it goes into the library.
- **Libraries never import an orchestrator.** sigshep and markertracker stay
  usable on any data, in any lab, in any folder layout.
- **ExperimentManager is optional. The record never depends on it.** Everything
  it produces is plain files in the layout projectkit defines, with sidecars
  projectkit can check on its own. If this project stalls or is rewritten, every
  dataset it ever filed is still readable and verifiable.

That last rule is what lets ExperimentManager be ambitious: a GUI, camera SDKs,
fast releases. projectkit stays small, conservative and dependency-free, and
nothing about your data rests on the more experimental of the two.

## The boundary with ProjectManager

One question decides where a feature goes:

> *Would I need this to read and verify my data five years from now, with
> ExperimentManager uninstalled?*

| Yes: stays in ProjectManager | No: belongs here |
|---|---|
| Sidecar format and dataset profiles | The slate |
| `dataset new / scan / check / list` | Ingest from SD cards and capture folders |
| Folder layout, stages, git/OneDrive split | Camera identity: card labels, serials |
| Stencils, bibliography, doctor, figures | Sync alignment across cameras |
| | Session QC, bench workflow, acquisition control |

## The interface

Files, not messages. ExperimentManager writes where projectkit expects, using
projectkit as a library, and the dependency only ever points one way.

1. **Paths come from projectkit.** `Config.load().stage_dir("raw")`, never a
   hardcoded path, so a change to the project blueprint is followed
   automatically.
2. **Sidecars are created through projectkit** (`Dataset.create()`, `save()`),
   so ExperimentManager cannot write one projectkit does not recognise.
3. **Capture details live in their own block** of the sidecar, such as
   `"capture": {takes, cameras, sync points}`. projectkit keeps the block and
   does not interpret it.
4. **After filing, projectkit verifies.** Ingest ends with projectkit's `scan`
   and `check`, the same integrity checks you would run by hand.
5. **Git stays the user's.** ExperimentManager writes files and never commits.

Two things must exist in projectkit before ingest relies on this contract:

- a **test that unknown sidecar blocks survive** `dataset edit` and `scan`
  untouched, because a silent drop would lose capture data without any error;
- a **schema version** in the sidecar, which ExperimentManager checks, refusing
  a newer schema than it understands.

For anything that is not Python, projectkit's read-only commands also answer in
JSON (`projectkit doctor --json`).

## Folder layout it will file into

Experiment, then take, then camera, with the original filenames untouched.
Two cameras of the same model write identical filenames, so the camera folder
is what keeps them apart.

```
3_experiments/raw/20260212_hooper1_vertical-swimming/
  take01/
    cam-left/GX010001.MP4
    cam-top/GX010001.MP4
  take02/
```

A condition change makes a new experiment, never a new take, so the id burned
into the footage by the slate can never go stale.

---

## Roadmap

Each stage is usable on its own, and each one is built only when real sessions
show it is needed. The risk to manage is months spent on tooling instead of
science.

| Stage | Delivers |
|---|---|
| 0 | This repo, the slate, the boundary and interface written down |
| 1 | `ingest --dry-run`: reports where each clip would be filed, copies nothing |
| 2 | Real ingest: copy, verify hashes, write the capture block |
| 3 | Session QC: every take decoded, every camera present, sync found at both ends, constant frame rate |
| 4 | Rig configs: which cameras a setup uses, their labels, how they sync |
| 5 | Bench app: plan → slate → record → ingest → QC, in one window, built on GUI-Modular-Widget-Library |
| 6 | Live acquisition and hardware sync |

The early stages need no GUI. The window comes once the steps under it have
proven themselves.

### Cameras in use

| Camera | Records to | Identity | Sync |
|---|---|---|---|
| Lucid Triton (10GigE) | Capture software on a PC, often image sequences | What the capture code writes | Hardware trigger or PTP between Tritons; the visual slate across camera types |
| Anker PowerConf C200 (USB-C) | Recording software on a PC | None in the file: one folder per webcam | Visual; force a fixed frame rate |
| Nikon Z6 III | SD card | Model, probably serial | Visual, or audio |
| Freefly Wave | SD card | `CAMERA.txt` card label | Visual; flicker matters at high frame rates |

---

## Running the tests

```bash
pytest
```

`tests/test_slate.py` needs Node and OpenCV and skips without them.
