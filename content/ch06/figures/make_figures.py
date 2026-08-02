"""Generate figures and sound examples for Chapter 6 (modulation synthesis).

Outputs are written to ../assets/. This file is *not* student-facing: it
renders the matplotlib diagrams (ring-modulation time domain, sidebands,
negative-frequency symmetry, amplitude modulation, time-varying frequency,
AM-vs-FM, and the FM index sweep) plus the synthetic demonstration tones.

Run with the project virtualenv (pyquist reached via PYTHONPATH):
    PYTHONPATH=../../../pyquist ../../../.venv/bin/python make_figures.py
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

plt.rcParams.update(
    {
        "font.size": 14,
        "axes.labelsize": 16,
        "xtick.labelsize": 13,
        "ytick.labelsize": 13,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "lines.linewidth": 2.0,
    }
)
COLORS = plt.rcParams["axes.prop_cycle"].by_key()["color"]


def save_fig(name: str) -> None:
    plt.tight_layout()
    plt.savefig(ASSETS / name, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  wrote {name}")


def write_audio(samples: np.ndarray, name: str) -> None:
    audio = pq.Audio(samples.astype(np.float32), F_S)
    audio.normalize(peak_dbfs=PEAK_DBFS)
    audio.write(str(ASSETS / name))
    print(f"  wrote {name}")


# ---------------------------------------------------------------------------
# Synthesis helpers
# ---------------------------------------------------------------------------


def t_axis(dur: float) -> np.ndarray:
    return np.arange(int(dur * F_S)) / F_S


def osc(f: float, dur: float) -> np.ndarray:
    """A basic (unit-amplitude, zero-phase) sine at f Hz."""
    return np.sin(2 * np.pi * f * t_axis(dur))


def ring_mod(f_c: float, f_m: float, dur: float) -> np.ndarray:
    return osc(f_c, dur) * osc(f_m, dur)


def amp_mod(f_c: float, f_m: float, dur: float, r: float = 2.0) -> np.ndarray:
    return osc(f_c, dur) * (r / 2.0 + osc(f_m, dur))


def fm(f_c: float, f_m: float, D: float, dur: float) -> np.ndarray:
    """Classic (integrated) FM: sin(2*pi*f_c*t + (D/f_m) sin(2*pi*f_m*t))."""
    t = t_axis(dur)
    return np.sin(2 * np.pi * f_c * t + (D / f_m) * np.sin(2 * np.pi * f_m * t))


def hzosc_naive(freq: np.ndarray) -> np.ndarray:
    """WRONG time-varying oscillator: instantaneous freq times absolute time."""
    n = np.arange(len(freq))
    return np.sin(2 * np.pi * freq * n / F_S)


def hzosc(freq: np.ndarray) -> np.ndarray:
    """CORRECT time-varying oscillator: accumulate phase (integrate freq)."""
    theta = np.cumsum(2 * np.pi * freq / F_S)
    return np.sin(theta)


def taper(x: np.ndarray, ms: float = 8.0) -> np.ndarray:
    """Short raised-cosine fade in/out to avoid onset/offset clicks."""
    n = int(ms / 1000 * F_S)
    if 2 * n >= len(x):
        return x
    ramp = 0.5 * (1 - np.cos(np.linspace(0, np.pi, n)))
    env = np.ones(len(x))
    env[:n] = ramp
    env[-n:] = ramp[::-1]
    return x * env


# Analytical amplitude-spectrum stem plots ----------------------------------


def stem(ax, freqs, amps, color, ms=8, lw=2.0):
    markerline, stemlines, baseline = ax.stem(freqs, amps)
    plt.setp(markerline, color=color, markersize=ms)
    plt.setp(stemlines, color=color, linewidth=lw)
    plt.setp(baseline, color="0.7", linewidth=1.0)


def half_gridlines(ax) -> None:
    """Dashed horizontal reference lines and y-ticks at 1/2 and 1."""
    for y in (0.5, 1.0):
        ax.axhline(y, color="0.8", linewidth=1.0, linestyle="--", zorder=0)
    ax.set_yticks([0.5, 1.0])
    ax.set_yticklabels([r"$\frac{1}{2}$", "1"])


# The book's frequency-domain colour convention: modulator blue, carrier red,
# sidebands purple (matching the lecture slides).
C_MOD, C_CAR, C_SIDE = COLORS[0], COLORS[3], COLORS[4]


# ---------------------------------------------------------------------------
# 1. Ring modulation in the time domain (carrier, LFO, product)
# ---------------------------------------------------------------------------


def fig_ringmod_time() -> None:
    dur = 1.0
    t = t_axis(dur)
    f_c, f_m = 50.0, 2.0
    carrier = osc(f_c, dur)
    modulator = osc(f_m, dur)
    product = carrier * modulator

    fig, axes = plt.subplots(3, 1, figsize=(13, 6), sharex=True)
    axes[0].plot(t, carrier, color=COLORS[0], linewidth=1.0)
    axes[0].set_ylabel(r"$\sin(\omega_c t)$")
    axes[1].plot(t, modulator, color=COLORS[1])
    axes[1].set_ylabel(r"$\sin(\omega_m t)$")
    axes[2].plot(t, product, color=COLORS[0], linewidth=1.0)
    # trace the modulator envelope over the product
    axes[2].plot(t, np.abs(modulator), color=COLORS[1], linewidth=1.2, linestyle="--")
    axes[2].plot(t, -np.abs(modulator), color=COLORS[1], linewidth=1.2, linestyle="--")
    axes[2].set_ylabel(r"$\sin(\omega_c t)\,\sin(\omega_m t)$")
    axes[2].set_xlabel("Time (s)")
    for ax in axes:
        ax.set_ylim(-1.15, 1.15)
    save_fig("fig-ringmod-time.png")


# ---------------------------------------------------------------------------
# 2. Ring-modulation sidebands (positive frequencies)
# ---------------------------------------------------------------------------


def fig_sidebands() -> None:
    f_c, f_m = 220.0, 40.0
    fig, ax = plt.subplots(figsize=(11, 4))

    half_gridlines(ax)

    # inputs (dashed) that "disappear": modulator blue, carrier red
    for f, lab, col in [(f_m, r"$\omega_m$", C_MOD), (f_c, r"$\omega_c$", C_CAR)]:
        ax.plot([f, f], [0, 1.0], linestyle="--", color=col, linewidth=1.8, alpha=0.7)
        ax.annotate(lab, xy=(f, 1.02), ha="center", va="bottom", fontsize=15, color=col)

    # outputs (solid) that appear: sidebands purple
    stem(ax, [f_c - f_m, f_c + f_m], [0.5, 0.5], C_SIDE)
    ax.annotate(r"$\omega_c - \omega_m$", xy=(f_c - f_m, 0.54), ha="center", va="bottom", fontsize=14)
    ax.annotate(r"$\omega_c + \omega_m$", xy=(f_c + f_m, 0.54), ha="center", va="bottom", fontsize=14)

    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Amplitude")
    ax.set_xlim(0, 320)
    ax.set_ylim(0, 1.15)
    save_fig("fig-sidebands.png")


# ---------------------------------------------------------------------------
# 3. Negative-frequency symmetry: amplitude (even) and phase (odd)
# ---------------------------------------------------------------------------


def fig_negative_symmetry() -> None:
    w = 1.0
    fig, (ax_a, ax_p) = plt.subplots(2, 1, figsize=(8.5, 5.2))
    fig.subplots_adjust(hspace=0.35)

    # amplitude spectrum: even
    stem(ax_a, [-w, w], [1.0, 1.0], COLORS[4])
    ax_a.axvline(0, color="0.6", linewidth=1.0)
    ax_a.set_ylabel("Amplitude")
    ax_a.set_ylim(0, 1.25)
    ax_a.set_xlim(-2.0, 2.0)
    ax_a.set_xticks([-w, 0, w])
    ax_a.set_xticklabels([r"$-\omega$", "0", r"$\omega$"])
    ax_a.annotate("even symmetry", xy=(0.02, 0.86), xycoords="axes fraction",
                  fontsize=13, color="0.4")

    # phase spectrum: odd
    stem(ax_p, [-w, w], [-np.pi, np.pi], COLORS[3])
    ax_p.axhline(0, color="0.6", linewidth=1.0)
    ax_p.axvline(0, color="0.6", linewidth=1.0)
    ax_p.set_ylabel("Phase")
    ax_p.set_xlabel("Frequency")
    ax_p.set_ylim(-np.pi * 1.3, np.pi * 1.3)
    ax_p.set_xlim(-2.0, 2.0)
    ax_p.set_yticks([-np.pi, 0, np.pi])
    ax_p.set_yticklabels([r"$-\pi$", "0", r"$\pi$"])
    ax_p.set_xticks([-w, 0, w])
    ax_p.set_xticklabels([r"$-\omega$", "0", r"$\omega$"])
    ax_p.annotate("odd symmetry", xy=(0.02, 0.86), xycoords="axes fraction",
                  fontsize=13, color="0.4")
    save_fig("fig-negative-symmetry.png")


# ---------------------------------------------------------------------------
# 4. Full ring-modulation spectrum with four sidebands (w_m > w_c)
# ---------------------------------------------------------------------------


def fig_ringmod_full() -> None:
    f_c, f_m = 55.0, 275.0  # w_m > w_c so the lower sideband goes negative
    lo, hi = f_c - f_m, f_c + f_m  # -220, 330
    fig, ax = plt.subplots(figsize=(12, 4))

    # the input frequencies (dashed): modulator blue, carrier red
    for f, lab, col in [(f_m, r"$\omega_m$", C_MOD), (f_c, r"$\omega_c$", C_CAR)]:
        ax.plot([f, f], [0, 0.68], linestyle="--", color=col, linewidth=1.6, alpha=0.7)
        ax.annotate(lab, xy=(f, 0.69), ha="center", va="bottom", fontsize=13, color=col)

    sidebands = [(-hi, r"$-(\omega_c+\omega_m)$"),
                 (lo, r"$\omega_c-\omega_m$"),
                 (-lo, r"$\omega_m-\omega_c$"),
                 (hi, r"$\omega_c+\omega_m$")]
    stem(ax, [s[0] for s in sidebands], [0.5] * 4, C_SIDE)
    for f, lab in sidebands:
        ax.annotate(lab, xy=(f, 0.53), ha="center", va="bottom", fontsize=12)

    ax.axvline(0, color="0.6", linewidth=1.0)
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Amplitude")
    ax.set_xlim(-hi * 1.25, hi * 1.25)
    ax.set_ylim(0, 0.85)
    save_fig("fig-ringmod-full.png")


# ---------------------------------------------------------------------------
# 5. Amplitude-modulation spectrum (carrier retained)
# ---------------------------------------------------------------------------


def fig_am_spectrum() -> None:
    f_c, f_m = 220.0, 40.0
    fig, ax = plt.subplots(figsize=(11, 4))
    half_gridlines(ax)
    stem(ax, [f_c], [1.0], C_CAR)
    stem(ax, [f_c - f_m, f_c + f_m], [0.5, 0.5], C_SIDE)
    ax.annotate(r"$\omega_c$", xy=(f_c, 1.02), ha="center", va="bottom", fontsize=15, color=C_CAR)
    ax.annotate(r"$\omega_c-\omega_m$", xy=(f_c - f_m, 0.52), ha="center", va="bottom", fontsize=13)
    ax.annotate(r"$\omega_c+\omega_m$", xy=(f_c + f_m, 0.52), ha="center", va="bottom", fontsize=13)
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Amplitude")
    ax.set_xlim(0, 320)
    ax.set_ylim(0, 1.2)
    save_fig("fig-am-spectrum.png")


# ---------------------------------------------------------------------------
# 6. Time-varying frequency control signal
# ---------------------------------------------------------------------------


def freq_ramp(dur: float) -> np.ndarray:
    """440 Hz held, ramped up to 880 Hz, then held (over `dur` seconds)."""
    t = t_axis(dur)
    return np.interp(t, [0.0, 0.25 * dur, 0.75 * dur, dur], [440, 440, 880, 880])


def fig_timevar_freq() -> None:
    dur = 2.0
    t = t_axis(dur)
    freq = freq_ramp(dur)
    fig, ax = plt.subplots(figsize=(11, 3.4))
    ax.plot(t, freq, color=COLORS[1])
    ax.set_xlabel("Time (s)")
    ax.set_ylabel(r"$f(t)$ (Hz)")
    ax.set_ylim(400, 920)
    save_fig("fig-timevar-freq.png")


# ---------------------------------------------------------------------------
# 7. Amplitude modulation vs. frequency modulation (schematic spectra)
# ---------------------------------------------------------------------------


def fig_am_vs_fm() -> None:
    f_c, f_m = 220.0, 40.0
    fig, (ax_am, ax_fm) = plt.subplots(1, 2, figsize=(13, 4), sharey=True)

    # AM: carrier + two sidebands
    stem(ax_am, [f_c], [1.0], COLORS[3])
    stem(ax_am, [f_c - f_m, f_c + f_m], [0.5, 0.5], COLORS[4])
    ax_am.text(0.5, 0.97, "Amplitude modulation", transform=ax_am.transAxes,
               ha="center", va="top", fontsize=15, fontweight="bold")
    ax_am.set_xlabel("Frequency (Hz)")
    ax_am.set_ylabel("Amplitude")

    # FM: carrier + many sidebands at f_c + k f_m (Bessel-ish decay, schematic)
    ks = np.arange(-5, 6)
    I = 2.0  # index of modulation, schematic Gaussian sideband envelope
    amps = np.exp(-(ks / (I + 1.0)) ** 2)
    amps = amps / amps.max()
    freqs = f_c + ks * f_m
    keep = freqs > 0
    stem(ax_fm, freqs[keep & (ks != 0)], amps[keep & (ks != 0)], COLORS[4])
    stem(ax_fm, [f_c], [1.0], COLORS[3])
    ax_fm.text(0.5, 0.97, "Frequency modulation", transform=ax_fm.transAxes,
               ha="center", va="top", fontsize=15, fontweight="bold")
    ax_fm.set_xlabel("Frequency (Hz)")

    for ax in (ax_am, ax_fm):
        ax.set_xlim(f_c - 6 * f_m, f_c + 6 * f_m)
        ax.set_ylim(0, 1.15)
        ax.axvline(f_c, color=COLORS[3], linewidth=0.8, alpha=0.3)
    save_fig("fig-am-vs-fm.png")


# ---------------------------------------------------------------------------
# 8. FM spectrum grows with the index of modulation (measured via FFT)
# ---------------------------------------------------------------------------


def _amp_spectrum(x: np.ndarray):
    win = np.hanning(len(x))
    X = np.abs(np.fft.rfft(x * win))
    freqs = np.fft.rfftfreq(len(x), 1 / F_S)
    return freqs, X / X.max()


def fig_fm_index() -> None:
    f_c, f_m = 440.0, 110.0
    dur = 0.5
    indices = [0.0, 1.0, 2.0, 4.0]
    fig, axes = plt.subplots(len(indices), 1, figsize=(12, 8), sharex=True)
    for ax, I in zip(axes, indices):
        D = I * f_m
        freqs, X = _amp_spectrum(fm(f_c, f_m, D, dur) if I > 0 else osc(f_c, dur))
        ax.plot(freqs, X, color=COLORS[4], linewidth=1.2)
        ax.fill_between(freqs, 0, X, color=COLORS[4], alpha=0.25)
        ax.axvline(f_c, color=COLORS[3], linewidth=1.0, linestyle="--", alpha=0.7)
        ax.set_ylabel(f"$I = {I:g}$")
        ax.set_ylim(0, 1.1)
        ax.set_yticks([])
    axes[-1].set_xlabel("Frequency (Hz)")
    axes[-1].set_xlim(0, f_c + 8 * f_m)
    save_fig("fig-fm-index.png")


# ---------------------------------------------------------------------------
# 9. Spectrograms of the real-instrument intro clips
# ---------------------------------------------------------------------------


def fig_spectrograms() -> None:
    import soundfile as sf

    clips = [
        ("cello", "audio-cello-tremolo"),
        ("guitar", "audio-guitar-vibrato"),
        ("trumpet", "audio-trumpet"),
    ]
    for label, stem_name in clips:
        path = ASSETS / f"{stem_name}.wav"
        if not path.exists():
            print(f"  (skip fig-spec-{label}: {path.name} missing)")
            continue
        samples, sr = sf.read(str(path))
        audio = pq.Audio(samples.astype(np.float32), sr)
        fig, ax = plt.subplots(figsize=(5.2, 3.4))
        pq.plot_spec(audio, ax=ax, dynamic_range_db=70.0)
        ax.set_ylim(80, 8000)  # focus on the musically relevant range
        save_fig(f"fig-spec-{label}.png")


# ---------------------------------------------------------------------------
# Audio examples
# ---------------------------------------------------------------------------


def make_audio() -> None:
    dur = 3.0
    # Ring modulation as tremolo (slow modulation)
    for f_c in (220.0, 330.0):
        for f_m in (1.0, 2.0):
            write_audio(taper(ring_mod(f_c, f_m, dur)),
                        f"audio-rm-{int(f_c)}x{int(f_m)}.wav")

    # Sidebands emerging: fixed carrier, increasing modulation rate
    for f_m in (3, 6, 12, 24, 48):
        write_audio(taper(ring_mod(240.0, float(f_m), dur)),
                    f"audio-rm-240x{f_m}.wav")

    # Negative frequency: cos at +220 and -220 Hz sound identical
    t = t_axis(dur)
    write_audio(taper(np.cos(2 * np.pi * 220.0 * t)), "audio-cos-pos220.wav")
    write_audio(taper(np.cos(2 * np.pi * -220.0 * t)), "audio-cos-neg220.wav")

    # Amplitude modulation (carrier retained), audible modulation rate
    write_audio(taper(amp_mod(220.0, 55.0, dur)), "audio-am-220x55.wav")

    # Time-varying frequency: wrong vs right
    freq = freq_ramp(dur)
    write_audio(taper(hzosc_naive(freq)), "audio-timevar-wrong.wav")
    write_audio(taper(hzosc(freq)), "audio-timevar-right.wav")

    # Vibrato via FM (small depth, slow modulator)
    write_audio(taper(fm(440.0, 6.0, 12.0, dur)), "audio-fm-vibrato.wav")

    # FM timbres at increasing index of modulation
    for I in (1, 2, 4):
        write_audio(taper(fm(440.0, 110.0, I * 110.0, dur)),
                    f"audio-fm-I{I}.wav")
    # Harmonic (f_c/f_m = 2) vs inharmonic (f_c/f_m = 5/7) at the same index
    write_audio(taper(fm(440.0, 220.0, 3.0 * 220.0, dur)), "audio-fm-harmonic.wav")
    write_audio(taper(fm(200.0, 280.0, 3.0 * 280.0, dur)), "audio-fm-bell.wav")


def fig_riemann_sum() -> None:
    """A Riemann sum approximating the area under a curve (for the
    time-varying-frequency section, and referenced from Chapter 8)."""
    g = lambda u: 0.6 + 0.5 * np.sin(2 * np.pi * 0.5 * u) * np.exp(-0.15 * u)
    fig, ax = plt.subplots(figsize=(11, 3.6))
    u = np.linspace(0, 8, 500)
    edges = np.arange(0, 8, 0.125)
    for e in edges:
        ax.add_patch(plt.Rectangle((e, 0), 0.125, g(e), facecolor=COLORS[2],
                                   alpha=0.35, edgecolor=COLORS[2], linewidth=1.0))
    ax.plot(u, g(u), color=COLORS[0], linewidth=2.5, zorder=5, label=r"$\omega(\tau)$")
    ax.annotate(r"width $\Delta t$", xy=(edges[24] + 0.06, 0.06), ha="center",
                fontsize=12, color="0.3")
    ax.set_xlabel(r"$\tau$")
    ax.set_ylabel(r"$\omega(\tau)$")
    ax.set_xlim(0, 8)
    ax.set_ylim(0, 1.3)
    ax.legend(loc="upper right", fontsize=13)
    save_fig("fig-riemann-sum.png")


def main() -> None:
    print("Figures:")
    fig_ringmod_time()
    fig_riemann_sum()
    fig_sidebands()
    fig_negative_symmetry()
    fig_ringmod_full()
    fig_am_spectrum()
    fig_timevar_freq()
    fig_am_vs_fm()
    fig_fm_index()
    fig_spectrograms()
    print("Audio:")
    make_audio()


if __name__ == "__main__":
    main()
