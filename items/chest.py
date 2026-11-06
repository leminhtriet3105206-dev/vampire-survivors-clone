"""Treasure chest spawning and drops."""
from enum import Enum, auto
import math
import random
from typing import Optional
import pygame

from core.config import SCREEN_H, SCREEN_W, WORLD_H, WORLD_W
from spatial.math_utils import dist


class ChestDrop(Enum):
    GOLD   = auto()
    DRONE  = auto()
    TURRET = auto()


class Chest:
    """Treasure chest appearing across the world map with gold, companion drones, and turrets."""

    RADIUS        = 18
    RESPAWN_TICKS = 1800
    COLOR_CLOSED  = (180, 140, 40)
    COLOR_OPEN    = (100, 80, 20)

    __slots__ = ("x", "y", "open", "respawn_cd", "bob")

    def __init__(self):
        self._place()
        self.open: bool = False
        self.respawn_cd: int = 0
        self.bob: float = random.uniform(0, math.tau)

    def _place(self) -> None:
        self.x = float(random.randint(200, WORLD_W - 200))
        self.y = float(random.randint(200, WORLD_H - 200))

    def update(self, player) -> Optional[ChestDrop]:
        self.bob += 0.07
        if self.open:
            self.respawn_cd -= 1
            if self.respawn_cd <= 0:
                self._place()
                self.open = False
            return None

        if dist((self.x, self.y), (player.x, player.y)) < self.RADIUS + player.radius:
            self.open = True
            self.respawn_cd = self.RESPAWN_TICKS
            r = random.random()
            if r < 0.60:
                return ChestDrop.GOLD
            elif r < 0.85:
                return ChestDrop.DRONE
            else:
                return ChestDrop.TURRET
        return None

    def draw(self, surf: pygame.Surface, cam_x: float, cam_y: float) -> None:
        if self.open:
            return
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y + math.sin(self.bob) * 3)
        if sx + 24 < 0 or sx - 24 > SCREEN_W or sy + 24 < 0 or sy - 24 > SCREEN_H:
            return

        pygame.draw.rect(surf, self.COLOR_CLOSED, (sx - 14, sy - 10, 28, 20), border_radius=4)
        pygame.draw.rect(surf, (220, 180, 60), (sx - 14, sy - 10, 28, 20), 2, border_radius=4)
        pygame.draw.rect(surf, (200, 160, 50), (sx - 14, sy - 14, 28, 8), border_radius=3)
        pygame.draw.rect(surf, (240, 200, 80), (sx - 14, sy - 14, 28, 8), 1, border_radius=3)
        pygame.draw.rect(surf, (60, 50, 20), (sx - 3, sy - 4, 6, 6), border_radius=2)

