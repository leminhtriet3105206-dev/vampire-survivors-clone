"""High-performance 2D Spatial Hash Grid for fast spatial queries and collision detection."""
from collections import defaultdict
import math
from typing import Any, Callable, Dict, Generator, Iterable, List, Optional, Set, Tuple

from spatial.math_utils import dist_sq, in_radius_sq, dist_to_segment


class SpatialHashGrid:
    """
    2D Spatial Hash Grid partitioning 2D space into discrete grid cells.
    Reduces collision and proximity queries from O(N^2) or O(N) to O(1) / O(k).
    """

    __slots__ = ("cell_size", "inv_cell_size", "_grid", "_query_stamp", "_seen_entities")

    def __init__(self, cell_size: int = 120):
        self.cell_size: int = max(16, cell_size)
        self.inv_cell_size: float = 1.0 / self.cell_size
        self._grid: Dict[Tuple[int, int], List[Any]] = {}

    def clear(self) -> None:
        """Clear all grid buckets efficiently."""
        self._grid.clear()

    def _coord_to_cell(self, x: float, y: float) -> Tuple[int, int]:
        """Convert world coordinates (x, y) to grid cell indices."""
        return int(x // self.cell_size), int(y // self.cell_size)

    def insert(self, entity: Any, x: Optional[float] = None, y: Optional[float] = None) -> None:
        """Insert an entity into the grid based on its coordinates."""
        if x is None:
            x = getattr(entity, "x", 0.0)
        if y is None:
            y = getattr(entity, "y", 0.0)

        key = (int(x // self.cell_size), int(y // self.cell_size))
        bucket = self._grid.get(key)
        if bucket is None:
            self._grid[key] = [entity]
        else:
            bucket.append(entity)

    def insert_many(self, entities: Iterable[Any]) -> None:
        """Bulk insert multiple entities into the grid."""
        for e in entities:
            x = getattr(e, "x", 0.0)
            y = getattr(e, "y", 0.0)
            key = (int(x // self.cell_size), int(y // self.cell_size))
            bucket = self._grid.get(key)
            if bucket is None:
                self._grid[key] = [e]
            else:
                bucket.append(e)

    def query_radius(
        self,
        x: float,
        y: float,
        radius: float,
        exact: bool = True,
        predicate: Optional[Callable[[Any], bool]] = None,
    ) -> List[Any]:
        """
        Query all entities within a circular radius (x, y, radius).
        
        Args:
            x: Center X coordinate
            y: Center Y coordinate
            radius: Search radius
            exact: If True, filters candidates using exact Euclidean squared distance.
            predicate: Optional filter function (e.g. lambda e: e.alive)
        """
        min_cx = int((x - radius) // self.cell_size)
        max_cx = int((x + radius) // self.cell_size)
        min_cy = int((y - radius) // self.cell_size)
        max_cy = int((y + radius) // self.cell_size)

        results: List[Any] = []
        r_sq = radius * radius

        grid = self._grid
        for cx in range(min_cx, max_cx + 1):
            for cy in range(min_cy, max_cy + 1):
                bucket = grid.get((cx, cy))
                if not bucket:
                    continue
                for entity in bucket:
                    if predicate is not None and not predicate(entity):
                        continue
                    if exact:
                        ex = getattr(entity, "x", 0.0)
                        ey = getattr(entity, "y", 0.0)
                        dx = ex - x
                        if dx > radius or dx < -radius:
                            continue
                        dy = ey - y
                        if dy > radius or dy < -radius:
                            continue
                        if dx * dx + dy * dy <= r_sq:
                            results.append(entity)
                    else:
                        results.append(entity)

        return results

    def query_rect(
        self,
        min_x: float,
        min_y: float,
        max_x: float,
        max_y: float,
        predicate: Optional[Callable[[Any], bool]] = None,
    ) -> List[Any]:
        """Query all entities within an axis-aligned bounding box."""
        min_cx = int(min_x // self.cell_size)
        max_cx = int(max_x // self.cell_size)
        min_cy = int(min_y // self.cell_size)
        max_cy = int(max_y // self.cell_size)

        results: List[Any] = []
        grid = self._grid
        for cx in range(min_cx, max_cx + 1):
            for cy in range(min_cy, max_cy + 1):
                bucket = grid.get((cx, cy))
                if not bucket:
                    continue
                for entity in bucket:
                    if predicate is not None and not predicate(entity):
                        continue
                    ex = getattr(entity, "x", 0.0)
                    ey = getattr(entity, "y", 0.0)
                    if min_x <= ex <= max_x and min_y <= ey <= max_y:
                        results.append(entity)

        return results

    def query_segment(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        thickness: float = 20.0,
        predicate: Optional[Callable[[Any], bool]] = None,
    ) -> List[Any]:
        """Query entities near a line segment (e.g. whip strike, laser beam)."""
        min_x = min(x1, x2) - thickness
        max_x = max(x1, x2) + thickness
        min_y = min(y1, y2) - thickness
        max_y = max(y1, y2) + thickness

        candidates = self.query_rect(min_x, min_y, max_x, max_y, predicate=predicate)
        results: List[Any] = []
        p1 = (x1, y1)
        p2 = (x2, y2)
        th_sq = thickness * thickness

        for entity in candidates:
            ex = getattr(entity, "x", 0.0)
            ey = getattr(entity, "y", 0.0)
            d = dist_to_segment((ex, ey), p1, p2)
            if d <= thickness:
                results.append(entity)

        return results

    def find_nearest(
        self,
        x: float,
        y: float,
        max_radius: float = 1200.0,
        predicate: Optional[Callable[[Any], bool]] = None,
    ) -> Optional[Tuple[Any, float]]:
        """
        Find the single nearest entity within max_radius.
        Searches outward in concentric cell rings for optimal early-exit performance.
        Returns (nearest_entity, distance) or None if no entity found.
        """
        center_cx = int(x // self.cell_size)
        center_cy = int(y // self.cell_size)
        max_cell_dist = int(math.ceil(max_radius / self.cell_size))

        best_entity = None
        best_dist_sq = max_radius * max_radius

        grid = self._grid

        # Check center cell first
        bucket = grid.get((center_cx, center_cy))
        if bucket:
            for entity in bucket:
                if predicate is not None and not predicate(entity):
                    continue
                ex = getattr(entity, "x", 0.0)
                ey = getattr(entity, "y", 0.0)
                d2 = (ex - x) ** 2 + (ey - y) ** 2
                if d2 < best_dist_sq:
                    best_dist_sq = d2
                    best_entity = entity

        # Expand rings outward: ring 1, ring 2, ...
        for ring in range(1, max_cell_dist + 1):
            # If the best distance found so far is less than the closest possible point of this ring,
            # no cell in this or subsequent rings can beat best_dist_sq!
            closest_ring_dist = (ring - 1) * self.cell_size
            if best_entity is not None and closest_ring_dist * closest_ring_dist > best_dist_sq:
                break

            for dx in range(-ring, ring + 1):
                for dy in (-ring, ring):
                    cx = center_cx + dx
                    cy = center_cy + dy
                    bucket = grid.get((cx, cy))
                    if bucket:
                        for entity in bucket:
                            if predicate is not None and not predicate(entity):
                                continue
                            ex = getattr(entity, "x", 0.0)
                            ey = getattr(entity, "y", 0.0)
                            d2 = (ex - x) ** 2 + (ey - y) ** 2
                            if d2 < best_dist_sq:
                                best_dist_sq = d2
                                best_entity = entity

            for dy in range(-ring + 1, ring):
                for dx in (-ring, ring):
                    cx = center_cx + dx
                    cy = center_cy + dy
                    bucket = grid.get((cx, cy))
                    if bucket:
                        for entity in bucket:
                            if predicate is not None and not predicate(entity):
                                continue
                            ex = getattr(entity, "x", 0.0)
                            ey = getattr(entity, "y", 0.0)
                            d2 = (ex - x) ** 2 + (ey - y) ** 2
                            if d2 < best_dist_sq:
                                best_dist_sq = d2
                                best_entity = entity

        if best_entity is not None:
            return best_entity, math.sqrt(best_dist_sq)
        return None

