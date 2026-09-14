"""What on a card or in a folder counts as a recording, and which camera made it.

A **clip** is one recording: a video file, or a folder of numbered images (how
capture software for GigE cameras such as the Tritons usually writes). A folder
of images is one clip, not hundreds.

**Camera identity** comes from a label, not from guessing at metadata. Put a
`CAMERA.txt` containing one name (`cam-left`) at the top of each SD card, or in
each camera's capture folder, once; it stays true for as long as that card lives
in that camera. A clip takes the label of the nearest `CAMERA.txt` above it.
Without one, clips are grouped by the folder they came from -- two different
folders are two different cameras -- and named `unknown-1`, `unknown-2`, to be
identified later.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from markertracker.videoio import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS

LABEL_FILE = "CAMERA.txt"

#: A folder needs at least this many images to be read as an image sequence
#: rather than a few stray stills.
MIN_SEQUENCE = 2

#: Folders that cameras and operating systems put on cards, never recordings.
_SKIP_DIRS = {"system volume information", "$recycle.bin", ".trashes",
              ".spotlight-v100", ".fseventsd", "misc"}

_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class LabelError(ValueError):
    """A CAMERA.txt that does not hold a usable camera name."""


@dataclass(frozen=True)
class Clip:
    path: Path                 # the video file, or the image-sequence folder
    kind: str                  # "video" or "sequence"
    bytes: int
    files: int                 # 1 for a video; the image count for a sequence

    @property
    def name(self) -> str:
        return self.path.name


def find_clips(source: Path) -> tuple[list[Clip], list[Path]]:
    """Every clip under `source`, and the files that were not recordings.

    Hidden files, OS folders and label files are skipped silently; anything
    else that is not a clip is returned so the report can say it was ignored
    rather than letting it vanish.
    """
    clips: list[Clip] = []
    ignored: list[Path] = []

    for folder, subdirs, files in os.walk(source):
        subdirs[:] = sorted(d for d in subdirs
                            if not d.startswith(".") and d.lower() not in _SKIP_DIRS)
        here = Path(folder)
        images = sorted(f for f in files if Path(f).suffix.lower() in IMAGE_EXTENSIONS)

        if len(images) >= MIN_SEQUENCE:
            clips.append(Clip(here, "sequence",
                              sum((here / f).stat().st_size for f in images),
                              len(images)))
        else:
            ignored.extend(here / f for f in images)

        for name in sorted(files):
            path = here / name
            suffix = path.suffix.lower()
            if name.startswith(".") or name == LABEL_FILE or suffix in IMAGE_EXTENSIONS:
                continue
            if suffix in VIDEO_EXTENSIONS:
                clips.append(Clip(path, "video", path.stat().st_size, 1))
            else:
                ignored.append(path)

    return clips, ignored


def read_label(label_file: Path) -> str:
    text = label_file.read_text(encoding="utf-8-sig").strip()
    if not _LABEL.match(text):
        raise LabelError(
            f"{label_file} should hold one camera name, like cam-left "
            f"(letters, digits, hyphens, dots, underscores); found {text[:40]!r}")
    return text


def camera_for(clip: Clip, source: Path) -> tuple[str | None, Path | None]:
    """The camera label for `clip` and the file it came from, or (None, None).

    Searched from the clip's own folder upwards, stopping at `source`: a label
    outside what you pointed ingest at is somebody else's.
    """
    folder = clip.path if clip.kind == "sequence" else clip.path.parent
    source = source.resolve()
    folder = folder.resolve()
    while True:
        candidate = folder / LABEL_FILE
        if candidate.is_file():
            return read_label(candidate), candidate
        if folder == source or source not in folder.parents:
            return None, None
        folder = folder.parent


def home_folder(clip: Clip) -> Path:
    """The folder that stands in for an unlabelled camera.

    The folder a video sits in, or the folder that holds an image sequence's
    own folder: in both cases, where that camera writes its recordings.
    """
    return clip.path.parent
