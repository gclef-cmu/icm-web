# 5. The Frequency Domain

So far, we have seen several scenarios where _combinations of frequencies_ lead to interesting musical results. In additive synthesis ([Chapter 3](../ch03/index.md)), mixing basic sinusoids at integer multiples (harmonics) of a fundamental frequency gave rise to different timbres. In our study of scores ([Chapter 4](../ch04/index.md)), combining notes at different fundamental frequencies (pitches) turned out to be a primary axis of musical composition. Both observations point to the same conclusion: **variation in frequency is a fundamental property of musical expression**.

But how should we reason about these variations? Are there mathematical tools to formalize them? And if we are handed a new sound that we know nothing about, how can we determine what frequencies it contains? This chapter develops the {vocab}`frequency domain` and the {vocab}`Fourier transform`, the central tool for answering these questions.
