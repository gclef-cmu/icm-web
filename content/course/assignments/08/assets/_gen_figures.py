"""Generate the pipeline-roadmap figures for the Assignment 8 direction pages.

Run `python3 _gen_figures.py` from this directory. It writes
analog-resurrection-pipeline.png, bending-time-pipeline.png, and
wsola-pipeline.png next to itself; all PNGs are committed. Every curve
here is a hand-shaped sketch for illustration only: no graded function from
the starter notebooks (bilinear_transform, wsola_time_scale, ...) is
implemented.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import to_rgba
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Wedge

HERE = Path(__file__).resolve().parent

plt.rcParams.update({
    "font.size": 14, "axes.labelsize": 16, "xtick.labelsize": 13,
    "ytick.labelsize": 13, "axes.spines.top": False, "axes.spines.right": False,
    "lines.linewidth": 2.0,
    # real LaTeX: sans body text (helvet), Computer Modern math
    "text.usetex": True,
    "text.latex.preamble": "\n".join([
        r"\usepackage{amsmath}",
        r"\usepackage{amssymb}",
        r"\usepackage[T1]{fontenc}",
        r"\usepackage{helvet}",
        r"\renewcommand{\familydefault}{\sfdefault}",
    ]),
})

RED = "#C41230"
BLUE = "#007BC0"
GOLD = "#FDB515"
TEAL = "#008F91"
IRON = "#6D6E71"
STEEL = "#E0E0E0"
INK = "#3B3B3B"
GOLDENROD = "darkgoldenrod"   # the notebooks draw every analog curve in this
TAB_BLUE = "tab:blue"         # and every digital curve in this


def canvas(w, h):
    """Full-bleed axes where one data unit is one inch."""
    fig = plt.figure(figsize=(w, h))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.set_aspect("equal")
    ax.axis("off")
    return fig, ax


def inset(fig, x, y, w, h):
    """Real plotting axes placed in canvas inches."""
    W, H = fig.get_size_inches()
    ax = fig.add_axes([x / W, y / H, w / W, h / H])
    ax.axis("off")
    return ax


def card(ax, cx, cy, w, h, fc="0.98", ec="0.3", lw=1.6, zorder=3):
    ax.add_patch(FancyBboxPatch((cx - w / 2, cy - h / 2), w, h,
                                boxstyle="round,pad=0.02", facecolor=fc,
                                edgecolor=ec, lw=lw, zorder=zorder))


def deck(ax, cx, cy, w, h, ec="0.3"):
    """A card with two ghost copies behind it: one thing per band, four bands."""
    for i, off in enumerate((0.16, 0.08)):
        card(ax, cx + off, cy + off, w, h, fc="0.95", ec="0.75", lw=1.2,
             zorder=2 + i * 0.1)
    card(ax, cx, cy, w, h)


def arrow(ax, p0, p1, color="0.3", lw=1.6, ms=14):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=ms,
                                 color=color, lw=lw, shrinkA=0, shrinkB=0,
                                 zorder=4))


def tex(s):
    """Escape the LaTeX specials that appear in our labels."""
    return s.replace("_", r"\_").replace("%", r"\%")


def task_arrow(ax, p0, p1, num, fn, sub=None, dy=0.30):
    """A red roadmap arrow: Task number above, function name below."""
    arrow(ax, p0, p1, color=RED, lw=2.2)
    mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
    ax.text(mx, my + dy, r"\textbf{Task " + str(num) + "}", ha="center", va="center",
            fontsize=11, fontweight="bold", color=RED)
    ax.text(mx, my - dy, tex(fn), ha="center", va="center", fontsize=10,
            family="monospace", color=INK)
    if sub:
        ax.text(mx, my - dy - 0.24, sub, ha="center", va="center",
                fontsize=8.8, color=IRON)


def band(ax, x0, x1, y0, y1, color, alpha):
    ax.add_patch(FancyBboxPatch((x0, y0), x1 - x0, y1 - y0,
                                boxstyle="round,pad=0.02", facecolor=color,
                                alpha=alpha, edgecolor="none", zorder=0))


def dial(ax, cx, cy, r, phi, hand=TEAL, ghost=None, wedge=False):
    """A clock face for one bin's phase; angles in radians from 12 o'clock."""
    ax.add_patch(Circle((cx, cy), r, facecolor="white", edgecolor=INK,
                        lw=1.6, zorder=3))
    for k in range(12):
        a = k * np.pi / 6
        ax.plot([cx + 0.86 * r * np.sin(a), cx + 0.95 * r * np.sin(a)],
                [cy + 0.86 * r * np.cos(a), cy + 0.95 * r * np.cos(a)],
                color="0.75", lw=1.0, zorder=4)
    if ghost is not None:
        if wedge:
            deg = 90 - np.degrees(max(phi, ghost))
            span = np.degrees(abs(phi - ghost))
            ax.add_patch(Wedge((cx, cy), 0.7 * r, deg, deg + span,
                               facecolor=GOLD, alpha=0.55, zorder=4))
        ax.plot([cx, cx + 0.8 * r * np.sin(ghost)],
                [cy, cy + 0.8 * r * np.cos(ghost)],
                color=IRON, lw=1.8, ls=(0, (3, 2)), zorder=5)
    ax.plot([cx, cx + 0.8 * r * np.sin(phi)],
            [cy, cy + 0.8 * r * np.cos(phi)], color=hand, lw=2.4,
            solid_capstyle="round", zorder=6)
    ax.add_patch(Circle((cx, cy), 0.05 * r + 0.015, color=INK, zorder=7))


def hann(x):
    """The textbook window shape, for drawing bells only."""
    return 0.5 - 0.5 * np.cos(2 * np.pi * np.clip(x, 0, 1))


def sketch_wave(t):
    """A hand-mixed squiggle that stands in for any input sound."""
    return (0.52 * np.sin(2 * np.pi * 4.0 * t) +
            0.30 * np.sin(2 * np.pi * 9.5 * t + 1.2) +
            0.16 * np.sin(2 * np.pi * 2.2 * t + 0.4))


def frame_glyph(ax, x, y, w, h, hot, edge="0.45", hot_val=0.85):
    """One STFT frame: a rounded cell with a hand-painted magnitude column."""
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.015",
                                facecolor=STEEL, edgecolor=edge, lw=1.2,
                                zorder=3))
    n = 7
    ch = 0.72 * h / n
    for i in range(n):
        v = 0.10
        if i == hot:
            v = hot_val
        elif abs(i - hot) == 1:
            v = 0.45
        ax.add_patch(FancyBboxPatch((x + 0.2 * w, y + 0.14 * h + i * ch * 1.06),
                                    0.6 * w, ch, boxstyle="round,pad=0.004",
                                    facecolor=plt.cm.magma(v), edgecolor="none",
                                    zorder=5))


def save(fig, name):
    fig.savefig(HERE / name, dpi=150,
                metadata={"Software": "icm-f26 assignments/08 _gen_figures.py"})
    plt.close(fig)
    print(f"  wrote {name}")


# ---------------------------------------------------------------------------
# Figure A: the analog-to-digital EQ compiler (Direction 3)
# ---------------------------------------------------------------------------


def fig_analog_pipeline():
    fig, ax = canvas(9.0, 8.45)

    # two worlds, one bridge
    band(ax, 0.15, 8.85, 5.55, 8.15, GOLDENROD, 0.08)
    band(ax, 0.15, 8.85, 1.45, 3.65, BLUE, 0.07)
    ax.text(0.45, 7.88, r"\textbf{CONTINUOUS TIME}", fontsize=11, fontweight="bold",
            color=GOLDENROD, va="center")
    ax.text(0.45, 7.62, r"\textit{the analog circuit}", fontsize=9, color=IRON,
            style="italic", va="center")
    ax.text(8.55, 3.46, r"\textbf{DISCRETE TIME}", fontsize=11, fontweight="bold",
            color=BLUE, va="center", ha="right")
    ax.text(7.15, 3.46, r"\textit{sampled audio: 44,100 samples per second}", fontsize=9,
            color=IRON, style="italic", va="center", ha="right")

    # the target EQ: four bands, four knobs
    card(ax, 1.95, 6.5, 2.9, 1.7)
    ax.text(1.95, 7.05, r"\textbf{The target EQ}", fontsize=11,
            fontweight="bold", color=INK, ha="center", va="center")
    for i, kx in enumerate((1.05, 1.65, 2.25, 2.85)):
        a = np.radians((-55, -15, 30, 60)[i])
        ax.add_patch(Circle((kx, 6.55), 0.19, facecolor="white",
                            edgecolor=INK, lw=1.6, zorder=4))
        ax.plot([kx, kx + 0.15 * np.sin(a)], [6.55, 6.55 + 0.15 * np.cos(a)],
                color=RED, lw=2.0, zorder=5)
    ax.text(1.95, 6.10, "Rumble filter 50 Hz,  Low shelf 110 Hz", fontsize=9,
            color=IRON, ha="center", va="center")
    ax.text(1.95, 5.88, "Presence 3.2 kHz,  Air 12 kHz", fontsize=9,
            color=IRON, ha="center", va="center")

    # the prototypes are provided, so this arrow is gray, not a red task
    arrow(ax, (3.5, 6.5), (5.0, 6.5), color=IRON, lw=2.0)
    ax.text(4.25, 6.80, r"\textit{provided}", fontsize=10, style="italic", color=IRON,
            ha="center", va="center")
    ax.text(4.25, 6.20, tex("analog_prototype"), fontsize=10,
            family="monospace", color=IRON, ha="center", va="center")

    # one H(s) per band
    deck(ax, 7.0, 6.55, 3.4, 1.3)
    ax.text(7.0, 6.78,
            r"$H(s)=\dfrac{s^2+(A_g/Q)\,s+1}{s^2+(1/(A_g Q))\,s+1}$",
            fontsize=10.5, color=GOLDENROD, ha="center", va="center", zorder=5)
    ax.text(7.0, 6.24, "four normalized prototypes: coefficients (B, A)",
            fontsize=9, color=IRON, ha="center", va="center", zorder=5)

    # the bilinear transform spans the two worlds
    arrow(ax, (5.9, 5.85), (5.9, 5.20), color=RED, lw=2.2)
    card(ax, 4.1, 4.62, 4.6, 1.1, fc=to_rgba(GOLD, 0.35), ec=INK, lw=1.8)
    ax.text(2.75, 4.86, r"\textbf{Task 1}", fontsize=11, fontweight="bold", color=RED,
            ha="center", va="center", zorder=5)
    ax.text(2.75, 4.40, tex("bilinear_transform"), fontsize=10,
            family="monospace", color=INK, ha="center", va="center", zorder=5)
    ax.text(4.35, 4.62, r"$s\ \leftarrow\ K\,\dfrac{1-z^{-1}}{1+z^{-1}}$",
            fontsize=12, color=INK, ha="center", va="center", zorder=5)
    ax.text(5.72, 4.80, r"$K=1/\tan(\pi f_0/f_s)$", fontsize=9.3, color=INK,
            ha="center", va="center", zorder=5)
    ax.text(5.72, 4.44, "(pre-warp)", fontsize=9.3, color=INK, ha="center",
            va="center", zorder=5)
    ax.text(7.6, 4.74, "without pre-warp, the 12 kHz", fontsize=8.8,
            color=IRON, ha="center", va="center")
    ax.text(7.6, 4.50, "Air shelf lands near 9.9 kHz", fontsize=8.8,
            color=IRON, ha="center", va="center")
    arrow(ax, (2.3, 4.05), (2.3, 3.31), color=RED, lw=2.2)

    # digital sections, cascaded into one filter
    deck(ax, 1.95, 2.45, 2.5, 1.35)
    ax.text(1.95, 2.72, r"$H_1(z)\ \dots\ H_4(z)$", fontsize=11.5,
            color=TAB_BLUE, ha="center", va="center", zorder=5)
    ax.text(1.95, 2.28, "(b, a) per section", fontsize=9.5, color=IRON,
            ha="center", va="center", zorder=5)

    task_arrow(ax, (3.42, 2.45), (4.9, 2.45), 2, "combine_cascade",
               sub="np.convolve")

    card(ax, 6.9, 2.45, 3.7, 1.2)
    ax.text(6.9, 2.76, r"\textbf{one difference equation (9th order)}", fontsize=10.5,
            fontweight="bold", color=INK, ha="center", va="center", zorder=5)
    ax.text(6.9, 2.24,
            r"$y[n]=b_0x[n]+b_1x[n-1]+\cdots-a_1y[n-1]-\cdots$",
            fontsize=9.5, color=TAB_BLUE, ha="center", va="center", zorder=5)

    # out of the last card and into running code
    arrow(ax, (6.35, 1.83), (6.35, 1.00), color=RED, lw=2.2)
    ax.text(6.55, 1.50, r"\textbf{Task 3}", fontsize=11, fontweight="bold", color=RED,
            va="center")
    ax.text(6.55, 1.26, tex("apply_filter"), fontsize=10, family="monospace",
            color=INK, va="center")
    ax.text(6.55, 1.03, "44,100 steps per second", fontsize=8.8, color=IRON,
            va="center")
    axw = inset(fig, 5.6, 0.30, 1.5, 0.5)
    t = np.linspace(0, 1, 400)
    axw.plot(t, sketch_wave(t), color=TAB_BLUE, lw=1.6)
    axw.set_ylim(-1.3, 1.3)
    ax.text(7.25, 0.55, r"$y[n]$", fontsize=11, color=TAB_BLUE, va="center")

    save(fig, "analog-resurrection-pipeline.png")


# ---------------------------------------------------------------------------
# Figure B: the phase vocoder route (Direction 2, Route B)
# ---------------------------------------------------------------------------


def row_title(ax, x, y, title, fn, dx):
    ax.text(x, y, r"\textbf{" + title + "}", fontsize=11.5, fontweight="bold", color=INK,
            va="center")
    if fn:
        ax.text(x + dx, y, tex(fn), fontsize=9.5, family="monospace",
                color=IRON, va="center")


def spine_arrow(ax, ytop, ybot, label):
    arrow(ax, (0.7, ytop), (0.7, ybot), color=RED, lw=2.2)
    ax.text(0.95, (ytop + ybot) / 2, label, fontsize=9.3, color=INK,
            va="center")


def fig_vocoder_pipeline():
    fig, ax = canvas(9.0, 10.6)
    for y0, y1 in ((8.5, 10.25), (5.85, 7.95), (3.08, 5.3), (0.95, 2.6)):
        band(ax, 0.15, 8.85, y0, y1, "0.55", 0.07)

    # row 1: the STFT
    row_title(ax, 0.45, 10.0, "Short-Time Fourier Transform",
              "(your Assignment 7 stft)", 2.85)
    axw = inset(fig, 0.5, 8.95, 3.8, 0.85)
    t = np.linspace(0, 1, 700)
    axw.plot(t, sketch_wave(t), color=IRON, lw=1.1)
    for k in range(5):
        x0 = 0.05 + 0.1 * k
        xs = np.linspace(x0, x0 + 0.4, 200)
        bell = hann((xs - x0) / 0.4)
        col, fa = (GOLD, 0.28) if k == 2 else (TEAL, 0.13)
        axw.fill_between(xs, -1.25, -1.25 + 2.5 * bell, color=col, alpha=fa,
                         lw=0)
        axw.plot(xs, -1.25 + 2.5 * bell, color=col, lw=1.2, alpha=0.75)
    axw.set_xlim(0, 1)
    axw.set_ylim(-1.35, 1.35)
    ax.text(2.4, 8.84, tex("Hann window, n_fft = 2048 (about 46 ms)"),
            fontsize=9, color=IRON, ha="center", va="center")
    ax.text(2.4, 8.64, tex("analysis hop: hop_in = hop_out ") + r"$\cdot$"
            + " speed", fontsize=9, color=IRON, ha="center", va="center")
    arrow(ax, (4.45, 9.38), (4.95, 9.38), color=RED, lw=2.2)
    for i in range(6):
        frame_glyph(ax, 5.1 + i * 0.58, 8.95, 0.45, 0.85, hot=1 + i)
    ax.text(6.75, 9.94, r"$X[k,m]$: the STFT, one spectrum per frame",
            fontsize=9.8, color=INK, ha="center", va="center")
    ax.text(6.75, 8.78, "1025 bins per frame", fontsize=9, color=IRON,
            ha="center", va="center")
    spine_arrow(ax, 8.44, 8.01,
                r"phases $\phi=\angle X[k,m]$, one per bin per frame")

    # row 2: the true phase advance
    row_title(ax, 0.45, 7.7, "The True Phase Advance", "", 0)
    dial(ax, 1.45, 6.90, 0.52, phi=0.7)
    dial(ax, 3.35, 6.90, 0.52, phi=3.4, ghost=2.8, wedge=True)
    ax.text(1.45, 6.24, "frame m", fontsize=9.3, color=INK, ha="center",
            va="center")
    ax.text(3.35, 6.24, "frame m+1", fontsize=9.3, color=INK, ha="center",
            va="center")
    ax.add_patch(FancyArrowPatch((1.95, 7.32), (2.85, 7.32),
                                 connectionstyle="arc3,rad=-0.35",
                                 arrowstyle="-|>", mutation_scale=11,
                                 color=IRON, lw=1.4))
    ax.text(2.4, 7.56, r"measured $\Delta\phi$ (wrapped)", fontsize=9,
            color=IRON, ha="center", va="center")
    ax.text(4.22, 6.90, "expected\n" + r"$\omega_k H$", fontsize=8.3,
            color=IRON, ha="center", va="center")
    ax.text(6.6, 7.25, r"$\mathrm{princarg}(\phi)=((\phi+\pi)\bmod 2\pi)-\pi$",
            fontsize=10.3, color=INK, ha="center", va="center")
    ax.text(6.6, 6.80,
            r"$\Delta\phi_{\mathrm{true}}=\mathrm{princarg}(\Delta\phi-\omega_k H)+\omega_k H$",
            fontsize=10.3, color=INK, ha="center", va="center")
    ax.text(6.6, 6.48, r"bin center $\omega_k=2\pi k/N$", fontsize=9,
            color=IRON, ha="center", va="center")
    ax.text(6.6, 6.22, tex("(H = hop_in, the analysis hop)"), fontsize=9,
            color=IRON, ha="center", va="center")
    spine_arrow(ax, 5.79, 5.36,
                r"$\Delta\phi_{\mathrm{true}}$: each bin's advance, frame to frame")

    # row 3: same frames, new hop
    row_title(ax, 0.45, 5.05, "Change the Hop", "", 0)
    ax.text(8.55, 5.05, "speed 0.5 shown", fontsize=9.5, color=IRON,
            va="center", ha="right")
    for i in range(6):
        hot = i == 3
        xt = 0.9 + i * 0.42
        xb = 0.9 + i * 0.84
        card(ax, xt, 4.62, 0.30, 0.52, fc=STEEL, ec="0.45", lw=1.2)
        ax.text(xt, 4.62, str(i), fontsize=8.5, color=IRON, ha="center",
                va="center", zorder=5)
        card(ax, xb, 3.62, 0.4, 0.52,
             fc="white" if hot else "0.94", ec=GOLD if hot else "0.6",
             lw=2.0 if hot else 1.2, zorder=4 if hot else 3)
        ax.text(xb, 3.62, str(i), fontsize=8.5, color=INK if hot else IRON,
                ha="center", va="center", zorder=5)
        ax.plot([xt, xb], [4.36, 3.90], color=GOLD if hot else IRON,
                lw=2.0 if hot else 0.9, alpha=1.0 if hot else 0.45, zorder=3)
    ax.text(3.45, 4.62, tex("analyzed every hop_in samples"), fontsize=9,
            color=IRON, va="center")
    ax.text(3.0, 3.22,
            tex("the same frames, played back every hop_out samples; "
                "magnitudes pass through unchanged"),
            fontsize=9, color=IRON, ha="center", va="center")
    card(ax, 7.45, 4.12, 2.6, 1.15, ec=TEAL, lw=1.8)
    ax.text(7.45, 4.48, r"\textbf{phases never interpolate}", fontsize=10.3,
            fontweight="bold", color=TEAL, ha="center", va="center", zorder=5)
    ax.text(7.45, 4.08,
            r"$\varphi \leftarrow \varphi + \Delta\phi_{\mathrm{true}}[:,\,m]"
            r"\cdot\mathrm{hop\_out}/\mathrm{hop\_in}$",
            fontsize=8.6, color=INK, ha="center", va="center", zorder=5)
    ax.text(7.45, 3.76, r"a running accumulator per bin, from $\phi[:,0]$",
            fontsize=8.3, color=IRON, ha="center", va="center", zorder=5)
    spine_arrow(ax, 3.09, 2.66, r"$Y[k,m]$: the time-scaled STFT")

    # row 4: the inverse STFT
    row_title(ax, 0.45, 2.36, "The Inverse STFT",
              "(your Assignment 7 istft)", 1.75)
    axs = inset(fig, 0.5, 1.30, 3.8, 0.78)
    xs = np.linspace(0, 0.9, 600)
    total = np.zeros_like(xs)
    for k in range(4):
        x0 = 0.05 + 0.2 * k
        bell = hann((xs - x0) / 0.4)
        bell[(xs < x0) | (xs > x0 + 0.4)] = 0
        total += bell
        axs.plot(xs, bell, color=TEAL, lw=1.1, alpha=0.5)
    axs.plot(xs, total, color=INK, lw=2.2)
    axs.axhline(1.0, color=IRON, lw=0.9, ls=(0, (3, 2)), alpha=0.7)
    axs.set_xlim(0, 0.9)
    axs.set_ylim(0, 1.45)
    ax.text(4.16, 2.02, r"$= 1$", fontsize=8.3, color=IRON,
            ha="center", va="center")
    ax.text(2.4, 2.18, "irfft each frame, overlap-add",
            fontsize=9.3, color=INK, ha="center", va="center")
    ax.text(2.4, 1.17, tex("at hop_out = n_fft // 2 the Hann windows sum to 1"),
            fontsize=9, color=IRON, ha="center", va="center")
    arrow(ax, (4.45, 1.70), (4.95, 1.70), color=RED, lw=2.2)
    # two spectrogram sketches: same sweep, twice the width, gentler slope
    for x0, w in ((5.05, 1.15), (6.45, 2.3)):
        axc = inset(fig, x0, 1.30, w, 0.78)
        axc.set_facecolor(plt.cm.magma(0.04))
        axc.axis("on")
        for s in axc.spines.values():
            s.set_visible(True)
            s.set_color("0.45")
        axc.set_xticks([])
        axc.set_yticks([])
        u = np.linspace(0.06, 0.94, 120)
        v = 0.10 + 0.80 * (u - 0.06) / 0.88
        for a, b, va, vb in zip(u[:-1], u[1:], v[:-1], v[1:]):
            axc.plot([a, b], [va, vb],
                     color=plt.cm.magma(0.35 + 0.55 * va), lw=3.0)
        axc.set_xlim(0, 1)
        axc.set_ylim(0, 1)
    ax.text(6.9, 2.18, "twice as long, same pitch", fontsize=9.8,
            color=INK, ha="center", va="center")
    ax.text(5.62, 1.17, "original chirp", fontsize=8.6, color=IRON,
            ha="center", va="center")
    ax.text(7.6, 1.17, "half speed, sweep intact", fontsize=8.6, color=IRON,
            ha="center", va="center")

    # footer: the whole machine in one line
    ax.text(4.5, 0.62, r"\textbf{Verification}", fontsize=10.5, fontweight="bold",
            color=RED, ha="center", va="center")
    ax.text(4.5, 0.32,
            tex("phase_vocoder(x, speed) = stft at hop_in ") + r"$\rightarrow$"
            + " fix phases " + r"$\rightarrow$" + tex(" istft at hop_out"),
            fontsize=10, family="monospace", color=INK, ha="center",
            va="center")

    save(fig, "bending-time-pipeline.png")


# ---------------------------------------------------------------------------
# Figure C: WSOLA (Direction 2, Route A)
# ---------------------------------------------------------------------------


def fig_wsola_pipeline():
    fig, ax = canvas(9.0, 4.35)

    ax.text(0.45, 4.10, r"\textbf{WSOLA time stretching}", fontsize=11.5,
            fontweight="bold", color=INK, va="center")
    ax.text(8.55, 4.10, "speed 0.5 shown", fontsize=9.5, color=IRON,
            va="center", ha="right")

    # both strips share one inches-per-second scale, so the stretch is visible:
    # the input covers 1 unit of time, the output the same material over 2.
    FRAME, HOP = 0.30, 0.15
    n = 9

    def in_x(u):
        return 0.6 + u * 3.9

    def out_x(u):
        return 0.6 + u * 3.9

    axi = inset(fig, 0.6, 2.90, 3.9, 0.9)
    t = np.linspace(0, 1, 700)
    axi.plot(t, sketch_wave(t), color=IRON, lw=1.1)
    for m in range(n):
        p = 0.08 + m * HOP * 0.5  # the read position advances at half rate
        xs = np.linspace(p, p + FRAME, 200)
        bell = hann((xs - p) / FRAME)
        col, fa = (GOLD, 0.30) if m == 2 else (TEAL, 0.10)
        axi.fill_between(xs, -1.25, -1.25 + 2.5 * bell, color=col, alpha=fa,
                         lw=0)
        axi.plot(xs, -1.25 + 2.5 * bell, color=col, lw=1.1, alpha=0.7)
    axi.set_xlim(0, 1)
    axi.set_ylim(-1.35, 1.35)
    ax.text(0.62, 3.88, "input", fontsize=9.3, color=INK, va="center")
    ax.text(8.55, 3.88,
            r"read positions $p = \mathrm{round}(m \cdot \mathrm{hop\_out} \cdot \mathrm{speed})$",
            fontsize=9.3, color=IRON, ha="right", va="center")
    # the WSOLA similarity search: the highlighted frame slides to the best splice
    ax.add_patch(FancyArrowPatch((1.85, 3.87), (2.31, 3.87), arrowstyle="<->",
                                 mutation_scale=10, color=GOLDENROD, lw=1.6,
                                 zorder=5))
    ax.text(2.45, 3.87, r"slide $\pm\,\mathrm{search}$ to the best match",
            fontsize=9.3, color=IRON, va="center")

    axo = inset(fig, 0.6, 0.60, 7.8, 0.9)
    u = np.linspace(0, 2, 1400)
    axo.plot(u, sketch_wave(u / 2), color=TAB_BLUE, lw=1.1)
    for m in range(n):
        q = 0.08 + m * HOP  # fixed output spacing
        xs = np.linspace(q, q + FRAME, 200)
        bell = hann((xs - q) / FRAME)
        col, fa = (GOLD, 0.30) if m == 2 else (TEAL, 0.10)
        axo.fill_between(xs, -1.25, -1.25 + 2.5 * bell, color=col, alpha=fa,
                         lw=0)
        axo.plot(xs, -1.25 + 2.5 * bell, color=col, lw=1.1, alpha=0.7)
    axo.set_xlim(0, 2)
    axo.set_ylim(-1.35, 1.35)
    ax.text(0.62, 1.58, "output", fontsize=9.3, color=INK, va="center")
    ax.text(4.5, 0.38,
            tex("fixed output spacing hop_out = frame // 2, "
                "so the Hann windows sum to a constant"),
            fontsize=9.3, color=IRON, ha="center", va="center")

    # one thin connector per frame; the highlighted frame gets the gold one
    for m in range(n):
        xi = in_x(0.08 + m * HOP * 0.5 + FRAME / 2)
        xo = out_x(0.08 + m * HOP + FRAME / 2)
        hot = m == 2
        arrow(ax, (xi, 2.85), (xo, 1.57), color=GOLD if hot else IRON,
              lw=2.0 if hot else 0.9, ms=11 if hot else 8)
    ax.text(6.1, 2.23, "copy frame m, apply the Hann window,", fontsize=9.3,
            color=INK, va="center")
    ax.text(6.1, 1.99, r"add at output position $m \cdot \mathrm{hop\_out}$",
            fontsize=9.3, color=INK, va="center")

    save(fig, "wsola-pipeline.png")


def main():
    print("generating assignment 8 pipeline figures")
    fig_analog_pipeline()
    fig_vocoder_pipeline()
    fig_wsola_pipeline()


if __name__ == "__main__":
    main()
