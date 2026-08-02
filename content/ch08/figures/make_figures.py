"""Generate figures and sound examples for Chapter 8 (the DFT).

Outputs are written to ../assets/. This file is *not* student-facing.

Run with the project virtualenv (pyquist reached via PYTHONPATH):
    PYTHONPATH=../../../../pyquist ../../../.venv/bin/python make_figures.py
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pyquist as pq

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
# 1. Windowing: finite interval -> spectral leakage (time + frequency)
# ---------------------------------------------------------------------------


def fig_windowing() -> None:
    # Same running example as Chapter 7: x(t) = sin(2 pi t) + sin(2 pi 2 t).
    fs = 200.0
    dur = 8.0
    t = np.arange(int(dur * fs)) / fs
    x = np.sin(2 * np.pi * 1 * t) + np.sin(2 * np.pi * 2 * t)
    a, b = 2.0, 6.0
    w = ((t >= a) & (t <= b)).astype(float)
    xw = x * w

    def spectrum(sig):
        S = np.fft.fftshift(np.fft.fft(sig))
        f = np.fft.fftshift(np.fft.fftfreq(len(sig), 1 / fs))
        return f, np.abs(S) / np.abs(S).max()

    fig, axes = plt.subplots(2, 3, figsize=(14, 6))
    # time row
    axes[0, 0].plot(t, x, color=ORANGE)
    axes[0, 0].set_title(r"$x(t)$", fontsize=15)
    axes[0, 0].set_ylabel("Amplitude")
    axes[0, 1].plot(t, w, color=RED)
    axes[0, 1].set_title(r"$w_{a,b}(t)$", fontsize=15)
    axes[0, 2].plot(t, x, color=ORANGE, alpha=0.25, ls="--")
    axes[0, 2].plot(t, xw, color=GREEN)
    axes[0, 2].set_title(r"$x(t)\cdot w_{a,b}(t)$", fontsize=15)
    for ax in axes[0]:
        ax.set_xlabel("Time (s)")
        ax.set_xlim(0, dur)

    # frequency row
    stem(axes[1, 0], [-2, -1, 1, 2], [1, 1, 1, 1], ORANGE, ms=6)
    axes[1, 0].set_title(r"$|X(\omega)|$", fontsize=15)
    axes[1, 0].set_ylabel("Amplitude")
    fw, Sw = spectrum(w)
    axes[1, 1].plot(fw, Sw, color=RED)
    axes[1, 1].set_title(r"$|W_{a,b}(\omega)|$", fontsize=15)
    fxw, Sxw = spectrum(xw)
    axes[1, 2].plot(fxw, Sxw, color=GREEN)
    axes[1, 2].set_title(r"$|X_{a,b}(\omega)|$  (leakage)", fontsize=15)
    for ax in axes[1]:
        ax.set_xlabel("Frequency (Hz)")
        ax.set_xlim(-5, 5)
        ax.set_ylim(0, 1.15)
    save_fig("fig-windowing.png")


# ---------------------------------------------------------------------------
# 3. DFT analysis frequencies: real (cos) and imag (-sin) components
# ---------------------------------------------------------------------------


def fig_dft_bins() -> None:
    N = 64
    n = np.arange(N)
    fig, (ax_r, ax_i) = plt.subplots(2, 1, figsize=(12, 6), sharex=True)
    cmap = [ORANGE, RED, PURPLE, BLUE]
    for k in range(4):
        ph = np.exp(-1j * 2 * np.pi * k * n / N)
        ax_r.plot(n, ph.real, color=cmap[k], marker="o", markersize=3, label=f"$k = {k}$")
        ax_i.plot(n, ph.imag, color=cmap[k], marker="o", markersize=3)
    ax_r.set_ylabel(r"Real: $\cos(2\pi k n / N)$")
    ax_i.set_ylabel(r"Imag: $-\sin(2\pi k n / N)$")
    ax_i.set_xlabel(r"Sample index $n$")
    ax_r.legend(loc="upper right", ncol=4, fontsize=11)
    for ax in (ax_r, ax_i):
        ax.set_xlim(0, N - 1)
        ax.set_ylim(-1.25, 1.25)
        ax.axhline(0, color="0.8", linewidth=0.8)
    save_fig("fig-dft-bins.png")


# ---------------------------------------------------------------------------
# 4. FFT divide-and-conquer schematic (N-point DFT = two N/2-point DFTs)
# ---------------------------------------------------------------------------


def fig_fft_schematic() -> None:
    """A conventional 8-point decimation-in-time FFT butterfly diagram."""
    from matplotlib.patches import FancyBboxPatch
    fig, ax = plt.subplots(figsize=(12, 5.2))
    ax.axis("off")
    ax.set_xlim(-1.2, 8.2)
    ax.set_ylim(-1.0, 8.2)

    rows_even = [7, 6, 5, 4]  # E[0..3]
    rows_odd = [3, 2, 1, 0]   # O[0..3]
    x_in, x_box0, x_box1, x_eo, x_out = -0.3, 1.2, 2.8, 2.8, 6.0

    # input labels + rails into the two half-size DFT boxes (even/odd samples)
    for y, i in zip(rows_even, [0, 2, 4, 6]):
        ax.text(x_in - 0.15, y, f"$x[{i}]$", ha="right", va="center", fontsize=12)
        ax.plot([x_in, x_box0], [y, y], color="0.6", lw=1.0)
    for y, i in zip(rows_odd, [1, 3, 5, 7]):
        ax.text(x_in - 0.15, y, f"$x[{i}]$", ha="right", va="center", fontsize=12)
        ax.plot([x_in, x_box0], [y, y], color="0.6", lw=1.0)

    for y0, label, col in [(3.65, r"$N/2$-point DFT" + "\n" + "(even samples)", "#e7f2df"),
                           (-0.35, r"$N/2$-point DFT" + "\n" + "(odd samples)", "#e7f2df")]:
        ax.add_patch(FancyBboxPatch((x_box0, y0), x_box1 - x_box0, 3.7,
                                    boxstyle="round,pad=0.02", facecolor=col,
                                    edgecolor="0.3", linewidth=1.5))
        ax.text((x_box0 + x_box1) / 2, y0 + 1.85, label, ha="center", va="center", fontsize=11)

    # E/O output nodes, the butterfly crossings, and the final X[k] outputs
    for k in range(4):
        ey, oy = rows_even[k], rows_odd[k]
        top_y, bot_y = rows_even[k], rows_odd[k]  # X[k] and X[k+4]
        ax.text(x_eo + 0.12, ey + 0.18, f"$E[{k}]$", fontsize=9, color=BLUE)
        ax.text(x_eo + 0.12, oy + 0.18, f"$O[{k}]$", fontsize=9, color=ORANGE)
        # E[k] feeds X[k] (straight) and X[k+4] (diagonal)
        ax.plot([x_eo, x_out], [ey, top_y], color=BLUE, lw=1.3)
        ax.plot([x_eo, x_out], [ey, bot_y], color=BLUE, lw=1.3)
        # O[k] (scaled by the twiddle W_N^k) feeds X[k] and X[k+4]
        ax.plot([x_eo, x_out], [oy, top_y], color=ORANGE, lw=1.3)
        ax.plot([x_eo, x_out], [oy, bot_y], color=ORANGE, lw=1.3)
        ax.text((x_eo + x_out) / 2, (oy + top_y) / 2 + 0.12, f"$W_N^{k}$",
                fontsize=10, color=ORANGE, ha="center",
                bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none"))
        ax.plot(x_eo, ey, "o", color=BLUE, ms=5)
        ax.plot(x_eo, oy, "o", color=ORANGE, ms=5)

    for y, i in zip([7, 6, 5, 4, 3, 2, 1, 0], range(8)):
        ax.plot(x_out, y, "o", color=RED, ms=5)
        ax.text(x_out + 0.15, y, f"$X[{i}]$", ha="left", va="center", fontsize=12)

    ax.text(3.9, 7.9, r"combine (butterfly): $X[k] = E[k] + W_N^k\, O[k]$,"
                      r"$\quad X[k{+}4] = E[k] - W_N^k\, O[k]$",
            ha="center", fontsize=12, color="0.3")
    save_fig("fig-fft-schematic.png")


# ---------------------------------------------------------------------------
# 5. Clarinet analysis: time-domain waveform and DFT magnitude spectrum
# ---------------------------------------------------------------------------

CLARINET = ASSETS / "audio-clarinet.wav"


def _load_clarinet():
    import soundfile as sf
    x, sr = sf.read(str(CLARINET))
    x = np.asarray(x).reshape(len(np.asarray(x)), -1).mean(axis=1)
    return x, sr


def analyze_clarinet():
    """Extract f0, harmonic amplitudes, and an envelope; return + print them."""
    x, sr = _load_clarinet()
    dur = len(x) / sr

    # Envelope: peak amplitude per 20 ms frame.
    hop = int(0.02 * sr)
    frames = [np.max(np.abs(x[i:i + hop])) for i in range(0, len(x) - hop, hop)]
    env_t = np.arange(len(frames)) * hop / sr
    env = np.array(frames)

    # Spectrum of a stable sustained segment (1.0 s to 2.0 s).
    seg = x[int(1.0 * sr):int(2.0 * sr)]
    seg = seg * np.hanning(len(seg))
    X = np.abs(np.fft.rfft(seg))
    f = np.fft.rfftfreq(len(seg), 1 / sr)

    # Fundamental: strongest peak in the pitched band.
    band = (f > 200) & (f < 400)
    f0 = float(f[band][np.argmax(X[band])])

    # Harmonic amplitudes: magnitude at each multiple of f0 (peak-picked nearby).
    K = 8
    amps = []
    for k in range(1, K + 1):
        target = k * f0
        win = (f > target - 30) & (f < target + 30)
        amps.append(float(X[win].max()) if win.any() else 0.0)
    amps = np.array(amps)
    amps = amps / amps.max()

    print("  clarinet f0 = %.1f Hz, harmonic amps = %s" % (
        f0, ", ".join(f"{a:.2f}" for a in amps)))
    return dict(x=x, sr=sr, dur=dur, env_t=env_t, env=env, f=f, X=X / X.max(),
                f0=f0, amps=amps)


def fig_clarinet_time(A) -> None:
    x, sr = A["x"], A["sr"]
    t = np.arange(len(x)) / sr
    fig, ax = plt.subplots(figsize=(13, 3.4))
    ax.plot(t, x, color=BLUE, linewidth=0.6)
    ax.plot(A["env_t"], A["env"], color=RED, linewidth=2.5, label="envelope")
    ax.plot(A["env_t"], -A["env"], color=RED, linewidth=2.5)
    ax.set_xlim(0.8, A["dur"])  # start before the note's onset (~0.9 s) to show the attack
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Amplitude")
    ax.legend(loc="upper right", fontsize=12)
    save_fig("fig-clarinet-time.png")


def fig_clarinet_spectrum(A) -> None:
    fig, ax = plt.subplots(figsize=(13, 3.8))
    ax.plot(A["f"], A["X"], color=PURPLE, linewidth=1.0)
    ax.fill_between(A["f"], 0, A["X"], color=PURPLE, alpha=0.25)
    for k in range(1, 9):
        ax.axvline(k * A["f0"], color=RED, linestyle="--", linewidth=0.9, alpha=0.6)
    ax.set_xlim(0, 9 * A["f0"])
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Amplitude (norm.)")
    ax.annotate(f"$f_0 \\approx {A['f0']:.0f}$ Hz", xy=(A["f0"], 1.0),
                xytext=(A["f0"] + 130, 0.72), fontsize=13, color=RED,
                arrowprops=dict(arrowstyle="->", color=RED, lw=1.3))
    save_fig("fig-clarinet-spectrum.png")


def clarinet_resynth(A) -> None:
    """Additive resynthesis from extracted f0, harmonic amps, and envelope."""
    sr = F_S
    dur = 3.0
    t = np.arange(int(dur * sr)) / sr
    x = np.zeros_like(t)
    for k, a in enumerate(A["amps"], start=1):
        x += a * np.sin(2 * np.pi * k * A["f0"] * t)
    # Simple attack/decay envelope resembling the clarinet's.
    env = np.interp(t, [0.0, 0.08, dur - 0.3, dur], [0.0, 1.0, 1.0, 0.0])
    write_audio(x * env, "audio-clarinet-resynth.wav")


def main() -> None:
    print("Figures:")
    fig_windowing()
    fig_dft_bins()
    fig_fft_schematic()
    print("Clarinet analysis:")
    A = analyze_clarinet()
    fig_clarinet_time(A)
    fig_clarinet_spectrum(A)
    print("Audio:")
    clarinet_resynth(A)


if __name__ == "__main__":
    main()
