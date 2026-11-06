"""In-match collectible consumables: Health Potion and Global EXP Magnet."""
import math
import random
from typing import Any, List
import pygame

from core.config import SCREEN_H, SCREEN_W
from core.i18n import T
from gfx.vfx import ShockwaveRing, draw_additive_glow
from pooling.damage_number_pool import DamageNumberPool, PooledDamageNumber
from pooling.particle_pool import ParticlePool, PooledParticle
from spatial.math_utils import dist, norm


class HealthPotion:
    """Ruby-red health potion restoring max(30, 25% max HP) with radiant healing juice."""

    __slots__ = ("x", "y", "heal_amount", "alive", "bob")

    def __init__(self, x: float, y: float, heal_amount: int = 30):
        self.x = float(x)
        self.y = float(y)
        self.heal_amount = heal_amount
        self.alive = True
        self.bob = random.uniform(0, math.tau)

    def update(self, player, particles: list, damage_numbers: list, sfx=None) -> int:
        self.bob += 0.09
        d = dist((self.x, self.y), (player.x, player.y))
        if d < player.pickup_radius * 0.85:
            nx, ny = norm(player.x - self.x, player.y - self.y)
            self.x += nx * 5.2
            self.y += ny * 5.2
        if d < player.radius + 15:
            self.alive = False
            heal_val = max(self.heal_amount, int(player.max_hp * 0.25))
            old_hp = player.hp
            player.hp = min(player.max_hp, player.hp + heal_val)
            actual_heal = max(heal_val, player.hp - old_hp)
            player.heal_aura_timer = 38

            # Handle either pooled or standard damage number list
            if hasattr(damage_numbers, "spawn"):
                damage_numbers.spawn(player.x, player.y - 26, actual_heal, (80, 255, 130), is_heal=True)
            else:
                num = PooledDamageNumber()
                num.reset(player.x, player.y - 26, actual_heal, (80, 255, 130), is_heal=True)
                damage_numbers.append(num)

            for i in range(14):
                ang = (math.tau / 14) * i
                col = (80, 255, 130) if i % 2 == 0 else (255, 60, 95)
                if hasattr(particles, "spawn"):
                    particles.spawn(player.x, player.y, col, speed=3.2, size=4, life=26, angle=ang, spread=0.25)
                else:
                    p = PooledParticle()
                    p.reset(player.x, player.y, col, speed=3.2, size=4, life=26, angle=ang, spread=0.25)
                    particles.append(p)

            if sfx:
                sfx.play_levelup()
            return actual_heal
        return 0

    def draw(self, surf: pygame.Surface, cam_x: float, cam_y: float, tick: int) -> None:
        sx = int(self.x - cam_x)
        base_sy = int(self.y - cam_y)
        sy = int(base_sy + math.sin(self.bob) * 3.5)
        if not (-28 < sx < SCREEN_W + 28 and -28 < sy < SCREEN_H + 28):
            return

        pulse = 0.88 + 0.12 * math.sin(self.bob * 1.5)
        ind_r = int(16 * pulse)
        ind_s = pygame.Surface((ind_r * 2 + 6, ind_r + 6), pygame.SRCALPHA)
        pygame.draw.ellipse(ind_s, (255, 45, 80, 95), (2, 2, ind_r * 2, ind_r))
        pygame.draw.ellipse(ind_s, (255, 140, 165, 175), (2, 2, ind_r * 2, ind_r), 1)
        surf.blit(ind_s, (sx - ind_r - 2, base_sy + 4))

        draw_additive_glow(surf, sx, sy, 22, (255, 40, 80), intensity=0.52)

        pygame.draw.circle(surf, (130, 15, 35), (sx, sy + 2), 9)
        pygame.draw.circle(surf, (235, 30, 65), (sx, sy + 2), 8)
        pygame.draw.circle(surf, (255, 110, 140), (sx - 3, sy), 3)
        pygame.draw.circle(surf, (255, 240, 245), (sx - 3, sy - 1), 1)
        pygame.draw.circle(surf, (220, 240, 255), (sx, sy + 2), 9, 1)
        pygame.draw.rect(surf, (200, 225, 245), (sx - 3, sy - 9, 6, 4), border_radius=1)
        pygame.draw.rect(surf, (175, 115, 55), (sx - 2, sy - 12, 4, 4), border_radius=1)

        cy_cross = sy - 16 - int(abs(math.sin(self.bob)) * 3)
        pygame.draw.line(surf, (255, 80, 110), (sx - 3, cy_cross), (sx + 3, cy_cross), 2)
        pygame.draw.line(surf, (255, 80, 110), (sx, cy_cross - 3), (sx, cy_cross + 3), 2)


class ExpMagnet:
    """Global magnetic vacuum pulling all gems and coins across the map to the player."""

    __slots__ = ("x", "y", "alive", "bob")

    def __init__(self, x: float, y: float):
        self.x = float(x)
        self.y = float(y)
        self.alive = True
        self.bob = random.uniform(0, math.tau)

    def update(
        self,
        player,
        xp_gems: list,
        gold_coins: list,
        shockwaves: list,
        particles: list,
        damage_numbers: list,
        sfx=None,
    ) -> bool:
        self.bob += 0.09
        d = dist((self.x, self.y), (player.x, player.y))
        if d < player.pickup_radius * 0.85:
            nx, ny = norm(player.x - self.x, player.y - self.y)
            self.x += nx * 5.5
            self.y += ny * 5.5
        if d < player.radius + 15:
            self.alive = False
            for g in xp_gems:
                if getattr(g, "alive", True):
                    g.magnetized = True
            for c in gold_coins:
                if getattr(c, "alive", True):
                    c.magnetized = True

            shockwaves.append(ShockwaveRing(player.x, player.y, max_radius=340, color=(70, 225, 255)))
            shockwaves.append(ShockwaveRing(player.x, player.y, max_radius=220, color=(255, 70, 95)))

            if hasattr(damage_numbers, "spawn"):
                damage_numbers.spawn(player.x, player.y - 34, 0, (90, 240, 255), text_override=T("item_magnet_pickup"))
            else:
                num = PooledDamageNumber()
                num.reset(player.x, player.y - 34, 0, (90, 240, 255), text_override=T("item_magnet_pickup"))
                damage_numbers.append(num)

            for i in range(18):
                ang = (math.tau / 18) * i
                col = (70, 225, 255) if i % 2 == 0 else (255, 65, 85)
                if hasattr(particles, "spawn"):
                    particles.spawn(player.x, player.y, col, speed=4.2, size=4, life=28, angle=ang, spread=0.2)
                else:
                    p = PooledParticle()
                    p.reset(player.x, player.y, col, speed=4.2, size=4, life=28, angle=ang, spread=0.2)
                    particles.append(p)

            if sfx:
                sfx.play_levelup()
            return True
        return False

    def draw(self, surf: pygame.Surface, cam_x: float, cam_y: float, tick: int) -> None:
        sx = int(self.x - cam_x)
        base_sy = int(self.y - cam_y)
        sy = int(base_sy + math.sin(self.bob) * 3.5)
        if not (-28 < sx < SCREEN_W + 28 and -28 < sy < SCREEN_H + 28):
            return

        wave_r = 8 + int((tick * 0.6) % 14)
        ind_s = pygame.Surface((wave_r * 2 + 6, wave_r + 6), pygame.SRCALPHA)
        pygame.draw.ellipse(ind_s, (70, 220, 255, 150 - wave_r * 6), (2, 2, wave_r * 2, wave_r), 2)
        surf.blit(ind_s, (sx - wave_r - 2, base_sy + 4))

        draw_additive_glow(surf, sx, sy, 24, (70, 215, 255), intensity=0.55)

        pygame.draw.circle(surf, (130, 145, 175), (sx, sy + 2), 9, 4)
        pygame.draw.rect(surf, (235, 45, 65), (sx - 9, sy - 7, 5, 9), border_radius=1)
        pygame.draw.rect(surf, (45, 155, 255), (sx + 4, sy - 7, 5, 9), border_radius=1)
        pygame.draw.rect(surf, (245, 250, 255), (sx - 9, sy - 9, 5, 3))
        pygame.draw.rect(surf, (245, 250, 255), (sx + 4, sy - 9, 5, 3))

        if (tick // 3) % 2 == 0:
            pygame.draw.line(surf, (140, 245, 255), (sx - 6, sy - 10), (sx, sy - 14), 2)
            pygame.draw.line(surf, (255, 255, 255), (sx, sy - 14), (sx + 6, sy - 10), 2)

