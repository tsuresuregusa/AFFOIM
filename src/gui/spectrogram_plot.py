from PyQt6.QtWidgets import QWidget, QVBoxLayout
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np

class SpectrogramPlot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Create Matplotlib Figure with constrained layout
        # Increased height to 6 (Requested: larger spectrogram)
        self.figure = Figure(figsize=(5, 6), dpi=100, constrained_layout=True)
        self.canvas = FigureCanvas(self.figure)
        self.layout.addWidget(self.canvas)
        
        # Setup Plot
        self.ax = self.figure.add_subplot(111)
        self.ax.set_title("Real-time Spectrogram")
        self.ax.set_xlabel("Time")
        self.ax.set_ylabel("Frequency [Hz]")
        
        # Remove ticks for cleaner look
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        
        # Buffer for scrolling spectrogram
        self.buffer_size = 100
        self.n_fft_bins = 513 # Match blocksize=1024
        self.spectrogram_data = np.zeros((self.n_fft_bins, self.buffer_size))
        
        # Image
        self.im = self.ax.imshow(
            self.spectrogram_data, 
            aspect='auto', 
            origin='lower',
            cmap='inferno',
            extent=[0, self.buffer_size, 0, 22050]
        )
        
        self.ax.set_ylim(0, 5000) 


    def update_plot(self, audio_chunk, fundamental_freq=None):
        if audio_chunk is None: return
            
        window = np.hanning(len(audio_chunk))
        spectrum = np.fft.rfft(audio_chunk * window)
        magnitude = np.abs(spectrum)
        
        # Log scale
        magnitude = 20 * np.log10(np.maximum(magnitude, 1e-9))
        
        # Roll buffer
        self.spectrogram_data = np.roll(self.spectrogram_data, -1, axis=1)
        
        # Update last column
        if len(magnitude) == self.n_fft_bins:
             self.spectrogram_data[:, -1] = magnitude
        else:
            self.n_fft_bins = len(magnitude)
            self.spectrogram_data = np.zeros((self.n_fft_bins, self.buffer_size))
            self.spectrogram_data[:, -1] = magnitude
            
        self.im.set_data(self.spectrogram_data)
        self.im.set_clim(-80, -20)
        self.canvas.draw()
