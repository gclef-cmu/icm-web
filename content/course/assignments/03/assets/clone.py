"""Assignment 3 (Technical Track), authored by [your AndrewID] for 15-322 at Carnegie Mellon University
"""
import pyquist as pq 

# Your implementation goes here! Follow the steps in the assignment instructions. 

def cloned_instrument(pitch : float, duration : float, sample_rate : int = 44100, **kwargs) -> pq.Audio:
   raise NotImplementedError("Implement your cloned instrument here!")



# When you're ready, call this function to hear your instrument play a song! 
# We have left the harmony score untouched, but you're welcome to render it as well.
def play_song():
    from pyquist.web import theorytab 
    (metronome, score, harmony) = theorytab.fetch_theorytab("https://hookpad.hooktheory.com/?idOfSong=d_gw_QPzrgG")
    audio = score.render(cloned_instrument, metronome=metronome)
    audio.write("song.wav")
    pq.play(audio)
    
    
play_song()