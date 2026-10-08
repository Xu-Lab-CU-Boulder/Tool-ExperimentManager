"""Camera temperatures, read straight from the cameras over GenTL.

    experimentkit cameras temps                      print every camera's temperatures
    experimentkit cameras temps --log temps.jsonl    ...and append one row per reading

DaVis can store a camera temperature in each image, but the switch is hidden on
the PIV workstation, so this reads it the other way: through the frame grabber's
GenTL producer (Euresys eGrabber for the CoaXPress cameras), the way any GenICam
tool would. **Close DaVis first.** A second program opening a camera that DaVis
is acquiring from can make DaVis lose it.

The camera is opened read/write so a temperature selector can be stepped through
(sensor, mainboard, ...); the selector is put back as it was found. Nothing else
is written.

Needs the `egrabber` package, which ships with eGrabber rather than on PyPI:

    pip install "C:/Program Files/Euresys/eGrabber/python/egrabber-<version>-py2.py3-none-any.whl"
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

#: The SFNC feature, and the selector that picks which sensor it reports.
TEMPERATURE = "DeviceTemperature"
SELECTOR = "DeviceTemperatureSelector"

IDENTITY = ("DeviceVendorName", "DeviceModelName", "DeviceSerialNumber", "DeviceUserID")

EGRABBER_HINT = ("the egrabber package is not installed. It ships with eGrabber:\n"
                 '  pip install "C:/Program Files/Euresys/eGrabber/python/'
                 'egrabber-<version>-py2.py3-none-any.whl"')


@dataclass
class CameraReading:
    """One camera's temperatures at one moment."""
    index: int
    vendor: str = ""
    model: str = ""
    serial: str = ""
    user_id: str = ""
    temperatures_c: dict[str, float] = field(default_factory=dict)
    problem: str = ""

    @property
    def label(self) -> str:
        name = " ".join(x for x in (self.vendor, self.model) if x) or "camera"
        return f"{name} #{self.serial}" if self.serial else name


def _safe(remote, feature, dtype=None):
    try:
        return remote.get(feature, dtype) if dtype else remote.get(feature)
    except Exception:
        return None


def read_remote(remote, index: int = 0) -> CameraReading:
    """Read identity and every temperature a camera's remote module exposes.

    `remote` is anything with eGrabber's `get(feature[, dtype])`, `set(feature, value)`
    and `features()`; tests pass a fake.
    """
    ident = [_safe(remote, f, str) or "" for f in IDENTITY]
    reading = CameraReading(index, *ident)
    try:
        names = set(remote.features() or [])
    except Exception as exc:
        reading.problem = f"could not list features: {exc}"
        return reading

    if SELECTOR in names:
        original = _safe(remote, SELECTOR, str)
        try:
            for entry in _enum_entries(remote, SELECTOR):
                try:
                    remote.set(SELECTOR, entry)
                except Exception:
                    continue
                value = _safe(remote, TEMPERATURE, float)
                if value is not None:
                    reading.temperatures_c[entry] = float(value)
        finally:
            if original:
                try:
                    remote.set(SELECTOR, original)
                except Exception:
                    pass
    elif TEMPERATURE in names:
        value = _safe(remote, TEMPERATURE, float)
        if value is not None:
            reading.temperatures_c["Device"] = float(value)

    # Vendor-specific extras (e.g. SensorTemperature): any other readable float
    # whose name says temperature.
    for name in sorted(names):
        if name in (TEMPERATURE, SELECTOR) or "temperature" not in name.lower():
            continue
        value = _safe(remote, name, float)
        if isinstance(value, (int, float)):
            reading.temperatures_c[name] = float(value)

    if not reading.temperatures_c:
        reading.problem = "no temperature feature found"
    return reading


def _enum_entries(remote, feature: str) -> list[str]:
    from egrabber import query  # imported here: tests never reach it

    return list(remote.get(query.enum_entries(feature), list) or [])


def read_all(cti: str | None = None) -> list[CameraReading]:
    """Open every camera the GenTL producer can see and read its temperatures."""
    try:
        from egrabber import EGenTL, EGrabber, EGrabberDiscovery
    except ImportError as exc:
        raise RuntimeError(EGRABBER_HINT) from exc

    gentl = EGenTL(cti) if cti else EGenTL()
    discovery = EGrabberDiscovery(gentl)
    discovery.discover(find_cameras=True)

    readings = []
    for i in range(len(discovery.cameras)):
        try:
            grabber = EGrabber(discovery.cameras[i])
            readings.append(read_remote(grabber.remote, i))
            del grabber  # closes the camera before the next one opens
        except Exception as exc:  # one bad camera must not hide the others
            readings.append(CameraReading(i, problem=f"could not open: {exc}"))
    return readings


def log_rows(readings: list[CameraReading], note: str = "",
             when: datetime | None = None) -> list[dict]:
    when = when or datetime.now().astimezone()
    return [{"when": when.isoformat(timespec="seconds"), "note": note, **asdict(r)}
            for r in readings]


def append_log(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
