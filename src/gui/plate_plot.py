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
        
    def update_plot(self, X, Y, Z):
        self.ax.clear()
        self.ax.set_title("Virtual Plate Height Map")
        self.ax.set_aspect('equal')
        self.ax.axis('off')
        
        if X is None or Y is None or Z is None:
            self.canvas.draw()
            return
            
        # Contour Plot
        # Use 'turbo' or 'jet' or 'viridis'
        levels = 20
        contour = self.ax.contourf(X, Y, Z, levels=levels, cmap='turbo')
        
        # Add contour lines
        self.ax.contour(X, Y, Z, levels=levels, colors='k', linewidths=0.5, alpha=0.5)
        
        # Invert Y axis to match canvas (Top is 0, Bottom is 600)
        self.ax.invert_yaxis()
        
        self.canvas.draw()
