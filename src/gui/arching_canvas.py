from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPathItem, QFileDialog
from PyQt6.QtCore import Qt, pyqtSignal, QRectF
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QPainterPath, QPixmap
from .canvas import ControlPoint
from ..core.vision import VisionProcessor
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
        self.scene.setSceneRect(0, 0, 400, 800)
        
        self.top_points = []
        self.back_points = []
        
        self.top_template = [(0,0),(0.05,0.2),(0.15,0.65),(0.5,1),(0.85,0.65),(0.95,0.2),(1,0)]
        self.back_template = [(0,0),(0.05,0.25),(0.15,0.7),(0.5,1),(0.85,0.7),(0.95,0.25),(1,0)]
        
        self.top_path = QGraphicsPathItem()
        self.top_path.setPen(QPen(Qt.GlobalColor.black, 2.0))
        self.scene.addItem(self.top_path)
        
        self.back_path = QGraphicsPathItem()
        self.back_path.setPen(QPen(Qt.GlobalColor.black, 2.0))
        self.scene.addItem(self.back_path)
        
        self.background_item = None
        self.current_zoom = 1.0
        self.reset_points_to_rect(self.scene.sceneRect())
        self.scene.update_geometry = self.update_geometry
        self.update_geometry()
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    def reset_points_to_rect(self, rect):
        self.current_bb = rect
        # Try load custom default if available
        import os, json
        try:
            if os.path.exists("geometry_default.json"):
                with open("geometry_default.json", 'r') as f:
                    data = json.load(f)
                    if "arching" in data:
                        arch_data = data["arching"]
                        self.top_template = arch_data.get("top", self.top_template)
                        self.back_template = arch_data.get("back", self.back_template)
        except: pass

        for p in self.top_points + self.back_points: self.scene.removeItem(p)
        self.top_points.clear(); self.back_points.clear()
        
        cx, top, h, w = rect.center().x(), rect.top(), rect.height(), rect.width()
        
        # Visual Parameters
        arch_depth = min(40.0, w)   # Max bulge depth
        rib_thickness = 35.0        # ~30mm separation between plates
        
        cx_top = cx - rib_thickness / 2.0
        cx_back = cx + rib_thickness / 2.0
        
        for i, (u, v) in enumerate(self.top_template):
            # Top Plate: Bulges Left (Negative X relative to its base)
            px = cx_top - (v * arch_depth)
            py = top + (u * h)
            cp = ControlPoint(px, py, color="blue")
            self.scene.addItem(cp)
            self.top_points.append(cp)
            
        for i, (u, v) in enumerate(self.back_template):
            # Back Plate: Bulges Right (Positive X relative to its base)
            px = cx_back + (v * arch_depth)
            py = top + (u * h)
            cp = ControlPoint(px, py, color="orange")
            self.scene.addItem(cp)
            self.back_points.append(cp)
            
        self.update_geometry()

    def get_current_template(self):
        """Returns normalized coordinates (bulge v at length u) for Top and Back."""
        if not hasattr(self, 'current_bb'): 
            return {"top": self.top_template, "back": self.back_template}
            
        bb = self.current_bb
        cx, top, h = bb.center().x(), bb.top(), bb.height()
        arch_depth = min(40.0, bb.width())
        rib_thickness = 35.0
        
        cx_top = cx - rib_thickness / 2.0
        cx_back = cx + rib_thickness / 2.0
        
        res = {"top": [], "back": []}
        for p in self.top_points:
            pos = p.pos()
            u = (pos.y() - top) / h if h != 0 else 0
            v = (cx_top - pos.x()) / arch_depth if arch_depth != 0 else 0
            res["top"].append((float(u), float(v)))
            
        for p in self.back_points:
            pos = p.pos()
            u = (pos.y() - top) / h if h != 0 else 0
            v = (pos.x() - cx_back) / arch_depth if arch_depth != 0 else 0
            res["back"].append((float(u), float(v)))
        return res

    def update_geometry(self):
        def draw_spline(pts, path_item):
            if len(pts) < 3: return
            x = np.array([p.pos().x() for p in pts]); y = np.array([p.pos().y() for p in pts])
            s = np.linspace(0, 1, len(pts))
            try:
                sx = make_interp_spline(s, x, k=3); sy = make_interp_spline(s, y, k=3)
                sf = np.linspace(0, 1, 200)
                path = QPainterPath(); path.moveTo(sx(0), sy(0))
                for t in sf[1:]: path.lineTo(sx(t), sy(t))
                path_item.setPath(path)
            except: pass
        draw_spline(self.top_points, self.top_path)
        draw_spline(self.back_points, self.back_path)
        # Emit current state
        self.geometryChanged.emit([p.pos() for p in self.top_points + self.back_points])


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
                
                detection = VisionProcessor.detect_violin_body(image_path=file_name, view_type='side')
                if detection:
                    dx, dy, dw, dh = detection
                    # TRIM: Remove scroll and endpin (approx 20% total)
                    trimmed_y = dy + dh * 0.10
                    trimmed_h = dh * 0.80
                    
                    body_center_x = ix + (dx + dw/2) * scale
                    body_top_y = iy + trimmed_y * scale
                    
                    body_h = trimmed_h * scale
                    body_w = dw * scale
                    
                    # Lozenge dimensions: Realistic rib thickness (max 35px)
                    v_w = min(body_w, 35.0) 
                    target_rect = QRectF(body_center_x - v_w/2, body_top_y, v_w, body_h)
                    self.reset_points_to_rect(target_rect)
                    
                    # Standardized Zoom: Height-limited zoom for matching scale with front view
                    self.fitInView(target_rect.adjusted(-100, -50, 100, 50), Qt.AspectRatioMode.KeepAspectRatio)
                else:
                    # Realistic 350px height fallback
                    cx, cy = sr.center().x(), sr.center().y()
                    v_rect = QRectF(cx - 15, cy - 175, 30, 350)
                    self.reset_points_to_rect(v_rect)
                    self.fitInView(v_rect.adjusted(-40, -20, 40, 20), Qt.AspectRatioMode.KeepAspectRatio)
            except Exception as e: print(f"Side load error: {e}")

    def set_background_opacity(self, opacity):
        if self.background_item: self.background_item.setOpacity(opacity)

    def wheelEvent(self, event):
        f = 1.05 if event.angleDelta().y() > 0 else 1/1.05
        if 0.5 < self.current_zoom * f < 10.0:
            self.current_zoom *= f; self.scale(f, f)
