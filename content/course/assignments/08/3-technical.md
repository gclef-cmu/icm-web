# Direction 3 (Technical): Analog Resurrection

:::{important}
**This is the most demanding direction of the three.** You will carry filter formulas between continuous and discrete time and debug polynomial algebra where a single flipped coefficient makes a filter subtly wrong. To keep the load fair, the starter notebook provides all four analog prototype formulas as working code; you implement the three functions that turn them into a running digital EQ.
:::

Alexander "Howard" Dumble hand-built around three hundred amplifiers, voiced each one for its player (John Mayer tours with one), and potted his circuit boards in opaque epoxy so nobody could copy them. He died in 2022 without publishing a single schematic, and a community of engineers now painstakingly dissolves the "goop" on broken units to trace the circuits before the sound is lost forever. Meanwhile the most recorded EQ in history, the **Neve 1073** (1970), still sells for thousands of dollars per module, yet you can buy one as a plugin for a hundredth of the price. How?

:::{figure}
![A Neve 80 series console next to the plugin version of its channel module](./assets/analog-to-plugin.png)

A Neve 80 series console at The Manor, Virgin's countryside studio, and the plugin recreation of its channel module, the 1073. Console photo by JacoTen, CC BY-SA 3.0. Plugin image from Universal Audio.
:::

The answer is a piece of math called the **bilinear transform**, which carries a system from continuous time into discrete time. An analog EQ is a real circuit: electricity flows smoothly through resistors and capacitors, and its voltage exists at every instant. That is _continuous time_, and a circuit living there is fully described by its **transfer function** `H(s)`, a formula you can work out from the circuit itself that says exactly how much it boosts or cuts each frequency. Your laptop never sees a smooth voltage. It sees 44,100 snapshots per second, a stream of plain numbers, which is _discrete time_. The bilinear transform converts `H(s)` into `H(z)`, a discrete-time system with the same response: a **digital EQ**, written as a _difference equation_, a short loop over the samples of a song that boosts and cuts exactly what the circuit did.

**Analog resurrection.** This is how companies like Universal Audio, Brainworx, and Neural DSP make their living: start from a revered circuit, work out its `H(s)`, and run it through the bilinear transform. In this direction you will build that pipeline yourself, an **analog-to-digital EQ compiler** that turns any cascade of analog filter sections into a running digital filter, and use it to resurrect a channel EQ modeled on the 1073.

:::{figure}
![Pipeline diagram of the analog-to-digital EQ compiler: an analog channel EQ becomes one transfer function per band, the bilinear transform carries each section into discrete time, and the sections combine into a single difference equation that filters the samples](./assets/analog-resurrection-pipeline.png)

The compiler: each band becomes an `H(s)`, the bilinear transform (with pre-warping) carries it to `H(z)`, and the sections combine into one difference equation. Red labels are the functions you write.
:::

**{download}`Download the starter notebook <./assets/8-3-eq.ipynb>`.** It contains the target EQ, the provided analog prototypes, a checkpoint for each of the three functions you write, verification scaffolding, and pointers for going further.

The notebook shows one good path through the topic, but this is an open-ended assignment: feel free to adjust it, restructure it, or leave it behind once you have ideas of your own. AI is allowed, and creativity is encouraged. **You do not submit the notebook.** Your deliverables are the standard open-ended technical format (demo video, `TECHNICAL.md`, and `src/`) described on the [Assignments page](../index.md#open-ended-submission-instructions-and-policies).

**Requirements**
- Write a `bilinear_transform` function that carries **one** analog section of **any order** into its digital `b` and `a` coefficients (the analog prototypes, including the third-order rumble filter, are provided; the notebook walks you through the recipe)
  - You must **pre-warp** the section's critical frequency so the digital response matches the analog response exactly at that frequency
- Write a function that **combines the cascade of digital sections into one difference equation** (the full `b` and `a` of `H(z)`)
- Write your **own difference-equation engine** (`apply_filter`) that runs any `(b, a)` filter over a signal, verified against theory by measuring its impulse response
- Verify your compiler with the four-way frequency-response comparison (the notebook provides the scaffolding)
- In `TECHNICAL.md`, include
  - An explanation of what `bilinear_transform` does to a section, and why **pre-warping** is necessary
  - An explanation of how you combined the sections into one difference equation
  - The verification plots

**You May Use**
- AI to aid implementation
- Online resources about the bilinear transform, EQ design, and biquad filters (please list them in your writeup), but note the starter notebook's warning about the Audio EQ Cookbook's pre-baked digital coefficients
- `numpy` for numerical routines such as polynomial multiplication (`np.convolve`), but no `scipy.signal` or other ready-made filtering/DSP libraries

All formulas, hints, and checkpoints are in the starter notebook.
