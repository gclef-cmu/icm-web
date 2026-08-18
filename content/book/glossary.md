# Glossary

An alphabetical reference of key terms used throughout the book. Terms marked
with the `{vocab}` role in the text link to their definition here. Entries are
sorted automatically, so this page doubles as the book's global index.

:::{glossary}
:sorted:

periodic
  A signal is periodic if it repeats at a fixed interval in time — that is,
  $x(t) = x(t + T)$ for some period $T$.

fundamental period
  The smallest strictly positive interval $t_0$ over which a periodic signal
  repeats; the duration of one cycle.

frequency
  The number of cycles a periodic signal completes per second, measured in
  hertz (Hz). It is the reciprocal of the fundamental period, $f = 1/t_0$.

amplitude
  The peak deviation of a waveform from its rest (zero) value.

harmonic
  A sinusoidal component whose frequency is an integer multiple of the
  fundamental frequency.

Fourier series
  The representation of a periodic signal as a sum of sinusoidal harmonics.

additive synthesis
  Building a complex tone by summing sinusoidal harmonics with chosen
  amplitudes.

timbre
  The tonal "color" of a sound — what distinguishes two tones of the same pitch
  and loudness, largely determined by the relative amplitudes of their
  harmonics.

Hertz
  The unit of frequency, abbreviated Hz; one hertz is one cycle per second.

basic sinusoid
  The most elementary periodic function, $x(t) = a \sin(2\pi f t + \phi)$. It
  sounds like a pure tone and is the building block from which all periodic
  sound can be composed.

angular frequency
  The rate of phase accumulation of a sinusoid of frequency $f$,
  $\omega = 2\pi f$, measured in radians per second.

phase
  A quantity characterizing the current position within a cycle of a sinusoid.

initial phase
  The constant offset $\phi$, in radians, that shifts a sinusoid's starting
  point within its cycle.

instantaneous phase
  The total phase of a sinusoid at time $t$, $\theta(t) = 2\pi f t + \phi
  = \omega t + \phi$, in radians.

wavetable
  An array storing a single cycle of a waveform, sampled at $M$ points, used to
  synthesize a tone by repeated lookup.

wavetable synthesis
  Synthesizing a tone efficiently by precomputing one cycle of a waveform as a
  wavetable, then reading through it repeatedly at the rate that yields the
  desired frequency.

phase increment
  In wavetable synthesis, how far the read position advances through the table
  per output sample.
:::
