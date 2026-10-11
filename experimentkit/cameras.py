"""Camera temperatures, read straight from the cameras over GenTL.

    experimentkit cameras temps                      print every camera's temperatures
    experimentkit cameras temps --log temps.jsonl    ...and append one row per camera

DaVis can store a camera temperature in each image, but the switch is hidden on
the PIV workstation, so this reads it the other way: through the frame grabber's
GenTL producer, the way any GenICam tool would. **Close DaVis first.** A second
program opening a camera that DaVis is acquiring from can make DaVis lose it.

The producer is **DaVis's own** Coaxlink `.cti` by default. The Coaxlink driver
on the PIV workstation is the 2020 one DaVis 10.2.1 needs; the newer standalone
eGrabber (and its Python package) refuse to open against it, and the driver must
not be updated. `harvesters` is a generic GenTL consumer, so it works with the
old producer as it is.

The camera is opened read/write so the temperature selector can be stepped
through (Mainboard, Power, FPGA, Imager on the CX-16s); it is put back as it was
found. Nothing else is written.

Needs `harvesters` (and `genicam`), from PyPI.
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

#: The producer DaVis itself uses for the CoaXPress cameras (CX-16s).
DAVIS_COAXLINK_CTI = Path(
    r"C:\DaVis_10.2.1.90613_Parker\win64\Hardware\Cameras\CoaXPress\cti\x86_64\coaxlink.cti")

HARVESTERS_HINT = "harvesters is not installed:  pip install harvesters genicam"


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


class NodeMapRemote:
    """A GenICam node map (genicam / harvesters) behind a small get/set/features face."""

    def __init__(self, node_map):
        self.nm = node_map

    def features(self) -> list[str]:
        return [n.node.name for n in self.nm.nodes]

    def get(self, feature, dtype=None):
        value = self.nm.get_node(feature).value
        return dtype(value) if dtype else value

    def set(self, feature, value) -> None:
        self.nm.get_node(feature).value = value

    def entries(self, feature) -> list[str]:
        return list(self.nm.get_node(feature).symbolics)


def _safe(remote, feature, dtype=None):
    try:
        return remote.get(feature, dtype)
    except Exception:
        return None


def _is_extra_temperature(name: str) -> bool:
    """A vendor feature like SensorTemperature -- not the SFNC pair, nor the
    register/converter/enum-entry nodes a node map exposes under them."""
    return (name not in (TEMPERATURE, SELECTOR) and name.endswith("Temperature")
            and not name.startswith(("EnumEntry_", "has")))


def read_remote(remote, index: int = 0) -> CameraReading:
    """Read identity and every temperature a camera's remote device exposes.

    `remote` needs `get(feature[, dtype])`, `set(feature, value)`, `features()`
    and `entries(enum_feature)`; tests pass a fake.
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
            for entry in remote.entries(SELECTOR):
                try:
                    remote.set(SELECTOR, entry)
                except Exception:
                    continue
                value = _safe(remote, TEMPERATURE, float)
                if value is not None:
                    reading.temperatures_c[entry] = value
        finally:
            if original:
                try:
                    remote.set(SELECTOR, original)
                except Exception:
                    pass
    elif TEMPERATURE in names:
        value = _safe(remote, TEMPERATURE, float)
        if value is not None:
            reading.temperatures_c["Device"] = value

    for name in sorted(n for n in names if _is_extra_temperature(n)):
        value = _safe(remote, name, float)
        if value is not None:
            reading.temperatures_c[name] = value

    if not reading.temperatures_c:
        reading.problem = "no temperature feature found"
    return reading


def default_cti() -> str:
    if DAVIS_COAXLINK_CTI.exists():
        return str(DAVIS_COAXLINK_CTI)
    raise RuntimeError(f"DaVis's Coaxlink producer is not at {DAVIS_COAXLINK_CTI}; pass --cti")


def read_all(cti: str | None = None) -> list[CameraReading]:
    """Every camera on the PIV workstation: the CoaXPress CX-16s, then the PCO sCMOS.

    A failure on one kind is reported as a reading with a problem; it never hides
    the other kind.
    """
    readings = []
    for reader, args in ((read_coaxpress, (cti,)), (read_pco, ())):
        try:
            readings += reader(*args)
        except Exception as exc:
            readings.append(CameraReading(len(readings), model=reader.__name__,
                                          problem=str(exc)))
    return readings


#: PCO's SC2 SDK as DaVis ships it (the sCMOS cameras, over Camera Link on the
#: Silicon Software microEnable IV cards).
DAVIS_SC2 = Path(r"C:\DaVis_10.2.1.90613_Parker\win64\Hardware\Cameras\SC2")


def read_pco(sdk: Path = DAVIS_SC2) -> list[CameraReading]:
    """Open each PCO camera through DaVis's sc2_cam.dll and read PCO_GetTemperature.

    Sensor temperature comes in tenths of a degree (the sensor is cooled, ~5 °C);
    camera body and power supply in whole degrees.
    """
    import ctypes as ct
    import os

    if not (sdk / "sc2_cam.dll").exists():
        raise RuntimeError(f"PCO's SDK is not at {sdk}")
    os.add_dll_directory(str(sdk))
    dll = ct.WinDLL(str(sdk / "sc2_cam.dll"))

    handles = []
    try:
        for _ in range(8):  # PCO_OpenCamera opens the next free camera each call
            h = ct.c_void_p()
            if dll.PCO_OpenCamera(ct.byref(h), ct.c_ushort(0)) != 0:
                break
            handles.append(h)
        readings = []
        for i, h in enumerate(handles):
            name = ct.create_string_buffer(64)
            dll.PCO_GetCameraName(h, name, ct.c_ushort(64))
            r = CameraReading(i, vendor="PCO", model=name.value.decode(errors="replace"),
                              serial=f"port{i}")
            ccd, cam, pwr = ct.c_short(), ct.c_short(), ct.c_short()
            err = dll.PCO_GetTemperature(h, ct.byref(ccd), ct.byref(cam), ct.byref(pwr))
            if err == 0:
                r.temperatures_c = {"Sensor": ccd.value / 10, "Camera": float(cam.value),
                                    "Power": float(pwr.value)}
            else:
                r.problem = f"PCO_GetTemperature error 0x{err & 0xFFFFFFFF:08x}"
            readings.append(r)
        return readings
    finally:
        for h in handles:
            dll.PCO_CloseCamera(h)


def read_coaxpress(cti: str | None = None) -> list[CameraReading]:
    """Open every camera the producer can see and read its temperatures.

    Empty grabber ports (they list as devices but cannot be opened) are skipped.
    """
    try:
        from harvesters.core import Harvester
    except ImportError as exc:
        raise RuntimeError(HARVESTERS_HINT) from exc

    # The 2020 producer lacks some newer GenTL calls, and genicam's C layer prints
    # 'GenTL producer does not implement ...' for each on stderr. Harmless.
    h = Harvester()
    try:
        h.add_file(cti or default_cti())
        h.update()
        readings = []
        for i in range(len(h.device_info_list)):
            try:
                ia = h.create(i)
            except Exception:
                continue  # an empty port on the grabber
            try:
                readings.append(read_remote(NodeMapRemote(ia.remote_device.node_map), i))
            except Exception as exc:  # one bad camera must not hide the others
                readings.append(CameraReading(i, problem=f"could not read: {exc}"))
            finally:
                ia.destroy()
        return readings
    finally:
        h.reset()


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
