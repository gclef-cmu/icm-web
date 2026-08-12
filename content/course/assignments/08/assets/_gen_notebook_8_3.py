"""Generate the starter and solution notebooks for Assignment 8, Direction 3
(Analog Resurrection: analog-to-digital EQ via the bilinear transform).

Cells are triple-quoted literals for easy manual editing. `md()`/`code()` wrap
them into notebook JSON. Regenerate with `python _gen_notebook_8_3.py`. The
starter `8-3-eq.ipynb` is committed beside this script; the solution goes to
`.solutions/` (dot-prefixed, so `make split` never mirrors it into the book
repo).
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
# ICMF26 Assignment 8: Analog Resurrection

The most recorded equalizer in history is probably the [Neve 1073](https://en.wikipedia.org/wiki/Neve_1073),
designed in 1970 under [Rupert Neve](https://en.wikipedia.org/wiki/Rupert_Neve). Studios pay
thousands of dollars for original units, yet a plugin version costs a hundredth of that. The
method: work out the circuit's **transfer function**, then convert it into a **difference
equation** your laptop can run, using the **bilinear transform** (the same tool as in David
Yeh & Julius Smith, *"Discretization of the '59 Fender Bassman Tone Stack,"* DAFx 2006).

In this project you build that converter, an **analog-to-digital EQ compiler**, and use it on
a 1073-style channel EQ. The four analog prototype formulas are **provided as working code**;
you implement `bilinear_transform`, `combine_cascade`, and `apply_filter`, each with a
checkpoint, followed by a provided verification and an open Explore section.

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
# Setup: run this cell to verify your installation.
import numpy as np
import matplotlib.pyplot as plt
import pyquist as pq

SAMPLE_RATE = 44100  # the digital EQ will run at CD quality
FREQS = np.geomspace(20, 20000, 2048)  # log-spaced frequency grid (Hz) for all plots
'''.strip())


UNIT_MD = md(r"""
## The Target EQ

An equalizer (EQ) is a set of tone controls: each **band** boosts or cuts one region of the
frequency range. Our target borrows the 1073's architecture and knob values, four bands in a
row:

| Section | Type | Our setting | Drawn from the real 1073's options |
|---|---|---|---|
| *Rumble filter* | high-pass, **3rd-order Butterworth** (18 dB/oct) | 50 Hz | 50 / 80 / 160 / 300 Hz |
| *Low shelf* | shelving | 110 Hz, +4 dB | 35 / 60 / 110 / 220 Hz |
| *Presence* | peaking | 3.2 kHz, +3 dB, Q 1.0 | 0.36 / 0.7 / 1.6 / 3.2 / 4.8 / 7.2 kHz |
| *Air* | shelving | 12 kHz, +4 dB | fixed at 12 kHz |

In plain words: the *rumble filter* cuts everything below 50 Hz, the *low shelf* boosts below
about 110 Hz, *Presence* is a gentle bump at 3.2 kHz, and *Air* lifts the highs above 12 kHz.
Note the rumble filter: an 18 dB per octave slope needs a **third-order** section while the
other bands are second-order, which is why second-order shortcuts do not work in this
assignment.

(We are modeling the 1073's *filter architecture*, not its transformers and Class-A gain stages.)
""".strip())


CHANNEL_EQ_CODE = code(r'''
# The target: a channel EQ modeled on the Neve 1073.
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


PROTO_MD = md(r"""
## The Analog Prototypes (provided)

An analog filter is described by a **transfer function** $H(s)$, a ratio of two polynomials
in $s$: plug in $s = j\,(f/f_0)$ and the magnitude of the result is the filter's gain at
frequency $f$. We store a filter as coefficient arrays `B` (numerator) and `A` (denominator),
**highest power of $s$ first**: $H(s) = \dfrac{s^2 + 3s + 1}{2s^2 + 1}$ is `B = [1, 3, 1]`
and `A = [2, 0, 1]`.

The formulas below are the standard catalog (Robert Bristow-Johnson's
[**Audio EQ Cookbook**](https://www.w3.org/TR/audio-eq-cookbook/)), each **normalized** so
its **critical frequency** sits at exactly 1 in units of $s$. Transcribing them is not the
lesson, so the next cell implements all four, with $A_g = 10^{\text{gain\_db}/40}$; these
arrays are the input to everything you build.

- **Peaking**:
  $\;H(s) = \dfrac{s^2 + (A_g/Q)\,s + 1}{s^2 + \big(1/(A_g Q)\big)\,s + 1}$
- **Low shelf**:
  $\;H(s) = \dfrac{A_g\big(s^2 + (\sqrt{A_g}/Q)\,s + A_g\big)}{A_g\,s^2 + (\sqrt{A_g}/Q)\,s + 1}$
- **High shelf**:
  $\;H(s) = \dfrac{A_g\big(A_g\,s^2 + (\sqrt{A_g}/Q)\,s + 1\big)}{s^2 + (\sqrt{A_g}/Q)\,s + A_g}$
- **Butterworth high-pass of order $n$** (the standard "maximally flat" cutoff filter):
  $\;H(s) = \dfrac{s^n}{B_n(s)}$, where
  $B_1 = s + 1$, $\;B_2 = s^2 + \sqrt{2}\,s + 1$, $\;B_3 = s^3 + 2s^2 + 2s + 1$.
  Orders 1 to 3; the third-order arrays have length 4.

Do not copy the cookbook's ready-made *digital* coefficients: they bypass the assignment and
cannot produce the third-order rumble filter.
""".strip())


PROTO_CODE = code(r'''
def analog_prototype(kind: str, gain_db: float = 0.0, q: float = 0.707,
                     order: int = 1) -> tuple[np.ndarray, np.ndarray]:
    """One normalized analog section from the standard catalog (provided).

    Returns (B, A): coefficient arrays of H(s), highest power of s first,
    normalized so the section's critical frequency is at omega = 1 rad/s.
    Array length is (section order + 1), e.g. length 3 for second-order,
    length 4 for a third-order Butterworth high-pass.
    """
    Ag = 10 ** (gain_db / 40)
    if kind == "peak":
        return np.array([1.0, Ag / q, 1.0]), np.array([1.0, 1.0 / (Ag * q), 1.0])
    elif kind == "low_shelf":
        return (Ag * np.array([1.0, np.sqrt(Ag) / q, Ag]),
                np.array([Ag, np.sqrt(Ag) / q, 1.0]))
    elif kind == "high_shelf":
        return (Ag * np.array([Ag, np.sqrt(Ag) / q, 1.0]),
                np.array([1.0, np.sqrt(Ag) / q, Ag]))
    elif kind == "highpass":
        denominators = {1: [1.0, 1.0],
                        2: [1.0, np.sqrt(2.0), 1.0],
                        3: [1.0, 2.0, 2.0, 1.0]}
        if order not in denominators:
            raise ValueError("highpass supports orders 1 to 3")
        B = np.zeros(order + 1)
        B[0] = 1.0  # numerator is s^n
        return B, np.array(denominators[order])
    raise ValueError(f"unknown section kind: {kind!r}")


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


TARGET_CODE = code(r'''
# The prototypes in action: evaluate each section at its critical frequency,
# then draw the analog response of the whole channel strip, the target curve
# your digital filter must trace. (Peak: full gain at f0; shelf: half its dB
# gain; Butterworth high-pass: -3.01 dB at any order.)
sections = eq_sections(CHANNEL_EQ)
for name, B, A, f0 in sections:
    gain = db(analog_response(B, A, f0, np.array([f0])))[0]
    print(f"  {name:>14}: {gain:+.2f} dB at {f0:.0f} Hz")

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


TASK1_MD = md(r"""
## Task 1: The Bilinear Transform (`bilinear_transform`)

Analog filters live in continuous time; your laptop samples every $T = 1/f_s$ seconds. The
**bilinear transform** converts a continuous-time $H(s)$ into a discrete-time $H(z)$, a ratio
of polynomials in $z^{-1}$ (multiplying by $z^{-1}$ means "delay by one sample"), by
substituting

$$s \;=\; \frac{2}{T}\cdot\frac{1 - z^{-1}}{1 + z^{-1}}.$$

It preserves stability, but it squeezes the infinite analog frequency axis into the range
below the **Nyquist frequency** $f_s/2$, so bands land *lower* than they aimed: at 44.1 kHz,
the 12 kHz *Air* shelf would land near 9.9 kHz. The fix is **pre-warping**: move the analog
critical frequency to $\Omega = \frac{2}{T}\tan(\omega_0 T / 2)$, with $\omega_0 = 2\pi f_0$,
so it lands exactly at $f_0$. For a normalized prototype, both steps collapse into one
substitution:

$$s \;\leftarrow\; K \cdot \frac{1 - z^{-1}}{1 + z^{-1}},
\qquad K = \frac{1}{\tan(\pi f_0 / f_s)}.$$

Implement `bilinear_transform`: substitute, clear the fractions by multiplying top and bottom
by $(1+z^{-1})^N$ ($N$ is the section's order), collect the polynomials in $z^{-1}$, and
divide both by $a_0$.

**Requirements:** it must work for **any order** $N$; the rumble filter is third-order, so
ready-made second-order formulas will not work. Hints: polynomial multiplication is
`np.convolve`, and the provided `_poly_power` raises a polynomial to a power. In the
checkpoint plot the digital curves peel away from the analog ones near Nyquist; that is
warping, not a bug, and worth a sentence in your `TECHNICAL.md`.
""".strip())


TASK1_STARTER = code(r'''
def _poly_power(p, k):
    """(provided helper) The polynomial p raised to the k-th power, via repeated np.convolve.
    Polynomials are coefficient arrays in z^-1, constant term first; p**0 is [1.0]."""
    out = np.array([1.0])
    for _ in range(k):
        out = np.convolve(out, p)
    return out


def bilinear_transform(B: np.ndarray, A: np.ndarray, f0: float,
                       sample_rate: int) -> tuple[np.ndarray, np.ndarray]:
    """Convert one analog section into a digital filter via the bilinear transform.

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


TASK1_CHECK_CODE = code(r'''
# Checkpoint: each section's digital curve should sit right on top of its analog
# original, and at f0 they must agree exactly; that is the pre-warp promise.
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
    print(f"  {name:>14}: {gain_digital:+.2f} dB at {f0:.0f} Hz, on target")

ax.set_title("Section by section: analog (dashed) vs. digital (solid)")
ax.set_xlabel("frequency (Hz)")
ax.set_ylabel("gain (dB)")
ax.grid(alpha=0.3, which="both")
ax.legend(fontsize=8)
plt.show()
print("All four sections converted correctly.")
'''.strip())


TASK2_MD = md(r"""
## Task 2: Combine the Cascade (`combine_cascade`)

In the real module, the signal flows through the sections one after another: rumble filter into
low shelf into presence into air. Filters in series **multiply**:

$$H_{\text{EQ}}(z) = H_1(z)\cdot H_2(z)\cdot H_3(z)\cdot H_4(z).$$

Each $H_i(z)$ is a ratio of polynomials, so the combined numerator is the product of all four
numerators, and the same for denominators. And you already know how to multiply polynomials:
convolve their coefficient arrays. Implement `combine_cascade`: combine the list of digital
sections into the single pair `(b, a)` of one big difference equation. Ours comes out **9th
order**: $3 + 2 + 2 + 2$.
""".strip())


TASK2_STARTER = code(r'''
def combine_cascade(
    digital_sections: list[tuple[np.ndarray, np.ndarray]]
) -> tuple[np.ndarray, np.ndarray]:
    """Combine a cascade of digital filter sections into one difference equation.

    Args:
        digital_sections: a list of (b, a) coefficient-array pairs, one per section
            (any orders; they need not all match).

    Returns:
        (b, a): the numerator and denominator coefficient arrays of the single
            combined H(z), i.e. the full digital EQ as one difference equation.
    """
    raise NotImplementedError("Implement me!")
'''.strip())


TASK3_MD = md(r"""
## Task 3: The Difference Equation (`apply_filter`)

With $a_0$ normalized to 1, $H(z)$ runs as a **difference equation**:

$$y[n] = b_0 x[n] + b_1 x[n-1] + \dots + b_M x[n-M] \;-\; a_1 y[n-1] - \dots - a_M y[n-M].$$

Each output sample is a weighted mix of current and recent *inputs* (the `b` side) minus
recent *outputs* (the `a` side). Implement `apply_filter`: run this equation over a signal,
one sample at a time, for **any** filter order, treating samples with negative indexes as
zero. (A Python loop is slow; production EQs run the same arithmetic in C.)

**Requirements:** no `scipy.signal`, no library filters.

The checkpoint feeds your engine a **unit impulse** and takes the FFT of the **impulse
response**; by the convolution theorem, that spectrum is the filter's frequency response,
ready to compare against $H(z)$.
""".strip())


TASK3_STARTER = code(r'''
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


TASK3_CHECK_CODE = code(r'''
# Checkpoint: measure the running filter, impulse in, FFT of what comes out.
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
ax.set_title("Theory vs. measurement (Presence section)")
ax.set_xlabel("frequency (Hz)")
ax.set_ylabel("gain (dB)")
ax.grid(alpha=0.3, which="both")
ax.legend(fontsize=9)
plt.show()

print(f"max |measured - theory| deviation: {dev:.2e} dB")
assert dev < 0.01, "Your engine's measured response disagrees with H(z); check apply_filter."
print("Measured response matches theory.")
'''.strip())


VERIFY_MD = md(r"""
## Verification

The provided cell below puts four curves on one plot: **(a)** the analog target, **(b)** the
product of your digital sections' responses, **(c)** the single combined $H(z)$ from
`combine_cascade`, and **(d)** the measured impulse response of your engine on the combined
filter. The last three are the same filter and must agree, and all should hug the target
until near Nyquist; these are the plots your `TECHNICAL.md` needs. ((b) and (c) will differ
slightly in the last digits; Explore explains why.)
""".strip())


VERIFY_CODE = code(r'''
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
ax.set_title("The channel EQ, verified four ways")
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
print("Verified: all four views agree.")
'''.strip())


EXPLORE_MD = md(r"""
## Explore

Nothing in your three functions knows about the 1073: **you built a compiler**, and this is
how commercial plugins are made. This part is open: explore, and show us what you find in
`TECHNICAL.md` and your demo video. Some directions:

- **Hear it:** run a recording through the channel strip with `apply_filter`
  (`pq.Audio.from_file`, mix to mono, mind the sample rate).
- **Design an EQ of your own:** pick bands, compile, listen.
- **Coefficient quantization:** round the coefficients of the combined filter and of each
  section to fewer digits, watch the responses and the denominator roots (`np.roots`), and
  see why production EQs run as cascades of second-order sections; factoring your 9th-order
  filter into biquads is the follow-up.
- **The Fender Bassman tone stack** (Yeh & Smith, DAFx 2006): compile a real amplifier's tone
  circuit through your own pipeline, with a published answer to check against.

Check your work against the requirements on the project page.
""".strip())


EXPLORE_CODE = code(r'''
# Your exploration starts here.
'''.strip())


SOLUTION_NOTE = md(r"""
**Instructor solution. Do not distribute.**
""".strip())


TASK1_SOLUTION = code(r'''
def _poly_power(p, k):
    """(provided helper) The polynomial p raised to the k-th power, via repeated np.convolve.
    Polynomials are coefficient arrays in z^-1, constant term first; p**0 is [1.0]."""
    out = np.array([1.0])
    for _ in range(k):
        out = np.convolve(out, p)
    return out


def bilinear_transform(B: np.ndarray, A: np.ndarray, f0: float,
                       sample_rate: int) -> tuple[np.ndarray, np.ndarray]:
    """Bilinear transform with pre-warp, any order (instructor solution).

    Substituting s = K (1 - z^-1)/(1 + z^-1) and clearing fractions with
    (1 + z^-1)^N turns each coefficient of s^p into
    K^p (1 - z^-1)^p (1 + z^-1)^(N - p), a length N+1 polynomial in z^-1.
    """
    B = np.asarray(B, dtype=float)
    A = np.asarray(A, dtype=float)
    N = max(len(B), len(A)) - 1
    K = 1.0 / np.tan(np.pi * f0 / sample_rate)
    Bp = np.concatenate([np.zeros(N + 1 - len(B)), B])
    Ap = np.concatenate([np.zeros(N + 1 - len(A)), A])
    num = np.zeros(N + 1)
    den = np.zeros(N + 1)
    for i in range(N + 1):
        power = N - i  # Bp[i] and Ap[i] multiply s^power
        term = (K ** power) * np.convolve(_poly_power([1.0, -1.0], power),
                                          _poly_power([1.0, 1.0], N - power))
        num += Bp[i] * term
        den += Ap[i] * term
    return num / den[0], den / den[0]
'''.strip())


TASK2_SOLUTION = code(r'''
def combine_cascade(
    digital_sections: list[tuple[np.ndarray, np.ndarray]]
) -> tuple[np.ndarray, np.ndarray]:
    """Series filters multiply, so coefficient arrays convolve (instructor solution)."""
    b = np.array([1.0])
    a = np.array([1.0])
    for b_i, a_i in digital_sections:
        b = np.convolve(b, b_i)
        a = np.convolve(a, a_i)
    return b, a
'''.strip())


TASK3_SOLUTION = code(r'''
def apply_filter(b: np.ndarray, a: np.ndarray, x: np.ndarray) -> np.ndarray:
    """The difference equation, one sample at a time (instructor solution)."""
    b = np.asarray(b, dtype=float)
    a = np.asarray(a, dtype=float)
    b = b / a[0]
    a = a / a[0]
    y = np.zeros(len(x))
    for n in range(len(x)):
        acc = 0.0
        for k in range(len(b)):
            if n - k >= 0:
                acc += b[k] * x[n - k]
        for k in range(1, len(a)):
            if n - k >= 0:
                acc -= a[k] * y[n - k]
        y[n] = acc
    return y
'''.strip())


def build_cells(task1, task2, task3, note=None):
    cells = [
        INTRO_MD,
        SETUP_CODE,
        UNIT_MD,
        CHANNEL_EQ_CODE,
        PROTO_MD,
        PROTO_CODE,
        TARGET_CODE,
        TASK1_MD,
        task1,
        TASK1_CHECK_CODE,
        TASK2_MD,
        task2,
        TASK3_MD,
        task3,
        TASK3_CHECK_CODE,
        VERIFY_MD,
        VERIFY_CODE,
        EXPLORE_MD,
        EXPLORE_CODE,
    ]
    if note is not None:
        cells.insert(0, note)
    return cells


path = HERE / "8-3-eq.ipynb"
with open(path, "w") as f:
    json.dump(make_notebook(build_cells(TASK1_STARTER, TASK2_STARTER,
                                        TASK3_STARTER)), f, indent=1)
print(f"Written: {path}")

sol_dir = HERE / ".solutions"
sol_dir.mkdir(exist_ok=True)
sol_path = sol_dir / "8-3-eq-solution.ipynb"
with open(sol_path, "w") as f:
    json.dump(make_notebook(build_cells(TASK1_SOLUTION, TASK2_SOLUTION,
                                        TASK3_SOLUTION, SOLUTION_NOTE)),
              f, indent=1)
print(f"Written: {sol_path}")
