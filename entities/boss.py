"""Boss mechanics, attack phases, projectile barrages, and death explosions."""
import math
import random
from typing import Any, List, Optional, Tuple
import pygame

from core.config import (
    C_HP_BG,
    C_ICE,
    C_RED,
    C_WHITE,
    SCREEN_H,
    SCREEN_W,
    WORLD_H,
    WORLD_W,
    get_sys_font,
)
from core.i18n import T
from gfx.biome_renderer import apply_hit_flash_mask, get_drop_shadow
from gfx.vfx import ShockwaveRing, draw_additive_glow
from items.consumables import ExpMagnet, HealthPotion
from items.drops import GoldCoin
from pooling.damage_number_pool import DamageNumberPool, PooledDamageNumber
from pooling.particle_pool import ParticlePool, PooledParticle
from pooling.projectile_pool import ProjectilePool, PooledProjectile
from spatial.math_utils import angle_to, clamp, dist, norm

# Aliases
Particle = PooledParticle
DamageNumber = PooledDamageNumber
Projectile = PooledProjectile

class Boss:
    """
    Đại Trùm Dark Fantasy với kích thước khổng lồ (3x quái thường), hào quang động,
    vương miện/đôi cánh bay lượn, thanh máu Trùm trên đỉnh màn hình và đòn đánh AoE
    có vùng cảnh báo đỏ (telegraphed red warning circles/lines) trước khi phát nổ:
      - boss_kind == 0: Chúa Tể Xương (Lich King) - Vương miện hoàng kim hắc ám, áo choàng tử linh, vòng triệu hồi nổ cổ ngữ.
      - boss_kind == 1: Ác Quỷ Vực Thẳm (Abyssal Demon Lord) - Đôi cánh quỷ khổng lồ, sừng đại ma vương, tia lửa địa ngục cắt chéo.
    """
    BASE_HP     = 1800
    BASE_DAMAGE = 36
    BASE_SPEED  = 0.95
    RADIUS      = 45   # Lớn gấp ~3 lần quái thường (radius 14-15)
    COLOR       = (220, 30, 180)
    RING_COLOR  = (255, 80, 220)
    XP_REWARD   = 150
    GOLD_REWARD = 100

    def __init__(self, x, y, wave):
        self.x, self.y  = float(x), float(y)
        self.wave       = max(0, int(wave))
        self.boss_kind  = self.wave % 2  # 0: Chúa Tể Xương (Lich King), 1: Ác Quỷ Vực Thẳm (Abyssal Demon Lord)
        # Chỉ số tăng trưởng theo cấp số nhân khiến trận đấu trùm căng thẳng, khốc liệt
        hp_scale        = 1.40 ** min(self.wave, 12)
        self.max_hp     = int(self.BASE_HP * hp_scale)
        self.hp         = self.max_hp
        self.damage     = int(self.BASE_DAMAGE * (1.20 ** min(self.wave, 12)))
        self.armor      = 8 + self.wave * 3  # Giáp cứng kháng cự sát thương của Boss
        self.speed      = self.BASE_SPEED * min(1.8, 1.04 ** self.wave)
        self.radius     = self.RADIUS
        self.alive      = True
        self.hit_flash  = 0
        self.shoot_cd   = 75
        self.telegraph_cd = 150
        # Danh sách vùng cảnh báo AoE: dict(kind='circle'|'line', x, y, radius, angle, timer, max_timer)
        self.telegraphs: List[dict] = []
        self.kbx = self.kby = 0.0
        self.angle      = 0.0
        self.slow_timer = 0
        self.slow_factor = 1.0
        self.frozen_timer = 0
        self.burn_timer = 0
        self.burn_dmg = 0
        if self.boss_kind == 0:
            self.COLOR = (70, 210, 195)
            self.RING_COLOR = (120, 255, 225)
        else:
            self.COLOR = (225, 35, 70)
            self.RING_COLOR = (255, 110, 50)

    def apply_slow(self, duration: int, factor: float) -> None:
        self.slow_timer = max(self.slow_timer, duration)
        self.slow_factor = min(self.slow_factor, factor)

    def apply_freeze(self, duration: int) -> None:
        self.frozen_timer = max(self.frozen_timer, duration)

    def apply_burn(self, duration: int, dmg_per_tick: int) -> None:
        self.burn_timer = max(self.burn_timer, duration)
        self.burn_dmg = max(self.burn_dmg, dmg_per_tick)

    def take_damage(self, amount):
        # Boss có Giáp giảm sát thương trực tiếp
        actual = max(2, amount - getattr(self, "armor", 8))
        self.hp -= actual
        self.hit_flash = 6  # 100ms white mask
        self.kbx += random.uniform(-1.5, 1.5)
        self.kby += random.uniform(-1.5, 1.5)
        if self.hp <= 0:
            self.alive = False

    def update(self, player, projectiles_out):
        self.angle += 0.04
        self.x += self.kbx;  self.kbx *= 0.8
        self.y += self.kby;  self.kby *= 0.8
        if self.burn_timer > 0:
            self.burn_timer -= 1
            if self.burn_timer % 30 == 0 and self.burn_dmg > 0:
                self.hp -= self.burn_dmg
                if self.hp <= 0:
                    self.alive = False
                    return
        if self.frozen_timer > 0:
            self.frozen_timer -= 1
        if self.slow_timer > 0:
            self.slow_timer -= 1
            if self.slow_timer <= 0:
                self.slow_factor = 1.0

        # Giai đoạn Cuồng Nộ (Phase 2) khi máu dưới 50%
        enraged = (self.hp < self.max_hp * 0.5)
        spd_mult = 1.25 if enraged else 1.0
        effective_speed = 0.0 if self.frozen_timer > 0 else self.speed * self.slow_factor * spd_mult
        dx = player.x - self.x
        dy = player.y - self.y
        d  = math.hypot(dx, dy)
        if d > 0 and effective_speed > 0:
            self.x += (dx / d) * effective_speed
            self.y += (dy / d) * effective_speed
        self.x = clamp(self.x, 0, WORLD_W)
        self.y = clamp(self.y, 0, WORLD_H)
        if self.hit_flash > 0:
            self.hit_flash -= 1

        # Đòn bắn đạn định kỳ
        self.shoot_cd -= 1
        if self.shoot_cd <= 0:
            self.shoot_cd = 48 if enraged else 62
            a = angle_to((self.x, self.y), (player.x, player.y))
            n_shots = 6 if enraged else 4
            p_col = (90, 255, 220) if self.boss_kind == 0 else (255, 70, 50)
            for i in range(n_shots):
                spread = (i - (n_shots - 1) / 2.0) * 0.15
                proj = Projectile(self.x, self.y, a + spread, speed=4.0,
                                  damage=self.damage, lifetime=105,
                                  color=p_col, size=9)
                proj.is_enemy = True
                projectiles_out.append(proj)

        # Tạo đòn đánh AoE có vùng cảnh báo đỏ (Telegraphed AoE Attack)
        self.telegraph_cd -= 1
        if self.telegraph_cd <= 0:
            self.telegraph_cd = 135 if enraged else 175
            if self.boss_kind == 0:
                # Chúa Tể Xương: Triệu hồi 2-3 vòng tròn tử linh cảnh báo đỏ dưới chân người chơi
                for i in range(3 if enraged else 2):
                    ox = 0.0 if i == 0 else random.uniform(-130, 130)
                    oy = 0.0 if i == 0 else random.uniform(-130, 130)
                    self.telegraphs.append({
                        "kind": "circle",
                        "x": clamp(player.x + ox, 60, WORLD_W - 60),
                        "y": clamp(player.y + oy, 60, WORLD_H - 60),
                        "radius": 92,
                        "angle": 0.0,
                        "timer": 55,
                        "max_timer": 55,
                    })
            else:
                # Ác Quỷ Vực Thẳm: Phóng đường cảnh báo tia hủy diệt đỏ + vòng nổ quanh thân
                base_a = angle_to((self.x, self.y), (player.x, player.y))
                for off_a in (-0.25, 0.0, 0.25):
                    self.telegraphs.append({
                        "kind": "line",
                        "x": self.x,
                        "y": self.y,
                        "radius": 380,
                        "angle": base_a + off_a,
                        "timer": 50,
                        "max_timer": 50,
                    })

        # Cập nhật và kích nổ các vùng cảnh báo AoE
        remaining_tele = []
        for tg in self.telegraphs:
            tg["timer"] -= 1
            if tg["timer"] <= 0:
                if tg["kind"] == "circle":
                    # Kích nổ vùng tròn: gây sát thương nếu người chơi đứng trong vòng + bắn mảnh đạn tỏa tròn
                    if dist((player.x, player.y), (tg["x"], tg["y"])) <= tg["radius"]:
                        player.take_damage(int(self.damage * 0.9))
                    for k in range(8):
                        ang_k = (math.tau / 8) * k
                        p = Projectile(tg["x"], tg["y"], ang_k, speed=4.2,
                                       damage=int(self.damage * 0.75), lifetime=45,
                                       color=(255, 65, 85), size=8)
                        p.is_enemy = True
                        projectiles_out.append(p)
                else:
                    # Kích nổ tia hủy diệt: bắn chuỗi đạn tốc độ cao dọc theo đường cảnh báo
                    for step_i in range(4):
                        p = Projectile(tg["x"], tg["y"], tg["angle"], speed=5.5 + step_i * 1.1,
                                       damage=int(self.damage * 0.85), lifetime=75,
                                       color=(255, 80, 40), size=10)
                        p.is_enemy = True
                        projectiles_out.append(p)
            else:
                remaining_tele.append(tg)
        self.telegraphs = remaining_tele

    def draw(self, surf, cam_x, cam_y):
        # 1. Vẽ các vùng cảnh báo AoE màu đỏ trên mặt đất trước (Telegraphed Red Warning Circles/Lines)
        for tg in self.telegraphs:
            ratio = 1.0 - (tg["timer"] / max(1, tg["max_timer"]))
            tsx = int(tg["x"] - cam_x)
            tsy = int(tg["y"] - cam_y)
            pulse_alpha = int(75 + 110 * abs(math.sin(tg["timer"] * 0.35)))
            if tg["kind"] == "circle":
                rad = tg["radius"]
                if -rad <= tsx <= SCREEN_W + rad and -rad <= tsy <= SCREEN_H + rad:
                    warn_s = pygame.Surface((rad * 2 + 8, rad * 2 + 8), pygame.SRCALPHA)
                    wc = rad + 4
                    pygame.draw.circle(warn_s, (220, 25, 35, int(45 + 65 * ratio)), (wc, wc), rad)
                    pygame.draw.circle(warn_s, (255, 50, 60, pulse_alpha), (wc, wc), rad, 3)
                    inner_r = max(4, int(rad * ratio))
                    pygame.draw.circle(warn_s, (255, 120, 90, 170), (wc, wc), inner_r, 2)
                    surf.blit(warn_s, (tsx - wc, tsy - wc))
            else:
                end_x = tsx + int(math.cos(tg["angle"]) * tg["radius"])
                end_y = tsy + int(math.sin(tg["angle"]) * tg["radius"])
                pygame.draw.line(surf, (255, 40, 40), (tsx, tsy), (end_x, end_y), max(2, int(2 + 6 * ratio)))
                pygame.draw.line(surf, (255, 200, 140), (tsx, tsy), (end_x, end_y), 1)

        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        r  = self.radius
        if sx + r + 50 < 0 or sx - r - 50 > SCREEN_W or sy + r + 50 < 0 or sy - r - 50 > SCREEN_H:
            return

        # Bóng đổ elip khổng lồ dưới chân Boss
        sh = get_drop_shadow(int(r * 2.7), int(r * 1.15), 140)
        surf.blit(sh, (sx - sh.get_width() // 2, sy + r - sh.get_height() // 2 + 6))

        # Hào quang cổ ngữ xoay ngoài
        ring_surf = pygame.Surface((r * 3 + 24, r * 3 + 24), pygame.SRCALPHA)
        rc = (r * 3 + 24) // 2
        pygame.draw.circle(ring_surf, (*self.RING_COLOR, 75), (rc, rc), r + 14, 2)
        pygame.draw.circle(ring_surf, (*self.COLOR, 40), (rc, rc), r + 6)
        for i in range(8):
            a  = self.angle + (math.tau / 8) * i
            px = rc + int(math.cos(a) * (r + 14))
            py = rc + int(math.sin(a) * (r + 14))
            pygame.draw.circle(ring_surf, (*self.RING_COLOR, 210), (px, py), 5)
        surf.blit(ring_surf, (sx - rc, sy - rc))

        # Vẽ thân Boss đa lớp (3x scale) lên surface riêng để áp dụng mặt nạ trắng (hit flash)
        bs_size = r * 3 + 36
        bsurf = pygame.Surface((bs_size, bs_size), pygame.SRCALPHA)
        bcx, bcy = bs_size // 2, bs_size // 2
        bob = int(math.sin(self.angle * 2.0) * 3)

        if self.frozen_timer > 0:
            color = C_ICE
        elif self.slow_timer > 0:
            color = tuple(int(c * 0.7 + 130 * 0.3) for c in self.COLOR)
        else:
            color = self.COLOR

        if self.boss_kind == 0:
            # --- CHÚA TỂ XƯƠNG (LICH KING) ---
            # Áo choàng hoàng đế tử linh màu lục-tím sẫm
            cloak_pts = [
                (bcx, bcy - r + 4),
                (bcx - r - 10, bcy + r + 8),
                (bcx - r // 2, bcy + r + 2),
                (bcx, bcy + r + 12),
                (bcx + r // 2, bcy + r + 2),
                (bcx + r + 10, bcy + r + 8),
            ]
            pygame.draw.polygon(bsurf, (20, 32, 38), cloak_pts)
            pygame.draw.polygon(bsurf, color, cloak_pts, 3)
            # Giáp vai xương & lồng ngực xương khổng lồ
            pygame.draw.circle(bsurf, (195, 205, 195), (bcx - r + 6, bcy - 4), 12)
            pygame.draw.circle(bsurf, (195, 205, 195), (bcx + r - 6, bcy - 4), 12)
            for ry in (-6, 2, 10, 18):
                pygame.draw.line(bsurf, (210, 220, 210), (bcx - 16, bcy + ry), (bcx + 16, bcy + ry), 3)
            # Đầu lâu Chúa Tể Xương
            pygame.draw.circle(bsurf, (225, 232, 220), (bcx, bcy - 12), 20)
            pygame.draw.rect(bsurf, (210, 218, 205), (bcx - 10, bcy + 2, 20, 9), border_radius=2)
            # Vương miện hoàng kim lơ lửng trên đầu (Floating Crown)
            cr_y = bcy - 34 + bob
            crown_pts = [
                (bcx - 18, cr_y + 10),
                (bcx - 20, cr_y - 4),
                (bcx - 9, cr_y + 3),
                (bcx, cr_y - 9),
                (bcx + 9, cr_y + 3),
                (bcx + 20, cr_y - 4),
                (bcx + 18, cr_y + 10),
            ]
            pygame.draw.polygon(bsurf, (255, 210, 55), crown_pts)
            pygame.draw.polygon(bsurf, (255, 245, 160), crown_pts, 2)
            pygame.draw.circle(bsurf, (80, 255, 220), (bcx, cr_y + 2), 4)
            # Hốc mắt xanh lục bảo rực cháy
            pygame.draw.circle(bsurf, (15, 25, 28), (bcx - 8, bcy - 13), 5)
            pygame.draw.circle(bsurf, (15, 25, 28), (bcx + 8, bcy - 13), 5)
            pygame.draw.circle(bsurf, (90, 255, 220), (bcx - 8, bcy - 13), 3)
            pygame.draw.circle(bsurf, (90, 255, 220), (bcx + 8, bcy - 13), 3)
        else:
            # --- ÁC QUỶ VỰC THẲM (ABYSSAL DEMON LORD) ---
            flap = int(math.sin(self.angle * 2.5) * 10)
            # Đôi cánh Ác Quỷ khổng lồ vỗ hai bên (Animated Giant Demon Wings)
            lw_pts = [
                (bcx - 14, bcy - 4),
                (bcx - r - 24, bcy - r - 8 + flap),
                (bcx - r - 18, bcy + 12 + flap // 2),
                (bcx - r + 2, bcy + 20),
            ]
            rw_pts = [
                (bcx + 14, bcy - 4),
                (bcx + r + 24, bcy - r - 8 + flap),
                (bcx + r + 18, bcy + 12 + flap // 2),
                (bcx + r - 2, bcy + 20),
            ]
            pygame.draw.polygon(bsurf, (85, 12, 28), lw_pts)
            pygame.draw.polygon(bsurf, (255, 90, 50), lw_pts, 2)
            pygame.draw.polygon(bsurf, (85, 12, 28), rw_pts)
            pygame.draw.polygon(bsurf, (255, 90, 50), rw_pts, 2)
            # Cặp sừng Đại Ma Vương uốn cong
            pygame.draw.polygon(bsurf, (50, 12, 20), [(bcx - 16, bcy - 18), (bcx - r - 8, bcy - r - 14), (bcx - 6, bcy - 28)])
            pygame.draw.polygon(bsurf, (50, 12, 20), [(bcx + 16, bcy - 18), (bcx + r + 8, bcy - r - 14), (bcx + 6, bcy - 28)])
            # Thân giáp quỷ vực thẳm & lõi dung nham
            pygame.draw.circle(bsurf, (70, 10, 22), (bcx, bcy), r - 4)
            pygame.draw.circle(bsurf, color, (bcx, bcy), r - 10)
            pygame.draw.circle(bsurf, self.RING_COLOR, (bcx, bcy), r - 10, 3)
            # Mắt ma vương rực lửa vàng cam
            pygame.draw.polygon(bsurf, (255, 240, 90), [(bcx - 16, bcy - 10), (bcx - 4, bcy - 5), (bcx - 11, bcy + 2)])
            pygame.draw.polygon(bsurf, (255, 240, 90), [(bcx + 16, bcy - 10), (bcx + 4, bcy - 5), (bcx + 11, bcy + 2)])

        if self.hit_flash > 0:
            bsurf = apply_hit_flash_mask(bsurf)

        surf.blit(bsurf, bsurf.get_rect(center=(sx, sy + bob // 2)).topleft)

        if self.frozen_timer > 0:
            pygame.draw.circle(surf, (200, 240, 255), (sx, sy), r + 2, 2)

        # Thanh máu phụ ngay trên đầu Boss (bên cạnh thanh máu lớn trên đỉnh màn hình)
        bw = r * 3
        bx = sx - r - r // 2
        by = sy - r - 22
        pygame.draw.rect(surf, C_HP_BG, (bx, by, bw, 8), border_radius=3)
        fill = int(bw * max(0, self.hp) / max(1, self.max_hp))
        pygame.draw.rect(surf, self.COLOR, (bx, by, fill, 8), border_radius=3)
        pygame.draw.rect(surf, self.RING_COLOR, (bx, by, bw, 8), 1, border_radius=3)
        font = get_sys_font(13, bold=True)
        b_name = T("boss_demon") if self.boss_kind == 1 else T("boss_lich")
        lbl  = font.render(b_name, True, self.RING_COLOR)
        surf.blit(lbl, (sx - lbl.get_width() // 2, by - 16))


# ---------------------------------------------------------------------------
# Sandık sistemi
# ---------------------------------------------------------------------------
