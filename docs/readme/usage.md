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

```python run
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

**Keep a DaVis project on the work and backup drives**, from your own shell (an agent's sandbox can hide the registry it writes in `AppData`). Label each drive once, register the project, then sync and check:

```bat
experimentkit storage volume G:\ --id xulab-work-01 --purpose work
experimentkit storage volume F:\ --id xulab-backup-01 --purpose backup
experimentkit storage add C:\...\Project_Tomo_Setup --work xulab-work-01 --backup xulab-backup-01
experimentkit storage sync --phased
experimentkit storage status
```

The other storage commands (verify, deletable, progress, usage, watch, pause, keep, schedule), and what a day of recording taught it, are in [docs/guide.md](../guide.md). The `examples/` run ingest, the slate reader and the whole storage chain on synthetic data in temporary folders.
