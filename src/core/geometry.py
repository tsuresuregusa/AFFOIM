import numpy as np
from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class Point:
    x: float
    y: float

    def to_tuple(self) -> Tuple[float, float]:
        return (self.x, self.y)

class BezierCurve:
    @staticmethod
    def cubic_bezier(p0: Point, p1: Point, p2: Point, p3: Point, t: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Calculate cubic Bezier curve points.
        B(t) = (1-t)^3 P0 + 3(1-t)^2 t P1 + 3(1-t) t^2 P2 + t^3 P3
        """
        one_minus_t = 1 - t
        
        x = (one_minus_t**3 * p0.x +
             3 * one_minus_t**2 * t * p1.x +
             3 * one_minus_t * t**2 * p2.x +
             t**3 * p3.x)
             
        y = (one_minus_t**3 * p0.y +
             3 * one_minus_t**2 * t * p1.y +
             3 * one_minus_t * t**2 * p2.y +
             t**3 * p3.y)
             
        return x, y

class GeometryExtractor:
    @staticmethod
    def calculate_c_bout_width(points: List[Point]) -> float:
        if not points: return 0.0
        min_x = float('inf')
        for p in points:
            if p.x > 10: min_x = min(min_x, p.x)
        return min_x if min_x != float('inf') else 100.0

    @staticmethod
    def calculate_area(points: List[Point]) -> float:
        """Calculates area using Shoelace formula for the half-outline."""
        if len(points) < 3: return 0.0
        area = 0.0
        n = len(points)
        for i in range(n):
            j = (i + 1) % n
            area += points[i].x * points[j].y
            area -= points[j].x * points[i].y
        return abs(area) / 2.0

    @staticmethod
    def get_max_depth(points: List[Point]) -> float:
        """Finds peak depth from arching points."""
        if not points: return 1.0
        # In ArchingCanvas, x is the depth axis
        xs = [p.x for p in points]
        return max(xs) - min(xs) if xs else 1.0
