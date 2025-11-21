from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QSlider, QLabel
from PyQt6.QtCore import Qt
from .canvas import Canvas
from .arching_canvas import ArchingCanvas
from .controls import Controls
from ..core.physics import AcousticModel
from ..core.synthesizer import Synthesizer

from .spl_plot import SPLPlot

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AFFOIM - Violin CAD Prototype")
        self.resize(1400, 800)

        # Core Components
        self.physics = AcousticModel()
        self.synthesizer = Synthesizer()
        
        # GUI Components
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        self.main_layout = QHBoxLayout(self.central_widget)
        
        # --- Left Column: Outline Canvas & Transparency ---
        self.left_panel = QWidget()
        self.left_layout = QVBoxLayout(self.left_panel)
        
        self.canvas = Canvas()
        self.left_layout.addWidget(self.canvas)
        
        # Transparency Slider
        self.transparency_layout = QHBoxLayout()
        self.transparency_layout.addWidget(QLabel("Image Opacity:"))
        self.transparency_slider = QSlider(Qt.Orientation.Horizontal)
        self.transparency_slider.setRange(0, 100)
        self.transparency_slider.setValue(50)
        self.transparency_slider.valueChanged.connect(self.on_transparency_changed)
        self.transparency_layout.addWidget(self.transparency_slider)
        self.left_layout.addLayout(self.transparency_layout)
        
        self.main_layout.addWidget(self.left_panel, stretch=2)
        
        # --- Center Column: Arching Canvas ---
        self.center_panel = QWidget()
        self.center_layout = QVBoxLayout(self.center_panel)
        
        self.arching_canvas = ArchingCanvas()
        self.center_layout.addWidget(self.arching_canvas)
        
        # Arching Transparency Slider
        self.arch_transparency_layout = QHBoxLayout()
        self.arch_transparency_layout.addWidget(QLabel("Arching Opacity:"))
        self.arch_transparency_slider = QSlider(Qt.Orientation.Horizontal)
        self.arch_transparency_slider.setRange(0, 100)
        self.arch_transparency_slider.setValue(50)
        self.arch_transparency_slider.valueChanged.connect(self.on_arch_transparency_changed)
        self.arch_transparency_layout.addWidget(self.arch_transparency_slider)
        self.center_layout.addLayout(self.arch_transparency_layout)
        
        self.main_layout.addWidget(self.center_panel, stretch=2)
        
        # --- Right Column: Controls, Info & SPL Plot ---
        self.right_panel = QWidget()
        self.right_layout = QVBoxLayout(self.right_panel)
        
        self.controls = Controls()
        self.right_layout.addWidget(self.controls)
        
        # SPL Plot
        self.spl_plot = SPLPlot()
        self.right_layout.addWidget(self.spl_plot, stretch=1)
        
        self.load_bg_btn = QPushButton("Load Background Image")
        self.load_bg_btn.clicked.connect(self.canvas.load_background)
        self.right_layout.addWidget(self.load_bg_btn)
        
        self.load_arching_bg_btn = QPushButton("Load Arching Image")
        self.load_arching_bg_btn.clicked.connect(self.arching_canvas.load_background)
        self.right_layout.addWidget(self.load_arching_bg_btn)
        
        self.start_audio_btn = QPushButton("Start Audio")
        self.start_audio_btn.setCheckable(True)
        self.start_audio_btn.clicked.connect(self.toggle_audio)
        self.right_layout.addWidget(self.start_audio_btn)
        
        self.right_layout.addStretch()
        self.main_layout.addWidget(self.right_panel, stretch=1)

        # Wiring
        self.canvas.geometryChanged.connect(self.on_geometry_changed)
        self.controls.materialChanged.connect(self.on_material_changed)
        
        # Initial update
        self.canvas.update_geometry()

    def on_geometry_changed(self, points):
        # 1. Predict modes from geometry
        modes = self.physics.predict(points)
        
        # 2. Update synthesizer
        self.synthesizer.update_modes(modes)
        
        # 3. Update SPL Plot
        freqs, spl = self.physics.calculate_spectrum(modes)
        self.spl_plot.update_plot(freqs, spl)
        
    def on_material_changed(self, td, tm, bd, bm):
        # 1. Update physics model
        self.physics.set_material_properties(td, tm, bd, bm)
        
        # 2. Re-predict using current geometry
        self.canvas.update_geometry()
        # Note: update_geometry emits signal which calls on_geometry_changed, 
        # so SPL plot will update automatically.

    def on_transparency_changed(self, value):
        opacity = value / 100.0
        self.canvas.set_background_opacity(opacity)

    def on_arch_transparency_changed(self, value):
        opacity = value / 100.0
        self.arching_canvas.set_background_opacity(opacity)

    def toggle_audio(self, checked):
        if checked:
            self.synthesizer.start()
            self.start_audio_btn.setText("Stop Audio")
        else:
            self.synthesizer.stop()
            self.start_audio_btn.setText("Start Audio")

    def closeEvent(self, event):
        self.synthesizer.stop()
        super().closeEvent(event)
