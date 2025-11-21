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
        """
        Calculates the width of the C-bouts based on control points.
        Assumes points are ordered such that specific indices correspond to the C-bout area.
        For this prototype, we'll assume the C-bout width is roughly determined by the 
        minimum x-distance between left and right C-bout points relative to the center line.
        
        For a simple mock, we can just take the x-coordinate of a specific point that represents
        the C-bout width (e.g., the narrowest part).
        """
        # Mock implementation: 
        # Assuming points[2] is the inner-most point of the C-bout on one side.
        # We return its distance from the center (assuming center is x=0 or relative).
        # If points are absolute, we might look for the point with the smallest width.
        
        if not points:
            return 0.0
            
        # Just finding the minimum width (x-coordinate) among points that might represent the waist
        # This is a simplification for the prototype.
        # Let's assume the user is drawing the right half of the violin.
        # The "width" is just the x value.
        
        # Find the point with the minimum x value (closest to center axis)
        # excluding the top and bottom endpoints which might be on the axis.
        
        min_x = float('inf')
        for p in points:
             # Filter out points that are likely on the center line (x ~ 0)
             if p.x > 10: 
                 min_x = min(min_x, p.x)
                 
        return min_x if min_x != float('inf') else 100.0
