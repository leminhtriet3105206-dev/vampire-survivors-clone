"""Enemy archetypes, scaling formulas, steering behaviors, and drops."""
from enum import Enum, auto
import math
import random
from typing import Any, Dict, List, Optional, Tuple
import pygame

from core.config import (
    C_HP,
    C_HP_BG,
    C_ICE,
    C_RED,
    C_WHITE,
    FPS,
    SCREEN_H,
    SCREEN_W,
    WORLD_H,
    WORLD_W,
)
from gfx.biome_renderer import apply_hit_flash_mask, get_drop_shadow
from gfx.sprite_cache import _ENEMY_FLASH_CACHE, _ENEMY_SPRITE_CACHE
from items.consumables import ExpMagnet, HealthPotion
from items.drops import GoldCoin, XPGem
from pooling.particle_pool import ParticlePool, PooledParticle
from pooling.projectile_pool import ProjectilePool, PooledProjectile
from spatial.math_utils import angle_to, clamp, dist, norm
from entities.ai_behaviors import (
    FlockingSeparation,
    KitingBehavior,
    ExploderChargeBehavior,
    SummonerOrbitBehavior,
)

# Aliases
Particle = PooledParticle
Projectile = PooledProjectile

class EnemyType(Enum):
    BASIC           = auto()
    FAST            = auto()
    TANK            = auto()
    RUNNER          = auto()
    EXPLODER        = auto()
    NECROMANCER     = auto()
    SUMMONED_MINION = auto()
    RANGED          = auto()

ENEMY_DEFS = {
    EnemyType.BASIC:  dict(hp=40,  speed=1.2, damage=8,  xp=5,  radius=14, color=(200, 60, 60)),
    EnemyType.FAST:   dict(hp=20,  speed=2.4, damage=5,  xp=8,  radius=10, color=(255, 120, 40)),
    EnemyType.TANK:   dict(hp=160, speed=0.65, damage=8,  xp=28, radius=20, color=(70, 70, 75)),
    EnemyType.RUNNER:   dict(hp=24,  speed=3.2,  damage=5,  xp=9,  radius=8,  color=(255, 60, 210)),
    EnemyType.EXPLODER:        dict(hp=65,  speed=1.6,  damage=8,  xp=12, radius=12, color=(255, 90, 30)),
    EnemyType.NECROMANCER:     dict(hp=80,  speed=0.9,  damage=6,  xp=18, radius=14, color=(80, 35, 110)),
    EnemyType.SUMMONED_MINION: dict(hp=15,  speed=1.1,  damage=3,  xp=2,  radius=10, color=(185, 185, 190)),
    EnemyType.RANGED:          dict(hp=35,  speed=0.9, damage=10, xp=12, radius=13, color=(60, 200, 120)),
}

def enemy_hp_multiplier(wave: int) -> float:
    """Tăng trưởng máu quái vật theo hàm mũ 35% mỗi Đợt (Wave) để thử thách người chơi."""
    w = max(0, wave)
    return 1.35 ** w

def enemy_damage_multiplier(wave: int) -> float:
    """Tăng sát thương quái vật +20% mỗi Đợt (Wave)."""
    w = max(0, wave)
    return 1.20 ** w

def enemy_speed_multiplier(wave: int) -> float:
    """Tăng tốc độ di chuyển quái vật +5% mỗi Đợt (Wave, giới hạn tối đa 2.2x)."""
    w = max(0, wave)
    return min(2.2, 1.05 ** w)

_ENEMY_SPRITE_CACHE: Dict[Tuple[EnemyType, bool, int, int], pygame.Surface] = {}
_ENEMY_FLASH_CACHE: Dict[Tuple[EnemyType, bool, int, int], pygame.Surface] = {}

class Enemy:
    def __init__(self, x, y, etype: EnemyType, wave: int):
        self.x, self.y = float(x), float(y)
        self.etype = etype
        self.wave = wave
        d = ENEMY_DEFS[etype]
        self.max_hp = int(d['hp'] * enemy_hp_multiplier(wave))
        self.hp     = self.max_hp
        self.speed  = d['speed'] * enemy_speed_multiplier(wave)
        self.damage = int(d['damage'] * enemy_damage_multiplier(wave))
        self.xp     = d['xp']
        self.radius = d['radius']
        self.color  = d['color']
        self.alive  = True
        self.hit_flash = 0
        self.shoot_cd  = random.randint(60, 120)

        # Knockback & Squash/Stretch
        self.kbx = 0.0
        self.kby = 0.0
        self.squash_timer = 0
        self.anim_phase = random.uniform(0, math.tau)
        self.vx_last = 0.0

        self.pending_shots: List[Projectile] = []

        self.slow_timer = 0
        self.slow_factor = 1.0
        self.frozen_timer = 0
        self.burn_timer = 0
        self.burn_dmg = 0

        self.exploder_armed = False
        self.exploder_fuse = 0

        # Elemental Synergy & Resistance Shred
        self.elemental_statuses: Dict[Any, Any] = {}
        self.defense_shred: float = 1.0
        self.defense_shred_timer: int = 0
        self.corrupt_timer: int = 0

        self.summon_cd = 6 * FPS
        self.summoned_minions: List[Enemy] = []

    def apply_slow(self, duration: int, factor: float) -> None:
        self.slow_timer = max(self.slow_timer, duration)
        self.slow_factor = min(self.slow_factor, factor)

    def apply_freeze(self, duration: int) -> None:
        self.frozen_timer = max(self.frozen_timer, duration)

    def apply_burn(self, duration: int, dmg_per_tick: int) -> None:
        self.burn_timer = max(self.burn_timer, duration)
        self.burn_dmg = max(self.burn_dmg, dmg_per_tick)

    def take_damage(self, amount):
        if self.etype == EnemyType.EXPLODER and self.exploder_armed:
            amount *= 0.5
        # Quái Tinh Anh (TANK) có Giáp kháng cự sát thương tăng theo cấp số cộng mỗi đợt
        if self.etype == EnemyType.TANK:
            tank_armor = 4 + max(0, self.wave) * 2
            amount = max(1, amount - tank_armor)
        self.hp -= amount
        self.hit_flash = 6  # 100ms @ 60 FPS
        self.squash_timer = 8
        self.kbx += random.uniform(-2, 2)
        self.kby += random.uniform(-2, 2)
        if self.hp <= 0:
            self.alive = False

    def update(
        self,
        player,
        projectiles_out,
        summoned_out=None,
        spatial_grid=None,
        all_enemies=None,
        particles=None,
        damage_numbers=None,
        shockwaves=None,
        sfx=None,
    ):
        self.anim_phase += 0.18
        if self.squash_timer > 0:
            self.squash_timer -= 1

        if self.defense_shred_timer > 0:
            self.defense_shred_timer -= 1
            if self.defense_shred_timer <= 0:
                self.defense_shred = 1.0
        if self.corrupt_timer > 0:
            self.corrupt_timer -= 1

        if self.burn_timer > 0:
            self.burn_timer -= 1
            if self.burn_timer % 30 == 0 and self.burn_dmg > 0:
                self.hp -= self.burn_dmg
                if self.hp <= 0:
                    self.alive = False
                    return

        if not self.exploder_armed:
            self.x += self.kbx
            self.y += self.kby
            self.kbx *= 0.8
            self.kby *= 0.8
        else:
            self.kbx = 0.0
            self.kby = 0.0

        if self.frozen_timer > 0:
            self.frozen_timer -= 1
        if self.slow_timer > 0:
            self.slow_timer -= 1
            if self.slow_timer <= 0:
                self.slow_factor = 1.0

        effective_speed = 0.0 if self.frozen_timer > 0 else self.speed * self.slow_factor
        dx = player.x - self.x
        dy = player.y - self.y
        d = math.hypot(dx, dy)

        # Modular AI Behaviors & Steering
        if self.etype == EnemyType.EXPLODER:
            vx, vy, is_dead = ExploderChargeBehavior.update_exploder(
                self,
                player,
                effective_speed,
                all_enemies=all_enemies,
                particles=particles,
                damage_numbers=damage_numbers,
                shockwaves=shockwaves,
                sfx=sfx,
            )
            if is_dead:
                return
        elif self.etype == EnemyType.RANGED:
            vx, vy = KitingBehavior.compute_velocity(self, player, effective_speed)
        elif self.etype == EnemyType.NECROMANCER:
            vx, vy = SummonerOrbitBehavior.compute_velocity(self, player, effective_speed)
        else:
            if d > 0 and effective_speed > 0:
                vx = (dx / d) * effective_speed
                vy = (dy / d) * effective_speed
            else:
                vx, vy = 0.0, 0.0

        # Flocking Separation: repulsive force preventing crowded clump collapses
        if spatial_grid is not None and effective_speed > 0 and not getattr(self, "exploder_armed", False):
            # Interleaved steering: computes every 2 frames per mob, halving spatial hash queries
            if (id(self) + int(self.anim_phase * 5.0)) % 2 == 0:
                sep_x, sep_y = FlockingSeparation.compute(self, spatial_grid, separation_radius=28.0)
                self.flock_vx = sep_x * (effective_speed * 0.42)
                self.flock_vy = sep_y * (effective_speed * 0.42)
            vx += getattr(self, "flock_vx", 0.0)
            vy += getattr(self, "flock_vy", 0.0)

        if vx != 0.0 or vy != 0.0:
            self.vx_last = vx
            self.x += vx
            self.y += vy
        else:
            self.vx_last = 0.0

        self.x = clamp(self.x, 0, WORLD_W)
        self.y = clamp(self.y, 0, WORLD_H)

        if self.hit_flash > 0:
            self.hit_flash -= 1

        if self.etype == EnemyType.NECROMANCER and summoned_out is not None:
            self.summon_cd -= 1
            self.summoned_minions = [m for m in self.summoned_minions if m.alive]
            if self.summon_cd <= 0:
                self.summon_cd = 6 * FPS
                if len(self.summoned_minions) < 4:
                    ang = random.uniform(0, math.tau)
                    spawn_dist = self.radius + 18
                    mx = clamp(self.x + math.cos(ang) * spawn_dist, 0, WORLD_W)
                    my = clamp(self.y + math.sin(ang) * spawn_dist, 0, WORLD_H)
                    minion = Enemy(mx, my, EnemyType.SUMMONED_MINION, self.wave)
                    self.summoned_minions.append(minion)
                    summoned_out.append(minion)

        if self.etype == EnemyType.RANGED:
            self.shoot_cd -= 1
            if self.shoot_cd <= 0:
                self.shoot_cd = random.randint(90, 150)
                a = angle_to((self.x, self.y), (player.x, player.y))
                proj = Projectile(self.x, self.y, a, speed=3.5,
                                  damage=self.damage, lifetime=80,
                                  color=(60, 200, 120), size=7)
                proj.is_enemy = True
                projectiles_out.append(proj)

    def draw(self, surf, cam_x, cam_y):
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        r = self.radius
        if sx + r + 24 < 0 or sx - r - 24 > SCREEN_W or sy + r + 24 < 0 or sy - r - 24 > SCREEN_H:
            return

        # Bóng đổ elip (SRCALPHA) dưới chân quái vật
        sh = get_drop_shadow(int(r * 2.2), int(r * 0.9), 100)
        surf.blit(sh, (sx - sh.get_width() // 2, sy + r - sh.get_height() // 2 + 2))

        # Trạng thái hiệu ứng (status_state: 0=thường, 1=đóng băng, 2=thiêu đốt, 3=làm chậm, 4=phát nổ)
        if self.etype == EnemyType.EXPLODER and self.exploder_armed and (self.exploder_fuse // 6) % 2 == 0:
            status_state = 4
        elif self.frozen_timer > 0:
            status_state = 1
        elif self.burn_timer > 0 and (self.burn_timer // 5) % 2 == 0:
            status_state = 2
        elif self.slow_timer > 0:
            status_state = 3
        else:
            status_state = 0

        is_right = self.vx_last >= 0

        # Phân đoạn hoạt ảnh (quantized animation step 0..7)
        if self.etype in (EnemyType.TANK, EnemyType.EXPLODER):
            anim_step = 0
        elif self.etype in (EnemyType.FAST, EnemyType.RUNNER):
            anim_step = int(self.anim_phase * 2.0) % 8
        elif self.etype in (EnemyType.RANGED, EnemyType.NECROMANCER):
            anim_step = int(self.anim_phase * 1.5) % 8
        else:
            anim_step = int(self.anim_phase * 1.5) % 6

        cache_key = (self.etype, is_right, status_state, anim_step)
        esurf = _ENEMY_SPRITE_CACHE.get(cache_key)
        if esurf is None:
            if len(_ENEMY_SPRITE_CACHE) > 768:
                _ENEMY_SPRITE_CACHE.clear()
                _ENEMY_FLASH_CACHE.clear()

            canvas_s = r * 2 + 24
            esurf = pygame.Surface((canvas_s, canvas_s), pygame.SRCALPHA)
            ecx, ecy = canvas_s // 2, canvas_s // 2

            if status_state == 4:
                base_c = (255, 50, 50)
            elif status_state == 1:
                base_c = C_ICE
            elif status_state == 2:
                base_c = (255, 130, 40)
            elif status_state == 3:
                base_c = tuple(int(c * 0.7 + 130 * 0.3) for c in self.color)
            else:
                base_c = self.color

            dark_c = tuple(max(0, int(c * 0.52)) for c in base_c)
            eye_off = 2 if is_right else -2

            # Vẽ chi tiết 4 nguyên mẫu Quái Vật Dark Fantasy
            if self.etype in (EnemyType.TANK, EnemyType.EXPLODER):
                armor_dark = (26, 24, 34) if status_state != 1 else dark_c
                armor_mid = (46, 42, 62) if status_state != 1 else base_c
                rune_col = (195, 75, 255) if self.etype == EnemyType.TANK else (255, 85, 55)
                pygame.draw.rect(esurf, armor_dark, (ecx - r + 2, ecy - r + 4, (r - 2) * 2, (r - 2) * 2), border_radius=5)
                pygame.draw.rect(esurf, armor_mid, (ecx - r + 4, ecy - r + 6, (r - 4) * 2, (r - 4) * 2), border_radius=4)
                pygame.draw.rect(esurf, (150, 145, 175), (ecx - r + 2, ecy - r + 4, (r - 2) * 2, (r - 2) * 2), 2, border_radius=5)
                pygame.draw.polygon(esurf, (175, 170, 195), [(ecx - r + 3, ecy - r + 6), (ecx - r - 5, ecy - r - 5), (ecx - 4, ecy - r + 4)])
                pygame.draw.polygon(esurf, (175, 170, 195), [(ecx + r - 3, ecy - r + 6), (ecx + r + 5, ecy - r - 5), (ecx + 4, ecy - r + 4)])
                sh_x = ecx - r - 2 if not is_right else ecx + r - 7
                pygame.draw.rect(esurf, (32, 28, 44), (sh_x, ecy - 4, 9, 14), border_radius=3)
                pygame.draw.rect(esurf, rune_col, (sh_x, ecy - 4, 9, 14), 1, border_radius=3)
                pygame.draw.line(esurf, rune_col, (ecx, ecy - 3), (ecx, ecy + 7), 2)
                pygame.draw.line(esurf, rune_col, (ecx - 4, ecy + 2), (ecx + 4, ecy + 2), 2)
                pygame.draw.circle(esurf, (255, 65, 95), (ecx - 4 + eye_off, ecy - 4), 2)
                pygame.draw.circle(esurf, (255, 65, 95), (ecx + 4 + eye_off, ecy - 4), 2)

            elif self.etype in (EnemyType.RANGED, EnemyType.NECROMANCER):
                wisp_col = (80, 235, 255) if self.etype == EnemyType.RANGED else (195, 95, 255)
                cloak_rgba = (*dark_c, 185)
                inner_rgba = (*base_c, 210)
                wave_tail = int(math.sin(anim_step * (math.tau / 8)) * 3)
                pts = [
                    (ecx, ecy - r - 4),
                    (ecx - r - 2, ecy + 2),
                    (ecx - r + 2 + wave_tail, ecy + r + 4),
                    (ecx, ecy + r - 2),
                    (ecx + r - 2 + wave_tail, ecy + r + 4),
                    (ecx + r + 2, ecy + 2),
                ]
                pygame.draw.polygon(esurf, cloak_rgba, pts)
                pygame.draw.polygon(esurf, inner_rgba, pts, 2)
                pygame.draw.circle(esurf, (14, 10, 24, 235), (ecx + eye_off // 2, ecy - 3), max(5, r // 2))
                for wi in range(2):
                    wa = anim_step * (math.tau / 8) * 0.8 + wi * math.pi
                    wx = ecx + int(math.cos(wa) * (r + 3))
                    wy = ecy + int(math.sin(wa) * (r * 0.6)) + 3
                    pygame.draw.circle(esurf, (*wisp_col, 175), (wx, wy), 2)
                pygame.draw.circle(esurf, wisp_col, (ecx - 3 + eye_off, ecy - 4), 2)
                pygame.draw.circle(esurf, wisp_col, (ecx + 3 + eye_off, ecy - 4), 2)

            elif self.etype in (EnemyType.FAST, EnemyType.RUNNER):
                flap = int(math.sin(anim_step * (math.tau / 8)) * (r * 0.75))
                wing_c = (68, 22, 95) if status_state != 1 else dark_c
                wing_edge = (145, 50, 185) if status_state != 1 else base_c
                l_wing = [(ecx - 3, ecy), (ecx - r - 7, ecy - 5 - flap), (ecx - r - 2, ecy + 5 - flap // 2), (ecx - 4, ecy + 4)]
                r_wing = [(ecx + 3, ecy), (ecx + r + 7, ecy - 5 - flap), (ecx + r + 2, ecy + 5 - flap // 2), (ecx + 4, ecy + 4)]
                pygame.draw.polygon(esurf, wing_c, l_wing)
                pygame.draw.polygon(esurf, wing_edge, l_wing, 1)
                pygame.draw.polygon(esurf, wing_c, r_wing)
                pygame.draw.polygon(esurf, wing_edge, r_wing, 1)
                pygame.draw.circle(esurf, (38, 16, 52), (ecx, ecy), max(5, r - 2))
                pygame.draw.polygon(esurf, (58, 22, 78), [(ecx - 5, ecy - 5), (ecx - 7, ecy - r - 3), (ecx - 1, ecy - 6)])
                pygame.draw.polygon(esurf, (58, 22, 78), [(ecx + 5, ecy - 5), (ecx + 7, ecy - r - 3), (ecx + 1, ecy - 6)])
                pygame.draw.circle(esurf, (255, 40, 60), (ecx - 3 + eye_off // 2, ecy - 2), 2)
                pygame.draw.circle(esurf, (255, 40, 60), (ecx + 3 + eye_off // 2, ecy - 2), 2)
                pygame.draw.line(esurf, (255, 230, 230), (ecx - 2, ecy + 2), (ecx - 2, ecy + 5), 1)
                pygame.draw.line(esurf, (255, 230, 230), (ecx + 2, ecy + 2), (ecx + 2, ecy + 5), 1)

            else:
                bone_c = (220, 215, 200) if status_state != 1 else base_c
                bone_shadow = (145, 138, 125) if status_state != 1 else dark_c
                rattle = int(math.sin(anim_step * (math.tau / 6)) * 1.5)
                sword_bob = int(math.sin(anim_step * (math.tau / 6)) * 2.2)
                pygame.draw.line(esurf, bone_shadow, (ecx, ecy - 2), (ecx, ecy + r - 2), 3)
                for ry_off in (0, 4, 8):
                    pygame.draw.line(esurf, bone_c, (ecx - 6, ecy + ry_off), (ecx + 6, ecy + ry_off), 2)
                pygame.draw.circle(esurf, bone_c, (ecx + rattle, ecy - 5), max(6, r - 5))
                pygame.draw.circle(esurf, bone_shadow, (ecx + rattle, ecy - 5), max(6, r - 5), 1)
                pygame.draw.rect(esurf, bone_c, (ecx - 3 + rattle, ecy - 1, 6, 4))
                eye_c = (255, 65, 50) if self.etype == EnemyType.BASIC else (120, 255, 140)
                pygame.draw.circle(esurf, (20, 15, 22), (ecx - 3 + rattle + eye_off // 2, ecy - 6), 2)
                pygame.draw.circle(esurf, (20, 15, 22), (ecx + 3 + rattle + eye_off // 2, ecy - 6), 2)
                pygame.draw.circle(esurf, eye_c, (ecx - 3 + rattle + eye_off // 2, ecy - 6), 1)
                pygame.draw.circle(esurf, eye_c, (ecx + 3 + rattle + eye_off // 2, ecy - 6), 1)
                sw_dir = 1 if is_right else -1
                sx_hand = ecx + sw_dir * 7
                sy_hand = ecy + 2
                pygame.draw.line(esurf, (135, 90, 65), (sx_hand, sy_hand), (sx_hand + sw_dir * 7, sy_hand - 9 + sword_bob), 3)
                pygame.draw.line(esurf, (185, 175, 165), (sx_hand, sy_hand), (sx_hand + sw_dir * 7, sy_hand - 9 + sword_bob), 1)

            _ENEMY_SPRITE_CACHE[cache_key] = esurf

        if self.hit_flash > 0:
            flash_surf = _ENEMY_FLASH_CACHE.get(cache_key)
            if flash_surf is None:
                flash_surf = apply_hit_flash_mask(esurf)
                _ENEMY_FLASH_CACHE[cache_key] = flash_surf
            draw_surf = flash_surf
        else:
            draw_surf = esurf

        # Squash & Stretch khi nhận sát thương
        if self.squash_timer > 0:
            sq = 1.0 + 0.18 * math.sin(self.squash_timer * 0.6)
            canvas_s = r * 2 + 24
            w = max(8, int(canvas_s * sq))
            h = max(8, int(canvas_s / sq))
            draw_surf = pygame.transform.scale(draw_surf, (w, h))

        bob = int(math.sin(self.anim_phase) * 2.2)
        rect = draw_surf.get_rect(center=(sx, sy + bob))
        surf.blit(draw_surf, rect.topleft)

        if self.frozen_timer > 0:
            pygame.draw.circle(surf, (200, 240, 255), (sx, sy + bob), r + 2, 2)
        if self.etype == EnemyType.EXPLODER and self.exploder_armed:
            pygame.draw.circle(surf, C_RED, (sx, sy), 90, 1)

        # Thanh máu
        bar_w = r * 2
        bar_h = 4
        bx = sx - r
        by = sy - r - 9
        pygame.draw.rect(surf, C_HP_BG, (bx, by, bar_w, bar_h))
        fill = int(bar_w * max(0, self.hp) / max(1, self.max_hp))
        pygame.draw.rect(surf, C_HP, (bx, by, fill, bar_h))


# ---------------------------------------------------------------------------
# XP Drop
# ---------------------------------------------------------------------------
