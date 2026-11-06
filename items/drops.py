"""XP Gems and Gold Coins drops."""
import math
import random
from typing import List, Tuple
import pygame

from core.config import C_GREEN, C_WHITE, SCREEN_H, SCREEN_W
from gfx.biome_renderer import get_drop_shadow


class XPGem:
    """Experience gem dropped by defeated enemies."""

    __slots__ = ("x", "y", "value", "alive", "bob", "magnetized", "trail")

    def __init__(self, x: float, y: float, value: int):
        self.x = float(x)
        self.y = float(y)
        self.value = value
        self.alive = True
        self.bob = random.uniform(0, math.tau)
        self.magnetized = False
        self.trail: List[Tuple[float, float]] = []

    def update(self, player) -> int:
        self.bob += 0.08
        dx = player.x - self.x
        dy = player.y - self.y
        pr = player.pickup_radius
        if self.magnetized:
            self.trail.append((self.x, self.y))
            if len(self.trail) > 6:
                self.trail.pop(0)
            d = math.hypot(dx, dy)
            if d > 0:
                self.x += (dx / d) * 15.5
                self.y += (dy / d) * 15.5
            if d < player.radius + 14:
                self.alive = False
                return self.value
            return 0

        if dx > pr or dx < -pr or dy > pr or dy < -pr:
            return 0

        d2 = dx * dx + dy * dy
        if d2 < pr * pr:
            d = math.sqrt(d2)
            if d > 0:
                self.x += (dx / d) * 6.8
                self.y += (dy / d) * 6.8
            if d < player.radius + 14:
                self.alive = False
                return self.value
        return 0

    def draw(self, surf: pygame.Surface, cam_x: float, cam_y: float, tick: int) -> None:
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y + math.sin(self.bob) * 3)
        if -24 < sx < SCREEN_W + 24 and -24 < sy < SCREEN_H + 24:
            if self.magnetized and len(self.trail) >= 2:
                for i in range(len(self.trail) - 1):
                    p1 = (int(self.trail[i][0] - cam_x), int(self.trail[i][1] - cam_y))
                    p2 = (int(self.trail[i + 1][0] - cam_x), int(self.trail[i + 1][1] - cam_y))
                    pygame.draw.line(surf, (80, 255, 220), p1, p2, max(1, i))
            sh = get_drop_shadow(10, 5, 70)
            surf.blit(sh, (sx - 5, int(self.y - cam_y) + 6))
            pygame.draw.polygon(
                surf,
                C_GREEN,
                [(sx, sy - 8), (sx + 6, sy), (sx, sy + 8), (sx - 6, sy)],
            )
            pygame.draw.polygon(
                surf,
                (180, 255, 200),
                [(sx, sy - 5), (sx + 3, sy), (sx, sy + 5), (sx - 3, sy)],
            )
            pygame.draw.polygon(
                surf,
                C_WHITE,
                [(sx, sy - 8), (sx + 6, sy), (sx, sy + 8), (sx - 6, sy)],
                1,
            )


class GoldCoin:
    """Gold coin dropped from enemies with 3D spinning animation."""

    __slots__ = ("x", "y", "value", "alive", "bob", "spin", "magnetized", "trail")

    def __init__(self, x: float, y: float, value: int):
        self.x = float(x)
        self.y = float(y)
        self.value = value
        self.alive = True
        self.bob = random.uniform(0, math.tau)
        self.spin = random.uniform(0, math.tau)
        self.magnetized = False
        self.trail: List[Tuple[float, float]] = []

    def update(self, player) -> int:
        self.bob += 0.09
        self.spin += 0.16
        dx = player.x - self.x
        dy = player.y - self.y
        pr = player.pickup_radius
        if self.magnetized:
            self.trail.append((self.x, self.y))
            if len(self.trail) > 6:
                self.trail.pop(0)
            d = math.hypot(dx, dy)
            if d > 0:
                self.x += (dx / d) * 15.5
                self.y += (dy / d) * 15.5
            if d < player.radius + 14:
                self.alive = False
                mult = getattr(player, "gold_mult", 1.0)
                return max(1, int(round(self.value * mult)))
            return 0

        if dx > pr or dx < -pr or dy > pr or dy < -pr:
            return 0

        d2 = dx * dx + dy * dy
        if d2 < pr * pr:
            d = math.sqrt(d2)
            if d > 0:
                self.x += (dx / d) * 6.8
                self.y += (dy / d) * 6.8
            if d < player.radius + 14:
                self.alive = False
                mult = getattr(player, "gold_mult", 1.0)
                return max(1, int(round(self.value * mult)))
        return 0

    def draw(self, surf: pygame.Surface, cam_x: float, cam_y: float) -> None:
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y + math.sin(self.bob) * 3)
        if -24 < sx < SCREEN_W + 24 and -24 < sy < SCREEN_H + 24:
            if self.magnetized and len(self.trail) >= 2:
                for i in range(len(self.trail) - 1):
                    p1 = (int(self.trail[i][0] - cam_x), int(self.trail[i][1] - cam_y))
                    p2 = (int(self.trail[i + 1][0] - cam_x), int(self.trail[i + 1][1] - cam_y))
                    pygame.draw.line(surf, (255, 225, 80), p1, p2, max(1, i))
            sh = get_drop_shadow(12, 6, 80)
            surf.blit(sh, (sx - 6, int(self.y - cam_y) + 6))
            w = max(3, int(abs(math.cos(self.spin)) * 14))
            h = 14
            rect = pygame.Rect(sx - w // 2, sy - h // 2, w, h)
            pygame.draw.ellipse(surf, (255, 215, 45), rect)
            pygame.draw.ellipse(surf, (195, 135, 10), rect, 2)
            if w >= 6:
                pygame.draw.line(surf, (255, 250, 190), (sx, sy - 3), (sx, sy + 3), 2)

