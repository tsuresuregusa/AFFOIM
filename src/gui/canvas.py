from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsEllipseItem, QGraphicsPathItem, QFileDialog
from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QRectF
from PyQt6.QtGui import QPainter, QPen, QPainterPath, QBrush, QColor, QPixmap, QImage
from ..core.geometry import Point, BezierCurve
import numpy as np
from scipy.interpolate import make_interp_spline, UnivariateSpline

class ControlPoint(QGraphicsEllipseItem):
    def __init__(self, x, y, color="red", r=5, parent=None):
        super().__init__(-r, -r, 2*r, 2*r, parent)
        self.setPos(x, y)
        self.setBrush(QBrush(QColor("white")))
        self.setPen(QPen(Qt.GlobalColor.black, 2.0))
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
            (0.00, 0.00, "black"), # 0: Top Block
            (0.35, 0.02, "black"),   # 1
            (0.70, 0.10, "black"),   # 2
            (0.85, 0.22, "black"),   # 3
            (0.75, 0.35, "black"),   # 4
            (0.94, 0.40, "black"), # 5: Upper Corner
            (0.65, 0.45, "black"),   # 6
            (0.58, 0.53, "black"),   # 7: Waist
            (0.65, 0.60, "black"),   # 8
            (0.96, 0.64, "black"), # 9: Lower Corner
            (0.80, 0.68, "black"),   # 10
            (0.95, 0.78, "black"),   # 11
            (1.00, 0.86, "black"),   # 12
            (0.70, 0.95, "black"),   # 13
            (0.00, 1.00, "black")  # 14: Bottom Block
        ]
        
        self.path_item = QGraphicsPathItem()
        pen = QPen(Qt.GlobalColor.black, 2.0)
        pen.setCosmetic(True)
        self.path_item.setPen(pen)
        self.scene.addItem(self.path_item)
        
        self.reset_points_to_rect(self.scene.sceneRect())
        self.scene.itemIndexMethod = lambda: QGraphicsScene.ItemIndexMethod.NoIndex
        self.scene.update_geometry = self.update_geometry
        self.update_geometry()
        
        self.current_zoom = 1.0
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    def reset_points_to_rect(self, rect):
        self.current_bb = rect
        # Try load custom default if available
        import os, json
        try:
            if os.path.exists("geometry_default.json"):
                with open("geometry_default.json", 'r') as f:
                    data = json.load(f)
                    if "outline" in data:
                        # Use loaded points. They might be (u,v) or (u,v,c).
                        # We normalize the format to (u,v,c) for convenience.
                        new_tmpl = []
                        for item in data["outline"]:
                            u, v = item[0], item[1]
                            c = item[2] if len(item) > 2 else "black"
                            new_tmpl.append((u, v, c))
                        self.normalized_template = new_tmpl
        except: pass

        for p in self.points: self.scene.removeItem(p)
        self.points.clear()
        
        cx, top, h, w = rect.center().x(), rect.top(), rect.height(), rect.width()
        half_w = w / 2.0
        
        for u, v, color in self.normalized_template:
            px = cx + (u * half_w)
            py = top + (v * h)
            cp = ControlPoint(px, py, color)
            self.scene.addItem(cp)
            self.points.append(cp)
        self.update_geometry()

    def get_current_template(self):
        """Returns normalized coordinates of current points relative to the bounding box."""
        if not hasattr(self, 'current_bb'): return [ (u,v) for u,v,c in self.normalized_template ]
        
        bb = self.current_bb
        cx = bb.center().x()
        half_w = bb.width() / 2.0
        top = bb.top()
        h = bb.height()
        
        template = []
        for p in self.points:
            pos = p.pos()
            u = (pos.x() - cx) / half_w if half_w != 0 else 0
            v = (pos.y() - top) / h if h != 0 else 0
            template.append((float(u), float(v)))
        return template

    def update_geometry(self):
        if len(self.points) < 15: return
        path = QPainterPath()
        
        # Helper for Splines with Geometric Boundary Conditions (Phantom Points)
        def get_spline_coords(pts, k_val=3, flat_start=False, flat_end=False):
            x = np.array([p.pos().x() for p in pts])
            y = np.array([p.pos().y() for p in pts])
            
            # --- Phantom Points for Symmetry (Horizontal Tangent) ---
            # If we want a flat tangent at the start (P0), we add a virtual point P_minus1
            # that is the mirror of P1 across the vertical axis intersecting P0.
            # Symmetry ensures the derivative at P0 is 0.
            
            # Original Indices tracking
            start_idx = 0
            end_idx = len(x) - 1
            
            if flat_start:
                # Mirror P1 across P0
                # P0 is (x[0], y[0]). P1 is (x[1], y[1]).
                # Virt = (x[0] - (x[1]-x[0]), y[1]) => (2*x[0] - x[1], y[1])
                virt_x = 2 * x[0] - x[1]
                virt_y = y[1]
                x = np.r_[virt_x, x]
                y = np.r_[virt_y, y]
                start_idx += 1 # Original start is now at index 1
                end_idx += 1
                
            if flat_end:
                # Mirror P_last-1 across P_last
                # P_last is (x[-1], y[-1]). P_prev is (x[-2], y[-2]).
                virt_x = 2 * x[-1] - x[-2]
                virt_y = y[-2]
                x = np.r_[x, virt_x]
                y = np.r_[y, virt_y]
            
            # Chord-Length Parameterization
            dist = np.sqrt(np.diff(x)**2 + np.diff(y)**2)
            if np.sum(dist) < 1.0: return np.c_[x, y]
            
            t = np.hstack(([0], np.cumsum(dist)))
            t /= t[-1] # Normalize 0..1
            
            # Determine t-range for the ACTUAL curve (excluding phantom segments)
            t_min = t[start_idx]
            t_max = t[end_idx]
            
            # Fit Spline
            try:
                k = min(k_val, len(x)-1)
                bspl_x = make_interp_spline(t, x, k=k)
                bspl_y = make_interp_spline(t, y, k=k)
                
                # Interpolate only within the valid original segment
                fine_t = np.linspace(t_min, t_max, 100)
                return np.c_[bspl_x(fine_t), bspl_y(fine_t)]
            except:
                # Fallback: return original points if spline fails
                # Strip phantom points before returning
                orig_x = x[start_idx : end_idx+1]
                orig_y = y[start_idx : end_idx+1]
                return np.c_[orig_x, orig_y]

        # Define Sections
        # Upper: 0-5 (Flat Start for Neck joint)
        # C-Bout: 5-9
        # Lower: 9-14 (Flat End for Endpin joint)
        sections = [
            (range(0, 6), 3, True, False),
            (range(5, 10), 2, False, False),
            (range(9, 15), 3, False, True)
        ]
        
        # 1. Draw Right Side
        first_pt = True
        right_coords_list = []
        
        for (indices, k_val, f_start, f_end) in sections:
            subset = [self.points[i] for i in indices]
            coords = get_spline_coords(subset, k_val, f_start, f_end)
            right_coords_list.append(coords)
            
            if first_pt:
                path.moveTo(coords[0,0], coords[0,1])
                first_pt = False
            for i in range(1, len(coords)):
                path.lineTo(coords[i,0], coords[i,1])
                
        # 2. Draw Left Side (Mirrored dynamically across P0-P14 axis)
        # Calculate Axis of Symmetry from the CURRENT positions of Top and Bottom
        p0_x = self.points[0].pos().x()
        p14_x = self.points[14].pos().x()
        axis_x = (p0_x + p14_x) / 2.0
        
        # Consolidate Right Side
        right_array = np.vstack(right_coords_list)
        # Store Right Side Smooth Outline (for Plate Generator which needs half-profile)
        self.smooth_right_outline = [Point(x, y) for x, y in right_array]
        
        # Calculate Left Side (Mirrored)
        # x_mirrored = 2*axis - x_orig
        left_array_x = 2 * axis_x - right_array[:, 0]
        left_array_y = right_array[:, 1]
        left_array = np.column_stack((left_array_x, left_array_y))
        
        # Reverse Left Side to draw from Bottom back to Top
        left_array_reversed = left_array[::-1]
        
        # Draw Left Side
        for i in range(len(left_array_reversed)):
            # Avoid duplicating the very bottom point if it matches?
            # Usually strict mirroring implies they meet at P14.
            path.lineTo(left_array_reversed[i, 0], left_array_reversed[i, 1])

        path.closeSubpath()
        self.path_item.setPath(path)
        
        # Store Smooth Outline for Physics/Plate Map
        # Combine Right + Left(Reversed)
        full_loop_np = np.vstack((right_array, left_array_reversed))
        self.smooth_outline = [Point(x, y) for x, y in full_loop_np]
        
        # Emit CONTROL POINTS for Physics (Physics uses sparse model)
        # But we offer smooth_outline for visual consumers
        self.geometryChanged.emit([Point(p.pos().x(), p.pos().y()) for p in self.points])

    def get_simplified_outline(self):
        """Returns a smooth outline skipping corner points (P4-P6, P8-P10) for the height map."""
        if len(self.points) < 15: return []
        
        # We use a single spline across P3 -> P7 -> P11 (Subset based)
        indices = [0, 1, 2, 3, 7, 11, 12, 13, 14]
        subset = [self.points[i] for i in indices]
        
        x = np.array([p.pos().x() for p in subset])
        y = np.array([p.pos().y() for p in subset])
        
        # Chord-Length Parameterization
        dist = np.sqrt(np.diff(x)**2 + np.diff(y)**2)
        t = np.hstack(([0], np.cumsum(dist)))
        t /= t[-1]
        
        try:
            k = 3
            bspl_x = make_interp_spline(t, x, k=k)
            bspl_y = make_interp_spline(t, y, k=k)
            fine_t = np.linspace(0, 1, 100)
            coords = np.c_[bspl_x(fine_t), bspl_y(fine_t)]
            return [Point(pt[0], pt[1]) for pt in coords]
        except:
            return [Point(p.pos().x(), p.pos().y()) for p in subset]

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
                
                valid_detection = False
                if detection:
                    dx, dy, dw, dh = detection
                    body_h = dh * scale
                    body_w = dw * scale
                    
                    # 1. Reject Tiny Noise (Chinrest, etc.)
                    if body_h > ih * 0.45:
                        
                        # 2. Rejection Logic for Neck/Scroll Inclusion
                        # Standard violin body aspect ratio is ~1.7 (356mm / 208mm)
                        # If ratio > 1.75, we likely have the neck included.
                        ratio = body_h / body_w
                        if ratio > 1.72:
                            # Trim the top (neck) to force a standard body ratio ~1.72
                            target_h = body_w * 1.72
                            diff = body_h - target_h
                            # OFFSET FIX: Lower the whole box by 15px to avoid the neck heel
                            body_top_y = (iy + dy * scale) + diff + 15
                            body_h = target_h
                        else:
                            body_top_y = (iy + dy * scale) + 15
                        
                        body_center_x = ix + (dx + dw/2) * scale
                        
                        valid_detection = True
                        target_rect = QRectF(body_center_x - body_w/2, body_top_y, body_w, body_h)
                        self.reset_points_to_rect(target_rect)
                        
                        # Standardized Zoom: Height-limited zoom for matching scale with side view
                        self.fitInView(target_rect.adjusted(-100, -50, 100, 50), Qt.AspectRatioMode.KeepAspectRatio)
                
                if not valid_detection:
                    # Fallback: Assume a STANDARD VIOLIN BODY SHAPE (Ratio ~1.7)
                    target_w = iw * 0.38
                    target_h = target_w * 1.7 
                    
                    center_x = ix + iw / 2
                    center_y = iy + ih * 0.65 
                    
                    v_rect = QRectF(center_x - target_w/2, center_y - target_h/2, target_w, target_h)
                    
                    self.reset_points_to_rect(v_rect)
                    self.fitInView(v_rect.adjusted(-40, -20, 40, 20), Qt.AspectRatioMode.KeepAspectRatio)
            except Exception as e: print(f"Load error: {e}")

    def set_background_opacity(self, opacity):
        if self.background_item: self.background_item.setOpacity(opacity)

    def wheelEvent(self, event):
        f = 1.05 if event.angleDelta().y() > 0 else 1/1.05
        if 0.5 < self.current_zoom * f < 10.0:
            self.current_zoom *= f
            self.scale(f, f)
