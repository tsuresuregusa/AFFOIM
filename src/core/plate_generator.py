import numpy as np
from scipy.interpolate import interp1d

class PlateGenerator:
    def __init__(self):
        pass

    def generate_mesh(self, outline_points, arch_points, resolution=100):
        """
        Generates a 3D height map (mesh) for the violin plate.
        
        Args:
            outline_points: List of Point objects defining the half-outline (x > 0).
            arch_points: List of Point objects defining the longitudinal arch (y, z).
            resolution: Number of points along the y-axis.
            
        Returns:
            X, Y, Z: 2D arrays defining the surface.
        """
        if not outline_points or not arch_points:
            return None, None, None

        # 1. Prepare Data
        # Outline: (x, y)
        # We need to interpolate x as a function of y to get Width(y).
        # The outline points might not be sorted by y, or might loop.
        # Assuming standard violin outline where y increases monotonically-ish or we can sort.
        # Actually, the outline goes up and down? No, usually P0 (top) to P9 (bottom).
        # Let's extract arrays.
        
        ox = np.array([p.x for p in outline_points])
        oy = np.array([p.y for p in outline_points])
        
        # Sort by Y to ensure interpolation works
        # But violin outline might have multiple x for same y? (e.g. corners)
        # For simplicity, we assume unique y or strictly increasing/decreasing segments.
        # The provided points P0->P9 go from Top(y=50) to Bottom(y=550).
        # So it is monotonic in Y roughly.
        
        # Sort just in case
        sorted_indices = np.argsort(oy)
        oy_sorted = oy[sorted_indices]
        ox_sorted = ox[sorted_indices]
        
        # Create interpolation for Width(y) = x(y)
        # We use linear or cubic. Pchip is good for monotonic.
        # But let's use simple linear for robustness or interp1d.
        try:
            outline_func = interp1d(oy_sorted, ox_sorted, kind='linear', bounds_error=False, fill_value=0)
        except Exception as e:
            print(f"Outline interp error: {e}")
            return None, None, None

        # Arching: (x, y) in canvas coords, but conceptually (pos, height).
        # In ArchingCanvas, x is longitudinal position (length), y is height (inverted?).
        # Wait, ArchingCanvas draws it vertically now?
        # "Top Arch: x ~ 200, y varies 50-550".
        # So Y is the longitudinal axis (length), X is the height (elevation).
        # Let's assume the "height" is relative to the flat side.
        # If x ~ 200 is the base, then deviation from 200 is height?
        # Or is it a profile view?
        # Let's assume the user draws the profile.
        # We need to normalize it.
        # Let's assume the "max" x value is the base (0 height) or min x?
        # Usually arching goes "up".
        # Let's take the raw values and normalize so edges are 0.
        
        ax = np.array([p.x for p in arch_points])
        ay = np.array([p.y for p in arch_points])
        
        # Sort by Y (longitudinal axis)
        sorted_arch_indices = np.argsort(ay)
        ay_sorted = ay[sorted_arch_indices]
        ax_sorted = ax[sorted_arch_indices]
        
        # Normalize height
        # Assume the ends are at height 0.
        # Or just take min(ax) as 0?
        # Let's assume the curve defines the absolute shape.
        # We'll shift it so the minimum X is 0? Or maximum?
        # If it's drawn vertically, usually "right" is "up" or "left" is "up"?
        # Let's assume deviation from the line connecting endpoints.
        # Simple approach: Linear detrend the endpoints to 0.
        
        # Fit line between first and last point
        y0, y1 = ay_sorted[0], ay_sorted[-1]
        x0, x1 = ax_sorted[0], ax_sorted[-1]
        
        # Slope m = (x1 - x0) / (y1 - y0)
        if y1 != y0:
            m = (x1 - x0) / (y1 - y0)
            c = x0 - m * y0
            # Baseline x_base = m * y + c
            x_base = m * ay_sorted + c
            # Height = x - x_base (or x_base - x depending on direction)
            # Let's assume "bulge" is positive.
            heights = np.abs(ax_sorted - x_base)
        else:
            heights = np.zeros_like(ax_sorted)
            
        # Interpolate Arch Height H(y)
        try:
            arch_func = interp1d(ay_sorted, heights, kind='cubic', bounds_error=False, fill_value=0)
        except:
            arch_func = interp1d(ay_sorted, heights, kind='linear', bounds_error=False, fill_value=0)

        # 2. Generate Grid
        # Y range: min to max of outline
        y_min, y_max = oy_sorted[0], oy_sorted[-1]
        y_grid = np.linspace(y_min, y_max, resolution)
        
        # X range: -max_width to max_width
        # We need to find max width first
        max_w = np.max(ox_sorted)
        # Centerline is usually x=0 in our math model, but in canvas x=150 is center?
        # We need to normalize outline X too.
        # Let's assume the "centerline" is the min X of the outline?
        # Or user provided half-outline.
        # In Canvas, points are like (150, 50).
        # 150 seems to be the center line if it's a half outline?
        # "P0: Top Start (200, 50)". "P15: Bottom End (200, 550)".
        # Yes, x=200 is the new centerline.
        centerline_x = 200
        
        # Width(y) = abs(outline_x(y) - centerline_x)
        widths = np.abs(outline_func(y_grid) - centerline_x)
        
        # Create 2D Grid
        # We want a grid that covers the whole violin width
        max_width_val = np.max(widths)
        x_grid = np.linspace(-max_width_val, max_width_val, resolution)
        
        X, Y = np.meshgrid(x_grid, y_grid)
        Z = np.zeros_like(X)
        
        # 3. Calculate Z
        # Z(x, y) = H(y) * CrossArch(x / W(y))
        
        # Pre-calculate H(y) for the grid rows
        H_y = arch_func(y_grid)
        
        # Pre-calculate W(y) for the grid rows
        W_y = widths
        
        for i in range(resolution):
            h_val = H_y[i]
            w_val = W_y[i]
            
            if w_val < 1e-6:
                continue
                
            # Normalized x: u = x / w_val
            # We only care about x within [-w, w]
            row_x = X[i, :]
            
            # Mask for inside outline
            mask = np.abs(row_x) <= w_val
            
            u = row_x[mask] / w_val
            
            # Cross Arching Function: Modified Cosine
            # z = h * cos(u * pi / 2) ^ 0.5 ? Or cycloid?
            # Simple Cosine: cos(u * pi / 2)
            # Curtate Cycloid is better but complex to solve numerically.
            # Let's use a "flattened" cosine: cos(u * pi / 2) ^ 0.8
            
            z_vals = h_val * np.cos(u * np.pi / 2)
            
            Z[i, mask] = z_vals
            
        return X, Y, Z
