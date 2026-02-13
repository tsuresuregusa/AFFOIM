from PyQt6.QtWidgets import QWidget, QVBoxLayout
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np

class PlatePlot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Create Matplotlib Figure
        self.figure = Figure(figsize=(5, 5), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.layout.addWidget(self.canvas)
        
        # Setup Plot
        self.ax = self.figure.add_subplot(111)
        self.ax.set_title("Virtual Plate Height Map")
        self.ax.set_aspect('equal')
        self.ax.axis('off')
        
    def update_plot(self, X, Y, Z, simplified_pts=None, visual_pts=None, spine_x=None):
        self.ax.clear()
        self.ax.set_title("Virtual Plate Height Map")
        self.ax.set_aspect('equal')
        self.ax.axis('off')
        
        if X is None or Y is None or Z is None:
            self.canvas.draw()
            return
            
        # 1. Contour Plot (The Heatmap)
        levels = 20
        self.ax.contourf(X, Y, Z, levels=levels, cmap='turbo')
        self.ax.contour(X, Y, Z, levels=levels, colors='k', linewidths=0.5, alpha=0.2)
        
        # 2. Overlay Simplified Outline (Subtle reference)
        if simplified_pts:
            self._draw_outline(simplified_pts, color='#444', alpha=0.3, linewidth=1.0, linestyle='--', spine_x=spine_x)
            
        # 3. Overlay Visual Outline (High-Res, High Contrast)
        if visual_pts:
            self._draw_outline(visual_pts, color='black', alpha=0.9, linewidth=1.2, spine_x=spine_x)

        self.ax.invert_yaxis()
        self.canvas.draw()

    def _draw_outline(self, pts, color='black', alpha=0.9, linewidth=1.0, linestyle='-', spine_x=None):
        if not pts: return
        ox = np.array([p.x for p in pts])
        oy = np.array([p.y for p in pts])
        
        # Strictly Vertical Mirroring to match PlateGenerator behavior
        # Use provided spine_x or fallback to Top Point (P0)
        if spine_x is None:
            spine_x = ox[0]
        
        # Draw mirrored halves
        ox_left = 2 * spine_x - ox
        self.ax.plot(ox, oy, color=color, alpha=alpha, linewidth=linewidth, linestyle=linestyle)
        self.ax.plot(ox_left, oy, color=color, alpha=alpha, linewidth=linewidth, linestyle=linestyle)
