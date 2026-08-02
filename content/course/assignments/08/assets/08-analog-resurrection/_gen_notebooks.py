"""Generate the starter notebook for Assignment 8 (Analog Resurrection:
analog-to-digital EQ via the bilinear transform).

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
# ICMF26 Assignment 8: Analog Resurrection

The most recorded equalizer in history is probably the [Neve 1073](https://en.wikipedia.org/wiki/Neve_1073),
a recording-console module designed in 1970 under [Rupert Neve](https://en.wikipedia.org/wiki/Rupert_Neve).
Studios still pay thousands of dollars for original units, yet you can buy a 1073 as a software
plugin for a hundredth of the price. How? Companies like Universal Audio and Waves start from the
analog circuit and work out its **transfer function**: a formula that says exactly how much the
circuit boosts or cuts each frequency. Then they convert that formula into a **difference
equation**: a short loop your laptop can run over the samples of a song. The standard tool for
that conversion is the **bilinear transform**, and it is the heart of this notebook. (It is also
the tool used in the classic paper on this exact problem: David Yeh & Julius Smith,
*"Discretization of the '59 Fender Bassman Tone Stack,"* DAFx 2006.)

In this project, you will do the same thing, small: build an **analog-to-digital EQ compiler**
and use it to bring a 1073-style channel EQ back to life on your laptop. Do not worry if terms
like "transfer function" are new to you; each idea is introduced right where you need it, and
every formula you must implement is written out in full. This notebook defines the structure and
the minimum requirement: four functions, each with a checkpoint that tells you whether it works,
followed by a provided verification and a final task that is yours to take wherever you like. The project is
open-ended and is meant to be more difficult than the autograded assignments; where you take it
beyond the minimum is up to you.

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

Run the cell below to verify your installation.
""".strip())


SETUP_CODE = code(r'''
import numpy as np
import matplotlib.pyplot as plt
import pyquist as pq

SAMPLE_RATE = 44100  # the resurrected EQ will run at CD quality
FREQS = np.geomspace(20, 20000, 2048)  # log-spaced frequency grid (Hz) for all plots
'''.strip())


UNIT_MD = md(r"""
## The Unit on the Bench

An equalizer (EQ) is a set of tone controls: each **band** boosts or cuts one region of the
frequency range. Our resurrection target borrows the 1073's architecture and knob values, four
bands in a row:

| Section | Type | Our setting | Drawn from the real 1073's options |
|---|---|---|---|
| *Rumble filter* | high-pass, **3rd-order Butterworth** (18 dB/oct) | 50 Hz | 50 / 80 / 160 / 300 Hz |
| *Low shelf* | shelving | 110 Hz, +4 dB | 35 / 60 / 110 / 220 Hz |
| *Presence* | peaking | 3.2 kHz, +3 dB, Q 1.0 | 0.36 / 0.7 / 1.6 / 3.2 / 4.8 / 7.2 kHz |
| *Air* | shelving | 12 kHz, +4 dB | fixed at 12 kHz |

In plain words: the *rumble filter* is a **high-pass**, cutting everything below 50 Hz (stage
rumble, mic thumps). The *low shelf* boosts the lows below about 110 Hz by 4 dB. *Presence* is a
**peaking** band, a gentle bump centered at 3.2 kHz, where voices and guitars cut through a mix.
*Air* is another shelf, lifting the sparkly highs above 12 kHz.

One band deserves a closer look. The rumble filter rolls off at **18 dB per octave**: each
octave you go below 50 Hz, the signal drops by another 18 dB. A steeper slope needs a more
complex filter, and this one is a **third-order** section while the other bands are
second-order. Keep an eye on it: it is the reason several shortcuts in this assignment do not
work, and your compiler will have to earn its keep.

(We are modeling the 1073's *filter architecture*, not its transformers and Class-A gain stages.)
""".strip())


CHANNEL_EQ_CODE = code(r'''
# Our resurrection target: a channel EQ in the image of the Neve 1073.
# This list is the input format your compiler consumes, and your compiler must
# work for ANY such list, not just this one.
CHANNEL_EQ = [
    dict(name="Rumble filter", kind="highpass",   f0=50.0,    order=3),
    dict(name="Low shelf",     kind="low_shelf",  f0=110.0,   gain_db=+4.0),
    dict(name="Presence",      kind="peak",       f0=3200.0,  gain_db=+3.0, q=1.0),
    dict(name="Air",           kind="high_shelf", f0=12000.0, gain_db=+4.0),
]

for band in CHANNEL_EQ:
    print(f"{band['name']:>14}: {band}")
'''.strip())


TASK1_MD = md(r"""
## Task 1: Stock the Parts Bin (`analog_prototype`)

An analog filter is described by a **transfer function** $H(s)$: a ratio of two polynomials in a
variable called $s$. You do not need the theory behind $s$ here; what matters is practical. Plug
$s = j\,(f/f_0)$ into $H(s)$, where $j$ is the imaginary unit, and the magnitude of the
resulting complex number tells you how much the filter boosts or cuts the frequency $f$. The
provided `analog_response` helper below does that plugging-in for you.

A polynomial is fully described by its coefficients, so we represent a filter as two coefficient
arrays `B` (numerator) and `A` (denominator), **highest power of $s$ first**. For example,
$H(s) = \dfrac{s^2 + 3s + 1}{2s^2 + 1}$ would be `B = [1, 3, 1]` and `A = [2, 0, 1]`.

Filter designers do not derive these polynomials from scratch. There is a standard catalog:
Robert Bristow-Johnson's [**Audio EQ Cookbook**](https://www.w3.org/TR/audio-eq-cookbook/),
published as a W3C note and cited in DSP code everywhere. It lists each EQ section as a
**normalized prototype**: a version whose **critical frequency** (the center of a peak, the
midpoint of a shelf, the cutoff of a high-pass) sits at exactly 1 in the units of $s$.
Normalizing keeps the numbers tame, and it will make Task 2 remarkably clean.

Your job is careful transcription: turn the formulas below into code, with
$A_g = 10^{\text{gain\_db}/40}$. Get the coefficient order right (highest power of $s$ first)
and remember to distribute the $A_g$ out front into the numerator array.

- **Peaking** *(implemented for you as a worked example)*:
  $\;H(s) = \dfrac{s^2 + (A_g/Q)\,s + 1}{s^2 + \big(1/(A_g Q)\big)\,s + 1}$
- **Low shelf**:
  $\;H(s) = \dfrac{A_g\big(s^2 + (\sqrt{A_g}/Q)\,s + A_g\big)}{A_g\,s^2 + (\sqrt{A_g}/Q)\,s + 1}$
- **High shelf**:
  $\;H(s) = \dfrac{A_g\big(A_g\,s^2 + (\sqrt{A_g}/Q)\,s + 1\big)}{s^2 + (\sqrt{A_g}/Q)\,s + A_g}$
- **Butterworth high-pass of order $n$** (the standard "maximally flat" cutoff filter):
  $\;H(s) = \dfrac{s^n}{B_n(s)}$, where
  $B_1 = s + 1$, $\;B_2 = s^2 + \sqrt{2}\,s + 1$, $\;B_3 = s^3 + 2s^2 + 2s + 1$.
  Support orders 1 to 3. Note these arrays have length $n+1$, so your prototypes are no longer
  all second-order; that is the point.

**Requirements:** Your pipeline must go through the analog domain and your own bilinear
transform (Task 2). The cookbook also tabulates ready-made *digital* coefficients; do not copy
those. It defeats the assignment, and those tables cannot produce the third-order rumble filter
anyway.
""".strip())


TASK1_STARTER = code(r'''
def analog_prototype(kind: str, gain_db: float = 0.0, q: float = 0.707,
                     order: int = 1) -> tuple[np.ndarray, np.ndarray]:
    """One normalized analog section from the standard catalog.

    Returns (B, A): coefficient arrays of H(s), highest power of s first,
    normalized so the section's critical frequency is at omega = 1 rad/s.
    Array length is (section order + 1), e.g. length 3 for second-order,
    length 4 for a third-order Butterworth high-pass.
    """
    Ag = 10 ** (gain_db / 40)
    if kind == "peak":  # worked example: H(s) = (s^2 + (Ag/q)s + 1) / (s^2 + (1/(Ag q))s + 1)
        return np.array([1.0, Ag / q, 1.0]), np.array([1.0, 1.0 / (Ag * q), 1.0])
    elif kind == "low_shelf":
        raise NotImplementedError("Implement me!")
    elif kind == "high_shelf":
        raise NotImplementedError("Implement me!")
    elif kind == "highpass":
        raise NotImplementedError("Implement me!")
    raise ValueError(f"unknown section kind: {kind!r}")
'''.strip())


BENCH_MD = md(r"""
### The measurement bench (provided)

Helpers that evaluate a transfer function's frequency response by plugging in points along the
frequency axis ($s = j\,(f/f_0)$ for a normalized analog prototype, $z = e^{\,j 2\pi f / f_s}$
for a digital filter), plus a helper that runs your `analog_prototype` over a whole EQ
configuration.
""".strip())


BENCH_CODE = code(r'''
def analog_response(B, A, f0, freqs):
    """Frequency response of a normalized analog section with critical frequency f0 (Hz),
    evaluated at freqs (Hz). Returns a complex array."""
    s = 1j * (np.asarray(freqs) / f0)
    return np.polyval(B, s) / np.polyval(A, s)


def digital_response(b, a, freqs, sample_rate):
    """Frequency response of a digital filter H(z) = (sum_k b[k] z^-k) / (sum_k a[k] z^-k),
    evaluated at freqs (Hz). Works for any filter order. Returns a complex array."""
    zinv = np.exp(-2j * np.pi * np.asarray(freqs) / sample_rate)
    return np.polyval(np.asarray(b)[::-1], zinv) / np.polyval(np.asarray(a)[::-1], zinv)


def db(H):
    """Magnitude in decibels."""
    return 20 * np.log10(np.maximum(np.abs(H), 1e-12))


def eq_sections(config):
    """Compile an EQ config into a list of (name, B, A, f0) analog sections."""
    sections = []
    for band in config:
        params = {k: v for k, v in band.items() if k not in ("name", "f0")}
        B, A = analog_prototype(**params)
        sections.append((band["name"], B, A, band["f0"]))
    return sections
'''.strip())


TASK1_CHECK_MD = md(r"""
### Checkpoint

Your prototypes must reproduce three facts at the critical frequency $f = f_0$:

- a **peaking** section reads its full gain there,
- a **shelf** reads exactly *half* its dB gain (a shelf's critical frequency is its midpoint,
  halfway up the ramp; the full gain arrives in the flat region beyond),
- a **Butterworth high-pass** of *any* order reads exactly $-3.01$ dB. That is the Butterworth
  signature.

If the asserts pass, the plot shows the analog response of the whole channel strip. This is the
target curve: by the end of the notebook, your digital filter has to trace it.
""".strip())


TASK1_CHECK_CODE = code(r'''
sections = eq_sections(CHANNEL_EQ)

expected_at_f0 = {"peak": lambda band: band.get("gain_db", 0.0),
                  "low_shelf": lambda band: band.get("gain_db", 0.0) / 2,
                  "high_shelf": lambda band: band.get("gain_db", 0.0) / 2,
                  "highpass": lambda band: -20 * np.log10(np.sqrt(2))}
for band, (name, B, A, f0) in zip(CHANNEL_EQ, sections):
    got = db(analog_response(B, A, f0, np.array([f0])))[0]
    want = expected_at_f0[band["kind"]](band)
    assert abs(got - want) < 0.01, (
        f"{name}: expected {want:+.2f} dB at f0={f0:.0f} Hz, got {got:+.2f} dB; "
        f"check your {band['kind']!r} prototype")
    print(f"  {name:>14}: {got:+.2f} dB at {f0:.0f} Hz, as the catalog demands")

H_truth = np.ones_like(FREQS, dtype=complex)
for name, B, A, f0 in sections:
    H_truth *= analog_response(B, A, f0, FREQS)

fig, ax = plt.subplots(figsize=(10, 3.5))
ax.semilogx(FREQS, db(H_truth), color="darkgoldenrod", lw=2.5)
for band in CHANNEL_EQ:
    ax.axvline(band["f0"], color="gray", ls=":", lw=0.8)
    ax.annotate(band["name"], (band["f0"], ax.get_ylim()[0]), rotation=90,
                fontsize=8, color="gray", va="bottom", ha="right")
ax.set_title("The target: analog response of the 1073-style channel EQ")
ax.set_xlabel("frequency (Hz)")
ax.set_ylabel("gain (dB)")
ax.grid(alpha=0.3, which="both")
plt.show()
'''.strip())


TASK2_MD = md(r"""
## Task 2: Build the Bridge (`bilinear_transform`)

Analog filters live in continuous time; your laptop takes one sample every $T = 1/f_s$ seconds.
The **bilinear transform** is the standard bridge between those two worlds. It converts a
continuous-time $H(s)$ into a discrete-time $H(z)$, a ratio of polynomials in $z^{-1}$ (where
multiplying by $z^{-1}$ simply means "delay by one sample"), by substituting

$$s \;=\; \frac{2}{T}\cdot\frac{1 - z^{-1}}{1 + z^{-1}}.$$

The bridge is sturdy: a stable analog filter always becomes a stable digital filter. But it is
not straight. The analog frequency axis goes on forever, while the digital one stops at the
**Nyquist frequency** $f_s/2$, the highest frequency a sample rate can represent. The transform
squeezes the whole infinite analog axis into that finite range, so bands land *lower* than they
aimed. At 44.1 kHz, our *Air* shelf aimed at 12 kHz would land near 9.9 kHz. The fix is
**pre-warping**: aim high on purpose, moving the analog critical frequency to
$\Omega = \frac{2}{T}\tan(\omega_0 T / 2)$ with $\omega_0 = 2\pi f_0$, chosen so the squeeze
lands the band exactly at $f_0$ on the digital side.

Here the catalog's normalization pays off. For a normalized prototype, placing the section at
$\Omega$ and crossing the bridge collapse into one clean substitution:

$$s \;\leftarrow\; K \cdot \frac{1 - z^{-1}}{1 + z^{-1}},
\qquad K = \frac{1}{\tan(\pi f_0 / f_s)}.$$

Implement `bilinear_transform`: make that substitution, clear the fractions by multiplying the
top and bottom by $(1+z^{-1})^N$ (where $N$ is the section's order), collect the resulting
polynomials in $z^{-1}$, and divide both by $a_0$ so it equals 1.

**Requirements:** It must work for a prototype of **any order** $N$, not just two. The rumble
filter is third-order, so the ready-made second-order formulas you may find online will not save
you. Two hints: multiplying two polynomials is exactly `np.convolve` of their coefficient
arrays, and the provided `_poly_power` helper raises a polynomial to a power.
""".strip())


TASK2_STARTER = code(r'''
def _poly_power(p, k):
    """(provided helper) The polynomial p raised to the k-th power, via repeated np.convolve.
    Polynomials are coefficient arrays in z^-1, constant term first; p**0 is [1.0]."""
    out = np.array([1.0])
    for _ in range(k):
        out = np.convolve(out, p)
    return out


def bilinear_transform(B: np.ndarray, A: np.ndarray, f0: float,
                       sample_rate: int) -> tuple[np.ndarray, np.ndarray]:
    """Carry one analog section across the bridge to the digital world.

    Args:
        B, A: coefficient arrays of a *normalized* analog prototype H(s)
            (highest power of s first, critical frequency at omega = 1),
            of any order: length 3 for a biquad, length 4 for third-order, etc.
        f0: the section's true critical frequency in Hz. Pre-warp this!
        sample_rate: the digital sample rate in Hz.

    Returns:
        (b, a): numpy arrays of digital filter coefficients in powers of z^-1
            (constant term first), same length as the section's order + 1,
            normalized so that a[0] == 1.
    """
    raise NotImplementedError("Implement me!")
'''.strip())


TASK2_CHECK_MD = md(r"""
### Checkpoint

Each section's digital curve should sit right on top of its analog original, and at $f_0$ they
must agree exactly; that is the pre-warp promise. You will also see the digital curves peel away
from the analog ones as they climb toward Nyquist, most visibly for the *Air* shelf. That is
frequency warping at work, not a bug, and it is worth a sentence in your `TECHNICAL.md`.
""".strip())


TASK2_CHECK_CODE = code(r'''
digital_sections = []
fig, ax = plt.subplots(figsize=(10, 3.5))
for i, (name, B, A, f0) in enumerate(sections):
    b, a = bilinear_transform(B, A, f0, SAMPLE_RATE)
    assert len(b) == max(len(B), len(A)), (
        f"{name}: expected {max(len(B), len(A))} digital coefficients, got {len(b)}; "
        "your transform must preserve the section's order")
    digital_sections.append((b, a))

    color = plt.get_cmap("tab10")(i)
    ax.semilogx(FREQS, db(analog_response(B, A, f0, FREQS)), color=color, ls="--", lw=1.2)
    ax.semilogx(FREQS, db(digital_response(b, a, FREQS, SAMPLE_RATE)),
                color=color, lw=1.8, label=name)

    gain_analog = db(analog_response(B, A, f0, np.array([f0])))[0]
    gain_digital = db(digital_response(b, a, np.array([f0]), SAMPLE_RATE))[0]
    assert abs(gain_analog - gain_digital) < 0.01, (
        f"{name}: digital gain at f0 is {gain_digital:.3f} dB but the analog section "
        f"says {gain_analog:.3f} dB; check your pre-warping!")
    print(f"  {name:>14} across the bridge: {gain_digital:+.2f} dB at {f0:.0f} Hz, on target")

ax.set_title("Section by section: analog original (dashed) vs. digital resurrection (solid)")
ax.set_xlabel("frequency (Hz)")
ax.set_ylabel("gain (dB)")
ax.grid(alpha=0.3, which="both")
ax.legend(fontsize=8)
plt.show()
print("All four sections made it across.")
'''.strip())


TASK3_MD = md(r"""
## Task 3: Reassemble the Channel Strip (`combine_cascade`)

In the real module, the signal flows through the sections one after another: rumble filter into
low shelf into presence into air. Filters in series **multiply**:

$$H_{\text{EQ}}(z) = H_1(z)\cdot H_2(z)\cdot H_3(z)\cdot H_4(z).$$

Each $H_i(z)$ is a ratio of polynomials, so the combined numerator is the product of all four
numerators, and the same for denominators. And you already know how to multiply polynomials:
convolve their coefficient arrays. Implement `combine_cascade`: fuse the list of digital
sections into the single pair `(b, a)` of one big difference equation. Ours comes out **9th
order**: $3 + 2 + 2 + 2$.
""".strip())


TASK3_STARTER = code(r'''
def combine_cascade(
    digital_sections: list[tuple[np.ndarray, np.ndarray]]
) -> tuple[np.ndarray, np.ndarray]:
    """Fuse a cascade of digital filter sections into one difference equation.

    Args:
        digital_sections: a list of (b, a) coefficient-array pairs, one per section
            (any orders; they need not all match).

    Returns:
        (b, a): the numerator and denominator coefficient arrays of the single
            combined H(z), i.e. the full digital EQ as one difference equation.
    """
    raise NotImplementedError("Implement me!")
'''.strip())


TASK4_MD = md(r"""
## Task 4: Make It Run (`apply_filter`)

So far $H(z)$ is just algebra. Here is how it becomes sound. With $a_0$ normalized to 1, the
filter runs as a **difference equation**:

$$y[n] = b_0 x[n] + b_1 x[n-1] + \dots + b_M x[n-M] \;-\; a_1 y[n-1] - \dots - a_M y[n-M].$$

Read it out loud: each output sample is a weighted mix of the current and recent *input* samples
(the `b` side), minus a weighted mix of the recent *output* samples (the `a` side). The output
feeds back into itself, and that feedback is what lets a handful of numbers carve long, smooth
frequency curves.

Implement `apply_filter`: run this equation over a signal, one sample at a time, for **any**
filter order. Treat any sample with a negative index as zero; the filter starts at rest. (Yes, a
Python loop over 44,100 samples per second is slow. Production EQs run the identical arithmetic
in optimized C. Same math, different horsepower.)

**Requirements:** No `scipy.signal`, no library filters. The whole point of the compiler is that
its output is a handful of numbers plus this loop.

The checkpoint below measures your engine the way you would measure a physical device: feed it a
single-sample spike (a **unit impulse**), record what comes out (the **impulse response**), and
take its FFT. By the convolution theorem you met in the autograded assignments, that spectrum is
the filter's frequency response. Math, meet machine.
""".strip())


TASK4_STARTER = code(r'''
def apply_filter(b: np.ndarray, a: np.ndarray, x: np.ndarray) -> np.ndarray:
    """Run the difference equation defined by (b, a) over signal x.

    Args:
        b, a: digital filter coefficient arrays (any order; a[0] need not be 1;
            normalize inside).
        x: the input signal, a 1-D array of samples.

    Returns:
        y: the filtered signal, same length as x (a numpy array).
    """
    raise NotImplementedError("Implement me!")
'''.strip())


TASK4_CHECK_CODE = code(r'''
# Measure the running machine: impulse in, FFT of what comes out.
b_test, a_test = digital_sections[2]  # the Presence peak
impulse = np.zeros(8192)
impulse[0] = 1.0
ir = apply_filter(b_test, a_test, impulse)

fft_freqs = np.fft.rfftfreq(len(ir), 1 / SAMPLE_RATE)
H_measured = np.fft.rfft(ir)
H_theory = digital_response(b_test, a_test, fft_freqs, SAMPLE_RATE)

band = (fft_freqs >= 20) & (fft_freqs <= 20000)
dev = np.max(np.abs(db(H_measured[band]) - db(H_theory[band])))

fig, ax = plt.subplots(figsize=(10, 3))
ax.semilogx(fft_freqs[band], db(H_theory[band]), color="darkgoldenrod", lw=3, alpha=0.5,
            label="theory: $H(z)$ on the unit circle")
ax.semilogx(fft_freqs[band], db(H_measured[band]), color="tab:blue", lw=1.2, ls="--",
            label="measured: FFT of your engine's impulse response")
ax.set_title("Math, meet machine (Presence section)")
ax.set_xlabel("frequency (Hz)")
ax.set_ylabel("gain (dB)")
ax.grid(alpha=0.3, which="both")
ax.legend(fontsize=9)
plt.show()

print(f"max |measured - theory| deviation: {dev:.2e} dB")
assert dev < 0.01, "Your engine's measured response disagrees with H(z); check apply_filter."
print("The machine keeps the promise.")
'''.strip())


TASK5_MD = md(r"""
## Task 5: The Proof

The provided cell below puts four curves on one plot: **(a)** the analog target from Task 1,
**(b)** the product of your digital sections' responses, **(c)** the single combined $H(z)$ from
`combine_cascade`, and **(d)** the FFT of an impulse run through your `apply_filter` on the
combined filter. Curves (b), (c), and (d) are three views of mathematically the same filter, so
they should agree to within a few hundredths of a dB, and all three should hug (a) across the
audible range, drifting away only near Nyquist.

One subtle detail: (b) and (c) will *not* match perfectly. Just evaluating one big 9th-order
polynomial loses a little floating-point precision compared to multiplying four small ones. Tuck
that observation away; it is a thread worth pulling in Task 6.

These are the plots your `TECHNICAL.md` needs.
""".strip())


TASK5_CODE = code(r'''
b_full, a_full = combine_cascade(digital_sections)
print(f"combined difference equation: order {len(a_full) - 1}")

# (b) product of the digital sections' responses
H_cascade = np.ones_like(FREQS, dtype=complex)
for b, a in digital_sections:
    H_cascade *= digital_response(b, a, FREQS, SAMPLE_RATE)

# (c) the single combined filter, evaluated
H_combined = digital_response(b_full, a_full, FREQS, SAMPLE_RATE)

# (d) the single combined filter, MEASURED running in your engine
impulse = np.zeros(16384)
impulse[0] = 1.0
ir_full = apply_filter(b_full, a_full, impulse)
fft_freqs = np.fft.rfftfreq(len(ir_full), 1 / SAMPLE_RATE)
H_measured = np.fft.rfft(ir_full)
band = (fft_freqs >= 20) & (fft_freqs <= 20000)

fig, ax = plt.subplots(figsize=(10, 3.5))
ax.semilogx(FREQS, db(H_truth), color="darkgoldenrod", lw=3.5, alpha=0.5,
            label="(a) analog target")
ax.semilogx(FREQS, db(H_cascade), color="tab:blue", lw=1.6, ls="--",
            label="(b) digital cascade")
ax.semilogx(FREQS, db(H_combined), color="tab:red", lw=1.2, ls=":",
            label="(c) combined difference equation")
ax.semilogx(fft_freqs[band], db(H_measured[band]), color="tab:green", lw=0.9, alpha=0.8,
            label="(d) measured impulse response")
ax.set_title("The resurrection, verified four ways")
ax.set_xlabel("frequency (Hz)")
ax.set_ylabel("gain (dB)")
ax.grid(alpha=0.3, which="both")
ax.legend(fontsize=9)
plt.show()

dev_bc = np.max(np.abs(db(H_cascade) - db(H_combined)))
dev_measured = np.max(np.abs(db(H_measured[band])
                             - db(digital_response(b_full, a_full, fft_freqs[band], SAMPLE_RATE))))
dev_analog = np.max(np.abs(db(H_truth) - db(H_cascade))[FREQS < 5000])
print(f"max |cascade - combined| deviation: {dev_bc:.2e} dB")
print("  (small, but noticeably not zero; the 9th-order polynomial is already leaking precision)")
print(f"max |measured - theory| deviation: {dev_measured:.2e} dB")
print(f"max |analog - digital| deviation below 5 kHz: {dev_analog:.3f} dB")
assert dev_bc < 0.1, "Combined filter disagrees with the cascade; check combine_cascade."
assert dev_measured < 1e-2, "Measurement disagrees with theory; check apply_filter."
print("Verified. The channel strip lives again.")
'''.strip())


TASK6_MD = md(r"""
## Task 6: Explore

Your compiler is built and verified. Step back and look at what you have: nothing in your four
functions knows anything about the 1073. **You built a compiler**, and the 1073-style channel
strip was merely its first program. Feed it any list of analog sections and it will carry them
across the bridge just the same. This is also how commercial plugins are actually made.
Universal Audio, Brainworx, Neural DSP, and Waves ship products built exactly this way: take a
revered analog circuit, derive its transfer function, and discretize it, very often with the
very bilinear transform you just implemented.

The last task is deliberately open: explore what you built, and show us what you find in your
`TECHNICAL.md` and demo video. Some directions, in no particular order:

- **Hear it.** Run a recording of your own through the channel strip with `apply_filter` (load
  it with `pq.Audio.from_file`, mix to mono, mind the sample rate). Does it do what the response
  plot promises?
- **Design an EQ of your own.** Pick your bands, name it, compile it, and listen.
- **Break it.** Task 5 hinted that the combined 9th-order filter leaks precision. What happens
  to each form when you round its coefficients to fewer decimal places, the way real hardware
  must? Look up coefficient quantization, and watch where the roots of the denominator move
  (`np.roots` will help).
- **Support more section types** (notch, band-pass, low-pass) or Butterworth sections of
  arbitrary order.
- **Factor any high-order section into biquads programmatically** (`np.roots`, pair the
  complex-conjugate roots), like production EQs do.
- **The final boss**, with a published answer to check yourself against: implement the analog
  transfer function from Yeh & Smith's *"Discretization of the '59 Fender Bassman Tone Stack"*
  (DAFx 2006) and compile a real amplifier's tone circuit through your own pipeline.

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
        UNIT_MD,
        CHANNEL_EQ_CODE,
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
        TASK4_MD,
        task4,
        TASK4_CHECK_CODE,
        TASK5_MD,
        TASK5_CODE,
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
