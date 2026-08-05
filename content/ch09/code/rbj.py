"""
rbj.py -- Audio EQ Cookbook biquads.

Every function returns (b, a), ready for scipy.signal.lfilter:

    from scipy.signal import lfilter, freqz
    b, a = lpf(f_c=800, Q=6, f_s=44100)
    y = lfilter(b, a, x)

Parameters throughout:
    f_c   corner / center frequency in Hz   (0 < f_c < f_s/2)
    Q     resonance. 0.707 = flat (Butterworth), higher = peakier.
    f_s   sample rate in Hz
    gain  for peaking/shelf filters only, in dB

Coefficients follow Robert Bristow-Johnson's "Audio EQ Cookbook".
"""

import numpy as np

__all__ = ["lpf", "hpf", "bpf", "notch", "apf", "peaking", "lowshelf", "highshelf"]


def _common(f_c, Q, f_s):
    """Shared intermediates. Returns (cos_w0, alpha)."""
    if not 0 < f_c < f_s / 2:
        raise ValueError(f"f_c={f_c} must be between 0 and Nyquist ({f_s / 2})")
    if Q <= 0:
        raise ValueError(f"Q={Q} must be positive")
    w0 = 2 * np.pi * f_c / f_s
    return np.cos(w0), np.sin(w0) / (2 * Q)


def _norm(b0, b1, b2, a0, a1, a2):
    """Normalize so a[0] == 1, as lfilter expects."""
    return (np.array([b0, b1, b2]) / a0, np.array([1.0, a1 / a0, a2 / a0]))


def lpf(f_c, Q, f_s):
    """Resonant lowpass. Unity gain at DC, peak gain approx Q at f_c."""
    c, al = _common(f_c, Q, f_s)
    return _norm((1 - c) / 2, 1 - c, (1 - c) / 2, 1 + al, -2 * c, 1 - al)


def hpf(f_c, Q, f_s):
    """Resonant highpass. Unity gain at Nyquist."""
    c, al = _common(f_c, Q, f_s)
    return _norm((1 + c) / 2, -(1 + c), (1 + c) / 2, 1 + al, -2 * c, 1 - al)


def bpf(f_c, Q, f_s, unity_peak=True):
    """Bandpass. unity_peak=True gives 0 dB at f_c; False gives peak gain Q."""
    c, al = _common(f_c, Q, f_s)
    b0 = al if unity_peak else Q * al
    return _norm(b0, 0.0, -b0, 1 + al, -2 * c, 1 - al)


def notch(f_c, Q, f_s):
    """Band-reject. Full null at f_c; Q sets notch width."""
    c, al = _common(f_c, Q, f_s)
    return _norm(1.0, -2 * c, 1.0, 1 + al, -2 * c, 1 - al)


def apf(f_c, Q, f_s):
    """Allpass. Flat magnitude, phase flips through 180 deg at f_c."""
    c, al = _common(f_c, Q, f_s)
    return _norm(1 - al, -2 * c, 1 + al, 1 + al, -2 * c, 1 - al)


def peaking(f_c, Q, f_s, gain):
    """Peaking EQ. Boost (gain>0) or cut (gain<0) a band around f_c."""
    c, al = _common(f_c, Q, f_s)
    A = 10 ** (gain / 40)
    return _norm(1 + al * A, -2 * c, 1 - al * A, 1 + al / A, -2 * c, 1 - al / A)


def lowshelf(f_c, Q, f_s, gain):
    """Low shelf. Everything below f_c shifted by gain dB."""
    c, al = _common(f_c, Q, f_s)
    A = 10 ** (gain / 40)
    s = 2 * np.sqrt(A) * al
    return _norm(
        A * ((A + 1) - (A - 1) * c + s),
        2 * A * ((A - 1) - (A + 1) * c),
        A * ((A + 1) - (A - 1) * c - s),
        (A + 1) + (A - 1) * c + s,
        -2 * ((A - 1) + (A + 1) * c),
        (A + 1) + (A - 1) * c - s,
    )


def highshelf(f_c, Q, f_s, gain):
    """High shelf. Everything above f_c shifted by gain dB."""
    c, al = _common(f_c, Q, f_s)
    A = 10 ** (gain / 40)
    s = 2 * np.sqrt(A) * al
    return _norm(
        A * ((A + 1) + (A - 1) * c + s),
        -2 * A * ((A - 1) + (A + 1) * c),
        A * ((A + 1) + (A - 1) * c - s),
        (A + 1) - (A - 1) * c + s,
        2 * ((A - 1) - (A + 1) * c),
        (A + 1) - (A - 1) * c - s,
    )