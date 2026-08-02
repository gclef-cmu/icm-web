# 8. The Discrete Fourier Transform

In [Chapter 5](../05-frequency-domain) we developed the Fourier transform, which converts a signal from the time domain into the frequency domain. It is a powerful and elegant tool, but the version we studied is a _mathematical_ primitive, and it is riddled with assumptions that are impractical in the real world. This is a book on _computer_ music: we want a tool we can actually run on digital audio.

In this chapter we address those incompatibilities one at a time to derive the {vocab}`discrete Fourier transform` (DFT), a metamorphosis of the Fourier transform that a computer can actually evaluate on a finite array of samples. This comes at a cost, and along the way we will meet the consequences of discretizing the transform. Finally, we will introduce the {vocab}`fast Fourier transform` (FFT), an _algorithm_ that computes the DFT exactly but with asymptotic behavior superior to a naive implementation.
