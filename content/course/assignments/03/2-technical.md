## Direction 2 (Technical): Clone an acoustic instrument using additive synthesis

Download the starter code file [clone.py](https://gclef-cmu.org/icm-autograde/f26/clone.py) (TODO : FIX LINK)

With your skills in additive synthesis, you're already able to create simple but convincing sounds that emulate a real instrument. In this direction you will choose an instrument sample, and use sound analysis tools and your existing knowledge in additive synthesis to recreate it.

To clone a **pitched** instrument using just additive synthesis, we need to recreate three behaviors: it's frequency spectrum, amplitude envelope, and fundamental frequency. We provide steps below on how to analyze these behaviors, but it's up to you to recreate them!

### Steps 
1. **Find a sound** on https://www.freesound.org/, or https://samplefocus.com. You want **one clean tone** of your desired instrument. That means it should be your instrument playing one note at a time, uninterrupted, and have no background noise. These aren't hard to find, but don't be afraid to go to "page 3" to find it -- a clean sound will be infinitely easier for the following steps. Can't find one? Use [violin](), or [flute]() as a starting point.
2. **Analyze the frequency spectrum** of your sound. Turn your sound into a pyquist Audio, either via the Freesound API, or `pq.Audio.from_file(fp)`. Then use `pq.plot.plot_spec(audio)` to visualize the frequency spectrum. You will want to identify the fundamental frequency, and the relative amplitudes of the harmonics. 
3. **Analyze the amplitude envelope** of your sound. Use `pq.plot.plot(audio)` to visualize the amplitude envelope. You should identify the attack, decay, sustain, and release times of the sound. This is more of an approximation than the frequency spectrum, but you should be able to get a good idea of how long each phase lasts.
4. **Implement your cloned instrument**. Using the information you gathered from the previous steps, implement your `cloned_instrument(pitch , duration, sample_rate, **kwargs) -> pq.Audio` function. You should be able to play a note at any frequency and duration, and have it sound like your instrument.
5. **Hear your instrument!** In the starter code, we have provided a function `play_song()` that will play a short song using your cloned instrument. You can use this to test your implementation, and make adjustments as needed. This function also outputs the required file `song.wav` for submission.

**Note**: some instruments are able to achieve "vibrato", or a slight oscillation in pitch. You cannot achieve this with additive synthesis itself, though you'll have the opportunity to implement it in Project 4! 

### Requirements
- Use the steps above to recreate the **pitched** instrument of your choice.
- Submit `clone.py` with your implementation of `cloned_instrument(pitch, duration, sample_rate **kwargs) -> pq.Audio`.
- Submit `song.wav`, which is the output of `play_song()`.
- Submit `source.wav`, which is the original sound you used to analyze your instrument.
- In `TECHNICAL.md`, include
  - The name of the instrument you chose to clone.
  - Any attributions required from the source sound.
  - A brief description of how you implemented your cloned instrument, including the frequency spectrum and amplitude envelope you analyzed, and how you used that information to implement your instrument.
