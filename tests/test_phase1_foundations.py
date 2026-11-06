"""Unit tests and performance benchmarks for Phase 1: Spatial Hash Grid and Object Pools."""
import math
import os
import sys
import time
import unittest

# Ensure root directory is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Pygame headless initialization
os.environ["SDL_VIDEODRIVER"] = "dummy"
import pygame
pygame.init()
pygame.display.set_mode((1, 1))

from spatial.math_utils import (
    clamp,
    dist,
    dist_sq,
    in_radius_sq,
    norm,
    angle_to,
    dist_to_segment,
)
from spatial.spatial_grid import SpatialHashGrid
from pooling.object_pool import ObjectPool
from pooling.particle_pool import ParticlePool, PooledParticle
from pooling.damage_number_pool import DamageNumberPool, PooledDamageNumber
from pooling.projectile_pool import ProjectilePool, PooledProjectile


class DummyEntity:
    __slots__ = ("x", "y", "alive", "id")

    def __init__(self, x: float, y: float, entity_id: int = 0):
        self.x = x
        self.y = y
        self.alive = True
        self.id = entity_id


class TestMathUtils(unittest.TestCase):
    def test_clamp(self):
        self.assertEqual(clamp(5, 0, 10), 5)
        self.assertEqual(clamp(-5, 0, 10), 0)
        self.assertEqual(clamp(15, 0, 10), 10)

    def test_dist_and_sq(self):
        p1 = (0.0, 0.0)
        p2 = (3.0, 4.0)
        self.assertEqual(dist_sq(p1, p2), 25.0)
        self.assertEqual(dist(p1, p2), 5.0)

    def test_in_radius_sq(self):
        self.assertTrue(in_radius_sq(0, 0, 3, 4, 5.0))
        self.assertFalse(in_radius_sq(0, 0, 3, 4, 4.9))
        self.assertFalse(in_radius_sq(0, 0, 100, 0, 50.0))

    def test_norm(self):
        nx, ny = norm(3.0, 4.0)
        self.assertAlmostEqual(nx, 0.6)
        self.assertAlmostEqual(ny, 0.8)
        self.assertEqual(norm(0.0, 0.0), (0.0, 0.0))

    def test_dist_to_segment(self):
        a = (0.0, 0.0)
        b = (10.0, 0.0)
        # Point right above middle
        self.assertAlmostEqual(dist_to_segment((5.0, 5.0), a, b), 5.0)
        # Point before start
        self.assertAlmostEqual(dist_to_segment((-5.0, 0.0), a, b), 5.0)
        # Point past end
        self.assertAlmostEqual(dist_to_segment((15.0, 0.0), a, b), 5.0)


class TestSpatialHashGrid(unittest.TestCase):
    def setUp(self):
        self.grid = SpatialHashGrid(cell_size=100)

    def test_insert_and_query_radius(self):
        e1 = DummyEntity(50, 50, 1)
        e2 = DummyEntity(120, 120, 2)
        e3 = DummyEntity(500, 500, 3)

        self.grid.insert_many([e1, e2, e3])

        # Query around (50, 50) with radius 80
        res = self.grid.query_radius(50, 50, 80)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0].id, 1)

        # Query around (50, 50) with radius 120 (covers e1 and e2)
        res = self.grid.query_radius(50, 50, 120)
        self.assertEqual(len(res), 2)
        ids = {e.id for e in res}
        self.assertEqual(ids, {1, 2})

    def test_find_nearest(self):
        e1 = DummyEntity(100, 100, 1)
        e2 = DummyEntity(300, 300, 2)
        self.grid.insert_many([e1, e2])

        nearest, d = self.grid.find_nearest(110, 110, max_radius=500)
        self.assertIsNotNone(nearest)
        self.assertEqual(nearest.id, 1)
        self.assertAlmostEqual(d, math.hypot(10, 10))

    def test_query_segment(self):
        e1 = DummyEntity(50, 10, 1)  # 10 units away from y=0
        e2 = DummyEntity(50, 40, 2)  # 40 units away from y=0
        self.grid.insert_many([e1, e2])

        res = self.grid.query_segment(0, 0, 100, 0, thickness=20)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0].id, 1)

    def test_spatial_performance_10k_entities(self):
        # Stress test: 10,000 entities in 2000x2000 arena
        entities = [
            DummyEntity((i * 37) % 2000, (i * 73) % 2000, i)
            for i in range(10000)
        ]
        t0 = time.perf_counter()
        self.grid.insert_many(entities)
        insert_time = time.perf_counter() - t0

        t0 = time.perf_counter()
        # 100 proximity queries
        for i in range(100):
            self.grid.query_radius((i * 19) % 2000, (i * 31) % 2000, 150)
        query_time = time.perf_counter() - t0

        print(f"\n[Spatial Benchmark] 10,000 entities insert: {insert_time*1000:.2f}ms | 100 radius queries: {query_time*1000:.2f}ms")
        self.assertLess(query_time, 0.05)  # 100 queries in < 50ms


class TestObjectPools(unittest.TestCase):
    def test_generic_pool(self):
        class Item:
            def __init__(self):
                self.val = 0
            def reset(self, val):
                self.val = val

        pool = ObjectPool(factory=Item, initial_capacity=10, max_size=50)
        self.assertEqual(pool.available_count, 10)

        # Acquire
        item = pool.acquire(42)
        self.assertEqual(item.val, 42)
        self.assertEqual(pool.available_count, 9)
        self.assertEqual(pool.active_count, 1)

        # Release
        self.assertTrue(pool.release(item))
        self.assertEqual(pool.available_count, 10)
        self.assertEqual(pool.active_count, 0)

        # Double release guard
        self.assertFalse(pool.release(item))

    def test_particle_pool(self):
        pool = ParticlePool(initial_capacity=50, max_size=200)
        p = pool.spawn(100, 200, (255, 0, 0), speed=3.0, life=15)
        self.assertEqual(p.x, 100.0)
        self.assertEqual(p.y, 200.0)
        self.assertEqual(p.life, 15)
        self.assertTrue(p.update())

        burst = pool.spawn_burst(50, 50, (0, 255, 0), count=10)
        self.assertEqual(len(burst), 10)

        pool.release(p)
        pool.release_many(burst)

    def test_damage_number_pool(self):
        pool = DamageNumberPool(initial_capacity=50, max_size=200)
        font = pygame.font.Font(None, 24)

        d_hit = pool.spawn(100, 100, 150)
        self.assertEqual(d_hit.value, "150")

        d_crit = pool.spawn(100, 100, 450, is_crit=True)
        self.assertEqual(d_crit.value, "450!")

        d_heal = pool.spawn(100, 100, 50, is_heal=True)
        self.assertEqual(d_heal.value, "+50 HP")

        surf = pygame.Surface((300, 300))
        d_crit.draw(surf, 0, 0, font)

        pool.release_many([d_hit, d_crit, d_heal])

    def test_projectile_pool(self):
        pool = ProjectilePool(initial_capacity=50, max_size=200)
        proj = pool.spawn(0, 0, angle=0.0, speed=10.0, damage=25, lifetime=30, color=(255, 200, 50))
        self.assertEqual(proj.vx, 10.0)
        self.assertEqual(proj.vy, 0.0)
        self.assertEqual(proj.damage, 25)

        proj.update()
        self.assertEqual(len(proj.trail), 1)
        self.assertEqual(proj.x, 10.0)

        surf = pygame.Surface((300, 300))
        proj.draw(surf, 0, 0)

        pool.release(proj)


if __name__ == "__main__":
    unittest.main()

