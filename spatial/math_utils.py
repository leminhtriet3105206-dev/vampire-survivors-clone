"""High-performance mathematical and geometrical utilities for 2D spatial calculations."""
import math
from typing import Tuple


def clamp(val: float, low: float, high: float) -> float:
    """Clamp a numerical value within [low, high]."""
    return max(low, min(high, val))


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation between a and b by factor t."""
    return a + (b - a) * t


def dist(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """Euclidean distance between two 2D points."""
    return math.hypot(a[0] - b[0], a[1] - b[1])


def dist_sq(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """Squared Euclidean distance between two 2D points (avoids sqrt)."""
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return dx * dx + dy * dy


def in_radius_sq(x1: float, y1: float, x2: float, y2: float, radius: float) -> bool:
    """Ultra-fast radial collision check with early bounding-box rejection."""
    dx = x2 - x1
    if dx > radius or dx < -radius:
        return False
    dy = y2 - y1
    if dy > radius or dy < -radius:
        return False
    return dx * dx + dy * dy <= radius * radius


def norm(dx: float, dy: float) -> Tuple[float, float]:
    """Normalize a 2D vector, returns (0.0, 0.0) if magnitude is 0."""
    d = math.hypot(dx, dy)
    if d == 0.0:
        return 0.0, 0.0
    return dx / d, dy / d


def angle_to(src: Tuple[float, float], dst: Tuple[float, float]) -> float:
    """Calculate angle in radians from src to dst."""
    return math.atan2(dst[1] - src[1], dst[0] - src[0])


def dist_to_segment(p: Tuple[float, float], a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """Shortest distance from point p to line segment a-b."""
    px, py = p
    ax, ay = a
    bx, by = b
    dx = bx - ax
    dy = by - ay
    l2 = dx * dx + dy * dy
    if l2 == 0.0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
    proj_x = ax + t * dx
    proj_y = ay + t * dy
    return math.hypot(px - proj_x, py - proj_y)
