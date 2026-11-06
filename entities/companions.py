"""Companions, summons, and defensive emplacements (SoulMinion, Drone, Turret)."""
import math
import random
from typing import Any, List, Optional, Tuple
import pygame

from core.config import C_WHITE, SCREEN_H, SCREEN_W
from gfx.sprite_cache import get_skin_vfx_colors
from gfx.vfx import draw_additive_glow
from pooling.particle_pool import PooledParticle
from pooling.projectile_pool import PooledProjectile
from spatial.math_utils import angle_to, dist, lerp


class SoulMinion:
    """Summoned skeletal soul seeking nearby enemies and exploding on contact."""

    __slots__ = ("x", "y", "damage", "skin_id", "alive", "life", "max_life", "angle", "speed", "trail")

    def __init__(self, x: float, y: float, damage: int, skin_id: str = "default"):
        self.x: float = float(x)
        self.y: float = float(y)
        self.damage: int = damage
        self.skin_id: str = skin_id
        self.alive: bool = True
        self.life: int = 360
        self.max_life: int = 360
        self.angle: float = random.uniform(0, math.tau)
        self.speed: float = 3.8
        self.trail: List[Tuple[float, float]] = []

    def update(self, player, enemies: Any, damage_numbers: list, particles: list) -> None:
        self.life -= 1
        if self.life <= 0:
            self.alive = False
            return

        self.trail.append((self.x, self.y))
        if len(self.trail) > 6:
            self.trail.pop(0)

        target = None
        closest_d = 480.0

        if hasattr(enemies, "find_nearest"):
            res = enemies.find_nearest(self.x, self.y, max_radius=480.0, predicate=lambda e: getattr(e, "alive", True))
            if res:
                target, closest_d = res
        else:
            for e in enemies:
                if getattr(e, "alive", True):
                    d = dist((self.x, self.y), (e.x, e.y))
                    if d < closest_d:
                        closest_d = d
                        target = e

        if target:
            ang = angle_to((self.x, self.y), (target.x, target.y))
            self.x += math.cos(ang) * self.speed
            self.y += math.sin(ang) * self.speed
            t_radius = getattr(target, "radius", 14)
            if closest_d < t_radius + 12:
                col, _ = get_skin_vfx_colors(player, (50, 245, 190), (120, 255, 230))
                from weapons.weapon_base import deal_player_damage
                deal_player_damage(player, target, self.damage, damage_numbers, col)

                for _ in range(6):
                    if hasattr(particles, "spawn"):
                        particles.spawn(self.x, self.y, col, speed=3.6, size=4, life=22)
                    else:
                        p = PooledParticle()
                        p.reset(self.x, self.y, col, speed=3.6, size=4, life=22)
                        particles.append(p)
                self.alive = False
        else:
            self.angle += 0.05
            tx = player.x + math.cos(self.angle) * 56
            ty = player.y + math.sin(self.angle) * 56
            self.x = lerp(self.x, tx, 0.12)
            self.y = lerp(self.y, ty, 0.12)

    def draw(self, surf: pygame.Surface, cam_x: float, cam_y: float, tick: int) -> None:
        sx, sy = int(self.x - cam_x), int(self.y - cam_y)
        if -40 < sx < SCREEN_W + 40 and -40 < sy < SCREEN_H + 40:
            col = (40, 230, 185)
            draw_additive_glow(surf, sx, sy, 18, col, intensity=0.55)
            pygame.draw.circle(surf, (225, 245, 240), (sx, sy), 6)
            pygame.draw.circle(surf, col, (sx, sy), 8, 1)
            pygame.draw.circle(surf, (15, 55, 45), (sx - 2, sy - 1), 1)
            pygame.draw.circle(surf, (15, 55, 45), (sx + 2, sy - 1), 1)
            for i, (tx, ty) in enumerate(self.trail):
                tsx, tsy = int(tx - cam_x), int(ty - cam_y)
                tr_alpha = int(140 * (i + 1) / len(self.trail))
                pygame.draw.circle(surf, (*col, tr_alpha) if len(col) == 4 else col, (tsx, tsy), max(1, i // 2))


class Drone:
    """Companion drone orbiting the player and automatically engaging nearby targets."""

    ORBIT_RADIUS = 70
    ORBIT_SPEED  = 0.045
    SHOOT_CD     = 45
    DAMAGE       = 20
    RANGE        = 300
    COLOR        = (80, 200, 255)

    __slots__ = ("index", "angle", "shoot_cd")

    def __init__(self, index: int = 0):
        self.index: int = index
        self.angle: float = (math.tau / 4) * index
        self.shoot_cd: int = random.randint(0, self.SHOOT_CD)

    def update(self, player, enemies: Any, projectiles_out: list, damage_numbers: list, particles: list) -> None:
        self.angle += self.ORBIT_SPEED
        ox = player.x + math.cos(self.angle) * self.ORBIT_RADIUS
        oy = player.y + math.sin(self.angle) * self.ORBIT_RADIUS

        self.shoot_cd -= 1
        if self.shoot_cd <= 0:
            target = None
            best_d = float(self.RANGE)

            if hasattr(enemies, "find_nearest"):
                res = enemies.find_nearest(ox, oy, max_radius=float(self.RANGE), predicate=lambda e: getattr(e, "alive", True))
                if res:
                    target, best_d = res
            else:
                for e in enemies:
                    if getattr(e, "alive", True):
                        d = dist((ox, oy), (e.x, e.y))
                        if d < best_d:
                            best_d = d
                            target = e

            if target:
                self.shoot_cd = self.SHOOT_CD
                a = angle_to((ox, oy), (target.x, target.y))

                if hasattr(projectiles_out, "spawn"):
                    projectiles_out.spawn(ox, oy, a, speed=7.0, damage=self.DAMAGE, lifetime=50, color=self.COLOR, size=5)
                else:
                    proj = PooledProjectile()
                    proj.reset(ox, oy, a, speed=7.0, damage=self.DAMAGE, lifetime=50, color=self.COLOR, size=5)
                    projectiles_out.append(proj)

                for _ in range(3):
                    if hasattr(particles, "spawn"):
                        particles.spawn(ox, oy, self.COLOR, speed=2.0, life=15)
                    else:
                        p = PooledParticle()
                        p.reset(ox, oy, self.COLOR, speed=2.0, life=15)
                        particles.append(p)
            else:
                self.shoot_cd = self.SHOOT_CD // 2

    def draw(self, surf: pygame.Surface, cam_x: float, cam_y: float, player) -> None:
        ox = int(player.x + math.cos(self.angle) * self.ORBIT_RADIUS - cam_x)
        oy = int(player.y + math.sin(self.angle) * self.ORBIT_RADIUS - cam_y)
        px = int(player.x - cam_x)
        py = int(player.y - cam_y)
        pygame.draw.line(surf, (*self.COLOR, 60), (px, py), (ox, oy), 1)
        glow = pygame.Surface((28, 28), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*self.COLOR, 50), (14, 14), 12)
        surf.blit(glow, (ox - 14, oy - 14))
        pygame.draw.circle(surf, self.COLOR, (ox, oy), 7)
        pygame.draw.circle(surf, C_WHITE, (ox, oy), 3)


class Turret:
    """Stationary defense turret firing at enemies in range."""

    RANGE    = 220
    SHOOT_CD = 35
    DAMAGE   = 28
    LIFETIME = 1800
    RADIUS   = 14
    COLOR    = (255, 180, 40)

    __slots__ = ("x", "y", "shoot_cd", "life", "alive", "angle")

    def __init__(self, x: float, y: float):
        self.x: float = float(x)
        self.y: float = float(y)
        self.shoot_cd: int = 0
        self.life: int = self.LIFETIME
        self.alive: bool = True
        self.angle: float = 0.0

    def update(self, enemies: Any, projectiles_out: list, damage_numbers: list, particles: list) -> None:
        self.life -= 1
        if self.life <= 0:
            self.alive = False
            return

        self.shoot_cd -= 1
        if self.shoot_cd <= 0:
            target = None
            best_d = float(self.RANGE)

            if hasattr(enemies, "find_nearest"):
                res = enemies.find_nearest(self.x, self.y, max_radius=float(self.RANGE), predicate=lambda e: getattr(e, "alive", True))
                if res:
                    target, best_d = res
            else:
                for e in enemies:
                    if getattr(e, "alive", True):
                        d = dist((self.x, self.y), (e.x, e.y))
                        if d < best_d:
                            best_d = d
                            target = e

            if target:
                self.shoot_cd = self.SHOOT_CD
                self.angle = angle_to((self.x, self.y), (target.x, target.y))
                a = self.angle

                if hasattr(projectiles_out, "spawn"):
                    projectiles_out.spawn(self.x, self.y, a, speed=8.0, damage=self.DAMAGE, lifetime=40, color=self.COLOR, size=5)
                else:
                    proj = PooledProjectile()
                    proj.reset(self.x, self.y, a, speed=8.0, damage=self.DAMAGE, lifetime=40, color=self.COLOR, size=5)
                    projectiles_out.append(proj)

                for _ in range(3):
                    if hasattr(particles, "spawn"):
                        particles.spawn(self.x, self.y, self.COLOR, speed=2.0, life=12)
                    else:
                        p = PooledParticle()
                        p.reset(self.x, self.y, self.COLOR, speed=2.0, life=12)
                        particles.append(p)
            else:
                self.shoot_cd = self.SHOOT_CD // 2

    def draw(self, surf: pygame.Surface, cam_x: float, cam_y: float) -> None:
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        if sx + 20 < 0 or sx - 20 > SCREEN_W or sy + 20 < 0 or sy - 20 > SCREEN_H:
            return

        range_surf = pygame.Surface((self.RANGE * 2 + 2, self.RANGE * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(range_surf, (*self.COLOR, 18), (self.RANGE + 1, self.RANGE + 1), self.RANGE)
        pygame.draw.circle(range_surf, (*self.COLOR, 50), (self.RANGE + 1, self.RANGE + 1), self.RANGE, 1)
        surf.blit(range_surf, (sx - self.RANGE - 1, sy - self.RANGE - 1))

        pygame.draw.circle(surf, (80, 60, 20), (sx, sy), self.RADIUS)
        pygame.draw.circle(surf, self.COLOR, (sx, sy), self.RADIUS - 2)

        ex = sx + int(math.cos(self.angle) * (self.RADIUS + 8))
        ey = sy + int(math.sin(self.angle) * (self.RADIUS + 8))
        pygame.draw.line(surf, (255, 220, 80), (sx, sy), (ex, ey), 4)

        lf = self.life / self.LIFETIME
        bw = self.RADIUS * 2
        pygame.draw.rect(surf, (60, 40, 0), (sx - self.RADIUS, sy + self.RADIUS + 4, bw, 4))
        pygame.draw.rect(surf, self.COLOR, (sx - self.RADIUS, sy + self.RADIUS + 4, int(bw * lf), 4))

