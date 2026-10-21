<!-- Built by Lab-Docs' README generator (python -m labdocs readme Tool-ExperimentManager) from docs/readme/.
     Edit those parts and rebuild; changes made here are lost. -->

# ExperimentManager

Capture at the bench, from "I'm about to record" to "the data is filed and checked": a slate that puts the experiment and take into the footage, an ingest that reads it back out, and the storage that keeps DaVis projects on a work and a backup drive, for lab members recording experiments on the rig.

no release yet · MIT licence · tests passing (78, 2026-10-20)

Source control for how data was collected, the tools to run a session, and the path from camera to project. **Status: stage 1.** The [slate](slate/README.md) puts the experiment id and take into the footage itself, and `experimentkit ingest --dry-run` reads it back out and reports where every clip would be filed; nothing is copied yet. The storage commands do copy, C: to work drive to backup, and say which recordings are safe to delete; they never delete anything and never write into a DaVis project. The package and its command are both `experimentkit`.

## Features

- **A slate for every take**: one HTML page in a browser, held up to each camera. Its QR code names the experiment and take, so the footage carries its own identity through renamed files and mixed-up SD cards; its sync bar flips and numbers each flip, to line up cameras to the frame.
- **Where would every clip go?** Point it at an SD card or a capture folder and it reads the slate in each clip's first or last 10 s, works out the camera from a `CAMERA.txt` label, and reports where each clip would be filed in the project. It never guesses: a clip with no slate, codes that disagree or a clash is listed as unsorted or a conflict, with the reason.
- **Keep DaVis projects safe**: each project copied from C: to a work drive and on to a backup drive, one recording at a time, checksummed and safe to interrupt, waiting quietly for a drive to be plugged in.
- **What is safe to delete from C:?** Only what both drives hold and the backup has been re-read in full; you delete it, in DaVis.
- **See the copy and the drives**: what is where, the running copy's progress, free space on each drive over time and the days until it is full, a screen to leave open, pause and resume.
- **Watch the rig on the way past**: quality control on new recordings and calibrations with every sync (through daviskit).
- **Camera temperatures**: read straight from the cameras while DaVis is closed, logged over the warm-up, with the laser's temperatures and status by read-only queries.

## Install

Needs Python 3.12 or newer.

It needs two lab packages that are not on PyPI: **projectkit** (the record), from the sibling folder `../Tool-ProjectManager`, so clone that beside this repository; and **markertracker** (frame sources), from Tool-TrackAnything on GitHub at commit `a934ab5`, so Git must be installed. `pyproject.toml` names both under `[tool.uv.sources]`, which only [uv](https://docs.astral.sh/uv/) reads. With uv it is one step, test tools included:

```bat
uv sync
```

pip reads none of that. To install with pip, make the `.venv` (the first of the two lines at the end of this section), put the two lab packages into it, then install this one (the second line):

```bat
.venv\Scripts\pip install -e ..\Tool-ProjectManager
.venv\Scripts\pip install "markertracker @ git+https://github.com/Xu-Lab-CU-Boulder/Tool-TrackAnything.git@a934ab51b5fbca59435b199fc0894e6eff2b8c1d"
```

Optional: daviskit (Tool-DaVisKit) installed in the same environment reads the DaVis `.set` files and runs the QC; matplotlib draws the storage plots. `cameras temps` needs `harvesters` and `genicam` from PyPI, and DaVis's own camera drivers.

```bat
uv sync
```

## Start it

Open `slate/index.html` in a browser to see the slate; it needs nothing installed. For the commands, `experimentkit --help` lists them (`ingest`, `storage`, `cameras`) and `experimentkit storage --help` the storage ones. To see ingest work with no camera or card, run the example that builds a fake SD card and a throwaway project in a temporary folder:

```bat
.venv\Scripts\python examples\ingest_plan.py
```

## Usage

**Slate every take.** Open `slate/index.html` in a browser, fill in the experiment id and take, and hold it up to each camera when the take starts (and, if you like, before it stops). Everything entered lives in the page's address, so a bookmark reopens the same slate and nothing leaves the device:

```text
slate/index.html#id=20260212_hooper1_vertical-swimming&take=3&note=18+°C
```

**Where would every clip go?** From inside a project repository (or with `--project`), point ingest at an SD card or a capture folder. It copies nothing. (Here and below, `experimentkit` is this repository's `.venv\Scripts\experimentkit`; from another folder, `uv run --project <this repository> experimentkit ...` finds it.)

```bat
experimentkit ingest E:\ --dry-run
```

Its report, for a card with two clips, looks like this:

```text
ingest --dry-run   E:\
into project       <the project>

  DCIM/100NIKON/DSC_0001.mp4
      video, 1.2 GB, camera cam-left
      slate  20260212_hooper1_vertical-swimming take03  (head, frame 12)
      ->     3_experiments/raw/20260212_hooper1_vertical-swimming/take03/cam-left/DSC_0001.mp4

  DCIM/100NIKON/DSC_0002.mp4
      video, 800 MB, camera cam-left
      UNSORTED  no slate found in the first or last 10 s

2 clip(s): 1 would be filed, 0 already filed, 0 conflict, 1 unsorted.
--dry-run: nothing was copied.
```

The exit code is 0 only when every clip would be filed or already is, so it works in a script; `--json` gives the same facts as one object.

**How a slate is read**, on a frame made up here: a QR code drawn into a noisy synthetic image, found with the two OpenCV detectors ingest uses, and parsed. A code that is not the slate's, such as a product label, is ignored rather than guessed at:

```python
import cv2
import numpy as np

from experimentkit.decode import find_codes
from experimentkit.payload import parse

code = cv2.QRCodeEncoder.create().encode("pk1:20260212_hooper1_vertical-swimming:take03")
code = cv2.resize(code, None, fx=8, fy=8, interpolation=cv2.INTER_NEAREST)
scene = np.clip(np.random.default_rng(0).normal(110, 6, (720, 1280)), 0, 255).astype(np.uint8)
scene[100:100 + code.shape[0], 400:400 + code.shape[1]] = code
frame = cv2.cvtColor(scene, cv2.COLOR_GRAY2BGR)

print(parse(find_codes(frame)[0]))
print(parse("https://example.com/label"))
```

```text
SlateCode(dataset_id='20260212_hooper1_vertical-swimming', take=3, sync=None)
None
```

**Keep a DaVis project on the work and backup drives**, from your own shell (an agent's sandbox can hide the registry it writes in `AppData`). Label each drive once, register the project, then sync and check:

```bat
experimentkit storage volume G:\ --id xulab-work-01 --purpose work
experimentkit storage volume F:\ --id xulab-backup-01 --purpose backup
experimentkit storage add C:\...\Project_Tomo_Setup --work xulab-work-01 --backup xulab-backup-01
experimentkit storage sync --phased
experimentkit storage status
```

The other storage commands (verify, deletable, progress, usage, watch, pause, keep, schedule), and what a day of recording taught it, are in [docs/guide.md](docs/guide.md). The `examples/` run ingest, the slate reader and the whole storage chain on synthetic data in temporary folders.

## More

- Documentation: the lab docs site, page *ExperimentManager* (README, algorithms and API)
- What changed: [CHANGELOG.md](CHANGELOG.md)
- Examples: [examples/](examples/)
- Licence: [LICENSE](LICENSE)
- Contact: Xu Lab, Parker McDonnell
- Guide (setup, ingest in detail, labelling cameras, storage, camera temperatures, where it sits beside projectkit, the interface, the folder layout, the roadmap, the tests): [docs/guide.md](docs/guide.md)
- The slate, and the format of its codes: [slate/README.md](slate/README.md)
- Storage's design and every decision behind it: [docs/design/storage-sync.md](docs/design/storage-sync.md)
- How each step works, with its sources: [docs/algorithms/](docs/algorithms/README.md)
- Design rules and layout, for people and agents changing the code: [AGENTS.md](AGENTS.md)
