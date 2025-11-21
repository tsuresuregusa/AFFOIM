from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsEllipseItem, QGraphicsPathItem, QFileDialog
from PyQt6.QtCore import Qt, pyqtSignal, QPointF
from PyQt6.QtGui import QPainter, QPen, QPainterPath, QBrush, QColor, QPixmap
from ..core.geometry import Point, BezierCurve
import numpy as np

from scipy.interpolate import make_interp_spline

class ControlPoint(QGraphicsEllipseItem):
    def __init__(self, x, y, color="red", r=5, parent=None):
        super().__init__(-r, -r, 2*r, 2*r, parent)
        self.setPos(x, y)
        self.setBrush(QBrush(QColor(color)))
        self.setFlags(QGraphicsEllipseItem.GraphicsItemFlag.ItemIsMovable | 
                      QGraphicsEllipseItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def itemChange(self, change, value):
        if change == QGraphicsEllipseItem.GraphicsItemChange.ItemPositionChange:
            if self.scene():
                self.scene().update_geometry()
        return super().itemChange(change, value)

class Canvas(QGraphicsView):
    geometryChanged = pyqtSignal(list) # Emits list of Point objects

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag) # Enable Panning
        
        # Enforce Aspect Ratio 1:2 (e.g., 400x800)
        # We set the scene rect to a fixed size.
        self.scene.setSceneRect(0, 0, 400, 800)
        
        # Background image item
        self.background_item = None

        # Initialize points for a half-violin shape (10 points)
        # Sections:
        # Upper: P0(R) -> P1(R) -> P2(R) -> P3(G)
        # Center: P3(G) -> P4(R) -> P5(R) -> P6(G)
        # Lower: P6(G) -> P7(R) -> P8(R) -> P9(R)
        
        self.points = []
        # Format: (x, y, color)
        initial_data = [
            (150, 50, "red"),    # P0: Top Start
            (170, 90, "red"),    # P1: Upper Bout 1 (Moved in and up slightly)
            (195, 140, "red"),   # P2: Upper Bout 2 (Adjusted)
            (150, 220, "green"), # P3: Upper Corner
            (130, 250, "red"),   # P4: C-Bout 1
            (130, 310, "red"),   # P5: C-Bout 2
            (150, 340, "green"), # P6: Lower Corner
            (200, 400, "red"),   # P7: Lower Bout 1
            (210, 480, "red"),   # P8: Lower Bout 2
            (150, 550, "red")    # P9: Bottom End
        ]
        
        self.path_item = QGraphicsPathItem()
        self.path_item.setPen(QPen(Qt.GlobalColor.black, 2))
        self.path_item.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        self.scene.addItem(self.path_item)

        for x, y, color in initial_data:
            cp = ControlPoint(x, y, color)
            self.scene.addItem(cp)
            self.points.append(cp)
            
        # Monkey patch scene to call our update method
        self.scene.update_geometry = self.update_geometry
        
        self.update_geometry()
        
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

    def update_geometry(self):
        path = QPainterPath()
        if not self.points:
            return

        # Sections indices
        # Upper: P0-P1-P2-P3
        # Center: P3-P4-P5-P6
        # Lower: P6-P7-P8-P9
        
        # Helper to fit spline for a subset of points
        def fit_spline(pts, bc_start=None, bc_end=None):
            # Extract coordinates
            x = np.array([p.pos().x() for p in pts])
            y = np.array([p.pos().y() for p in pts])
            
            # Parameterize by cumulative distance
            dx = np.diff(x)
            dy = np.diff(y)
            ds = np.sqrt(dx**2 + dy**2)
            s = np.concatenate(([0], np.cumsum(ds)))
            
            try:
                # Prepare boundary conditions
                # bc_type expects a tuple (start_bc, end_bc)
                # Each bc is (order, value). 1st derivative = 0 means slope 0.
                # But we are doing parametric spline x(s), y(s).
                # "Horizontal tangent" means dy/dx = 0 => dy/ds = 0.
                # So we enforce y'(s) = 0 at start/end.
                # x'(s) can be anything (usually 1 or proportional to ds).
                
                # make_interp_spline with bc_type applies to the dependent variable.
                # Here dependent is [x, y].
                # So bc should be shape (2,).
                
                bc = None
                if bc_start is not None or bc_end is not None:
                    # Default to natural (None) if not specified
                    start = bc_start if bc_start else (2, 0.0) # 2nd deriv=0 (Natural)
                    end = bc_end if bc_end else (2, 0.0)
                    
                    # We want dy/ds = 0.
                    # For x, we don't constrain it strictly to 0, but maybe we should?
                    # Actually, at the center line (vertical), dx/ds should be 0?
                    # No, the outline goes horizontal at top/bottom.
                    # So tangent vector is (1, 0) or (-1, 0).
                    # So dy/ds = 0. dx/ds != 0.
                    
                    # Construct BCs for [x, y]
                    # This is tricky with make_interp_spline for multidimensional y.
                    # It applies same BC structure?
                    # Let's fit x(s) and y(s) separately to be safe.
                    pass

                # Correct BC format for make_interp_spline (1D) is ((order, value), (order, value))
                # We fit X and Y separately.
                
                # X Spline (Natural)
                spl_x = make_interp_spline(s, x, k=3) 
                
                # Y Spline (Horizontal Tangent => 1st deriv = 0)
                # Error suggested "pair of iterables of pairs".
                # So we wrap the (order, value) tuple in a list.
                
                bc_y = None
                if bc_start == 'horizontal' or bc_end == 'horizontal':
                    # Start BC
                    if bc_start == 'horizontal':
                        start_bc = [(1, 0.0)]
                    else:
                        start_bc = [(2, 0.0)] # Natural
                        
                    # End BC
                    if bc_end == 'horizontal':
                        end_bc = [(1, 0.0)]
                    else:
                        end_bc = [(2, 0.0)] # Natural
                        
                    bc_y = (start_bc, end_bc)

                spl_y = make_interp_spline(s, y, k=3, bc_type=bc_y)
                
                # Evaluate
                s_new = np.linspace(s[0], s[-1], 50)
                x_new = spl_x(s_new)
                y_new = spl_y(s_new)
                
                return np.c_[x_new, y_new]

            except Exception as e:
                print(f"Spline error: {e}")
                return np.c_[x, y]

        # Define sections by indices
        sections_indices = [
            ([0, 1, 2, 3], 'horizontal', None), # Upper: Start horizontal
            ([3, 4, 5, 6], None, None),         # Center
            ([6, 7, 8, 9], None, 'horizontal')  # Lower: End horizontal
        ]
        
        first_point = True
        
        for indices, start_bc, end_bc in sections_indices:
            subset = [self.points[i] for i in indices]
            curve_coords = fit_spline(subset, start_bc, end_bc)
            
            if first_point:
                path.moveTo(curve_coords[0, 0], curve_coords[0, 1])
                first_point = False
            
            for i in range(1, len(curve_coords)):
                path.lineTo(curve_coords[i, 0], curve_coords[i, 1])
            
        self.path_item.setPath(path)
        
        # Emit geometry data
        geometry_data = [Point(p.pos().x(), p.pos().y()) for p in self.points]
        self.geometryChanged.emit(geometry_data)

    def load_background(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Image", "", "Image Files (*.png *.jpg *.bmp)")
        if file_name:
            try:
                pixmap = QPixmap(file_name)
                if pixmap.isNull():
                    print(f"Failed to load image: {file_name}")
                    return

                if self.background_item:
                    self.scene.removeItem(self.background_item)
                
                self.background_item = self.scene.addPixmap(pixmap)
                self.background_item.setZValue(-1) # Send to back
                self.background_item.setOpacity(0.5)
                
                # Scale image to fit the view
                view_rect = self.viewport().rect()
                # Adjust for potential scrollbars or margins roughly
                target_width = view_rect.width() * 0.9
                target_height = view_rect.height() * 0.9
                
                if target_width > 0 and target_height > 0:
                    scale_x = target_width / pixmap.width()
                    scale_y = target_height / pixmap.height()
                    scale = min(scale_x, scale_y)
                    self.background_item.setScale(scale)
                    
                    # Center the image
                    # We need to center it relative to the scene rect or view center
                    # For now, let's just place it at (0,0) or center of current view?
                    # Let's place it such that it's centered in the view.
                    # But scene coordinates might be different.
                    # Simple approach: Set pos to 0,0 and let user pan/zoom if we had that.
                    # Since we don't have pan/zoom yet, let's center it in the visible area.
                    
                    # Actually, let's just leave it at 0,0 but scaled.
                    self.background_item.setPos(0, 0)
                    
            except Exception as e:
                print(f"Error loading background: {e}")

    def set_background_opacity(self, opacity: float):
        if self.background_item:
            self.background_item.setOpacity(opacity)
