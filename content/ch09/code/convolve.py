"""Convolution from its definition, as a nested loop.

Standalone, student-facing implementation for Chapter 9. Run directly to check
it against NumPy's optimized ``np.convolve``.

The convolution of a length-``K`` filter ``h`` with a length-``N`` signal ``x``
is the length ``N + K - 1`` signal

    y[n] = sum_{k=0}^{K-1} h[k] * x[n - k],

where any sample of ``x`` at a negative or out-of-range index is treated as 0.
"""

import numpy as np


def convolve(x: np.ndarray, h: np.ndarray) -> np.ndarray:
    """Convolves signal ``x`` with filter ``h``, returning ``h * x``.

    A direct transcription of the convolution sum: for every output index
    ``n``, accumulate ``h[k] * x[n - k]`` over all ``k``, skipping any term
    whose ``x`` index falls outside the signal (an implicit zero).

    The two nested loops make the cost plain: with ``N = len(x)`` outputs and
    ``K = len(h)`` terms each, this is an O(NK) computation.
    """
    N, K = len(x), len(h)
    y = np.zeros(N + K - 1)
    for n in range(N + K - 1):
        for k in range(K):
            if 0 <= n - k < N:
                y[n] += h[k] * x[n - k]
    return y


if __name__ == "__main__":
    x = np.array([1.0, 1.0, 1.0])
    h = np.array([3.0, 2.0, 1.0])
    print("h * x   =", convolve(x, h))            # [3. 5. 6. 3. 1.]
    print("np ref  =", np.convolve(x, h))

    rng = np.random.default_rng(0)
    a, b = rng.standard_normal(40), rng.standard_normal(7)
    err = np.max(np.abs(convolve(a, b) - np.convolve(a, b)))
    print(f"max error vs np.convolve: {err:.2e}")
