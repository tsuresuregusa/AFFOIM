from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QComboBox, QGridLayout, QToolButton, QFrame, QSizePolicy
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QParallelAnimationGroup, QAbstractAnimation
import numpy as np

class CollapsibleBox(QWidget):
    """
    A simple collapsible box inspired by accordion menus.
    """
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.toggle_button = QToolButton(text=title, checkable=True, checked=False)
        self.toggle_button.setStyleSheet("""
            QToolButton { 
                border: 1px solid #999; 
                font-weight: bold; 
                background: #c0c0c0; /* Darker than before */
                color: #222;
                padding: 6px; 
            }
            QToolButton:checked {
                background: #a0a0a0;
            }
            QToolButton:hover {
                background: #d0d0d0;
            }
        """)
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle_button.setArrowType(Qt.ArrowType.RightArrow)
        self.toggle_button.pressed.connect(self.on_pressed)
        self.toggle_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(5, 5, 5, 5)
        self.content_area.setVisible(False)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(0)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.toggle_button)
        self.main_layout.addWidget(self.content_area)

    def on_pressed(self):
        # We handle the actual reveal in the parent (Controls) to ensure accordion behavior
        pass

    def set_content_layout(self, layout):
        # Clear existing
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self.content_layout.addLayout(layout)

    def set_expanded(self, expanded):
        self.toggle_button.setChecked(expanded)
        self.content_area.setVisible(expanded)
        self.toggle_button.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)

class Controls(QWidget):
    materialChanged = pyqtSignal(float, float, float, float)
    stringFrequencyChanged = pyqtSignal(object)
    splModeChanged = pyqtSignal(str)
    noiseLevelChanged = pyqtSignal(float)
    smoothingLevelChanged = pyqtSignal(float)
    excitationModeChanged = pyqtSignal(str)
    bowVelocityChanged = pyqtSignal(float)
    bowForceChanged = pyqtSignal(float)
    saveSettings = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Main Layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(2)
        
        # --- String Selection (Always visible) ---
        string_container = QWidget()
        string_layout = QHBoxLayout(string_container)
        string_layout.addWidget(QLabel("<b>String:</b>"))
        self.string_combo = QComboBox()
        self.string_combo.addItem("G3 (196.0 Hz)", 196.0)
        self.string_combo.addItem("D4 (293.66 Hz)", 293.66)
        self.string_combo.addItem("A4 (440.0 Hz)", 440.0)
        self.string_combo.addItem("E5 (659.25 Hz)", 659.25)
        
        # Sibelius Opening (freq, duration)
        sibelius_melody = [
            (587.33, 1.5), # D5
            (783.99, 0.4), # G5
            (880.00, 0.4), # A5
            (1174.66, 1.0), # D6
            (1108.73, 0.4), # C6#
            (932.33, 0.4), # Bb5
            (880.00, 1.0)  # A5
        ]
        self.string_combo.addItem("Sibelius Opening", sibelius_melody)
        string_layout.addWidget(self.string_combo)
        self.layout.addWidget(string_container)
        
        # --- Accordion Sections ---
        self.sections = []

        # 1. Materials
        self.mat_box = CollapsibleBox("Materials")
        self.setup_material_section(self.mat_box)
        self.layout.addWidget(self.mat_box)
        self.sections.append(self.mat_box)

        # 2. Input (Excitation)
        self.input_box = CollapsibleBox("Input (Excitation)")
        self.setup_input_section(self.input_box)
        self.layout.addWidget(self.input_box)
        self.sections.append(self.input_box)

        # 3. SPL Model (Response)
        self.resp_box = CollapsibleBox("SPL Model (Response)")
        self.setup_response_section(self.resp_box)
        self.layout.addWidget(self.resp_box)
        self.sections.append(self.resp_box)

        # Connect toggles for accordion behavior
        self.mat_box.toggle_button.clicked.connect(lambda: self.on_section_toggled(0))
        self.input_box.toggle_button.clicked.connect(lambda: self.on_section_toggled(1))
        self.resp_box.toggle_button.clicked.connect(lambda: self.on_section_toggled(2))

        # Initial State: Input open
        self.on_section_toggled(1)

        # --- Footer ---
        from PyQt6.QtWidgets import QPushButton
        self.save_btn = QPushButton("Save Default Geometry")
        self.layout.addWidget(self.save_btn)
        
        self.layout.addStretch()
        self.setup_connections()

    def on_section_toggled(self, index):
        for i, section in enumerate(self.sections):
            section.set_expanded(i == index)

    def setup_material_section(self, box):
        grid = QGridLayout()
        grid.addWidget(QLabel("<b>Top</b>"), 0, 1, Qt.AlignmentFlag.AlignCenter)
        grid.addWidget(QLabel("<b>Back</b>"), 0, 2, Qt.AlignmentFlag.AlignCenter)
        
        # Density Row
        grid.addWidget(QLabel("Density"), 1, 0)
        
        # Top Density
        self.top_density_slider = QSlider(Qt.Orientation.Horizontal)
        self.top_density_slider.setRange(300, 850); self.top_density_slider.setValue(400)
        self.top_density_label = QLabel("400")
        vbox1 = QVBoxLayout(); vbox1.addWidget(self.top_density_slider); vbox1.addWidget(self.top_density_label, 0, Qt.AlignmentFlag.AlignCenter)
        grid.addLayout(vbox1, 1, 1)
        
        # Back Density
        self.back_density_slider = QSlider(Qt.Orientation.Horizontal)
        self.back_density_slider.setRange(300, 850); self.back_density_slider.setValue(600)
        self.back_density_label = QLabel("600")
        vbox2 = QVBoxLayout(); vbox2.addWidget(self.back_density_slider); vbox2.addWidget(self.back_density_label, 0, Qt.AlignmentFlag.AlignCenter)
        grid.addLayout(vbox2, 1, 2)
        
        # Stiffness Row
        grid.addWidget(QLabel("Stiffness"), 2, 0)
        
        # Top Stiffness (Value = Slider/10.0)
        self.top_modulus_slider = QSlider(Qt.Orientation.Horizontal)
        self.top_modulus_slider.setRange(50, 200); self.top_modulus_slider.setValue(120)
        self.top_modulus_label = QLabel("12.0")
        vbox3 = QVBoxLayout(); vbox3.addWidget(self.top_modulus_slider); vbox3.addWidget(self.top_modulus_label, 0, Qt.AlignmentFlag.AlignCenter)
        grid.addLayout(vbox3, 2, 1)
        
        # Back Stiffness
        self.back_modulus_slider = QSlider(Qt.Orientation.Horizontal)
        self.back_modulus_slider.setRange(50, 200); self.back_modulus_slider.setValue(100)
        self.back_modulus_label = QLabel("10.0")
        vbox4 = QVBoxLayout(); vbox4.addWidget(self.back_modulus_slider); vbox4.addWidget(self.back_modulus_label, 0, Qt.AlignmentFlag.AlignCenter)
        grid.addLayout(vbox4, 2, 2)
        
        box.set_content_layout(grid)

    def setup_input_section(self, box):
        layout = QVBoxLayout()
        h1 = QHBoxLayout()
        h1.addWidget(QLabel("Model:"))
        self.excitation_combo = QComboBox()
        self.excitation_combo.addItem("Sawtooth", "sawtooth")
        self.excitation_combo.addItem("Waveguide", "waveguide")
        self.excitation_combo.addItem("FDTD", "fdtd")
        h1.addWidget(self.excitation_combo)
        layout.addLayout(h1)

        h2 = QHBoxLayout()
        h2.addWidget(QLabel("Vel:"))
        self.bow_vel_slider = QSlider(Qt.Orientation.Horizontal)
        self.bow_vel_slider.setRange(0, 100); self.bow_vel_slider.setValue(50)
        h2.addWidget(self.bow_vel_slider)
        layout.addLayout(h2)

        h3 = QHBoxLayout()
        h3.addWidget(QLabel("Force:"))
        self.bow_force_slider = QSlider(Qt.Orientation.Horizontal)
        self.bow_force_slider.setRange(0, 100); self.bow_force_slider.setValue(50)
        h3.addWidget(self.bow_force_slider)
        layout.addLayout(h3)
        box.set_content_layout(layout)

    def setup_response_section(self, box):
        layout = QVBoxLayout()
        h1 = QHBoxLayout()
        h1.addWidget(QLabel("Type:"))
        self.spl_mode_combo = QComboBox()
        self.spl_mode_combo.addItem("Flat", "FLAT")
        self.spl_mode_combo.addItem("Model", "MODEL")
        self.spl_mode_combo.addItem("Sampled", "SAMPLED")
        self.spl_mode_combo.addItem("Noisy", "NOISY")
        self.spl_mode_combo.setCurrentIndex(1)
        h1.addWidget(self.spl_mode_combo)
        layout.addLayout(h1)

        h2 = QHBoxLayout()
        h2.addWidget(QLabel("Noise:"))
        self.noise_slider = QSlider(Qt.Orientation.Horizontal)
        self.noise_slider.setRange(0, 100); self.noise_slider.setValue(0)
        h2.addWidget(self.noise_slider)
        layout.addLayout(h2)

        h3 = QHBoxLayout()
        h3.addWidget(QLabel("Smooth:"))
        self.smoothing_slider = QSlider(Qt.Orientation.Horizontal)
        self.smoothing_slider.setRange(0, 100); self.smoothing_slider.setValue(0)
        h3.addWidget(self.smoothing_slider)
        layout.addLayout(h3)
        box.set_content_layout(layout)

    def setup_connections(self):
        self.top_density_slider.valueChanged.connect(self.on_value_changed)
        self.back_density_slider.valueChanged.connect(self.on_value_changed)
        self.top_modulus_slider.valueChanged.connect(self.on_value_changed)
        self.back_modulus_slider.valueChanged.connect(self.on_value_changed)
        self.string_combo.currentIndexChanged.connect(self.on_string_changed)
        self.spl_mode_combo.currentIndexChanged.connect(self.on_spl_mode_changed)
        self.noise_slider.valueChanged.connect(self.on_noise_changed)
        self.smoothing_slider.valueChanged.connect(self.on_smoothing_changed)
        self.excitation_combo.currentIndexChanged.connect(self.on_excitation_changed)
        self.bow_vel_slider.valueChanged.connect(self.on_bow_vel_changed)
        self.bow_force_slider.valueChanged.connect(self.on_bow_force_changed)
        self.save_btn.clicked.connect(self.saveSettings.emit)

    def on_string_changed(self, index):
        freq = self.string_combo.currentData()
        self.stringFrequencyChanged.emit(freq)

    def on_value_changed(self):
        td = float(self.top_density_slider.value())
        bd = float(self.back_density_slider.value())
        tm = self.top_modulus_slider.value() / 10.0
        bm = self.back_modulus_slider.value() / 10.0
        
        # Update Labels
        self.top_density_label.setText(str(int(td)))
        self.back_density_label.setText(str(int(bd)))
        self.top_modulus_label.setText(f"{tm:.1f}")
        self.back_modulus_label.setText(f"{bm:.1f}")
        
        self.materialChanged.emit(td, tm, bd, bm)

    def on_spl_mode_changed(self, index):
        mode = self.spl_mode_combo.currentData()
        self.splModeChanged.emit(mode)
        self.noise_slider.setEnabled(mode == "NOISY" or mode == "SAMPLED")

    def on_noise_changed(self, value):
        self.noiseLevelChanged.emit(value / 100.0)

    def on_smoothing_changed(self, value):
        self.smoothingLevelChanged.emit(value / 100.0)

    def on_excitation_changed(self, index):
        self.excitationModeChanged.emit(self.excitation_combo.currentData())

    def on_bow_vel_changed(self, value):
        self.bowVelocityChanged.emit(value / 100.0)

    def on_bow_force_changed(self, value):
        self.bowForceChanged.emit(value / 100.0)
