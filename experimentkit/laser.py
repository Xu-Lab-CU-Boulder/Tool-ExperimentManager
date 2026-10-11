"""Laser temperatures and status, read (never written) over the laser's serial port.

    experimentkit cameras temps --laser COM4     adds one "laser" row to each reading

The PIV workstation's laser is a Quantel EverGreen on COM4. Its controller speaks
Quantel's ASCII protocol: `$NAME value` sets something, `$NAME ?` asks for it.
**Only questions are ever sent.** Every command this module can send is listed in
`QUERIES`, each ends in " ?", and `_ask` refuses anything else, so no code path
here can start the lamps, open a shutter or change a setting (the lab lead's
condition, 2026-10-11: "just never modify anything").

The command names come from DaVis's own driver (the strings in
Hardware.LightSources.dll: LTEMP, TEMPF, TEMPS, STATUS, STATE, SSHOT, each used with
" ?"), not from a manual, so replies are stored as the controller sent them, with a
number pulled out where there is one. DaVis holds the port while it runs: close
DaVis first, exactly as for the cameras.

Needs `pyserial`.
"""

from __future__ import annotations

import re

#: Everything this module may send. Queries only.
QUERIES = {
    "LTEMP": "$LTEMP ?",    # laser head, °C. First live reply 2026-10-11: "$LTEMP 34.6"
    "TEMPF": "$TEMPF ?",    # oven (harmonic crystal), °C: "$TEMPF 70.0"
    "TEMPS": "$TEMPS ?",    # the same 70.0: taken to be the oven set point (not confirmed)
    "STATUS": "$STATUS ?",  # status word, hex: "$STATU 7808000000"
    "STATE": "$STATE ?",    # state byte, hex: "$STATE 78"
    "SSHOT": "$SSHOT ?",    # lamp shot counter: "$SSHOT 38168652"
}
_ALLOWED = frozenset(QUERIES.values())
_NUMBER = re.compile(r"[-+]?\d+(?:\.\d+)?")


class NotAQuery(Exception):
    """Refused: the text was not one of the read-only questions in QUERIES."""


def _ask(port, command: str) -> str:
    """Send one question and return the reply line. Refuses anything but a listed query."""
    if command not in _ALLOWED or not command.endswith(" ?"):
        raise NotAQuery(f"refusing to send {command!r}: only the queries in QUERIES are allowed")
    port.reset_input_buffer()
    port.write((command + "\r\n").encode("ascii"))
    return port.readline().decode("ascii", errors="replace").strip()


def read_laser(device: str = "COM4", *, baudrate: int = 9600, timeout: float = 1.0,
               open_port=None) -> dict:
    """Ask every query once. Returns {"raw": {name: reply}, "values": {name: number}}.

    `open_port` is for tests; by default the port is opened with pyserial, without
    hardware flow control, and closed again before returning.
    """
    if open_port is None:
        import serial

        def open_port():
            return serial.Serial(device, baudrate=baudrate, bytesize=8, parity="N", stopbits=1,
                                 timeout=timeout, write_timeout=timeout,
                                 rtscts=False, dsrdtr=False, xonxoff=False)

    port = open_port()
    try:
        raw = {name: _ask(port, cmd) for name, cmd in QUERIES.items()}
    finally:
        port.close()
    values = {}
    for name, reply in raw.items():
        m = _NUMBER.search(reply.split(None, 1)[1] if " " in reply else "")  # after the echoed name
        if m and name not in ("STATUS", "STATE"):  # those two are hex words, kept raw
            values[name] = float(m.group())
    return {"raw": raw, "values": values}
