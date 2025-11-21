from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPathItem
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QPainterPath
from .canvas import ControlPoint
import numpy as np
from scipy.interpolate import make_interp_spline

class ArchingCanvas(QGraphicsView):
    geometryChanged = pyqtSignal(list) # Emits list of points (placeholder)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag) # Enable Panning
        
        # Enforce Aspect Ratio 1:2 (Vertical)
        self.scene.setSceneRect(0, 0, 600, 600) # Arching might need different ratio? 
        # User said "images should be trimmed at an aspect ratio relevant to the violin".
        # Arching is side view, so length is same (800), height is less (e.g. 200).
        # But we are drawing it in a square-ish view?
        # Let's stick to a reasonable rect.
        self.scene.setSceneRect(0, 0, 600, 600)
        
        # Top Arch (Blue) - Vertical orientation
        self.top_points = []
        # Back Arch (Orange) - Vertical orientation
        self.back_points = []
        
        # Initialize points (Vertical)
        # Top Arch: x ~ 200, y varies 50-550
        top_data = [
            (200, 50), (150, 150), (140, 300), (150, 450), (200, 550)
        ]
        # Back Arch: x ~ 400, y varies 50-550
        back_data = [
            (400, 50), (450, 150), (460, 300), (450, 450), (400, 550)
        ]
        
        self.top_path = QGraphicsPathItem()
        self.top_path.setPen(QPen(QColor("blue"), 2))
        self.scene.addItem(self.top_path)
        
        self.back_path = QGraphicsPathItem()
        self.back_path.setPen(QPen(QColor("orange"), 2))
        self.scene.addItem(self.back_path)
        
        for x, y in top_data:
            cp = ControlPoint(x, y, color="blue")
            self.scene.addItem(cp)
            self.top_points.append(cp)
            
        for x, y in back_data:
            cp = ControlPoint(x, y, color="orange")
            self.scene.addItem(cp)
            self.back_points.append(cp)

        # Monkey patch scene
        self.scene.update_geometry = self.update_geometry
        self.update_geometry()
        
        self.background_item = None
        
        # Zoom state
        self.current_zoom = 1.0

    def wheelEvent(self, event):
        zoom_in_factor = 1.15
        zoom_out_factor = 1 / zoom_in_factor

        # Calculate proposed zoom
        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        else:
            zoom_factor = zoom_out_factor
            
        new_zoom = self.current_zoom * zoom_factor
        
        # Clamp zoom (1.0 to 3.0)
        if new_zoom < 1.0:
            zoom_factor = 1.0 / self.current_zoom
            new_zoom = 1.0
        elif new_zoom > 3.0:
            zoom_factor = 3.0 / self.current_zoom
            new_zoom = 3.0
            
        if abs(zoom_factor - 1.0) < 0.001:
            return

        self.current_zoom = new_zoom

        # Save the scene pos
        old_pos = self.mapToScene(event.position().toPoint())

        # Zoom
        self.scale(zoom_factor, zoom_factor)

        # Get the new position
        new_pos = self.mapToScene(event.position().toPoint())

        # Move scene to old position
        delta = new_pos - old_pos
        self.translate(delta.x(), delta.y())

    def load_background(self):
        from PyQt6.QtWidgets import QFileDialog
        from PyQt6.QtGui import QPixmap
        
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Arching Image", "", "Image Files (*.png *.jpg *.bmp)")
        if file_name:
            try:
                pixmap = QPixmap(file_name)
                if pixmap.isNull():
                    return

                if self.background_item:
                    self.scene.removeItem(self.background_item)
                
                self.background_item = self.scene.addPixmap(pixmap)
                self.background_item.setZValue(-1)
                self.background_item.setOpacity(0.5)
                
                # Scale logic (similar to Canvas but simplified)
                self.background_item.setScale(0.5) # Default scale
                
            except Exception as e:
                print(f"Error loading arching background: {e}")

    def set_background_opacity(self, opacity: float):
        if self.background_item:
            self.background_item.setOpacity(opacity)

    def update_geometry(self):
        def draw_spline(points, path_item):
            if len(points) < 3: return
            
            x = np.array([p.pos().x() for p in points])
            y = np.array([p.pos().y() for p in points])
            
            # Parameterize
            dx = np.diff(x)
            dy = np.diff(y)
            ds = np.sqrt(dx**2 + dy**2)
            s = np.concatenate(([0], np.cumsum(ds)))
            
            try:
                spl = make_interp_spline(s, np.c_[x, y], k=2) # Quadratic
                s_new = np.linspace(s[0], s[-1], 50)
                coords = spl(s_new)
                
                path = QPainterPath()
                path.moveTo(coords[0, 0], coords[0, 1])
                for i in range(1, len(coords)):
                    path.lineTo(coords[i, 0], coords[i, 1])
                path_item.setPath(path)
            except Exception as e:
                print(f"Arching spline error: {e}")

        draw_spline(self.top_points, self.top_path)
        draw_spline(self.back_points, self.back_path)
