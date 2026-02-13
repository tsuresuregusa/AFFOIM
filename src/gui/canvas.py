from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsEllipseItem, QGraphicsPathItem, QFileDialog
from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QRectF
from PyQt6.QtGui import QPainter, QPen, QPainterPath, QBrush, QColor, QPixmap, QImage
from ..core.geometry import Point, BezierCurve
import numpy as np
from scipy.interpolate import make_interp_spline

class ControlPoint(QGraphicsEllipseItem):
    def __init__(self, x, y, color="red", r=5, parent=None):
        super().__init__(-r, -r, 2*r, 2*r, parent)
        self.setPos(x, y)
        self.setBrush(QBrush(QColor(color)))
        self.setFlags(QGraphicsEllipseItem.GraphicsItemFlag.ItemIsMovable | 
                      QGraphicsEllipseItem.GraphicsItemFlag.ItemSendsGeometryChanges |
                      QGraphicsEllipseItem.GraphicsItemFlag.ItemIgnoresTransformations)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def itemChange(self, change, value):
        if change == QGraphicsEllipseItem.GraphicsItemChange.ItemPositionChange:
            if self.scene():
                self.scene().update_geometry()
        return super().itemChange(change, value)

class Canvas(QGraphicsView):
    geometryChanged = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.scene.setSceneRect(0, 0, 400, 800)
        
        self.points = []
        self.background_item = None
        
        # Stradivari Template (Normalized 0..1) - 4,3,4 distribution
        # u: x offset (normalized to half-width)
        # v: y offset (normalized to body height)
        self.normalized_template = [
            (0.00, 0.00, "green"), # 0: Top Block
            # Upper Bout (4 points)
            (0.35, 0.02, "red"),   # 1
            (0.70, 0.10, "red"),   # 2
            (0.85, 0.22, "red"),   # 3: Max width region
            (0.75, 0.35, "red"),   # 4
            (0.94, 0.40, "green"), # 5: Upper Corner
            # C-Bout (3 points)
            (0.65, 0.45, "red"),   # 6
            (0.58, 0.53, "red"),   # 7: Waist
            (0.65, 0.60, "red"),   # 8
            (0.96, 0.64, "green"), # 9: Lower Corner
            # Lower Bout (4 points)
            (0.80, 0.68, "red"),   # 10
            (0.95, 0.78, "red"),   # 11
            (1.00, 0.86, "red"),   # 12: Max width region
            (0.70, 0.95, "red"),   # 13
            (0.00, 1.00, "green")  # 14: Bottom Block
        ]
        
        self.path_item = QGraphicsPathItem()
        self.path_item.setPen(QPen(Qt.GlobalColor.black, 2))
        self.scene.addItem(self.path_item)
        
        self.reset_points_to_rect(self.scene.sceneRect())
        self.scene.update_geometry = self.update_geometry
        self.update_geometry()
        
        self.current_zoom = 1.0
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    def reset_points_to_rect(self, rect):
        for p in self.points: self.scene.removeItem(p)
        self.points.clear()
        
        cx, top, h, w = rect.center().x(), rect.top(), rect.height(), rect.width()
        half_w = (w / 2) * 0.95
        
        for u, v, color in self.normalized_template:
            px = cx + (u * half_w)
            py = top + (v * h)
            cp = ControlPoint(px, py, color)
            self.scene.addItem(cp)
            self.points.append(cp)
        self.update_geometry()

    def update_geometry(self):
        path = QPainterPath()
        if not self.points: return

        def fit_spline(pts, bc_start=None, bc_end=None):
            x = np.array([p.pos().x() for p in pts])
            y = np.array([p.pos().y() for p in pts])
            s = np.linspace(0, 1, len(pts))
            try:
                k = min(3, len(pts)-1)
                spl_x = make_interp_spline(s, x, k=k)
                bc_y = None
                if bc_start == 'horizontal' or bc_end == 'horizontal':
                    s_bc = [(1, 0.0)] if bc_start == 'horizontal' else [(2, 0.0)]
                    e_bc = [(1, 0.0)] if bc_end == 'horizontal' else [(2, 0.0)]
                    bc_y = (s_bc, e_bc)
                spl_y = make_interp_spline(s, y, k=k, bc_type=bc_y)
                
                s_new = np.linspace(0, 1, 50)
                return np.c_[spl_x(s_new), spl_y(s_new)]
            except:
                return np.c_[x, y]

        # Sections with 4,3,4 internals
        sections = [
            ([0,1,2,3,4,5], 'horizontal', None), # Top Bout (Block + 4 + Corner)
            ([5,6,7,8,9], None, None),           # C-Bout (Corner + 3 + Corner)
            ([9,10,11,12,13,14], None, 'horizontal') # Lower Bout (Corner + 4 + Block)
        ]
        
        first = True
        for indices, sbc, ebc in sections:
            subset = [self.points[i] for i in indices]
            coords = fit_spline(subset, sbc, ebc)
            if first:
                path.moveTo(coords[0,0], coords[0,1])
                first = False
            for i in range(1, len(coords)):
                path.lineTo(coords[i,0], coords[i,1])
        self.path_item.setPath(path)
        self.geometryChanged.emit([Point(p.pos().x(), p.pos().y()) for p in self.points])

    def load_background(self, file_path=None):
        if not file_path:
            file_name, _ = QFileDialog.getOpenFileName(self, "Open Image", "", "Images (*.png *.jpg *.bmp)")
        else: file_name = file_path
            
        if file_name:
            try:
                pixmap = QPixmap(file_name)
                if pixmap.isNull(): return
                if self.background_item: self.scene.removeItem(self.background_item)
                
                self.background_item = self.scene.addPixmap(pixmap)
                self.background_item.setZValue(-1)
                self.background_item.setOpacity(0.5)
                
                scene_rect = self.scene.sceneRect()
                scale = min(scene_rect.width()/pixmap.width(), scene_rect.height()/pixmap.height()) * 0.95
                self.background_item.setScale(scale)
                
                iw, ih = pixmap.width()*scale, pixmap.height()*scale
                ix, iy = scene_rect.center().x() - iw/2, scene_rect.center().y() - ih/2
                self.background_item.setPos(ix, iy)
                
                from ..core.vision import VisionProcessor
                detection = VisionProcessor.detect_violin_body(file_name, view_type='front')
                if detection:
                    dx, dy, dw, dh = detection
                    self.reset_points_to_rect(QRectF(ix + dx*scale, iy + dy*scale, dw*scale, dh*scale))
                else:
                    self.reset_points_to_rect(QRectF(ix, iy, iw, ih))
            except Exception as e: print(f"Load error: {e}")

    def set_background_opacity(self, opacity):
        if self.background_item: self.background_item.setOpacity(opacity)

    def wheelEvent(self, event):
        f = 1.15 if event.angleDelta().y() > 0 else 1/1.15
        if 0.5 < self.current_zoom * f < 10.0:
            self.current_zoom *= f
            self.scale(f, f)
