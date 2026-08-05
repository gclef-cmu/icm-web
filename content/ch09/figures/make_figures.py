"""Generate figures and sound examples for Chapter 9 (Filters).

Outputs are written to ../assets/. This file is *not* student-facing.

Run with the project virtualenv (pyquist reached via PYTHONPATH):
    PYTHONPATH=../../../../pyquist ../../../.venv/bin/python make_figures.py
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pyquist as pq
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / "assets"
ASSETS.mkdir(exist_ok=True)

F_S = 44100
PEAK_DBFS = -6.0

plt.rcParams.update({
    "font.size": 14, "axes.labelsize": 16, "xtick.labelsize": 13,
    "ytick.labelsize": 13, "axes.spines.top": False, "axes.spines.right": False,
    "lines.linewidth": 2.0,
})
COLORS = plt.rcParams["axes.prop_cycle"].by_key()["color"]
# Chapter color convention: x (input) is blue, h (filter) is red, y (output) is purple.
BLUE, ORANGE, GREEN, RED, PURPLE = COLORS[0], COLORS[1], COLORS[2], COLORS[3], COLORS[4]


def save_fig(name: str) -> None:
    plt.tight_layout()
    plt.savefig(ASSETS / name, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  wrote {name}")


def write_audio(samples: np.ndarray, name: str, sr: int = F_S) -> None:
    audio = pq.Audio(samples.astype(np.float32), sr)
    audio.normalize(peak_dbfs=PEAK_DBFS)
    audio.write(str(ASSETS / name))
    print(f"  wrote {name}")


def stem(ax, xs, ys, color, ms=7, lw=2.0):
    ml, sl, bl = ax.stem(xs, ys)
    plt.setp(ml, color=color, markersize=ms)
    plt.setp(sl, color=color, linewidth=lw)
    plt.setp(bl, color="0.7", linewidth=1.0)


# ---------------------------------------------------------------------------
# 2. High-level goal: sculpting the frequency domain, |Y| = |H| . |X|.
# ---------------------------------------------------------------------------


def fig_lti_goal() -> None:
    fig, axes = plt.subplots(1, 3, figsize=(14, 3.6))
    f = np.linspace(0, 1, 500)
    # input line spectrum: evenly-spaced partials with decreasing amplitude
    fx = np.linspace(0.1, 0.85, 6)
    ax_amp = np.array([1.0, 0.85, 0.7, 0.55, 0.42, 0.30])
    # filter magnitude response: a smooth band emphasis peaking mid-low
    H = np.exp(-((f - 0.30) ** 2) / (2 * 0.16 ** 2))
    H = H / H.max()

    def Hval(freqs):
        return np.interp(freqs, f, H)

    stem(axes[0], fx, ax_amp, BLUE, ms=6)
    axes[0].set_title(r"Input  $|X[k]|$", fontsize=15, color=BLUE)
    axes[1].plot(f, H, color=RED)
    axes[1].fill_between(f, 0, H, color=RED, alpha=0.15)
    axes[1].set_title(r"Filter  $|H[k]|$", fontsize=15, color=RED)
    stem(axes[2], fx, ax_amp * Hval(fx), PURPLE, ms=6)
    axes[2].plot(f, H, color=RED, ls="--", lw=1.5, alpha=0.7)  # ghost of filter response
    axes[2].set_title(r"Output  $|Y[k]| = |H[k]| \cdot |X[k]|$", fontsize=15, color=PURPLE)
    for ax in axes:
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1.1)
        ax.set_xticks([0, 1])
        ax.set_xticklabels(["0", r"$f_s/2$"])
        ax.set_yticks([])
        ax.set_xlabel("Frequency")
    save_fig("fig-lti-goal.png")


# ---------------------------------------------------------------------------
# 3. Difference equation examples: low-pass y[n]=x[n]+x[n-1], high-pass ...
# ---------------------------------------------------------------------------

_SQUARE = np.array(([1.0] * 5 + [-1.0] * 5) * 4)  # 10-sample period, 40 samples


def _diffeq_panels(rows, labels, colors, warmup, fname, ylim=(-2.3, 2.3)):
    N = 32
    n = np.arange(N)
    fig, axes = plt.subplots(3, 1, figsize=(11, 5.4), sharex=True)
    for ax, data, lab, col in zip(axes, rows, labels, colors):
        if warmup > 0:
            ax.axvspan(-0.5, warmup - 0.5, color="0.85", alpha=0.7)
        stem(ax, n, data[:N], col, ms=5)
        ax.set_ylabel(lab, fontsize=15, color=col)
        ax.set_ylim(*ylim)
        ax.set_xlim(-0.5, N - 0.5)
        ax.axhline(0, color="0.8", lw=0.8)
    axes[-1].set_xlabel(r"Sample index $n$")
    save_fig(fname)


def fig_diffeq_lowpass() -> None:
    x = _SQUARE
    xd = np.concatenate([np.zeros(1), x])[:len(x)]  # x[n-1], zero before n=0
    y = x + xd
    _diffeq_panels(
        [x, xd, y],
        [r"$x[n]$", r"$x[n-1]$", r"$y[n]$"],
        [BLUE, GREEN, PURPLE],
        warmup=1,
        fname="fig-diffeq-lowpass.png",
    )


def fig_diffeq_highpass() -> None:
    x = _SQUARE
    xd = np.concatenate([np.zeros(1), x])[:len(x)]  # x[n-1]
    half_x = 0.5 * x
    neg_half_xd = -0.5 * xd
    y = half_x + neg_half_xd
    _diffeq_panels(
        [half_x, neg_half_xd, y],
        [r"$\frac{1}{2}x[n]$", r"$-\frac{1}{2}x[n-1]$", r"$y[n]$"],
        [BLUE, GREEN, PURPLE],
        warmup=1,
        fname="fig-diffeq-highpass.png",
        ylim=(-1.2, 1.2),
    )


# ---------------------------------------------------------------------------
# 4. What do these filters do to sound? spectra + audio (441 Hz square wave).
# ---------------------------------------------------------------------------


def fig_diffeq_responses() -> None:
    f0 = 441.0
    period = int(round(F_S / f0))          # ~100 samples
    dur = 1.5
    reps = int(np.ceil(dur * F_S / period))
    one = np.array([1.0] * (period // 2) + [-1.0] * (period - period // 2))
    x = np.tile(one, reps)[:int(dur * F_S)]

    def lp(sig):   # low-pass: y[n] = x[n] + x[n-1]
        return sig + np.concatenate([[0.0], sig])[:len(sig)]

    def hp(sig):   # high-pass: y[n] = 1/2 x[n] - 1/2 x[n-1]
        return 0.5 * sig - 0.5 * np.concatenate([[0.0], sig])[:len(sig)]

    # Audio, kept quiet (-20 dBFS): a harsh square wave through each filter.
    for sig, name in [(x, "audio-diffeq-input.wav"), (lp(x), "audio-diffeq-y1.wav"),
                      (hp(x), "audio-diffeq-y2.wav")]:
        audio = pq.Audio(sig.astype(np.float32), F_S)
        audio.normalize(peak_dbfs=-20.0)
        audio.write(str(ASSETS / name))
        print(f"  wrote {name}")

    # Pass white noise (a flat spectrum) through each filter and plot the
    # amplitude spectrum of the result. Since the input is flat, the output
    # spectrum traces out the filter's own frequency response. Averaging the
    # spectrum over many windows (Welch's method) smooths away the randomness.
    rng = np.random.default_rng(0)
    noise = rng.standard_normal(300 * 2048)

    def avg_spectrum(sig, nfft=2048):
        win = np.hanning(nfft)
        mags = [np.abs(np.fft.rfft(sig[i:i + nfft] * win))
                for i in range(0, len(sig) - nfft, nfft)]
        return np.mean(mags, axis=0)

    freq = np.fft.rfftfreq(2048, d=1.0)     # normalized frequency, 0 .. 0.5
    S1, S2 = avg_spectrum(lp(noise)), avg_spectrum(hp(noise))
    S1 /= S1.max()
    S2 /= S2.max()

    fig, ax = plt.subplots(figsize=(11, 4.0))
    ax.plot(freq, S1, color=BLUE, lw=2.6, label=r"$y_1 = x[n] + x[n-1]$  (low-pass)")
    ax.plot(freq, S2, color=ORANGE, lw=2.6,
            label=r"$y_2 = \frac{1}{2}x[n] - \frac{1}{2}x[n-1]$  (high-pass)")
    ax.set_xlim(0, 0.5)
    ax.set_ylim(0, 1.08)
    ax.set_xticks([0, 0.25, 0.5])
    ax.set_xticklabels(["0", r"$f_s/4$", r"$f_s/2$"], fontsize=14)
    ax.set_xlabel("Frequency")
    ax.set_ylabel("Filtered-noise amplitude")
    ax.legend(loc="upper center", fontsize=13)
    save_fig("fig-diffeq-responses.png")


# ---------------------------------------------------------------------------
# 5. Example of convolution: x=[1,1,1], h=[3,2,1], y = h*x = [3,5,6,3,1].
# ---------------------------------------------------------------------------


def fig_convolution_example() -> None:
    x = np.array([1.0, 1.0, 1.0])
    h = np.array([3.0, 2.0, 1.0])
    y = np.convolve(x, h)  # [3, 5, 6, 3, 1]
    fig, axes = plt.subplots(1, 3, figsize=(14, 3.4))
    idx = np.arange(6)
    stem(axes[0], np.arange(len(x)), x, BLUE)
    axes[0].set_title(r"$x[n] = [1,1,1]$  ($N=3$)", fontsize=14, color=BLUE)
    stem(axes[1], np.arange(len(h)), h, RED)
    axes[1].set_title(r"$h[n] = [3,2,1]$  ($K=3$)", fontsize=14, color=RED)
    stem(axes[2], np.arange(len(y)), y, PURPLE)
    axes[2].set_title(r"$y = h * x$  ($N+K-1 = 5$)", fontsize=14, color=PURPLE)
    for ax in axes:
        ax.set_xlim(-0.5, 5.5)
        ax.set_ylim(0, 6.5)
        ax.set_xticks(idx)
        ax.set_xlabel(r"$n$")
    axes[0].set_ylabel("Amplitude")
    save_fig("fig-convolution-example.png")


# ---------------------------------------------------------------------------
# 6. Recursive filters: signal flow diagrams (ordinary vs recursive).
# ---------------------------------------------------------------------------


def _adder(ax, cx, cy, r=0.18):
    ax.add_patch(Circle((cx, cy), r, facecolor="white", edgecolor="0.2", lw=1.8, zorder=3))
    ax.text(cx, cy, "+", ha="center", va="center", fontsize=20, zorder=4)


def _delay(ax, cx, cy, w=0.6, h=0.44):
    ax.add_patch(FancyBboxPatch((cx - w / 2, cy - h / 2), w, h,
                                boxstyle="round,pad=0.01", facecolor="0.92",
                                edgecolor="0.3", lw=1.6, zorder=3))
    ax.text(cx, cy, r"$z^{-1}$", ha="center", va="center", fontsize=16, zorder=4)


def _arrow(ax, p0, p1, color="0.3"):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=14,
                                 color=color, lw=1.6, shrinkA=0, shrinkB=0, zorder=2))


def _wire(ax, pts, color="0.3"):
    xs, ys = zip(*pts)
    ax.plot(xs, ys, color=color, lw=1.6, zorder=1)


def fig_recursive_signalflow() -> None:
    fig, (axo, axr) = plt.subplots(1, 2, figsize=(13, 4.6))
    LBL, EQ = 18, 16
    X0, X1 = 0.9, 4.1                        # main wire spans X0..X1
    C = (X0 + X1) / 2                        # adder, perfectly centered on the wire
    BW = (X1 - X0) / 3                       # branch width = 1/3 of the main wire
    AY, R, HW = 2.0, 0.18, 0.3
    low = AY - BW                            # drop = branch width, so the loop is square
    EQY = AY + BW + 0.35                     # equation sits above the diagram
    for ax in (axo, axr):
        ax.axis("off")
        ax.set_aspect("equal")              # round adders and a true-square loop
        ax.set_xlim(0, 5)
        ax.set_ylim(low - 0.35, EQY + 0.25)

    # --- Feedforward only: y[n] = x[n] + x[n-1] ---  (branch taps the INPUT) ---
    ax = axo
    ax.text(C, EQY, r"$y[n] = x[n] + x[n-1]$", ha="center", fontsize=EQ, color="0.3")
    ax.text(X0 - 0.45, AY, r"$x[n]$", ha="center", va="center", fontsize=LBL, color=BLUE)
    _wire(ax, [(X0, AY), (C - R - 0.12, AY)])                     # main wire into adder
    _arrow(ax, (C - R - 0.12, AY), (C - R, AY))
    split, zc = C - BW, C - BW / 2
    ax.add_patch(Circle((split, AY), 0.055, color="0.3", zorder=3))
    _wire(ax, [(split, AY), (split, low), (zc - HW, low)])        # down to delay
    _delay(ax, zc, low, h=0.34)                                  # centered in the branch
    _wire(ax, [(zc + HW, low), (C, low), (C, AY - R - 0.12)])     # up into adder
    _arrow(ax, (C, AY - R - 0.12), (C, AY - R))
    _adder(ax, C, AY, r=R)
    _wire(ax, [(C + R, AY), (X1, AY)])
    _arrow(ax, (X1 - 0.14, AY), (X1, AY))                        # arrow at wire terminus
    ax.text(X1 + 0.15, AY, r"$y[n]$", ha="left", va="center", fontsize=LBL, color=PURPLE)
    ax.set_title("Feedforward only", fontsize=16, fontweight="bold")

    # --- Feedback only: y[n] = x[n] + y[n-1] ---  (branch taps the OUTPUT) ---
    ax = axr
    ax.text(C, EQY, r"$y[n] = x[n] + y[n-1]$", ha="center", fontsize=EQ, color="0.3")
    ax.text(X0 - 0.45, AY, r"$x[n]$", ha="center", va="center", fontsize=LBL, color=BLUE)
    _wire(ax, [(X0, AY), (C - R - 0.12, AY)])
    _arrow(ax, (C - R - 0.12, AY), (C - R, AY))
    _adder(ax, C, AY, r=R)
    _wire(ax, [(C + R, AY), (X1, AY)])                            # main wire out of adder
    _arrow(ax, (X1 - 0.14, AY), (X1, AY))
    ax.text(X1 + 0.15, AY, r"$y[n]$", ha="left", va="center", fontsize=LBL, color=PURPLE)
    tap, zc = C + BW, C + BW / 2
    ax.add_patch(Circle((tap, AY), 0.055, color="0.3", zorder=3))
    _wire(ax, [(tap, AY), (tap, low), (zc + HW, low)])           # tap down to delay
    _delay(ax, zc, low, h=0.34)                                 # centered in the branch
    _wire(ax, [(zc - HW, low), (C, low), (C, AY - R - 0.12)])     # back up into adder
    _arrow(ax, (C, AY - R - 0.12), (C, AY - R))
    ax.set_title("Feedback only", fontsize=16, fontweight="bold")
    save_fig("fig-recursive-signalflow.png")


# ---------------------------------------------------------------------------
# 7. Filter types: idealized magnitude responses (low/high/band pass, notch).
# ---------------------------------------------------------------------------


def fig_filter_types() -> None:
    """Idealized 'brick-wall' responses for the four canonical filter types."""
    def brick(passband):
        f = np.linspace(0, 1, 2000)
        m = np.zeros_like(f)
        for lo, hi in passband:
            m[(f >= lo) & (f <= hi)] = 1.0
        return f, m

    fig, axes = plt.subplots(2, 2, figsize=(13, 6.8))
    # (title, passband intervals, f_C marks, labels, bandwidth interval + its label)
    specs = [
        (axes[0, 0], "Low pass",  [(0.0, 0.5)], [0.5],
         [("passband", 0.25), ("stopband", 0.75)], (0.0, 0.5), "bandwidth"),
        (axes[0, 1], "High pass", [(0.5, 1.0)], [0.5],
         [("stopband", 0.25), ("passband", 0.75)], (0.5, 1.0), "bandwidth"),
        (axes[1, 0], "Band pass", [(0.35, 0.65)], [0.5],
         [("stopband", 0.16), ("passband", 0.5), ("stopband", 0.84)], (0.35, 0.65), "bandwidth"),
        (axes[1, 1], "Band stop (notch)", [(0.0, 0.35), (0.65, 1.0)], [0.5],
         [("passband", 0.16), ("stopband", 0.5), ("passband", 0.84)], (0.35, 0.65), "bandwidth"),
    ]
    for ax, title, passband, cuts, labels, bw, bwname in specs:
        f, m = brick(passband)
        ax.plot(f, m, color=RED, lw=2.5)
        ax.fill_between(f, 0, m, color=GREEN, alpha=0.18)
        for c in cuts:
            ax.axvline(c, color="0.5", ls="--", lw=1.2)
        for name, xpos in labels:
            ax.text(xpos, 0.6, name, ha="center", va="center", fontsize=13, color="0.25")
        # bandwidth double-arrow, drawn inside the plot near the bottom
        ax.annotate("", xy=(bw[0], 0.16), xytext=(bw[1], 0.16),
                    arrowprops=dict(arrowstyle="<->", color="0.5", lw=1.2))
        ax.text((bw[0] + bw[1]) / 2, 0.24, bwname, ha="center", va="bottom",
                fontsize=12, color="0.4")
        ax.set_title(title, fontsize=17, fontweight="bold")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1.2)
        ax.set_xticks([0] + cuts + [1])          # f_C sits on the x-axis
        ax.set_xticklabels(["0"] + [r"$f_C$"] * len(cuts) + [r"$f_s/2$"], fontsize=15)
        ax.set_yticks([0, 1])
        ax.tick_params(axis="y", labelsize=14)
        ax.set_xlabel("Frequency", fontsize=16)
        ax.set_ylabel(r"$|H(f)|$", fontsize=16)
    save_fig("fig-filter-types.png")


def fig_filter_realworld() -> None:
    """Real-world anatomy: a low-pass with a transition band, and a resonant
    band-pass showing bandwidth and quality factor Q, both in decibels."""
    f = np.linspace(0, 1, 2000)

    def db(mag):
        return 20 * np.log10(np.maximum(mag, 1e-4))

    fig, (axl, axr) = plt.subplots(1, 2, figsize=(13, 4.8))
    LAB = 13

    # --- left: real low-pass that rolls off and smoothly settles into a floor ---
    order, fc = 9, 0.30
    floor = 10 ** (-72 / 20)                    # stopband floor as a linear magnitude
    lp = 1 / np.sqrt(1 + (f / fc) ** (2 * order))
    lp_db = db(np.sqrt(lp ** 2 + floor ** 2))   # smooth asymptote into the floor
    axl.plot(f, lp_db, color=RED, lw=2.6)
    for lvl in (-6, -60):
        axl.axhline(lvl, color="0.5", ls="--", lw=1.1)
        axl.text(1.01, lvl, f"{lvl} dB", va="center", fontsize=LAB, color="0.3")
    f6 = f[np.argmin(np.abs(lp_db + 6))]       # cutoff: where response hits -6 dB
    f60 = f[np.argmin(np.abs(lp_db + 60))]     # edge of stopband: -60 dB
    axl.axvspan(f6, f60, color=ORANGE, alpha=0.15)
    axl.axvline(f6, color="0.6", lw=1.0)
    axl.text(f6 / 2, -30, "passband", ha="center", fontsize=LAB, color="0.25")
    axl.text((f6 + f60) / 2, -42, "transition\nband", ha="center", fontsize=12, color="0.25")
    axl.text((f60 + 1) / 2, -30, "stopband", ha="center", fontsize=LAB, color="0.25")
    axl.set_title("Real low-pass filter", fontsize=17, fontweight="bold")
    axl.set_ylim(-78, 10)
    axl.set_xticks([0, f6, 1])                  # f_C on the x-axis
    axl.set_xticklabels(["0", r"$f_C$", r"$f_s/2$"], fontsize=15)

    # --- right: resonant band-pass, bandwidth from the two -6 dB crossings ---
    fC, Q = 0.5, 4.0
    w, w0 = 2 * np.pi * f, 2 * np.pi * fC
    bp = (w / Q) / np.sqrt((w0 ** 2 - w ** 2) ** 2 + (w * w0 / Q) ** 2) * w0
    bp_db = db(bp / bp.max())
    axr.plot(f, bp_db, color=RED, lw=2.6)
    axr.axhline(-6, color="0.5", ls="--", lw=1.1)
    axr.text(1.01, -6, "-6 dB", va="center", fontsize=LAB, color="0.3")
    below = np.where(bp_db >= -6)[0]
    fL, fH = f[below[0]], f[below[-1]]
    for fx in (fL, fC, fH):
        axr.axvline(fx, color="0.6", lw=1.0)
    axr.annotate("", xy=(fL, -14), xytext=(fH, -14),
                 arrowprops=dict(arrowstyle="<->", color="0.5", lw=1.2))
    axr.text(fC, -20, r"bandwidth $= f_H - f_L$", ha="center", fontsize=12, color="0.35")
    axr.set_title("Resonant band-pass filter", fontsize=17, fontweight="bold")
    axr.set_ylim(-48, 10)
    axr.set_xticks([0, fL, fC, fH, 1])          # f_L, f_C, f_H on the x-axis
    axr.set_xticklabels(["0", r"$f_L$", r"$f_C$", r"$f_H$", r"$f_s/2$"], fontsize=15)

    for ax in (axl, axr):
        ax.set_xlim(0, 1)
        ax.set_xlabel("Frequency", fontsize=16)
        ax.set_ylabel("Magnitude (dB)", fontsize=16)
        ax.tick_params(axis="y", labelsize=14)
    save_fig("fig-filter-realworld.png")


# ---------------------------------------------------------------------------
# 8. Empirical frequency response of a 2-tap averager y[n] = x[n] + x[n-1].
# ---------------------------------------------------------------------------


def fig_frequency_response() -> None:
    fs = 48000

    def sinusoid(freq):
        n = np.arange(fs)  # one second
        return np.cos(2 * np.pi * freq * n / fs)

    # The naive empirical amplitude estimate: the largest output sample. Because
    # the true continuous peak usually falls between samples, this slightly
    # UNDER-estimates the response at some probe frequencies (a teachable point).
    # 41 probes (step f_s/80) so that exactly f_s/4 and f_s/2 are sampled,
    # matching the hand calculations above.
    test = np.linspace(0, fs / 2, 41)
    empirical = []
    for freq in test:
        x = sinusoid(freq)
        y = x[1:] + x[:-1]              # y[n] = x[n] + x[n-1]
        empirical.append(np.max(np.abs(y)))
    empirical = np.array(empirical)

    fine = np.linspace(0, fs / 2, 500)
    analytical = 2 * np.abs(np.cos(np.pi * fine / fs))

    fig, ax = plt.subplots(figsize=(13, 4.0))
    ax.plot(fine, analytical, color=RED, lw=2.2,
            label=r"analytical  $2\,|\cos(\pi f / f_s)|$")
    stem(ax, test, empirical, BLUE)
    ax.plot([], [], color=BLUE, marker="o", lw=0, label=r"empirical  $\max|y|$")
    ax.set_xlim(0, fs / 2)
    ax.set_ylim(0, 2.2)
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Output amplitude")
    ax.legend(loc="upper right", fontsize=12)
    save_fig("fig-frequency-response.png")


# ---------------------------------------------------------------------------
# 7c. Sound examples: white noise through each of the four filter types (RBJ).
# ---------------------------------------------------------------------------


def fig_filter_type_audio() -> None:
    """Filter white noise through low/high/band-pass and notch RBJ biquads,
    kept quiet (-20 dBFS) to protect ears."""
    from scipy.signal import lfilter

    def biquad(kind, fc, Q):
        w0 = 2 * np.pi * fc / F_S
        c, al = np.cos(w0), np.sin(w0) / (2 * Q)
        b = {"lp": [(1 - c) / 2, 1 - c, (1 - c) / 2],
             "hp": [(1 + c) / 2, -(1 + c), (1 + c) / 2],
             "bp": [al, 0.0, -al],
             "notch": [1.0, -2 * c, 1.0]}[kind]
        a = [1 + al, -2 * c, 1 - al]
        return np.array(b) / a[0], np.array(a) / a[0]

    rng = np.random.default_rng(0)
    noise = rng.uniform(-1, 1, int(2.0 * F_S))
    ref = pq.Audio(noise.astype(np.float32), F_S)     # unfiltered noise for reference
    ref.normalize(peak_dbfs=-20.0)
    ref.write(str(ASSETS / "audio-filter-noise.wav"))
    print("  wrote audio-filter-noise.wav")
    specs = [("lp", 600, 0.707, "audio-filter-lowpass.wav"),
             ("hp", 3500, 0.707, "audio-filter-highpass.wav"),
             ("bp", 1200, 2.5, "audio-filter-bandpass.wav"),
             ("notch", 1200, 2.5, "audio-filter-bandstop.wav")]
    for kind, fc, Q, name in specs:
        b, a = biquad(kind, fc, Q)
        y = lfilter(b, a, lfilter(b, a, noise))    # cascade twice for a steeper slope
        audio = pq.Audio(y.astype(np.float32), F_S)
        audio.normalize(peak_dbfs=-20.0)
        audio.write(str(ASSETS / name))
        print(f"  wrote {name}")


# ---------------------------------------------------------------------------
# 8b. Manual filter analysis: three probe points suggest a low-pass shape.
# ---------------------------------------------------------------------------


def fig_manual_analysis() -> None:
    freqs = np.array([0.0, 0.25, 0.5])       # 0, f_s/4, f_s/2 (normalized)
    amps = np.array([2.0, 1.0, 0.0])
    fig, ax = plt.subplots(figsize=(8.5, 4.0))
    ax.plot(freqs, amps, ls="--", color="0.6", lw=1.5, zorder=1)
    stem(ax, freqs, amps, RED, ms=11)
    for fx, a in zip(freqs, amps):
        ax.annotate(rf"$\max|y| = {a:.0f}$", xy=(fx, a), xytext=(fx, a + 0.18),
                    ha="center", fontsize=12, color="0.25")
    ax.text(0.35, 1.35, "low pass!", fontsize=16, color=RED, style="italic", fontweight="bold")
    ax.set_xlim(-0.03, 0.55)
    ax.set_ylim(0, 2.4)
    ax.set_xticks([0, 0.25, 0.5])
    ax.set_xticklabels(["0", r"$f_s/4$", r"$f_s/2$"])
    ax.set_xlabel("Frequency")
    ax.set_ylabel("Output amplitude")
    save_fig("fig-manual-analysis.png")


# ---------------------------------------------------------------------------
# 8c. Subtractive-synthesis schematic: rich source -> filter -> shaped output.
# ---------------------------------------------------------------------------


def fig_subtractive_diagram() -> None:
    fig, axes = plt.subplots(2, 3, figsize=(13, 5.2),
                             gridspec_kw={"height_ratios": [1, 1]})
    t = np.linspace(0, 1, 500)
    pulse = np.where((t % 0.25) < 0.09, 1.0, -1.0)  # narrow pulse wave
    k = np.arange(1, 14)
    src_spec = np.abs(np.sinc(0.28 * k))            # rich, many-harmonic spectrum
    Hk = np.exp(-((k - 1) / 4.0) ** 2)              # low-pass-ish filter shape
    out_spec = src_spec * Hk

    # top row: waveforms / box
    axes[0, 0].plot(t, pulse, color=BLUE)
    axes[0, 0].set_title("Rich source (pulse)", fontsize=13, color=BLUE)
    axes[0, 0].set_ylim(-1.4, 1.4)
    axes[0, 1].axis("off")
    axes[0, 1].add_patch(FancyBboxPatch((0.2, 0.35), 0.6, 0.3, boxstyle="round,pad=0.02",
                                        facecolor="0.92", edgecolor="0.3", lw=1.6,
                                        transform=axes[0, 1].transAxes))
    axes[0, 1].text(0.5, 0.5, "Filter\n(time-varying)", ha="center", va="center",
                    fontsize=13, transform=axes[0, 1].transAxes)
    axes[0, 1].annotate("", xy=(0.18, 0.5), xytext=(-0.02, 0.5),
                        xycoords="axes fraction", arrowprops=dict(arrowstyle="-|>", color="0.4", lw=2))
    axes[0, 1].annotate("", xy=(1.02, 0.5), xytext=(0.82, 0.5),
                        xycoords="axes fraction", arrowprops=dict(arrowstyle="-|>", color="0.4", lw=2))
    out_wave = np.convolve(pulse, np.ones(40) / 40, mode="same")  # smoothed = filtered
    axes[0, 2].plot(t, out_wave, color=PURPLE)
    axes[0, 2].set_title("Shaped output", fontsize=13, color=PURPLE)
    axes[0, 2].set_ylim(-1.4, 1.4)

    # bottom row: spectra
    stem(axes[1, 0], k, src_spec, BLUE, ms=5)
    axes[1, 0].set_title("many harmonics", fontsize=11)
    axes[1, 1].plot(k, Hk, color=RED)
    axes[1, 1].fill_between(k, 0, Hk, color=RED, alpha=0.15)
    axes[1, 1].set_title("filter response", fontsize=11)
    stem(axes[1, 2], k, out_spec, PURPLE, ms=5)
    axes[1, 2].set_title("carved spectrum", fontsize=11)
    for ax in axes[1]:
        ax.set_xlabel("Harmonic")
        ax.set_yticks([])
    for ax in list(axes[0]) + list(axes[1]):
        if ax is not axes[0, 1]:
            ax.set_xticks([])
    save_fig("fig-subtractive-diagram.png")


# ---------------------------------------------------------------------------
# 9. Sliding-convolution animation (GIF): reversed filter slides across x.
# ---------------------------------------------------------------------------


def fig_convolution_sliding() -> None:
    from PIL import Image

    # A pulse-train-like input (isolated bumps) makes the "spreading" clear.
    x = np.array([0, 3, 0, 0, 0, 2, 3, 0, 0, 0, 0, 2, 0, 0], dtype=float)
    h = np.array([3.0, 2.0, 1.0])           # asymmetric, so the reversal is visible
    K = len(h)
    y = np.convolve(x, h)
    xlim = (-3.5, len(y) + 0.5)

    frames = []
    order = list(range(len(y))) + [len(y) - 1] * 4  # hold on the last frame
    for n in order:
        fig, (axt, axb) = plt.subplots(2, 1, figsize=(9, 4.6), sharex=True)
        # top: input x (blue) with the reversed filter overlaid at position n
        stem(axt, np.arange(len(x)), x, BLUE, ms=6)
        axt.axvspan(n - K + 0.5, n + 0.5, color=RED, alpha=0.10)
        taps = [n - k for k in range(K)]        # tap k sits at index n-k
        stem(axt, taps, h, RED, ms=6)
        axt.set_ylabel(r"$x[n]$ and reversed $h$", fontsize=12)
        axt.set_ylim(-0.5, 3.5)
        # bottom: output y built up to index n, current sample highlighted
        stem(axb, np.arange(n + 1), y[:n + 1], PURPLE, ms=5)
        axb.plot([n], [y[n]], "o", color=PURPLE, ms=12)
        axb.set_ylabel(r"$y = h * x$", fontsize=12)
        axb.set_xlabel(r"Sample index $n$")
        axb.set_ylim(0, y.max() * 1.15)
        for ax in (axt, axb):
            ax.set_xlim(*xlim)
            ax.set_xticks(range(-3, len(y) + 1, 2))
            ax.axvline(-0.5, color="0.75", lw=1.0, ls=":")   # marks where n < 0 (x assumed 0)
            ax.axhline(0, color="0.8", lw=0.8)
        fig.tight_layout()
        fig.canvas.draw()
        frames.append(Image.fromarray(np.asarray(fig.canvas.buffer_rgba())).convert("RGB"))
        plt.close(fig)

    pal = frames[0].convert("P", palette=Image.ADAPTIVE, colors=255)
    frames_p = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
    frames_p[0].save(str(ASSETS / "fig-convolution-sliding.gif"), save_all=True,
                     append_images=frames_p[1:], duration=450, loop=0, disposal=2)
    print("  wrote fig-convolution-sliding.gif")


def main() -> None:
    print("Figures:")
    fig_lti_goal()
    fig_diffeq_lowpass()
    fig_diffeq_highpass()
    fig_convolution_example()
    fig_recursive_signalflow()
    fig_filter_types()
    fig_filter_realworld()
    fig_frequency_response()
    fig_manual_analysis()
    fig_subtractive_diagram()
    print("Audio:")
    fig_diffeq_responses()
    fig_filter_type_audio()
    print("Animations:")
    fig_convolution_sliding()
    # The room impulse-response GIF (fig-room-ir.gif) is McFee's original,
    # fetched by fetch_mcfee_ir.py rather than generated here.


if __name__ == "__main__":
    main()
