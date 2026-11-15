"""The Xu Lab icon family (2026-11-14; chosen by Parker the same day).

One slate tile and one line weight from LabCommand's E7 icon; a glyph and an accent colour per tool.
ClaudeTalk and ClaudeDrive sit on a Claude-orange tile instead, as a pair.
Every size is drawn from the vector (QPainter), never shrunk from a big bitmap. See STYLE.md.
Needs PySide6.

    python draw_icons.py                # final files for every tool into ./final/<tool>/
    python draw_icons.py maskanything   # ... for the tools named (keys of TOOLS)
    python draw_icons.py sheets         # the contact sheets into ./round2/
"""
import math
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # draw without opening a window
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QFont, QGuiApplication, QImage, QLinearGradient, QPainter,
                           QPainterPath, QPen, QPolygonF, QTransform)

app = QGuiApplication.instance() or QGuiApplication(sys.argv)
HERE = Path(__file__).parent
S = 256

# ---------------------------------------------------------------- colours
HUES = {
    "claude": ("#E8956F", "#C96442"), "red": ("#F87171", "#DC2626"), "orange": ("#FB923C", "#EA580C"),
    "amber": ("#FBBF24", "#D97706"), "yellow": ("#FACC15", "#CA8A04"), "lime": ("#A3E635", "#65A30D"),
    "green": ("#4ADE80", "#16A34A"), "emerald": ("#34D399", "#059669"), "teal": ("#2DD4BF", "#0D9488"),
    "cyan": ("#22D3EE", "#0891B2"), "sky": ("#38BDF8", "#0284C7"), "blue": ("#60A5FA", "#2563EB"),
    "indigo": ("#818CF8", "#4F46E5"), "violet": ("#A78BFA", "#7C3AED"), "purple": ("#C084FC", "#9333EA"),
    "fuchsia": ("#E879F9", "#C026D3"), "pink": ("#F472B6", "#DB2777"), "rose": ("#FB7185", "#E11D48"),
    "gold": ("#FCD34D", "#B7791F"), "mint": ("#6EE7B7", "#10B981"), "stone": ("#D6D3D1", "#78716C"),
    "copper": ("#E0A877", "#A0612F"), "silver": ("#E2E8F0", "#94A3B8"), "sea": ("#5EEAD4", "#0F766E"),
    "periwinkle": ("#A5B4FC", "#6366F1"), "azure": ("#7DD3FC", "#0369A1"), "crimson": ("#FDA4AF", "#BE123C"),
}
SLATE = ("#1E293B", "#475569")


def mix(a, b, t):
    a, b = QColor(a), QColor(b)
    return QColor(round(a.red() + (b.red() - a.red()) * t), round(a.green() + (b.green() - a.green()) * t),
                  round(a.blue() + (b.blue() - a.blue()) * t))


# ---------------------------------------------------------------- drawing helpers
class G:
    """What a glyph draws with: the line colour, the tool's accent, and whether it is tiny."""

    def __init__(self, p, accent, line, small, k):
        self.p, self.a, self.line, self.small, self.k = p, accent, QColor(line), small, k

    def pen(self, w=10, col=None, cap=Qt.PenCapStyle.RoundCap):
        # refinement pass: two weights only, primary 10 and detail 7 (heavier strokes are shapes, kept as drawn)
        w = 7 if 6 <= w <= 9 else 10 if 10 <= w <= 12 else w
        return QPen(QColor(col) if col is not None else self.line, w * self.k, Qt.PenStyle.SolidLine, cap,
                    Qt.PenJoinStyle.RoundJoin)

    def acc_brush(self, rect, light=None):
        g = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        c0, c1 = QColor(self.a[0]), QColor(self.a[1])
        if len(self.a) > 2:  # (light, dark, alpha0, alpha1): a see-through white fill on a coloured tile
            c0.setAlpha(self.a[2]); c1.setAlpha(self.a[3])
        g.setColorAt(0, c0); g.setColorAt(1, c1)
        return QBrush(g)

    def fill(self, path, brush):
        self.p.setPen(Qt.PenStyle.NoPen); self.p.setBrush(brush); self.p.drawPath(path)

    def acc(self, path, clip=None):
        if clip is not None:
            path = path.intersected(clip)
        self.fill(path, self.acc_brush(path.boundingRect()))

    def glass(self, path):
        c = QColor(self.line); c.setAlpha(40); self.fill(path, QBrush(c))

    def stroke(self, path, w=10, col=None):
        self.p.setPen(self.pen(w, col)); self.p.setBrush(Qt.BrushStyle.NoBrush); self.p.drawPath(path)

    def line_(self, x1, y1, x2, y2, w=10, col=None):
        self.p.setPen(self.pen(w, col)); self.p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    def poly(self, *xy, close=True):
        path = QPainterPath(); path.moveTo(*xy[0])
        for pt in xy[1:]:
            path.lineTo(*pt)
        if close:
            path.closeSubpath()
        return path

    def disc(self, x, y, r, brush=None):
        path = QPainterPath(); path.addEllipse(QPointF(x, y), r, r)
        self.fill(path, brush if brush is not None else QBrush(self.line))
        return path

    def acc_disc(self, x, y, r):
        path = QPainterPath(); path.addEllipse(QPointF(x, y), r, r); self.acc(path); return path

    def rrect(self, x, y, w, h, r):
        path = QPainterPath(); path.addRoundedRect(QRectF(x, y, w, h), r, r); return path

    def ellipse(self, x, y, rx, ry):
        path = QPainterPath(); path.addEllipse(QPointF(x, y), rx, ry); return path

    def arrowhead(self, x, y, ang, size=18, w=10, col=None):
        a = math.radians(ang)
        for d in (150, -150):
            b = a + math.radians(d)
            self.line_(x, y, x + size * math.cos(b), y + size * math.sin(b), w, col)


def wave(x0, x1, y, amp, cycles, phase=0.0, n=80):
    path = QPainterPath()
    for i in range(n + 1):
        t = i / n
        pt = QPointF(x0 + (x1 - x0) * t, y - amp * math.sin(2 * math.pi * cycles * t + phase))
        path.moveTo(pt) if i == 0 else path.lineTo(pt)
    return path


# ---------------------------------------------------------------- glyphs (256 grid, live area 40..216)
def funnel_a(g):
    f = g.poly((48, 60), (208, 60), (146, 138), (146, 206), (110, 206), (110, 138))
    g.glass(f)
    lvl = QPainterPath(); lvl.moveTo(20, 104); lvl.cubicTo(90, 94, 160, 114, 236, 102)
    lvl.lineTo(236, 240); lvl.lineTo(20, 240); lvl.closeSubpath()
    g.acc(f, lvl); g.stroke(f)


def funnel_b(g):
    f = g.poly((52, 92), (204, 92), (146, 154), (146, 212), (110, 212), (110, 154))
    g.glass(f)
    spout = QPainterPath(); spout.addRect(QRectF(0, 150, 256, 100)); g.acc(f, spout)
    g.stroke(f)
    for x, y in ((88, 56), (128, 44), (168, 56)) if not g.small else ((128, 50),):
        g.acc_disc(x, y, 13)


def chip(g, inner=None):
    pins = (100, 128, 156) if not g.small else (110, 146)
    for c in pins:
        g.line_(c, 50, c, 70, 8); g.line_(c, 186, c, 206, 8); g.line_(50, c, 70, c, 8); g.line_(186, c, 206, c, 8)
    body = g.rrect(72, 72, 112, 112, 18); g.glass(body); g.stroke(body)
    die = g.rrect(98, 98, 60, 60, 10) if inner is None else g.rrect(92, 92, 72, 72, 12)
    g.acc(die)
    if inner:
        inner(g)


def chip_b(g):
    def mark(g):
        f = g.poly((106, 108), (150, 108), (134, 128), (134, 148), (122, 148), (122, 128))
        g.fill(f, QBrush(g.line))
    chip(g, mark)


def clapper(g):
    body = g.rrect(50, 108, 156, 100, 14)
    g.acc(body); g.stroke(body)
    if not g.small:
        g.line_(72, 144, 184, 144, 7); g.line_(72, 172, 150, 172, 7)
    g.p.save(); g.p.translate(54, 100); g.p.rotate(-14)
    bar = g.rrect(0, -30, 152, 30, 6); g.glass(bar)
    for x in (20, 62, 104) if not g.small else (40, 96):
        g.fill(g.poly((x, 0), (x + 22, 0), (x + 40, -30), (x + 18, -30)), QBrush(g.line))
    g.stroke(bar); g.p.restore()


def bending_a(g):
    g.line_(44, 208, 212, 208)
    arm = QPainterPath(); arm.moveTo(86, 150); arm.cubicTo(86, 84, 136, 52, 200, 66)
    g.stroke(arm, 34); g.p.setPen(QPen(QBrush(g.acc_brush(QRectF(80, 50, 130, 110))), 20 * g.k,
                                     Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)); g.p.drawPath(arm)
    m = g.ellipse(86, 172, 30, 30); g.fill(m, QBrush(QColor(SLATE[0]) if g.line.lightness() > 128 else QColor("#F8FAFC")))
    g.glass(m); g.stroke(m); g.disc(86, 172, 9)


def bending_b(g):
    bell = QPainterPath(); bell.moveTo(52, 128); bell.cubicTo(52, 40, 204, 40, 204, 128)
    bell.cubicTo(170, 116, 86, 116, 52, 128); bell.closeSubpath()
    g.acc(bell); g.stroke(bell)
    g.stroke(wave(52, 204, 178, 22, 1.5), 10)


def signal_a(g):
    w = wave(44, 212, 120, 46, 1.25, 0.0)
    area = QPainterPath(w); area.lineTo(212, 196); area.lineTo(44, 196); area.closeSubpath()
    g.acc(area); g.line_(44, 196, 212, 196); g.stroke(w)


def signal_b(g):
    g.p.setPen(QPen(QBrush(g.acc_brush(QRectF(40, 120, 180, 70))), 18 * g.k, Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap))
    g.p.setBrush(Qt.BrushStyle.NoBrush); g.p.drawPath(wave(44, 212, 156, 30, 1.5, 0.6))
    crook = QPainterPath(); crook.moveTo(150, 214); crook.lineTo(150, 86)
    crook.arcTo(QRectF(92, 52, 58, 68), 0, 180); crook.lineTo(92, 100)
    g.stroke(crook, 12)


def track_a(g):
    c = g.ellipse(128, 128, 60, 60); g.glass(c); g.stroke(c)
    for a in range(4):
        x, y = math.cos(a * math.pi / 2), math.sin(a * math.pi / 2)
        g.line_(128 + 44 * x, 128 + 44 * y, 128 + 84 * x, 128 + 84 * y)
    g.acc_disc(128, 128, 24 if not g.small else 30)


def track_b(g):
    path = QPainterPath(); path.moveTo(56, 194); path.cubicTo(70, 110, 160, 160, 196, 62)
    pen = g.pen(7); pen.setDashPattern([1.6, 2.2]) if not g.small else None
    g.p.setPen(pen); g.p.setBrush(Qt.BrushStyle.NoBrush); g.p.drawPath(path)
    pts = ((56, 194, 16), (124, 140, 18), (196, 62, 24)) if not g.small else ((196, 62, 30), (64, 190, 22))
    for x, y, r in pts:
        g.acc_disc(x, y, r); g.stroke(g.ellipse(x, y, r, r), 7)


def blob():
    b = QPainterPath(); b.moveTo(56, 122)
    b.cubicTo(50, 66, 138, 40, 174, 76); b.cubicTo(208, 110, 198, 172, 148, 184)
    b.cubicTo(100, 196, 62, 170, 56, 122); b.closeSubpath()
    return b


def cursor(g, x, y, sc=1.0):
    pts = [(0, 0), (0, 62), (16, 47), (28, 72), (41, 66), (29, 41), (50, 41)]
    path = g.poly(*[(x + px * sc, y + py * sc) for px, py in pts])
    g.fill(path, QBrush(g.line)); g.stroke(path, 6, SLATE[0] if g.line.lightness() > 128 else "#F8FAFC")


def mask_a(g):
    b = blob(); g.acc(b); g.stroke(b); cursor(g, 150, 140, 1.0 if not g.small else 1.15)


def mask_b(g):
    frame = g.rrect(44, 44, 168, 168, 26)
    pen = g.pen(7); pen.setDashPattern([2.2, 2.0]); g.p.setPen(pen); g.p.setBrush(Qt.BrushStyle.NoBrush)
    g.p.drawPath(frame)
    b = blob().translated(0, 6); g.acc(b); g.stroke(b)
    g.disc(124, 128, 12); g.stroke(g.ellipse(124, 128, 24, 24), 6)


def spiral(cx, cy, r0, r1, turns, n=160):
    path = QPainterPath()
    for i in range(n + 1):
        t = i / n; a = 2 * math.pi * turns * t; r = r0 + (r1 - r0) * t
        pt = QPointF(cx + r * math.cos(a), cy + r * math.sin(a))
        path.moveTo(pt) if i == 0 else path.lineTo(pt)
    return path


def flow_a(g):
    g.acc_disc(128, 128, 82)
    g.stroke(spiral(128, 128, 6, 66, 2.25 if not g.small else 1.5), 10)


def flow_b(g):
    for y0, s in ((70, -1), (186, 1)):
        path = QPainterPath(); path.moveTo(40, y0); path.cubicTo(90, y0, 92, y0 + s * 26, 128, y0 + s * 26)
        path.cubicTo(164, y0 + s * 26, 166, y0, 216, y0); g.stroke(path, 10)
    if not g.small:
        g.line_(40, 128, 72, 128, 8); g.line_(184, 128, 216, 128, 8)
    g.acc_disc(128, 128, 36); g.stroke(g.ellipse(128, 128, 36, 36))


def arrow(g, x, y, ang, L, w=10, col=None):
    a = math.radians(ang); dx, dy = math.cos(a) * L / 2, math.sin(a) * L / 2
    g.line_(x - dx, y - dy, x + dx, y + dy, w, col); g.arrowhead(x + dx, y + dy, ang, L * 0.42, w, col)


def davis_a(g):
    fr = g.rrect(44, 44, 168, 168, 22); g.glass(fr); g.stroke(fr)
    # a vortex: arrows turning about the centre; the accent paints the arrows
    accent = QColor(g.a[0])
    pts = (-1, 0, 1) if not g.small else (-1, 1)
    for i in pts:
        for j in pts:
            if i == 0 and j == 0:
                g.disc(128, 128, 8, QBrush(accent)); continue
            x, y = 128 + 46 * i, 128 + 46 * j
            ang = math.degrees(math.atan2(j, i)) + 90
            arrow(g, x, y, ang, 34 if not g.small else 44, 9, accent)


def davis_b(g):
    sheet = g.poly((112, 124), (214, 58), (214, 190))
    c = QColor(g.a[0]); c.setAlpha(150); g.fill(sheet, QBrush(c))
    body = g.rrect(42, 96, 64, 56, 10); g.glass(body); g.stroke(body)
    lens = g.rrect(104, 108, 16, 32, 4); g.fill(lens, QBrush(g.line))
    if not g.small:
        g.acc_disc(178, 104, 7); g.acc_disc(160, 140, 7); g.acc_disc(196, 154, 7)


def bell_path(cx, top, half, rim):
    b = QPainterPath(); b.moveTo(cx - half, rim)
    b.cubicTo(cx - half, top - 10, cx + half, top - 10, cx + half, rim)
    b.cubicTo(cx + half * 0.5, rim - 12, cx - half * 0.5, rim - 12, cx - half, rim); b.closeSubpath()
    return b


def wake_rings(g, y0):
    """Vortex rings left behind, seen at a slant: flat ellipses shrinking downstream."""
    g.stroke(g.ellipse(128, y0, 52, 12), 10)
    if not g.small:
        g.stroke(g.ellipse(128, y0 + 34, 34, 8), 7)


def swim_a(g):
    b = bell_path(128, 48, 66, 118); g.acc(b); g.stroke(b)
    wake_rings(g, 164)


def swim_b(g):
    wake_rings(g, 176)
    g.acc_disc(128, 104, 40); g.stroke(g.ellipse(128, 104, 40, 40))
    g.stroke(g.poly((108, 52), (128, 36), (148, 52), close=False), 10)


def spice_a(g):
    tri = g.poly((80, 58), (80, 198), (194, 128)); g.acc(tri)
    g.line_(46, 96, 80, 96); g.line_(46, 160, 80, 160); g.line_(194, 128, 214, 128)
    g.stroke(tri)
    if not g.small:
        g.stroke(wave(92, 148, 128, 16, 1), 7)


def spice_b(g):
    g.p.setPen(QPen(QBrush(g.acc_brush(QRectF(40, 60, 180, 70))), 16 * g.k, Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap)); g.p.setBrush(Qt.BrushStyle.NoBrush)
    g.p.drawPath(wave(48, 208, 92, 30, 1))
    z = [(44, 170), (76, 170)] + [(86 + 14 * i, 146 if i % 2 == 0 else 194) for i in range(7)] + [(184, 170), (212, 170)]
    g.stroke(g.poly(*z, close=False), 10)


def figure(g):
    for x, h in ((80, 56), (118, 92), (156, 124)):
        g.acc(g.rrect(x, 192 - h, 26, h, 5))
    path = g.poly((72, 150), (110, 112), (146, 126), (194, 66), close=False); g.stroke(path, 8)
    g.disc(194, 66, 12)
    g.stroke(g.poly((56, 50), (56, 200), (212, 200), close=False))


def slide(g):
    scr = g.rrect(44, 52, 168, 112, 12); g.glass(scr)
    g.acc(g.rrect(64, 74, 58, 68, 8))
    if not g.small:
        for y, x1 in ((86, 190), (108, 182), (130, 168)):
            g.line_(138, y, x1, y, 7)
    g.stroke(scr); g.line_(128, 164, 128, 196)
    g.stroke(g.poly((96, 212), (128, 196), (160, 212), close=False))


def table(g):
    t = g.rrect(46, 60, 164, 136, 16)
    hdr = QPainterPath(); hdr.addRect(QRectF(0, 0, 256, 102)); g.glass(t); g.acc(t, hdr)
    rows = (136, 166) if not g.small else (149,)
    cols = (101, 155) if not g.small else (128,)
    for y in rows:
        g.line_(46, y, 210, y, 6)
    for x in cols:
        g.line_(x, 102, x, 196, 6)
    g.line_(46, 102, 210, 102, 8); g.stroke(t)


def diagram(g):
    top = g.rrect(90, 46, 76, 50, 12); g.acc(top); g.stroke(top)
    g.stroke(g.poly((128, 96), (128, 128), close=False), 8)
    g.stroke(g.poly((80, 158), (80, 128), (176, 128), (176, 158), close=False), 8)
    for x in (42, 138):
        b = g.rrect(x, 158, 76, 50, 12); g.glass(b); g.stroke(b)


def pitch(g):
    ph = g.rrect(82, 38, 92, 180, 20); g.glass(ph)
    g.acc(g.rrect(98, 62, 60, 44, 7))
    if not g.small:
        for y, x1 in ((126, 158), (146, 150), (166, 140)):
            g.line_(98, y, x1, y, 7)
    g.stroke(ph); g.line_(116, 198, 140, 198, 7)


def matlab_a(g):
    pts = ((88, 176, -45), (124, 136, -38), (160, 108, -28), (196, 86, -18)) if not g.small else ((100, 156, -40), (170, 98, -20))
    for x, y, a in pts:
        arrow(g, x, y, a, 34 if not g.small else 56, 12, g.a[0])
    g.stroke(g.poly((56, 50), (56, 200), (212, 200), close=False))


def matlab_b(g):
    path = QPainterPath(); path.moveTo(66, 176); path.cubicTo(100, 60, 140, 190, 200, 70); g.stroke(path, 9)
    tri = g.poly((146, 140), (146, 206), (200, 173)); g.acc(tri); g.stroke(tri, 7)
    g.stroke(g.poly((56, 50), (56, 200), (126, 200), close=False))


def shell(g):
    w = g.rrect(42, 54, 172, 148, 16); g.glass(w)
    g.acc(g.rrect(58, 102, 50, 84, 7))
    if not g.small:
        for y in (102, 148):
            g.stroke(g.rrect(120, y, 78, 38, 7), 6)
        for x in (64, 82, 100):
            g.disc(x, 72, 5)
    g.line_(42, 88, 214, 88, 8); g.stroke(w)


def web_a(g):
    g.acc_disc(128, 128, 76)
    g.stroke(g.ellipse(128, 128, 32, 76), 7); g.line_(128, 52, 128, 204, 7)
    for y, half in ((96, 68), (160, 68)) if not g.small else ():
        g.line_(128 - half, y, 128 + half, y, 7)
    g.line_(52, 128, 204, 128, 7); g.stroke(g.ellipse(128, 128, 76, 76))


def web_b(g):
    w = g.rrect(42, 54, 172, 148, 16); g.glass(w)
    for x, y in ((60, 104), (134, 104), (60, 152), (134, 152)) if not g.small else ((60, 104), (134, 104)):
        g.acc(g.rrect(x, y, 62, 36, 7))
    g.line_(42, 88, 214, 88, 8); g.stroke(w)
    if not g.small:
        g.stroke(g.rrect(100, 64, 92, 14, 7), 5)


def book_pages():
    left = QPainterPath(); left.moveTo(128, 76); left.cubicTo(104, 60, 70, 58, 42, 66); left.lineTo(42, 192)
    left.cubicTo(70, 184, 104, 186, 128, 202); left.closeSubpath()
    right = QTransform(-1, 0, 0, 1, 256, 0).map(left)
    return left, right


def book_a(g):
    l, r = book_pages()
    g.acc(l); g.acc(r)
    if not g.small:
        for y in (98, 122, 146):
            g.line_(64, y - 4, 104, y + 2, 6); g.line_(152, y + 2, 192, y - 4, 6)
    g.stroke(l); g.stroke(r)


def book_b(g):
    cov = g.rrect(58, 42, 140, 172, 14); g.acc(cov); g.stroke(cov)
    g.line_(86, 42, 86, 214, 8)
    g.stroke(g.poly((130, 104), (112, 128), (130, 152), close=False), 9)
    g.stroke(g.poly((158, 104), (176, 128), (158, 152), close=False), 9)


def page_path(x, y, w, h, fold=30):
    return QPainterPath() if False else _page(x, y, w, h, fold)


def _page(x, y, w, h, fold):
    pth = QPainterPath(); pth.moveTo(x, y); pth.lineTo(x + w - fold, y); pth.lineTo(x + w, y + fold)
    pth.lineTo(x + w, y + h); pth.lineTo(x, y + h); pth.closeSubpath(); return pth


def docs(g):
    pg = _page(54, 40, 120, 156, 32); g.glass(pg)
    if not g.small:
        for y, x1 in ((84, 140), (108, 150), (132, 120)):
            g.line_(76, y, x1, y, 7)
    g.stroke(pg); g.stroke(g.poly((142, 40), (142, 72), (174, 72), close=False), 7)
    g.line_(176, 182, 206, 212, 16)
    c = g.ellipse(156, 162, 30, 30); g.acc(c); g.stroke(c)


def folder_path():
    f = QPainterPath(); f.moveTo(44, 84); f.lineTo(44, 196); f.quadTo(44, 208, 56, 208); f.lineTo(200, 208)
    f.quadTo(212, 208, 212, 196); f.lineTo(212, 100); f.quadTo(212, 88, 200, 88); f.lineTo(124, 88)
    f.lineTo(108, 68); f.lineTo(56, 68); f.quadTo(44, 68, 44, 80); f.closeSubpath(); return f


def project_a(g):
    paper = _page(88, 40, 96, 100, 22); g.fill(paper, QBrush(g.line))
    f = folder_path(); g.acc(f, g.rrect(0, 104, 256, 152, 0) if True else None)
    g.stroke(f)
    g.line_(44, 104, 212, 104, 8)


def project_b(g):
    pg = _page(58, 38, 140, 180, 30); g.glass(pg)
    g.acc(g.rrect(78, 62, 72, 22, 6))
    rows = ((78, 112, 170), (100, 138, 178), (100, 164, 160), (78, 190, 150)) if not g.small else ((78, 120, 170), (100, 160, 170))
    for x0, y, x1 in rows:
        g.line_(x0, y, x1, y, 7)
    g.stroke(pg)


def box_a(g):
    top = g.poly((128, 46), (206, 86), (128, 126), (50, 86)); g.acc(top)
    body = g.poly((50, 86), (128, 46), (206, 86), (206, 172), (128, 212), (50, 172)); g.glass(body)
    g.stroke(body); g.stroke(g.poly((50, 86), (128, 126), (206, 86), close=False))
    g.line_(128, 126, 128, 212)


def clip_b(g):
    b = g.rrect(58, 52, 140, 164, 14); g.glass(b); g.stroke(b)
    g.fill(g.rrect(96, 38, 64, 30, 9), QBrush(g.line))
    for y in (100, 140, 180) if not g.small else (104, 164):
        g.acc(g.rrect(78, y - 12, 24, 24, 5)); g.line_(118, y, 176, y, 7)


def db(g):
    body = QPainterPath(); body.moveTo(60, 70); body.lineTo(60, 186); body.arcTo(QRectF(60, 168, 136, 36), 180, 180)
    body.lineTo(196, 70); body.closeSubpath()
    g.acc(body)
    top = g.ellipse(128, 70, 68, 20); g.fill(top, QBrush(g.line))
    if not g.small:
        for y in (110, 148):
            arc = QPainterPath(); arc.arcMoveTo(QRectF(60, y - 18, 136, 36), 180); arc.arcTo(QRectF(60, y - 18, 136, 36), 180, 180)
            g.stroke(arc, 7)
    g.stroke(body); g.stroke(top)


def auri_a(g):
    d = g.ellipse(128, 128, 78, 78); g.acc(d)
    for i in range(4):  # the moon jelly's four gonads, as petals around the centre
        g.p.save(); g.p.translate(128, 128); g.p.rotate(45 + 90 * i)
        g.fill(g.ellipse(34, 0, 22, 13), QBrush(g.line)); g.p.restore()
    g.stroke(d)


def auri_b(g):
    b = bell_path(128, 50, 70, 126); g.acc(b)
    for x in (88, 128, 168) if not g.small else (100, 156):
        t = QPainterPath(); t.moveTo(x, 124)
        t.cubicTo(x - 14, 150, x + 14, 176, x, 210); g.stroke(t, 8)
    g.stroke(b)


def cloud_path():
    c = QPainterPath()
    for x, y, r in ((92, 140, 38), (140, 114, 50), (182, 148, 32)):
        e = QPainterPath(); e.addEllipse(QPointF(x, y), r, r); c = c.united(e)
    r = QPainterPath(); r.addRoundedRect(QRectF(54, 136, 160, 44), 22, 22); return c.united(r)


def drive_a(g):
    c = cloud_path(); g.acc(c); g.stroke(c)
    g.line_(132, 168, 132, 118, 12); g.arrowhead(132, 112, -90, 22, 12)


def drive_b(g):
    pn = g.rrect(52, 44, 152, 168, 18); g.glass(pn)
    g.acc(g.rrect(68, 62, 120, 38, 9))
    for y in (124, 152, 180) if not g.small else (130, 170):
        g.disc(80, y, 7); g.line_(98, y, 176, y, 7)
    g.stroke(pn)


def talk_a(g):
    cap = g.rrect(100, 40, 56, 104, 28); g.acc(cap); g.stroke(cap)
    u = QPainterPath(); u.arcMoveTo(QRectF(72, 64, 112, 112), 180); u.arcTo(QRectF(72, 64, 112, 112), 180, 180)
    g.stroke(u); g.line_(128, 176, 128, 204); g.line_(98, 208, 158, 208)


def talk_b(g):
    b = QPainterPath(); b.addRoundedRect(QRectF(42, 52, 172, 124), 30, 30)
    tail = g.poly((78, 160), (70, 214), (124, 168)); b = b.united(tail)
    g.acc(b); g.stroke(b)
    hs = (22, 46, 30, 54, 24) if not g.small else (30, 54, 30)
    xs = [128 + (i - (len(hs) - 1) / 2) * 26 for i in range(len(hs))]
    for x, h in zip(xs, hs):
        g.line_(x, 114 - h / 2, x, 114 + h / 2, 11)


def flask_e7(g):
    """LabCommand's E7, for reference: the anchor of the family."""
    top, neck, base = 36, 92, 222
    path = QPainterPath()
    path.moveTo(102, top); path.lineTo(154, top); path.lineTo(154, neck)
    path.lineTo(214, 202); path.quadTo(224, base, 202, base)
    path.lineTo(54, base); path.quadTo(32, base, 42, 202)
    path.lineTo(102, neck); path.closeSubpath()
    g.glass(path)
    lq = QPainterPath(); lq.moveTo(20, 118); lq.cubicTo(96, 106, 160, 130, 236, 118)
    lq.lineTo(236, 240); lq.lineTo(20, 240); lq.closeSubpath(); g.acc(path, lq)
    cx, cy, r = 128, 166, 31
    pts = [(cx + r * math.cos(math.radians(-90 + i * 72)), cy + r * math.sin(math.radians(-90 + i * 72))) for i in range(5)]
    for x, y in pts:
        g.line_(cx, cy, x, y, 5)
    for x, y in pts:
        g.disc(x, y, 11)
    g.disc(cx, cy, 14)
    g.stroke(path); g.line_(94, top, 162, top)


# ---------------------------------------------------------------- the tools
# key: (display name, repository, hue, [(option letter, idea, glyph)])
TOOLS = {
    "labcommand": ("LabCommand", "Tool-LabCommand", "claude", [("E7", "chosen: flask + hub", flask_e7)]),
    "claudedrive": ("ClaudeDrive", "Tool-AgentTray", "claude", [("A", "cloud, upload arrow", drive_a), ("B", "the tray list", drive_b)]),
    "claudetalk": ("ClaudeTalk", "Tool-Dictate", "claude", [("A", "microphone", talk_a), ("B", "speech bubble, voice bars", talk_b)]),
    "auri": ("Auri", "Agent-Auri", "fuchsia", [("A", "moon jelly from above", auri_a), ("B", "jelly from the side", auri_b)]),
    "datafunnel": ("DataFunnel", "Tool-DataFunnel", "emerald", [("A", "funnel, filling", funnel_a), ("B", "funnel, samples dropping in", funnel_b)]),
    "firmware": ("DataFunnel firmware", "Firmware-DataFunnel", "lime", [("A", "microcontroller chip", chip), ("B", "chip with funnel mark", chip_b)]),
    "experimentmanager": ("ExperimentManager", "Tool-ExperimentManager", "teal", [("A", "clapperboard (the slate)", clapper)]),
    "bending": ("Bending Mechanism", "GUI-BendingMechanism-Controller", "green", [("A", "motor bending an arm", bending_a), ("B", "bell over a sine drive", bending_b)]),
    "signalshepherd": ("SignalShepherd", "Tool-SignalMaster", "blue", [("A", "signal, area under it", signal_a), ("B", "shepherd's crook over a signal", signal_b)]),
    "trackanything": ("TrackAnything", "Tool-TrackAnything", "pink", [("A", "crosshair on a marker", track_a), ("B", "markers along a track", track_b)]),
    "maskanything": ("MaskAnything", "Tool-MaskAnything", "violet", [("A", "mask + pointer click", mask_a), ("B", "mask in a selection box", mask_b)]),
    "flowkit": ("FlowKit", "Lib-FlowKit", "cyan", [("A", "vortex", flow_a), ("B", "streamlines past a body", flow_b)]),
    "daviskit": ("DaVisKit", "Tool-DaVisKit", "indigo", [("A", "PIV vector field", davis_a), ("B", "camera + laser sheet", davis_b)]),
    "swimulator": ("FluidSwimulator", "Tool-FluidSwimulator", "sky", [("A", "bell shedding vortex rings", swim_a), ("B", "sphere pulled up, wake", swim_b)]),
    "spicekit": ("SpiceKit", "Tool-SpiceKit", "yellow", [("A", "op-amp", spice_a), ("B", "resistor under a sine", spice_b)]),
    "figurekit": ("FigureKit", "Tool-FigureKit", "red", [("A", "bars + trend line", figure)]),
    "slidekit": ("SlideKit", "Tool-SlideKit", "amber", [("A", "slide on a screen", slide)]),
    "tablekit": ("TableKit", "Tool-TableKit", "orange", [("A", "table, coloured header", table)]),
    "diagramkit": ("DiagramKit", "Tool-DiagramKit", "purple", [("A", "boxes and connectors", diagram)]),
    "pitchpal": ("PitchPal", "Tool-PitchPal", "rose", [("A", "phone following the slide", pitch)]),
    "plotting": ("MATLAB plotting", "General-Plotting-Presenting-Tools", "crimson", [("A", "quiver arrows", matlab_a), ("B", "curve + play (video)", matlab_b)]),
    "qtshell": ("qtshell", "GUI-Modular-Widget-Library", "silver", [("A", "window with panels", shell)]),
    "labweb": ("LabWeb", "Lib-LabWeb", "periwinkle", [("A", "globe", web_a), ("B", "browser with cards", web_b)]),
    "handbook": ("Lab handbook", "Lab-Code-Guide", "gold", [("A", "open book", book_a), ("B", "book with code brackets", book_b)]),
    "labdocs": ("Lab-Docs", "Lab-Docs", "mint", [("A", "page + magnifier", docs)]),
    "projectmanager": ("ProjectManager / PaperManager", "Tool-ProjectManager", "azure", [("A", "folder holding a paper", project_a), ("B", "paper with an outline", project_b)]),
    "labviewer": ("LabViewer", "Tools-LabViewer", "copper", [("A", "inventory box", box_a), ("B", "checklist clipboard", clip_b)]),
    "database": ("AnimalRobots database", "database-AnimalRobots", "sea", [("A", "database cylinder", db)]),
}
# Parker 11-14: family A (slate, as E7) for all, except ClaudeTalk, fixed on a Claude-orange tile.
FAMILY = {"claudetalk": "claude", "claudedrive": "claude"}  # the Claude pair (Parker, 11-14)
# The option this session suggests where there are two (Parker picks).
SUGGEST = {"claudedrive": "A", "claudetalk": "A", "datafunnel": "A", "firmware": "A", "bending": "A",
           "signalshepherd": "A", "trackanything": "A", "maskanything": "A", "flowkit": "A", "daviskit": "A",
           "swimulator": "A", "spicekit": "A", "plotting": "B", "handbook": "A", "projectmanager": "A",
           "labviewer": "A", "labweb": "A", "auri": "B"}


def chosen(k):
    """(glyph, hue, family) of a tool's suggested option."""
    _, _, hue, opts = TOOLS[k]
    fn = next((f for l, _, f in opts if l == SUGGEST.get(k)), opts[0][2])
    return fn, hue, FAMILY.get(k, "slate")


# ---------------------------------------------------------------- rendering
def render(glyph, hue, size=256, family="slate"):
    img = QImage(size, size, QImage.Format.Format_ARGB32); img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img); paint(p, glyph, hue, size, family)
    return img


def paint(p, glyph, hue, size=256, family="slate"):
    """Draw one icon on any painter (a bitmap, or an SVG generator), drawn for `size` pixels."""
    accent = HUES[hue]
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size / S, size / S)
    k = 2.0 if size <= 16 else 1.5 if size <= 24 else 1.2 if size <= 32 else 1.0
    inset = 8 if size >= 48 else 3
    if family == "slate":
        tile, line, rim = SLATE, "#FFFFFF", QColor(255, 255, 255, 26)
    elif family == "tint":
        tile, line, rim = (mix(accent[1], "#0F172A", 0.72).name(), mix(accent[1], "#0F172A", 0.38).name()), "#FFFFFF", QColor(255, 255, 255, 26)
    elif family == "claude":  # Parker 11-14: ClaudeTalk on a Claude-orange tile, white glyph
        tile, line, rim = HUES["claude"], "#FFFFFF", QColor(255, 255, 255, 40)
        accent = ("#FFFFFF", "#FFFFFF", 115, 60)  # see-through white where the slate icons put colour
    else:  # light
        tile, line, rim = ("#FFFFFF", "#E2E8F0"), SLATE[0], QColor(0, 0, 0, 30)
    gr = QLinearGradient(0, 0, S, S); gr.setColorAt(0, QColor(tile[0])); gr.setColorAt(1, QColor(tile[1]))
    tr = QRectF(inset, inset, S - 2 * inset, S - 2 * inset)
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(gr)); p.drawRoundedRect(tr, 52, 52)
    if size >= 32:
        p.setPen(QPen(rim, 2 * S / size if size < 64 else 2)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(tr.adjusted(1, 1, -1, -1), 51, 51)
    g = G(p, accent, line, size <= 24, k)
    glyph(g)
    p.end()


# ---------------------------------------------------------------- final files
ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def png_bytes(img):
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice
    data = QByteArray(); buf = QBuffer(data); buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG"); buf.close()
    return bytes(data)


def write_ico(path, glyph, hue, family):
    """A .ico holding every size, each drawn at that size (PNG entries; Windows Vista and later)."""
    import struct
    blobs = [png_bytes(render(glyph, hue, s, family)) for s in ICO_SIZES]
    head = struct.pack("<HHH", 0, 1, len(blobs))
    offset = 6 + 16 * len(blobs)
    entries = b""
    for s, b in zip(ICO_SIZES, blobs):
        entries += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(b), offset)
        offset += len(b)
    path.write_bytes(head + entries + b"".join(blobs))


def write_svg(path, glyph, hue, family, title):
    from PySide6.QtCore import QSize
    from PySide6.QtSvg import QSvgGenerator
    gen = QSvgGenerator(); gen.setFileName(str(path)); gen.setSize(QSize(S, S))
    gen.setViewBox(QRectF(0, 0, S, S)); gen.setTitle(title); gen.setDescription("Xu Lab icon family, 2026-11-14")
    p = QPainter(gen); paint(p, glyph, hue, S, family)


def final(keys):
    """Per tool: <key>-512.png, <key>.ico (16-256, every size drawn), <key>.svg, into ./final/<key>/."""
    for k in keys:
        fn, hue, fam = chosen(k)
        out = HERE / "final" / k; out.mkdir(parents=True, exist_ok=True)
        render(fn, hue, 512, fam).save(str(out / f"{k}-512.png"))
        render(fn, hue, 256, fam).save(str(out / f"{k}-256.png"))
        write_ico(out / f"{k}.ico", fn, hue, fam)
        write_svg(out / f"{k}.svg", fn, hue, fam, TOOLS[k][0])
        print(out)


LIGHT, DARK, PAPER, INK = QColor("#F3F3F3"), QColor("#202020"), QColor("#FFFFFF"), QColor("#1F2937")
CW, CH = 284, 492


def cell(p, x, y, title, sub, glyph, hue, family="slate"):
    p.setPen(INK); p.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
    p.drawText(QRectF(x, y, CW - 8, 22), Qt.AlignmentFlag.AlignLeft, title)
    p.setPen(QColor("#6B7280")); p.setFont(QFont("Segoe UI", 10))
    p.drawText(QRectF(x, y + 22, CW - 8, 20), Qt.AlignmentFlag.AlignLeft, sub)
    y += 46
    p.fillRect(QRectF(x, y, 272, 272), LIGHT); p.drawImage(QPointF(x + 8, y + 8), render(glyph, hue, 256, family))
    y += 272
    for bg, yy in ((LIGHT, y + 4), (DARK, y + 88)):
        p.fillRect(QRectF(x, yy, 272, 80), bg)
        p.drawImage(QPointF(x + 8, yy + 8), render(glyph, hue, 64, family))
        p.drawImage(QPointF(x + 84, yy + 24), render(glyph, hue, 32, family))
        i16 = render(glyph, hue, 16, family)
        p.drawImage(QPointF(x + 128, yy + 32), i16)
        p.drawImage(QRectF(x + 160, yy + 8, 64, 64), i16.scaled(64, 64, Qt.AspectRatioMode.IgnoreAspectRatio,
                                                               Qt.TransformationMode.FastTransformation))
        p.setPen(QColor("#9CA3AF")); p.setFont(QFont("Segoe UI", 8))
        p.drawText(QRectF(x + 228, yy + 30, 44, 20), Qt.AlignmentFlag.AlignLeft, "16 ×4")


def sheet(name, heading, cells, cols=5, family_of=None):
    rows = math.ceil(len(cells) / cols)
    W, H = 24 + cols * CW, 70 + rows * CH + 10
    img = QImage(W, H, QImage.Format.Format_ARGB32); img.fill(PAPER)
    p = QPainter(img); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
    p.setPen(INK); p.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
    p.drawText(QRectF(24, 14, W - 40, 32), Qt.AlignmentFlag.AlignLeft, heading)
    p.setPen(QColor("#6B7280")); p.setFont(QFont("Segoe UI", 10))
    p.drawText(QRectF(24, 44, W - 40, 20), Qt.AlignmentFlag.AlignLeft,
               "Each: 256 px; then 64 / 32 / 16 px and 16 px enlarged ×4, on a light and a dark taskbar. Round 2 (refined), 2026-11-14.")
    for i, c in enumerate(cells):
        cell(p, 24 + (i % cols) * CW, 70 + (i // cols) * CH, *c)
    p.end()
    out = HERE / "round2" / f"{name}.png"; out.parent.mkdir(exist_ok=True); img.save(str(out)); print(out)
    return out


def tool_cells(keys):
    out = []
    for k in keys:
        name, repo, hue, opts = TOOLS[k]
        for letter, idea, fn in opts:
            label = f"{name}  {letter}" if len(opts) > 1 or letter == "E7" else name
            if len(opts) > 1 and SUGGEST.get(k) == letter:
                label += "  (suggested)"
            fam = FAMILY.get(k, "slate")
            out.append((label, f"{idea} · {'Claude-orange tile' if fam == 'claude' else hue}", fn, hue, fam))
    return out


def claude_pair_sheet():
    """ClaudeTalk's orange tile is fixed (Parker, 11-14); ClaudeDrive on the same tile, or on slate."""
    cells = [("ClaudeTalk A (orange, fixed)", "microphone", talk_a, "claude", "claude"),
             ("ClaudeDrive A1: orange pair", "cloud + upload, matches ClaudeTalk", drive_a, "claude", "claude"),
             ("ClaudeDrive B1: orange pair", "tray list, matches ClaudeTalk", drive_b, "claude", "claude"),
             ("ClaudeTalk B (orange, fixed)", "speech bubble, voice bars", talk_b, "claude", "claude"),
             ("ClaudeDrive A2: slate family", "cloud + upload, like the other tools", drive_a, "claude", "slate"),
             ("ClaudeDrive B2: slate family", "tray list, like the other tools", drive_b, "claude", "slate")]
    return sheet("1b-claude-pair", "1b · Claude pair: ClaudeDrive on orange or slate?",
                 cells, cols=3)


GROUPS = [
    ("1-hub-claude-acquisition", "1 · Hub, Claude tools, acquisition",
     ["labcommand", "claudedrive", "claudetalk", "datafunnel", "firmware", "experimentmanager", "bending"]),
    ("2-analysis", "2 · Analysis",
     ["signalshepherd", "trackanything", "maskanything", "flowkit", "daviskit", "swimulator", "spicekit"]),
    ("3-figures-talks", "3 · Figures and talks", ["figurekit", "slidekit", "tablekit", "diagramkit", "pitchpal", "plotting"]),
    ("4-records-infrastructure", "4 · Records, infrastructure, Auri",
     ["handbook", "labdocs", "projectmanager", "labviewer", "database", "qtshell", "labweb", "auri"]),
]


def family_sheet():
    pick = ["signalshepherd", "maskanything", "figurekit", "claudetalk"]
    cells = []
    for fam, letter, what in (("slate", "A", "slate tile (E7), colour in the glyph"),
                              ("tint", "B", "tile tinted by the tool's colour"),
                              ("light", "C", "light tile, slate lines")):
        for k in pick:
            name, _, hue, opts = TOOLS[k]
            cells.append((f"Family {letter}: {name}", what, opts[0][2], hue, fam))
    return sheet("0-family", "0 · Family look: A slate (as E7), B tinted, C light", cells, cols=4)


def strip():
    """Every tool's first option at 32 px in a taskbar row, light and dark: does the family hold?"""
    keys = list(TOOLS)
    W, H = 40 + len(keys) * 44, 200
    img = QImage(W, H, QImage.Format.Format_ARGB32); img.fill(PAPER)
    p = QPainter(img)
    p.setPen(INK); p.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
    p.drawText(QRectF(20, 8, W, 26), Qt.AlignmentFlag.AlignLeft, "Taskbar test: every tool's suggested option at 32 px and 16 px")
    for row, bg in enumerate((LIGHT, DARK)):
        y = 44 + row * 76
        p.fillRect(QRectF(0, y, W, 70), bg)
        for i, k in enumerate(keys):
            fn, hue, fam = chosen(k)
            p.drawImage(QPointF(20 + i * 44, y + 6), render(fn, hue, 32, fam))
            p.drawImage(QPointF(28 + i * 44, y + 46), render(fn, hue, 16, fam))
    p.end()
    out = HERE / "round2" / "5-taskbar-strip.png"; img.save(str(out)); print(out)


if __name__ == "__main__":
    if sys.argv[1:2] == ["sheets"]:
        claude_pair_sheet()
        for name, heading, keys in GROUPS:
            sheet(name, heading, tool_cells(keys))
        strip()
    else:  # python draw_icons.py [tool ...]: the final files, for every tool or the ones named
        final(sys.argv[1:] or list(TOOLS))
