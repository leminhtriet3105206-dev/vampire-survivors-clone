"""Player entity class, stat upgrades, movement physics, dash, and weapons suite."""
import math
import random
from typing import Any, Dict, List, Optional, Set, Tuple
import pygame

from core.config import (
    ANIME_SKIN_BY_ID,
    C_PLAYER,
    C_PLAYER_DARK,
    C_WHITE,
    CHARACTER_DEFS,
    FPS,
    PERM_UPGRADE_DEFS,
    SCREEN_H,
    SCREEN_W,
    WORLD_H,
    WORLD_W,
)
from gfx.biome_renderer import get_drop_shadow, get_player_glow_surface
from gfx.sprite_cache import draw_character_procedural_sprite
from gfx.vfx import ShockwaveRing, draw_additive_glow
from pooling.damage_number_pool import DamageNumberPool, PooledDamageNumber
from pooling.particle_pool import ParticlePool, PooledParticle
from spatial.math_utils import clamp, lerp, norm
from weapons.all_weapons import (
    AuraWeapon,
    BoomerangWeapon,
    DragonfireThrustWeapon,
    FamiliarWeapon,
    FireTrailWeapon,
    IceWandWeapon,
    JudgementHammerWeapon,
    LightningStaffWeapon,
    OrbWeapon,
    PhantomArrowWeapon,
    SkeletalLegionWeapon,
    VoidSingularityWeapon,
    WhipWeapon,
)
from weapons.ultimates import ActiveUltimate
from weapons.upgrades import UpgradeType

# Aliases
Particle = PooledParticle
DamageNumber = PooledDamageNumber

class Player:
    def __init__(self, x, y, character_id="warrior", color=C_PLAYER, skin_id="default"):
        self.x, self.y = float(x), float(y)
        self.character_id = character_id
        self.skin_id = skin_id
        self.color = color
        self.dark_color = tuple(max(0, int(c * 0.5)) for c in color)
        self.base_speed = 3.0
        self.speed_mult = 1.0
        self.radius = 16
        self.pickup_radius = 85

        self.max_hp = 120
        self.hp = self.max_hp
        self.recovery = 0
        self.armor = 0
        self.recovery_acc = 0.0

        # RPG Class & Permanent Upgrade traits
        self.damage_mult = 1.0
        self.cdr = 0.0
        self.crit_chance = 0.0
        self.bonus_pierce = 0
        self.lifesteal_on_kill = 0
        self.gold_mult = 1.0

        self.invincible = 0
        self.hit_flash = 0
        self.micro_shake = 0
        self.heal_aura_timer = 0

        # Walk cycle, cape sway, squash-and-stretch, dash & afterimages
        self.vx = 0.0
        self.vy = 0.0
        self.moving = False
        self.cape_sway_x = 0.0
        self.cape_sway_y = 0.0
        self.squash_x = 1.0
        self.squash_y = 1.0
        self.dash_cd = 0
        self.dash_timer = 0
        self.afterimages: List[Tuple[float, float, int]] = []

        self.xp = 0
        self.level = 1
        self.xp_needed = 10

        # Tất cả kỹ năng khởi đầu ở level=0 (chưa mở khóa).
        # Mỗi Hệ Phái sẽ chỉ mở khóa DUY NHẤT 1 Kỹ Năng Độc Quyền ở Lv1 khi vào trận!
        self.whip             = WhipWeapon()
        self.void_singularity = VoidSingularityWeapon()
        self.phantom_arrow    = PhantomArrowWeapon()
        self.judgement_hammer = JudgementHammerWeapon()
        self.orb              = OrbWeapon()
        self.aura             = AuraWeapon()
        self.boomerang        = BoomerangWeapon()
        self.lightning_staff  = LightningStaffWeapon()
        self.ice_wand         = IceWandWeapon()
        self.fire_trail       = FireTrailWeapon()
        self.familiar         = FamiliarWeapon()
        self.skeletal_legion  = SkeletalLegionWeapon()
        self.dragonfire_thrust = DragonfireThrustWeapon()
        self.unlocked_fusions: set = set()

        # Thanh nạp Kỹ năng Tối Thượng (Ultimate Gauge)
        self.ult_charge = 0.0
        self.ult_max = 100.0
        self.ult_active_timer = 0

        # Buff từ Vật phẩm Tác chiến & Thiên Phú Sảnh Chờ (Consumable Buffs & Lobby Perks)
        self.potion_rage_timer = 0
        self.potion_speed_timer = 0
        self.potion_armor_timer = 0
        self.active_perk = ""
        self.perk_cuong_huyet = False
        self.perk_damage_reduction = 0.0

        self.angle = 0.0

    def charge_ult(self, amount: float):
        """Nạp thanh kỹ năng tối thượng (khi tiêu diệt quái hoặc gây sát thương lớn)."""
        self.ult_charge = min(self.ult_max, self.ult_charge + float(amount))

    def get_weapon(self, ut: UpgradeType):
        mapping = {
            UpgradeType.WHIP:             self.whip,
            UpgradeType.VOID_SINGULARITY: self.void_singularity,
            UpgradeType.PHANTOM_ARROW:    self.phantom_arrow,
            UpgradeType.JUDGEMENT_HAMMER: self.judgement_hammer,
            UpgradeType.ORB:              self.orb,
            UpgradeType.AURA:             self.aura,
            UpgradeType.BOOMERANG:        self.boomerang,
            UpgradeType.LIGHTNING_STAFF:  self.lightning_staff,
            UpgradeType.ICE_WAND:         self.ice_wand,
            UpgradeType.FIRE_TRAIL:       self.fire_trail,
            UpgradeType.FAMILIAR:         self.familiar,
            UpgradeType.SKELETAL_LEGION:  self.skeletal_legion,
            UpgradeType.DRAGONFIRE_THRUST: self.dragonfire_thrust,
        }
        return mapping.get(ut)

    @property
    def speed(self):
        mult = 2.1 if self.dash_timer > 0 else 1.0
        if self.potion_speed_timer > 0:
            mult *= 1.6
        return self.base_speed * self.speed_mult * mult

    def gain_xp(self, amount):
        self.xp += amount
        leveled = False
        while self.xp >= self.xp_needed:
            self.xp -= self.xp_needed
            self.level += 1
            self.xp_needed = int(self.xp_needed * 1.3)
            leveled = True
        return leveled

    def take_damage(self, amount):
        if self.invincible > 0 or self.dash_timer > 0 or self.potion_armor_timer > 0:
            return
        dmg = max(1, amount - self.armor)
        if self.perk_damage_reduction > 0.0:
            dmg = max(1, int(dmg * (1.0 - self.perk_damage_reduction)))
        self.hp -= dmg
        self.invincible = 45
        self.hit_flash = 6  # 100ms white silhouette mask
        self.squash_x = 1.32
        self.squash_y = 0.72

    def update(self, keys, dt):
        dx = dy = 0
        if keys[pygame.K_w] or keys[pygame.K_UP]:    dy -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:  dy += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:  dx -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: dx += 1

        # Cập nhật thời gian hiệu lực bình thuốc tác chiến
        if self.potion_rage_timer > 0:
            self.potion_rage_timer -= 1
        if self.potion_speed_timer > 0:
            self.potion_speed_timer -= 1
        if self.potion_armor_timer > 0:
            self.potion_armor_timer -= 1

        # Hỗ trợ lướt nhanh (Dash) bằng SPACE hoặc LSHIFT
        if self.dash_cd > 0:
            self.dash_cd -= 1
        if self.dash_timer > 0:
            self.dash_timer -= 1
        if self.heal_aura_timer > 0:
            self.heal_aura_timer -= 1
        if (keys[pygame.K_SPACE] or keys[pygame.K_LSHIFT]) and self.dash_cd <= 0 and (dx != 0 or dy != 0):
            self.dash_timer = 10
            self.dash_cd = 90
            self.squash_x = 0.76
            self.squash_y = 1.28

        nx, ny = norm(dx, dy)
        self.vx = nx * self.speed
        self.vy = ny * self.speed
        self.moving = (nx != 0 or ny != 0)

        self.x = clamp(self.x + self.vx, 0, WORLD_W)
        self.y = clamp(self.y + self.vy, 0, WORLD_H)

        # Áo choàng bay ngược chiều di chuyển
        target_sway_x = -nx if self.moving else 0.0
        target_sway_y = -ny if self.moving else 0.25
        self.cape_sway_x = lerp(self.cape_sway_x, target_sway_x, 0.16)
        self.cape_sway_y = lerp(self.cape_sway_y, target_sway_y, 0.16)

        # Phục hồi tỉ lệ squash-and-stretch mượt mà
        self.squash_x = lerp(self.squash_x, 1.0, 0.22)
        self.squash_y = lerp(self.squash_y, 1.0, 0.22)

        if self.moving:
            self.angle = math.atan2(ny, nx)

        # Lưu ảnh ảo kỹ thuật số (Digital Afterimages cho Cyber-Shadow Ranger hoặc khi đang Dash)
        if (self.character_id == "rogue" and self.moving) or self.dash_timer > 0:
            if random.random() < 0.55 or self.dash_timer > 0:
                self.afterimages.append((self.x, self.y, 14))
        self.afterimages = [(ax, ay, life - 1) for ax, ay, life in self.afterimages if life > 1]

        if self.invincible > 0:
            self.invincible -= 1
        if self.hit_flash > 0:
            self.hit_flash -= 1

        if self.recovery > 0:
            self.recovery_acc += self.recovery / FPS
            while self.recovery_acc >= 1.0:
                self.hp = min(self.max_hp, self.hp + 1)
                self.recovery_acc -= 1.0

        # Nạp Kỹ Năng Tối Thượng thụ động (~30 giây đầy 100%)
        self.charge_ult(100.0 / (30.0 * FPS))
        if self.ult_active_timer > 0:
            self.ult_active_timer -= 1

    def draw(self, surf, cam_x, cam_y, tick):
        # Vẽ ảnh ảo kỹ thuật số (Afterimages)
        after_col = self.color[:3]
        if self.skin_id in ANIME_SKIN_BY_ID:
            after_col = ANIME_SKIN_BY_ID[self.skin_id]["vfx_primary"]
        for ax, ay, life in self.afterimages:
            asx, asy = int(ax - cam_x), int(ay - cam_y)
            alpha = int(95 * (life / 14.0))
            ghost = pygame.Surface((self.radius * 2 + 8, self.radius * 2 + 8), pygame.SRCALPHA)
            pygame.draw.circle(ghost, (*after_col, alpha),
                               (self.radius + 4, self.radius + 4), self.radius - 2)
            surf.blit(ghost, (asx - self.radius - 4, asy - self.radius - 4))

        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        draw_character_procedural_sprite(
            surf, self.character_id, sx, sy, self.radius,
            self.color, self.dark_color, self.angle, tick,
            vx=self.vx, vy=self.vy, moving=self.moving,
            hit_flash=self.hit_flash, invincible=self.invincible,
            squash_x=self.squash_x, squash_y=self.squash_y,
            cape_sway=(self.cape_sway_x, self.cape_sway_y),
            is_preview=False,
            skin_id=self.skin_id,
        )

        # Hào quang Hồi Máu (Rising Green/Crimson Heal Aura khi nhặt Bình Máu hoặc dùng Ultimate)
        if self.heal_aura_timer > 0:
            t_ratio = min(1.0, max(0.0, self.heal_aura_timer / 38.0))
            draw_additive_glow(surf, sx, sy, int(36 * (1.2 - 0.3 * t_ratio)), (80, 255, 130), intensity=0.55 * t_ratio)
            aura_s = pygame.Surface((64, 64), pygame.SRCALPHA)
            rise = int((1.0 - t_ratio) * 22)
            pygame.draw.circle(aura_s, (80, 255, 140, min(255, int(190 * t_ratio))), (32, 36 - rise // 2), 22, 2)
            pygame.draw.circle(aura_s, (255, 70, 95, min(255, int(160 * t_ratio))), (32, 32 - rise // 3), 16, 2)
            for c_i in range(3):
                cx_p = 18 + c_i * 14
                cy_p = 42 - rise - (c_i % 2) * 8
                alpha_line = min(255, max(0, int(230 * t_ratio)))
                pygame.draw.line(aura_s, (100, 255, 150, alpha_line), (cx_p - 4, cy_p), (cx_p + 4, cy_p), 2)
                pygame.draw.line(aura_s, (100, 255, 150, alpha_line), (cx_p, cy_p - 4), (cx_p, cy_p + 4), 2)
            surf.blit(aura_s, (sx - 32, sy - 32))

        # Hiệu ứng thị giác khi kích hoạt Bình Thuốc Tác Chiến (Consumables Buff Visuals)
        if self.potion_rage_timer > 0:
            draw_additive_glow(surf, sx, sy, 32, (255, 45, 55), intensity=0.55)
            pygame.draw.circle(surf, (255, 60, 60), (sx, sy), 22, 2)
        if self.potion_speed_timer > 0:
            draw_additive_glow(surf, sx, sy, 30, (60, 215, 255), intensity=0.45)
        if self.potion_armor_timer > 0:
            draw_additive_glow(surf, sx, sy, 36, (255, 220, 75), intensity=0.6)
            pygame.draw.circle(surf, (255, 225, 80), (sx, sy), 25, 2)

