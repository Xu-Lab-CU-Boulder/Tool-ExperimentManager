# This repository's icon

Its icon in the Xu Lab icon family (2026-11-14, chosen by Parker): the slate tile and white line
of LabCommand's icon, with a glyph and accent colour of its own. ClaudeTalk and ClaudeDrive sit on
a Claude-orange tile, as a pair.

| File | Use |
|---|---|
| `icon.ico` | Windows: shortcuts, the window and the taskbar. Holds 16, 20, 24, 32, 40, 48, 64, 128 and 256 px, each drawn at that size |
| `icon-512.png`, `icon-256.png` | LabCommand's card, READMEs, docs |
| `icon.svg` | anywhere it must scale |
| `draw_icons.py` | draws the whole family. `python draw_icons.py experimentmanager` redraws this one into `./final/experimentmanager/` (needs PySide6) |

LabCommand looks for `assets/icon/` by default. To change the icon, change its glyph in
`draw_icons.py` (the `TOOLS` table, key `experimentmanager`), redraw it, and copy the files back here. Keep the
family rules in the lab icon style guide: same tile, two line weights, one accent colour, no text.
