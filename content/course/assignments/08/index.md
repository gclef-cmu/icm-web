# Assignment 8\*: Exploring advanced topics I

This is an **open-ended** assignment. Review the open-ended submission
instructions and policies on the [Assignments page](../index.md) before you begin.

## Due: Mon Nov 02 2026 by 11:59PM Eastern

**Accomplish _either_ of the open-ended directions below.**

## Direction 1 (Creative): A 30-60s Song with a Real-World Impulse Response

In Assignment 6 you learned how convolution, the Fourier transform, and filters let you reshape sound. Convolution in particular gives us **convolution reverb**: if you capture the _impulse response_ (IR) of a real acoustic space, you can convolve any audio with that IR to make it sound as though it were played in that space. In this direction you will go out and capture an IR from a specific spot on campus, then build a 30-60s composition around it.

**Capture your impulse response under the circle dome in Baker Hall.** The dome is one of the most reverberant, acoustically distinctive spaces on campus, and it is the required recording location for this assignment.

<!-- TODO: add photo of the circle dome in Baker Hall (assets/baker-dome.jpg) -->

To capture an IR, generate a short, broadband excitation under the dome (a sine sweep played from a speaker, or a sharp impulse like a balloon pop or hand clap) and record the result. See the Autograded notebook and [resources](../../resources/index.md) for guidance on turning a recording into a usable IR.

**Requirements**
- Capture your own impulse response from under the circle dome in Baker Hall
- Use that impulse response as a **convolution reverb** on a meaningful portion of your composition
- Use at least one **filter** (e.g., an EQ, low-pass, high-pass, or band-pass) to shape the spectrum of your sound
- 30 to 60 seconds in length
- In `CREATIVE.md`, include
  - A description of your song and the creative intent behind it
  - A description of how you captured your impulse response (method, equipment, what you recorded)
  - A description of how you used convolution and filtering to achieve your desired sound

**You May Use**
- The TheoryTab or FreeSound API
- Any outside sources of audio (found or recorded)
  - Any outside audio material you use must be properly cited in your submission
- AI to aid implementation (no generating songs with Suno, Udio, etc.)
- Any DAW or editing software may be used to arrange and add effects, however a non-trivial amount of the track must be rendered by executing your submitted code
  - Acceptable: Use Pyquist to convolve your dry stems with your Baker dome IR and apply your own filters, then mix in a DAW
  - Unacceptable: Apply a stock convolution-reverb plugin in a DAW and compose the rest entirely outside of code

Need a good place to start?
- Record several different excitations (clap, balloon, sweep) and compare how their IRs color your sound
- Use a filter to carve space for the reverb tail so your mix doesn't get muddy
- Write a piece that leans into the long, washy reverb of the dome
- Contrast a dry, close sound against the same sound drenched in the dome's reverb

## Direction 2 (Technical): Analog Resurrection

Alexander "Howard" Dumble hand-built around three hundred amplifiers, voiced each one for its player (John Mayer tours with one), and potted his circuit boards in opaque epoxy so nobody could copy them. He died in 2022 without publishing a single schematic — and a community of engineers now painstakingly dissolves the "goop" on broken units to trace the circuits before the sound is lost forever. Meanwhile the most recorded EQ in history, the **Neve 1073** (1970), still sells for thousands of dollars per module — yet you can buy one as a plugin for a hundredth of the price. How?

**Analog resurrection.** Companies like Universal Audio, Brainworx, and Neural DSP make their living exactly this way: take a revered analog circuit, derive its continuous-time transfer function `H(s)`, and carry it across the bridge into the digital world — where it becomes a _difference equation_ your laptop can run. The bridge is the **bilinear transform**, and in this direction you will build the whole crossing yourself: an **analog-to-digital EQ compiler** that turns any cascade of analog filter sections into a running digital filter, demonstrated by resurrecting a channel EQ built in the image of the 1073. Every fact in this story is real, and so is the technique — this is not an imitation of what the pros do; it _is_ what the pros do.

**[Download the starter notebook](./assets/analog_resurrection.ipynb)** — it provides the story, the target EQ, step-by-step guidance and a checkpoint for every task, all the formulas you need, verification scaffolding, a numerical experiment where you get to watch a filter explode, and a listening test.

**Requirements**
- Implement the **normalized analog prototypes** (all formulas are given in the notebook): peaking, low-shelf, high-shelf, and Butterworth high-pass sections — including **third order** (the 1073's high-pass rolls off at 18 dB/octave; a biquads-only compiler can't build it)
- Write a `bilinear_transform` function that carries **one** analog section of **any order** into its digital `b` and `a` coefficients (the notebook walks you through the recipe)
  - You must **pre-warp** the section's critical frequency so the digital response matches the analog response exactly at that frequency
- Write a function that **combines the cascade of digital sections into one difference equation** (the full `b` and `a` of `H(z)`)
- Write your **own difference-equation engine** (`apply_filter`) that runs any `(b, a)` filter over a signal, verified against theory by measuring its impulse response
- Run the notebook's verification (four-way frequency-response comparison) and the coefficient-quantization experiment with your functions
- In `TECHNICAL.md`, include
  - An explanation of what `bilinear_transform` does to a section, and why **pre-warping** is necessary
  - An explanation of how you combined the sections into one difference equation, and your findings from the quantization experiment: **why** every real-world EQ runs as a cascade of second-order sections even though the combined form is mathematically identical
  - The verification and experiment plots

**You May Use**
- AI to aid implementation
- Online resources about the bilinear transform, EQ design, and biquad filters (please list them in your writeup) — but note the starter notebook's warning about the Audio EQ Cookbook's pre-baked digital coefficients
- `numpy` for numerical routines such as polynomial multiplication (`np.convolve`) — but no `scipy.signal` or other ready-made filtering/DSP libraries

All formulas, hints, checkpoints, and the listening test are in the starter notebook.

## Submission

1. First, confirm your submission formatting is valid via Gradescope: https://www.gradescope.com/courses/1326756/assignments/8238316
2. Then, submit the **Gradescope-verified zip file** to Google Forms: https://forms.gle/2qSfJsG3A2EdoJnU8

## Grading

For grading details, see the [open-ended grading policy](../index.md#open-ended-submission-instructions-and-policies) on the Assignments page.
