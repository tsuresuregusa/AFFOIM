import numpy as np
from typing import List, Dict
from .geometry import Point, GeometryExtractor

class AcousticModel:
    def __init__(self):
        # Base modes for a generic violin plate (approximate)
        # Frequencies in Hz, Amplitudes relative, Damping ratio
        self.base_modes = [
            {'freq': 275.0, 'amp': 1.0, 'damping': 0.02}, # A0 (Air)
            {'freq': 450.0, 'amp': 0.8, 'damping': 0.03}, # B1-
            {'freq': 550.0, 'amp': 0.9, 'damping': 0.03}, # B1+
            {'freq': 800.0, 'amp': 0.5, 'damping': 0.04}, # C2
            {'freq': 1200.0, 'amp': 0.4, 'damping': 0.05} # D-modes
        ]
        # Default Material Properties
        self.top_density = 400.0
        self.top_modulus = 12.0
        self.back_density = 600.0
        self.back_modulus = 10.0

    def set_material_properties(self, td, tm, bd, bm):
        self.top_density = td
        self.top_modulus = tm
        self.back_density = bd
        self.back_modulus = bm

    def predict(self, geometry_data: List[Point]) -> List[Dict[str, float]]:
        """
        Predicts acoustic modes based on geometry and material properties.
        Frequency proportional to sqrt(E/rho).
        """
        c_bout_width = GeometryExtractor.calculate_c_bout_width(geometry_data)
        
        # Standard reference width (e.g., 100 units)
        reference_width = 100.0
        
        # Geometry Scaling factor
        geom_factor = reference_width / max(c_bout_width, 1.0)
        geom_factor = max(0.5, min(geom_factor, 2.0))
        
        # Material Factor: f ~ sqrt(E/rho)
        # We use a weighted average or simply average the factors for Top and Back
        ref_density = 450.0
        ref_modulus = 10.0
        ref_c = (ref_modulus / ref_density)**0.5
        
        # Calculate speed of sound for Top and Back
        c_top = (self.top_modulus / self.top_density)**0.5
        c_back = (self.back_modulus / self.back_density)**0.5
        
        # Average speed factor (simplified model)
        current_c = (c_top + c_back) / 2.0
        
        material_factor = current_c / ref_c
        
        total_scale_factor = geom_factor * material_factor
        
        predicted_modes = []
        for mode in self.base_modes:
            predicted_modes.append({
                'freq': mode['freq'] * total_scale_factor,
                'amp': mode['amp'],
                'damping': mode['damping']
            })
            
        return predicted_modes

    def calculate_spectrum(self, modes, f_min=100, f_max=5000, n_points=1000):
        """
        Calculates the frequency response spectrum (SPL) from the given modes.
        Returns (frequencies, magnitudes_db).
        """
        freqs = np.linspace(f_min, f_max, n_points)
        response = np.zeros_like(freqs, dtype=complex)
        
        for mode in modes:
            f0 = mode['freq']
            amp = mode['amp']
            gamma = mode['damping'] * f0 # Damping bandwidth approx
            
            # Simple Lorentzian resonance
            # H(f) = A / (f0^2 - f^2 + j*gamma*f)
            # Using a simplified form for visualization
            numerator = amp * f0**2
            denominator = (f0**2 - freqs**2) + 1j * gamma * freqs
            response += numerator / denominator
            
        magnitude = np.abs(response)
        # Avoid log(0)
        magnitude = np.maximum(magnitude, 1e-9)
        spl_db = 20 * np.log10(magnitude)
        
        return freqs, spl_db
