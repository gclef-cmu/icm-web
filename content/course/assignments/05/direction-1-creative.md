# Direction 1 (Creative): A 30-60s Song

The FM oscillators you implemented in Assignment 4 allow for much more sophisticated sounds than what you've previously seen in the course. You can now make instruments with vibrato, portamento, and time-varying timbre qualities. Using what you've learned about envelopes, additive synthesis, and FM modulation, you will create a 30-60s song with some creative intent behind it.

**Requirements**
- Define 2+ custom FM instruments which are meaningfully different from each other
- Configure your instruments to use time-varying parameters via envelopes or other oscillators
- At least one instrument should use vibrato, portamento, or tremolo
- Song must be 30 to 60 seconds in length
- In `CREATIVE.md`, include
  - A description of your song and the creative intent behind it
  - A description of your FM instruments and how you configured them to achieve your desired sound

**You May Use**
- The TheoryTab or FreeSound API
- Any outside sources of audio (found or recorded)
  - Any outside audio material you use must be properly cited in your submission
- AI to aid implementation (no generating songs with Suno, Udio, etc.)
- Any DAW or editing software may be used to arrange and add effects, however a non-trivial amount of the track must be rendered by executing your submitted code
  - Acceptable : Use Pyquist to generate stems for two FM voices, then add drums and reverb in the DAW
  - Unacceptable : Generate a single 2-second FM sound effect, import into Kontakt, and compose most of the music in the DAW
  

Need a good place to start?
- Experiment with strongly aliasing sidebands
- Use oscillators to make a spooky melody
- Make an instrument who's _timbre_ changes over time
- Write a song inspired by a daily activity
