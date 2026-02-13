import numpy as np
from scipy.interpolate import interp1d

class PlateGenerator:
    def __init__(self):
        pass

    def generate_mesh(self, outline_points, arch_points, resolution=100, spine_x=None):
        if not outline_points or not arch_points:
            return None, None, None

        # 1. Prepare Outline (Right Side)
        ox = np.array([p.x for p in outline_points])
        oy = np.array([p.y for p in outline_points])
        
        # Sort by Y
        idx = np.argsort(oy)
        oy_sorted, ox_sorted = oy[idx], ox[idx]
        y_top, y_bot = oy_sorted[0], oy_sorted[-1]
        x_top, x_bot = ox_sorted[0], ox_sorted[-1]

        # ENFORCE VERTICAL SPINE
        if spine_x is None:
            spine_x = x_top
        
        # Ensure outline starts and ends AT the spine to guarantee closure
        ox_corrected = ox_sorted.copy()
        ox_corrected[0] = spine_x
        ox_corrected[-1] = spine_x
        
        try:
            outline_func = interp1d(oy_sorted, ox_corrected, kind='linear', bounds_error=False, fill_value=(spine_x, spine_x))
        except Exception as e:
            print(f"Outline interp error: {e}")
            return None, None, None

        # 2. Prepare Arching (Longitudinal)
        ax = np.array([p.x for p in arch_points])
        ay = np.array([p.y for p in arch_points])
        
        # Sort by Y
        a_idx = np.argsort(ay)
        ay_sorted, ax_sorted = ay[a_idx], ax[a_idx]
        
        # Map Arch Y to Outline Y range
        if len(ay_sorted) > 1 and ay_sorted[-1] != ay_sorted[0]:
            ay_mapped = y_top + (ay_sorted - ay_sorted[0]) / (ay_sorted[-1] - ay_sorted[0]) * (y_bot - y_top)
            
            # Heights relative to base chord
            x0, x1 = ax_sorted[0], ax_sorted[-1]
            y0, y1 = ay_sorted[0], ay_sorted[-1]
            m = (x1 - x0) / (y1 - y0)
            c = x0 - m * y0
            heights = np.abs(ax_sorted - (m * ay_sorted + c))
            
            try:
                arch_func = interp1d(ay_mapped, heights, kind='cubic', bounds_error=False, fill_value=0)
            except:
                arch_func = interp1d(ay_mapped, heights, kind='linear', bounds_error=False, fill_value=0)
        else:
            def arch_func(y): return np.zeros_like(y)

        # 3. Generate 2D Grid
        y_grid = np.linspace(y_top, y_bot, resolution)
        u_norm = np.linspace(-1, 1, resolution) # Mirroring built-in: -1 to 1
        
        U_norm, Y = np.meshgrid(u_norm, y_grid)
        
        # Calculate Widths and Heights for each Y-row
        W_y = np.abs(outline_func(y_grid) - spine_x)
        H_y = arch_func(y_grid)
        
        # Reshape for broadcasting
        W_2D = W_y[:, np.newaxis]
        H_2D = H_y[:, np.newaxis]
        
        # Final Geometry
        X = spine_x + U_norm * W_2D
        Z = H_2D * np.cos(U_norm * np.pi / 2.0)
        
        return X, Y, Z
