import numpy as np
import sounddevice as sd
import queue
from typing import List, Dict
import threading

class Synthesizer:
    def __init__(self, sample_rate=44100):
        self.sample_rate = sample_rate
        self.phase = 0.0
        self.frequency = 196.0 # G3 string
        self.modes = []
        self.lock = threading.Lock()
        self.stream = None
        self.is_running = False

    def update_modes(self, modes: List[Dict[str, float]]):
        """
        Update the filter modes in a thread-safe way.
        """
        with self.lock:
            self.modes = modes

    def _audio_callback(self, outdata, frames, time, status):
        if status:
            print(status)
            
        # Generate Sawtooth Wave
        t = (np.arange(frames) + self.phase) / self.sample_rate
        # Simple sawtooth: 2 * (t * f - floor(t * f + 0.5))
        # Or using numpy's mod:
        phase_increment = self.frequency / self.sample_rate
        
        # Vectorized sawtooth generation
        # We need to maintain phase continuity across callbacks
        # phase goes from 0 to 1
        
        # Create a time array for this block
        t_block = np.arange(frames) * phase_increment
        current_phases = self.phase + t_block
        current_phases -= np.floor(current_phases) # Wrap to [0, 1)
        
        # Sawtooth: map [0, 1) to [-1, 1]
        waveform = 2.0 * (current_phases - 0.5)
        
        # Update global phase for next callback
        self.phase += frames * phase_increment
        self.phase -= np.floor(self.phase)

        # Apply Filter Bank (Mock Implementation)
        # In a real DSP context, we'd use biquad filters or convolution.
        # For this prototype, to keep it simple and fast in Python without heavy DSP libs,
        # we will simulate the effect by adding sine waves at the mode frequencies (Resonators)
        # driven by the sawtooth, OR just summing sine waves if the sawtooth is too harsh unfiltered.
        # BUT, the requirement asks for "Filter: Apply a filter bank...".
        # Let's try a simple additive synthesis approach weighted by the sawtooth spectrum 
        # to simulate "filtering" a source, OR just implement a simple IIR filter if possible.
        
        # Let's stick to the requirement: Source = Sawtooth. Filter = Modes.
        # Implementing a full IIR filter bank in Python callback might be slow.
        # Let's do a simplified approach: 
        # The output is the Sawtooth + Resonance Sine Waves triggered by it? 
        # No, that's not filtering.
        
        # Let's implement a simple resonant filter effect.
        # Since we want to "hear" the modes, let's just add sine waves at the mode frequencies
        # but modulate their amplitude by the sawtooth's spectral envelope?
        # Or simpler: Just synthesize the modes directly as if they were being excited.
        # 
        # HOWEVER, the prompt says: "Source: Generate a Sawtooth... Filter: Apply a filter bank".
        # Let's try to do it properly but efficiently.
        # We can use a simple 1-pole lowpass or bandpass for each mode? No, that's too much math for python callback.
        
        # ALTERNATIVE:
        # Generate the sound as a sum of sine waves (additive synthesis) where the frequencies are the modes.
        # This is "Physical Modeling" in a way.
        # But to strictly follow "Sawtooth + Filter":
        # Let's generate the sawtooth, convert to frequency domain? No, latency.
        
        # Let's go with: Output = Sawtooth * 0.2 + Sum(Resonators).
        # A resonator at freq F with damping D can be approximated by a Sine wave at F 
        # that decays? No, continuous excitation.
        
        # Let's just implement a simple parametric EQ effect?
        # Too complex for scratch.
        
        # DECISION:
        # I will implement a "Modal Synthesizer". 
        # The "Sawtooth" represents the slip-stick motion.
        # The "Modes" are the body resonances.
        # I will approximate the filtered sound by summing sine waves at the mode frequencies,
        # but their amplitude is determined by how close they are to the harmonics of the sawtooth.
        # This simulates the source-filter interaction.
        
        output_signal = waveform * 0.1 # Dry signal
        
        with self.lock:
            current_modes = self.modes

        # Add resonances
        # To make it efficient, we pre-calculate or just do it for a few modes.
        # We have 5-10 modes.
        
        # Actually, let's just add sine waves for the modes to ensure they are audible.
        # This is a "Modal Synthesis" approach where the modes are the oscillators.
        # It satisfies the "hear the physics" requirement best.
        # The "Sawtooth" requirement might be to ensure there's a rich spectrum input.
        # I'll mix the sawtooth with the mode frequencies.
        
        if current_modes:
            t_vec = (np.arange(frames) + (time.inputBufferAdcTime if time else 0)) / self.sample_rate
            # We can't use absolute time easily for phase continuity of multiple oscillators without state.
            # So let's just use a random phase or keep state for each mode? 
            # Keeping state is better.
            
            # For the prototype, let's just do a simple ring modulation or addition
            # to color the sound.
            
            # Let's try a very simple IIR filter for one main mode (the "air" mode)
            # y[n] = x[n] + a * y[n-1] ... 
            # Too slow in pure Python loop.
            
            # Vectorized approach for "Filtering":
            # FFT -> Apply spectral mask -> IFFT
            # This adds latency but is fast in numpy.
            # Frame size is usually small (e.g. 512 or 1024).
            
            # Let's use FFT convolution for the filter.
            # 1. FFT the sawtooth chunk.
            # 2. Create a frequency response from modes.
            # 3. Multiply.
            # 4. IFFT.
            
            # To avoid overlap-add complexity for this prototype, 
            # let's just do the "Additive Synthesis based on Modes" approach.
            # It's computationally cheaper and guarantees audible pitch changes.
            
            # Re-interpreting "Filter":
            # The user wants to hear the body modes change.
            # I will generate the mode frequencies directly.
            # It sounds like a "ringing" body.
            
            mixed_signal = np.zeros(frames)
            
            # Create a local time vector for this block to keep phases somewhat aligned?
            # No, we need persistent phase for each mode to avoid clicks.
            # This is getting complicated for a single file.
            
            # SIMPLIFICATION:
            # Just modulate the Sawtooth amplitude with a low frequency sine based on the first mode?
            # No, that's tremolo.
            
            # Let's stick to the FFT approach, it's robust for "shaping" timbre.
            # We'll ignore windowing artifacts for the prototype.
            
            spectrum = np.fft.rfft(waveform)
            freqs = np.fft.rfftfreq(frames, 1/self.sample_rate)
            
            # Build filter response
            response = np.ones_like(freqs, dtype=complex)
            
            for mode in current_modes:
                f_c = mode['freq']
                amp = mode['amp']
                bw = mode['damping'] * f_c # Bandwidth
                
                # Simple Lorentzian (Resonance) curve
                # 1 / (1 + j * (f - fc) / (bw/2))
                # Avoid division by zero
                denominator = 1 + 1j * (freqs - f_c) / (bw/2 + 1e-6)
                response += amp / denominator
                
            filtered_spectrum = spectrum * response
            filtered_waveform = np.fft.irfft(filtered_spectrum)
            
            # Normalize
            if np.max(np.abs(filtered_waveform)) > 0:
                filtered_waveform = filtered_waveform / np.max(np.abs(filtered_waveform)) * 0.5
                
            output_signal = filtered_waveform

        # Reshape for sounddevice (frames, channels)
        outdata[:] = output_signal.reshape(-1, 1)

    def start(self):
        if self.is_running:
            return
        self.stream = sd.OutputStream(
            channels=1, 
            callback=self._audio_callback,
            samplerate=self.sample_rate,
            blocksize=2048 # Larger block size for FFT stability
        )
        self.stream.start()
        self.is_running = True

    def stop(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
        self.is_running = False
