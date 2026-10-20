"""Build a fake SD card and a throwaway project, and ask ingest where each clip would go.

Shows `experimentkit.ingest.plan_ingest` (docs/algorithms/clip-filing.md) and the
windowed slate search under it (docs/algorithms/read-slate.md). The fake card holds:

    card/CAMERA.txt = cam-left
    card/DCIM/head_slate.mp4    slate in the first second      -> file
    card/DCIM/tail_slate.mp4    slate only in the last second  -> file (the tail fallback)
    card/DCIM/no_slate.mp4      no slate at all                -> unsorted
    card/DCIM/two_takes.mp4     take03 at the head, take04 at the tail -> unsorted (disagree)
    card/DCIM/wrong_id.mp4      a slate naming a dataset the project lacks -> unsorted
    other/seq_001/frame_*.png   unlabelled image sequence      -> camera "unknown-1"

Everything is synthetic and lives in a new temporary folder (the project, its
"bulk storage", the card); nothing is copied anywhere -- stage 1 writes nothing.
The QR codes come from OpenCV's encoder.

    .venv/Scripts/python examples/ingest_plan.py
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import cv2
import numpy as np

FPS, SIZE = 30, (640, 480)
ID = "20260212_hooper1_vertical-swimming"

PROJECT_TOML = """
[project]
name = "Example-Project"
slug = "example"
kind = "paper"

[paths]
data_root_env = "EK_EXAMPLE_DATA_ROOT"
bulk = "Example-Project"
raw = "3_experiments/raw"
processed = "3_experiments/processed"
"""


def scene(text: str | None = None) -> np.ndarray:
    ys, xs = np.mgrid[0:SIZE[1], 0:SIZE[0]]
    shade = (70 + 40 * np.sin(xs / 90.0) * np.cos(ys / 70.0)).astype(np.uint8)
    frame = np.dstack([shade, shade + 10, shade + 20])
    if text:
        code = cv2.QRCodeEncoder.create().encode(text)
        code = cv2.resize(code, None, fx=8, fy=8, interpolation=cv2.INTER_NEAREST)
        h, w = code.shape
        y, x = (SIZE[1] - h) // 2, (SIZE[0] - w) // 2
        frame[y:y + h, x:x + w] = cv2.cvtColor(code, cv2.COLOR_GRAY2BGR)
    return frame


def video(path: Path, seconds: list[str | None]) -> None:
    """One second of footage per entry: a slate payload, or None for plain scene."""
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, SIZE)
    for text in seconds:
        frame = scene(text)
        for _ in range(FPS):
            writer.write(frame)
    writer.release()


def main() -> None:
    root = Path(tempfile.mkdtemp(prefix="ek_ingest_plan_"))
    repo, bulk, card, other = root / "repo", root / "bulk", root / "card", root / "other"
    (repo / "experiments").mkdir(parents=True)
    (repo / "project.toml").write_text(PROJECT_TOML, encoding="utf-8")
    for stage in ("raw", "processed"):
        (bulk / "Example-Project" / "3_experiments" / stage).mkdir(parents=True)
    os.environ["EK_EXAMPLE_DATA_ROOT"] = str(bulk)

    from projectkit.config import Config
    from projectkit.dataset import Dataset

    from experimentkit.ingest import plan_ingest

    cfg = Config.load(repo)
    Dataset.create(cfg, ID, "kinematics").save()

    card.mkdir()
    (card / "CAMERA.txt").write_text("cam-left\n", encoding="utf-8")
    take3, take4 = f"pk1:{ID}:take03", f"pk1:{ID}:take04"
    blank = [None] * 12                                   # 12 s: longer than one 3.5 s window pair
    video(card / "DCIM" / "head_slate.mp4", [take3] + blank)
    video(card / "DCIM" / "tail_slate.mp4", blank + [take3])
    video(card / "DCIM" / "no_slate.mp4", blank)
    video(card / "DCIM" / "two_takes.mp4", [take3] + blank + [take4])
    video(card / "DCIM" / "wrong_id.mp4", ["pk1:20260101_nobody_nothing:take01"] + blank)
    seq = other / "seq_001"
    seq.mkdir(parents=True)
    for i, text in enumerate([take3] * FPS + [None] * FPS):
        cv2.imwrite(str(seq / f"frame_{i:05d}.png"), scene(text))

    for source in (card, other):
        plan = plan_ingest(source, cfg, window_seconds=3.5)
        print(f"source {source.name}: {len(plan.clips)} clip(s); problems: {plan.problems or 'none'}")
        for c in plan.clips:
            dest = c.destination.relative_to(bulk).as_posix() if c.destination else "-"
            print(f"  {c.clip.name:<16} camera={c.camera:<10} ({c.camera_source:<10}) "
                  f"{c.status:<9} {dest}")
            if c.reason:
                print(f"  {'':<16} reason: {c.reason}")
            heads = [s.frame for s in c.reading.sightings if s.where == "head"]
            tails = [s.frame for s in c.reading.sightings if s.where == "tail"]
            print(f"  {'':<16} sighted at head frames {heads[:4]}{'...' if len(heads) > 4 else ''}, "
                  f"tail frames {tails[:4]}{'...' if len(tails) > 4 else ''}")
    print(f"\neverything above lives in {root}")


if __name__ == "__main__":
    main()
