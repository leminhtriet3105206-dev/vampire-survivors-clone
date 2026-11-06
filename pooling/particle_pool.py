"""High-performance pooled Particle system for zero-allocation visual effects."""
import math
import random
from typing import List, Optional, Tuple
import pygame

from pooling.object_pool import ObjectPool

SCREEN_W = 1280
SCREEN_H = 720
C_WHITE = (255, 255, 255)


class PooledParticle:
    """Recyclable particle with directional sparks and glowing cores."""

    __slots__ = (
        "x",
        "y",
        "vx",
        "vy",
        "life",
        "max_life",
        "color",
        "size",
        "dir_spark",
        "_pooled",
    )

    def __init__(self, *args, **kwargs):
        self.x: float = 0.0
        self.y: float = 0.0
        self.vx: float = 0.0
        self.vy: float = 0.0
        self.life: int = 0
        self.max_life: int = 1
        self.color: Tuple[int, int, int] = (255, 255, 255)
        self.size: int = 4
        self.dir_spark: bool = False
        self._pooled: bool = False
        if args or kwargs:
            self.reset(*args, **kwargs)

    def reset(
        self,
        x: float,
        y: float,
        color: Tuple[int, int, int],
        speed: float = 2.0,
        size: int = 4,
        life: int = 30,
        angle: Optional[float] = None,
        spread: float = 0.45,
    ) -> "PooledParticle":
        """Reinitialize particle properties in-place."""
        self.x = float(x)
        self.y = float(y)
        ang = angle + random.uniform(-spread, spread) if angle is not None else random.uniform(0, math.tau)
        s = random.uniform(speed * 0.45, speed * 1.15)
        self.vx = math.cos(ang) * s
        self.vy = math.sin(ang) * s
        self.life = max(1, life)
        self.max_life = self.life
        self.color = color[:3] if len(color) >= 3 else (255, 255, 255)
        self.size = size
        self.dir_spark = angle is not None
        return self

    def update(self) -> bool:
        """Update physics. Returns True if alive, False if expired."""
        self.x += self.vx
        self.y += self.vy
        self.vx *= 0.91
        self.vy *= 0.91
        self.life -= 1
        return self.life > 0

    def draw(self, surf: pygame.Surface, cam_x: float, cam_y: float) -> None:
        """Render particle to surface with viewport culling."""
        t = self.life / max(1, self.max_life)
        r, g, b = self.color
        s = max(1, int(self.size * t))
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)

        if -12 < sx < SCREEN_W + 12 and -12 < sy < SCREEN_H + 12:
            if self.dir_spark and t > 0.35:
                tx = int(sx - self.vx * 2.4)
                ty = int(sy - self.vy * 2.4)
                pygame.draw.line(surf, (r, g, b), (tx, ty), (sx, sy), max(1, s))
                pygame.draw.circle(surf, C_WHITE, (sx, sy), max(1, s // 2))
            else:
                pygame.draw.circle(surf, (r, g, b), (sx, sy), s)
                if s >= 3:
                    pygame.draw.circle(surf, C_WHITE, (sx, sy), max(1, s // 2))


class ParticlePool:
    """Dedicated pool manager for game particles."""

    __slots__ = ("_pool",)

    def __init__(self, initial_capacity: int = 1000, max_size: int = 4000):
        self._pool: ObjectPool[PooledParticle] = ObjectPool(
            factory=PooledParticle,
            initial_capacity=initial_capacity,
            max_size=max_size,
        )

    def spawn(
        self,
        x: float,
        y: float,
        color: Tuple[int, int, int],
        speed: float = 2.0,
        size: int = 4,
        life: int = 30,
        angle: Optional[float] = None,
        spread: float = 0.45,
    ) -> PooledParticle:
        """Acquire and reset a single particle."""
        return self._pool.acquire(
            x=x,
            y=y,
            color=color,
            speed=speed,
            size=size,
            life=life,
            angle=angle,
            spread=spread,
        )

    def spawn_burst(
        self,
        x: float,
        y: float,
        color: Tuple[int, int, int],
        count: int = 8,
        speed: float = 2.5,
        size: int = 4,
        life: int = 24,
    ) -> List[PooledParticle]:
        """Spawn a radial burst of particles."""
        particles = []
        for _ in range(count):
            p = self.spawn(x, y, color, speed=speed, size=size, life=life)
            particles.append(p)
        return particles

    def release(self, particle: PooledParticle) -> bool:
        """Return a particle back to the pool."""
        return self._pool.release(particle)

    def release_many(self, particles: List[PooledParticle]) -> int:
        """Bulk release dead particles."""
        return self._pool.release_many(particles)

    @property
    def available_count(self) -> int:
        return self._pool.available_count

    @property
    def active_count(self) -> int:
        return self._pool.active_count
