import numpy as np
import sounddevice as sd
import queue
import os
from typing import List, Dict
import threading
from scipy.signal import savgol_filter
from abc import ABC, abstractmethod

class ExcitationSource(ABC):
    @abstractmethod
    def generate(self, frames: int, frequency: float, sample_rate: float, bow_velocity: float, bow_force: float) -> np.ndarray:
        pass

class SawtoothSource(ExcitationSource):
    def __init__(self):
        self.phase = 0.0
        # DC blocker state
        self.dc_x_prev = 0.0
        self.dc_y_prev = 0.0

    def generate(self, frames: int, frequency: float, sample_rate: float, bow_velocity: float, bow_force: float) -> np.ndarray:
        t = np.arange(frames) / sample_rate
        phase_increments = frequency / sample_rate
        current_phases = self.phase + np.cumsum(np.ones(frames) * phase_increments) - phase_increments
        current_phases -= np.floor(current_phases)
        
        self.phase = (current_phases[-1] + phase_increments) % 1.0
        
        raw_saw = 2.0 * (current_phases - 0.5)
        # Match legacy boxcar filter
        source = np.convolve(raw_saw, np.ones(4)/4, mode='same')
        
        # DC Blocking Filter (High-pass IIR)
        # y[n] = x[n] - x[n-1] + 0.995 * y[n-1]
        output = np.zeros(frames)
        for i in range(frames):
            output[i] = source[i] - self.dc_x_prev + 0.995 * self.dc_y_prev
            self.dc_x_prev = source[i]
            self.dc_y_prev = output[i]
        
        # Use bow_velocity as gain for sawtooth baseline
        return output * bow_velocity

class WaveguideSource(ExcitationSource):
    def __init__(self, size=2048):
        self.upper = np.zeros(size)
        self.lower = np.zeros(size)
        self.v_c = 0.1
        self.mu_d = 0.01

    def generate(self, frames: int, frequency: float, sample_rate: float, bow_velocity: float, bow_force: float) -> np.ndarray:
        L = int(sample_rate / (2 * frequency))
        L = max(10, min(L, len(self.upper) - 1))
        
        output = np.zeros(frames)
        # Optimized inner loop
        for t in range(frames):
            # Delays
            u_temp = self.upper[0]
            self.upper[1:L] = self.upper[0:L-1]
            self.lower[0:L-1] = self.lower[1:L]
            
            # Refection
            self.upper[0] = -self.lower[0]
            self.lower[L-1] = -self.upper[L-1]
            
            # Friction at bow
            bow_pos = L // 4
            v_string = self.upper[bow_pos] + self.lower[bow_pos]
            v_rel = v_string - (bow_velocity * 0.2) # Scaled
            
            friction = v_rel * np.exp(-1.0 * (v_rel / self.v_c)**2) + self.mu_d
            force = friction * bow_force * 0.05
            
            self.upper[bow_pos] -= force
            self.lower[bow_pos] -= force
            
            output[t] = self.lower[L-1]
            
        return output * 50.0 # Gain compensation

class FDTDSource(ExcitationSource):
    def __init__(self, nodes=200):
        self.nodes = nodes
        self.u = np.zeros(nodes)
        self.u_prev = np.zeros(nodes)
        self.damping = 0.9995

    def generate(self, frames: int, frequency: float, sample_rate: float, bow_velocity: float, bow_force: float) -> np.ndarray:
        nodes = self.nodes
        dx = 1.0 / nodes
        dt = 1.0 / sample_rate
        c = 2.0 * frequency
        
        r2 = (c * dt / dx)**2
        if r2 > 1.0:
            r2 = 0.99
        
        output = np.zeros(frames)
        bow_idx = nodes // 4
        
        # Simplified excitation: velocity-driven force
        drive_strength = bow_velocity * bow_force * 0.5
        
        for t in range(frames):
            u_next = np.zeros(nodes)
            
            # Wave equation update
            u_next[1:-1] = (2 * self.u[1:-1] - self.u_prev[1:-1] + 
                            r2 * (self.u[2:] - 2 * self.u[1:-1] + self.u[:-2]))
            
            # Simple driving force at bow position
            u_next[bow_idx] += drive_strength * np.sin(2 * np.pi * frequency * t * dt)
            
            # Damping and boundaries
            u_next *= self.damping
            u_next[0] = 0
            u_next[-1] = 0
            
            self.u_prev[:] = self.u[:]
            self.u[:] = u_next[:]
            
            output[t] = self.u[-2]
            
        return output * 10000.0

class Synthesizer:
    def __init__(self, sample_rate=44100):
        self.sample_rate = sample_rate
        self.sample_count = 0
        self.frequency = 196.0 
        self.modes = []
        self.lock = threading.Lock()
        self.stream = None
        self.is_running = False
        self.audio_queue = queue.Queue(maxsize=10)
        self.response_mode = "MODEL" 
        self.noise_level = 0.0 
        self.smoothing_level = 0.0
        
        # Excitation Selection
        self.excitation_type = "sawtooth"
        self.excitation_sources = {
            "sawtooth": SawtoothSource(),
            "waveguide": WaveguideSource(),
            "fdtd": FDTDSource()
        }
        self.bow_velocity = 0.5
        self.bow_force = 0.5
        
        # High-pass filter state for removing sub-audio rumble
        self.hpf_x_prev = 0.0
        self.hpf_y_prev = 0.0
        
        # Sampled SPL Data
        self.sampled_spl = None
        self.raw_sampled_spl = None
        self.sampled_freqs = None
        self._load_sampled_spl()

    def _load_sampled_spl(self):
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            spl_file = os.path.join(base_dir, "spl.csv")
            if os.path.exists(spl_file):
                data = np.genfromtxt(spl_file, delimiter=',')
                valid_data = data[~np.isnan(data)]
                self.raw_sampled_spl = 10**((valid_data + 50.0) / 20.0)
                self.sampled_spl = self.raw_sampled_spl.copy()
                self.sampled_freqs = np.linspace(100, 8200, len(self.sampled_spl))
        except Exception as e:
            print(f"Synthesizer error loading spl.csv: {e}")

    def update_modes(self, modes: List[Dict[str, float]]):
        with self.lock:
            self.modes = modes
            
    def set_frequency(self, freq: float):
        with self.lock:
            self.frequency = freq

    def set_response_mode(self, mode: str):
        with self.lock:
            self.response_mode = mode

    def set_noise_level(self, level: float):
        with self.lock:
            self.noise_level = level

    def set_smoothing_level(self, level: float):
        with self.lock:
            self.smoothing_level = level

    def set_excitation_type(self, ext_type: str):
        with self.lock:
            self.excitation_type = ext_type

    def set_bow_params(self, velocity: float, force: float):
        with self.lock:
            self.bow_velocity = velocity
            self.bow_force = force

    def _audio_callback(self, outdata, frames, time, status):
        vibrato_speed = 5.5
        vibrato_depth = 0.0  # Disabled - was causing low-freq rumble when interacting with SPL filtering
        
        t_arr = (self.sample_count + np.arange(frames)) / self.sample_rate
        
        with self.lock:
            if isinstance(self.frequency, (list, tuple)):
                # Melody Mode: cycle through notes
                # note = (freq, duration_seconds)
                total_duration = sum(n[1] for n in self.frequency)
                current_time = (self.sample_count / self.sample_rate) % total_duration
                
                # Find current note
                elapsed = 0
                f_base = self.frequency[0][0]
                for freq, dur in self.frequency:
                    if elapsed <= current_time < elapsed + dur:
                        f_base = freq
                        break
                    elapsed += dur
            else:
                f_base = self.frequency

            vib = 1.0 + vibrato_depth * np.sin(2 * np.pi * vibrato_speed * t_arr)
            f_current = f_base * vib
            ext_type = self.excitation_type
            v_bow = self.bow_velocity
            f_bow = self.bow_force
            mode_choice = self.response_mode
            noise_val = self.noise_level
            smooth_val = self.smoothing_level
            current_modes = list(self.modes)
        
        # 1. Generate Excitation
        source_gen = self.excitation_sources.get(ext_type, self.excitation_sources["sawtooth"])
        source = source_gen.generate(frames, f_current[0], self.sample_rate, v_bow, f_bow)
        
        self.sample_count += frames

        # 2. Body Resonance Filtering (FFT Method)
        spectrum = np.fft.rfft(source)
        freqs = np.fft.rfftfreq(frames, 1/self.sample_rate)
        
        if mode_choice == "FLAT":
            # Flat line with slight realistic HF roll-off
            mag = (0.2 - 0.1 * (freqs / 10000.0)**2).astype(complex)
            response = mag
        elif mode_choice == "SAMPLED" and self.raw_sampled_spl is not None:
            mag_data = self.raw_sampled_spl.copy()
            if smooth_val > 0:
                window_size = int(smooth_val * 100)
                if window_size > 3:
                    if window_size % 2 == 0: window_size += 1
                    mag_data = savgol_filter(mag_data, window_size, 3)
            mag = np.interp(freqs, self.sampled_freqs, mag_data)
            
            # Physical Roll-off below 100Hz (Sampled data starts at 100Hz)
            f_floor = 100.0
            mask = freqs < f_floor
            if np.any(mask):
                mag[mask] *= (freqs[mask] / f_floor)**3
                
            response = mag.astype(complex) * 0.1
        else:
            # Physical Baseline: Low-Frequency high-pass roll-off for radiation
            f_hpf_floor = 200.0
            floor_mag = 0.05 * (freqs / f_hpf_floor)**2 / (1 + (freqs / f_hpf_floor)**2 + 1e-6)
            response = floor_mag.astype(complex)
            
            for mode in current_modes:
                fc, amp, damp = mode['freq'], mode['amp'], mode['damping']
                if fc > 20000: continue
                bw = damp * fc
                denominator = 1 + 1j * (freqs - fc) / (bw/2 + 1e-6)
                response += amp / denominator
            
            # Global Radiation High-Pass (Violin acts as a dipole/monopole with LF roll-off)
            # Targeted to hit approx -20dB at 100Hz
            f_rad = 400.0
            hp_roll = (freqs / f_rad)**3 / (1 + (freqs / f_rad)**3)
            response *= hp_roll

            if mode_choice == "NOISY" and noise_val > 0:
                noise = (np.random.rand(len(freqs)) - 0.5) * noise_val * 2.0
                response = response * (1.0 + noise)

            if smooth_val > 0:
                mag = np.abs(response)
                window_size = int(smooth_val * 100)
                if window_size > 3:
                    if window_size % 2 == 0: window_size += 1
                    mag_smoothed = savgol_filter(mag, window_size, 3)
                    phase = np.angle(response)
                    response = mag_smoothed * np.exp(1j * phase)

        filtered_spectrum = spectrum * response
        output_signal = np.fft.irfft(filtered_spectrum)
        
        # High-pass filter to remove sub-audio rumble and low-freq artifacts
        # First-order IIR: y[n] = x[n] - x[n-1] + alpha * y[n-1]
        # alpha = 0.994 gives cutoff ~40 Hz at 44.1kHz (well below G3 = 196 Hz)
        hpf_output = np.zeros(len(output_signal))
        for i in range(len(output_signal)):
            hpf_output[i] = output_signal[i] - self.hpf_x_prev + 0.994 * self.hpf_y_prev
            self.hpf_x_prev = output_signal[i]
            self.hpf_y_prev = hpf_output[i]
        output_signal = hpf_output
        
        # Normalization & Safe Limiting
        # Proactive normalization: scale UP if too quiet, but only if there's actual signal
        rms = np.sqrt(np.mean(output_signal**2))
        target_rms = 0.1
        if rms > 1e-6:
            output_signal = output_signal * (target_rms / (rms + 1e-9))
        elif rms > 0:
            # Avoid extreme boosting of silence
            output_signal = output_signal * (target_rms / (1e-6))
        
        output_signal = np.tanh(output_signal * 1.5) * 0.5
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
