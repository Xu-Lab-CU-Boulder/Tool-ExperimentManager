"""Recordings the user wants to stay on C:, however well they are backed up.

A calibration's own self-cal recordings belong beside the project that was
calibrated from them: the analysis is opened and re-run for months, and the
drives are portable, so "it is on G: and F:" is not the same as "it is here".
Those recordings are still copied and still verified -- they are simply never
listed as safe to delete.

The list is a plain text file beside the project, the same place its `.exp`
and `.qc` live, and reads like a .gitignore:

    <project>.keep

        # the recordings this project's calibration came from
        Volume_Self_Cal/*
        Working/Full_Mixing_Settling_Time_Dataset

One glob per line, matched against a recording's path inside the project, with
`#` for comments. A pattern with no slash matches a recording's folder name
anywhere in the project, so `Toy_Jellyfish_Media_Only` is enough. A leading `!`
takes a recording back out again, so a broad pattern can keep a whole folder
with an exception under it. Later lines win, as in .gitignore.

The file is version-controlled by the sync like anything else beside the
project, so the drives carry it too.
"""

from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path


def read_patterns(path: Path) -> list[str]:
    """The patterns in a `.keep` file, comments and blank lines dropped."""
    if not Path(path).is_file():
        return []
    lines = Path(path).read_text(encoding="utf8", errors="replace").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]


def matches(rel: str, patterns: list[str]) -> bool:
    """Is this recording kept? `rel` is its path inside the project, e.g. Working/Tow_A."""
    kept = False
    for pattern in patterns:
        negated = pattern.startswith("!")
        glob = pattern[1:].strip() if negated else pattern
        if not glob:
            continue
        hit = fnmatch(rel, glob) or fnmatch(rel, f"{glob.rstrip('/')}/*")
        if "/" not in glob:  # a bare name matches that folder anywhere in the project
            hit = hit or fnmatch(rel.rsplit("/", 1)[-1], glob)
        if hit:
            kept = not negated
    return kept


def add(path: Path, patterns: list[str]) -> list[str]:
    """Append patterns to the `.keep` file (creating it), skipping ones already there."""
    path = Path(path)
    existing = read_patterns(path)
    new = [p for p in patterns if p not in existing]
    if not new:
        return []
    header = "" if path.exists() else (
        "# Recordings to keep on C: even once both drives hold a verified copy.\n"
        "# One glob per line; '!' takes one back out. See experimentkit storage keep --help.\n")
    with path.open("a", encoding="utf8") as fh:
        fh.write(header + "\n".join(new) + "\n")
    return new


def remove(path: Path, patterns: list[str]) -> list[str]:
    """Drop patterns from the `.keep` file; returns the ones that were there."""
    path = Path(path)
    if not path.is_file():
        return []
    kept_lines, dropped = [], []
    for line in path.read_text(encoding="utf8", errors="replace").splitlines():
        if line.strip() in patterns:
            dropped.append(line.strip())
        else:
            kept_lines.append(line)
    if dropped:
        path.write_text("\n".join(kept_lines).rstrip("\n") + "\n", encoding="utf8")
    return dropped
