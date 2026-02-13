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
        self.geometry_data = []

    def set_material_properties(self, td, tm, bd, bm):
        self.top_density = td
        self.top_modulus = tm
        self.back_density = bd
        self.back_modulus = bm

    def update_geometry(self, points: List[Point]):
        self.geometry_data = points

    def update_arching(self, top_points: List[Point], back_points: List[Point]):
        self.arching_data = (top_points, back_points)

    def predict(self, geometry_data: List[Point] = None) -> List[Dict[str, float]]:
        """
        Predicts acoustic modes based on geometry and material properties.
        A0 (Air) frequency depends on Volume (~Area * Height).
        B modes depend on stiffness (Height) and weight (Area).
        """
        if geometry_data is None: geometry_data = self.geometry_data
        if not geometry_data: return self.base_modes
            
        area = GeometryExtractor.calculate_area(geometry_data)
        
        # Get arching height
        if hasattr(self, 'arching_data'):
            top_pts, back_pts = self.arching_data
            h_top = GeometryExtractor.get_max_depth(top_pts)
            h_back = GeometryExtractor.get_max_depth(back_pts)
            height = (h_top + h_back) / 2.0
        else:
            height = 20.0 # Default
            
        # Normalization (based on approx scene coordinates: half-width ~120, height ~400)
        ref_area = 25000.0 # Approx area for a standard violin half-outline in scene units
        ref_height = 50.0   # Approx side-view height
        
        # Physics Heuristics:
        # Higher area = lower freq. Higher arch = higher freq.
        geom_factor = (height / ref_height)**0.7 * (ref_area / area)**0.5
        geom_factor = max(0.4, min(geom_factor, 2.5))
        
        # Material Factor
        ref_c = (10.0 / 450.0)**0.5
        c_avg = ((self.top_modulus/self.top_density)**0.5 + (self.back_modulus/self.back_density)**0.5) / 2.0
        material_factor = c_avg / ref_c
        
        total_scale_factor = geom_factor * material_factor
        
        predicted_modes = []
        # Specific shift for Air Mode (A0) - Volume sensitivity
        vol_factor = (ref_area * ref_height) / (area * height)
        a0_shift = vol_factor**0.4
        
        for i, mode in enumerate(self.base_modes):
            shift = a0_shift if i == 0 else total_scale_factor
            predicted_modes.append({
                'freq': mode['freq'] * shift,
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
