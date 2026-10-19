# Glossary

An alphabetical reference of the key terms in this book. Click a term to
jump to where it first appears.

:::{note}
{icon-ai} The definitions on this page were AI-generated from the passage
where each term first appears. They may contain mistakes. When in doubt,
click the term to read it in context, and trust the book's text.
:::

:::{glossary}
:sorted:

additive synthesis
  Building a periodic tone by summing $K$ sinusoidal harmonics, each with its
  own amplitude $a_k$ and initial phase $\phi_k$. The fundamental $f_0$ sets the
  pitch, and the relative amplitudes mostly set the timbre.

ADSR
  A common four-phase envelope shape: attack (rise from silence), decay (fall
  from the peak), sustain (hold steady while the note is held), and release
  (fade back to silence). Usually only the sustain stretches with note length.

aliasing
  Distortion that occurs when a signal is sampled too slowly, so frequencies
  above the Nyquist frequency masquerade as lower ones. A frequency $f$ produces
  exactly the same samples as its aliases $f + k f_s$ for any integer $k$.

all-pass
  A filter that leaves the amplitude of every frequency unchanged and alters
  only the phase.

amplitude
  The peak deviation of a waveform from zero. A basic sinusoid $a \sin(\cdot)$
  stays within $[-a, a]$, and larger amplitudes sound louder.

amplitude modulation
  Multiplying a carrier by a modulator that oscillates around a nonzero average,
  $\sin(\omega_c t)\,[1 + \sin(\omega_m t)]$. It equals ring modulation plus the
  carrier, so the spectrum keeps the carrier alongside two sidebands.

amplitude spectrum
  The magnitude $|X(\omega)|$ of the Fourier transform, which tells how much of
  each frequency a signal contains. It is real and non-negative, and is used far
  more than the phase spectrum because the ear is largely insensitive to phase.

angular frequency
  Frequency measured in radians per second instead of cycles per second,
  $\omega = 2\pi f$. It lets the basic sinusoid be written compactly as
  $a \sin(\omega t + \phi)$.

anti-aliasing filter
  A filter applied before sampling (or before downsampling) that removes content
  above the Nyquist frequency, so that nothing is left to alias.

antinode
  A point halfway between the nodes of a standing wave, where the medium
  oscillates with the largest amplitude.

band-pass
  A filter that passes a band of frequencies around a center frequency and
  rejects everything else.

band-stop
  A filter that rejects a band of frequencies around a center frequency and
  passes everything else. Also called a notch.

bandwidth
  The width of a band of frequencies. For a band-pass filter it is $f_H - f_L$,
  the distance between the two frequencies where the response crosses $-6$ dB.

baseband
  The central, unshifted copy of a signal's spectrum, spanning
  $[-f_{\max}, f_{\max}]$. Sampling replicates the baseband around every
  multiple of $f_s$.

basic sinusoid
  The simplest periodic function, $x(t) = a \sin(2\pi f t + \phi)$, with
  frequency $f$, amplitude $a$, and initial phase $\phi$. It sounds like a pure
  tone, and any periodic sound can be built as a sum of basic sinusoids.

beat
  A symbolic unit of musical time referring to the underlying pulse, what you
  might tap your foot to.

bin
  One of the $N$ evenly spaced analysis frequencies of the DFT, indexed by $k$.
  Bin $k$ sits at $k f_s / N$ Hz, so adjacent bins are $\Delta f = f_s/N = 1/T$
  apart.

block
  The name for a frame in real-time audio. The audio system repeatedly asks a
  program for the next $B$ samples, which is frame-based processing with
  $N_H = N_F = B$.

butterfly
  The combining step of the FFT, which merges two half-size DFTs $E[k]$ and
  $O[k]$ into $X[k] = E[k] + W_N^k O[k]$ and $X[k + N/2] = E[k] - W_N^k O[k]$
  in $O(N)$ time.

carrier frequency
  In modulation synthesis, the frequency of the carrier, the signal whose
  amplitude or frequency is being modulated. Written $\omega_c$ in radians per
  second or $f_c$ in Hz.

circular buffer
  An array with a pointer to its oldest entry, used to implement a delay line.
  Each step reads the oldest sample, overwrites it with the newest, and advances
  the pointer, wrapping from the end back to the start.

comb filter
  A filter whose magnitude response has evenly spaced peaks, like the teeth of
  a comb. A feedback delay line of $M$ samples is a comb filter that boosts
  whole-number multiples of $\frac{f_s}{M}$ and rejects the frequencies in
  between.

commuted synthesis
  Reordering and regrouping the filters of a physical model (delays, losses,
  low-pass filters) into whatever order is cheapest to compute. This is valid
  because LTI filters commute, as long as we only listen at points the
  reordering does not disturb.

complex sinusoid
  The complex-valued signal
  $a e^{j\omega t} = a\cos(\omega t) + j\,a\sin(\omega t)$. It is a vector of
  length $a$ rotating around the complex plane, whose real part traces a cosine
  and whose imaginary part traces a sine.

constant overlap-add
  A property (COLA) of a window $w$ and hop length $N_H$ where the shifted
  windows sum to a non-zero constant at every sample. It guarantees that
  overlap-adding windowed frames reconstructs the signal up to a scale factor.

control point
  A pair $(t_i, a_i)$ that fixes an envelope's value $a_i$ at time $t_i$. A
  piecewise-linear envelope interpolates linearly between consecutive control
  points.

convolution
  The operation $y[n] = \sum_{k=0}^{K-1} h[k]\, x[n-k]$, written $y = h * x$,
  which sums weighted, delayed copies of the input. Every LTI filter can be
  written as a convolution with its impulse response.

convolution reverb
  A reverb effect made by convolving a dry recording with the recorded impulse
  response of a real space, so it sounds as if it were played in that space.

convolution theorem
  The result that convolution in the time domain equals multiplication in the
  frequency domain: if $y = h * x$, then $Y[k] = H[k] \cdot X[k]$. Its dual
  says multiplication in time equals convolution in frequency.

critical sampling
  Sampling at exactly twice the highest frequency, $f_s = 2 f_{\max}$. A
  component right at $f_s/2$ may vanish depending on its phase, so perfect
  reconstruction is not guaranteed.

crossfade
  Gradually fading one piece of audio out while fading another in. Samplers
  crossfade at each wrap of a sustain loop to hide the mismatch between the
  loop's end and its start.

cutoff frequency
  The frequency $f_C$ marking the boundary between a filter's passband and
  stopband. For a real filter it is conventionally where the response has
  fallen to a threshold such as $-6$ dB.

dB SPL
  Decibels of sound pressure level, measured relative to the threshold of
  hearing $p_0 = 20$ μPa, so $\text{dB SPL} = 20\log_{10}(p/p_0)$.

dBFS
  Decibels relative to full scale, using the reference amplitude $a_0 = 1$, so
  $\text{dBFS} = 20\log_{10}(a)$. Values are normally negative, and 0 dBFS is
  the clipping point.

decibel
  A logarithmic unit (dB) that compares an amplitude $a$ to a reference $a_0$
  as $20\log_{10}(a/a_0)$. Doubling an amplitude adds about 6 dB, and
  multiplying it by 10 adds 20 dB.

delay line
  A filter that outputs its input $M$ samples later, $y[n] = x[n - M]$. In
  physical models it simulates the time a wave takes to travel through a
  medium.

depth
  In frequency modulation, the amount $D$, in Hz, by which the instantaneous
  frequency wavers above and below the carrier frequency $f_c$.

difference equation
  A formula that defines a filter by expressing each output sample $y[n]$ in
  terms of input samples and possibly past output samples, such as
  $y[n] = x[n] + x[n-1]$.

digital filter
  A function $g$ that maps an array of input samples $x$ to an array of output
  samples $y$, written $g : x \mapsto y$.

digital waveguide
  A physical model that represents the right-going and left-going waves on a
  string with two delay lines running in opposite directions. Reflections at
  the ends multiply by $-1$, and summing the two lines at a point gives the
  string's displacement there.

discrete Fourier transform
  The DFT, a version of the Fourier transform that a computer can evaluate on
  $N$ samples, $\texttt{DFT}(x)[k] = \sum_{n=0}^{N-1} x[n]\, e^{-2\pi j k n / N}$.
  It maps $N$ samples to $N$ complex bins.

drum machine
  A sequencer whose interface is a grid of steps. Each row is a drum sound,
  each column is a subdivision of a beat, and the musician switches cells on or
  off.

dynamic range
  The span between the quietest and loudest levels a system can represent or a
  listener can hear, measured in dB. Each bit of depth adds about 6 dB, so
  16-bit audio has about 96 dB.

envelope
  A function $\text{Envelope}(t)$ with values in $[0, 1]$ that is zero outside a
  finite time window. Multiplying a sustained tone by an envelope shapes its
  loudness over time and turns it into a finite sound event.

Euler's formula
  The identity $e^{j\theta} = \cos\theta + j\sin\theta$. It places $e^{j\theta}$
  on the unit circle at angle $\theta$ and links polar and rectangular form.

event
  Something that happens at a specific point in time and carries parameters
  describing it, such as a note with a pitch and a duration. In Pyquist an event
  is a pair of a time and a dict of keyword arguments.

fast Fourier transform
  The FFT, a divide-and-conquer algorithm that computes the DFT exactly in
  $O(N \log N)$ time instead of $O(N^2)$, by splitting it into two half-size
  DFTs over the even- and odd-indexed samples.

feedback coefficient
  One of the weights $a_j$ in a recursive difference equation that multiply
  past outputs $y[n-j]$.

feedforward coefficient
  One of the weights $b_i$ in a difference equation that multiply the current
  and past inputs $x[n-i]$.

filter
  Broadly, any function that takes a signal as input and produces another
  signal as output. In everyday usage the word is shorthand for a linear
  time-invariant filter, which reshapes a sound's spectrum.

finite impulse response
  FIR, an impulse response that ends after finitely many samples. A filter with
  only feedforward coefficients has one, equal to those coefficients.

foldover
  Aliasing of frequencies just above the Nyquist frequency, in $[f_s/2, f_s]$,
  which reflect back below it as if the Nyquist frequency were a crease in a
  folded sheet of paper.

Fourier series
  The result that any periodic signal with fundamental frequency $f_0$ can be
  written as a constant plus a sum of sinusoids at integer multiples of $f_0$,
  $x(t) = a_0 + \sum_{k} a_k \sin(2\pi k f_0 t + \phi_k)$.

Fourier transform
  The function $X(\omega) = \int_{-\infty}^{\infty} x(t)\, e^{-j\omega t}\, dt$,
  which maps each angular frequency to a complex number describing how much of
  that frequency $x(t)$ contains and at what phase. It works by multiplying the
  signal by a phasor and integrating over time.

frame
  A contiguous chunk of $N_F$ samples extracted from a signal. The $k$-th frame
  starts at sample $k \cdot N_H$, so $x_k[n] = x[k \cdot N_H + n]$.

frame length
  The number of samples $N_F$ in each frame.

frame rate
  The number of frames per second, $f_s / N_H$ for a signal sampled at $f_s$
  with hop length $N_H$.

frame-based processing
  A family of techniques that chop audio into chunks called frames and analyze
  or manipulate those frames. It lets us work at musically intuitive rates of
  tens to hundreds of times per second.

frequency
  The number of cycles a periodic signal completes per second, measured in
  Hertz. The fundamental frequency is the reciprocal of the fundamental period,
  $f_0 = 1/t_0$, and is the property most strongly tied to perceived pitch.

frequency domain
  A view of a sound in terms of how much of each frequency it contains, such as
  its amplitude spectrum. It complements the time-domain waveform $x(t)$.

frequency modulation
  Synthesis in which a modulator varies the carrier's frequency over time,
  giving $\sin(2\pi f_c t + \frac{D}{f_m} \sin(2\pi f_m t))$. At audio rates it
  creates a theoretically infinite series of sidebands at $f_c \pm k f_m$ from
  just two oscillators.

fundamental period
  The smallest positive $T$ for which a periodic signal satisfies
  $x(t + T) = x(t)$, written $t_0$. It is the duration of one cycle.

grain
  A tiny slice of sound, typically tens of milliseconds long, used as the
  building block of granular synthesis.

granular synthesis
  Chopping a sound into many grains, then transforming and rearranging them
  (changing their order, amplitude, duration, pitch, or density) to build a
  new sound.

Hann window
  A window shaped like a raised cosine that tapers smoothly from zero at both
  ends to a peak in the middle. Its spectrum has much smaller side lobes than
  the rectangular window's, so it causes less spectral leakage.

Hertz
  The unit of frequency, abbreviated Hz. One hertz is one cycle per second.

high-pass
  A filter that passes frequencies above its cutoff and rejects those below,
  for example to remove low-frequency rumble.

hop length
  The spacing $N_H$, in samples, between the start of one frame and the start
  of the next.

impulse response
  A filter's output when fed the unit impulse $\delta$. It fully characterizes
  an LTI filter, and for the convolution $h * x$ it is just $h$.

impulse train
  A function that is 1 at every sampling instant $t = n/f_s$ and 0 everywhere
  else, written $\text{Ш}_{f_s}(t)$. Sampling can be modeled as multiplying a
  signal by an impulse train.

index of modulation
  In frequency modulation, the unitless ratio $I = D/f_m$ of the depth to the
  modulating frequency. Larger $I$ spreads energy into more sidebands, with
  roughly $I + 1$ audible on each side of the carrier.

infinite impulse response
  IIR, an impulse response that never ends. Recursive filters generally have
  one because feedback keeps copying past outputs forward.

initial phase
  The constant offset $\phi$, in radians, that shifts where a sinusoid starts
  within its cycle. Changing it has almost no audible effect.

instantaneous phase
  The total phase of a sinusoid at time $t$, $\theta(t) = \omega t + \phi$, in
  radians. It grows by $2\pi$ every period, and the sinusoid can be written
  $x(t) = a \sin(\theta(t))$.

inverse DFT
  The IDFT, which exactly reconstructs $N$ time-domain samples from $N$ DFT
  coefficients via
  $\texttt{IDFT}(X)[n] = \frac{1}{N}\sum_{k=0}^{N-1} X[k]\, e^{+2\pi j k n / N}$.

inverse FFT
  The IFFT, a fast algorithm that computes the inverse DFT in $O(N \log N)$
  time using the same divide-and-conquer strategy as the FFT.

Karplus-Strong algorithm
  A plucked-string synthesis algorithm that fills a feedback delay line with a
  burst of white noise and recirculates it through a low-pass filter and a
  gain, $y[n] = x[n] + g \cdot \tfrac{1}{2}(y[n - M] + y[n - M - 1])$. The
  delay $M = \mathrm{round}(f_s / f)$ sets the pitch.

linear
  A property of a filter $g$ that respects gain and mixing, so
  $g(A x) = A\, g(x)$ and $g(x_1 + x_2) = g(x_1) + g(x_2)$.

linear time-invariant
  Describes a filter (LTI) that is both linear and time-invariant. LTI filters
  can only boost or attenuate frequencies already present, and every LTI filter
  is a convolution with its impulse response.

low-pass
  A filter that passes frequencies below its cutoff and rejects those above,
  making a sound darker or more muffled.

mode of oscillation
  A standing wave that an object supports. On a string of length $L$ with
  fixed ends, the modes have wavelengths $\lambda_i = \frac{2L}{i}$ and
  frequencies $f_i = i \cdot \frac{v}{2L}$, which are harmonics.

modulating frequency
  In modulation synthesis, the frequency of the modulator, the signal that
  alters the carrier. Written $\omega_m$ in radians per second or $f_m$ in Hz.

modulation synthesis
  A family of techniques that affect a property of one signal, the carrier, with
  another oscillating signal, the modulator. It produces rich, time-varying
  spectra from only a few oscillators.

multisampling
  Recording an instrument at several pitches across its range and repitching
  whichever recording is closest to the target pitch. Keeping the shift small
  keeps the result realistic.

node
  A point on a standing wave that never moves. On a string, nodes occur every
  half wavelength, and fixed ends are always nodes.

notch
  Another name for a band-stop filter, especially one that removes a narrow
  band such as a single hum frequency.

Nyquist frequency
  Half the sampling rate, $f_s/2$. It is the highest frequency that can be
  unambiguously represented in a signal sampled at $f_s$.

Nyquist-Shannon sampling theorem
  The theorem that a signal with no content above $f_{\max}$ can be perfectly
  reconstructed from its samples, provided $f_s > 2 f_{\max}$.

order
  The number of samples of memory a filter needs, equal to the largest delay
  in its difference equation, $\max(M, L)$.

overlap
  The fraction of a frame shared with the next frame,
  $\frac{N_F - N_H}{N_F}$. It is non-zero when the hop length is shorter than
  the frame length.

overlap-add
  Reassembling a signal from frames by shifting each frame $x_k$ back to its
  position $k \cdot N_H$ and summing,
  $\hat{x}[n] = \sum_k x_k[n - k \cdot N_H]$.

passband
  The range of frequencies that a filter lets through.

periodic
  A signal $x(t)$ is periodic if it repeats exactly after some fixed time
  $T > 0$, so that $x(t + T) = x(t)$ for all $t$.

phase
  A sinusoid's position within its cycle, measured in radians. The book
  distinguishes the constant initial phase $\phi$ from the time-varying
  instantaneous phase $\theta(t)$.

phase increment
  In wavetable synthesis, how far the read position advances through the table
  per output sample, $\Delta m = f_0 M / f_s$. It is usually not an integer, so
  reads often land between table entries.

phase spectrum
  The angle $\angle X(\omega)$ of the Fourier transform, giving the phase of
  each frequency component in $(-\pi, \pi]$. It matters mainly when
  reconstructing a signal from its spectrum.

phase vocoder
  A spectral-processing algorithm that time-stretches audio without changing
  its pitch by interpolating STFT frames. It resolves the $2\pi$ ambiguity in
  each bin's phase by predicting how much the phase should advance over one
  hop.

phasor
  Another name for a complex sinusoid $a e^{j\omega t}$, pictured as a vector of
  length $a$ rotating counterclockwise once every $1/f$ seconds. Like the basic
  sinusoid, it is a function of time.

physical modeling synthesis
  Synthesizing sound by directly simulating the physics of an instrument, so
  that properties like harmonics emerge on their own instead of being
  synthesized explicitly.

pitch class
  The set of all frequencies separated from $f$ by whole numbers of octaves,
  $\{f \cdot 2^i \mid i \in \mathbb{Z}\}$. Listeners hear its members as the
  same note in different registers.

polar form
  Writing a complex number by its magnitude $r$ and angle $\theta$, as
  $z = r e^{j\theta}$. In polar form, multiplication multiplies magnitudes and
  adds angles.

polyphonic
  Having many notes sound at the same time. A score represents this with
  multiple events that share a timestamp.

quality factor
  Written $Q$, a measure of a band filter's selectivity, equal to center
  frequency over bandwidth, $Q = f_C / (f_H - f_L)$. A high $Q$ gives a narrow
  resonant peak and a low $Q$ a broad, gentle one.

quantization
  Rounding each sample to one of a finite set of levels so it can be stored in
  $b$ bits. Unlike sampling, it is lossy and cannot be undone.

quantization noise
  The irreversible rounding error introduced by quantization, heard as noise.
  Each additional bit halves it, lowering it by about 6 dB.

rectangular form
  Writing a complex number as $z = x + jy$, with real part $x$ and imaginary
  part $y$. Also called Cartesian form.

rectangular window
  The simplest window, equal to 1 on the interval of interest and 0 outside.
  Analyzing any finite stretch of audio implicitly applies one, and its abrupt
  edges cause strong spectral leakage.

recursive filter
  A filter whose difference equation also uses past outputs $y[n-j]$, not just
  inputs. Feedback lets it achieve good frequency responses with few
  coefficients, but its impulse response is generally infinite.

resampling
  Changing the sample rate of already-sampled audio by reading it at
  interpolated fractional positions. Lowering the rate requires anti-alias
  filtering first.

Riemann sum
  An approximation of an integral as a sum of thin rectangles. The book uses it
  to turn the phase integral $\int_0^t \omega(\tau)\, d\tau$ into the running
  sum $\theta[n] = \theta[n-1] + \omega[n]\,\Delta t$ over samples.

ring modulation
  Multiplying two sinusoids, $\sin(\omega_c t) \sin(\omega_m t)$. The result
  contains sidebands at the sum and difference frequencies
  $\omega_c \pm \omega_m$, while the original frequencies disappear. Slow
  modulation is heard as tremolo.

sample-based synthesis
  Pre-recording musical material and manipulating it on the fly to change its
  expressive parameters, such as pitch, duration, and loudness. It sounds
  realistic and is cheap to compute, but uses a lot of memory.

sampling
  In the musical sense, lifting a clip of audio (a sample) from one recording
  and reusing it in another context, often with some manipulation. This is
  distinct from digital sampling in analog-to-digital conversion.

sampling rate
  The number of samples recorded per second, $f_s$. Sampling a continuous
  signal $x(t)$ gives $x[n] = x(n/f_s)$.

score
  A symbolic description of music as a set of timed events. In Pyquist a score
  is a list of events, and it says when sounds happen while instruments decide
  what they sound like.

semitone
  A relative pitch unit, also called a step. Raising a frequency by $k$
  semitones multiplies it by $2^{k/12}$, so 12 semitones make an octave.

sequencing
  Playing samples back in different orders or with different timing than in
  their original recordings, as when building new beats from fragments of old
  ones.

short-time Fourier transform
  The DFT of each frame of a signal, which shows how its frequency content
  evolves over time. Abbreviated STFT, it is invertible via overlap-add.

sideband
  New frequency content that modulation creates on either side of a carrier.
  Ring and amplitude modulation produce two sidebands at $\omega_c \pm \omega_m$,
  while frequency modulation produces a whole series at $f_c \pm k f_m$.

signal-flow diagram
  A directed graph showing how signals move through a system. Processing
  elements such as unit generators, multipliers, summing junctions, or delay
  blocks are connected by wires that carry signals between them.

spectral leakage
  The smearing of each true frequency into neighboring frequencies that comes
  from analyzing a finite, windowed slice of a signal. It happens because the
  spectrum is convolved with the window's own spectrum.

spectral processing
  Transforming a sound into the time-frequency domain with the STFT, editing
  the spectral coefficients, and transforming back with the inverse STFT.

spectrogram
  A two-dimensional image of the STFT magnitudes, with time on the horizontal
  axis, frequency on the vertical axis, and amplitude (usually in log scale)
  shown as color.

standing wave
  A wave that oscillates in place rather than traveling. It forms when waves
  traveling in opposite directions, such as reflections on a string fixed at
  both ends, superimpose.

stopband
  The range of frequencies that a filter rejects.

subtractive synthesis
  Synthesis that starts from a harmonically rich source, such as noise or a
  sawtooth, and carves away frequencies with filters (often time-varying) to
  shape a timbre.

superposition
  The principle that when two waves overlap, the displacement of the medium
  at each point is the sum of their individual displacements. It is a physical
  example of linearity.

sustain loop
  A section $[t_s, t_e)$ of a recording's sustain that is repeated as many
  times as needed to lengthen a note, while the attack and release play once.

tempo
  The rate of beats, usually measured in beats per minute (BPM).

timbre
  The attributes of a sound that let us recognize it as a distinct instrument
  or component, independent of pitch and loudness. In additive synthesis it is
  shaped mainly by the relative amplitudes of the harmonics.

time domain
  A view of a sound as a waveform $x(t)$ that gives its amplitude at each
  instant. It mirrors how sound physically reaches our ears or microphones.

time stretching
  Changing the duration (and hence playback speed) of audio without changing
  its pitch. Granular synthesis does this by reassembling grains at a different
  hop length than the one used to extract them.

time-invariant
  A property of a filter for which delaying the input simply delays the output
  by the same amount, so filtering and delaying can happen in either order.

transcription
  Converting audio into a symbolic representation of its notes, such as a
  score. A crude version picks the loudest pitch in each STFT frame.

transition band
  The region between a real filter's passband and stopband, where its response
  slides gradually from the cutoff level (such as $-6$ dB) down to a fully
  rejected level (such as $-60$ dB).

tremolo
  A performance technique that periodically varies a note's amplitude while
  keeping its pitch constant. It can be synthesized with slow ring or amplitude
  modulation.

unit generator
  A reusable function that produces or processes sound, such as an oscillator,
  an envelope, or a multiplier. Unit generators are combined into larger
  topologies to build instruments and effects.

unit impulse
  The signal $\delta = [1, 0, 0, \ldots]$, a single one followed by zeros. It
  is the identity for convolution, $\delta * x = x$.

unstable
  Describes a recursive filter whose impulse response grows without bound
  instead of decaying, as with $y[n] = x[n] + 1.1\, y[n-1]$.

vibrato
  A performance technique in which the fundamental frequency wavers
  periodically over time. It can be synthesized as frequency modulation with a
  slow, shallow modulator.

wagon-wheel effect
  A visual form of aliasing in which a spoked wheel on film appears to slow,
  stop, or spin backwards because the camera's frame rate samples its rotation
  too slowly.

wave
  A disturbance that transfers energy through a medium, like a string or the
  air. Each particle of the medium is displaced temporarily and returns to
  rest, so the disturbance travels but the medium does not.

wavelength
  The distance $\lambda$ a sinusoidal wave travels during one cycle, which is
  the distance between neighboring peaks. For frequency $f$ and speed $v$,
  $\lambda = \frac{v}{f}$.

wavetable
  An array of $M$ samples holding exactly one cycle of a waveform. It is
  computed once and then read repeatedly to produce a tone.

wavetable synthesis
  An efficient alternative to computing additive synthesis sample by sample.
  One cycle of the waveform is precomputed into a wavetable, which is then read
  repeatedly at the rate that gives the desired frequency.

white noise
  A random signal whose samples are independent and identically distributed
  with mean zero. Its spectrum is flat on average, so it excites all
  frequencies at once.

window
  A function that is zero outside an interval of interest and non-negative
  inside it. Multiplying a signal by a window restricts analysis, such as the
  DFT, to a finite segment.

zero-pad
  To fill missing samples with zeros, as when a final frame runs past the end
  of a signal.
:::
