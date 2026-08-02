"""The Discrete Fourier Transform and a radix-2 Fast Fourier Transform.

Standalone, student-facing implementations for Chapter 8. Run directly to
check all three against NumPy's FFT.
"""

import numpy as np


def dft(x: np.ndarray) -> np.ndarray:
    """The DFT, fully vectorized: build the N x N grid of analysis phasors
    e^{-2 pi j k n / N} (row k, column n), multiply each row by the signal,
    and sum along n to get each output bin."""
    N = len(x)
    k, n = np.arange(N).reshape(-1, 1), np.arange(N).reshape(1, -1)
    phasors = np.exp(-2j * np.pi * k * n / N)
    return (phasors * x).sum(axis=1)


def dft_unrolled(x: np.ndarray) -> np.ndarray:
    """The same DFT written as an explicit double loop, so the O(N^2)
    structure is visible: for each output bin k, sum over all N samples n."""
    N = len(x)
    out = np.zeros(N, dtype=np.complex128)
    for k in range(N):
        for n in range(N):
            out[k] += x[n] * np.exp(-2j * np.pi * k * n / N)
    return out


def fft(x: np.ndarray) -> np.ndarray:
    """A radix-2 Cooley-Tukey FFT. Splits the signal into even- and
    odd-indexed samples, recurses (the log N part), and combines the two
    half-size DFTs with a vectorized butterfly (the N part). Requires that
    ``len(x)`` be a power of two."""
    x = np.asarray(x, dtype=np.complex128)
    N = len(x)
    if N == 1:
        return x
    if N % 2 != 0:
        raise ValueError("FFT input length must be a power of 2")
    even, odd = fft(x[::2]), fft(x[1::2])
    twiddle = np.exp(-2j * np.pi * np.arange(N // 2) / N) * odd
    return np.concatenate([even + twiddle, even - twiddle])


if __name__ == "__main__":
    rng = np.random.default_rng(0)
    x = rng.standard_normal(64)
    ref = np.fft.fft(x)
    for name, fn in [("dft", dft), ("dft_unrolled", dft_unrolled), ("fft", fft)]:
        err = np.max(np.abs(fn(x) - ref))
        print(f"{name:14s} max error vs np.fft.fft: {err:.2e}")
