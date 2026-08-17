# 10. Frame-based Processing

So far we have studied two extremes of how a computer handles time. When we studied {ref}`sampling <sec-sampling-and-frequency>` in [Chapter 7](../ch07/index.md), we saw that music audio is usually sampled at more than $40{,}000$ times per second, fast enough to capture the highest frequencies we can hear. When we studied the {ref}`Fourier transform <sec-fourier-transform>` in [Chapter 5](../ch05/index.md) and its practical cousin the {ref}`DFT <def-dft>` in [Chapter 8](../ch08/index.md), we did the opposite: we integrated across _all_ of time to produce a single summary of a sound's frequency content, in effect measuring it just once no matter how long it was (a "rate" of $0$ measurements per second).

Most phenomena in music live _between_ these two extremes. The attack of a plucked string lasts about a hundredth of a second, a four-on-the-floor kick drum at 120 BPM lands twice a second, a pianist playing Bach's Prelude in C plays around five notes a second, and the [world's fastest drummer](https://en.wikipedia.org/wiki/World%27s_Fastest_Drummer) can manage twenty strokes a second. None of these needs the microsecond precision of individual samples, but all of them are lost to the time integration of a global Fourier transform.

:::{list-table} The rate at which things happen in music, from a single Fourier measurement to individual samples. The musically interesting middle (blue) is what this chapter is about.
:header-rows: 1
:name: tbl-rates

- - Phenomenon
  - Interval
  - Rate
- - Fourier transform (whole recording)
  - $\red{\infty}$
  - $\red{0}$ Hz
- - Kick drum at 120 BPM
  - $\blue{500}$ ms
  - $\blue{2}$ Hz
- - Melody (Bach, ~5 notes/sec)
  - $\blue{200}$ ms
  - $\blue{5}$ Hz
- - World's fastest drummer
  - $\blue{50}$ ms
  - $\blue{20}$ Hz
- - Instrument attack
  - $\blue{10}$ ms
  - $\blue{100}$ Hz
- - Audio samples
  - $\red{0.023}$ ms
  - $\red{44{,}100}$ Hz
:::

**How do we process phenomena that happen at these intermediate, musically intuitive rates, say tens to hundreds of times per second?** The answer is {vocab}`frame-based processing`, a family of techniques that aggregate audio samples into chunks called {vocab}`frames` and then analyze or manipulate those frames. It is the foundation for granular synthesis, the spectrogram, time stretching, and much of the audio software you use every day. Throughout the chapter we will use a recording of a jazz trio as a running example:

:::{audio}
[A jazz trio (our running example)](./assets/audio-trio.wav)

Eight seconds of a jazz trio, which we will slice, scramble, stretch, and analyze throughout this chapter. [725677](https://freesound.org/s/725677/) by draganov89, License: [Attribution NonCommercial 4.0](https://creativecommons.org/licenses/by-nc/4.0/).
:::

(sec-extracting-frames)=
