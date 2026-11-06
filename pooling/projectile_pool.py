"""High-performance pooled Projectile system to eliminate per-bullet heap allocations."""
import math
from typing import List, Optional, Set, Tuple
import pygame

from gfx.vfx import C_WHITE, SCREEN_H, SCREEN_W, draw_additive_glow, draw_magic_circle
from pooling.object_pool import ObjectPool


class PooledProjectile:
    """Recyclable projectile with motion ribbon trails, magic firing seal, and glow."""

    __slots__ = (
        "x",
        "y",
        "angle",
        "vx",
        "vy",
        "damage",
        "life",
        "max_life",
        "color",
        "size",
        "pierce",
        "hit_set",
        "alive",
        "is_enemy",
        "trail",
        "_pooled",
    )

    def __init__(self, *args, **kwargs):
        self.x: float = 0.0
        self.y: float = 0.0
        self.angle: float = 0.0
        self.vx: float = 0.0
        self.vy: float = 0.0
        self.damage: int = 10
        self.life: int = 60
        self.max_life: int = 60
        self.color: Tuple[int, int, int] = (255, 255, 255)
        self.size: int = 6
        self.pierce: int = 1
        self.hit_set: Set[int] = set()
        self.alive: bool = True
        self.is_enemy: bool = False
        self.trail: List[Tuple[float, float]] = []
        self._pooled: bool = False
        if args or kwargs:
            self.reset(*args, **kwargs)

    def reset(
        self,
        x: float,
        y: float,
        angle: float,
        speed: float,
        damage: int,
        lifetime: int,
        color: Tuple[int, int, int],
        size: int = 6,
        pierce: int = 1,
        is_enemy: bool = False,
    ) -> "PooledProjectile":
        """Reinitialize projectile properties in-place without garbage collection."""
        self.x = float(x)
        self.y = float(y)
        self.angle = float(angle)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.damage = int(damage)
        self.life = max(1, lifetime)
        self.max_life = self.life
        self.color = color[:3] if len(color) >= 3 else (255, 255, 255)
        self.size = size
        self.pierce = max(1, pierce)
        self.hit_set.clear()
        self.alive = True
        self.is_enemy = is_enemy
        self.trail.clear()
        return self

    def update(self) -> bool:
        """Update projectile position, trail, and lifetime."""
        self.trail.append((self.x, self.y))
        if len(self.trail) > 6:
            self.trail.pop(0)
        self.x += self.vx
        self.y += self.vy
        self.life -= 1
        if self.life <= 0:
            self.alive = False
        return self.alive

    def draw(self, surf: pygame.Surface, cam_x: float, cam_y: float) -> None:
        """Render projectile with glowing ribbon trail and additive glow."""
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        if -30 < sx < SCREEN_W + 30 and -30 < sy < SCREEN_H + 30:
            r, g, b = self.color[:3]
            # Glowing Motion Ribbon Trail
            if not self.is_enemy and len(self.trail) >= 2:
                for idx, (tx, ty) in enumerate(self.trail):
                    tsx, tsy = int(tx - cam_x), int(ty - cam_y)
                    tr_r = max(1, int(self.size * (idx + 1) / (len(self.trail) + 1)))
                    pygame.draw.circle(surf, (r // 2, g // 2, b // 2), (tsx, tsy), tr_r)
                # Magic Circle on initial firing (age < 10)
                age = self.max_life - self.life
                if age < 10:
                    ox, oy = int(self.trail[0][0] - cam_x), int(self.trail[0][1] - cam_y)
                    draw_magic_circle(surf, ox, oy, 14 + age, self.color, age * 0.25, 180 - age * 16)

            draw_additive_glow(surf, sx, sy, self.size * 3, self.color, 0.55)
            pygame.draw.circle(surf, self.color, (sx, sy), self.size)
            pygame.draw.circle(surf, C_WHITE, (sx, sy), max(2, self.size // 2))


class ProjectilePool:
    """Dedicated pool manager for game projectiles."""

    __slots__ = ("_pool",)

    def __init__(self, initial_capacity: int = 500, max_size: int = 2500):
        self._pool: ObjectPool[PooledProjectile] = ObjectPool(
            factory=PooledProjectile,
            initial_capacity=initial_capacity,
            max_size=max_size,
        )

    def spawn(
        self,
        x: float,
        y: float,
        angle: float,
        speed: float,
        damage: int,
        lifetime: int,
        color: Tuple[int, int, int],
        size: int = 6,
        pierce: int = 1,
        is_enemy: bool = False,
    ) -> PooledProjectile:
        """Acquire and reset a projectile."""
        return self._pool.acquire(
            x=x,
            y=y,
            angle=angle,
            speed=speed,
            damage=damage,
            lifetime=lifetime,
            color=color,
            size=size,
            pierce=pierce,
            is_enemy=is_enemy,
        )

    def release(self, proj: PooledProjectile) -> bool:
        """Return a projectile back to the pool."""
        return self._pool.release(proj)

    def release_many(self, projectiles: List[PooledProjectile]) -> int:
        """Bulk release dead projectiles."""
        return self._pool.release_many(projectiles)

    @property
    def available_count(self) -> int:
        return self._pool.available_count

    @property
    def active_count(self) -> int:
        return self._pool.active_count
