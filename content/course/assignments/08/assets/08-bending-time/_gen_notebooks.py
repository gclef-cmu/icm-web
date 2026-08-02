"""Generate the starter notebook for Assignment 8 (Bending Time:
time-stretching without pitch-shifting via the phase vocoder).

Cells are triple-quoted literals for easy manual editing. Markdown and code
cells both use raw triple-quoted strings; `md()`/`code()` wrap them into the
notebook JSON. Regenerate with `python _gen_notebooks.py`.
"""

import json
import pathlib
import zipfile

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

In 1958, Ross Bagdasarian sang into a tape recorder running at half speed, played the tape
back at full speed, and [sold millions of records](https://en.wikipedia.org/wiki/The_Chipmunk_Song_%28Christmas_Don%27t_Be_Late%29)
as Alvin and the Chipmunks. That was the state of the art for changing the speed of audio:
time and pitch were handcuffed together, and every tape deck, turntable, and sampler paid the
same price. Slow a sound down and it sags an octave; speed it up and it squeaks. The tool that
finally broke the handcuffs is the **phase vocoder**, invented at Bell Labs in 1966 (James
Flanagan and Roger Golden, *"Phase Vocoder,"* Bell System Technical Journal) and explained to
a generation of computer musicians by Mark Dolson's classic *"The Phase Vocoder: A Tutorial"*
(Computer Music Journal, 1986). Today one hides behind your podcast app's speed slider,
YouTube's playback menu, Ableton Live's warp engine, and half of the "slowed + reverb" remixes
on the internet.

In this project, you will build the real thing, small: a complete time-bending engine in five
functions. Assignment 7 left you with most of the parts: frames, windows, an STFT and its
inverse. Here you will rebuild that machinery a little sturdier, then add the one ingredient
Assignment 7 never touched: **phase**. Do not worry if phase still feels slippery; each idea
is introduced right where you need it, and every formula you must implement is written out in
full. This notebook defines the structure and the minimum requirement: four tasks, each with a
checkpoint that tells you whether it works, followed by a provided verification and a final
task that is yours to take wherever you like. The project is open-ended and is meant to be
more difficult than the autograded assignments; where you take it beyond the minimum is up to
you.

First, **follow the installation instructions on the course website** (see "Resources" tab) to install `pyquist` and Jupyter on your local machine. We recommend [using Jupyter through VSCode](https://code.visualstudio.com/docs/datascience/jupyter-notebooks).

**AI Policy**. Unlike the autograded assignments, **you are allowed to use AI tools on this
project**. You must disclose in your `TECHNICAL.md` how you used AI, and you must be able to
explain every line you submit under the oral-quiz policy.

## Submission Instructions

This notebook is a launchpad, not the whole assignment. The full requirements, deliverables
(`TECHNICAL.md`, demo video), and submission instructions live on the project page of the course
site.
""".strip())


SETUP_MD = md(r"""
## Setup

Run the cell below to verify your installation. The `hann_window` helper is the same one
Assignment 7 gave you, and the vocoder's home settings live here too: 2048-sample frames
(about 46 ms) hopped every 512 samples, which is 75% overlap.
""".strip())


SETUP_CODE = code(r'''
import numpy as np
import matplotlib.pyplot as plt
import pyquist as pq

SAMPLE_RATE = 44100   # playback rate for everything we synthesize
N_FFT = 2048          # frame length: about 46 ms of sound
HOP = 512             # analysis hop: 75% overlap, the phase vocoder's home base


def hann_window(size: int) -> np.ndarray:
    """A periodic Hann window of the given size (provided for you)."""
    return 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(size) / size)


WINDOW = hann_window(N_FFT)
'''.strip())


PROBLEM_MD = md(r"""
## The Handcuffs

A recording is one long list of samples, and playback reads them out at a fixed rate. If you
want the sound to take less time, the obvious move is the tape deck's move: read the samples
out faster. `naive_speed_change` below does that in code (resampling by linear interpolation),
and on duration it truly works. Listen to what it costs. The test tune is a four-note
arpeggio; at half speed it sags an octave into the mud, and at double speed it is pure
chipmunk.

The failure is baked into the representation. A list of samples never mentions pitch, so there
is no way to grab hold of pitch and tell it to stay put while time moves. Step one of the fix,
then, is a representation where pitch is written down explicitly. You already know one.
""".strip())


PROBLEM_CODE = code(r'''
def naive_speed_change(x: np.ndarray, speed: float) -> np.ndarray:
    """Change speed the tape-deck way: read the samples out at a different rate
    (resampling by linear interpolation). Duration changes, and pitch goes with it."""
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


tune = arpeggio()
print("the tune, as written")
pq.play(pq.Audio(tune, sample_rate=SAMPLE_RATE))
print("half speed: twice as long, but an octave down in the mud")
pq.play(pq.Audio(naive_speed_change(tune, 0.5), sample_rate=SAMPLE_RATE))
print("double speed: half as long, pure chipmunk")
pq.play(pq.Audio(naive_speed_change(tune, 2.0), sample_rate=SAMPLE_RATE))
'''.strip())


TASK1_MD = md(r"""
## Task 1: Cut the Film (`stft`)

The fix begins with a change of representation. The **Short-Time Fourier Transform** slices
the signal into overlapping frames, applies a window, and takes the FFT of each frame:

$$X[k, m] \;=\; \sum_{n=0}^{N-1} x[n + mH]\; w[n]\; e^{-j 2\pi k n / N}$$

where $N$ is the frame length `n_fft`, $H$ is the hop `hop`, $w$ is the analysis window, $m$
numbers the frames, and $k$ numbers the frequency bins. Think of the result as a **film strip
of sound**: each column $X[:, m]$ is one still photograph of the spectrum, taken every $H$
samples. Where a list of samples never mentions pitch, this representation puts it front and
center, one row per frequency. Flip through the frames at a different rate and duration
changes; leave the rows alone and pitch stays put. That is the whole plan, and the rest of the
notebook is making it actually work.

You built an STFT in Assignment 7 as parallel lists of magnitudes and phases. Build it again,
sturdier: one complex 2D array of shape `(n_bins, n_frames)`, because the vocoder will need to
index time freely and do arithmetic on whole rows at once. As before, the input is real audio,
so keep only the non-redundant half of the spectrum (`np.fft.rfft`, giving
`n_bins = n_fft // 2 + 1`; recall Hermitian symmetry). Take only complete frames and drop the
tail, so the frame count is exactly the formula you derived in Assignment 7, Question 1:
$\;M = 1 + \lfloor (\mathrm{len}(x) - N) / H \rfloor$.

**Requirements:** `np.fft.rfft` and `np.fft.irfft` are the only Fourier calls in this
notebook, and the STFT/ISTFT pair must be your own. `librosa.stft` and `scipy.signal` defeat
the point, which is to own every seam of this machine.
""".strip())


TASK1_STARTER = code(r'''
def stft(x: np.ndarray, n_fft: int, hop: int, window: np.ndarray) -> np.ndarray:
    """Short-time Fourier transform of a mono signal.

    Args:
        x: the input signal, a 1-D float array of samples.
        n_fft: frame length N in samples.
        hop: hop H in samples.
        window: the length-n_fft analysis window (use hann_window(n_fft)).

    Returns:
        X: complex array of shape (n_fft // 2 + 1, n_frames) with columns in
            time order, where n_frames = 1 + (len(x) - n_fft) // hop. Only
            complete frames; drop the tail and do not zero-pad.
    """
    raise NotImplementedError("Implement me!")
'''.strip())


BENCH_MD = md(r"""
### The light table (provided)

Film gets inspected on a light table. Ours has two instruments: `plot_spectrogram` draws the
magnitude of an STFT matrix in decibels, time running left to right and frequency bottom to
top, and `measure_pitch` is a tuner that reads the strongest frequency out of the middle of a
signal. Both get heavy use before the notebook is done.
""".strip())


BENCH_CODE = code(r'''
def db(X):
    """Magnitude in decibels."""
    return 20 * np.log10(np.maximum(np.abs(X), 1e-12))


def plot_spectrogram(X, hop, sample_rate, ax, title="", f_max=6000.0):
    """Draw the magnitude of an STFT matrix X: time across, frequency up."""
    mag = db(X)
    extent = [0, X.shape[1] * hop / sample_rate, 0, sample_rate / 2]
    ax.imshow(mag, origin="lower", aspect="auto", extent=extent,
              cmap="magma", vmin=mag.max() - 70, vmax=mag.max())
    ax.set_ylim(0, f_max)
    ax.set_xlabel("time (s)")
    ax.set_ylabel("frequency (Hz)")
    ax.set_title(title)


def measure_pitch(x, sample_rate):
    """The frequency (Hz) of the strongest spectral peak, read from a stretch
    of up to one second taken from the middle of x."""
    mid = x[len(x) // 4 : len(x) // 4 + sample_rate]
    spectrum = np.abs(np.fft.rfft(mid * hann_window(len(mid))))
    return np.fft.rfftfreq(len(mid), 1 / sample_rate)[int(np.argmax(spectrum))]
'''.strip())


TASK1_CHECK_MD = md(r"""
### Checkpoint

Two facts to verify: the shape must match the Assignment 7 frame-count formula, and a pure
440 Hz sine must put its energy in the row nearest 440 Hz. Then the light table: a chirp
gliding from 200 Hz to 4 kHz should photograph as one clean rising stripe. Keep the chirp
around; it comes back for the final verification.
""".strip())


TASK1_CHECK_CODE = code(r'''
# A 1 s, 440 Hz sine must land its energy in the right row.
t = np.arange(SAMPLE_RATE) / SAMPLE_RATE
sine = 0.5 * np.sin(2 * np.pi * 440.0 * t)
X_sine = stft(sine, N_FFT, HOP, WINDOW)

expected_shape = (N_FFT // 2 + 1, 1 + (len(sine) - N_FFT) // HOP)
assert X_sine.shape == expected_shape, (
    f"expected shape {expected_shape}, got {X_sine.shape}; "
    "complete frames only, drop the tail")
assert np.iscomplexobj(X_sine), "X must stay complex; keep rfft's output as is"

peak_bin = int(np.argmax(np.abs(X_sine[:, X_sine.shape[1] // 2])))
expected_bin = round(440.0 * N_FFT / SAMPLE_RATE)
assert peak_bin == expected_bin, (
    f"440 Hz should peak in bin {expected_bin}, got bin {peak_bin}")
print(f"  shape {X_sine.shape}, 440 Hz lands in bin {peak_bin}: the analyzer sees straight")

# The film strip itself: 3 seconds gliding from 200 Hz up to 4 kHz.
T_CHIRP = 3.0
t = np.arange(int(T_CHIRP * SAMPLE_RATE)) / SAMPLE_RATE
chirp = 0.5 * np.sin(2 * np.pi * (200.0 * t + (4000.0 - 200.0) / (2 * T_CHIRP) * t ** 2))

fig, ax = plt.subplots(figsize=(10, 3))
plot_spectrogram(stft(chirp, N_FFT, HOP, WINDOW), HOP, SAMPLE_RATE, ax,
                 "Your STFT of a 200 Hz to 4 kHz chirp: one clean rising stripe")
plt.show()
'''.strip())


TASK2_MD = md(r"""
## Task 2: Splice It Back (`istft`)

An analyzer alone is not an instrument; whatever we do to the film strip has to become sound
again. Synthesis retraces the analysis steps:

1. Inverse FFT each column back into a time-domain frame:
   $\hat{x}_m[n] = \mathrm{irfft}(X[:, m])$
2. Window the frame *again*: $\tilde{x}_m[n] = \hat{x}_m[n]\, w[n]$
3. **Overlap-add** each windowed frame into the output at its hop position:
   $y[n + mH] \leftarrow y[n + mH] + \tilde{x}_m[n]$
4. Overlapping windows pile up, so keep a running total of the squared window in a second
   buffer, $W[n + mH] \leftarrow W[n + mH] + w[n]^2$, and normalize at the end with a
   **floored** denominator: $y[n] \leftarrow y[n] \,/\, \max(W[n],\, 0.1)$. In the interior
   the pile-up sits far above the floor (about 1.5 at 75% overlap), so this is plain division
   and reconstruction is exact. At the outer edges the pile-up trails off toward zero, and
   honest division there would boost near-silence by factors in the thousands; the floor caps
   the boost, so the edges keep the window's natural fade instead of erupting. That eruption
   is invisible right now and detonates only when Task 4 starts synthesizing phases, so take
   the floor seriously today.

For $M$ frames the output has $(M - 1)\,H + N$ samples; you worked that length out in
Assignment 7 as well.

Two things are new since Assignment 7. First, your Assignment 7 inverse only worked at exactly
50% overlap, where Hann windows happen to sum to one; Question 8 asked what breaks at any
other hop, and step 4 is the answer, in code. Second, the window goes on *twice*, once at
analysis and once here. Right now that looks pointless. But Task 4 is going to perform surgery
on the phases, and afterward the frames no longer agree with their neighbors at the edges; the
synthesis window fades every splice smoothly to zero, and the normalization pays the loudness
back.

**Requirements:** your `istft` must reconstruct correctly at **any** hop $H \le N$, not just
75% overlap. The checkpoint holds you to it.
""".strip())


TASK2_STARTER = code(r'''
def istft(X: np.ndarray, n_fft: int, hop: int, window: np.ndarray) -> np.ndarray:
    """Inverse STFT by windowed overlap-add with window-sum normalization.

    Args:
        X: complex STFT matrix of shape (n_fft // 2 + 1, n_frames).
        n_fft, hop: the frame length and hop the matrix was built with.
        window: the same length-n_fft window used for analysis.

    Returns:
        y: a 1-D float array of length (n_frames - 1) * hop + n_fft.
    """
    raise NotImplementedError("Implement me!")
'''.strip())


TASK2_CHECK_MD = md(r"""
### Checkpoint

A round trip through your pair must hand back what it was given: `istft(stft(x))` equals `x`
in the interior (the first and last frame's worth of samples taper, so we trim them before
comparing). The trip runs twice: once at the home hop of 512, and once at a hop of 300, which
divides into nothing and sums to no tidy constant. Only honest window-sum normalization
survives the second one.
""".strip())


TASK2_CHECK_CODE = code(r'''
for test_hop in (HOP, 300):
    X_trip = stft(tune, N_FFT, test_hop, WINDOW)
    y_trip = istft(X_trip, N_FFT, test_hop, WINDOW)
    interior = slice(N_FFT, len(y_trip) - N_FFT)
    error = np.max(np.abs(y_trip[interior] - tune[:len(y_trip)][interior]))
    print(f"  hop {test_hop:4d}: round-trip error {error:.2e}")
    assert error < 1e-6, (
        f"round trip at hop {test_hop} does not reconstruct; check your normalization")
print("In one ear and out the other, unchanged, at any overlap. The splicer works.")
'''.strip())


TASK3_MD = md(r"""
## Task 3: The Continuity Department (`princarg`, `true_phase_advance`)

Every STFT value is a complex number, and its polar form splits the job in two:

$$X[k, m] = |X[k, m]|\; e^{\,j \phi[k, m]}$$

The magnitude $|X|$ says *how much* of frequency bin $k$ is present in frame $m$: it is what
the photograph shows. The phase $\phi = \angle X[k, m]$ says *where in its cycle* that
oscillation was at the moment the frame was shot. In film terms, phase is the continuity
department: the bookkeeping that makes consecutive frames line up so the cut is invisible.
Assignment 7 let you carry phase around without ever touching it. That ends now.

Phase comes with one nuisance: it is circular. `np.angle` reports values in $[-\pi, \pi]$, and
angles that differ by a whole turn of $2\pi$ are the same angle. Your first tool wraps any
angle back onto that interval:

$$\mathrm{princarg}(\phi) = \big((\phi + \pi) \bmod 2\pi\big) - \pi$$

Your second tool measures how much phase *actually* advances from one frame to the next. Bin
$k$'s center frequency is $\omega_k = 2\pi k / N$ radians per sample, so a sinusoid sitting
exactly on the bin would advance by

$$\mathrm{expected}_k = \omega_k H$$

between frames. The *measured* difference $\Delta\phi[k, m] = \phi[k, m+1] - \phi[k, m]$ has
been wrapped, possibly many whole turns ago, so it cannot be trusted as is. But real sounds
sit *near* bin centers, not on them, so the truth differs from the expectation by only a small
deviation. Recover it by wrapping just the deviation:

$$\Delta\phi_{\mathrm{true}}[k, m] = \mathrm{princarg}\big(\Delta\phi[k, m] - \omega_k H\big) + \omega_k H$$

Implement both functions. They are short; the checkpoint is where they earn their keep.
""".strip())


TASK3_STARTER = code(r'''
def princarg(phi: np.ndarray) -> np.ndarray:
    """Wrap angles (radians) to the interval [-pi, pi]."""
    raise NotImplementedError("Implement me!")


def true_phase_advance(phase: np.ndarray, n_fft: int, hop: int) -> np.ndarray:
    """The unwrapped per-hop phase advance for every bin and frame pair.

    Args:
        phase: (n_bins, n_frames) array of STFT phases, i.e. np.angle(X).
        n_fft, hop: the analysis parameters the phases came from.

    Returns:
        advance: (n_bins, n_frames - 1) array where advance[k, m] is the
            corrected phase advance from frame m to frame m + 1 in bin k.
    """
    raise NotImplementedError("Implement me!")
'''.strip())


TASK3_CHECK_MD = md(r"""
### Checkpoint

`princarg` must leave in-range angles alone and strip whole turns from everything else. Then
the payoff, and it is the insight the entire algorithm turns on. Your bins are spaced
$44100 / 2048 \approx 21.5$ Hz apart, so from magnitude alone the frequency of a sine is only
known to the nearest bin. But convert your corrected advance back to hertz,

$$f = \Delta\phi_{\mathrm{true}} \cdot \frac{f_s}{2\pi H},$$

and the checkpoint recovers a 225.5 Hz sine to a fraction of a hertz, from a spectrum whose
nearest bins sit at 215.3 and 236.9. Magnitude can only guess to the nearest bin; phase knows
the true frequency. That knowledge is exactly what Task 4 spends.
""".strip())


TASK3_CHECK_CODE = code(r'''
rng = np.random.default_rng(0)
angles = rng.uniform(-np.pi, np.pi, size=1000)
turns = rng.integers(-5, 6, size=1000) * 2 * np.pi
assert np.allclose(princarg(angles), angles, atol=1e-9), (
    "angles already in [-pi, pi] must pass through untouched")
assert np.allclose(princarg(angles + turns), angles, atol=1e-6), (
    "whole turns of 2 pi must be stripped away")
assert np.all(np.abs(princarg(rng.uniform(-50, 50, size=1000))) <= np.pi + 1e-9)
print("  princarg keeps every angle on the circle")

# The payoff: read a sine's TRUE frequency from phase alone.
f_true = 225.5   # deliberately between bin 10 (215.3 Hz) and bin 11 (236.9 Hz)
t = np.arange(SAMPLE_RATE) / SAMPLE_RATE
sine = np.sin(2 * np.pi * f_true * t)
X_sine = stft(sine, N_FFT, HOP, WINDOW)
advance = true_phase_advance(np.angle(X_sine), N_FFT, HOP)
assert advance.shape == (X_sine.shape[0], X_sine.shape[1] - 1), (
    f"expected shape {(X_sine.shape[0], X_sine.shape[1] - 1)}, got {advance.shape}")

k_peak = int(np.argmax(np.abs(X_sine[:, X_sine.shape[1] // 2])))
f_estimated = advance[k_peak, advance.shape[1] // 2] * SAMPLE_RATE / (2 * np.pi * HOP)
bin_hz = SAMPLE_RATE / N_FFT
print(f"  bins are {bin_hz:.1f} Hz apart; the peak is bin {k_peak}, centered at {k_peak * bin_hz:.1f} Hz")
print(f"  the phase advance says the true frequency is {f_estimated:.2f} Hz (actual: {f_true} Hz)")
assert abs(f_estimated - f_true) < 0.5, (
    "the advance should recover the true frequency; check the wrap-and-restore")
print("  phase knows what magnitude can only guess")
'''.strip())


TASK4_MD = md(r"""
## Task 4: Reshoot at a New Frame Rate (`pv_time_scale`)

Everything is on the bench: film strip in, film strip out, and the continuity department.
Time to bend.

**The plan.** To play at `speed` $s$, build a new strip with
$M_{\mathrm{out}} = \lceil M_{\mathrm{in}} / s \rceil$ frames, where output frame $m$ reads
from the fractional source position $p = m \cdot s$. At $s = 0.5$, output frames
$0, 1, 2, 3, \dots$ read source positions $0, 0.5, 1, 1.5, \dots$: the same photographs,
flipped through at half the rate.

**Magnitudes interpolate.** The position $p$ falls between source frames
$i = \lfloor p \rfloor$ and $i + 1$, so blend the two photographs linearly, with
$\mathrm{frac} = p - i$:

$$|Y[:, m]| = (1 - \mathrm{frac}) \cdot |X[:, i]| \;+\; \mathrm{frac} \cdot |X[:, i + 1]|$$

(Clamp $i$ so you never index past the last available pair.)

**Phases accumulate.** Here is the one place the vocoder demands real care. Output frame $m$
must be continuous with output frame $m - 1$, its *new* neighbor, not with whatever its source
frame's old neighbors were. And continuity across one hop is exactly what Task 3 measures: a
sinusoid's phase must advance by its true per-hop advance. So keep a **running phase**
$\varphi[k]$, one accumulator per bin. Start it at the source's opening phase $\phi[:, 0]$,
write each output column as

$$Y[:, m] = |Y[:, m]| \; e^{\,j \varphi},$$

then step the accumulator by the true advance measured at the source position you just read:
$\varphi \leftarrow \varphi + \Delta\phi_{\mathrm{true}}[:, i]$. Pitch never moves, because
every bin still advances at its own true frequency per hop; there are simply more hops (or
fewer) than the original had.

Do **not** interpolate phases the way you interpolated magnitudes: averaging two angles on
opposite sides of the circle produces garbage, and that bug is the classic way phase vocoders
die. If your output warbles, look here first.

This task is deliberately looser than the previous ones. Several choices are defensible (step
the accumulator before or after writing the first frame, interpolate the advance or take the
left neighbor's, how to treat the tail), and any bookkeeping that passes the checkpoint and
the Proof is correct. If the result sounds clean but faintly "underwater" on real recordings,
that is the textbook vocoder's signature, not a bug; Task 6 has more to say about it.
""".strip())


TASK4_STARTER = code(r'''
def pv_time_scale(X: np.ndarray, speed: float, n_fft: int, hop: int) -> np.ndarray:
    """Time-scale an STFT matrix: new duration, same pitch.

    Args:
        X: complex STFT matrix (n_bins, n_frames).
        speed: rate multiplier; 2.0 plays twice as fast (half the frames),
            0.5 plays at half speed (twice the frames).
        n_fft, hop: the analysis parameters X was built with.

    Returns:
        Y: complex STFT matrix of shape (n_bins, ceil(n_frames / speed)),
            ready for istft. If X has fewer than two frames, return a copy.
    """
    raise NotImplementedError("Implement me!")
'''.strip())


TASK4_CHECK_MD = md(r"""
### Checkpoint

The full chain on a pure tone: 220 Hz through `stft`, your time-bender at half and double
speed, then `istft`. The frame count and duration must scale; the tuner must keep reading
220 Hz. This is precisely the test the naive resampler failed in the opening section.

The checkpoint also insists the output stay at sane amplitude. With synthetic phases, frames
no longer taper at their edges, and an unfloored version of the Task 2 normalization (dividing
everywhere, or guarding with only a tiny epsilon) detonates a spectacular click at the very
last samples. If the amplitude assert fires, revisit the floor in step 4 of Task 2.
""".strip())


TASK4_CHECK_CODE = code(r'''
t = np.arange(2 * SAMPLE_RATE) / SAMPLE_RATE
tone = 0.5 * np.sin(2 * np.pi * 220.0 * t)
X_tone = stft(tone, N_FFT, HOP, WINDOW)

for speed in (0.5, 2.0):
    Y = pv_time_scale(X_tone, speed, N_FFT, HOP)
    expected_frames = int(np.ceil(X_tone.shape[1] / speed))
    assert Y.shape == (X_tone.shape[0], expected_frames), (
        f"at speed {speed}, expected {expected_frames} output frames, got {Y.shape[1]}")
    y = istft(Y, N_FFT, HOP, WINDOW)
    peak_hz = measure_pitch(y, SAMPLE_RATE)
    print(f"  speed {speed}: {len(y) / len(tone):.2f}x duration, tuner reads {peak_hz:.1f} Hz")
    assert abs(peak_hz - 220.0) < 3.0, (
        f"pitch moved to {peak_hz:.1f} Hz; check your phase accumulator")
    assert np.max(np.abs(y)) < 2.0, (
        f"output peaks at {np.max(np.abs(y)):.1f} for a 0.5-amplitude input; if the spike "
        "sits at the very edge, revisit the normalization floor in Task 2, step 4")
print("Half speed, double speed, same 220 Hz. The handcuffs are off.")
'''.strip())


TASK5_MD = md(r"""
## Task 5: The Proof

The provided cell below bolts your five functions together into the finished instrument,
`phase_vocoder`, and puts it on trial twice. First the tone test: a 220 Hz tone slowed and
sped, with the naive resampler from the opening as the control group; duration has to move,
pitch has to hold, and the naive row shows what failure looks like so that passing means
something. Then the film test: the Task 1 chirp, slowed both ways, side by side on the light
table. The naive strip is twice as long but sweeps only half as high; yours is twice as long
with the sweep intact. This figure is the heart of your `TECHNICAL.md`.
""".strip())


TASK5_CODE = code(r'''
def phase_vocoder(x: np.ndarray, speed: float,
                  n_fft: int = 2048, hop: int | None = None) -> np.ndarray:
    """The finished instrument: analyze, bend time, resynthesize.

    Note that no sample rate appears anywhere: the vocoder moves frames, not
    seconds. Play the result at the same rate as the input.
    """
    if hop is None:
        hop = n_fft // 4
    window = hann_window(n_fft)
    X = stft(x, n_fft, hop, window)
    Y = pv_time_scale(X, speed, n_fft, hop)
    return istft(Y, n_fft, hop, window)


# Trial 1: the tone test, with the naive resampler as the control group.
t = np.arange(2 * SAMPLE_RATE) / SAMPLE_RATE
tone = 0.5 * np.sin(2 * np.pi * 220.0 * t)
trials = [
    ("naive, half speed  ", naive_speed_change(tone, 0.5), 2.0, 110.0),
    ("vocoder, half speed", phase_vocoder(tone, 0.5),      2.0, 220.0),
    ("vocoder, 2x speed  ", phase_vocoder(tone, 2.0),      0.5, 220.0),
]
for label, y, want_ratio, want_hz in trials:
    ratio = len(y) / len(tone)
    hz = measure_pitch(y, SAMPLE_RATE)
    print(f"  {label}: {ratio:.2f}x duration, tuner reads {hz:6.1f} Hz")
    assert abs(ratio - want_ratio) / want_ratio < 0.03, (
        f"{label.strip()}: duration should scale to ~{want_ratio}x, got {ratio:.2f}x")
    assert abs(hz - want_hz) < 3.0, (
        f"{label.strip()}: expected a peak near {want_hz} Hz, got {hz:.1f} Hz")
print("  the naive resampler drops the octave; the vocoder does not\n")

# Trial 2: the film test. The Task 1 chirp, slowed both ways.
X_orig = stft(chirp, N_FFT, HOP, WINDOW)
X_naive = stft(naive_speed_change(chirp, 0.5), N_FFT, HOP, WINDOW)
X_pv = stft(phase_vocoder(chirp, 0.5), N_FFT, HOP, WINDOW)

fig, axes = plt.subplots(3, 1, figsize=(10, 8))
plot_spectrogram(X_orig, HOP, SAMPLE_RATE, axes[0],
                 "original chirp: 200 Hz to 4 kHz in 3 s")
plot_spectrogram(X_naive, HOP, SAMPLE_RATE, axes[1],
                 "naive half speed: twice as long, but the sweep tops out at 2 kHz")
plot_spectrogram(X_pv, HOP, SAMPLE_RATE, axes[2],
                 "vocoder half speed: twice as long, sweep intact")
plt.tight_layout()
plt.show()

# The same evidence in numbers: at matching musical moments, the vocoder's peak
# sits on the original's, and the naive version's sits an octave low.
for m_src in (40, 120, 200):
    b_orig = int(np.argmax(np.abs(X_orig[:, m_src])))
    b_pv = int(np.argmax(np.abs(X_pv[:, 2 * m_src])))
    b_naive = int(np.argmax(np.abs(X_naive[:, 2 * m_src])))
    print(f"  source frame {m_src:3d}: original bin {b_orig:3d}, "
          f"vocoder bin {b_pv:3d}, naive bin {b_naive:3d}")
    assert abs(b_pv - b_orig) <= 3, (
        "the vocoder should preserve the sweep; check pv_time_scale")
    assert abs(b_naive - b_orig / 2) <= 3, (
        "the naive comparison looks off; was naive_speed_change modified?")
print("Verified. Time bends; pitch holds.")
'''.strip())


LISTEN_MD = md(r"""
### Hear it

The arpeggio from the opening, rescued: half speed without the octave drop. Then take it to
real material: any FreeSound clip (your API key from Assignment 7 works here), or your own
files via `pq.Audio.from_file`. Real recordings are where you will start to hear the vocoder's
own personality; hold that thought for Task 6.
""".strip())


LISTEN_CODE = code(r'''
tune = arpeggio()
print("the tune, as written")
pq.play(pq.Audio(tune, sample_rate=SAMPLE_RATE))
print("naive half speed: the octave sags")
pq.play(pq.Audio(naive_speed_change(tune, 0.5), sample_rate=SAMPLE_RATE))
print("vocoder half speed: twice as long, pitch intact")
pq.play(pq.Audio(phase_vocoder(tune, 0.5), sample_rate=SAMPLE_RATE))

# Real material. Swap in your own FreeSound ID, or load a file of your own.
from pyquist.web.freesound import fetch_freesound
clip, _ = fetch_freesound(42981)  # <-- replace with YOUR sound ID
x = clip.as_mono().samples[:, 0]
print("a real recording at 0.75x")
pq.play(pq.Audio(phase_vocoder(x, 0.75), sample_rate=clip.sample_rate))
'''.strip())


TASK6_MD = md(r"""
## Task 6: Explore

Step back and look at what you have. Nothing in your five functions knows anything about
arpeggios, chirps, or half speed; you built a general instrument for bending musical time, the
same family of machinery that ships inside commercial warp engines, pitch correctors, and
podcast speed sliders. The last task is deliberately open: explore what you built, and show us
what you find in your `TECHNICAL.md` and demo video. Some directions, in no particular order:

- **Play it on everything.** Your own voice, a song, a podcast (`pq.Audio.from_file`, mix to
  mono, mind the sample rate). Find where it shines and where it hurts: drum hits smear, and
  dense mixes go slightly "underwater." Name what you hear in the field's own vocabulary
  (transient smearing, phasiness) in your `TECHNICAL.md`. For a reality check,
  `librosa.effects.time_stretch` is also a phase vocoder; how does yours compare?
- **Harness the chipmunk.** `naive_speed_change` moves pitch and time together; your vocoder
  moves time alone. Chain the two and you get pitch alone: a pitch shifter that preserves
  duration. Work out the stretch factor for a shift of $n$ semitones ($2^{n/12}$ is involved)
  and the order of the two steps, then transpose a song.
- **Freeze time.** Nothing forces the source position $p$ to keep moving. Pin it and the sound
  sustains forever: an infinite pad out of one second of audio. Drift it slowly for shimmer.
- **Bend, do not just stretch.** Your loop maps output frame to source position with
  $p = m \cdot s$. Replace that one line with any curve you like: a tape-stop, a DJ scratch, a
  ritardando synced to a score.
- **Go to extremes.** Try `speed = 0.05`. This is the territory of Paulstretch, the algorithm
  behind the famous "Justin Bieber slowed 800%" ambient recording. Where does your vocoder
  fall apart at that depth, and what does Paulstretch do with phase instead? (Hint: it gives
  up on it entirely.)
- **The final boss**, with a published answer to check yourself against: your vocoder keeps
  each bin honest with its own past but says nothing about bins staying honest with *each
  other*, and that slow drift between neighbors is exactly the "underwater" phasiness. Jean
  Laroche and Mark Dolson, *"Improved Phase Vocoder Time-Scale Modification of Audio"* (IEEE
  Transactions on Speech and Audio Processing, 1999), fix it with **identity phase locking**:
  find the spectral peaks in each frame, let the peaks run your Task 4 bookkeeping, and force
  each neighbor to keep its original phase relationship to its peak. Implement it and A/B it
  against your Task 4 by ear.

Before you submit, check your work against the requirements on the project page of the course
site.
""".strip())


TASK6_CODE = code(r'''
# Your exploration starts here.
'''.strip())


def assemble(task1, task2, task3, task4):
    return [
        INTRO_MD,
        SETUP_MD,
        SETUP_CODE,
        PROBLEM_MD,
        PROBLEM_CODE,
        TASK1_MD,
        task1,
        BENCH_MD,
        BENCH_CODE,
        TASK1_CHECK_MD,
        TASK1_CHECK_CODE,
        TASK2_MD,
        task2,
        TASK2_CHECK_MD,
        TASK2_CHECK_CODE,
        TASK3_MD,
        task3,
        TASK3_CHECK_MD,
        TASK3_CHECK_CODE,
        TASK4_MD,
        task4,
        TASK4_CHECK_MD,
        TASK4_CHECK_CODE,
        TASK5_MD,
        TASK5_CODE,
        LISTEN_MD,
        LISTEN_CODE,
        TASK6_MD,
        TASK6_CODE,
    ]


starter_cells = assemble(TASK1_STARTER, TASK2_STARTER, TASK3_STARTER, TASK4_STARTER)

d = HERE / "starter"
d.mkdir(exist_ok=True)
path = d / "ICMF26Assignment08.ipynb"
with open(path, "w") as f:
    json.dump(make_notebook(starter_cells), f, indent=1)
print(f"Written: {path}")

# fixed timestamp so regenerating doesn't churn the zip bytes
zip_path = HERE / "starter.zip"
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
    info = zipfile.ZipInfo(path.name, date_time=(2026, 1, 1, 0, 0, 0))
    zf.writestr(info, path.read_text())
print(f"Written: {zip_path}")
