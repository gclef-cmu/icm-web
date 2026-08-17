"""Extracting and reassembling frames (Chapter 10).

Two tiny, standalone, student-facing building blocks for frame-based
processing: ``iter_frames`` slices audio into frames, and ``overlap_add``
glues frames back into audio. Everything else in the chapter (granular
synthesis, the STFT) is built on top of these.
"""

from typing import Iterator

import numpy as np
import pyquist as pq


def iter_frames(audio: pq.Audio, N_H: int, N_F: int) -> Iterator[np.ndarray]:
    """Yields successive frames of ``N_F`` samples, spaced ``N_H`` apart.

    We do nothing special at the boundaries: the loop walks the signal in steps
    of the hop length ``N_H`` and stops once fewer than a full frame remains, so
    every yielded frame has exactly ``N_F`` samples. Each frame keeps its channel
    axis, so a frame has shape ``(N_F, num_channels)``.
    """
    for start in range(0, len(audio) - N_F + 1, N_H):
        yield audio.samples[start:start + N_F]


def overlap_add(frames: np.ndarray, N_H: int, sample_rate: int) -> pq.Audio:
    """Reassembles a stack of frames by adding each one back at its hop position.

    ``frames`` is an array of shape ``(num_frames, N_F, num_channels)``, e.g.
    ``np.array(list(iter_frames(...)))``. Passing a hop length ``N_H`` different
    from the one used to extract the frames stretches or compresses the result in
    time, which is the basis of the time-stretching examples.
    """
    num_frames, N_F, num_channels = frames.shape
    length = N_H * (num_frames - 1) + N_F
    out = np.zeros((length, num_channels), dtype=frames.dtype)
    for k, frame in enumerate(frames):
        out[k * N_H: k * N_H + N_F] += frame
    return pq.Audio(out, sample_rate)


if __name__ == "__main__":
    # Rectangular windows at 0% overlap (hop == frame) are perfect reconstruction.
    rng = np.random.default_rng(0)
    x = pq.Audio(rng.standard_normal((10 * 1024, 1)).astype(np.float32), 44100)  # whole # of frames
    N_F = 1024
    frames = np.array(list(iter_frames(x, N_F, N_F)))
    y = overlap_add(frames, N_F, 44100)
    n = min(len(x), len(y))
    err = np.max(np.abs(np.asarray(x.samples)[:n] - np.asarray(y.samples)[:n]))
    print(f"rect @ 0% overlap, max reconstruction error: {err:.2e}")
