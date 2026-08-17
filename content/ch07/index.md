# 7. Sampling Theory

In this chapter we seek a deeper understanding of the theory behind digital audio sampling, and its practical consequences. Back in {ref}`Chapter 1 <sec-sampling>`, we converted analog sound to digital audio in the _time domain_, through sampling and quantization. Since then we have gained crucial context about the _frequency domain_: in {ref}`Chapter 5 <sec-fourier-transform>` we developed the Fourier transform, and in {ref}`Chapter 6 <sec-negative-frequencies>` we uncovered the negative frequencies that lurk behind every positive one.

Armed with these tools, we can now study sampling from the perspective of the frequency domain. Our goal is to understand the _theory of sampling_ well enough to make principled choices about how to sample for a given audio application. Along the way we will answer three questions:

1. What, if anything, do we lose when we sample a sound?
1. Can we sample in a way that permits _perfect reconstruction_ of the original sound?
1. What sample rates and bit depths should we actually use?

(sec-sampling-and-frequency)=
