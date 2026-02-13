from PyQt6.QtWidgets import QWidget, QVBoxLayout
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np

class SPLPlot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Create Matplotlib Figure with constrained layout to prevent cropping
        # Increased height factor to 8 (Requested: factor 2)
        self.figure = Figure(figsize=(5, 8), dpi=100, constrained_layout=True)
        self.canvas = FigureCanvas(self.figure)
        self.layout.addWidget(self.canvas)
        
        # Setup Plot
        self.ax = self.figure.add_subplot(111)
        self.ax.set_title("Frequency Response (SPL)")
        self.ax.set_xlabel("Frequency [Hz]")
        self.ax.set_ylabel("SPL [dB]")
        
        # Logarithmic Frequency Axis
        self.ax.set_xscale('log')
        self.ax.set_xlim(100, 10000)
        self.ax.set_xticks([100, 200, 500, 1000, 2000, 5000, 10000])
        from matplotlib.ticker import ScalarFormatter
        self.ax.xaxis.set_major_formatter(ScalarFormatter())
        
        self.ax.grid(True, which="both", ls="-", alpha=0.3)
        
        # Initial empty plot
        # Lines for both models
        self.model_line, = self.ax.plot([], [], color='SteelBlue', linewidth=1.5, label='Physical Model')
        self.sampled_line, = self.ax.plot([], [], color='DarkOrange', linewidth=1.2, label='Sampled Data', alpha=0.5)
        
        self.ax.legend(loc='upper right', frameon=False, fontsize='small')
        
        # Set limits
        self.ax.set_ylim(-40, 60)

    def update_plot(self, freqs, model_spl, sampled_spl, active_mode="MODEL"):
        # Update Model Line
        self.model_line.set_data(freqs, model_spl)
        
        # Update Sampled Line
        self.sampled_line.set_data(freqs, sampled_spl)
        
        # Adjust Transparency based on active mode
        if active_mode == "SAMPLED":
            m_alpha, s_alpha = 0.3, 1.0
        elif active_mode in ["MODEL", "NOISY"]:
            m_alpha, s_alpha = 1.0, 0.3
        else: # FLAT or others
            m_alpha, s_alpha = 0.3, 0.3
            
        self.model_line.set_alpha(m_alpha)
        self.sampled_line.set_alpha(s_alpha)
            
        self.canvas.draw()
