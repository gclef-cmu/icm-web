#!/usr/bin/env python3
"""Generate the Fall 2026 ICM poster from deterministic scientific figures.

Swiss-style typographic poster on an exact US Letter canvas (2550x3300 at
300 dpi).  Every figure is computed with numpy (fixed seeds, exact DFT bins,
row-stochastic Markov matrices) so the poster is fully reproducible, and each
figure is also emitted as a standalone SVG and PNG.

Text is real SVG text resolved through fontconfig by rsvg-convert, so the
PNG/PDF renders are deterministic on this machine (macOS system fonts).
"""

from __future__ import annotations

import base64
import html
import math
import subprocess
import tempfile
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "content" / "images" / "posters"
FIG_DIR = OUT_DIR / "scientific-figures"
POSTER_STEM = OUT_DIR / "introduction-to-computer-music-fall-2026-v9-swiss"

RED = "#c41230"
INK = "#1a1712"
GRAY = "#6f6a62"
FAINT = "#a49d92"
SCAFFOLD = "#c3bbae"
FIG_SCAFFOLD = "#b9b1a3"
PAPER = "#faf7f2"
WHITE = "#faf7f2"

SANS = "Helvetica Neue"
SERIF = "Charter"
MONO = "Menlo"

_LATEX_CACHE: dict[str, str] = {}


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def svg_text(
    x: float,
    y: float,
    value: str,
    *,
    size: float,
    weight: int = 400,
    fill: str = INK,
    anchor: str = "start",
    family: str = SANS,
    italic: bool = False,
    condensed: bool = False,
    spacing: float = 0,
    x_scale: float = 1.0,
) -> str:
    stretch = ' font-stretch="condensed"' if condensed else ""
    style = ' font-style="italic"' if italic else ""
    if x_scale != 1.0:
        # librsvg has no reliable textLength, so compress horizontally via a
        # group transform; the anchor point stays at the group origin.
        inner = (
            f'<text x="0" y="{y:.2f}" fill="{fill}" '
            f'font-family="{esc(family)}" font-size="{size:.2f}" '
            f'font-weight="{weight}" text-anchor="{anchor}"'
            f'{stretch}{style} letter-spacing="{spacing:.2f}">{esc(value)}</text>'
        )
        return f'<g transform="translate({x:.2f},0) scale({x_scale:.5f},1)">{inner}</g>'
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" fill="{fill}" '
        f'font-family="{esc(family)}" font-size="{size:.2f}" '
        f'font-weight="{weight}" text-anchor="{anchor}"'
        f'{stretch}{style} letter-spacing="{spacing:.2f}">{esc(value)}</text>'
    )


def line(x1, y1, x2, y2, *, stroke=INK, width=2, dash=None, opacity=1.0) -> str:
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
        f'stroke="{stroke}" stroke-width="{width:.2f}" opacity="{opacity:.3f}"'
        f' stroke-linecap="round"{dash_attr}/>'
    )


def rect(x, y, w, h, *, fill="none", stroke="none", width=1, radius=0, opacity=1.0) -> str:
    return (
        f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" '
        f'rx="{radius:.2f}" fill="{fill}" stroke="{stroke}" '
        f'stroke-width="{width:.2f}" opacity="{opacity:.3f}"/>'
    )


def circle(x, y, r, *, fill="none", stroke=INK, width=2, opacity=1.0) -> str:
    return (
        f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{r:.2f}" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="{width:.2f}" opacity="{opacity:.3f}"/>'
    )


def polyline(points, *, stroke=INK, width=2, fill="none", opacity=1.0, dash=None) -> str:
    pts = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'<polyline points="{pts}" fill="{fill}" stroke="{stroke}" '
        f'stroke-width="{width:.2f}" stroke-linejoin="round" '
        f'stroke-linecap="round" opacity="{opacity:.3f}"{dash_attr}/>'
    )


def polygon(points, *, fill=INK, stroke="none", width=0) -> str:
    pts = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    return f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>'


def arrow(x1, y1, x2, y2, *, stroke=INK, width=2, head=9, dash=None) -> str:
    parts = [line(x1, y1, x2, y2, stroke=stroke, width=width, dash=dash)]
    ang = math.atan2(y2 - y1, x2 - x1)
    p1 = (x2, y2)
    p2 = (x2 - head * math.cos(ang - math.pi / 6), y2 - head * math.sin(ang - math.pi / 6))
    p3 = (x2 - head * math.cos(ang + math.pi / 6), y2 - head * math.sin(ang + math.pi / 6))
    parts.append(polygon([p1, p2, p3], fill=stroke))
    return "".join(parts)


def path_from_xy(xs, ys, x, y, w, h, *, xmin=None, xmax=None, ymin=None, ymax=None, stroke=INK, width=2, opacity=1.0):
    xmin = float(np.min(xs) if xmin is None else xmin)
    xmax = float(np.max(xs) if xmax is None else xmax)
    ymin = float(np.min(ys) if ymin is None else ymin)
    ymax = float(np.max(ys) if ymax is None else ymax)
    px = x + (np.asarray(xs) - xmin) / (xmax - xmin) * w
    py = y + h - (np.asarray(ys) - ymin) / (ymax - ymin) * h
    return polyline(list(zip(px, py)), stroke=stroke, width=width, opacity=opacity)


def arc_text(cx, cy, r, value, start_deg, end_deg, *, size, fill=RED, weight=700, flip=False) -> str:
    """Place glyphs along a circular arc, one rotated glyph at a time."""
    glyphs = list(value)
    n = len(glyphs)
    if n == 1:
        angles = [(start_deg + end_deg) / 2]
    else:
        angles = np.linspace(start_deg, end_deg, n)
    parts = []
    for glyph, ang in zip(glyphs, angles):
        theta = math.radians(ang)
        gx = cx + r * math.sin(theta)
        gy = cy - r * math.cos(theta)
        rot = ang + (180 if flip else 0)
        parts.append(
            f'<text x="0" y="0" fill="{fill}" font-family="{esc(SANS)}" '
            f'font-size="{size:.2f}" font-weight="{weight}" text-anchor="middle" '
            f'transform="translate({gx:.2f},{gy:.2f}) rotate({rot:.2f})">{esc(glyph)}</text>'
        )
    return "".join(parts)


def latex_data_uri(expression: str) -> str:
    """Compile a math expression with LaTeX and return a self-contained SVG URI."""
    if expression in _LATEX_CACHE:
        return _LATEX_CACHE[expression]
    document = rf'''\documentclass[preview,border=1pt]{{standalone}}
\usepackage{{amsmath}}
\begin{{document}}
$\displaystyle {expression}$
\end{{document}}
'''
    with tempfile.TemporaryDirectory(prefix="icm-latex-") as tmp_name:
        tmp = Path(tmp_name)
        tex_path = tmp / "equation.tex"
        tex_path.write_text(document, encoding="utf-8")
        subprocess.run(
            ["latex", "-interaction=nonstopmode", "-halt-on-error", tex_path.name],
            cwd=tmp,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        svg_path = tmp / "equation.svg"
        subprocess.run(
            ["dvisvgm", "--no-fonts", "--exact-bbox", f"--output={svg_path.name}", "equation.dvi"],
            cwd=tmp,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        encoded = base64.b64encode(svg_path.read_bytes()).decode("ascii")
    uri = f"data:image/svg+xml;base64,{encoded}"
    _LATEX_CACHE[expression] = uri
    return uri


def latex_image(expression: str, x: float, y: float, width: float, height: float, *, align: str = "xMinYMid") -> str:
    uri = latex_data_uri(expression)
    return (
        f'<image x="{x:.2f}" y="{y:.2f}" width="{width:.2f}" height="{height:.2f}" '
        f'preserveAspectRatio="{align} meet" href="{uri}"/>'
    )


# ---------------------------------------------------------------------------
# Scientific figures.  Each returns the body of a 720x370 drawing.
# ---------------------------------------------------------------------------

FIG_W, FIG_H = 720, 370


def digital_audio_figure() -> str:
    x0, x1 = 42, 688
    yc, amp = 168, 112
    t = np.linspace(0, 1, 800)
    raw = 0.72 * np.sin(2 * np.pi * 1.5 * t + 0.35) + 0.28 * np.sin(2 * np.pi * 4.2 * t)
    scale = float(np.max(np.abs(raw)))
    analog = raw / scale
    ts = np.linspace(0, 1, 16)
    samples = (0.72 * np.sin(2 * np.pi * 1.5 * ts + 0.35) + 0.28 * np.sin(2 * np.pi * 4.2 * ts)) / scale
    levels = np.linspace(-1, 1, 8)
    q = levels[np.argmin(np.abs(samples[:, None] - levels[None, :]), axis=1)]
    px = lambda z: x0 + z * (x1 - x0)
    py = lambda z: yc - z * amp
    parts = [
        svg_text(x1, 40, "3-BIT / 8 LEVELS", size=26, fill=GRAY, anchor="end", family=MONO),
        svg_text(x0 + 4, 40, "x(t)", size=30, italic=True, family=SERIF),
    ]
    for level in levels:
        parts.append(line(x0, py(level), x1, py(level), stroke=FIG_SCAFFOLD, width=2.2, dash="3 8"))
    stair = []
    mids = (ts[:-1] + ts[1:]) / 2
    edges = np.concatenate(([0], mids, [1]))
    for i, value in enumerate(q):
        stair.extend([(px(edges[i]), py(value)), (px(edges[i + 1]), py(value))])
    parts.append(polyline(stair, stroke=RED, width=4, opacity=0.9))
    parts.append(path_from_xy(t, analog, x0, yc - amp, x1 - x0, 2 * amp, ymin=-1, ymax=1, stroke=INK, width=3.2))
    for tv, sv in zip(ts, samples):
        parts.append(line(px(tv), yc, px(tv), py(sv), stroke=FAINT, width=2))
        parts.append(circle(px(tv), py(sv), 5, fill=PAPER, stroke=INK, width=2.4))
    parts.extend([
        line(60, 340, 108, 340, stroke=INK, width=3.2),
        svg_text(122, 349, "signal", size=26, fill=GRAY),
        circle(258, 340, 5, fill=PAPER, stroke=INK, width=2.4),
        svg_text(276, 349, "16 samples", size=26, fill=GRAY),
        line(464, 340, 512, 340, stroke=RED, width=4),
        svg_text(526, 349, "quantized", size=26, fill=GRAY),
    ])
    return "".join(parts)


def synthesis_figure() -> str:
    t = np.linspace(0, 1, 400)
    amps = [1.0, 0.55, 0.30]
    shades = [INK, "#6f6a62", "#a49d92"]
    parts = []
    for i, (k, a, shade) in enumerate(zip([1, 2, 3], amps, shades)):
        y0 = 18 + i * 58
        vals = a * np.sin(2 * np.pi * k * 2 * t)
        parts.append(path_from_xy(t, vals, 40, y0, 230, 44, ymin=-1.05, ymax=1.05, stroke=shade, width=2.6))
        parts.append(latex_image(rf"{'' if k == 1 else k}f_0", 286, y0 + 10, 46, 26))
    summed = sum(a * np.sin(2 * np.pi * k * 2 * t) for k, a in zip([1, 2, 3], amps))
    parts.extend([
        arrow(352, 100, 402, 100, stroke=INK, width=2.4),
        path_from_xy(t, summed, 415, 28, 275, 152, ymin=-1.9, ymax=1.9, stroke=RED, width=3.6),
        latex_image(r"x(t)=\sum_{k=1}^{3} a_k\,\sin(2\pi k f_0 t)", 40, 196, 380, 56),
    ])
    fm = np.sin(2 * np.pi * 12 * t + 5 * np.sin(2 * np.pi * 1.5 * t))
    parts.extend([
        svg_text(40, 300, "FM", size=26, fill=GRAY, family=MONO),
        latex_image(r"y(t)=\sin\!\bigl(2\pi f_c t+I\,\sin(2\pi f_m t)\bigr)", 330, 272, 360, 32),
        path_from_xy(t, fm, 40, 314, 650, 46, ymin=-1.05, ymax=1.05, stroke=RED, width=2.6),
    ])
    return "".join(parts)


def fourier_dsp_figure() -> str:
    n = np.arange(128)
    x = np.sin(2 * np.pi * 3 * n / 128) + 0.6 * np.sin(2 * np.pi * 7 * n / 128) + 0.3 * np.sin(2 * np.pi * 11 * n / 128)
    mag = 2 * np.abs(np.fft.rfft(x)) / len(x)
    assert set(np.flatnonzero(mag > 0.1)) == {3, 7, 11}
    taps = 33
    m = np.arange(taps) - (taps - 1) / 2
    cutoff = 0.18
    h = 2 * cutoff * np.sinc(2 * cutoff * m) * np.hamming(taps)
    h /= h.sum()
    assert np.isclose(h.sum(), 1.0)
    H = np.abs(np.fft.rfft(h, 1024))
    freq_nyq = np.linspace(0, 1, len(H))
    parts = [
        latex_image(r"x[n]", 30, 18, 60, 26),
        latex_image(r"\lvert X[k]\rvert", 408, 18, 84, 26),
        path_from_xy(n, x, 30, 56, 296, 100, ymin=-2, ymax=2, stroke=INK, width=2.8),
        arrow(342, 106, 392, 106, stroke=INK, width=2.4),
        svg_text(367, 86, "DFT", size=25, fill=GRAY, anchor="middle", family=MONO),
        line(408, 156, 690, 156, stroke=FIG_SCAFFOLD, width=2.2),
    ]
    for k in range(len(mag)):
        if mag[k] > 0.02:
            xx = 408 + k / 14 * 282
            yy = 156 - mag[k] / 1.05 * 100
            parts.append(line(xx, 156, xx, yy, stroke=RED, width=6))
            parts.append(svg_text(xx, 184, str(k), size=26, anchor="middle", fill=INK, family=MONO))
    cutoff_x = 60 + 2 * cutoff * 630
    parts.extend([
        svg_text(60, 226, "33-TAP WINDOWED-SINC LOW-PASS", size=26, fill=GRAY, family=MONO),
        latex_image(r"\lvert H(f)\rvert", 606, 244, 82, 26),
        line(60, 342, 690, 342, stroke=INK, width=1.6),
        line(60, 240, 60, 342, stroke=INK, width=1.6),
        line(cutoff_x, 240, cutoff_x, 342, stroke=FIG_SCAFFOLD, width=2, dash="4 6"),
        latex_image(r"f_c", cutoff_x + 8, 244, 30, 24),
        path_from_xy(freq_nyq, H, 60, 240, 630, 102, xmin=0, xmax=1, ymin=0, ymax=1.08, stroke=RED, width=3.4),
        svg_text(60, 368, "0", size=25, anchor="middle", fill=INK, family=MONO),
        svg_text(690, 368, "NYQUIST", size=25, anchor="end", fill=INK, family=MONO),
    ])
    return "".join(parts)


def effects_figure() -> str:
    delays = [0, 1, 2, 3]
    left_gains = {0: 1.00, 1: 0.55, 2: 0.25}
    right_gains = {0: 1.00, 1: 0.20, 3: 0.35}
    tap_x = {d: 96 + d * 150 for d in delays}
    parts = [
        latex_image(r"x[n]", 24, 36, 58, 26),
        arrow(88, 48, tap_x[0] - 6, 48, stroke=INK, width=2.4),
        circle(tap_x[0], 48, 5.5, fill=INK, stroke=INK),
    ]
    for i, d in enumerate(delays[1:], start=1):
        bx = (tap_x[d - 1] + tap_x[d]) / 2
        parts.append(arrow(tap_x[d - 1] + 6, 48, bx - 44, 48, stroke=INK, width=2.4))
        parts.append(rect(bx - 44, 22, 88, 52, stroke=INK, width=1.8, radius=6, fill=PAPER))
        parts.append(latex_image(r"z^{-D}", bx - 28, 34, 56, 28))
        parts.append(line(bx + 44, 48, tap_x[d], 48, stroke=INK, width=2.4))
        parts.append(circle(tap_x[d], 48, 5.5, fill=INK, stroke=INK))
    for d in delays:
        parts.append(line(tap_x[d], 80, tap_x[d], 328, stroke=FIG_SCAFFOLD, width=2, dash="2 7"))
    lane = [("L", RED, left_gains, 130, 218), ("R", "#33618d", right_gains, 240, 328)]
    for label, color, gains, top, base in lane:
        parts.append(line(70, base, 620, base, stroke=FIG_SCAFFOLD, width=2.2))
        parts.append(svg_text(44, (top + base) / 2 + 9, label, size=30, weight=700, fill=color))
        for d in delays:
            xx = tap_x[d]
            g = gains.get(d)
            if g:
                h = (base - top - 8) * g
                parts.append(line(xx, base, xx, base - h, stroke=color, width=5))
                parts.append(circle(xx, base - h, 5.5, fill=color, stroke=color))
                parts.append(svg_text(xx + 14, base - h + 5, f"{g:.2f}", size=25, fill=INK, family=MONO))
        parts.append(latex_image(rf"h_{{{label}}}[n]", 636, base - 34, 70, 28))
    for d in delays:
        parts.append(svg_text(tap_x[d], 358, "0" if d == 0 else (f"{d}D" if d > 1 else "D"), size=25, anchor="middle", fill=INK, family=MONO))
    parts.append(svg_text(690, 358, "delay", size=25, anchor="end", fill=GRAY, family=MONO))
    return "".join(parts)


def algorithmic_figure() -> str:
    states = ["C4", "E4", "G4"]
    transition = np.array([[0.10, 0.60, 0.30], [0.30, 0.20, 0.50], [0.60, 0.30, 0.10]])
    assert np.allclose(transition.sum(axis=1), 1.0)
    rng = np.random.default_rng(322)
    seq = [0]
    for _ in range(15):
        seq.append(int(rng.choice(3, p=transition[seq[-1]])))
    parts = [
        svg_text(48, 40, "P(NEXT | CURRENT)", size=26, fill=GRAY, family=MONO),
    ]
    tx, ty, cw, ch = 110, 66, 68, 62
    for j, state in enumerate(states):
        parts.append(svg_text(tx + (j + 0.5) * cw, ty + 20, state, size=26, anchor="middle", fill=GRAY))
    for i in range(3):
        parts.append(svg_text(tx - 16, ty + 32 + (i + 1) * ch - 20, states[i], size=26, anchor="end", fill=GRAY))
        for j in range(3):
            p = transition[i, j]
            cy = ty + 30 + i * ch
            parts.append(rect(tx + j * cw, cy, cw - 4, ch - 4, fill=RED, opacity=0.06 + 0.78 * p, radius=4))
            parts.append(svg_text(tx + (j + 0.5) * cw - 2, cy + ch / 2 + 8, f".{int(round(p * 100)):02d}", size=25, anchor="middle", fill=INK, family=MONO))
    parts.append(arrow(334, 160, 364, 160, stroke=INK, width=2.4))
    # The seed-322 sequence engraved on a treble staff: C4 on its ledger line,
    # E4 on the bottom line, G4 on the second line, quarter notes in 4/4.
    sp = 12
    y_bottom = 190
    staff_x0, staff_x1 = 402, 700
    for i in range(5):
        parts.append(line(staff_x0, y_bottom - i * sp, staff_x1, y_bottom - i * sp, stroke=INK, width=2))
    parts.append(svg_text(418, 208, "\U0001D11E", size=128, fill=INK, anchor="middle", family="Apple Symbols"))
    parts.append(svg_text(454, 177, "4", size=30, weight=700, fill=INK, anchor="middle", family=SERIF))
    parts.append(svg_text(454, 201, "4", size=30, weight=700, fill=INK, anchor="middle", family=SERIF))
    note_y = {0: y_bottom + sp, 1: y_bottom, 2: y_bottom - sp}
    note_xs = [474 + (i // 4) * 58.8 + (i % 4) * 12.2 for i in range(len(seq))]
    for nx, s in zip(note_xs, seq):
        ny = note_y[s]
        if s == 0:
            parts.append(line(nx - 10, ny, nx + 10, ny, stroke=INK, width=2))
        parts.append(f'<ellipse cx="{nx:.2f}" cy="{ny:.2f}" rx="5.6" ry="4.4" fill="{RED}" transform="rotate(-20 {nx:.2f} {ny:.2f})"/>')
        parts.append(line(nx + 5, ny - 1.5, nx + 5, ny - 34, stroke=RED, width=2.4))
    for g in range(1, 4):
        bx = note_xs[4 * g - 1] + 11.1
        parts.append(line(bx, y_bottom, bx, y_bottom - 4 * sp, stroke=INK, width=1.8))
    parts.append(line(690, y_bottom, 690, y_bottom - 4 * sp, stroke=INK, width=1.8))
    parts.append(line(697, y_bottom, 697, y_bottom - 4 * sp, stroke=INK, width=4))
    parts.append(svg_text(697, 248, "16 STEPS / SEED 322", size=25, anchor="end", fill=GRAY, family=MONO))
    parts.append(svg_text(48, 332, "rows sum to 1 · each note draws the next", size=26, fill=GRAY))
    return "".join(parts)


def realtime_ai_figure() -> str:
    t = np.linspace(0, 1, 600)
    sig = 0.62 * np.sin(2 * np.pi * (3.5 * t + 4.5 * t**2)) + 0.2 * np.sin(2 * np.pi * 17 * t)
    parts = [
        path_from_xy(t, sig, 30, 34, 660, 100, ymin=-1, ymax=1, stroke=INK, width=2.4),
        svg_text(690, 24, "N=512 / HOP=256 / 50% OVERLAP", size=25, anchor="end", fill=GRAY, family=MONO),
    ]
    frame_w, hop_w = 200, 100
    for i in range(3):
        fx = 160 + i * hop_w
        u = np.linspace(0, 1, 160)
        hann = 0.5 - 0.5 * np.cos(2 * np.pi * u)
        parts.append(path_from_xy(u, hann, fx, 36, frame_w, 96, ymin=0, ymax=1.02, stroke=RED, width=2.4, opacity=0.85))
        parts.append(line(fx, 134, fx + frame_w, 134, stroke=RED, width=2.4))
    boxes = ["buffer", "|STFT|", "features", "model"]
    bw, bh, by = 126, 58, 214
    xs = [30 + i * 150 for i in range(4)]
    parts.append(svg_text(30, 200, "audio in", size=25, fill=GRAY, family=MONO))
    parts.append(svg_text(706, 200, "control", size=25, anchor="end", fill=RED, family=MONO, weight=700))
    for i, (bx, label) in enumerate(zip(xs, boxes)):
        parts.append(rect(bx, by, bw, bh, stroke=INK, width=1.8, radius=6, fill=PAPER))
        parts.append(svg_text(bx + bw / 2, by + bh / 2 + 8, label, size=23, anchor="middle", family=MONO))
        if i < 3:
            parts.append(arrow(bx + bw + 2, by + bh / 2, xs[i + 1] - 4, by + bh / 2, stroke=RED, width=2.4))
    parts.extend([
        arrow(xs[-1] + bw + 2, by + bh / 2, 706, by + bh / 2, stroke=RED, width=2.4),
        svg_text(30, 332, "one prediction per hop · 256 / 44100 s = 5.8 ms", size=26, fill=GRAY),
    ])
    return "".join(parts)


FIGURES = [
    ("01-digital-audio", digital_audio_figure),
    ("02-synthesis", synthesis_figure),
    ("03-fourier-dsp", fourier_dsp_figure),
    ("04-effects-spatialization", effects_figure),
    ("05-algorithmic-composition", algorithmic_figure),
    ("06-realtime-music-ai", realtime_ai_figure),
]

FIGURE_LABELS = {
    "01-digital-audio": "Continuous waveform sampled at 16 instants and quantized to eight levels",
    "02-synthesis": "Additive synthesis from three harmonics and a frequency-modulated sinusoid",
    "03-fourier-dsp": "A three-partial signal, its exact DFT bins, and a 33-tap windowed-sinc FIR response",
    "04-effects-spatialization": "Stereo tapped delay line impulse responses with explicit tap gains",
    "05-algorithmic-composition": "A row-stochastic Markov matrix and the seed-322 sequence engraved as quarter notes on a treble staff",
    "06-realtime-music-ai": "Overlapping Hann frames feeding an STFT feature pipeline and a model",
}


def figure_standalone(slug: str, body: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{FIG_W}" height="{FIG_H}" '
        f'viewBox="0 0 {FIG_W} {FIG_H}" role="img" aria-label="{esc(FIGURE_LABELS[slug])}">\n'
        f'<rect width="100%" height="100%" fill="{PAPER}"/>\n{body}\n</svg>\n'
    )


# ---------------------------------------------------------------------------
# Poster assembly.
# ---------------------------------------------------------------------------

W, H = 2550, 3300
M = 132


# Official PSF two-snake logo paths (from ipykernel's logo-svg.svg), used in
# single-color nominative form; native bounding box is 111 x 112 user units.
PYTHON_LOGO_PATHS = (
    "M 54.918785,9.1927421e-4 C 50.335132,0.02221727 45.957846,0.41313697 42.106285,1.0946693 30.760069,3.0991731 28.700036,7.2947714 28.700035,15.032169 v 10.21875 h 26.8125 v 3.40625 h -26.8125 -10.0625 c -7.792459,0 -14.6157588,4.683717 -16.7499998,13.59375 -2.46181998,10.212966 -2.57101508,16.586023 0,27.25 1.9059283,7.937852 6.4575432,13.593748 14.2499998,13.59375 h 9.21875 v -12.25 c 0,-8.849902 7.657144,-16.656248 16.75,-16.65625 h 26.78125 c 7.454951,0 13.406253,-6.138164 13.40625,-13.625 v -25.53125 c 0,-7.2663386 -6.12998,-12.7247771 -13.40625,-13.9374997 C 64.281548,0.32794397 59.502438,-0.02037903 54.918785,9.1927421e-4 Z m -14.5,8.21875012579 c 2.769547,0 5.03125,2.2986456 5.03125,5.1249996 -2e-6,2.816336 -2.261703,5.09375 -5.03125,5.09375 -2.779476,-1e-6 -5.03125,-2.277415 -5.03125,-5.09375 -10e-7,-2.826353 2.251774,-5.1249996 5.03125,-5.1249996 z",
    "m 85.637535,28.657169 v 11.90625 c 0,9.230755 -7.825895,16.999999 -16.75,17 h -26.78125 c -7.335833,0 -13.406249,6.278483 -13.40625,13.625 v 25.531247 c 0,7.266344 6.318588,11.540324 13.40625,13.625004 8.487331,2.49561 16.626237,2.94663 26.78125,0 6.750155,-1.95439 13.406253,-5.88761 13.40625,-13.625004 V 86.500919 h -26.78125 v -3.40625 h 26.78125 13.406254 c 7.792461,0 10.696251,-5.435408 13.406241,-13.59375 2.79933,-8.398886 2.68022,-16.475776 0,-27.25 -1.92578,-7.757441 -5.60387,-13.59375 -13.406241,-13.59375 z m -15.0625,64.65625 c 2.779478,3e-6 5.03125,2.277417 5.03125,5.093747 -2e-6,2.826354 -2.251775,5.125004 -5.03125,5.125004 -2.76955,0 -5.03125,-2.29865 -5.03125,-5.125004 2e-6,-2.81633 2.261697,-5.093747 5.03125,-5.093747 z",
)


PYTHON_BLUE = "#306998"
PYTHON_YELLOW = "#ffd43b"


def python_logo(cx: float, cy: float, height: float, colors: tuple[str, str] = (PYTHON_BLUE, PYTHON_YELLOW)) -> str:
    s = height / 112
    parts = [f'<g transform="translate({cx - 55.5 * s:.2f},{cy - 56 * s:.2f}) scale({s:.5f})">']
    for d, fill in zip(PYTHON_LOGO_PATHS, colors):
        parts.append(f'<path fill="{fill}" d="{d}"/>')
    parts.append("</g>")
    return "".join(parts)


def stamp(cx: float, cy: float, scale: float = 1.0) -> str:
    parts = [
        f'<g transform="rotate(-10 {cx} {cy}) translate({cx:.2f},{cy:.2f}) scale({scale:.4f}) translate({-cx:.2f},{-cy:.2f})">',
        circle(cx, cy, 205, stroke=RED, width=7),
        circle(cx, cy, 176, stroke=RED, width=2.5),
        arc_text(cx, cy, 138, "NOW FULLY IN", -62, 62, size=44),
        svg_text(cx, cy + 26, "PYTHON", size=86, weight=900, fill=RED, anchor="middle", condensed=True, spacing=2),
        arc_text(cx, cy, 148, "FALL 2026", 234, 126, size=40, flip=True),
        "</g>",
    ]
    return "".join(parts)


def fourier_band(y_top: float, y_bottom: float) -> str:
    """Fourier series convergence: ridge N is the N-term partial sum of a
    square wave, morphing from a pure sine (back) to the square (front, red)."""
    n_sums, cycles, scale, step = 15, 2, 55, 15
    u = np.linspace(0, 1, 900)
    xs = M + u * (W - 2 * M)
    term = lambda n: (4 / np.pi) * np.sin(2 * np.pi * cycles * (2 * n - 1) * u) / (2 * n - 1)
    parts = [
        latex_image(r"x_N(t)=\frac{4}{\pi}\sum_{n=1}^{N}\frac{\sin\bigl(2\pi(2n-1)f_0 t\bigr)}{2n-1}", M, y_top + 2, 620, 52),
        svg_text(W - M, y_top + 8, "SQUARE WAVE PARTIAL SUMS · N = 1 TO 15", size=26, fill=GRAY, anchor="end", family=MONO),
    ]
    partial = np.zeros_like(u)
    curves = []
    for n in range(1, n_sums + 1):
        partial = partial + term(n)
        curves.append(partial.copy())
    for j, partial in enumerate(curves, start=1):
        center = y_top + 132 + (j - 1) * step
        curve = list(zip(xs, center - partial * scale))
        if j < n_sums:
            parts.append(polygon([(xs[0], center + 74), *curve, (xs[-1], center + 74)], fill=PAPER))
            parts.append(polyline(curve, stroke=INK, width=2))
        else:
            parts.append(polygon([(xs[0], y_bottom), *curve, (xs[-1], y_bottom)], fill=PAPER))
            parts.append(polyline(curve, stroke=RED, width=3))
    return "".join(parts)


def poster_svg(figure_bodies: dict[str, str], tabloid: bool = False) -> str:
    # Tabloid keeps the letter coordinate width; 11x17 aspect gives 2550 x 3941.
    page_h = 3941 if tabloid else H
    page_size = ("11in", "17in") if tabloid else ("8.5in", "11in")
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{page_size[0]}" height="{page_size[1]}" viewBox="0 0 {W} {page_h}" '
        f'role="img" aria-label="Fall 2026 Introduction to Computer Music course poster">',
        rect(0, 0, W, page_h, fill=PAPER),
    ]
    # Masthead.
    parts.extend([
        svg_text(M, 148, "CARNEGIE MELLON UNIVERSITY · SCHOOL OF COMPUTER SCIENCE", size=34, weight=600, fill=GRAY, spacing=6),
        line(M, 184, W - M, 184, width=3),
    ])
    # Course number row, restored to display scale.
    parts.extend([
        svg_text(M - 4, 322, "15-322 / 15-622", size=136, weight=900, fill=RED, condensed=True, spacing=2),
        line(1180, 232, 1180, 322, stroke=GRAY, width=3),
        svg_text(1236, 322, "FALL 2026", size=136, weight=900, condensed=True, spacing=2),
    ])
    # Hero, justified to the text column (sizes, tracking, and horizontal
    # compression measured empirically from rendered ink extents).
    parts.extend([
        svg_text(M - 10, 598, "INTRODUCTION TO", size=319, weight=900, condensed=True, spacing=0),
        svg_text(M - 9, 938, "COMPUTER MUSIC", size=395, weight=900, fill=RED, condensed=True, spacing=0, x_scale=0.7884),
    ])
    # Tagline, description, stamp.
    parts.extend([
        rect(M, 996, 140, 14, fill=RED),
        svg_text(M, 1106, "Turn code into sound.", size=88, italic=True, family=SERIF),
        svg_text(M, 1200, "Sampling, synthesis, Fourier analysis, effects, and generative music,", size=45, fill=GRAY),
        svg_text(M, 1262, "from first principles to real-time systems.", size=45, fill=GRAY),
        python_logo(1740, 1163, 250),
        stamp(2160, 1156, 0.885),
    ])
    # On tabloid, the extra page height opens with a full-width Fourier-series
    # band between the hero and the logistics strip; later sections shift down.
    dy = 512 if tabloid else 0
    if tabloid:
        parts.append(fourier_band(1395, 1825))
    # Logistics strip.  Vertical dividers share the card-gutter axis of the grid
    # below; icon + text groups are centered from probe-measured text widths.
    gap = 48
    card_w = (W - 2 * M - 2 * gap) / 3
    divider_xs = [M + card_w + gap / 2, M + 2 * card_w + 1.5 * gap]
    edges = [M, *divider_xs, W - M]
    centers = [(edges[i] + edges[i + 1]) / 2 for i in range(3)]
    parts.append(line(M, 1368 + dy, W - M, 1368 + dy, width=3))
    parts.append(line(M, 1600 + dy, W - M, 1600 + dy, width=3))
    for dx in divider_xs:
        parts.append(line(dx, 1398 + dy, dx, 1570 + dy, stroke=SCAFFOLD, width=2.4))
    icy = 1490 + dy
    # Calendar icon + days/time.
    cal_x = 245
    parts.extend([
        rect(cal_x - 40, icy - 32, 80, 70, stroke=RED, width=6.5, radius=8),
        line(cal_x - 20, icy - 44, cal_x - 20, icy - 20, stroke=RED, width=6.5),
        line(cal_x + 20, icy - 44, cal_x + 20, icy - 20, stroke=RED, width=6.5),
        line(cal_x - 40, icy - 8, cal_x + 40, icy - 8, stroke=RED, width=5),
        rect(cal_x - 22, icy + 4, 11, 11, fill=RED), rect(cal_x - 5, icy + 4, 11, 11, fill=RED), rect(cal_x + 12, icy + 4, 11, 11, fill=RED),
        rect(cal_x - 22, icy + 20, 11, 11, fill=RED), rect(cal_x - 5, icy + 20, 11, 11, fill=RED),
        svg_text(565, 1474 + dy, "TUE + THU", size=52, weight=700, anchor="middle"),
        svg_text(565, 1538 + dy, "11:00 AM – 12:20 PM", size=52, weight=700, anchor="middle"),
    ])
    # Map-pin icon + room.
    pin_x = 1139
    parts.extend([
        f'<path d="M {pin_x} {icy + 40} C {pin_x - 12} {icy + 22}, {pin_x - 32} {icy + 8}, {pin_x - 32} {icy - 10} '
        f'A 32 32 0 1 1 {pin_x + 32} {icy - 10} C {pin_x + 32} {icy + 8}, {pin_x + 12} {icy + 22}, {pin_x} {icy + 40} Z" '
        f'fill="none" stroke="{RED}" stroke-width="6.5" stroke-linejoin="round"/>',
        circle(pin_x, icy - 10, 10, fill=RED, stroke=RED),
        svg_text(1331, 1512 + dy, "CIC 1203", size=58, weight=700, anchor="middle"),
    ])
    # Waveform icon + units.
    wav_x = 1810
    parts.extend([
        polyline([(wav_x - 42, icy), (wav_x - 26, icy), (wav_x - 16, icy - 28), (wav_x - 2, icy + 32),
                  (wav_x + 10, icy - 20), (wav_x + 20, icy), (wav_x + 42, icy)], stroke=RED, width=6.5),
        svg_text(2097, 1474 + dy, "9 UNITS · 15-322", size=52, weight=700, anchor="middle"),
        svg_text(2097, 1538 + dy, "12 UNITS · 15-622", size=52, weight=700, anchor="middle"),
    ])
    # Section header.
    dyh = 522 if tabloid else 0
    parts.extend([
        line(M, 1688 + dyh, W / 2 - 470, 1688 + dyh, stroke=RED, width=4),
        line(W / 2 + 470, 1688 + dyh, W - M, 1688 + dyh, stroke=RED, width=4),
        svg_text(W / 2, 1712 + dyh, "WHAT YOU’LL LEARN", size=76, weight=900, fill=RED, anchor="middle", condensed=True, spacing=8),
    ])
    # Topic grid.
    cards = [
        ("01", "DIGITAL AUDIO", "SAMPLING · QUANTIZATION · ALIASING"),
        ("02", "SYNTHESIS", "ADDITIVE · FM · PHYSICAL MODELING"),
        ("03", "FOURIER & DSP", "DFT / FFT · FILTERS · CONVOLUTION · STFT"),
        ("04", "EFFECTS & SPATIALIZATION", "DELAY LINES · MODULATION · PHASE VOCODING"),
        ("05", "ALGORITHMIC COMPOSITION", "MARKOV CHAINS · LPC · MIDI"),
        ("06", "REAL-TIME & MUSIC AI", "STREAMING · MIR · GENERATIVE MODELS"),
    ]
    grid_y = 2286 if tabloid else 1764
    fig_scale = card_w / FIG_W
    card_h = 168 + FIG_H * fig_scale
    row_gap = 96 if tabloid else 48
    for index, ((num, title, keywords), (slug, _)) in enumerate(zip(cards, FIGURES)):
        row, col = divmod(index, 3)
        x = M + col * (card_w + gap)
        y = grid_y + row * (card_h + row_gap)
        if col > 0:
            parts.append(line(x - gap / 2, y + 8, x - gap / 2, y + card_h - 8, stroke=SCAFFOLD, width=2.2))
        parts.extend([
            svg_text(x, y + 38, num, size=34, weight=700, fill=RED, family=MONO),
            svg_text(x, y + 106, title, size=62, weight=900, condensed=True, spacing=0),
            svg_text(x, y + 150, keywords, size=29, weight=600, fill=GRAY, spacing=1),
            f'<g transform="translate({x:.2f},{y + 168:.2f}) scale({fig_scale:.5f})">',
            figure_bodies[slug],
            "</g>",
        ])
    # Facts strip.
    facts_y = grid_y + 2 * card_h + row_gap + (56 if tabloid else 46)
    parts.append(line(M, facts_y, W - M, facts_y, width=3))
    # Icon + text positions solved from measured text widths per column.
    facts_items = [
        ("compass", "OPEN-ENDED PROJECTS", "EXPLORE YOUR OWN INTERESTS", 201, 562),
        ("code", "PREREQUISITE", "15-122 OR 15-112", 1101, 1339),
        ("clef", "MUSIC EXPERIENCE", "NOT REQUIRED", 1848, 2085),
    ]
    for dx in divider_xs:
        parts.append(line(dx, facts_y + 26, dx, facts_y + 148, stroke=SCAFFOLD, width=2.4))
    for kind, a, b, icx, tcx in facts_items:
        icy = facts_y + 90
        if kind == "compass":
            parts.append(circle(icx, icy, 36, stroke=RED, width=6.5))
            parts.append(f'<g transform="rotate(35 {icx} {icy})">')
            parts.append(polygon([(icx, icy - 26), (icx - 10, icy), (icx + 10, icy)], fill=RED))
            parts.append(polygon([(icx, icy + 26), (icx - 10, icy), (icx + 10, icy)], fill=PAPER, stroke=RED, width=4))
            parts.append("</g>")
        elif kind == "code":
            parts.append(rect(icx - 46, icy - 40, 92, 80, stroke=RED, width=6.5, radius=9))
            parts.append(svg_text(icx, icy + 13, "</>", size=38, weight=700, fill=RED, anchor="middle", family=MONO))
        else:
            parts.append(svg_text(icx, icy + 44, "\U0001D11E", size=180, fill=RED, anchor="middle", family="Apple Symbols"))
        parts.append(svg_text(tcx, facts_y + 70, a, size=36, weight=700, anchor="middle"))
        parts.append(svg_text(tcx, facts_y + 128, b, size=36, weight=700, anchor="middle"))
    # Footer.  Text baselines keep well clear of the trim edge for office printers.
    footer_y = 3712 if tabloid else 3110
    base_a, base_b = (130, 134) if tabloid else (108, 112)
    parts.extend([
        rect(0, footer_y, W, page_h - footer_y, fill=RED),
        svg_text(M, footer_y + base_a, "INSTRUCTOR · CHRIS DONAHUE", size=52, weight=700, fill=WHITE, spacing=2),
        svg_text(W - M, footer_y + base_b, "CARNEGIE MELLON UNIVERSITY", size=72, weight=900, fill=WHITE, anchor="end", condensed=True, spacing=3),
    ])
    parts.append("</svg>")
    return "\n".join(parts)


def render_svg(svg_path: Path, png_path: Path, width: int) -> None:
    subprocess.run(
        ["rsvg-convert", "-w", str(width), str(svg_path), "-o", str(png_path)],
        check=True,
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    figure_bodies: dict[str, str] = {}
    for slug, builder in FIGURES:
        body = builder()
        figure_bodies[slug] = body
        svg_path = FIG_DIR / f"{slug}.svg"
        png_path = FIG_DIR / f"{slug}.png"
        svg_path.write_text(figure_standalone(slug, body), encoding="utf-8")
        render_svg(svg_path, png_path, 1440)

    poster_svg_path = POSTER_STEM.with_suffix(".svg")
    poster_png_path = POSTER_STEM.with_suffix(".png")
    poster_pdf_path = POSTER_STEM.with_suffix(".pdf")
    svg = poster_svg(figure_bodies)
    poster_svg_path.write_text(svg, encoding="utf-8")
    render_svg(poster_svg_path, poster_png_path, W)
    subprocess.run(["rsvg-convert", "-f", "pdf", str(poster_svg_path), "-o", str(poster_pdf_path)], check=True)

    # Print variant: white background so office lasers lay no tint (print on cream stock).
    print_stem = POSTER_STEM.parent / (POSTER_STEM.name + "-print")
    print_svg_path = print_stem.with_suffix(".svg")
    print_pdf_path = print_stem.with_suffix(".pdf")
    print_svg_path.write_text(svg.replace(PAPER, "#ffffff"), encoding="utf-8")
    subprocess.run(["rsvg-convert", "-f", "pdf", str(print_svg_path), "-o", str(print_pdf_path)], check=True)

    # 11x17 tabloid variant with its own layout, plus its print version.
    tab_stem = POSTER_STEM.parent / (POSTER_STEM.name + "-11x17")
    tab_svg_path = tab_stem.with_suffix(".svg")
    tab_png_path = tab_stem.with_suffix(".png")
    tab_pdf_path = tab_stem.with_suffix(".pdf")
    tab_svg = poster_svg(figure_bodies, tabloid=True)
    tab_svg_path.write_text(tab_svg, encoding="utf-8")
    render_svg(tab_svg_path, tab_png_path, 3300)
    subprocess.run(["rsvg-convert", "-f", "pdf", str(tab_svg_path), "-o", str(tab_pdf_path)], check=True)
    tab_print_stem = POSTER_STEM.parent / (POSTER_STEM.name + "-11x17-print")
    tab_print_svg = tab_print_stem.with_suffix(".svg")
    tab_print_pdf = tab_print_stem.with_suffix(".pdf")
    tab_print_svg.write_text(tab_svg.replace(PAPER, "#ffffff"), encoding="utf-8")
    subprocess.run(["rsvg-convert", "-f", "pdf", str(tab_print_svg), "-o", str(tab_print_pdf)], check=True)
    print(poster_svg_path)
    print(poster_png_path)
    print(poster_pdf_path)
    print(print_pdf_path)
    print(tab_svg_path)
    print(tab_png_path)
    print(tab_pdf_path)
    print(tab_print_pdf)


if __name__ == "__main__":
    main()
