"""Generate the starter and solution notebooks for Assignment 8, Direction 2
(Bending Time: time-scale modification with pitch preserved, WSOLA or
phase-vocoder route).

Cells are triple-quoted literals for easy manual editing. `md()`/`code()` wrap
them into notebook JSON. Regenerate with `python _gen_notebook_8_2.py`. The
starter `8-2-timescale.ipynb` is committed beside this script; the solution
goes to `.solutions/` (dot-prefixed, so `make split` never mirrors it into the
book repo).
"""

import json
import pathlib

HERE = pathlib.Path(__file__).parent


def make_notebook(cells):
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "version": "3.10.0"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def md(source):
    return {"cell_type": "markdown", "metadata": {}, "source": [source]}


def code(source):
    return {
        "cell_type": "code",
        "metadata": {},
        "source": [source],
        "outputs": [],
        "execution_count": None,
    }


INTRO_MD = md(r"""
# ICMF26 Assignment 8: Bending Time

Build a function that changes the playback speed of a sound while keeping its pitch
unchanged. There are two classic routes: **Route A, WSOLA** (time-domain overlap-add,
easier) and **Route B, the phase vocoder** (STFT based, harder; Flanagan and Golden, Bell
Labs 1966). Implement exactly one. Both build on your Assignment 7 code, and both must pass
the same verification cell below.

First, **follow the installation instructions on the course website** (see "Resources" tab) to install `pyquist` and Jupyter on your local machine. We recommend [using Jupyter through VSCode](https://code.visualstudio.com/docs/datascience/jupyter-notebooks).

**AI Policy**. Unlike the autograded assignments, **you are allowed to use AI tools on this
project**. You must disclose in your `TECHNICAL.md` how you used AI, and you must be able to
explain every line you submit under the oral-quiz policy.

## Submission Instructions

This notebook is a launchpad, not the whole assignment. The full requirements, deliverables
(`TECHNICAL.md`, demo video), and submission instructions live on the project page of the course
site.
""".strip())


SETUP_CODE = code(r'''
# Setup and provided helpers. Run this cell to verify your installation.
import numpy as np
import matplotlib.pyplot as plt
import pyquist as pq

SAMPLE_RATE = 44100  # playback rate for everything we synthesize


def hann_window(size: int) -> np.ndarray:
    """A periodic Hann window of the given size (same as Assignment 7)."""
    return 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(size) / size)


def naive_speed_change(x: np.ndarray, speed: float) -> np.ndarray:
    """Change speed by resampling: read the samples out at a different rate
    (linear interpolation). Duration changes, and pitch goes with it."""
    x = np.asarray(x, dtype=float)
    positions = np.arange(int(len(x) / speed)) * speed
    return np.interp(positions, np.arange(len(x)), x)


def arpeggio() -> np.ndarray:
    """Four notes of A major with soft edges: our test tune for the whole notebook."""
    notes = [(220.00, 0.4), (277.18, 0.4), (329.63, 0.4), (440.00, 0.8)]  # A3, C#4, E4, A4
    out = []
    for freq, dur in notes:
        t = np.arange(int(dur * SAMPLE_RATE)) / SAMPLE_RATE
        envelope = np.minimum(1.0, np.minimum(t / 0.02, (dur - t) / 0.05))
        out.append(0.5 * envelope * np.sin(2 * np.pi * freq * t))
    return np.concatenate(out)


def measure_pitch(x, sample_rate):
    """The frequency (Hz) of the strongest spectral peak, read from a stretch
    of up to one second taken from the middle of x."""
    mid = x[len(x) // 4 : len(x) // 4 + sample_rate]
    spectrum = np.abs(np.fft.rfft(mid * hann_window(len(mid))))
    return np.fft.rfftfreq(len(mid), 1 / sample_rate)[int(np.argmax(spectrum))]


def plot_spectrogram(x, ax, title="", f_max=6000.0):
    """Draw a spectrogram of signal x: time across, frequency up. Returns
    (spec, freqs) so checks can also read the values numerically."""
    spec, freqs, _, _ = ax.specgram(x, NFFT=2048, noverlap=1024,
                                    Fs=SAMPLE_RATE, cmap="magma")
    ax.set_ylim(0, f_max)
    ax.set_xlabel("time (s)")
    ax.set_ylabel("frequency (Hz)")
    ax.set_title(title)
    return spec, freqs
'''.strip())


PROBLEM_MD = md(r"""
## The Problem: Naive Resampling

`naive_speed_change` reads the samples out at a different rate: duration changes, but pitch
moves with it. Listen: at half speed the arpeggio drops an octave, and at double speed it
sounds like the Chipmunks. Both routes below fix this the same way: move through the material
at a new rate while playing each local stretch of sound at its original rate.
""".strip())


PROBLEM_CODE = code(r'''
tune = arpeggio()
print("the tune, as written")
pq.play(pq.Audio(tune, sample_rate=SAMPLE_RATE))
print("naive half speed: twice as long, but an octave down")
pq.play(pq.Audio(naive_speed_change(tune, 0.5), sample_rate=SAMPLE_RATE))
print("naive double speed: half as long, an octave up")
pq.play(pq.Audio(naive_speed_change(tune, 2.0), sample_rate=SAMPLE_RATE))
'''.strip())


ROUTE_A_MD = md(r"""
## Your Task: Two Routes, Choose One

Implement **one** of the two functions below; both must pass the verification cell at the
bottom. Only the top-level signature is fixed: declare any helper functions you like.

### Route A: WSOLA (easier)

Copy short overlapping Hann-windowed **frames** out of the input and overlap-add them at a
fixed output spacing, while the read position steps through the input at the chosen speed;
each frame plays at its native rate, so pitch never moves. Each frame here plays the role of
a grain in Assignment 7's granular synthesis, with the loop inverted: Assignment 7 kept the
*input* hop fixed, this route fixes the *output* spacing. For output frame
$m = 0, 1, 2, \dots$:

1. Compute the read position
   $p = \mathrm{round}(m \cdot \mathrm{hop\_out} \cdot \mathrm{speed})$.
2. **Similarity search:** among candidate frames starting at $p + d$ for
   $d \in [-\mathrm{search}, \mathrm{search}]$ (clamped to stay inside the input), pick the
   $d$ whose windowed first `hop_out` samples best match what is already written at output
   position $m \cdot \mathrm{hop\_out}$ (maximize the dot product; take $d = 0$ for the
   first frame).
3. Multiply that frame by `hann_window(frame)` and add it at $m \cdot \mathrm{hop\_out}$.
4. Stop when the read runs past the end of the input.

With `hop_out = frame // 2` the shifted Hann windows sum to a constant, so no normalization
is needed. Steps 1, 3, and 4 alone are plain overlap-add, and its splices land out of phase:
audible roughness and a measurable detune. Step 2 is what makes it **WSOLA** (waveform
similarity overlap-add, Verhelst and Roelands 1993), the algorithm Chrome runs behind the
YouTube speed slider (production uses 20 ms windows and a 30 ms search). The artifacts that
remain, mainly doubled transients, are worth naming in your writeup.
""".strip())


ROUTE_A_STUB = code(r'''
def wsola_time_scale(x: np.ndarray, speed: float, frame: int = 4096,
                     hop_out: int = 2048, search: int = 512) -> np.ndarray:
    """Time-scale x by 1/speed with waveform-similarity overlap-add (WSOLA).

    For each output frame m, consider frames starting at p + d, where
    p = round(m * hop_out * speed) and d runs over [-search, search]
    (clamped so the frame stays inside x). Pick the d whose windowed first
    hop_out samples best match what is already written at output position
    m * hop_out (d = 0 when nothing is written yet), then apply a Hann
    window and add the frame there. With hop_out = frame // 2 the windows
    sum to a constant, so no normalization is needed.

    Returns a 1-D float array roughly len(x) / speed samples long.
    """
    raise NotImplementedError("Implement me if you chose Route A!")
'''.strip())


ROUTE_B_MD = md(r"""
### Route B: The Phase Vocoder (harder)

Analyze the sound into an STFT with your **own Assignment 7** `stft`, then resynthesize the
same frames at a different spacing with your `istft` (port both from `pq.Audio` and parallel
lists to plain complex arrays). The synthesis hop stays fixed at `hop_out = n_fft // 2`, the
50% overlap where your Assignment 7 `istft` reconstructs exactly; the analysis hop is
`hop_in = round(hop_out * speed)`. At speed 0.5 the frames are analyzed every 512 samples
and played back every 1024, so the sound lasts twice as long. Rubber Band and
`librosa.effects.time_stretch`, the stretchers inside real music tools, are both phase
vocoders.

Frames map one to one and magnitudes pass through unchanged. The work is **phase**: each
frame's phases $\phi[k, m] = \angle X[k, m]$ were measured at a spacing of `hop_in` but play
back at `hop_out`, so every frame must be made phase-continuous with its neighbor at the new
spacing. Three formulas do it, with $H = \mathrm{hop\_in}$:

1. Wrap any angle to $[-\pi, \pi]$:
   $$\mathrm{princarg}(\phi) = \big((\phi + \pi) \bmod 2\pi\big) - \pi$$
2. Bin $k$ (center frequency $\omega_k = 2\pi k / N$) is expected to advance by
   $\omega_k H$ per analysis hop; recover the **true advance** from the measured, wrapped
   difference $\Delta\phi[k, m] = \phi[k, m+1] - \phi[k, m]$:
   $$\Delta\phi_{\mathrm{true}}[k, m] = \mathrm{princarg}\big(\Delta\phi[k, m] - \omega_k H\big) + \omega_k H$$
3. Keep one running phase accumulator per bin, seeded with $\phi[:, 0]$: write each frame
   with the accumulated phases, then step the accumulator by the true advance scaled to the
   new spacing,
   $$\varphi \leftarrow \varphi + \Delta\phi_{\mathrm{true}}[:, m] \cdot \frac{\mathrm{hop\_out}}{\mathrm{hop\_in}}.$$

Never interpolate phases (averaging angles across the circle is the classic vocoder bug;
warble means you did it). Optional upgrade: a synthesis window plus division by the summed
squared window makes `istft` exact at any hop (Assignment 7 Question 8, in code), and
`hop_out = n_fft // 4` then sounds smoother; some roughness at 50% overlap is expected.
""".strip())


ROUTE_B_STUB = code(r'''
def phase_vocoder(x: np.ndarray, speed: float, n_fft: int = 2048,
                  hop_out: int = 1024) -> np.ndarray:
    """Time-scale x by 1/speed with an STFT phase vocoder.

    Analyze x with your Assignment 7 stft at hop_in = round(hop_out * speed),
    then resynthesize the same frames with your Assignment 7 istft at
    hop_out = n_fft // 2, the 50% overlap where it reconstructs exactly.
    Magnitudes pass through unchanged; phases come from a per-bin running
    accumulator seeded with the first frame's phases and stepped by the
    true advance scaled by hop_out / hop_in.

    Returns a 1-D float array roughly len(x) / speed samples long.
    """
    raise NotImplementedError("Implement me if you chose Route B!")
'''.strip())


VERIFY_MD = md(r"""
## Verification

Set `ROUTE` in the cell below to the route you implemented; the same three checks run on
either function:

1. **Duration scales:** at speeds 0.5 and 2.0, output length within 10% of `len(x) / speed`.
2. **Pitch holds:** a 220 Hz tone measures within 1% of 220 Hz at both speeds; on Route A,
   skipping the similarity search detunes past this bar, and the naive control reads 110 Hz.
3. **The sweep survives:** a 200 Hz to 4 kHz chirp at half speed keeps its full sweep; the
   three-panel spectrogram is the heart of your `TECHNICAL.md`.
""".strip())


VERIFY_CODE = code(r'''
ROUTE = "wsola"   # set to "vocoder" if you implemented Route B
time_scale = {"wsola": wsola_time_scale, "vocoder": phase_vocoder}[ROUTE]

# Checks 1 and 2: duration scales, pitch holds. Naive control printed first.
t = np.arange(3 * SAMPLE_RATE) / SAMPLE_RATE
tone = 0.5 * np.sin(2 * np.pi * 220.0 * t)
y_naive = naive_speed_change(tone, 0.5)
print(f"  naive, speed 0.5: {len(y_naive) / len(tone):.2f}x duration, "
      f"measured pitch {measure_pitch(y_naive, SAMPLE_RATE):6.1f} Hz  (the failure mode)")
for speed in (0.5, 2.0):
    y = time_scale(tone, speed)
    ratio = len(y) / len(tone)
    hz = measure_pitch(y, SAMPLE_RATE)
    print(f"  {ROUTE}, speed {speed}: {ratio:.2f}x duration, measured pitch {hz:6.1f} Hz")
    assert abs(ratio * speed - 1.0) < 0.10, (
        f"at speed {speed} the duration should scale to ~{1 / speed:.2f}x, got {ratio:.2f}x")
    assert abs(hz - 220.0) < 0.01 * 220.0, (
        f"pitch moved to {hz:.1f} Hz; time scaling must not move pitch "
        "(tolerance 1%; on Route A the similarity search is what removes the detune)")

# Check 3: the chirp, 3 seconds rising 200 Hz to 4 kHz.
T_CHIRP = 3.0
t = np.arange(int(T_CHIRP * SAMPLE_RATE)) / SAMPLE_RATE
chirp = 0.5 * np.sin(2 * np.pi * (200.0 * t + (4000.0 - 200.0) / (2 * T_CHIRP) * t ** 2))

fig, axes = plt.subplots(3, 1, figsize=(10, 8))
spec_o, freqs = plot_spectrogram(chirp, axes[0], "original chirp: 200 Hz to 4 kHz in 3 s")
spec_n, _ = plot_spectrogram(naive_speed_change(chirp, 0.5), axes[1],
                             "naive half speed: twice as long, sweep tops out at 2 kHz")
spec_y, _ = plot_spectrogram(time_scale(chirp, 0.5), axes[2],
                             "your half speed: twice as long, sweep intact")
plt.tight_layout()
plt.show()

# The same evidence in numbers: at matching musical moments, your peak must sit
# on the original's, while the naive version's sits an octave low.
hop_cols = 1024  # spectrogram column spacing in samples (NFFT=2048, noverlap=1024)
for t_src in (0.8, 1.5, 2.2):
    c = int(t_src * SAMPLE_RATE / hop_cols)
    b_orig = int(np.argmax(spec_o[:, c]))
    b_yours = int(np.argmax(spec_y[:, 2 * c]))
    b_naive = int(np.argmax(spec_n[:, 2 * c]))
    print(f"  t = {t_src:.1f} s: original peak {freqs[b_orig]:6.0f} Hz, "
          f"yours {freqs[b_yours]:6.0f} Hz, naive {freqs[b_naive]:6.0f} Hz")
    assert abs(b_yours - b_orig) <= 10, (
        "the stretched sweep drifted; the output should hold the original's frequencies")
print("Verified: duration scales, pitch holds, the sweep survives.")
'''.strip())


LISTEN_CODE = code(r'''
# Listening tests: the arpeggio, then real material. Real recordings are where
# the artifacts live; name what you hear in your writeup.
print("the tune, then naive half speed, then yours")
pq.play(pq.Audio(tune, sample_rate=SAMPLE_RATE))
pq.play(pq.Audio(naive_speed_change(tune, 0.5), sample_rate=SAMPLE_RATE))
pq.play(pq.Audio(time_scale(tune, 0.5), sample_rate=SAMPLE_RATE))

# Real material: swap in your own FreeSound ID (your API key from Assignment 7
# works here), or load a file of your own with pq.Audio.from_file.
from pyquist.web.freesound import fetch_freesound
clip, _ = fetch_freesound(42981)  # <-- replace with YOUR sound ID
x = clip.as_mono().samples[:, 0]
print("a real recording at 0.75x")
pq.play(pq.Audio(time_scale(x, 0.75), sample_rate=clip.sample_rate))
'''.strip())


EXPLORE_MD = md(r"""
## Explore

You built a general instrument for changing musical time. This part is open: explore, and
show us what you find in your `TECHNICAL.md` and demo video. Some directions:

- **Play it on everything** (`pq.Audio.from_file`, mix to mono) and name the artifacts:
  transient smearing or doubling, phasiness.
- **Read the production code:**
  [Chromium's WSOLA](https://chromium.googlesource.com/chromium/src/+/main/media/filters/audio_renderer_algorithm.cc)
  (the code behind Chrome's speed slider) uses 20 ms windows and a 30 ms search; compare its
  choices to yours. Firefox ships SoundTouch, the same family. For both routes side by side,
  read [Driedger and Müller's review of time-scale modification](https://www.mdpi.com/2076-3417/6/2/57).
- **Route B upgrade:** identity phase locking (Laroche and Dolson 1999): let the spectral
  peaks run the accumulator and lock each neighbor to its peak.
- **Pitch shifting:** chain your function with `naive_speed_change` to move pitch without
  moving time ($2^{n/12}$ is involved).
- **Extremes:** freeze by repeating one analysis frame forever, vary `hop_in` over time
  (tape stop, ritardando), or try `speed = 0.05` (Paulstretch territory).

Implementing the second route and comparing by ear is a strong extension. Check your work
against the requirements on the project page.
""".strip())


EXPLORE_CODE = code(r'''
# Your exploration starts here.
'''.strip())


SOLUTION_NOTE = md(r"""
**Instructor solution. Do not distribute.** Both routes are implemented; the
verification cell runs Route A by default, set `ROUTE = "vocoder"` for Route B.
""".strip())


ROUTE_A_SOLUTION = code(r'''
def wsola_time_scale(x: np.ndarray, speed: float, frame: int = 4096,
                     hop_out: int = 2048, search: int = 512) -> np.ndarray:
    """Waveform-similarity overlap-add (instructor solution)."""
    x = np.asarray(x, dtype=float)
    w = hann_window(frame)
    out = np.zeros(int(len(x) / speed) + frame)
    m = 0
    end = 0
    while True:
        p = int(round(m * hop_out * speed))
        if p + frame > len(x):
            break
        d = 0
        lo, hi = max(-search, -p), min(search, len(x) - frame - p)
        if m > 0 and hi > lo:
            # score(d) = dot(what is already written, windowed candidate start)
            region = out[m * hop_out : m * hop_out + hop_out] * w[:hop_out]
            scores = np.correlate(x[p + lo : p + hi + hop_out], region, "valid")
            d = lo + int(np.argmax(scores))
        out[m * hop_out : m * hop_out + frame] += x[p + d : p + d + frame] * w
        end = m * hop_out + frame
        m += 1
    return out[:end]
'''.strip())


ROUTE_B_SOLUTION = code(r'''
def _stft(x, n_fft, hop, window):
    n_frames = 1 + (len(x) - n_fft) // hop
    return np.stack([np.fft.rfft(x[m * hop : m * hop + n_fft] * window)
                     for m in range(n_frames)], axis=1)


def _istft(X, n_fft, hop, window):
    # plain overlap-add, exact at 50% overlap where Hann windows sum to 1
    n_frames = X.shape[1]
    y = np.zeros((n_frames - 1) * hop + n_fft)
    for m in range(n_frames):
        y[m * hop : m * hop + n_fft] += np.fft.irfft(X[:, m])
    return y


def _princarg(phi):
    return ((phi + np.pi) % (2 * np.pi)) - np.pi


def phase_vocoder(x: np.ndarray, speed: float, n_fft: int = 2048,
                  hop_out: int = 1024) -> np.ndarray:
    """Hop-based phase vocoder (instructor solution)."""
    hop_in = max(1, int(round(hop_out * speed)))
    w = hann_window(n_fft)
    X = _stft(np.asarray(x, dtype=float), n_fft, hop_in, w)
    n_bins, n_frames = X.shape
    omega = 2 * np.pi * np.arange(n_bins) / n_fft
    phases = np.angle(X)
    adv = _princarg(np.diff(phases, axis=1) - omega[:, None] * hop_in) \
        + omega[:, None] * hop_in
    scale = hop_out / hop_in
    Y = np.zeros_like(X)
    acc = phases[:, 0].copy()
    for m in range(n_frames):
        Y[:, m] = np.abs(X[:, m]) * np.exp(1j * acc)
        acc += adv[:, min(m, n_frames - 2)] * scale
    return _istft(Y, n_fft, hop_out, w)
'''.strip())


def build_cells(route_a, route_b, note=None):
    cells = [
        INTRO_MD,
        SETUP_CODE,
        PROBLEM_MD,
        PROBLEM_CODE,
        ROUTE_A_MD,
        route_a,
        ROUTE_B_MD,
        route_b,
        VERIFY_MD,
        VERIFY_CODE,
        LISTEN_CODE,
        EXPLORE_MD,
        EXPLORE_CODE,
    ]
    if note is not None:
        cells.insert(0, note)
    return cells


path = HERE / "8-2-timescale.ipynb"
with open(path, "w") as f:
    json.dump(make_notebook(build_cells(ROUTE_A_STUB, ROUTE_B_STUB)), f, indent=1)
print(f"Written: {path}")

sol_dir = HERE / ".solutions"
sol_dir.mkdir(exist_ok=True)
sol_path = sol_dir / "8-2-timescale-solution.ipynb"
with open(sol_path, "w") as f:
    json.dump(make_notebook(build_cells(ROUTE_A_SOLUTION, ROUTE_B_SOLUTION,
                                        SOLUTION_NOTE)), f, indent=1)
print(f"Written: {sol_path}")
