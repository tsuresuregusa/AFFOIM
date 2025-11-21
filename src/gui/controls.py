from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSlider
from PyQt6.QtCore import Qt, pyqtSignal

class Controls(QWidget):
    # Emits: top_density, top_modulus, back_density, back_modulus
    materialChanged = pyqtSignal(float, float, float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        
        # --- Top Plate ---
        layout.addWidget(QLabel("<b>Top Plate</b>"))
        
        layout.addWidget(QLabel("Density (kg/m³)"))
        self.top_density_slider = QSlider(Qt.Orientation.Horizontal)
        self.top_density_slider.setRange(300, 600)
        self.top_density_slider.setValue(400)
        self.top_density_label = QLabel("400")
        layout.addWidget(self.top_density_slider)
        layout.addWidget(self.top_density_label)
        
        layout.addWidget(QLabel("Stiffness (GPa)"))
        self.top_modulus_slider = QSlider(Qt.Orientation.Horizontal)
        self.top_modulus_slider.setRange(50, 200) # 5.0 - 20.0 GPa
        self.top_modulus_slider.setValue(120) # 12.0 GPa
        self.top_modulus_label = QLabel("12.0")
        layout.addWidget(self.top_modulus_slider)
        layout.addWidget(self.top_modulus_label)
        
        layout.addSpacing(10)
        
        # --- Back Plate ---
        layout.addWidget(QLabel("<b>Back Plate</b>"))
        
        layout.addWidget(QLabel("Density (kg/m³)"))
        self.back_density_slider = QSlider(Qt.Orientation.Horizontal)
        self.back_density_slider.setRange(400, 800)
        self.back_density_slider.setValue(600)
        self.back_density_label = QLabel("600")
        layout.addWidget(self.back_density_slider)
        layout.addWidget(self.back_density_label)
        
        layout.addWidget(QLabel("Stiffness (GPa)"))
        self.back_modulus_slider = QSlider(Qt.Orientation.Horizontal)
        self.back_modulus_slider.setRange(50, 200) # 5.0 - 20.0 GPa
        self.back_modulus_slider.setValue(100) # 10.0 GPa
        self.back_modulus_label = QLabel("10.0")
        layout.addWidget(self.back_modulus_slider)
        layout.addWidget(self.back_modulus_label)

        layout.addStretch()
        
        # Connections
        self.top_density_slider.valueChanged.connect(self.on_value_changed)
        self.top_modulus_slider.valueChanged.connect(self.on_value_changed)
        self.back_density_slider.valueChanged.connect(self.on_value_changed)
        self.back_modulus_slider.valueChanged.connect(self.on_value_changed)

    def on_value_changed(self):
        td = self.top_density_slider.value()
        tm = self.top_modulus_slider.value() / 10.0
        bd = self.back_density_slider.value()
        bm = self.back_modulus_slider.value() / 10.0
        
        self.top_density_label.setText(f"{td}")
        self.top_modulus_label.setText(f"{tm:.1f}")
        self.back_density_label.setText(f"{bd}")
        self.back_modulus_label.setText(f"{bm:.1f}")
        
        self.materialChanged.emit(td, tm, bd, bm)
