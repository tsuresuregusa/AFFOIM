from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPathItem, QFileDialog
from PyQt6.QtCore import Qt, pyqtSignal, QRectF
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QPainterPath, QPixmap
from .canvas import ControlPoint
import numpy as np
from scipy.interpolate import make_interp_spline

class ArchingCanvas(QGraphicsView):
    geometryChanged = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.scene.setSceneRect(0, 0, 800, 400)
        
        self.top_points = []
        self.back_points = []
        
        self.top_template = [(0,0),(0.05,0.2),(0.15,0.65),(0.5,1),(0.85,0.65),(0.95,0.2),(1,0)]
        self.back_template = [(0,0),(0.05,0.25),(0.15,0.7),(0.5,1),(0.85,0.7),(0.95,0.25),(1,0)]
        
        self.top_path = QGraphicsPathItem()
        self.top_path.setPen(QPen(QColor("blue"), 2))
        self.scene.addItem(self.top_path)
        
        self.back_path = QGraphicsPathItem()
        self.back_path.setPen(QPen(QColor("orange"), 2))
        self.scene.addItem(self.back_path)
        
        self.background_item = None
        self.current_zoom = 1.0
        self.reset_points_to_rect(self.scene.sceneRect())
        self.scene.update_geometry = self.update_geometry
        self.update_geometry()
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    def reset_points_to_rect(self, rect):
        for p in self.top_points + self.back_points: self.scene.removeItem(p)
        self.top_points.clear(); self.back_points.clear()
        
        cx, top, h, w = rect.center().x(), rect.top(), rect.height(), rect.width()
        # Arch depth proportional to the smaller of w or h (usually w in side view images)
        arch_depth = min(w, h) * 0.15
        
        for u, v in self.top_template:
            px = cx - 10 - (v * arch_depth)
            py = top + (u * h)
            cp = ControlPoint(px, py, color="blue")
            self.scene.addItem(cp)
            self.top_points.append(cp)
            
        for u, v in self.back_template:
            px = cx + 10 + (v * arch_depth)
            py = top + (u * h)
            cp = ControlPoint(px, py, color="orange")
            self.scene.addItem(cp)
            self.back_points.append(cp)
        self.update_geometry()

    def update_geometry(self):
        def draw_spline(pts, path_item):
            if len(pts) < 3: return
            x = np.array([p.pos().x() for p in pts]); y = np.array([p.pos().y() for p in pts])
            s = np.linspace(0, 1, len(pts))
            try:
                sx = make_interp_spline(s, x, k=3); sy = make_interp_spline(s, y, k=3)
                sf = np.linspace(0, 1, 100)
                path = QPainterPath(); path.moveTo(sx(0), sy(0))
                for t in sf[1:]: path.lineTo(sx(t), sy(t))
                path_item.setPath(path)
            except: pass
        draw_spline(self.top_points, self.top_path)
        draw_spline(self.back_points, self.back_path)
        self.geometryChanged.emit([])

    def load_background(self, file_path=None):
        if not file_path:
            file_name, _ = QFileDialog.getOpenFileName(self, "Open Side", "", "Images (*.png *.jpg *.bmp)")
        else: file_name = file_path
            
        if file_name:
            try:
                pixmap = QPixmap(file_name)
                if pixmap.isNull(): return
                if self.background_item: self.scene.removeItem(self.background_item)
                self.background_item = self.scene.addPixmap(pixmap)
                self.background_item.setZValue(-1); self.background_item.setOpacity(0.5)
                sr = self.scene.sceneRect()
                scale = min(sr.width()/pixmap.width(), sr.height()/pixmap.height()) * 0.95
                self.background_item.setScale(scale)
                iw, ih = pixmap.width()*scale, pixmap.height()*scale
                ix, iy = sr.center().x() - iw/2, sr.center().y() - ih/2
                self.background_item.setPos(ix, iy)
                
                from ..core.vision import VisionProcessor
                detection = VisionProcessor.detect_violin_body(file_name, view_type='side')
                if detection:
                    dx, dy, dw, dh = detection
                    self.reset_points_to_rect(QRectF(ix + dx*scale, iy + dy*scale, dw*scale, dh*scale))
                else: self.reset_points_to_rect(QRectF(ix, iy, iw, ih))
            except: pass

    def set_background_opacity(self, opacity):
        if self.background_item: self.background_item.setOpacity(opacity)

    def wheelEvent(self, event):
        f = 1.15 if event.angleDelta().y() > 0 else 1/1.15
        if 0.5 < self.current_zoom * f < 10.0:
            self.current_zoom *= f; self.scale(f, f)
