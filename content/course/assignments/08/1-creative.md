# Direction 1 (Creative): A 30-60s Song with a Real-World Impulse Response

In Assignment 6 you learned how convolution, the Fourier transform, and filters let you reshape sound. Convolution in particular gives us **convolution reverb**: if you capture the _impulse response_ (IR) of a real acoustic space, you can convolve any audio with that IR to make it sound as though it were played in that space. In this direction you will go out and capture an IR from a specific spot on campus, then build a 30-60s composition around it.

**Capture your impulse response under the circle dome in Baker Hall.** The dome is one of the most reverberant, acoustically distinctive spaces on campus, and it is the required recording location for this assignment.

<!-- TODO: add photo of the circle dome in Baker Hall (assets/baker-dome.jpg) -->

To capture an IR, generate a short, broadband excitation under the dome (a sine sweep played from a speaker, or a sharp impulse like a balloon pop or hand clap) and record the result. See the Assignment 6 notebook and [resources](../../resources/index.md) for guidance on turning a recording into a usable IR.

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
