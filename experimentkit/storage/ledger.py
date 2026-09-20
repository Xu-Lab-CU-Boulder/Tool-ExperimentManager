"""The record of every copy and every check, kept on the drive beside the copy it describes.

    <drive>/<project>/.experimentkit/ledger.jsonl

JSON Lines, append-only (PhD-Thesis/DATA-FORMATS.md): a crash costs at most the
last line, and nothing written before can be rewritten. The state of a file on
this drive is the result of replaying its events in order:

    copy     {rel, size, source_mtime_ns, sha256, verified}   bytes written here
    adopt    {rel, size, source_mtime_ns, sha256}             already here (a hand copy)
    verify   {rel, sha256, ok, how}                           re-read or compared in transit
    version  {rel, moved_to}                                  an older copy set aside
    rename   {old, new}                                       moved on this drive to follow another
    recording {rel, set_time, source_rel}                     which folder is which recording, and
                                                              which C: folder it copies (the drive's
                                                              layout may differ from C:'s: matched
                                                              by SetTime, decided 2026-09-19)
    deletable {rel}                                           was reported safe to delete from C:
    gone     {rel, safe}                                      left C:

`sha256` is always the checksum of the bytes as read from the file's source --
C: for the work drive, the work drive for the backup -- so it is the file's
fingerprint, and a later re-read that matches it proves the copy intact.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import shutil
from pathlib import Path

LEDGER_DIR = ".experimentkit"
CHUNK = 8 * 1024 * 1024


def _now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


class Ledger:
    """One project's copy on one drive: its events, and each file's current state."""

    def __init__(self, target: Path):
        self.target = Path(target)  # <drive>/<project>
        self.path = self.target / LEDGER_DIR / "ledger.jsonl"
        self.files: dict[str, dict] = {}
        self.recordings: dict[str, str] = {}  # folder rel on this drive -> set_time
        self.source_map: dict[str, str] = {}  # folder rel on C: -> folder rel on this drive
        self.deletable: set[str] = set()
        self.gone: dict[str, bool] = {}  # folder rel -> was it safe when it left
        if self.path.exists():
            for line in self.path.read_text(encoding="utf8").splitlines():
                try:
                    self._apply(json.loads(line))
                except (json.JSONDecodeError, KeyError):
                    continue  # half a line from a crash: skip, never fatal

    def _apply(self, e: dict) -> None:
        kind = e["kind"]
        if kind in ("copy", "adopt"):  # a fresh copy replaces any earlier state, mismatch included
            self.files[e["rel"]] = {k: e.get(k) for k in
                                    ("size", "source_mtime_ns", "sha256", "verified", "at")}
            self.files[e["rel"]]["how"] = kind
        elif kind == "verify" and e["rel"] in self.files:
            state = self.files[e["rel"]]
            if state.get("sha256") is None and e["ok"]:
                # a file with no source to compare against (archived before this tool, on
                # this drive only): its first full read IS its fingerprint
                state["sha256"] = e["sha256"]
            if e["ok"]:
                rank = {None: 0, "transit": 1, "full": 2}
                if rank.get(e["how"], 0) >= rank.get(state.get("verified"), 0):
                    state["verified"] = e["how"]
                    state["verified_at"] = e.get("at")
            else:
                state["verified"] = None
                state["mismatch"] = e.get("sha256")
        elif kind == "version":
            self.files.pop(e["rel"], None)
        elif kind == "rename":
            old, new = e["old"], e["new"]
            for rel in [r for r in self.files if r == f"{old}.set" or r.startswith(old + "/")]:
                self.files[new + rel[len(old):]] = self.files.pop(rel)
            if old in self.recordings:
                self.recordings[new] = self.recordings.pop(old)
            for src, dst in list(self.source_map.items()):
                if dst == old:
                    self.source_map[src] = new
            if old in self.deletable:
                self.deletable.discard(old)
                self.deletable.add(new)
        elif kind == "recording":
            self.recordings[e["rel"]] = e["set_time"]
            if e.get("source_rel"):
                for src, dst in list(self.source_map.items()):
                    if dst == e["rel"]:  # C: renamed it: the old C: path no longer applies
                        del self.source_map[src]
                self.source_map[e["source_rel"]] = e["rel"]
        elif kind == "deletable":
            self.deletable.add(e["rel"])
        elif kind == "gone":
            self.gone[e["rel"]] = e["safe"]

    def add(self, kind: str, **fields) -> dict:
        """Append one event and apply it."""
        event = {"kind": kind, "at": _now(), **fields}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf8") as fh:
            fh.write(json.dumps(event) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        self._apply(event)
        return event

    def state(self, rel: str) -> dict | None:
        return self.files.get(rel)


def hash_file(path: Path) -> str:
    """SHA-256 of a whole file."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_hashing(src: Path, dst: Path) -> str:
    """Copy src to dst, returning the SHA-256 of the bytes read from src.

    Writes `dst.partial` first and renames it into place only when complete, so
    a drive pulled mid-copy leaves a `.partial`, never a file that looks whole.
    The modification time is copied too, so later runs can tell it unchanged.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    partial = dst.with_name(dst.name + ".partial")
    digest = hashlib.sha256()
    with Path(src).open("rb") as fin, partial.open("wb") as fout:
        for chunk in iter(lambda: fin.read(CHUNK), b""):
            digest.update(chunk)
            fout.write(chunk)
        fout.flush()
        os.fsync(fout.fileno())
    shutil.copystat(src, partial)
    os.replace(partial, dst)
    return digest.hexdigest()
