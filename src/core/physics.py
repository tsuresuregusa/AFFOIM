import numpy as np
import os
from typing import List, Dict
from .geometry import Point, GeometryExtractor
from scipy.signal import savgol_filter

class AcousticModel:
    """
    Physically-inspired acoustic model for violin-family instruments.
    Structured into 4 physical zones for interpretability:
    1. Body Modes: Discrete low-frequency resonances (A0, B1- etc.)
    2. Statistical Mixing: Overlapping dense modes (Wood/Body floor)
    3. Bridge Hill: Broad high-frequency resonance boost (2-5 kHz)
    4. HF Decay: Systemic air and material attenuation (> 5 kHz)
    """
    def __init__(self):
        # --- MATERIAL PROPERTIES (Baseline: Spruce/Maple) ---
        self.top_density = 400.0   # Rho (kg/m3)
        self.top_modulus = 12.0   # E (GPa)
        self.back_density = 600.0
        self.back_modulus = 10.0
        
        self.geometry_data = []
        self.arching_data = None
        
        # --- CALIBRATION CONSTANTS ---
        self.REF_AREA = 35000.0   # baseline Strad-ish area
        self.REF_DEPTH = 20.0    # baseline Strad-ish depth
        self.REF_VOL = self.REF_AREA * (30.0 + 0.66 * self.REF_DEPTH)
        
        # --- SAMPLED DATA ---
        self.sampled_spl = None
        self.raw_sampled_spl = None
        self.sampled_freqs = None
        self.smoothing_level = 0.0
        self._load_sampled_spl()

    def _load_sampled_spl(self):
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            spl_file = os.path.join(base_dir, "spl.csv")
            if os.path.exists(spl_file):
                data = np.genfromtxt(spl_file, delimiter=',')
                self.raw_sampled_spl = data[~np.isnan(data)] + 50.0
                self.sampled_spl = self.raw_sampled_spl.copy()
                self.sampled_freqs = np.linspace(100, 8200, len(self.sampled_spl))
        except Exception as e:
            print(f"Error loading spl.csv: {e}")

    def get_sampled_response(self, freqs):
        if self.sampled_spl is None:
            return np.ones_like(freqs) * -60.0 # Default low level
        
        data_to_interp = self.raw_sampled_spl.copy()
        if self.smoothing_level > 0:
            window_size = int(self.smoothing_level * 100)
            if window_size > 3:
                if window_size % 2 == 0: window_size += 1
                data_to_interp = savgol_filter(data_to_interp, window_size, 3)
                
        spl = np.interp(freqs, self.sampled_freqs, data_to_interp)
        
        # Physical Roll-off below 100Hz (Sampled data starts at 100Hz)
        f_floor = 100.0
        mask_lf = freqs < f_floor
        if np.any(mask_lf):
            att_lf = (freqs[mask_lf] / f_floor)**3
            spl[mask_lf] = 20 * np.log10(np.maximum(10**(spl[mask_lf]/20.0) * att_lf, 1e-6))
            
        # Physical Roll-off above 8200Hz (Sampled data ends at 8200Hz)
        f_ceil = 8200.0
        mask_hf = freqs > f_ceil
        if np.any(mask_hf):
            # Aggressive -24dB/oct roll-off
            att_hf = (f_ceil / freqs[mask_hf])**4
            spl[mask_hf] = 20 * np.log10(np.maximum(10**(spl[mask_hf]/20.0) * att_hf, 1e-6))
            
        return spl

    def update_geometry(self, points: List[Point]): self.geometry_data = points
    def update_arching(self, t_pts: List[Point], b_pts: List[Point]): self.arching_data = (t_pts, b_pts)
    def set_smoothing_level(self, level): self.smoothing_level = level
    def set_material_properties(self, td, tm, bd, bm):
        self.top_density, self.top_modulus = td, tm
        self.back_density, self.back_modulus = bd, bm

    def _calculate_physical_shifts(self, geometry_data):
        """Calculates frequency shifts based on volume (Helmholtz) and geometry (Bending)."""
        h_pix = max(10, max(p.y for p in geometry_data) - min(p.y for p in geometry_data))
        s_fact = 500.0 / h_pix
        area = GeometryExtractor.calculate_area(geometry_data, geometry_data[0].x) * (s_fact**2)
        
        if self.arching_data:
            h_t = GeometryExtractor.get_max_depth(self.arching_data[0])
            h_b = GeometryExtractor.get_max_depth(self.arching_data[1])
            depth = ((h_t + h_b) / 2.0) * s_fact
        else:
            depth = self.REF_DEPTH
            
        actual_vol = area * (30.0 + 0.66 * depth)
        
        # Volume Shift (Inverse sqrt of volume)
        h_shift = (self.REF_VOL / max(100000, actual_vol))**0.5
        h_shift = np.clip(h_shift, 0.6, 1.4)
        
        # Bending Shift (Stiffness/Mass from geometry)
        b_shift = (depth / self.REF_DEPTH) * (self.REF_AREA / max(10000, area))**0.5
        b_shift = np.clip(b_shift, 0.5, 2.0)
        
        # Material Shift (Sqrt(E/Rho))
        f_top = (self.top_modulus / 12.0 * 400.0 / max(1, self.top_density))**0.5
        f_back = (self.back_modulus / 10.0 * 600.0 / max(1, self.back_density))**0.5
        m_shift = 0.6 * f_top + 0.4 * f_back
        
        return h_shift, b_shift, m_shift

    def predict(self, geometry_data: List[Point] = None) -> List[Dict[str, float]]:
        """Orchestrates modal prediction across the 4 acoustic zones."""
        if geometry_data is None: geometry_data = self.geometry_data
        if not geometry_data: return []
            
        h_shift, b_shift, m_shift = self._calculate_physical_shifts(geometry_data)
        modes = []

        # --- ZONE 1: BODY MODES (< 1 kHz) ---
        # Signature modes: A0 (Helmholtz), B1-, B1+
        body_modes = [
            {'freq': 330.0, 'amp': 8.5,  'damp': 0.08, 'type': 'A0'},
            {'freq': 550.0, 'amp': 2.2, 'damp': 0.025, 'type': 'B1-'},
            {'freq': 670.0, 'amp': 5.0,  'damp': 0.05, 'type': 'B1+'},
        ]
        for m in body_modes:
            if m['type'] == 'A0':
                f = m['freq'] * h_shift * (m_shift**0.3)
            else:
                f = m['freq'] * b_shift * m_shift
            modes.append({'freq': f, 'amp': m['amp'], 'damping': m['damp']})

        # --- ZONE 2: STATISTICAL MIXING (1 - 2.5 kHz) ---
        # Dense body resonances forming the "timbre floor"
        mixing_modes = [916, 980, 1065, 1168, 1924, 1939, 2138]
        for f_base in mixing_modes:
            f = 1.5 * f_base * b_shift * m_shift
            modes.append({'freq': f, 'amp': 0.5, 'damping': 0.05})

        # --- ZONE 3: BRIDGE HILL (2.5 - 5 kHz) ---
        # Broad resonance boost from bridge/body coupling.
        # Uses multiple overlapping modes to ensure a smooth "hill".
        hill_center = 2500.0
        for f_base in np.linspace(2400, 4500, 8):
            f = f_base * b_shift * m_shift
            # Scaled amplitude with the bridge hill characteristic
            hill_boost = 1.0 + 1.5 * np.exp(-((f - hill_center)**2) / (2 * 1200**2))
            modes.append({'freq': f, 'amp': 0.3 * hill_boost, 'damping': 0.08})

        # --- ZONE 4: HF DECAY (> 5 kHz) ---
        # Systematic high-freq energy reduction
        hf_modes = [8500, 9500, 10500]
        for f_base in hf_modes:
            f = f_base * b_shift * m_shift
            decay = 1.0 / (1.0 + (f / 5000)**4)
            modes.append({'freq': f, 'amp': 0.2 * decay, 'damping': 0.12})

        return modes

    def calculate_spectrum(self, modes, f_min=100, f_max=10000, n_points=1200, mode="MODEL", noise_level=0.0):
        """
        Calculates the frequency response spectrum (SPL) from the given modes with physical radiation characteristics.
        """
        freqs = np.linspace(f_min, f_max, n_points)
        
        if mode == "FLAT":
            # Flat line with slight realistic HF roll-off
            spl_db = 20.0 - (freqs / 8000.0)**2
            return freqs, spl_db
            
        if mode == "SAMPLED":
            spl_db = self.get_sampled_response(freqs)
            return freqs, spl_db

        response = np.zeros_like(freqs, dtype=complex)
        
        # Physical Baseline: Low-Frequency high-pass roll-off for radiation
        # Instead of 0.05 flat, we use a 2nd order HPF floor characteristic
        f_hpf = 200.0
        floor_mag = 0.05 * (freqs / f_hpf)**2 / (1 + (freqs / f_hpf)**2 + 1e-6)
        response += floor_mag
        
        for mode_data in modes:
            f0 = mode_data['freq']
            amp = mode_data['amp']
            gamma = mode_data['damping'] * f0 
            
            numerator = amp * f0**2
            denominator = (f0**2 - freqs**2) + 1j * gamma * freqs
            response += numerator / denominator
            
        magnitude = np.abs(response)
        
        # Global Radiation High-Pass (Violin acts as a dipole/monopole with LF roll-off)
        # Targeted to hit approx -20dB at 100Hz
        f_rad = 400.0
        hp_roll = (freqs / f_rad)**3 / (1 + (freqs / f_rad)**3)
        magnitude *= hp_roll
        
        magnitude = np.maximum(magnitude, 1e-9)
        spl_db = 20 * np.log10(magnitude)
        
        # Apply noise if in NOISY mode
        if mode == "NOISY" and noise_level > 0:
            noise = (np.random.rand(len(freqs)) - 0.5) * noise_level * 20.0
            spl_db += noise
        
        if self.smoothing_level > 0:
            # Apply smoothing to the calculated spectrum too if desired
            window_size = int(self.smoothing_level * 100)
            if window_size > 3:
                if window_size % 2 == 0: window_size += 1
                spl_db = savgol_filter(spl_db, window_size, 3)
        
        return freqs, spl_db
