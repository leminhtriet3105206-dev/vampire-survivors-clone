"""Visual effects rendering helpers (Additive glow, lightning arcs, magic circles, shockwaves)."""
import math
import random
from typing import Dict, List, Optional, Tuple
import pygame

from spatial.math_utils import clamp

SCREEN_W = 1280
SCREEN_H = 720
C_WHITE = (255, 255, 255)

_ADDITIVE_GLOW_CACHE: Dict[Tuple[int, Tuple[int, int, int]], pygame.Surface] = {}


def draw_additive_glow(
    surf: pygame.Surface,
    sx: int,
    sy: int,
    radius: int,
    color: tuple,
    intensity: float = 0.65,
) -> None:
    """Draw a multi-layered neon glow using BLEND_RGB_ADD with pre-rendered cache."""
    radius = max(4, min(140, (int(radius) // 2) * 2))
    r, g, b = color[:3]
    cr = min(255, max(0, int(r * intensity)))
    cg = min(255, max(0, int(g * intensity)))
    cb = min(255, max(0, int(b * intensity)))
    key = (radius, (cr // 8 * 8, cg // 8 * 8, cb // 8 * 8))

    if key not in _ADDITIVE_GLOW_CACHE:
        if len(_ADDITIVE_GLOW_CACHE) > 256:
            _ADDITIVE_GLOW_CACHE.clear()
        gs = pygame.Surface((radius * 2, radius * 2))
        gs.fill((0, 0, 0))
        c = (radius, radius)
        pygame.draw.circle(gs, (key[1][0] // 3, key[1][1] // 3, key[1][2] // 3), c, radius)
        pygame.draw.circle(
            gs,
            (int(key[1][0] * 0.65), int(key[1][1] * 0.65), int(key[1][2] * 0.65)),
            c,
            int(radius * 0.62),
        )
        pygame.draw.circle(gs, key[1], c, max(2, int(radius * 0.3)))
        _ADDITIVE_GLOW_CACHE[key] = gs

    glow_s = _ADDITIVE_GLOW_CACHE[key]
    surf.blit(glow_s, (sx - radius, sy - radius), special_flags=pygame.BLEND_RGB_ADD)


def draw_jagged_lightning_arc(
    surf: pygame.Surface,
    p1: Tuple[int, int],
    p2: Tuple[int, int],
    outer_color: tuple,
    core_color: tuple = C_WHITE,
    width: int = 3,
    branches: bool = True,
    dark_haki: bool = False,
) -> None:
    """Draw a branching jagged lightning bolt (Midpoint displacement + outer glow)."""
    x1, y1 = p1
    x2, y2 = p2
    length = math.hypot(x2 - x1, y2 - y1)
    steps = max(4, min(9, int(length // 26) + 3))
    jitter = min(22, max(6, int(length * 0.11)))
    pts = [(x1, y1)]
    for i in range(1, steps):
        t = i / steps
        bx = int(x1 + (x2 - x1) * t + random.randint(-jitter, jitter))
        by = int(y1 + (y2 - y1) * t + random.randint(-jitter, jitter))
        pts.append((bx, by))
    pts.append((x2, y2))

    pygame.draw.lines(surf, outer_color[:3], False, pts, width + 3)
    if dark_haki:
        pygame.draw.lines(surf, (18, 4, 12), False, pts, max(2, width))
    else:
        pygame.draw.lines(surf, core_color[:3], False, pts, max(1, width - 1))

    if branches and len(pts) >= 4:
        for idx in range(1, len(pts) - 1, 2):
            bx, by = pts[idx]
            ang = math.atan2(y2 - y1, x2 - x1) + random.choice([-0.75, 0.75])
            blen = random.uniform(14, 30)
            b_mid = (
                int(bx + math.cos(ang) * (blen * 0.5) + random.randint(-5, 5)),
                int(by + math.sin(ang) * (blen * 0.5) + random.randint(-5, 5)),
            )
            b_end = (int(bx + math.cos(ang) * blen), int(by + math.sin(ang) * blen))
            pygame.draw.lines(surf, outer_color[:3], False, [(bx, by), b_mid, b_end], max(1, width - 1))


def draw_magic_circle(
    surf: pygame.Surface,
    sx: int,
    sy: int,
    radius: int,
    color: tuple,
    angle: float,
    alpha: int = 165,
) -> None:
    """Draw a rotating arcane geometric hexagram seal."""
    if radius < 6 or sx + radius < 0 or sx - radius > SCREEN_W or sy + radius < 0 or sy - radius > SCREEN_H:
        return
    ms = pygame.Surface((radius * 2 + 6, radius * 2 + 6), pygame.SRCALPHA)
    c = (radius + 3, radius + 3)
    rgba = (*color[:3], clamp(alpha, 0, 255))
    pygame.draw.circle(ms, rgba, c, radius, 2)
    pygame.draw.circle(ms, (*C_WHITE, clamp(alpha // 2, 0, 255)), c, int(radius * 0.74), 1)

    for tri in (0.0, math.pi / 3.0):
        pts = [
            (
                c[0] + int(math.cos(angle + tri + k * (math.tau / 3)) * (radius - 2)),
                c[1] + int(math.sin(angle + tri + k * (math.tau / 3)) * (radius - 2)),
            )
            for k in range(3)
        ]
        pygame.draw.polygon(ms, rgba, pts, 1)
    surf.blit(ms, (sx - radius - 3, sy - radius - 3))


class ShockwaveRing:
    """Expanding shockwave ripple on level-up or skill awakening."""

    __slots__ = ("x", "y", "color", "max_radius", "duration", "life", "width")

    def __init__(
        self,
        x: float,
        y: float,
        color: tuple,
        max_radius: int = 220,
        duration: int = 36,
        width: int = 5,
    ):
        self.x: float = float(x)
        self.y: float = float(y)
        self.color: tuple = color
        self.max_radius: int = max_radius
        self.duration: int = duration
        self.life: int = duration
        self.width: int = width

    def update(self) -> bool:
        self.life -= 1
        return self.life > 0

    def draw(self, surf: pygame.Surface, cam_x: float, cam_y: float) -> None:
        progress = 1.0 - (self.life / max(1, self.duration))
        eased = 1.0 - (1.0 - progress) ** 3
        r = max(4, int(self.max_radius * eased))
        alpha = int(245 * (1.0 - progress))
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)

        if -r <= sx <= SCREEN_W + r and -r <= sy <= SCREEN_H + r:
            ring_s = pygame.Surface((r * 2 + 8, r * 2 + 8), pygame.SRCALPHA)
            w = max(1, int(self.width * (1.0 - progress * 0.6)))
            pygame.draw.circle(ring_s, (*self.color[:3], alpha), (r + 4, r + 4), r, w)
            if r > 12:
                pygame.draw.circle(
                    ring_s,
                    (255, 255, 255, alpha // 2),
                    (r + 4, r + 4),
                    max(2, r - 4),
                    1,
                )
            surf.blit(ring_s, (sx - r - 4, sy - r - 4))


class AmbientParticle:
    """Dark Fantasy floating magical dust and embers."""

    __slots__ = ("x", "y", "vx", "vy", "size", "alpha", "color", "phase")

    def __init__(self, cam_x: float = 0.0, cam_y: float = 0.0):
        self.x: float = cam_x + random.uniform(0, SCREEN_W)
        self.y: float = cam_y + random.uniform(0, SCREEN_H)
        self.vx: float = random.uniform(-0.35, 0.35)
        self.vy: float = random.uniform(-0.65, -0.15)
        self.size: int = random.choice([1, 2, 2, 3])
        self.alpha: int = random.randint(45, 135)
        self.color: Tuple[int, int, int] = random.choice([
            (255, 120, 50),
            (160, 90, 255),
            (70, 220, 255),
            (255, 215, 90),
        ])
        self.phase: float = random.uniform(0, math.tau)

    def update(self, cam_x: float, cam_y: float) -> None:
        self.phase += 0.04
        self.x += self.vx + math.sin(self.phase) * 0.2
        self.y += self.vy
        if self.x < cam_x - 20:
            self.x += SCREEN_W + 40
        elif self.x > cam_x + SCREEN_W + 20:
            self.x -= SCREEN_W + 40
        if self.y < cam_y - 20:
            self.y += SCREEN_H + 40
        elif self.y > cam_y + SCREEN_H + 20:
            self.y -= SCREEN_H + 40

    def draw(self, surf: pygame.Surface, cam_x: float, cam_y: float) -> None:
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        if 0 <= sx < SCREEN_W and 0 <= sy < SCREEN_H:
            twinkle = int(self.alpha * (0.65 + 0.35 * math.sin(self.phase * 2.0)))
            r, g, b = self.color
            if self.size >= 2:
                glow = pygame.Surface((self.size * 4, self.size * 4), pygame.SRCALPHA)
                pygame.draw.circle(
                    glow,
                    (r, g, b, twinkle // 2),
                    (self.size * 2, self.size * 2),
                    self.size * 2,
                )
                surf.blit(glow, (sx - self.size * 2, sy - self.size * 2))
            pygame.draw.circle(surf, (r, g, b), (sx, sy), self.size)

