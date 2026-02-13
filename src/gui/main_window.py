
from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QSlider, QLabel, QTabWidget
from PyQt6.QtCore import Qt, QTimer
from .canvas import Canvas
from .arching_canvas import ArchingCanvas
from .controls import Controls
from ..core.physics import AcousticModel
from ..core.synthesizer import Synthesizer
from ..core.plate_generator import PlateGenerator

from .spl_plot import SPLPlot
from .spectrogram_plot import SpectrogramPlot
from .plate_plot import PlatePlot

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AFFOIM - Violin CAD Prototype")
        self.resize(1400, 900) # Increased height

        # Core Components
        self.physics = AcousticModel()
        self.synthesizer = Synthesizer()
        self.plate_generator = PlateGenerator()
        
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
        
        # --- Right Column: Controls, Info & Plots ---
        self.right_panel = QWidget()
        self.right_layout = QVBoxLayout(self.right_panel)
        
        self.controls = Controls()
        self.right_layout.addWidget(self.controls)
        
        # Tabs for Analysis vs Plate Map
        self.tabs = QTabWidget()
        self.right_layout.addWidget(self.tabs, stretch=1)
        
        # Tab 1: Acoustic Analysis
        self.analysis_tab = QWidget()
        self.analysis_layout = QVBoxLayout(self.analysis_tab)
        
        self.spl_plot = SPLPlot()
        self.analysis_layout.addWidget(self.spl_plot, stretch=1)
        
        self.spectrogram_plot = SpectrogramPlot()
        self.analysis_layout.addWidget(self.spectrogram_plot, stretch=1)
        
        self.tabs.addTab(self.analysis_tab, "Acoustics")
        
        # Tab 2: Plate Map
        self.plate_tab = QWidget()
        self.plate_layout = QVBoxLayout(self.plate_tab)
        
        self.plate_plot = PlatePlot()
        self.plate_layout.addWidget(self.plate_plot)
        
        self.tabs.addTab(self.plate_tab, "Plate Map")
        
        # Buttons
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
        # We also need to update when arching changes (though arching doesn't emit yet?)
        # Let's add geometryChanged to ArchingCanvas if not present or connect it.
        # ArchingCanvas has geometryChanged signal.
        self.arching_canvas.geometryChanged.connect(self.on_arching_changed)
        
        self.controls.materialChanged.connect(self.on_material_changed)
        
        # Initial update
        self.canvas.update_geometry()
        self.arching_canvas.update_geometry() # Ensure this emits
        
        # Load Example Images
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        outline_img = os.path.join(base_dir, "Baldwin-Violin-Front-Upright.jpg")
        arching_img = os.path.join(base_dir, "Antonio-Strad-5H-Violin-Right-Side-Upright.jpg")
        
        if os.path.exists(outline_img):
            self.canvas.load_background(outline_img)
        if os.path.exists(arching_img):
            self.arching_canvas.load_background(arching_img)
        
        # Spectrogram Timer
        self.spectrogram_timer = QTimer()
        self.spectrogram_timer.timeout.connect(self.update_spectrogram)
        self.spectrogram_timer.start(30) # 30ms ~ 33fps

    def update_spectrogram(self):
        if self.synthesizer.is_running:
            chunk = self.synthesizer.get_audio_chunk()
            if chunk is not None:
                self.spectrogram_plot.update_plot(chunk)
                
    def on_arching_changed(self, points):
        # Notify physics model about arching changes
        from ..core.geometry import Point
        top_pts = [Point(p.pos().x(), p.pos().y()) for p in self.arching_canvas.top_points]
        back_pts = [Point(p.pos().x(), p.pos().y()) for p in self.arching_canvas.back_points]
        self.physics.update_arching(top_pts, back_pts)
        
        # Re-trigger acoustic prediction
        outline_pts = [Point(p.pos().x(), p.pos().y()) for p in self.canvas.points]
        self.on_geometry_changed(outline_pts)
        
        # Update plate map
        self.update_plate_map()
        
    def update_plate_map(self):
        from ..core.geometry import Point
        outline_points = [Point(p.pos().x(), p.pos().y()) for p in self.canvas.points]
        arch_points = [Point(p.pos().x(), p.pos().y()) for p in self.arching_canvas.top_points]
        
        # Generate Mesh
        X, Y, Z = self.plate_generator.generate_mesh(outline_points, arch_points)
        
        # Update Plot
        self.plate_plot.update_plot(X, Y, Z)

    def on_geometry_changed(self, points):
        # 1. Predict modes from geometry
        # ... existing logic ...
        self.physics.update_geometry(points)
        modes = self.physics.predict()
        
        # 2. Update Synthesizer
        self.synthesizer.update_modes(modes)
        
        # 3. Update Plots
        freqs, spl = self.physics.calculate_spectrum(modes)
        self.spl_plot.update_plot(freqs, spl)
        
        # 4. Update Plate Map
        self.update_plate_map()
        
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
