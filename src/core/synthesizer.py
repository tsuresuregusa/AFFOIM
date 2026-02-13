import numpy as np
import sounddevice as sd
import queue
from typing import List, Dict
import threading

class Synthesizer:
    def __init__(self, sample_rate=44100):
        self.sample_rate = sample_rate
        self.phase = 0.0
        self.sample_count = 0
        self.frequency = 196.0 # G3 string
        self.modes = []
        self.lock = threading.Lock()
        self.stream = None
        self.is_running = False
        self.audio_queue = queue.Queue(maxsize=10)

    def update_modes(self, modes: List[Dict[str, float]]):
        with self.lock:
            self.modes = modes

    def _audio_callback(self, outdata, frames, time, status):
        # 1. Fundamental frequency with Vibrato
        vibrato_speed = 5.5 # Hz
        vibrato_depth = 0.006 # Semi-tone depth approx
        
        # Temporal LFO
        t = (self.sample_count + np.arange(frames)) / self.sample_rate
        vib = 1.0 + vibrato_depth * np.sin(2 * np.pi * vibrato_speed * t)
        f_current = self.frequency * vib
        
        # Vectorized phase integration
        phase_increments = f_current / self.sample_rate
        current_phases = self.phase + np.cumsum(phase_increments) - phase_increments[0]
        current_phases -= np.floor(current_phases)
        
        # Update state
        self.phase = (current_phases[-1] + phase_increments[-1]) % 1.0
        self.sample_count += frames

        # Source: Bowed Sawtooth (Sawtooth + Low Pass tilt)
        raw_saw = 2.0 * (current_phases - 0.5)
        source = np.convolve(raw_saw, np.ones(4)/4, mode='same')

        # 2. Body Resonance Filtering (FFT Method)
        spectrum = np.fft.rfft(source)
        freqs = np.fft.rfftfreq(frames, 1/self.sample_rate)
        response = np.ones_like(freqs, dtype=complex) * 0.1 # Constant floor
        
        with self.lock:
            for mode in self.modes:
                fc, amp, damp = mode['freq'], mode['amp'], mode['damping']
                bw = damp * fc
                # Lorentzian resonance
                # H(f) = amp / (1 + j * (f - fc) / (bw/2))
                denominator = 1 + 1j * (freqs - fc) / (bw/2 + 1e-6)
                response += amp / denominator
                
        filtered_spectrum = spectrum * response
        output_signal = np.fft.irfft(filtered_spectrum)
        
        # Soft Clipping / Normalization to avoid ear-piercing peaks
        max_val = np.max(np.abs(output_signal))
        if max_val > 0.5:
            output_signal = (output_signal / max_val) * 0.5
            
        outdata[:] = output_signal.reshape(-1, 1)
        
        try:
            self.audio_queue.put_nowait(output_signal.copy())
        except queue.Full:
            pass

    def get_audio_chunk(self):
        try:
            return self.audio_queue.get_nowait()
        except queue.Empty:
            return None

    def start(self):
        if self.is_running: return
        self.stream = sd.OutputStream(
            channels=1, 
            callback=self._audio_callback,
            samplerate=self.sample_rate,
            blocksize=1024
        )
        self.stream.start()
        self.is_running = True

    def stop(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
        self.is_running = False
