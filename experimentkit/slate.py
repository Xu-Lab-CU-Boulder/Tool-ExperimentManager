"""Reading the slate out of a clip.

Only the start and the end of a clip are searched. The slate is held up when a
take starts, and a tail slate -- held up before stopping, when the start was
forgotten -- is the standard fallback. Searching the whole of every clip would
make ingest something nobody runs.

Frames come from markertracker's frame sources, so a video file and a folder
of images from a GigE camera are read the same way.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from markertracker.videoio import open_source

from .clips import Clip
from .decode import find_codes
from .payload import SlateCode, parse

#: Seconds searched at each end.
WINDOW_SECONDS = 10.0

#: Frames looked at per second within a window. The slate is held for seconds,
#: so a few looks a second finds it without decoding every frame.
SAMPLES_PER_SECOND = 3.0


@dataclass
class Sighting:
    code: SlateCode
    where: str          # "head" or "tail"
    frame: int


@dataclass
class SlateReading:
    """What the slate said in one clip."""
    sightings: list[Sighting] = field(default_factory=list)
    frames: int | None = None
    fps: float | None = None
    error: str = ""                 # the clip could not be read at all
    tail_searched: bool = True

    @property
    def identities(self) -> set[tuple[str, int]]:
        """Distinct (experiment, take) pairs named anywhere in the clip."""
        return {(s.code.dataset_id, s.code.take) for s in self.sightings}

    @property
    def identity(self) -> tuple[str, int] | None:
        """The one (experiment, take) this clip belongs to, or None.

        None both when nothing was found and when codes disagree. A clip that
        names two takes is not one we can file with confidence, and the report
        says which of the two it was.
        """
        found = self.identities
        return next(iter(found)) if len(found) == 1 else None

    def sync_range(self, where: str) -> tuple[int, int] | None:
        counters = [s.code.sync for s in self.sightings
                    if s.where == where and s.code.is_sync]
        return (min(counters), max(counters)) if counters else None


#: Once a code has been seen, this many seconds of sampled frames without one
#: ends the search of that window: the slate has been put down. A sync
#: sequence keeps it going, because every flip is a code.
QUIET_SECONDS = 2.0


def _search(source, start: int, stop: int, step: int, where: str,
            reading: SlateReading, seekable_per_frame: bool,
            quiet_samples: int) -> None:
    """Sample every `step`-th frame of [start, stop) for slate codes.

    An image sequence jumps straight to each sample, because loading a still
    costs the same wherever it is. A video is read straight through: seeking
    a compressed stream lands on keyframes and is often slower than decoding
    forward to the next sample.
    """
    seen = False
    quiet = 0

    def look(index: int, image) -> bool:
        """Record codes in one frame. Returns False when the search should end."""
        nonlocal seen, quiet
        found = False
        for text in find_codes(image):
            code = parse(text)
            if code is not None:
                reading.sightings.append(Sighting(code, where, index))
                found = True
        if found:
            seen, quiet = True, 0
        elif seen:
            quiet += 1
        return not (seen and quiet >= quiet_samples)

    if seekable_per_frame:
        for index in range(start, stop, step):
            if not source.seek(index):
                return
            frame = source.read()
            if frame is None or not look(index, frame.image):
                return
        return

    if start and not source.seek(start):
        return
    for index in range(start, stop):
        frame = source.read()
        if frame is None:
            return
        if (index - start) % step == 0 and not look(index, frame.image):
            return


def read_slate(clip: Clip, window_seconds: float = WINDOW_SECONDS,
               samples_per_second: float = SAMPLES_PER_SECOND) -> SlateReading:
    """Search the start and end of `clip` for slate codes. Never raises."""
    reading = SlateReading()
    try:
        source = open_source(str(clip.path))
    except Exception as exc:                       # noqa: BLE001 -- reported, not hidden
        reading.error = f"could not open: {exc}"
        return reading

    try:
        info = source.info
        fps = info.fps if info.fps and info.fps > 0 else 30.0
        reading.fps = fps
        reading.frames = info.frame_count
        window = max(1, int(round(window_seconds * fps)))
        step = max(1, int(round(fps / samples_per_second)))
        quiet = max(1, int(round(QUIET_SECONDS * samples_per_second)))
        per_frame = clip.kind == "sequence"

        head_stop = window if info.frame_count is None else min(window, info.frame_count)
        _search(source, 0, head_stop, step, "head", reading, per_frame, quiet)

        if info.frame_count is None:
            # No frame count means no seeking to the end.
            reading.tail_searched = False
        else:
            tail_start = max(head_stop, info.frame_count - window)
            if tail_start < info.frame_count:
                _search(source, tail_start, info.frame_count, step, "tail",
                        reading, per_frame, quiet)
    except Exception as exc:                       # noqa: BLE001
        reading.error = f"could not read: {exc}"
    finally:
        source.close()
    return reading
