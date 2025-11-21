from PyQt6.QtWidgets import QWidget, QVBoxLayout
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np

class SPLPlot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Create Matplotlib Figure
        self.figure = Figure(figsize=(5, 4), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.layout.addWidget(self.canvas)
        
        # Setup Plot
        self.ax = self.figure.add_subplot(111)
        self.ax.set_title("Frequency Response (SPL)")
        self.ax.set_xlabel("Frequency [Hz]")
        self.ax.set_ylabel("SPL [dB]")
        self.ax.grid(True, which="both", ls="-", alpha=0.5)
        
        # Initial empty plot
        self.line, = self.ax.plot([], [], 'b-', linewidth=1.5)
        
        # Set limits
        self.ax.set_xlim(100, 5000)
        self.ax.set_ylim(0, 100) # Adjust based on expected values

    def update_plot(self, freqs, spl_db):
        self.line.set_data(freqs, spl_db)
        
        # Auto-scale Y axis if needed, or keep fixed
        if len(spl_db) > 0:
            y_min = np.min(spl_db)
            y_max = np.max(spl_db)
            margin = 5
            self.ax.set_ylim(y_min - margin, y_max + margin)
            
        self.canvas.draw()
