"""Generate figures and sound examples for Chapter 10 (Frame-based processing).

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


def write_audio(samples: np.ndarray, name: str, sr: int = F_S, peak: float = PEAK_DBFS) -> None:
    audio = pq.Audio(samples.astype(np.float32), sr)
    audio.normalize(peak_dbfs=peak)
    audio.write(str(ASSETS / name))
    print(f"  wrote {name}")


def load_trio() -> np.ndarray:
    a = pq.Audio.from_file(str(ASSETS / "audio-trio.wav"))
    return np.asarray(a.samples).reshape(-1)


# ---------------------------------------------------------------------------
# DSP building blocks (agent-side copies of the chapter's code)
# ---------------------------------------------------------------------------


def hann(n: int) -> np.ndarray:
    return 0.5 * (1 - np.cos(2 * np.pi * np.arange(n) / n))


def stft(x, hop, nF, window):
    return np.array([np.fft.rfft(x[s:s + nF] * window)
                     for s in range(0, len(x) - nF + 1, hop)])


def istft(S, hop, nF, window, trim=True):
    length = hop * (S.shape[0] - 1) + nF
    out = np.zeros(length)
    wsum = np.zeros(length)
    for k in range(S.shape[0]):
        frame = np.fft.irfft(S[k], nF) * window
        out[k * hop:k * hop + nF] += frame
        wsum[k * hop:k * hop + nF] += window ** 2
    out = out / np.maximum(wsum, 1e-8)
    return out[nF:-nF] if trim else out   # drop under-overlapped edges


def granular(x, grain_len, hop_extract, hop_overlap, window, manipulate=None):
    """Extract windowed grains, optionally manipulate the list, overlap-add."""
    grains = [x[s:s + grain_len] * window
              for s in range(0, len(x) - grain_len + 1, hop_extract)]
    if manipulate is not None:
        grains = manipulate(grains)
    length = hop_overlap * (len(grains) - 1) + grain_len
    out = np.zeros(length)
    for k, g in enumerate(grains):
        out[k * hop_overlap:k * hop_overlap + grain_len] += g
    return out


def phase_vocoder(D, rate, hop):
    """Standard phase-vocoder time stretch of a complex STFT by `rate`
    (>1 = faster/shorter, <1 = slower/longer)."""
    n_bins = D.shape[1]
    phi_adv = np.linspace(0, np.pi * hop, n_bins)
    D = np.concatenate([D, np.zeros((2, n_bins))], axis=0)
    steps = np.arange(0, D.shape[0] - 2, rate)
    out = np.zeros((len(steps), n_bins), dtype=complex)
    phase = np.angle(D[0])
    for i, step in enumerate(steps):
        j = int(np.floor(step))
        a = step - j
        mag = (1 - a) * np.abs(D[j]) + a * np.abs(D[j + 1])
        out[i] = mag * np.exp(1j * phase)
        dphi = np.angle(D[j + 1]) - np.angle(D[j]) - phi_adv
        dphi -= 2 * np.pi * np.round(dphi / (2 * np.pi))
        phase += phi_adv + dphi
    return out


def resample_by(x, factor):
    """Linearly resample x to length len(x)/factor (factor>1 shortens)."""
    n_out = int(round(len(x) / factor))
    return np.interp(np.arange(n_out) * factor, np.arange(len(x)), x)


# ===========================================================================
# AUDIO EXAMPLES
# ===========================================================================


def audio_melody():
    """A C-D-E-F-G melody of sine tones, notes contiguous (no gaps between them).
    Built from a phase-continuous per-sample frequency so note changes don't click."""
    pitches = [261.63, 293.66, 329.63, 349.23, 392.00]  # C4 D4 E4 F4 G4
    dur = 0.5
    n = int(dur * F_S)
    freq_seq = np.concatenate([[f] * n for f in pitches])
    phase = np.cumsum(2 * np.pi * freq_seq / F_S)        # phase-continuous
    x = np.sin(phase)
    total = len(x) / F_S
    x *= np.interp(np.arange(len(x)) / F_S, [0, 0.01, total - 0.02, total], [0, 1, 1, 0])
    write_audio(x, "audio-melody.wav")
    return x


def audio_granular(trio):
    sr = F_S
    # (1) A few long grains with a big gap, so each grain is audible on its own.
    grain_len = int(0.05 * sr)          # 50 ms grains
    ioi = int(0.5 * sr)                 # 500 ms inter-onset interval
    starts = np.arange(0, len(trio) - grain_len, int(0.35 * sr))[:14]
    rect = np.ones(grain_len)
    w = hann(grain_len)
    rect_out = np.zeros(ioi * len(starts) + grain_len)
    hann_out = np.zeros_like(rect_out)
    for k, s in enumerate(starts):
        g = trio[s:s + grain_len]
        rect_out[k * ioi:k * ioi + grain_len] += g * rect
        hann_out[k * ioi:k * ioi + grain_len] += g * w
    write_audio(rect_out, "audio-grains-rect.wav")
    write_audio(hann_out, "audio-grains-hann.wav")

    # (2) Dense granular texture: shuffle grain order within short segments.
    gl, hop = int(0.05 * sr), int(0.025 * sr)   # 50 ms grains, 50% overlap
    rng = np.random.default_rng(0)

    def shuffle_segments(grains, seg=40):
        grains = list(grains)
        for i in range(0, len(grains), seg):
            block = grains[i:i + seg]
            rng.shuffle(block)
            grains[i:i + seg] = block
        return grains
    tex = granular(trio, gl, hop, hop, hann(gl), manipulate=shuffle_segments)
    write_audio(tex, "audio-granular-texture.wav", peak=-12.0)   # 6 dB below full scale

    # (3) For contrast: randomize the raw SAMPLES (not grains) -> just noise.
    scrambled = trio.copy()
    rng.shuffle(scrambled)
    write_audio(scrambled, "audio-scrambled-samples.wav", peak=-18.0)   # noise: keep it quiet


def audio_time_stretch(trio):
    sr = F_S
    gl = int(0.06 * sr)
    hop = gl // 4                        # 75% overlap for smooth stretching
    w = hann(gl)
    # Granular time stretch: overlap grains at a different hop than extraction.
    half = granular(trio, gl, hop, hop * 2, w)      # spacing x2 -> 0.5x speed (longer)
    dbl = granular(trio, gl, hop, hop // 2, w)      # spacing /2 -> 2x speed (shorter)
    write_audio(half, "audio-stretch-half.wav")
    write_audio(dbl, "audio-stretch-double.wav")
    # Resampling for comparison: changes speed AND pitch together.
    write_audio(resample_by(trio, 0.5), "audio-resample-half.wav")
    write_audio(resample_by(trio, 2.0), "audio-resample-double.wav")
    # Decoupled pitch and time: raise the pitch 20% (resample down, then stretch
    # back to the original length), then independently time-stretch to half speed.
    up = resample_by(trio, 1.2)                          # shorter, +20% pitch
    up = granular(up, gl, hop, int(round(hop * 1.2)), w)   # stretch back to ~original length
    decoupled = granular(up, gl, hop, hop * 2, w)          # half speed (double the length)
    write_audio(decoupled, "audio-decoupled.wav")


def audio_spectral(trio):
    nF, hop = 2048, 512
    w = hann(nF)
    S = stft(trio, hop, nF, w)
    rng = np.random.default_rng(0)
    # (1) Phase randomization: keep magnitudes, scramble phases -> transients smear.
    Sr = np.abs(S) * np.exp(1j * rng.uniform(-np.pi, np.pi, S.shape))
    write_audio(istft(Sr, hop, nF, w), "audio-phase-random.wav")
    # (2) Brick-wall low-pass: zero every bin above a cutoff, in every frame.
    freqs = np.fft.rfftfreq(nF, 1 / F_S)
    Slp = S.copy()
    Slp[:, freqs > 1000.0] = 0.0                       # keep only content below 1 kHz
    write_audio(istft(Slp, hop, nF, w), "audio-lowpass.wav")
    # (3) Cross-synthesis: impose the voice's spectral envelope onto the trio. The
    # trio is the carrier and keeps its own (complex) spectrum; the voice is the
    # modulator and contributes only its per-bin magnitude, so the trio takes on
    # the voice's changing formants -- a "talking instrument" effect. (Following
    # the classic technique: carrier complex spectrum x modulator magnitude.)
    lucier_path = HERE.parent / "raw" / "lucier.wav"
    if lucier_path.exists():
        luc_audio = pq.Audio.from_file(str(lucier_path))
        if luc_audio.sample_rate != F_S:
            luc_audio = luc_audio.resample(F_S)
        voice = np.asarray(luc_audio.samples).reshape(-1)
        voice = np.resize(voice, len(trio))               # tile/trim to match
    else:
        print("  (raw/lucier.wav missing: using noise for cross-synth modulator)")
        voice = rng.standard_normal(len(trio))
    Sv = stft(voice, hop, nF, w)
    m = min(S.shape[0], Sv.shape[0])
    mag_v = np.abs(Sv[:m])
    mag_v = mag_v / (mag_v.max() + 1e-9)                  # voice envelope, normalized
    mag_v = mag_v ** 0.5                                  # compress its range so the trio stays bright
    Sx = S[:m] * mag_v                                    # trio's phase, voice's magnitude
    write_audio(istft(Sx, hop, nF, w), "audio-cross-synth.wav")


def audio_phase_vocoder(trio):
    nF, hop = 2048, 512
    w = hann(nF)
    S = stft(trio, hop, nF, w)
    half = istft(phase_vocoder(S, 0.5, hop), hop, nF, w)   # 0.5x speed, pitch kept
    dbl = istft(phase_vocoder(S, 2.0, hop), hop, nF, w)     # 2x speed, pitch kept
    write_audio(half, "audio-pv-half.wav")
    write_audio(dbl, "audio-pv-double.wav")
    # Pitch shift DOWN an octave: compress to 2x speed (pitch kept), then resample
    # back to the original length, which halves the pitch.
    compressed = istft(phase_vocoder(S, 2.0, hop), hop, nF, w)
    write_audio(resample_by(compressed, 0.5), "audio-pv-pitch.wav")


# ===========================================================================
# FIGURES
# ===========================================================================


def spectrogram(ax, x, nF, hop, window, sr=F_S, fmin=40.0, fmax=None, log=True):
    S = np.abs(stft(x, hop, nF, window)).T
    db = 20 * np.log10(S / S.max() + 1e-6)
    times = np.arange(S.shape[1]) * hop / sr
    freqs = np.fft.rfftfreq(nF, 1 / sr)
    fmax = fmax or sr / 2
    if log:
        ax.pcolormesh(times, freqs[1:], db[1:], cmap="magma", vmin=-80, vmax=0, shading="nearest")
        ax.set_yscale("log")
        ax.set_ylim(fmin, fmax)
    else:
        ax.pcolormesh(times, freqs, db, cmap="magma", vmin=-80, vmax=0, shading="nearest")
        ax.set_ylim(0, fmax)


_DEMO_CMAP = [BLUE, ORANGE, GREEN, RED, PURPLE, "#8c564b", "#17becf", "#e377c2"]


def _demo_wave(n):
    t = np.arange(n) / F_S
    return np.sin(2 * np.pi * 440 * t) + np.sin(2 * np.pi * 880 * t)


def fig_extract_basic():
    """A first look at framing: N_H = N_F, no overlap."""
    nF, nframes = 300, 4
    x = _demo_wave(nF * nframes)
    t = np.arange(len(x)) / F_S * 1000
    fig, ax = plt.subplots(figsize=(12, 3))
    ax.plot(t, x, color="0.35", lw=1.0)
    for k in range(nframes):
        s = k * nF
        ax.axvspan(s / F_S * 1000, (s + nF) / F_S * 1000, color=_DEMO_CMAP[k], alpha=0.16)
        ax.axvline(s / F_S * 1000, color="0.6", lw=1.0)
        ax.text((s + nF / 2) / F_S * 1000, 2.4, f"frame {k}", ha="center", fontsize=12,
                color=_DEMO_CMAP[k])
    ax.set_xlim(0, t[-1])
    ax.set_ylim(-2.6, 2.9)
    ax.set_xlabel("Time (ms)")
    ax.set_ylabel("Amplitude")
    save_fig("fig-extract-basic.png")


def gif_frame_extraction():
    """Three rows (0%, 25%, 50% overlap), one frame highlighted per timestep."""
    from PIL import Image
    nF = 300
    x = _demo_wave(1600)
    t = np.arange(len(x)) / F_S * 1000
    rows = [(nF, "0% overlap  ($N_H = N_F$)"),
            (int(nF * 0.75), "25% overlap  ($N_H = 3N_F/4$)"),
            (nF // 2, "50% overlap  ($N_H = N_F/2$)")]
    nsteps = max(len(range(0, len(x) - nF + 1, hop)) for hop, _ in rows)
    frames = []
    for step in range(nsteps):
        fig, axes = plt.subplots(3, 1, figsize=(11, 5.4), sharex=True)
        for ax, (hop, title) in zip(axes, rows):
            ax.plot(t, x, color="0.35", lw=1.0)
            starts = list(range(0, len(x) - nF + 1, hop))
            for s in starts:
                ax.axvline(s / F_S * 1000, color="0.82", lw=0.8)
            if step < len(starts):
                s = starts[step]
                ax.axvspan(s / F_S * 1000, (s + nF) / F_S * 1000, color=RED, alpha=0.22)
                ax.text((s + nF / 2) / F_S * 1000, 2.5, f"frame {step}", ha="center",
                        fontsize=11, color=RED)
            ax.set_title(title, fontsize=13)
            ax.set_ylim(-2.6, 3.2)
            ax.set_yticks([])
        axes[-1].set_xlabel("Time (ms)")
        axes[-1].set_xlim(0, t[-1])
        fig.tight_layout()
        fig.canvas.draw()
        frames.append(Image.fromarray(np.asarray(fig.canvas.buffer_rgba())).convert("RGB"))
        plt.close(fig)
    frames += [frames[-1]] * 3
    frames[0].save(str(ASSETS / "fig-frame-extraction.gif"), save_all=True,
                   append_images=frames[1:], duration=650, loop=0)
    print("  wrote fig-frame-extraction.gif")


def fig_boundary():
    """The four boundary-condition combinations: {left, center} x {pad, truncate}."""
    nF, nH = 300, 300
    x = _demo_wave(1000)                       # length not a multiple of nF
    t_full = np.arange(1200) / F_S * 1000       # a bit of room past the signal end
    end_ms = len(x) / F_S * 1000
    fig, axes = plt.subplots(4, 1, figsize=(11, 6.2), sharex=True)
    specs = [("Left-aligned, zero-pad", "left", "pad"),
             ("Left-aligned, truncate", "left", "trunc"),
             ("Centered, zero-pad", "center", "pad"),
             ("Centered, truncate", "center", "trunc")]
    tks = [k * nH for k in range(4)]                              # the shared frame timestamps
    for row, (ax, (title, align, mode)) in enumerate(zip(axes, specs)):
        ax.plot(np.arange(len(x)) / F_S * 1000, x, color="0.35", lw=1.0)
        ax.axvline(end_ms, color="0.5", ls="--", lw=1.2)          # signal ends here
        for tk in tks:                                            # same t_k in every panel
            ax.axvline(tk / F_S * 1000, color="0.15", ls=":", lw=1.1, zorder=5)
        if row == 0:                                              # label the timestamps once
            for k, tk in enumerate(tks):
                ax.text(tk / F_S * 1000, 2.15, f"$t_{k}$", ha="center", va="top",
                        fontsize=11, color="0.15",
                        bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.85))
        for k in range(5):
            center = k * nH
            start = center - nF // 2 if align == "center" else center
            stop = start + nF
            if start >= len(x):
                break
            complete = 0 <= start and stop <= len(x)
            if not complete and mode == "trunc":
                continue                                          # drop incomplete frames
            col = _DEMO_CMAP[k]
            a, b = start / F_S * 1000, stop / F_S * 1000
            ax.axvspan(max(a, 0), min(b, end_ms), color=col, alpha=0.18)
            if not complete and mode == "pad":                    # shade the zero-padded part
                if b > end_ms:
                    ax.axvspan(end_ms, b, color=col, alpha=0.18, hatch="///", ec=col)
                if a < 0:
                    ax.axvspan(a, 0, color=col, alpha=0.18, hatch="///", ec=col)
        ax.set_title(title, fontsize=12)
        ax.set_ylim(-2.6, 2.6)
        ax.set_yticks([])
    axes[-1].set_xlabel("Time (ms)")
    axes[-1].set_xlim(-3, t_full[-1])
    save_fig("fig-boundary.png")


def fig_cola():
    nF, hop = 200, 100                      # Hann at 50% overlap
    w = hann(nF)
    n = np.arange(700)
    fig, ax = plt.subplots(figsize=(11, 3.4))
    total = np.zeros(len(n))
    for k in range(-1, 7):
        start = k * hop
        seg = np.zeros(len(n))
        idx = np.arange(nF) + start
        valid = (idx >= 0) & (idx < len(n))
        seg[idx[valid]] = w[valid]
        ax.plot(n, seg, color=BLUE, lw=1.2, alpha=0.5)
        total += seg
    ax.plot(n, total, color=RED, lw=2.6, label="sum of windows")
    ax.axhline(1.0, color="0.6", ls="--", lw=1.0)
    ax.set_xlim(0, 600)
    ax.set_ylim(0, 1.3)
    ax.set_xlabel("Sample index $n$")
    ax.set_ylabel("Window value")
    ax.legend(loc="upper right", fontsize=12)
    save_fig("fig-cola.png")


def fig_reconstruction_cases():
    nF = 100
    fig, axes = plt.subplots(1, 3, figsize=(14, 3.4), sharey=True)
    specs = [(100, r"$N_H = N_F$", "perfect reconstruction"),
             (140, r"$N_H > N_F$", "gaps (samples lost)"),
             (60, r"$N_H < N_F$", "overlap (amplitude gain)")]
    n = np.arange(560)
    for ax, (hop, title, sub) in zip(axes, specs):
        total = np.zeros(len(n))
        for k in range(6):
            s = k * hop
            if s >= len(n):
                break
            idx = np.arange(nF) + s
            valid = idx < len(n)
            total[idx[valid]] += 1.0
            ax.axvspan(s, min(s + nF, len(n)), color=BLUE, alpha=0.10)
        ax.plot(n, total, color=RED, lw=2.4)
        ax.axhline(1.0, color="0.6", ls="--", lw=1.0)
        ax.set_title(title + "\n" + sub, fontsize=13)
        ax.set_xlabel("Sample index $n$")
        ax.set_xlim(0, 500)
        ax.set_ylim(0, 2.4)
    axes[0].set_ylabel("Reconstruction gain")
    save_fig("fig-reconstruction-cases.png")


def _grain_shape(x0, w, h, npts=100):
    t = np.linspace(0, 1, npts)
    return x0 + t * w, h * 0.5 * (1 - np.cos(2 * np.pi * t))


def fig_granular_collage(trio):
    fig, axes = plt.subplots(3, 1, figsize=(12, 5.2))
    cmap = [BLUE, ORANGE, GREEN, RED, PURPLE, "#8c564b"]   # six clearly distinct colors
    # source
    seg = trio[:int(2.2 * F_S)]
    axes[0].plot(np.linspace(0, 10, len(seg)), seg, color="0.35", lw=0.5)
    axes[0].set_ylabel("Source\nmaterial", rotation=0, ha="right", va="center", fontsize=12)
    # extract grains (overlapping windows), one per color
    gw, gh = 1.7, 1.0
    for k, x0 in enumerate(np.arange(0, 9, 1.5)):
        xs, ys = _grain_shape(x0, gw, gh)
        axes[1].fill_between(xs, 0, ys, color=cmap[k], alpha=0.5)
    axes[1].set_ylabel(r"Extract" + "\n" + r"grains $\times$", rotation=0, ha="right", va="center", fontsize=12)
    # reassemble: fewer grains, clearly reordered, with gaps (an obvious manipulation)
    order = [2, 5, 0, 3]
    for slot, k in enumerate(order):
        xs, ys = _grain_shape(slot * 2.3 + 0.5, gw, gh)
        axes[2].fill_between(xs, 0, ys, color=cmap[k], alpha=0.5)
    axes[2].set_ylabel(r"Reassemble" + "\n" + r"$+$", rotation=0, ha="right", va="center", fontsize=12)
    for ax in axes:
        ax.set_xlim(0, 10.5)
        ax.set_xticks([])
        ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_visible(False)
    save_fig("fig-granular-collage.png")


def fig_granular_randomize():
    rng = np.random.default_rng(2)
    n = 16
    cols = plt.cm.magma(np.linspace(0.1, 0.9, n))
    fig, axes = plt.subplots(2, 1, figsize=(12, 3.8))
    specs = [(axes[0], "Randomize order globally", rng.permutation(n), False),
             (axes[1], "Randomize order within segments of 4",
              np.concatenate([rng.permutation(4) + i for i in range(0, n, 4)]), True)]
    for ax, title, perm, segbars in specs:
        for i in range(n):
            ax.add_patch(plt.Rectangle((i, 1.1), 0.9, 0.7, color=cols[i]))         # original order
            ax.add_patch(plt.Rectangle((i, 0.0), 0.9, 0.7, color=cols[perm[i]]))   # shuffled
        if segbars:                                       # mark the segment-of-4 boundaries
            for b in range(0, n + 1, 4):
                ax.axvline(b - 0.05, ymin=0.05, ymax=0.95, color="0.25", lw=1.6)
        ax.annotate("", xy=(n / 2, 0.85), xytext=(n / 2, 1.05),
                    arrowprops=dict(arrowstyle="-|>", color="0.4"))
        ax.text(-0.4, 1.45, "grains", ha="right", va="center", fontsize=11, color="0.4")
        ax.text(-0.4, 0.35, "output", ha="right", va="center", fontsize=11, color="0.4")
        ax.set_title(title, fontsize=13)
        ax.set_xlim(-2.2, n + 0.3)
        ax.set_ylim(-0.15, 1.95)
        ax.axis("off")
    save_fig("fig-granular-randomize.png")


def fig_time_stretch():
    """Time stretching as decoupled extract/reassemble hops (collage language)."""
    fig, axes = plt.subplots(2, 1, figsize=(12, 3.8), sharex=True, sharey=True)
    cmap = [BLUE, ORANGE, GREEN, RED, PURPLE, "#8c564b"]
    gw = 1.4
    for k, x0 in enumerate(np.arange(0, 9, 1.5)):          # extract at hop N_H
        xs, ys = _grain_shape(x0, gw, 1.0)
        axes[0].fill_between(xs, 0, ys, color=cmap[k], alpha=0.5)
    axes[0].set_ylabel(r"Extract" + "\n" + r"(hop $N_H$)", rotation=0, ha="right", va="center", fontsize=12)
    for k, x0 in enumerate(np.arange(0, 18, 3.0)):          # reassemble at hop 2 N_H (spread out)
        xs, ys = _grain_shape(x0, gw, 1.0)
        axes[1].fill_between(xs, 0, ys, color=cmap[k], alpha=0.5)
    axes[1].set_ylabel(r"Reassemble" + "\n" + r"(hop $2N_H$)", rotation=0, ha="right", va="center", fontsize=12)
    axes[1].annotate("", xy=(0, -0.35), xytext=(17.4, -0.35),
                     arrowprops=dict(arrowstyle="<->", color="0.5", lw=1.2))
    axes[1].text(8.7, -0.72, "output is twice as long (half speed)", ha="center", fontsize=11, color="0.4")
    for ax in axes:
        ax.set_xlim(-0.3, 19)
        ax.set_xticks([])
        ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_visible(False)
    axes[0].set_ylim(-1.0, 1.2)          # shared y-axis: grains render at identical height
    save_fig("fig-time-stretch.png")


def _grain_with_tone(ax, x0, gw, cycles, color):
    """A bell-shaped grain envelope with an oscillation inside, to convey pitch."""
    t = np.linspace(0, 1, 160)
    env = 0.5 * (1 - np.cos(2 * np.pi * t))
    ax.fill_between(x0 + t * gw, 0, env, color=color, alpha=0.30)
    ax.plot(x0 + t * gw, env * np.sin(2 * np.pi * cycles * t), color=color, lw=1.2)


def fig_decoupled():
    """Decoupled pitch and time: resample grains (pitch), then respace them (time).
    Same collage design language as fig_time_stretch."""
    fig, axes = plt.subplots(3, 1, figsize=(12, 5.2), sharex=True, sharey=True)
    cmap = [BLUE, ORANGE, GREEN, RED, PURPLE, "#8c564b"]
    gw = 1.5             # original grain width
    gw_r = gw / 1.5      # resampling UP shortens each grain (and raises its pitch)
    cyc = 5              # same waveform in each grain; a shorter grain -> higher pitch
    # Row 1: extract grains at hop N_H (original pitch, width gw)
    for k, x0 in enumerate(np.arange(0, 9, 1.5)):
        _grain_with_tone(axes[0], x0, gw, cyc, cmap[k])
    axes[0].set_ylabel("Extract\n(hop $N_H$)", rotation=0, ha="right", va="center", fontsize=12)
    # Row 2: resample each grain -> shorter and higher-pitched, same start positions
    for k, x0 in enumerate(np.arange(0, 9, 1.5)):
        _grain_with_tone(axes[1], x0, gw_r, cyc, cmap[k])
    axes[1].set_ylabel("Resample\n(pitch $\\uparrow$, shorter)", rotation=0, ha="right", va="center", fontsize=12)
    # Row 3: reassemble the shorter grains at hop 2 N_H -> slower (longer)
    for k, x0 in enumerate(np.arange(0, 18, 3.0)):
        _grain_with_tone(axes[2], x0, gw_r, cyc, cmap[k])
    axes[2].set_ylabel("Reassemble\n(hop $2N_H$)", rotation=0, ha="right", va="center", fontsize=12)
    axes[2].annotate("", xy=(0, -0.95), xytext=(17.0, -0.95),
                     arrowprops=dict(arrowstyle="<->", color="0.5", lw=1.2))
    axes[2].text(8.5, -1.32, "twice as long (half speed), pitched up", ha="center", fontsize=11, color="0.4")
    for ax in axes:
        ax.set_xlim(-0.3, 19)
        ax.set_xticks([])
        ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_visible(False)
    axes[0].set_ylim(-1.6, 1.2)
    save_fig("fig-decoupled.png")


def fig_stft_melody(melody):
    fig, axes = plt.subplots(3, 1, figsize=(12, 8))
    total = len(melody) / F_S
    dur = total / 5
    # (1) the melody as full-length (legato) note rectangles, rising staircase
    names = ["C4", "D4", "E4", "F4", "G4"]
    for i, nm in enumerate(names):
        axes[0].add_patch(plt.Rectangle((i * dur, i - 0.4), dur, 0.8, facecolor="#e8f0fe",
                                        edgecolor=BLUE, lw=1.8))
        axes[0].text(i * dur + dur / 2, i, nm, ha="center", va="center", fontsize=14, color=BLUE)
    axes[0].set_xlim(0, total)
    axes[0].set_ylim(-0.8, 4.8)
    axes[0].set_title("The melody: C D E F G (rising)", fontsize=13)
    axes[0].set_xlabel("Time (s)")
    axes[0].set_yticks([])
    # (2) spectrogram: pitches step up over time (log frequency), aligned in time with (1)
    spectrogram(axes[1], melody, 4096, 512, hann(4096), fmin=180, fmax=900)
    axes[1].set_xlim(0, total)
    axes[1].set_title("Spectrogram: frequency over time (log scale)", fontsize=13)
    axes[1].set_xlabel("Time (s)")
    axes[1].set_ylabel("Frequency (Hz)")
    axes[1].set_yticks([200, 300, 400, 600])
    axes[1].set_yticklabels(["200", "300", "400", "600"])
    # (3) DFT of the whole signal, no window, for comparison (time lost, log-frequency axis)
    X = np.abs(np.fft.rfft(melody))
    f = np.fft.rfftfreq(len(melody), 1 / F_S)
    axes[2].plot(f, X / X.max(), color=PURPLE, lw=1.0)
    axes[2].set_xscale("log")
    axes[2].set_xlim(180, 900)
    axes[2].set_xticks([200, 300, 400, 600])
    axes[2].set_xticklabels(["200", "300", "400", "600"])
    axes[2].set_title("DFT of the whole signal: all five pitches, but no sense of order", fontsize=13)
    axes[2].set_xlabel("Frequency (Hz, log scale)")
    axes[2].set_ylabel("Amplitude")
    save_fig("fig-stft-melody.png")


def fig_leakage_windowing():
    """Two 2x3 figures (Time / Freq rows; x, w, x*w columns), one per window,
    matching 08B slides 9-10: framing convolves the spectrum with the window's."""
    fs, dur = 200.0, 4.0
    t = np.arange(int(dur * fs)) / fs
    x = np.sin(2 * np.pi * 1 * t) + np.sin(2 * np.pi * 4 * t)
    win_idx = (t >= 1.0) & (t < 3.0)

    def spec(sig):
        S = np.fft.fftshift(np.abs(np.fft.fft(sig)))
        fr = np.fft.fftshift(np.fft.fftfreq(len(sig), 1 / fs))
        return fr, S / S.max()

    for name, wfun, wlabel in [("fig-leakage.png", np.ones, r"$w(t)$ (rectangular)"),
                               ("fig-windowing.png", hann, r"$w(t)$ (Hann)")]:
        w = np.zeros_like(t)
        w[win_idx] = wfun(int(win_idx.sum()))
        xw = x * w
        fig, ax = plt.subplots(2, 3, figsize=(14, 6))
        ax[0, 0].plot(t, x, color=ORANGE);  ax[0, 0].set_title(r"$x(t)$", fontsize=15)
        ax[0, 1].plot(t, w, color=RED);      ax[0, 1].set_title(wlabel, fontsize=15)
        ax[0, 2].plot(t, x, color=ORANGE, alpha=0.25, ls="--")
        ax[0, 2].plot(t, xw, color=GREEN);   ax[0, 2].set_title(r"$x(t)\cdot w(t)$", fontsize=15)
        for a in ax[0]:
            a.set_xlim(0, dur); a.set_xlabel("Time (s)")
        ax[0, 0].set_ylabel("Amplitude")
        ax[1, 0].plot(*spec(x), color=ORANGE);   ax[1, 0].set_title(r"$|X(\omega)|$", fontsize=15)
        ax[1, 1].plot(*spec(w), color=RED);       ax[1, 1].set_title(r"$|W(\omega)|$", fontsize=15)
        ax[1, 2].plot(*spec(xw), color=GREEN);     ax[1, 2].set_title(r"$|X(\omega) * W(\omega)|$", fontsize=14)
        for a in ax[1]:
            a.set_xlim(-5, 5); a.set_xlabel("Frequency (Hz)"); a.set_ylim(0, 1.1)
        ax[1, 0].set_ylabel("Amplitude")
        save_fig(name)


def fig_spectrogram_window(trio):
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    nF, hop = 1024, 256
    spectrogram(axes[0], trio, nF, hop, np.ones(nF), fmin=60, fmax=8000)
    axes[0].set_title("Rectangular window (strong leakage)", fontsize=13)
    spectrogram(axes[1], trio, nF, hop, hann(nF), fmin=60, fmax=8000)
    axes[1].set_title("Hann window (leakage reduced)", fontsize=13)
    for ax in axes:
        ax.set_ylabel("Frequency (Hz)")
    axes[1].set_xlabel("Time (s)")
    save_fig("fig-spectrogram-window.png")


def fig_stft_analysis():
    """The basic STFT idea: cut the wave into frames, send each into a DFT."""
    from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
    fig, ax = plt.subplots(figsize=(12, 4.6))
    ax.axis("off")
    ax.set_xlim(0, 12)
    ax.set_ylim(-0.5, 5)
    cmap = [BLUE, ORANGE, GREEN, RED]
    nF = 240
    # A different (rising) pitch in each frame, so the four spectra visibly differ
    # and stacking them reads as a rising spectrogram.
    funds = [370.0, 550.0, 740.0, 920.0]
    n = np.arange(nF)
    wave = np.concatenate([np.sin(2 * np.pi * f * n / F_S) + 0.5 * np.sin(2 * np.pi * 2 * f * n / F_S)
                           for f in funds])
    wave = wave / np.abs(wave).max()
    tx = 0.6 + 10.8 * np.arange(len(wave)) / len(wave)
    ax.plot(tx, 4.3 + 0.32 * wave, color="0.35", lw=0.9)
    for k in range(4):
        xc = 0.6 + 10.8 * (k + 0.5) / 4
        x0 = 0.6 + 10.8 * k / 4
        x1 = 0.6 + 10.8 * (k + 1) / 4
        ax.axvspan(x0, x1, ymin=0.80, ymax=0.99, color=cmap[k], alpha=0.16)
        ax.text(xc, 4.95, f"frame {k}", ha="center", fontsize=10, color=cmap[k])
        ax.add_patch(FancyArrowPatch((xc, 3.75), (xc, 3.05), arrowstyle="-|>",
                                     mutation_scale=14, color="0.4", lw=1.5))
        ax.add_patch(FancyBboxPatch((xc - 0.75, 2.2), 1.5, 0.8, boxstyle="round,pad=0.03",
                                    fc="0.93", ec="0.3", lw=1.4))
        ax.text(xc, 2.6, "DFT", ha="center", va="center", fontsize=12)
        ax.add_patch(FancyArrowPatch((xc, 2.1), (xc, 1.5), arrowstyle="-|>",
                                     mutation_scale=14, color="0.4", lw=1.5))
        mag = np.abs(np.fft.rfft(wave[k * nF:(k + 1) * nF] * hann(nF)))[:14]
        mag = mag / mag.max() * 1.15
        bw = 1.36 / len(mag)
        bx = xc - 0.68 + bw * np.arange(len(mag))
        ax.bar(bx, mag, width=bw * 0.85, bottom=0.15, color=cmap[k],
               align="edge", alpha=0.9)
        ax.add_patch(plt.Rectangle((xc - 0.68, 0.15), 1.36, 1.35, fill=False,
                                   ec="0.5", lw=1.1))            # thin border per spectrum
    ax.text(0.3, 4.3, r"$x[n]$", ha="right", va="center", fontsize=14, color=BLUE)
    ax.text(6.0, -0.32, "one spectrum per frame  =  the spectrogram", ha="center", fontsize=12,
            style="italic", color="0.4")
    save_fig("fig-stft-analysis.png")


def fig_stft_diagram():
    from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
    fig, ax = plt.subplots(figsize=(13, 3.6))
    ax.axis("off")
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 4)

    def box(x, label, color="0.93"):
        ax.add_patch(FancyBboxPatch((x, 1.4), 1.7, 1.2, boxstyle="round,pad=0.03",
                                    fc=color, ec="0.3", lw=1.5))
        ax.text(x + 0.85, 2.0, label, ha="center", va="center", fontsize=12)

    def arrow(x0, x1):
        ax.add_patch(FancyArrowPatch((x0, 2.0), (x1, 2.0), arrowstyle="-|>",
                                     mutation_scale=16, color="0.35", lw=1.6))
    ax.text(0.5, 2.0, r"$x[n]$", ha="center", va="center", fontsize=15, color=BLUE)
    arrow(0.9, 1.4)
    box(1.4, "windowed\nframe $x'_k$")
    arrow(3.1, 3.6)
    box(3.6, "DFT")
    arrow(5.3, 5.8)
    box(5.8, "spectra\n(edit)", color="#e8f0fe")
    arrow(7.5, 8.0)
    box(8.0, "IDFT")
    arrow(9.7, 10.2)
    box(10.2, "overlap\nadd")
    arrow(11.9, 12.4)
    ax.text(12.6, 2.0, r"$\hat{x}[n]$", ha="center", va="center", fontsize=15, color=PURPLE)
    ax.text(4.45, 3.2, "analysis (STFT)", ha="center", fontsize=12, style="italic", color="0.4")
    ax.text(9.05, 3.2, "synthesis (ISTFT)", ha="center", fontsize=12, style="italic", color="0.4")
    save_fig("fig-stft-diagram.png")


def fig_phase_ambiguity():
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    for ax, ang, lab in [(axes[0], np.pi / 4, r"$\angle X[i,\,k] = \pi/4$"),
                         (axes[1], 5 * np.pi / 4, r"$\angle X[i{+}1,\,k] = 5\pi/4$")]:
        ax.add_patch(plt.Circle((0, 0), 1, fill=False, ec="0.4", lw=1.5))
        ax.annotate("", xy=(np.cos(ang), np.sin(ang)), xytext=(0, 0),
                    arrowprops=dict(arrowstyle="-|>", color=BLUE, lw=2.5))
        ax.axhline(0, color="0.8", lw=0.8)
        ax.axvline(0, color="0.8", lw=0.8)
        ax.set_xlim(-1.3, 1.3)
        ax.set_ylim(-1.3, 1.3)
        ax.set_aspect("equal")
        ax.axis("off")
        ax.set_title(lab, fontsize=15)
    fig.suptitle(r"Phase advanced by $\pi$... or $3\pi$, or $5\pi$?  The STFT cannot tell.",
                 fontsize=13, y=0.04)
    save_fig("fig-phase-ambiguity.png")


def gif_nf_sweep(trio):
    from PIL import Image
    frames = []
    for nF in [128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768]:
        fig, ax = plt.subplots(figsize=(8, 3.6), dpi=100)
        spectrogram(ax, trio, nF, max(nF // 4, 64), hann(nF), fmin=60, fmax=8000)
        ax.set_title(f"$N_F = {nF}$ samples  ({nF / F_S * 1000:.0f} ms)", fontsize=14)
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Frequency (Hz)")
        fig.tight_layout()
        fig.canvas.draw()
        img = Image.fromarray(np.asarray(fig.canvas.buffer_rgba())).convert("RGB")
        frames.append(img.resize((img.width // 2, img.height // 2), Image.LANCZOS))
        plt.close(fig)
    frames += [frames[-1]] * 3
    pal = frames[3].convert("P", palette=Image.ADAPTIVE, colors=128)
    fp = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
    fp[0].save(str(ASSETS / "fig-nf-sweep.gif"), save_all=True,
               append_images=fp[1:], duration=900, loop=0)
    print("  wrote fig-nf-sweep.gif")



def main_audio():
    print("Audio:")
    trio = load_trio()
    audio_melody()
    audio_granular(trio)
    audio_time_stretch(trio)
    audio_spectral(trio)
    audio_phase_vocoder(trio)


def main_figures():
    print("Figures:")
    trio = load_trio()
    melody = pq.Audio.from_file(str(ASSETS / "audio-melody.wav"))
    melody = np.asarray(melody.samples).reshape(-1)
    fig_extract_basic()
    fig_cola()
    fig_reconstruction_cases()
    fig_boundary()
    fig_granular_collage(trio)
    fig_granular_randomize()
    fig_time_stretch()
    fig_decoupled()
    fig_stft_melody(melody)
    fig_stft_analysis()
    fig_stft_diagram()
    fig_leakage_windowing()
    fig_spectrogram_window(trio)
    fig_phase_ambiguity()
    print("Animations:")
    gif_frame_extraction()
    gif_nf_sweep(trio)


if __name__ == "__main__":
    main_audio()
    main_figures()
