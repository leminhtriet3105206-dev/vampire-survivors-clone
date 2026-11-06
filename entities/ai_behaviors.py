"""Modular AI Steering Behaviors and Crowd Flocking system for enemies.

Behaviors:
  - FlockingSeparation  : Smooth crowd repulsive forces preventing 1000+ mobs from clumping
  - KitingBehavior      : Standoff distance keeping & tactical circling for ranged spellcasters
  - ExploderCharge      : Furious acceleration charge & lethal self-detonation for suicide bombers
  - SummonerOrbit       : Evasive orbital maneuvering & minion deployment for necromancers
"""
import math
import random
from typing import Any, List, Optional, Tuple

from gfx.vfx import ShockwaveRing
from pooling.particle_pool import PooledParticle
from spatial.math_utils import clamp, dist, norm


class FlockingSeparation:
    """Computes short-range repulsive separation vector using Spatial Hash Grid."""

    @staticmethod
    def compute(
        entity: Any,
        spatial_grid: Any,
        separation_radius: float = 30.0,
        max_neighbors: int = 6,
    ) -> Tuple[float, float]:
        """Query nearby neighbors and generate a soft-body repulsive push force."""
        if spatial_grid is None:
            return 0.0, 0.0

        ex, ey = entity.x, entity.y
        sep_x, sep_y = 0.0, 0.0
        count = 0

        # Query candidates from spatial hash grid in O(1)
        if hasattr(spatial_grid, "query_radius"):
            neighbors = spatial_grid.query_radius(ex, ey, separation_radius, exact=False)
        else:
            return 0.0, 0.0

        for other in neighbors:
            if other is entity or not getattr(other, "alive", True):
                continue
            dx = ex - other.x
            dy = ey - other.y
            d_sq = dx * dx + dy * dy
            if 0.001 < d_sq < separation_radius * separation_radius:
                d = math.sqrt(d_sq)
                # Stronger repulsion the closer they are
                force = (separation_radius - d) / separation_radius
                sep_x += (dx / d) * force
                sep_y += (dy / d) * force
                count += 1
                if count >= max_neighbors:
                    break

        if count > 0:
            return norm(sep_x, sep_y)
        return 0.0, 0.0


class KitingBehavior:
    """Tactical ranged movement maintaining optimal distance from player."""

    @staticmethod
    def compute_velocity(
        enemy: Any,
        player: Any,
        speed: float,
        ideal_dist: float = 230.0,
        min_dist: float = 170.0,
        max_dist: float = 300.0,
    ) -> Tuple[float, float]:
        dx = player.x - enemy.x
        dy = player.y - enemy.y
        d = math.hypot(dx, dy)
        if d <= 0.001:
            return 0.0, 0.0

        nx, ny = dx / d, dy / d

        if d < min_dist:
            # Too close: kite straight backwards
            return -nx * speed, -ny * speed
        elif d > max_dist:
            # Too far: close in
            return nx * speed, ny * speed
        else:
            # In sweet spot: strafe tangentially and slowly adjust range
            tangent_x = -ny
            tangent_y = nx
            radial_adj = ((d - ideal_dist) / (max_dist - min_dist)) * 0.4
            vx = tangent_x * 0.85 + nx * radial_adj
            vy = tangent_y * 0.85 + ny * radial_adj
            vnx, vny = norm(vx, vy)
            return vnx * speed, vny * speed


class ExploderChargeBehavior:
    """Suicide bomber acceleration and detonation trigger."""

    @staticmethod
    def update_exploder(
        enemy: Any,
        player: Any,
        base_speed: float,
        all_enemies: Optional[Any] = None,
        particles: Optional[list] = None,
        damage_numbers: Optional[list] = None,
        shockwaves: Optional[list] = None,
        sfx: Optional[Any] = None,
    ) -> Tuple[float, float, bool]:
        """Returns (vx, vy, is_exploding)."""
        from gfx.vfx import ShockwaveRing
        from pooling.particle_pool import PooledParticle

        dx = player.x - enemy.x
        dy = player.y - enemy.y
        d = math.hypot(dx, dy)

        if enemy.exploder_armed:
            enemy.exploder_fuse -= 1
            # Furious sprint during fuse count
            rush_speed = base_speed * 1.75
            nx, ny = norm(dx, dy)

            if enemy.exploder_fuse <= 0 or d <= enemy.radius + player.radius + 15:
                # DETONATE!
                enemy.alive = False
                blast_radius = 120.0
                blast_dmg = int(getattr(enemy, "damage", 15) * 2.5)

                if d <= blast_radius + player.radius:
                    player.take_damage(blast_dmg)
                    if sfx and hasattr(sfx, "play_damage"):
                        sfx.play_damage()

                # Also damage nearby enemies caught in friendly fire explosion
                if all_enemies is not None:
                    caught = []
                    if hasattr(all_enemies, "query_radius"):
                        caught = all_enemies.query_radius(enemy.x, enemy.y, blast_radius)
                    elif isinstance(all_enemies, list):
                        caught = [e for e in all_enemies if getattr(e, "alive", True) and dist((enemy.x, enemy.y), (e.x, e.y)) < blast_radius]
                    for other in caught:
                        if other is not enemy and getattr(other, "alive", True):
                            other.take_damage(blast_dmg // 2)

                if shockwaves is not None:
                    shockwaves.append(ShockwaveRing(enemy.x, enemy.y, (255, 90, 30), max_radius=140, duration=20, width=7))

                if particles is not None:
                    for _ in range(16):
                        col = random.choice([(255, 80, 20), (255, 200, 40), (200, 50, 20)])
                        if hasattr(particles, "spawn"):
                            particles.spawn(enemy.x, enemy.y, col, speed=5.0, size=5, life=30)
                        else:
                            particles.append(PooledParticle(enemy.x, enemy.y, col, speed=5.0, size=5, life=30))

                return 0.0, 0.0, True

            return nx * rush_speed, ny * rush_speed, False

        elif d <= 150.0:
            # Arm the fuse!
            enemy.exploder_armed = True
            enemy.exploder_fuse = 75  # ~1.25 seconds to react/dodge
            nx, ny = norm(dx, dy)
            return nx * base_speed * 1.4, ny * base_speed * 1.4, False

        else:
            nx, ny = norm(dx, dy)
            return nx * base_speed, ny * base_speed, False


class SummonerOrbitBehavior:
    """Evasive orbital maneuvers for necromancer lords."""

    @staticmethod
    def compute_velocity(
        enemy: Any,
        player: Any,
        speed: float,
        orbit_dist: float = 320.0,
    ) -> Tuple[float, float]:
        dx = player.x - enemy.x
        dy = player.y - enemy.y
        d = math.hypot(dx, dy)
        if d <= 0.001:
            return 0.0, 0.0

        nx, ny = dx / d, dy / d
        tangent_x = -ny
        tangent_y = nx

        # Blend orbit with distance stabilization
        radial_force = (d - orbit_dist) / 100.0
        vx = tangent_x * 0.7 + nx * radial_force * 0.5
        vy = tangent_y * 0.7 + ny * radial_force * 0.5
        vnx, vny = norm(vx, vy)
        return vnx * speed, vny * speed

