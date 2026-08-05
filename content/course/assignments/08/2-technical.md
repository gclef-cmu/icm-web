# Direction 2 (Technical): Analog Resurrection

Alexander "Howard" Dumble hand-built around three hundred amplifiers, voiced each one for its player (John Mayer tours with one), and potted his circuit boards in opaque epoxy so nobody could copy them. He died in 2022 without publishing a single schematic, and a community of engineers now painstakingly dissolves the "goop" on broken units to trace the circuits before the sound is lost forever. Meanwhile the most recorded EQ in history, the **Neve 1073** (1970), still sells for thousands of dollars per module, yet you can buy one as a plugin for a hundredth of the price. How?

The answer is a mathematical device called the **bilinear transform**: a transformation from continuous time to discrete time. What does that mean? An analog EQ is a real circuit: electricity flowing smoothly through resistors and capacitors, a voltage that exists at every instant. That smooth world is _continuous time_, and a circuit living there can be captured by its continuous-time **transfer function** `H(s)`: a formula, obtainable from the real circuit itself, that says exactly how much it boosts or cuts every frequency. Think of it as the mathematical fingerprint of the circuit's sound. Your laptop lives in a different world. It never sees a smooth voltage; it sees 44,100 snapshots per second, a stream of plain numbers: _discrete time_. Feed `H(s)` through the bilinear transform and out comes its discrete-time twin `H(z)`: a **digital EQ**, a _difference equation_, a short loop over the samples of a song that boosts and cuts exactly what the circuit did. Same tone, new body.

**Analog resurrection.** This is exactly how companies like Universal Audio, Brainworx, and Neural DSP make their living: start from a revered circuit, work out its `H(s)`, and carry it across the bridge into software. In this direction you will build the whole crossing yourself: an **analog-to-digital EQ compiler** that turns any cascade of analog filter sections into a running digital filter, demonstrated by resurrecting a channel EQ built in the image of the 1073. Every fact in this story is real, and so is the technique: this is not an imitation of what the pros do; it _is_ what the pros do.

**[Download the starter notebook](./assets/08-analog-resurrection/starter.zip)**. It provides the story, the target EQ, step-by-step guidance and a checkpoint for every task, all the formulas you need, verification scaffolding, a numerical experiment where you get to watch a filter explode, and a listening test.

The starter notebook is a guide, not a contract. It shows one good path through the topic, but this is an open-ended assignment: you may adjust the notebook, restructure it, or go beyond it as your own ideas take over; AI is allowed, and creativity is encouraged. **You do not submit the notebook.** Your deliverables are the standard open-ended technical format (demo video, `TECHNICAL.md`, and `src/`) described on the [Assignments page](../index.md#open-ended-submission-instructions-and-policies).

**Requirements**
- Implement the **normalized analog prototypes** (all formulas are given in the starter notebook): peaking, low-shelf, high-shelf, and Butterworth high-pass sections, including **third order** (the 1073's high-pass rolls off at 18 dB/octave; a biquads-only compiler can't build it)
- Write a `bilinear_transform` function that carries **one** analog section of **any order** into its digital `b` and `a` coefficients (the notebook walks you through the recipe)
  - You must **pre-warp** the section's critical frequency so the digital response matches the analog response exactly at that frequency
- Write a function that **combines the cascade of digital sections into one difference equation** (the full `b` and `a` of `H(z)`)
- Write your **own difference-equation engine** (`apply_filter`) that runs any `(b, a)` filter over a signal, verified against theory by measuring its impulse response
- Verify your compiler with a four-way frequency-response comparison and the coefficient-quantization experiment (the notebook provides scaffolding for both)
- In `TECHNICAL.md`, include
  - An explanation of what `bilinear_transform` does to a section, and why **pre-warping** is necessary
  - An explanation of how you combined the sections into one difference equation, and your findings from the quantization experiment: **why** every real-world EQ runs as a cascade of second-order sections even though the combined form is mathematically identical
  - The verification and experiment plots

**You May Use**
- AI to aid implementation
- Online resources about the bilinear transform, EQ design, and biquad filters (please list them in your writeup), but note the starter notebook's warning about the Audio EQ Cookbook's pre-baked digital coefficients
- `numpy` for numerical routines such as polynomial multiplication (`np.convolve`), but no `scipy.signal` or other ready-made filtering/DSP libraries

All formulas, hints, checkpoints, and the listening test are in the starter notebook.
