"""The short-time Fourier transform and its inverse (Chapter 10).

Standalone, student-facing implementations. The STFT is just "the DFT of each
frame"; the inverse STFT is "the inverse DFT of each frame, overlap-added back
together". Run directly to check that the round trip reconstructs a signal.
"""

import numpy as np


def stft(x: np.ndarray, N_H: int, N_F: int,
         window: np.ndarray = None) -> np.ndarray:
    """Short-time Fourier transform: window each frame and take its DFT.

    Returns a complex matrix of shape ``(num_frames, N_F // 2 + 1)``, one row per
    frame and one column per (non-redundant) frequency bin. ``N_F`` is the frame
    length and ``N_H`` the hop length. We use the real FFT ``np.fft.rfft`` since
    audio is real-valued.
    """
    if window is None:
        window = np.ones(N_F)
    frames = []
    for start in range(0, len(x) - N_F + 1, N_H):
        frames.append(np.fft.rfft(x[start:start + N_F] * window))
    return np.array(frames)


def istft(S: np.ndarray, N_H: int, N_F: int,
          window: np.ndarray = None) -> np.ndarray:
    """Inverse STFT: inverse-DFT each frame and overlap-add the results.

    Each frame is windowed again on the way out and the running sum of squared
    windows is divided out at the end. This "weighted overlap-add" gives perfect
    reconstruction whenever the windows satisfy the constant-overlap-add
    property (e.g. a rectangular window at 0% overlap, or a Hann window at 50%).
    """
    if window is None:
        window = np.ones(N_F)
    num_frames = S.shape[0]
    length = N_H * (num_frames - 1) + N_F
    out = np.zeros(length)
    window_sum = np.zeros(length)
    for k in range(num_frames):
        frame = np.fft.irfft(S[k], N_F) * window
        out[k * N_H: k * N_H + N_F] += frame
        window_sum[k * N_H: k * N_H + N_F] += window ** 2
    return out / np.maximum(window_sum, 1e-8)


def hann(N_F: int) -> np.ndarray:
    """A Hann window of length ``N_F``."""
    n = np.arange(N_F)
    return 0.5 * (1 - np.cos(2 * np.pi * n / N_F))


if __name__ == "__main__":
    rng = np.random.default_rng(0)
    x = rng.standard_normal(20000)
    N_F, N_H = 1024, 256                    # Hann window at 75% overlap
    w = hann(N_F)
    y = istft(stft(x, N_H, N_F, w), N_H, N_F, w)
    n = min(len(x), len(y))
    # Skip the warm-up region at the very edges, where fewer windows overlap.
    err = np.max(np.abs(x[N_F:n - N_F] - y[N_F:n - N_F]))
    print(f"STFT round-trip max error (interior): {err:.2e}")
