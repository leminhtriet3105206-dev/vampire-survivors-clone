"""Weapons and active skills system for Legendary Survival."""
import math
import random
from typing import Any, Dict, List, Optional, Set, Tuple
import pygame

from core.config import (
    ANIME_SKIN_BY_ID,
    C_BOOMERANG,
    C_CYAN,
    C_ICE,
    C_LIGHTNING,
    C_ORANGE,
    C_PURPLE,
    C_RED,
    C_WHITE,
    C_YELLOW,
    SCREEN_H,
    SCREEN_W,
)
from core.i18n import T
from gfx.biome_renderer import get_slash_scratch_surf
from gfx.sprite_cache import get_skin_vfx_colors
from gfx.vfx import (
    draw_additive_glow,
    draw_jagged_lightning_arc,
    draw_magic_circle,
    ShockwaveRing,
)
from pooling.damage_number_pool import DamageNumberPool, PooledDamageNumber
from pooling.particle_pool import ParticlePool, PooledParticle
from pooling.projectile_pool import ProjectilePool, PooledProjectile
from spatial.math_utils import angle_to, clamp, dist, dist_to_segment, in_radius_sq, norm, lerp
from core.elements import Element, ElementalReaction, ElementalSynergyManager
from weapons.weapon_base import deal_player_damage

# Aliases for compatibility
Particle = PooledParticle
DamageNumber = PooledDamageNumber
Projectile = PooledProjectile

class AuraWeapon:
    """
    Trường Lực Thánh (Sacred Aura):
    Vòng cổ ngữ tỏa sáng xung quanh người chơi, làm chậm (slow) và thiêu đốt (burn) kẻ địch bên trong.
    Khởi tạo level=0 (chưa mở khóa); lên cấp sẽ mở khóa ở Lv1 và thức tỉnh ở Lv5.
    """
    def __init__(self):
        self.radius = 88
        self.damage = 10
        self.cooldown = 0
        self.tick = 38
        self.level = 0
        self.fused = False
        self.element = Element.FIRE

    @property
    def awakened(self) -> bool:
        return self.level >= 5 or self.fused

    def upgrade(self):
        self.level += 1
        if self.level == 1:
            return
        self.radius += 16
        self.damage += 5
        self.tick = max(18, self.tick - 5)
        if self.level == 5:
            self.radius += 25
            self.damage += 10

    def update(self, player, enemies, particles, damage_numbers, sfx=None):
        if self.level <= 0:
            return
        self.cooldown -= 1
        eff_tick = max(12, int(self.tick * (1.0 - getattr(player, "cdr", 0.0))))
        if self.cooldown <= 0:
            self.cooldown = eff_tick
            px, py = player.x, player.y
            hit_any = False
            def_col = (255, 215, 70) if self.awakened else C_PURPLE
            col, sub_col = get_skin_vfx_colors(player, def_col, (100, 220, 255))
            for e in enemies:
                if not e.alive:
                    continue
                if dist((px, py), (e.x, e.y)) < self.radius + e.radius:
                    deal_player_damage(
                        player,
                        e,
                        self.damage,
                        damage_numbers,
                        col,
                        element=self.element,
                        all_enemies=enemies,
                        particles=particles,
                        sfx=sfx,
                    )
                    if hasattr(e, "apply_slow"):
                        e.apply_slow(45, 0.65 if not self.awakened else 0.45)
                    if hasattr(e, "apply_burn"):
                        e.apply_burn(90, max(2, self.damage // 3))
                    hit_any = True
                    hit_ang = angle_to((px, py), (e.x, e.y))
                    for _ in range(3):
                        particles.append(Particle(e.x, e.y, col, speed=2.4, angle=hit_ang, spread=0.8))
            if hit_any and sfx:
                sfx.play_aura()

    def draw(self, surf, cam_x, cam_y, player, tick):
        if self.level <= 0:
            return
        px = int(player.x - cam_x)
        py = int(player.y - cam_y)
        pulse = 0.92 + 0.08 * math.sin(tick * 0.14)
        r = int(self.radius * pulse)
        def_base = (255, 210, 65) if self.awakened else (180, 80, 255)
        def_sub = (190, 90, 255) if self.awakened else (100, 220, 255)
        base_col, sub_col = get_skin_vfx_colors(player, def_base, def_sub)

        # Vòng cổ ngữ ma thuật xoay dưới chân + Additive Glow
        draw_additive_glow(surf, px, py, int(r * 0.55), base_col, intensity=0.22)
        draw_magic_circle(surf, px, py, r, base_col, tick * 0.025, alpha=115 if self.awakened else 85)

        aura_surf = pygame.Surface((r * 2 + 8, r * 2 + 8), pygame.SRCALPHA)
        center = (r + 4, r + 4)
        pygame.draw.circle(aura_surf, (*base_col, 20), center, r)
        pygame.draw.circle(aura_surf, (*base_col, 110), center, r, 2)
        pygame.draw.circle(aura_surf, (*sub_col, 75), center, int(r * 0.72), 1)

        rune_count = 8 if self.awakened else 6
        for i in range(rune_count):
            a = tick * 0.032 + (math.tau / rune_count) * i
            rx = center[0] + int(math.cos(a) * r)
            ry = center[1] + int(math.sin(a) * r)
            pygame.draw.circle(aura_surf, (*base_col, 210), (rx, ry), 5 if self.awakened else 4)
            pygame.draw.circle(aura_surf, (255, 255, 255, 220), (rx, ry), 2)

        surf.blit(aura_surf, (px - r - 4, py - r - 4))


class Boomerang:
    """
    Lưỡi Hái Tử Thần (Boomerang Scythe):
    Vũ khí xoay tốc độ cao bay theo quỹ đạo cong và vòng ngược trở về người chơi.
    Khi Hợp Nhất (Reaper's Hurricane): Nảy ra các mũi tên độc ảnh truy kích khi chạm quái.
    """
    def __init__(self, x, y, angle, speed, damage, max_range, awakened=False, curve_dir=1, fused=False, skin_id="default"):
        self.x, self.y = float(x), float(y)
        self.angle = angle
        self.speed = speed
        self.damage = damage
        self.max_range = max_range
        self.traveled = 0.0
        self.returning = False
        self.hit_set: set = set()
        self.alive = True
        self.awakened = awakened
        self.fused = fused
        self.curve_dir = curve_dir
        self.skin_id = skin_id
        self.element = Element.VOID
        self.color = (255, 70, 95) if fused else ((255, 195, 55) if awakened else C_BOOMERANG)
        if skin_id in ANIME_SKIN_BY_ID:
            self.color = ANIME_SKIN_BY_ID[skin_id]["vfx_primary"]
        self.trail: List[Tuple[float, float]] = []

    def update(self, player):
        self.trail.append((self.x, self.y))
        if len(self.trail) > 9:
            self.trail.pop(0)

        if self.returning:
            target_a = angle_to((self.x, self.y), (player.x, player.y))
            diff = math.atan2(math.sin(target_a - self.angle), math.cos(target_a - self.angle))
            self.angle += diff * 0.22
            d = dist((self.x, self.y), (player.x, player.y))
            if d < 18:
                self.alive = False
                return
            self.x += math.cos(self.angle) * (self.speed * 1.18)
            self.y += math.sin(self.angle) * (self.speed * 1.18)
        else:
            self.angle += 0.014 * self.curve_dir
            self.x += math.cos(self.angle) * self.speed
            self.y += math.sin(self.angle) * self.speed
            self.traveled += self.speed
            if self.traveled >= self.max_range:
                self.returning = True
                self.hit_set.clear()

    def draw(self, surf, cam_x, cam_y):
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        if -50 < sx < SCREEN_W + 50 and -50 < sy < SCREEN_H + 50:
            # Vệt sáng chuyển động (Glowing Ribbon Motion Trail)
            if len(self.trail) >= 2:
                for idx in range(len(self.trail) - 1):
                    p1 = (int(self.trail[idx][0] - cam_x), int(self.trail[idx][1] - cam_y))
                    p2 = (int(self.trail[idx + 1][0] - cam_x), int(self.trail[idx + 1][1] - cam_y))
                    w = max(2, int(6 * (idx + 1) / len(self.trail)))
                    pygame.draw.line(surf, self.color[:3], p1, p2, w)

            spin = pygame.time.get_ticks() * 0.028
            size = 24 if self.fused else (18 if self.awakened else 14)
            draw_additive_glow(surf, sx, sy, int(size * 1.7), self.color[:3], intensity=0.55)

            # Biến thể Naruto: Rasenshuriken 4 cánh gió xoáy!
            blades = 4 if self.skin_id == "naruto" else (3 if self.fused else 2)
            for b_i in range(blades):
                base_a = spin + b_i * (math.tau / blades)
                p1 = (sx + int(math.cos(base_a) * 4), sy + int(math.sin(base_a) * 4))
                p2 = (sx + int(math.cos(base_a + 0.5) * size), sy + int(math.sin(base_a + 0.5) * size))
                p3 = (sx + int(math.cos(base_a + 1.25) * (size + 5)), sy + int(math.sin(base_a + 1.25) * (size + 5)))
                p4 = (sx + int(math.cos(base_a + 0.9) * (size * 0.55)), sy + int(math.sin(base_a + 0.9) * (size * 0.55)))
                pygame.draw.polygon(surf, self.color, [p1, p2, p3, p4])
                pygame.draw.polygon(surf, C_WHITE, [p1, p2, p3, p4], 1)
            pygame.draw.circle(surf, (60, 255, 180) if self.fused else C_WHITE, (sx, sy), 6)
            pygame.draw.circle(surf, self.color, (sx, sy), 6, 2)


class BoomerangWeapon:
    def __init__(self):
        self.damage = 22
        self.speed = 5.4
        self.range = 260
        self.cooldown = 0
        self.tick = 84
        self.level = 0
        self.fused = False
        self.element = Element.VOID
        self.boomerangs: List[Boomerang] = []

    @property
    def awakened(self) -> bool:
        return self.level >= 5 or self.fused

    def upgrade(self):
        self.level += 1
        if self.level == 1:
            return
        self.damage += 9
        self.speed += 0.5
        self.range += 32
        self.tick = max(38, self.tick - 8)
        if self.level == 5:
            self.damage += 15
            self.range += 40

    def update(self, player, enemies, particles, damage_numbers, sfx=None):
        if self.level <= 0 and not self.fused:
            return
        hit_r = 26 if self.fused else (22 if self.awakened else 16)
        for b in self.boomerangs:
            b.update(player)
            if b.alive:
                for e in enemies:
                    if e.alive and id(e) not in b.hit_set:
                        if dist((b.x, b.y), (e.x, e.y)) < hit_r + e.radius:
                            deal_player_damage(
                                player,
                                e,
                                b.damage,
                                damage_numbers,
                                b.color,
                                element=getattr(b, "element", Element.VOID),
                                all_enemies=enemies,
                                particles=particles,
                                sfx=sfx,
                            )
                            b.hit_set.add(id(e))
                            # Nếu Hợp Nhất (Reaper's Hurricane): Phân tách thành tên độc ảnh và bẫy bóng đêm
                            if b.fused and hasattr(player, "phantom_arrow"):
                                player.phantom_arrow.spawn_split_arrows(b.x, b.y, b.damage // 2, getattr(player, "skin_id", "default"))
                            for _ in range(5):
                                particles.append(Particle(b.x, b.y, b.color, speed=3.4, angle=b.angle, spread=0.9))
                            if sfx:
                                sfx.play_hit()
        self.boomerangs = [b for b in self.boomerangs if b.alive]

        self.cooldown -= 1
        eff_tick = max(18, int(self.tick * (1.0 - getattr(player, "cdr", 0.0))))
        if self.cooldown <= 0:
            target = None
            best = self.range + 150
            for e in enemies:
                d = dist((player.x, player.y), (e.x, e.y))
                if d < best:
                    best = d
                    target = e
            if target:
                self.cooldown = eff_tick
                a = angle_to((player.x, player.y), (target.x, target.y))
                count = 4 if self.fused else (3 if self.awakened else (2 if self.level >= 3 else 1))
                skin_id = getattr(player, "skin_id", "default")
                for i in range(count):
                    spread = (i - (count - 1) / 2.0) * 0.35
                    c_dir = 1 if i % 2 == 0 else -1
                    self.boomerangs.append(Boomerang(
                        player.x, player.y, a + spread, self.speed,
                        int(self.damage * (1.45 if self.fused else 1.0)),
                        self.range + (70 if self.fused else 0),
                        awakened=self.awakened, curve_dir=c_dir, fused=self.fused, skin_id=skin_id))
            else:
                self.cooldown = eff_tick // 2

    def draw(self, surf, cam_x, cam_y, player):
        if self.level <= 0 and not self.fused:
            return
        for b in self.boomerangs:
            b.draw(surf, cam_x, cam_y)


class WhipWeapon:
    """
    Kỹ năng Độc Quyền Huyết Kiếm Sĩ: Trảm Huyết Nguyệt (Blood Moon Slash):
    Chém vòng cung lưỡi liềm đỏ thẫm gây xuất huyết (bleeding) và hồi máu theo % sát thương gây ra.
    Khi Hợp Nhất với Trường Lực Thánh -> Huyết Ngục Vĩnh Hằng (Eternal Blood Domain).
    """
    def __init__(self):
        self.damage = 28
        self.cooldown = 0
        self.tick = 68
        self.range = 215
        self.level = 0
        self.fused = False
        self.element = Element.FIRE
        self.angle = 0.0
        self.flash = 0
        self.domain_pulse = 0.0
        # Danh sách dư ảnh nhát chém lưu lại 200ms (12 frames @ 60fps): (wx, wy, angle, r, life, max_life, col, sub_col)
        self.slash_trails: List[Tuple[float, float, float, float, int, int, Tuple[int, int, int], Tuple[int, int, int]]] = []

    @property
    def awakened(self) -> bool:
        return self.level >= 5 or self.fused

    def upgrade(self):
        self.level += 1
        if self.level == 1:
            return
        self.damage += 13
        self.range += 28
        self.tick = max(32, self.tick - 8)
        if self.level == 5:
            self.damage += 20
            self.range += 38

    def update(self, player, enemies, particles, damage_numbers, sfx=None):
        if self.level <= 0 and not self.fused:
            return
        self.cooldown -= 1
        self.domain_pulse += 0.08
        if self.flash > 0:
            self.flash -= 1
        # Cập nhật dư ảnh nhát chém 200ms (12 frames)
        self.slash_trails = [
            (wx, wy, ang, sr, lf - 1, mlf, c1, c2)
            for (wx, wy, ang, sr, lf, mlf, c1, c2) in self.slash_trails
            if lf > 1
        ]
        eff_tick = max(18, int(self.tick * (1.0 - getattr(player, "cdr", 0.0))))
        if self.fused:
            eff_tick = max(15, eff_tick // 2)

        if self.cooldown <= 0:
            target = None
            best = self.range + (90 if self.fused else 0)
            for e in enemies:
                d = dist((player.x, player.y), (e.x, e.y))
                if d < best:
                    best = d
                    target = e
            if target or self.fused:
                self.cooldown = eff_tick
                self.angle = angle_to((player.x, player.y), (target.x, target.y)) if target else (self.angle + 0.7)
                self.flash = 12  # ~200ms
                if sfx:
                    sfx.play_whip()
                def_col = (255, 215, 70) if self.fused else ((255, 185, 65) if self.awakened else (255, 55, 75))
                def_sub = (255, 60, 95) if self.fused else ((200, 70, 255) if self.awakened else (255, 140, 60))
                col, sub_col = get_skin_vfx_colors(player, def_col, def_sub)

                cone = math.pi if self.fused else (0.72 if self.awakened else 0.56)
                eff_range = self.range + (85 if self.fused else 0)

                # Ghi lại dư ảnh nhát chém (200ms = 12 frames)
                slashes = [self.angle, self.angle + math.pi] if (self.awakened or self.fused) else [self.angle]
                if self.fused:
                    slashes.extend([self.angle + math.pi / 2, self.angle - math.pi / 2])
                for s_ang in slashes:
                    self.slash_trails.append((player.x, player.y, s_ang, eff_range, 12, 12, col, sub_col))

                total_dealt = 0
                hit_count = 0
                for e in enemies:
                    if not e.alive:
                        continue
                    if dist((player.x, player.y), (e.x, e.y)) < eff_range + e.radius:
                        a = angle_to((player.x, player.y), (e.x, e.y))
                        da = abs(math.atan2(math.sin(a - self.angle), math.cos(a - self.angle)))
                        back_da = abs(math.atan2(math.sin(a - (self.angle + math.pi)), math.cos(a - (self.angle + math.pi))))
                        if self.fused or da < cone or (self.awakened and back_da < cone * 0.85):
                            dealt = deal_player_damage(
                                player,
                                e,
                                int(self.damage * (1.35 if self.fused else 1.0)),
                                damage_numbers,
                                col,
                                element=self.element,
                                all_enemies=enemies,
                                particles=particles,
                                sfx=sfx,
                            )
                            total_dealt += dealt
                            hit_count += 1
                            # Gây xuất huyết (Bleeding DoT)
                            if hasattr(e, "apply_burn"):
                                e.apply_burn(120, max(3, self.damage // 3))
                            if self.fused and hasattr(e, "apply_slow"):
                                e.apply_slow(50, 0.45)
                            # Tia máu & tia lửa văng theo hướng chém
                            for _ in range(5):
                                particles.append(Particle(e.x, e.y, col, speed=4.2, size=4, life=22, angle=a, spread=0.55))
                            particles.append(Particle(e.x, e.y, (255, 255, 255), speed=5.0, size=3, life=14, angle=a, spread=0.35))
                if hit_count >= 3:
                    player.micro_shake = max(getattr(player, "micro_shake", 0), 4)
                # Hồi máu theo % sát thương gây ra (Blood Moon Lifesteal) + hiển thị số +HP màu xanh
                if total_dealt > 0 and player.hp < player.max_hp:
                    heal = max(1, int(total_dealt * (0.10 if self.fused else 0.05)))
                    old_hp = player.hp
                    player.hp = min(player.max_hp, player.hp + heal)
                    if player.hp > old_hp:
                        damage_numbers.append(DamageNumber(
                            player.x, player.y - 24, player.hp - old_hp, (80, 255, 130), is_heal=True))
            else:
                self.cooldown = eff_tick // 2

    def draw(self, surf, cam_x, cam_y, player):
        if self.level <= 0 and not self.fused:
            return
        px, py = int(player.x - cam_x), int(player.y - cam_y)
        # Nếu đã Hợp Nhất thành Huyết Ngục Vĩnh Hằng: Vẽ pháp trận huyết kim khổng lồ
        if self.fused:
            dom_r = int((self.range + 75) * (0.94 + 0.06 * math.sin(self.domain_pulse)))
            c1, c2 = get_skin_vfx_colors(player, (255, 60, 80), (255, 215, 70))
            draw_magic_circle(surf, px, py, dom_r, c1, self.domain_pulse * 0.45, alpha=110)
            dom_s = pygame.Surface((dom_r * 2 + 12, dom_r * 2 + 12), pygame.SRCALPHA)
            c = (dom_r + 6, dom_r + 6)
            pygame.draw.circle(dom_s, (*c1, 28), c, dom_r)
            pygame.draw.circle(dom_s, (*c1, 150), c, dom_r, 3)
            pygame.draw.circle(dom_s, (*c2, 125), c, int(dom_r * 0.72), 2)
            surf.blit(dom_s, (px - dom_r - 6, py - dom_r - 6))

        # Vẽ kiếm khí hình bán nguyệt đa lớp có răng cưa năng lượng (Jagged Crescent Wave) + dư ảnh 200ms
        for (wx, wy, base_ang, r, lf, mlf, col, sub_col) in self.slash_trails:
            sx, sy = int(wx - cam_x), int(wy - cam_y)
            t = lf / float(mlf)
            alpha = int(t * 235)
            arc_pts_outer = []
            arc_pts_mid = []
            arc_pts_inner = []
            steps = 14
            sweep = 0.68
            for s_i in range(steps + 1):
                frac = s_i / steps
                ang = base_ang - sweep + (2 * sweep * frac)
                # Răng cưa kiếm khí ở rìa ngoài (Jagged energy edge)
                jag = (8.0 * math.sin(s_i * 2.7 + lf * 0.9)) if (0 < s_i < steps) else 0.0
                out_r = r * (0.88 + 0.14 * math.sin(frac * math.pi)) + jag
                mid_r = r * (0.72 + 0.12 * math.sin(frac * math.pi))
                in_r = r * (0.48 + 0.25 * (1.0 - math.sin(frac * math.pi)))
                arc_pts_outer.append((sx + int(math.cos(ang) * out_r), sy + int(math.sin(ang) * out_r)))
                arc_pts_mid.append((sx + int(math.cos(ang) * mid_r), sy + int(math.sin(ang) * mid_r)))
                arc_pts_inner.append((sx + int(math.cos(ang) * in_r), sy + int(math.sin(ang) * in_r)))

            poly_outer = arc_pts_outer + list(reversed(arc_pts_inner))
            poly_core = arc_pts_mid + list(reversed(arc_pts_inner))
            slash_s = get_slash_scratch_surf()
            pygame.draw.polygon(slash_s, (*col, alpha // 2), poly_outer)
            pygame.draw.polygon(slash_s, (*sub_col, int(alpha * 0.78)), poly_core)
            pygame.draw.lines(slash_s, (255, 255, 255, alpha), False, arc_pts_mid, 3)
            pygame.draw.polygon(slash_s, (*col, alpha), poly_outer, 2)
            surf.blit(slash_s, (0, 0))
            # Điểm bùng sáng ở tâm đường kiếm
            tip_x = sx + int(math.cos(base_ang) * (r * 0.85))
            tip_y = sy + int(math.sin(base_ang) * (r * 0.85))
            draw_additive_glow(surf, tip_x, tip_y, int(38 * t), col, intensity=0.55 * t)
            # Nếu mặc skin Luffy Gear 5: kèm tia sét Haki Bá Vương đỏ-đen trên nhát chém!
            if getattr(player, "skin_id", "default") == "luffy" and lf % 2 == 0:
                p_start = arc_pts_outer[2]
                p_end = arc_pts_outer[-3]
                draw_jagged_lightning_arc(surf, p_start, p_end, (255, 35, 65), (20, 5, 10), width=3, branches=1, dark_haki=True)


class SingularityOrb:
    """Quả cầu Hố Đen Hư Không hút kẻ địch vào tâm rồi phát nổ Nova."""
    def __init__(self, x, y, angle, damage, pull_radius, fused=False, awakened=False, skin_id="default"):
        self.x, self.y = float(x), float(y)
        self.vx = math.cos(angle) * 2.2
        self.vy = math.sin(angle) * 2.2
        self.damage = damage
        self.pull_radius = pull_radius
        self.fused = fused
        self.awakened = awakened
        self.skin_id = skin_id
        self.element = Element.VOID
        self.life = 135 if fused else 105
        self.max_life = self.life
        self.alive = True
        self.nova_timer = 0
        self.lightning_arcs: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []

    def update(self, player, enemies, particles, damage_numbers, sfx=None):
        if self.nova_timer > 0:
            self.nova_timer -= 1
            if self.nova_timer <= 0:
                self.alive = False
            return

        self.x += self.vx
        self.y += self.vy
        self.vx *= 0.988
        self.vy *= 0.988
        self.life -= 1
        self.lightning_arcs.clear()

        col, sub_col = get_skin_vfx_colors(player, (185, 100, 255), (110, 235, 255))

        # Lực hút Hố Đen kéo kẻ địch về tâm
        for e in enemies:
            if not e.alive:
                continue
            d = dist((self.x, self.y), (e.x, e.y))
            if d < self.pull_radius and d > 6:
                nx, ny = norm(self.x - e.x, self.y - e.y)
                pull_str = 2.6 if self.fused else (1.9 if self.awakened else 1.4)
                e.x += nx * pull_str
                e.y += ny * pull_str
                if self.life % 20 == 0:
                    deal_player_damage(
                        player,
                        e,
                        max(4, self.damage // 3),
                        damage_numbers,
                        col,
                        element=self.element,
                        all_enemies=enemies,
                        particles=particles,
                        sfx=sfx,
                    )

        # Khi Hợp Nhất (Cosmic Tempest): Phóng sét chuỗi liên tục từ Hố Đen
        if self.fused and self.life % 14 == 0:
            nearby = [e for e in enemies if e.alive and dist((self.x, self.y), (e.x, e.y)) < self.pull_radius * 1.45]
            nearby.sort(key=lambda e: dist((self.x, self.y), (e.x, e.y)))
            for t_e in nearby[:4]:
                self.lightning_arcs.append(((self.x, self.y), (t_e.x, t_e.y)))
                deal_player_damage(
                    player,
                    t_e,
                    int(self.damage * 0.65),
                    damage_numbers,
                    sub_col,
                    element=Element.LIGHTNING if self.fused else self.element,
                    all_enemies=enemies,
                    particles=particles,
                    sfx=sfx,
                )

        # Phát nổ Arcane Nova khi hết thời gian tồn tại
        if self.life <= 0:
            self.nova_timer = 16
            nova_col, _ = get_skin_vfx_colors(player, (255, 215, 80) if self.fused else (195, 95, 255), (110, 235, 255))
            hit_cnt = 0
            for e in enemies:
                if e.alive and dist((self.x, self.y), (e.x, e.y)) < self.pull_radius * 1.15 + e.radius:
                    deal_player_damage(
                        player,
                        e,
                        int(self.damage * 1.8),
                        damage_numbers,
                        nova_col,
                        element=self.element,
                        all_enemies=enemies,
                        particles=particles,
                        sfx=sfx,
                    )
                    hit_cnt += 1
            if hit_cnt >= 2:
                player.micro_shake = max(getattr(player, "micro_shake", 0), 5)
            for i in range(20):
                ang = (math.tau / 20) * i
                particles.append(Particle(self.x, self.y, nova_col, speed=4.8, size=5, life=30, angle=ang, spread=0.25))
            if sfx:
                sfx.play_orb()

    def draw(self, surf, cam_x, cam_y, tick):
        sx, sy = int(self.x - cam_x), int(self.y - cam_y)
        if not (-180 < sx < SCREEN_W + 180 and -180 < sy < SCREEN_H + 180):
            return
        col = (255, 195, 60) if self.fused else (165, 65, 255)
        sub_col = (110, 235, 255)
        if self.skin_id in ANIME_SKIN_BY_ID:
            col = ANIME_SKIN_BY_ID[self.skin_id]["vfx_primary"]
            sub_col = ANIME_SKIN_BY_ID[self.skin_id]["vfx_secondary"]

        if self.nova_timer > 0:
            # Sóng xung kích biến dạng không gian (Expanding Distortion Shockwave)
            t = 1.0 - (self.nova_timer / 16.0)
            nr = max(8, int(self.pull_radius * 1.2 * t))
            draw_additive_glow(surf, sx, sy, nr, col, intensity=0.85 * (1.0 - t))
            ns = pygame.Surface((nr * 2 + 12, nr * 2 + 12), pygame.SRCALPHA)
            c_pt = (nr + 6, nr + 6)
            pygame.draw.circle(ns, (*col, int(220 * (1.0 - t))), c_pt, nr, 5)
            pygame.draw.circle(ns, (255, 255, 255, int(200 * (1.0 - t))), c_pt, int(nr * 0.82), 2)
            pygame.draw.circle(ns, (*sub_col, int(130 * (1.0 - t))), c_pt, int(nr * 0.6))
            surf.blit(ns, (sx - nr - 6, sy - nr - 6))
            return

        pr = int(self.pull_radius * (0.92 + 0.08 * math.sin(tick * 0.2)))
        # Cổ ngữ ma thuật xoay dưới chân Hố Đen (Rotating Arcane Runes)
        draw_magic_circle(surf, sx, sy, pr, col, -tick * 0.045, alpha=125)
        draw_additive_glow(surf, sx, sy, int(pr * 0.65), col, intensity=0.45)

        field = pygame.Surface((pr * 2 + 8, pr * 2 + 8), pygame.SRCALPHA)
        c = (pr + 4, pr + 4)
        pygame.draw.circle(field, (*col, 26), c, pr)
        pygame.draw.circle(field, (*col, 130), c, pr, 2)
        for i in range(6):
            a = tick * 0.09 + i * (math.tau / 6)
            rx = c[0] + int(math.cos(a) * (pr * 0.72))
            ry = c[1] + int(math.sin(a) * (pr * 0.72))
            pygame.draw.line(field, (*sub_col, 140), c, (rx, ry), 2)
        surf.blit(field, (sx - pr - 4, sy - pr - 4))

        # Lõi Hố Đen (Hollow Purple cho Gojo / Dark Singularity)
        core_r = 19 if self.fused else 15
        pygame.draw.circle(surf, (12, 4, 24), (sx, sy), core_r)
        pygame.draw.circle(surf, sub_col if self.fused else col, (sx, sy), core_r, 3)
        pygame.draw.circle(surf, C_WHITE, (sx, sy), core_r - 4, 1)

        dark_haki = (self.skin_id == "luffy")
        for (x1, y1), (x2, y2) in self.lightning_arcs:
            p1 = (int(x1 - cam_x), int(y1 - cam_y))
            p2 = (int(x2 - cam_x), int(y2 - cam_y))
            draw_jagged_lightning_arc(surf, p1, p2, sub_col, C_WHITE, width=3, branches=2, dark_haki=dark_haki)


class VoidSingularityWeapon:
    """
    Kỹ năng Độc Quyền Pháp Sư Tinh Vân: Hố Đen Hư Không (Void Singularity).
    Khi Hợp Nhất với Bão Sấm Sét -> Bão Từ Trường Vũ Trụ (Cosmic Tempest).
    """
    def __init__(self):
        self.level = 0
        self.fused = False
        self.element = Element.VOID
        self.damage = 28
        self.pull_radius = 115
        self.cooldown = 0
        self.tick = 110
        self.orbs: List[SingularityOrb] = []

    @property
    def awakened(self) -> bool:
        return self.level >= 5 or self.fused

    def upgrade(self):
        self.level += 1
        if self.level == 1:
            return
        self.damage += 10
        self.pull_radius += 14
        self.tick = max(55, self.tick - 10)
        if self.level == 5:
            self.damage += 16
            self.pull_radius += 22

    def update(self, player, enemies, particles, damage_numbers, sfx=None):
        if self.level <= 0 and not self.fused:
            return
        self.cooldown -= 1
        eff_tick = max(32, int(self.tick * (1.0 - getattr(player, "cdr", 0.0))))
        if self.cooldown <= 0:
            self.cooldown = eff_tick
            target = None
            best = 520.0
            for e in enemies:
                if e.alive:
                    d = dist((player.x, player.y), (e.x, e.y))
                    if d < best:
                        best = d
                        target = e
            base_a = angle_to((player.x, player.y), (target.x, target.y)) if target else player.angle
            count = 2 if (self.level >= 4 or self.fused) else 1
            skin_id = getattr(player, "skin_id", "default")
            for i in range(count):
                spread = (i - (count - 1) / 2.0) * 0.45
                self.orbs.append(SingularityOrb(
                    player.x, player.y, base_a + spread,
                    int(self.damage * (1.4 if self.fused else 1.0)),
                    self.pull_radius + (35 if self.fused else 0),
                    fused=self.fused, awakened=self.awakened, skin_id=skin_id))
            if sfx:
                sfx.play_orb()

        for o in self.orbs:
            o.update(player, enemies, particles, damage_numbers, sfx)
        self.orbs = [o for o in self.orbs if o.alive]

    def draw(self, surf, cam_x, cam_y, tick):
        if self.level <= 0 and not self.fused:
            return
        for o in self.orbs:
            o.draw(surf, cam_x, cam_y, tick)


class ShadowTrap:
    """Bẫy Bóng Đêm do Mưa Tên Độc Ảnh để lại trên mặt đất."""
    def __init__(self, x, y, damage, col=(55, 255, 175)):
        self.x, self.y = float(x), float(y)
        self.damage = damage
        self.life = 180
        self.radius = 34
        self.col = col
        self.element = Element.VOID
        self.alive = True

    def update(self, player, enemies, particles, damage_numbers):
        self.life -= 1
        if self.life <= 0:
            self.alive = False
            return
        for e in enemies:
            if e.alive and dist((self.x, self.y), (e.x, e.y)) < self.radius + e.radius:
                # Kích hoạt nổ bẫy độc ảnh
                for sub_e in enemies:
                    if sub_e.alive and dist((self.x, self.y), (sub_e.x, sub_e.y)) < self.radius * 1.8:
                        deal_player_damage(
                            player,
                            sub_e,
                            self.damage,
                            damage_numbers,
                            self.col,
                            element=self.element,
                            all_enemies=enemies,
                            particles=particles,
                        )
                        if hasattr(sub_e, "apply_slow"):
                            sub_e.apply_slow(55, 0.55)
                for i in range(12):
                    ang = (math.tau / 12) * i
                    particles.append(Particle(self.x, self.y, self.col, speed=3.6, life=24, angle=ang, spread=0.25))
                self.alive = False
                return

    def draw(self, surf, cam_x, cam_y, tick):
        sx, sy = int(self.x - cam_x), int(self.y - cam_y)
        if -50 < sx < SCREEN_W + 50 and -50 < sy < SCREEN_H + 50:
            alpha = min(165, self.life * 2)
            draw_magic_circle(surf, sx, sy, self.radius, self.col, tick * 0.05, alpha=alpha)
            draw_additive_glow(surf, sx, sy, int(self.radius * 0.7), self.col, intensity=0.25)


class PhantomArrow:
    """Mũi tên Độc Ảnh nảy giữa nhiều kẻ địch và đặt Bẫy Bóng Đêm."""
    def __init__(self, x, y, angle, damage, bounces=2, awakened=False, skin_id="default"):
        self.x, self.y = float(x), float(y)
        self.spawn_x, self.spawn_y = float(x), float(y)
        self.angle = angle
        self.speed = 9.6
        self.damage = damage
        self.bounces = bounces
        self.awakened = awakened
        self.skin_id = skin_id
        self.element = Element.ICE
        self.life = 75
        self.max_life = 75
        self.hit_set: set = set()
        self.trail: List[Tuple[float, float]] = []
        self.alive = True

    def update(self, player, enemies, traps_out, particles, damage_numbers):
        self.trail.append((self.x, self.y))
        if len(self.trail) > 8:
            self.trail.pop(0)
        self.x += math.cos(self.angle) * self.speed
        self.y += math.sin(self.angle) * self.speed
        self.life -= 1
        def_col = (255, 215, 70) if self.awakened else (55, 255, 175)
        col, _ = get_skin_vfx_colors(player, def_col, (160, 255, 220))

        if self.life <= 0:
            if len(traps_out) < 18:
                traps_out.append(ShadowTrap(self.x, self.y, max(8, int(self.damage * 0.75)), col=col))
            self.alive = False
            return

        for e in enemies:
            if e.alive and id(e) not in self.hit_set:
                if dist((self.x, self.y), (e.x, e.y)) < 12 + e.radius:
                    self.hit_set.add(id(e))
                    deal_player_damage(
                        player,
                        e,
                        self.damage,
                        damage_numbers,
                        col,
                        element=self.element,
                        all_enemies=enemies,
                        particles=particles,
                    )
                    # Mảnh vỡ năng lượng văng theo hướng bắn (Directional Shatter Particles)
                    for _ in range(6):
                        particles.append(Particle(e.x, e.y, col, speed=3.8, size=4, life=20, angle=self.angle, spread=0.65))
                    if len(traps_out) < 18 and random.random() < 0.45:
                        traps_out.append(ShadowTrap(e.x, e.y, max(8, int(self.damage * 0.8)), col=col))
                    if self.bounces > 0:
                        self.bounces -= 1
                        # Tìm mục tiêu kế tiếp để nảy sang (Ricochet)
                        cands = [o for o in enemies if o.alive and id(o) not in self.hit_set and dist((self.x, self.y), (o.x, o.y)) < 220]
                        if cands:
                            nxt = min(cands, key=lambda o: dist((self.x, self.y), (o.x, o.y)))
                            self.angle = angle_to((self.x, self.y), (nxt.x, nxt.y))
                            self.life = max(self.life, 35)
                        else:
                            self.angle += random.uniform(-0.8, 0.8)
                    else:
                        self.alive = False
                    return

    def draw(self, surf, cam_x, cam_y):
        sx, sy = int(self.x - cam_x), int(self.y - cam_y)
        if -40 < sx < SCREEN_W + 40 and -40 < sy < SCREEN_H + 40:
            col = (255, 220, 80) if self.awakened else (55, 255, 175)
            if self.skin_id in ANIME_SKIN_BY_ID:
                col = ANIME_SKIN_BY_ID[self.skin_id]["vfx_primary"]

            # Vòng ma thuật xoay lúc khai hỏa (Rotating Magic Circle on Firing)
            age = self.max_life - self.life
            if age < 12:
                msx, msy = int(self.spawn_x - cam_x), int(self.spawn_y - cam_y)
                draw_magic_circle(surf, msx, msy, 16 + age, col, age * 0.25, alpha=int(180 * (1.0 - age / 12.0)))

            # Vệt đuôi sáng (Glowing Motion Trail)
            if len(self.trail) >= 2:
                for i in range(len(self.trail) - 1):
                    p1 = (int(self.trail[i][0] - cam_x), int(self.trail[i][1] - cam_y))
                    p2 = (int(self.trail[i + 1][0] - cam_x), int(self.trail[i + 1][1] - cam_y))
                    w = max(1, int(4 * (i + 1) / len(self.trail)))
                    pygame.draw.line(surf, col, p1, p2, w)

            draw_additive_glow(surf, sx, sy, 18, col, intensity=0.55)
            tip = (sx + int(math.cos(self.angle) * 14), sy + int(math.sin(self.angle) * 14))
            tail = (sx - int(math.cos(self.angle) * 10), sy - int(math.sin(self.angle) * 10))
            wing_l = (sx - int(math.cos(self.angle - 0.5) * 6), sy - int(math.sin(self.angle - 0.5) * 6))
            wing_r = (sx - int(math.cos(self.angle + 0.5) * 6), sy - int(math.sin(self.angle + 0.5) * 6))
            pygame.draw.line(surf, col, tail, tip, 4)
            pygame.draw.polygon(surf, C_WHITE, [tip, wing_l, wing_r])
            pygame.draw.circle(surf, C_WHITE, tip, 3)


class PhantomArrowWeapon:
    """
    Kỹ năng Độc Quyền Thợ Săn Bóng Đêm: Mưa Tên Độc Ảnh (Phantom Arrow Volley).
    Khi Hợp Nhất với Lưỡi Hái Tử Thần -> Cơn Lốc Tử Thần (Reaper's Hurricane).
    """
    def __init__(self):
        self.level = 0
        self.fused = False
        self.element = Element.ICE
        self.damage = 20
        self.cooldown = 0
        self.tick = 54
        self.arrows: List[PhantomArrow] = []
        self.traps: List[ShadowTrap] = []

    @property
    def awakened(self) -> bool:
        return self.level >= 5 or self.fused

    def upgrade(self):
        self.level += 1
        if self.level == 1:
            return
        self.damage += 8
        self.tick = max(26, self.tick - 6)
        if self.level == 5:
            self.damage += 12

    def spawn_split_arrows(self, x, y, dmg, skin_id="default"):
        for i in range(4):
            ang = i * (math.tau / 4) + random.uniform(-0.2, 0.2)
            self.arrows.append(PhantomArrow(x, y, ang, dmg, bounces=2, awakened=True, skin_id=skin_id))
        if len(self.traps) < 18:
            self.traps.append(ShadowTrap(x, y, dmg))

    def update(self, player, enemies, particles, damage_numbers, sfx=None):
        if self.level <= 0 and not self.fused:
            return
        self.cooldown -= 1
        eff_tick = max(16, int(self.tick * (1.0 - getattr(player, "cdr", 0.0))))
        if self.cooldown <= 0:
            target = None
            best = 480.0
            for e in enemies:
                if e.alive:
                    d = dist((player.x, player.y), (e.x, e.y))
                    if d < best:
                        best = d
                        target = e
            if target:
                self.cooldown = eff_tick
                base_a = angle_to((player.x, player.y), (target.x, target.y))
                volley = 5 if self.fused else (4 if self.awakened else (3 if self.level >= 2 else 2))
                bounces = 3 if self.awakened else (2 if self.level >= 3 else 1)
                skin_id = getattr(player, "skin_id", "default")
                for i in range(volley):
                    spread = (i - (volley - 1) / 2.0) * 0.19
                    self.arrows.append(PhantomArrow(
                        player.x, player.y, base_a + spread,
                        int(self.damage * (1.3 if self.fused else 1.0)),
                        bounces=bounces, awakened=self.awakened, skin_id=skin_id))
                if sfx:
                    sfx.play_hit()
            else:
                self.cooldown = eff_tick // 2

        for ar in self.arrows:
            ar.update(player, enemies, self.traps, particles, damage_numbers)
        self.arrows = [ar for ar in self.arrows if ar.alive]

        for tr in self.traps:
            tr.update(player, enemies, particles, damage_numbers)
        self.traps = [tr for tr in self.traps if tr.alive]

    def draw(self, surf, cam_x, cam_y, tick):
        if self.level <= 0 and not self.fused:
            return
        for tr in self.traps:
            tr.draw(surf, cam_x, cam_y, tick)
        for ar in self.arrows:
            ar.draw(surf, cam_x, cam_y)


class SpiralingHammer:
    """Búa Thánh Ánh Sáng xoay xoắn ốc từ người chơi ra ngoài và giáng cột sáng."""
    def __init__(self, px, py, start_angle, damage, fused=False, awakened=False, skin_id="default"):
        self.cx, self.cy = float(px), float(py)
        self.angle = start_angle
        self.radius = 24.0
        self.damage = damage
        self.fused = fused
        self.awakened = awakened
        self.skin_id = skin_id
        self.element = Element.LIGHTNING
        self.x = self.cx + math.cos(self.angle) * self.radius
        self.y = self.cy + math.sin(self.angle) * self.radius
        self.hit_set: set = set()
        self.smite_beams: List[Tuple[float, float, int]] = []
        self.trail: List[Tuple[float, float]] = []
        self.alive = True

    def update(self, player, enemies, particles, damage_numbers):
        self.cx, self.cy = player.x, player.y
        self.trail.append((self.x, self.y))
        if len(self.trail) > 8:
            self.trail.pop(0)
        self.angle += 0.115
        self.radius += 2.65
        self.x = self.cx + math.cos(self.angle) * self.radius
        self.y = self.cy + math.sin(self.angle) * self.radius
        self.smite_beams = [(bx, by, t - 1) for bx, by, t in self.smite_beams if t > 1]

        # Nếu đã Hợp Nhất (Solar Apocalypse): Rải vệt lửa thái dương trên quỹ đạo búa
        if self.fused and hasattr(player, "fire_trail") and int(self.radius) % 28 == 0:
            player.fire_trail.spawn_pool(self.x, self.y, max(8, self.damage // 2), solar=True)

        max_r = 310 if self.fused else (255 if self.awakened else 210)
        if self.radius >= max_r and not self.smite_beams:
            self.alive = False
            return

        col, sub_col = get_skin_vfx_colors(player, (255, 225, 80), (255, 245, 160))
        if self.radius < max_r:
            for e in enemies:
                if e.alive and id(e) not in self.hit_set:
                    if dist((self.x, self.y), (e.x, e.y)) < 20 + e.radius:
                        self.hit_set.add(id(e))
                        deal_player_damage(
                            player,
                            e,
                            self.damage,
                            damage_numbers,
                            col,
                            element=self.element,
                            all_enemies=enemies,
                            particles=particles,
                        )
                        # Giáng cột sáng Thánh Phạt (Holy Smite Beam) tại vị trí va chạm
                        self.smite_beams.append((e.x, e.y, 14))
                        for sub_e in enemies:
                            if sub_e.alive and dist((e.x, e.y), (sub_e.x, sub_e.y)) < (65 if self.fused else 45):
                                deal_player_damage(
                                    player,
                                    sub_e,
                                    max(6, self.damage // 2),
                                    damage_numbers,
                                    sub_col,
                                    element=self.element,
                                    all_enemies=enemies,
                                    particles=particles,
                                )
                        for _ in range(7):
                            particles.append(Particle(e.x, e.y, col, speed=3.8, angle=self.angle, spread=0.9))

    def draw(self, surf, cam_x, cam_y, tick):
        col = (255, 225, 80)
        if self.skin_id in ANIME_SKIN_BY_ID:
            col = ANIME_SKIN_BY_ID[self.skin_id]["vfx_primary"]
        # Vẽ cột sáng Thánh Phạt từ bầu trời + cổ ngữ mặt đất
        for bx, by, bt in self.smite_beams:
            bsx, bsy = int(bx - cam_x), int(by - cam_y)
            t_ratio = bt / 14.0
            w = max(4, int(28 * t_ratio))
            draw_magic_circle(surf, bsx, bsy, int(36 * (1.2 - 0.3 * t_ratio)), col, tick * 0.1, alpha=int(200 * t_ratio))
            draw_additive_glow(surf, bsx, bsy, int(45 * t_ratio), col, intensity=0.75 * t_ratio)
            beam_s = pygame.Surface((w * 2, 260), pygame.SRCALPHA)
            pygame.draw.rect(beam_s, (*col, int(175 * t_ratio)), (0, 0, w * 2, 260))
            pygame.draw.rect(beam_s, (255, 255, 255, int(235 * t_ratio)), (w // 2, 0, w, 260))
            surf.blit(beam_s, (bsx - w, bsy - 245))

        sx, sy = int(self.x - cam_x), int(self.y - cam_y)
        if -45 < sx < SCREEN_W + 45 and -45 < sy < SCREEN_H + 45:
            if len(self.trail) >= 2:
                for i in range(len(self.trail) - 1):
                    p1 = (int(self.trail[i][0] - cam_x), int(self.trail[i][1] - cam_y))
                    p2 = (int(self.trail[i + 1][0] - cam_x), int(self.trail[i + 1][1] - cam_y))
                    pygame.draw.line(surf, col, p1, p2, max(2, int(5 * (i + 1) / len(self.trail))))
            draw_additive_glow(surf, sx, sy, 26, col, intensity=0.6)
            spin = tick * 0.25
            hx = int(math.cos(spin) * 11)
            hy = int(math.sin(spin) * 11)
            pygame.draw.line(surf, (200, 150, 50), (sx - hx, sy - hy), (sx + hx, sy + hy), 4)
            pygame.draw.circle(surf, col, (sx + hx, sy + hy), 9)
            pygame.draw.circle(surf, C_WHITE, (sx + hx, sy + hy), 9, 2)


class JudgementHammerWeapon:
    """
    Kỹ năng Độc Quyền Thánh Kỵ Sĩ: Phán Quyết Ánh Sáng (Judgement Hammer).
    Khi Hợp Nhất với Vệt Lửa Địa Ngục -> Thánh Phạt Thái Dương (Solar Apocalypse).
    """
    def __init__(self):
        self.level = 0
        self.fused = False
        self.element = Element.LIGHTNING
        self.damage = 26
        self.cooldown = 0
        self.tick = 78
        self.hammers: List[SpiralingHammer] = []

    @property
    def awakened(self) -> bool:
        return self.level >= 5 or self.fused

    def upgrade(self):
        self.level += 1
        if self.level == 1:
            return
        self.damage += 10
        self.tick = max(38, self.tick - 8)
        if self.level == 5:
            self.damage += 16

    def update(self, player, enemies, particles, damage_numbers, sfx=None):
        if self.level <= 0 and not self.fused:
            return
        self.cooldown -= 1
        eff_tick = max(22, int(self.tick * (1.0 - getattr(player, "cdr", 0.0))))
        if self.cooldown <= 0:
            self.cooldown = eff_tick
            count = 4 if self.fused else (3 if self.awakened else (2 if self.level >= 3 else 1))
            skin_id = getattr(player, "skin_id", "default")
            for i in range(count):
                ang = player.angle + i * (math.tau / count)
                self.hammers.append(SpiralingHammer(
                    player.x, player.y, ang,
                    int(self.damage * (1.35 if self.fused else 1.0)),
                    fused=self.fused, awakened=self.awakened, skin_id=skin_id))
            if sfx:
                sfx.play_whip()

        for h in self.hammers:
            h.update(player, enemies, particles, damage_numbers)
        self.hammers = [h for h in self.hammers if h.alive]

    def draw(self, surf, cam_x, cam_y, tick):
        if self.level <= 0 and not self.fused:
            return
        for h in self.hammers:
            h.draw(surf, cam_x, cam_y, tick)


class FirePool:
    """Vùng lửa địa ngục / thái dương thiêu đốt kẻ địch bước qua."""
    def __init__(self, x, y, damage, radius=32, solar=False):
        self.x, self.y = float(x), float(y)
        self.damage = damage
        self.radius = radius
        self.solar = solar
        self.element = Element.FIRE
        self.life = 135
        self.alive = True

    def update(self, player, enemies, damage_numbers):
        self.life -= 1
        if self.life <= 0:
            self.alive = False
            return
        if self.life % 22 == 0:
            def_col = (255, 225, 80) if self.solar else (255, 105, 35)
            col, _ = get_skin_vfx_colors(player, def_col, (255, 240, 130))
            for e in enemies:
                if e.alive and dist((self.x, self.y), (e.x, e.y)) < self.radius + e.radius:
                    deal_player_damage(
                        player,
                        e,
                        self.damage,
                        damage_numbers,
                        col,
                        element=self.element,
                        all_enemies=enemies,
                    )
                    if hasattr(e, "apply_burn"):
                        e.apply_burn(60, max(2, self.damage // 2))

    def draw(self, surf, cam_x, cam_y, tick):
        sx, sy = int(self.x - cam_x), int(self.y - cam_y)
        if -50 < sx < SCREEN_W + 50 and -50 < sy < SCREEN_H + 50:
            alpha = min(155, self.life * 2)
            r = int(self.radius * (0.9 + 0.1 * math.sin(tick * 0.25 + self.x)))
            col = (255, 210, 60) if self.solar else (255, 85, 25)
            draw_additive_glow(surf, sx, sy, int(r * 0.85), col, intensity=0.25 * (alpha / 155.0))
            fs = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(fs, (*col, alpha // 3), (r + 2, r + 2), r)
            pygame.draw.circle(fs, (255, 235, 110, alpha), (r + 2, r + 2), int(r * 0.55))
            surf.blit(fs, (sx - r - 2, sy - r - 2))


class FireTrailWeapon:
    """Vệt Lửa Địa Ngục (Ground Fire Trails): Để lại vệt lửa thiêu đốt mặt đất theo bước chân."""
    def __init__(self):
        self.level = 0
        self.fused = False
        self.element = Element.FIRE
        self.damage = 12
        self.radius = 30
        self.cooldown = 0
        self.tick = 22
        self.pools: List[FirePool] = []

    @property
    def awakened(self) -> bool:
        return self.level >= 5 or self.fused

    def upgrade(self):
        self.level += 1
        if self.level == 1:
            return
        self.damage += 5
        self.radius += 4
        self.tick = max(12, self.tick - 2)

    def spawn_pool(self, x, y, dmg, solar=False):
        if len(self.pools) < 32:
            self.pools.append(FirePool(x, y, dmg, self.radius + 6, solar=solar))

    def update(self, player, enemies, particles, damage_numbers, sfx=None):
        if self.level <= 0 and not self.fused:
            return
        self.cooldown -= 1
        if self.cooldown <= 0:
            self.cooldown = self.tick
            if len(self.pools) < 28:
                self.pools.append(FirePool(player.x, player.y, self.damage, self.radius, solar=self.awakened))
        for p_f in self.pools:
            p_f.update(player, enemies, damage_numbers)
        self.pools = [p_f for p_f in self.pools if p_f.alive]

    def draw(self, surf, cam_x, cam_y, tick):
        if self.level <= 0 and not self.fused:
            return
        for p_f in self.pools:
            p_f.draw(surf, cam_x, cam_y, tick)


class FamiliarWeapon:
    """Tinh Linh Hộ Vệ (Summoning Familiars): Triệu hồi tinh linh bay quanh người chơi bắn đạn phép."""
    def __init__(self):
        self.level = 0
        self.damage = 16
        self.cooldown = 0
        self.tick = 38
        self.angle = 0.0

    @property
    def awakened(self) -> bool:
        return self.level >= 5

    def upgrade(self):
        self.level += 1
        if self.level == 1:
            return
        self.damage += 6
        self.tick = max(18, self.tick - 4)

    def update(self, player, enemies, player_projs, particles, damage_numbers):
        if self.level <= 0:
            return
        self.angle += 0.04
        self.cooldown -= 1
        count = 3 if self.awakened else (2 if self.level >= 3 else 1)
        if self.cooldown <= 0:
            self.cooldown = max(14, int(self.tick * (1.0 - getattr(player, "cdr", 0.0))))
            def_col = (255, 210, 80) if self.awakened else (150, 235, 255)
            col, _ = get_skin_vfx_colors(player, def_col, (255, 255, 255))
            for i in range(count):
                fa = self.angle + i * (math.tau / count)
                fx = player.x + math.cos(fa) * 52
                fy = player.y + math.sin(fa) * 52
                nearest = None
                best_d = 420.0
                for e in enemies:
                    if e.alive:
                        d = dist((fx, fy), (e.x, e.y))
                        if d < best_d:
                            best_d = d
                            nearest = e
                if nearest:
                    ang = angle_to((fx, fy), (nearest.x, nearest.y))
                    player_projs.append(Projectile(
                        fx, fy, ang, 8.6, int(self.damage * getattr(player, "damage_mult", 1.0)),
                        65, col, size=6, pierce=1 + getattr(player, "bonus_pierce", 0)))

    def draw(self, surf, cam_x, cam_y, player, tick):
        if self.level <= 0:
            return
        count = 3 if self.awakened else (2 if self.level >= 3 else 1)
        def_col = (255, 215, 75) if self.awakened else (110, 225, 255)
        col, _ = get_skin_vfx_colors(player, def_col, (255, 255, 255))
        for i in range(count):
            fa = self.angle + i * (math.tau / count)
            fx = int(player.x + math.cos(fa) * 52 - cam_x)
            fy = int(player.y + math.sin(fa) * 52 - cam_y + math.sin(tick * 0.15 + i) * 4)
            draw_additive_glow(surf, fx, fy, 16, col, intensity=0.55)
            pygame.draw.circle(surf, col, (fx, fy), 6)
            pygame.draw.circle(surf, C_WHITE, (fx, fy), 3)


class OrbWeapon:
    """
    Khiên Tinh Cầu (Orbiting Shields):
    Các quả cầu năng lượng xoay quanh nhân vật, co giãn bán kính nhịp nhàng (expand & contract).
    """
    def __init__(self):
        self.damage = 18
        self.cooldown = 0
        self.tick = 1
        self.count = 3
        self.radius = 105
        self.speed = 0.045
        self.angle = 0.0
        self.level = 0
        self.element = Element.LIGHTNING
        self.hit_cooldowns: dict = {}
        self.pulse_phase = 0.0

    @property
    def awakened(self) -> bool:
        return self.level >= 5

    def upgrade(self):
        self.level += 1
        if self.level == 1:
            return
        self.count += 1
        self.damage += 7
        self.radius += 10
        if self.level == 5:
            self.count += 1
            self.damage += 12

    def _current_radius(self) -> float:
        osc = 0.68 + 0.45 * math.sin(self.pulse_phase)
        return self.radius * osc

    def update(self, player, enemies, particles, damage_numbers, sfx=None):
        if self.level <= 0:
            return
        self.angle += self.speed * (1.25 if self.awakened else 1.0)
        self.pulse_phase += 0.065
        cur_r = self._current_radius()
        def_col = (210, 110, 255) if self.awakened else C_CYAN
        col, _ = get_skin_vfx_colors(player, def_col, (255, 200, 60))

        for i in range(self.count):
            a = self.angle + (math.tau / self.count) * i
            ox = player.x + math.cos(a) * cur_r
            oy = player.y + math.sin(a) * cur_r
            for e in enemies:
                if not e.alive:
                    continue
                eid = id(e)
                if eid not in self.hit_cooldowns:
                    self.hit_cooldowns[eid] = 0
                if self.hit_cooldowns[eid] > 0:
                    self.hit_cooldowns[eid] -= 1
                    continue
                if dist((ox, oy), (e.x, e.y)) < (22 if self.awakened else 18) + e.radius:
                    deal_player_damage(
                        player,
                        e,
                        self.damage,
                        damage_numbers,
                        col,
                        element=self.element,
                        all_enemies=enemies,
                        particles=particles,
                        sfx=sfx,
                    )
                    self.hit_cooldowns[eid] = 26
                    if sfx:
                        sfx.play_orb()
                    for _ in range(5):
                        particles.append(Particle(ox, oy, col, speed=3.0, angle=a + math.pi / 2, spread=0.9))
        live = {id(e) for e in enemies}
        self.hit_cooldowns = {k: v for k, v in self.hit_cooldowns.items() if k in live}

    def draw(self, surf, cam_x, cam_y, player, tick):
        if self.level <= 0:
            return
        cur_r = self._current_radius()
        px, py = int(player.x - cam_x), int(player.y - cam_y)
        def_col = (165, 65, 255) if self.awakened else C_CYAN
        col, sub_col = get_skin_vfx_colors(player, def_col, (255, 200, 60))
        for i in range(self.count):
            a = self.angle + (math.tau / self.count) * i
            ox = int(player.x + math.cos(a) * cur_r - cam_x)
            oy = int(player.y + math.sin(a) * cur_r - cam_y)
            if self.awakened:
                pygame.draw.line(surf, (*col, 95), (px, py), (ox, oy), 1)
            # Hào quang Additive Glow rực rỡ quanh mỗi Tinh Cầu
            draw_additive_glow(surf, ox, oy, 26, sub_col if self.awakened else col, intensity=0.55)
            pygame.draw.circle(surf, col, (ox, oy), 11)
            pygame.draw.circle(surf, (25, 10, 45), (ox, oy), 6)
            pygame.draw.circle(surf, C_WHITE, (ox, oy), 3)


class LightningBolt:
    WARN_FRAMES = 12
    STRIKE_FLASH_FRAMES = 14

    def __init__(self, tx, ty, damage, aoe_radius, index=0, awakened=False, chain_count=2, skin_id="default"):
        self.tx, self.ty = float(tx), float(ty)
        self.damage = damage
        self.aoe_radius = aoe_radius
        self.index = index
        self.timer = self.WARN_FRAMES
        self.struck = False
        self.flash_timer = 0
        self.alive = True
        self.awakened = awakened
        self.chain_count = chain_count
        self.skin_id = skin_id
        self.element = Element.LIGHTNING
        self.chain_arcs: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []

    def _strike(self, player, enemies, particles, damage_numbers, sfx):
        self.struck = True
        self.flash_timer = self.STRIKE_FLASH_FRAMES
        hit_enemies = []
        def_col = (255, 215, 80) if self.awakened else C_LIGHTNING
        col, sub_col = get_skin_vfx_colors(player, def_col, (130, 230, 255))
        for e in enemies:
            if not e.alive:
                continue
            if dist((self.tx, self.ty), (e.x, e.y)) < self.aoe_radius + e.radius:
                deal_player_damage(
                    player,
                    e,
                    self.damage,
                    damage_numbers,
                    col,
                    element=self.element,
                    all_enemies=enemies,
                    particles=particles,
                    sfx=sfx,
                )
                hit_enemies.append(e)
                for _ in range(6):
                    particles.append(Particle(e.x, e.y, col, speed=3.8, size=4, life=22))

        if len(hit_enemies) >= 2:
            player.micro_shake = max(getattr(player, "micro_shake", 0), 4)

        curr_x, curr_y = self.tx, self.ty
        chained_ids = {id(e) for e in hit_enemies}
        for _ in range(self.chain_count):
            candidates = [
                e for e in enemies
                if e.alive and id(e) not in chained_ids and dist((curr_x, curr_y), (e.x, e.y)) <= 195
            ]
            if not candidates:
                break
            nxt = min(candidates, key=lambda e: dist((curr_x, curr_y), (e.x, e.y)))
            chained_ids.add(id(nxt))
            self.chain_arcs.append(((curr_x, curr_y), (nxt.x, nxt.y)))
            deal_player_damage(
                player,
                nxt,
                int(self.damage * 0.7),
                damage_numbers,
                sub_col,
                element=self.element,
                all_enemies=enemies,
                particles=particles,
                sfx=sfx,
            )
            for _ in range(5):
                particles.append(Particle(nxt.x, nxt.y, sub_col, speed=3.4))
            curr_x, curr_y = nxt.x, nxt.y

        if sfx:
            sfx.play_lightning()

    def update(self, player, enemies, particles, damage_numbers, sfx=None):
        if not self.struck:
            self.timer -= 1
            if self.timer <= 0:
                self._strike(player, enemies, particles, damage_numbers, sfx)
        else:
            self.flash_timer -= 1
            if self.flash_timer <= 0:
                self.alive = False

    def draw(self, surf, cam_x, cam_y, tick):
        sx = int(self.tx - cam_x)
        sy = int(self.ty - cam_y)
        if not (-140 < sx < SCREEN_W + 140 and -140 < sy < SCREEN_H + 140):
            return
        col = (255, 210, 255) if self.awakened else C_LIGHTNING
        sub_col = (110, 235, 255)
        if self.skin_id in ANIME_SKIN_BY_ID:
            col = ANIME_SKIN_BY_ID[self.skin_id]["vfx_primary"]
            sub_col = ANIME_SKIN_BY_ID[self.skin_id]["vfx_secondary"]
        dark_haki = (self.skin_id == "luffy")

        if not self.struck:
            t = self.timer / self.WARN_FRAMES
            r = max(6, int(self.aoe_radius * (0.55 + 0.45 * t)))
            draw_magic_circle(surf, sx, sy, r, col, tick * 0.08, alpha=155)
        else:
            t = self.flash_timer / self.STRIKE_FLASH_FRAMES
            # Tia thiên lôi phân nhánh răng cưa từ bầu trời xuống (Multi-branching Procedural Lightning)
            sky_pt = (sx + random.randint(-18, 18), sy - 260)
            draw_jagged_lightning_arc(
                surf, sky_pt, (sx, sy), col, C_WHITE,
                width=max(2, int(6 * t)), branches=3, dark_haki=dark_haki
            )
            # Sét chuỗi giật sang các mục tiêu lân cận
            for (x1, y1), (x2, y2) in self.chain_arcs:
                p1 = (int(x1 - cam_x), int(y1 - cam_y))
                p2 = (int(x2 - cam_x), int(y2 - cam_y))
                draw_jagged_lightning_arc(
                    surf, p1, p2, sub_col, C_WHITE,
                    width=max(2, int(4 * t)), branches=2, dark_haki=dark_haki
                )

            # Vòng sóng xung kích điện từ lan rộng dưới đất (Expanding Distortion Shockwave)
            shock_r = int(self.aoe_radius * (1.25 - 0.35 * t))
            draw_additive_glow(surf, sx, sy, shock_r, col, intensity=0.75 * t)
            draw_magic_circle(surf, sx, sy, shock_r, col, tick * 0.12, alpha=int(210 * t))
            pygame.draw.circle(surf, C_WHITE, (sx, sy), max(4, int(10 * t)))


class LightningStaffWeapon:
    """
    Bão Sấm Sét (Thunderstorm):
    Giáng thiên lôi ưu tiên kẻ địch máu cao (High-HP) kèm hiệu ứng sét chuỗi (Chain-Lightning).
    """
    def __init__(self):
        self.level = 0
        self.fused = False
        self.element = Element.LIGHTNING
        self.damage = 30
        self.cooldown = 0
        self.tick = 100
        self.aoe_radius = 58
        self.count = 1
        self.detection_range = 500
        self.active: List[LightningBolt] = []

    @property
    def awakened(self) -> bool:
        return self.level >= 5 or self.fused

    def upgrade(self):
        self.level += 1
        if self.level == 1:
            return
        self.damage += 11
        self.tick = max(48, self.tick - 12)
        self.aoe_radius += 7
        if self.level >= 3 and self.count < 2:
            self.count = 2
        if self.level >= 5:
            self.count = 3
            self.damage += 14

    def _pick_targets(self, player, enemies):
        alive = [e for e in enemies
                 if e.alive and dist((player.x, player.y), (e.x, e.y)) <= self.detection_range]
        alive.sort(key=lambda e: (-e.hp, dist((player.x, player.y), (e.x, e.y))))
        return alive[:self.count]

    def update(self, player, enemies, particles, damage_numbers, sfx=None):
        if self.level <= 0:
            return
        self.cooldown -= 1
        eff_tick = max(25, int(self.tick * (1.0 - getattr(player, "cdr", 0.0))))
        if self.cooldown <= 0:
            targets = self._pick_targets(player, enemies)
            if targets:
                self.cooldown = eff_tick
                chains = 4 if self.awakened else (2 if self.level >= 2 else 1)
                skin_id = getattr(player, "skin_id", "default")
                for i, target in enumerate(targets):
                    self.active.append(
                        LightningBolt(target.x, target.y, self.damage, self.aoe_radius,
                                      index=i, awakened=self.awakened, chain_count=chains, skin_id=skin_id))
            else:
                self.cooldown = eff_tick // 2

        for bolt in self.active:
            bolt.update(player, enemies, particles, damage_numbers, sfx)
        self.active = [bolt for bolt in self.active if bolt.alive]

    def draw(self, surf, cam_x, cam_y, tick):
        if self.level <= 0:
            return
        for bolt in self.active:
            bolt.draw(surf, cam_x, cam_y, tick)


class IceShard:
    def __init__(self, px, py, angle, damage, speed, slow_duration, slow_factor,
                 freeze_duration, lifetime=95, size=7, pierce=1, awakened=False, skin_id="default"):
        self.x, self.y = float(px), float(py)
        self.spawn_x, self.spawn_y = float(px), float(py)
        self.angle = angle
        self.speed = speed
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.damage = damage
        self.slow_duration = slow_duration
        self.slow_factor = slow_factor
        self.freeze_duration = freeze_duration
        self.life = lifetime
        self.max_life = lifetime
        self.size = size
        self.pierce = pierce
        self.hit_set: set = set()
        self.awakened = awakened
        self.skin_id = skin_id
        self.element = Element.ICE
        self.trail: List[Tuple[float, float]] = []
        self.alive = True

    def update(self, player, enemies, particles, damage_numbers, sfx=None):
        self.trail.append((self.x, self.y))
        if len(self.trail) > 8:
            self.trail.pop(0)
        nearest = None
        best_d = 240.0
        for e in enemies:
            if e.alive and id(e) not in self.hit_set:
                d = dist((self.x, self.y), (e.x, e.y))
                if d < best_d:
                    best_d = d
                    nearest = e
        if nearest is not None:
            target_a = angle_to((self.x, self.y), (nearest.x, nearest.y))
            diff = math.atan2(math.sin(target_a - self.angle), math.cos(target_a - self.angle))
            self.angle += clamp(diff, -0.06, 0.06)
            self.vx = math.cos(self.angle) * self.speed
            self.vy = math.sin(self.angle) * self.speed

        self.x += self.vx
        self.y += self.vy
        self.life -= 1
        if self.life <= 0:
            self.alive = False
            return

        def_col = (210, 140, 255) if self.awakened else C_ICE
        col, _ = get_skin_vfx_colors(player, def_col, (180, 240, 255))
        for e in enemies:
            if not e.alive or id(e) in self.hit_set:
                continue
            if dist((self.x, self.y), (e.x, e.y)) < self.size + e.radius:
                self.hit_set.add(id(e))
                deal_player_damage(
                    player,
                    e,
                    self.damage,
                    damage_numbers,
                    col,
                    element=self.element,
                    all_enemies=enemies,
                    particles=particles,
                    sfx=sfx,
                )
                e.apply_slow(self.slow_duration, self.slow_factor)
                if self.freeze_duration > 0:
                    e.apply_freeze(self.freeze_duration)
                # Mảnh băng/năng lượng vỡ tung theo hướng va chạm (Directional Shatter Particles)
                for _ in range(7):
                    particles.append(Particle(e.x, e.y, col, speed=3.6, size=4, life=20, angle=self.angle, spread=0.7))
                if sfx:
                    sfx.play_ice()
                self.pierce -= 1
                if self.pierce <= 0:
                    self.alive = False
                    return

    def draw(self, surf, cam_x, cam_y):
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        if -35 < sx < SCREEN_W + 35 and -35 < sy < SCREEN_H + 35:
            col = (210, 130, 255) if self.awakened else C_ICE
            if self.skin_id in ANIME_SKIN_BY_ID:
                col = ANIME_SKIN_BY_ID[self.skin_id]["vfx_primary"]

            # Vòng phép khai hỏa tại vị trí bắn (Rotating Magic Circle on Firing)
            age = self.max_life - self.life
            if age < 11:
                msx, msy = int(self.spawn_x - cam_x), int(self.spawn_y - cam_y)
                draw_magic_circle(surf, msx, msy, 15 + age, col, -age * 0.28, alpha=int(175 * (1.0 - age / 11.0)))

            # Vệt đuôi lụa phát sáng (Glowing Ribbon Motion Trail)
            if len(self.trail) >= 2:
                for i in range(len(self.trail) - 1):
                    p1 = (int(self.trail[i][0] - cam_x), int(self.trail[i][1] - cam_y))
                    p2 = (int(self.trail[i + 1][0] - cam_x), int(self.trail[i + 1][1] - cam_y))
                    w = max(1, int(5 * (i + 1) / len(self.trail)))
                    pygame.draw.line(surf, col, p1, p2, w)

            draw_additive_glow(surf, sx, sy, int(self.size * 2.5), col, intensity=0.6)
            angle = math.atan2(self.vy, self.vx)
            pts = []
            for off, r in ((0, self.size * 1.7), (math.tau * 0.42, self.size * 0.7),
                           (math.pi, self.size * 1.0), (-math.tau * 0.42, self.size * 0.7)):
                a = angle + off
                pts.append((sx + math.cos(a) * r, sy + math.sin(a) * r))
            pygame.draw.polygon(surf, col, pts)
            pygame.draw.polygon(surf, C_WHITE, pts, 1)


class IceWandWeapon:
    ICE_FREEZE_LEVEL = 5

    def __init__(self):
        self.level = 0
        self.element = Element.ICE
        self.damage = 17
        self.cooldown = 0
        self.tick = 85
        self.proj_speed = 7.2
        self.slow_duration = 90
        self.slow_factor = 0.55
        self.freeze_duration = 0
        self.detection_range = 460
        self.active: List[IceShard] = []

    @property
    def awakened(self) -> bool:
        return self.level >= 5

    def upgrade(self):
        self.level += 1
        if self.level == 1:
            return
        self.damage += 8
        self.tick = max(40, self.tick - 9)
        self.proj_speed += 0.5
        self.slow_duration += 12
        self.slow_factor = max(0.25, self.slow_factor - 0.04)
        if self.level >= self.ICE_FREEZE_LEVEL:
            self.freeze_duration = min(45, 18 + (self.level - self.ICE_FREEZE_LEVEL) * 6)

    def _pick_target(self, player, enemies):
        target = None
        best = self.detection_range
        for e in enemies:
            if not e.alive:
                continue
            d = dist((player.x, player.y), (e.x, e.y))
            if d <= best:
                best = d
                target = e
        return target

    def update(self, player, enemies, particles, damage_numbers, sfx=None):
        if self.level <= 0:
            return
        self.cooldown -= 1
        eff_tick = max(20, int(self.tick * (1.0 - getattr(player, "cdr", 0.0))))
        if self.cooldown <= 0:
            target = self._pick_target(player, enemies)
            if target:
                self.cooldown = eff_tick
                a = angle_to((player.x, player.y), (target.x, target.y))
                pierce = 1 + getattr(player, "bonus_pierce", 0) + (1 if self.awakened else 0)
                shots = 3 if self.awakened else (2 if self.level >= 3 else 1)
                skin_id = getattr(player, "skin_id", "default")
                for i in range(shots):
                    spread = (i - (shots - 1) / 2.0) * 0.18
                    self.active.append(IceShard(
                        player.x, player.y, a + spread, self.damage, self.proj_speed,
                        self.slow_duration, self.slow_factor, self.freeze_duration,
                        pierce=pierce, awakened=self.awakened, skin_id=skin_id))
            else:
                self.cooldown = eff_tick // 2

        for shard in self.active:
            shard.update(player, enemies, particles, damage_numbers, sfx)
        self.active = [shard for shard in self.active if shard.alive]

    def draw(self, surf, cam_x, cam_y, tick):
        if self.level <= 0:
            return
        for shard in self.active:
            shard.draw(surf, cam_x, cam_y)


# ---------------------------------------------------------------------------
# Vũ Khí Độc Quyền Mới: Tử Linh Pháp Sư & Long Chiến Binh
# ---------------------------------------------------------------------------
class SoulMinion:
    """Cốt Binh / Linh Hồn Nguyền Rủa của Tử Linh Pháp Sư truy lùng mục tiêu & nổ hồn phách."""
    def __init__(self, x, y, damage, skin_id="default"):
        self.x, self.y = float(x), float(y)
        self.damage = damage
        self.skin_id = skin_id
        self.element = Element.VOID
        self.alive = True
        self.life = 360  # 6s
        self.max_life = 360
        self.angle = random.uniform(0, math.tau)
        self.speed = 3.8
        self.trail: List[Tuple[float, float]] = []

    def update(self, player, enemies, damage_numbers, particles):
        self.life -= 1
        if self.life <= 0:
            self.alive = False
            return

        self.trail.append((self.x, self.y))
        if len(self.trail) > 6:
            self.trail.pop(0)

        # Tìm mục tiêu gần nhất
        target = None
        closest_d = 480.0
        for e in enemies:
            if e.alive:
                d = dist((self.x, self.y), (e.x, e.y))
                if d < closest_d:
                    closest_d = d
                    target = e

        if target:
            ang = angle_to((self.x, self.y), (target.x, target.y))
            self.x += math.cos(ang) * self.speed
            self.y += math.sin(ang) * self.speed
            if closest_d < target.radius + 12:
                col, _ = get_skin_vfx_colors(player, (50, 245, 190), (120, 255, 230))
                deal_player_damage(
                    player,
                    target,
                    self.damage,
                    damage_numbers,
                    col,
                    element=self.element,
                    all_enemies=enemies,
                    particles=particles,
                )
                for _ in range(6):
                    particles.append(Particle(self.x, self.y, col, speed=3.6, size=4, life=22))
                self.alive = False
        else:
            self.angle += 0.05
            tx = player.x + math.cos(self.angle) * 56
            ty = player.y + math.sin(self.angle) * 56
            self.x = lerp(self.x, tx, 0.12)
            self.y = lerp(self.y, ty, 0.12)

    def draw(self, surf, cam_x, cam_y, tick):
        sx, sy = int(self.x - cam_x), int(self.y - cam_y)
        if -40 < sx < SCREEN_W + 40 and -40 < sy < SCREEN_H + 40:
            col = (40, 230, 185)
            draw_additive_glow(surf, sx, sy, 18, col, intensity=0.55)
            # Đầu lâu / linh hồn phát sáng
            pygame.draw.circle(surf, (225, 245, 240), (sx, sy), 6)
            pygame.draw.circle(surf, col, (sx, sy), 8, 1)
            pygame.draw.circle(surf, (15, 55, 45), (sx - 2, sy - 1), 1)
            pygame.draw.circle(surf, (15, 55, 45), (sx + 2, sy - 1), 1)
            # Khói linh hồn phía sau
            for i, (tx, ty) in enumerate(self.trail):
                tsx, tsy = int(tx - cam_x), int(ty - cam_y)
                tr_alpha = int(140 * (i + 1) / len(self.trail))
                pygame.draw.circle(surf, (*col, tr_alpha) if len(col) == 4 else col, (tsx, tsy), max(1, i // 2))


class SkeletalLegionWeapon:
    """Triệu Hồi Cốt Binh (Skeletal Legion): Triệu hồi binh đoàn linh hồn tự tìm quái & nổ hồn phách."""
    def __init__(self):
        self.level = 0
        self.element = Element.VOID
        self.damage = 22
        self.cooldown = 0
        self.tick = 70
        self.minions: List[SoulMinion] = []
        self.fused = False

    @property
    def awakened(self) -> bool:
        return self.level >= 5 or self.fused

    def upgrade(self):
        self.level += 1
        if self.level == 1:
            return
        self.damage += 7
        self.tick = max(34, self.tick - 7)

    def update(self, player, enemies, particles, damage_numbers, sfx=None):
        if self.level <= 0 and not self.fused:
            return
        self.cooldown -= 1
        max_minions = 7 if self.awakened else (5 if self.level >= 3 else 3)
        if self.cooldown <= 0:
            self.cooldown = max(22, int(self.tick * (1.0 - getattr(player, "cdr", 0.0))))
            if len(self.minions) < max_minions:
                skin_id = getattr(player, "skin_id", "default")
                self.minions.append(SoulMinion(
                    player.x + random.uniform(-25, 25), player.y + random.uniform(-25, 25),
                    self.damage, skin_id=skin_id))
                if sfx:
                    sfx.play_laser()
        for m in self.minions:
            m.update(player, enemies, damage_numbers, particles)
        self.minions = [m for m in self.minions if m.alive]

    def draw(self, surf, cam_x, cam_y, tick):
        if self.level <= 0 and not self.fused:
            return
        for m in self.minions:
            m.draw(surf, cam_x, cam_y, tick)


class DragonThrustWave:
    """Đòn đâm thương lửa rồng quét hình nón xuyên thấu & để lại vết nứt nham thạch."""
    def __init__(self, x, y, angle, damage, range_len=160, width=54):
        self.x, self.y = float(x), float(y)
        self.angle = angle
        self.damage = damage
        self.range_len = range_len
        self.width = width
        self.element = Element.FIRE
        self.life = 14
        self.max_life = 14
        self.alive = True
        self.hit_set = set()

    def update(self, player, enemies, damage_numbers, particles, fire_trail):
        self.life -= 1
        if self.life <= 0:
            self.alive = False
            return
        # Rải vết nứt dung nham trên mặt đất
        if self.life == self.max_life - 2 and fire_trail:
            for fi in (0.35, 0.70, 1.0):
                px = self.x + math.cos(self.angle) * (self.range_len * fi)
                py = self.y + math.sin(self.angle) * (self.range_len * fi)
                fire_trail.spawn_pool(px, py, max(8, self.damage // 2), solar=True)

        for e in enemies:
            if e.alive and id(e) not in self.hit_set:
                mid_x = self.x + math.cos(self.angle) * (self.range_len * 0.5)
                mid_y = self.y + math.sin(self.angle) * (self.range_len * 0.5)
                if dist((mid_x, mid_y), (e.x, e.y)) < (self.range_len * 0.55) + e.radius:
                    self.hit_set.add(id(e))
                    col, _ = get_skin_vfx_colors(player, (255, 115, 35), (255, 235, 110))
                    deal_player_damage(
                        player,
                        e,
                        self.damage,
                        damage_numbers,
                        col,
                        element=self.element,
                        all_enemies=enemies,
                        particles=particles,
                    )
                    if hasattr(e, "apply_burn"):
                        e.apply_burn(90, max(3, self.damage // 3))
                    for _ in range(5):
                        particles.append(Particle(e.x, e.y, col, speed=4.5, angle=self.angle, spread=0.6))

    def draw(self, surf, cam_x, cam_y):
        t = self.life / float(self.max_life)
        sx, sy = int(self.x - cam_x), int(self.y - cam_y)
        length = self.range_len * (1.1 - 0.2 * t)
        cos_a = math.cos(self.angle)
        sin_a = math.sin(self.angle)
        norm_x, norm_y = -sin_a, cos_a
        tip_x = sx + int(cos_a * length)
        tip_y = sy + int(sin_a * length)
        w = int(self.width * t)
        pts = [
            (sx - int(norm_x * (w * 0.3)), sy - int(norm_y * (w * 0.3))),
            (tip_x, tip_y),
            (sx + int(norm_x * (w * 0.3)), sy + int(norm_y * (w * 0.3))),
            (sx + int(cos_a * (length * 0.25)), sy + int(sin_a * (length * 0.25))),
        ]
        draw_additive_glow(surf, tip_x, tip_y, int(35 * t), (255, 115, 35), intensity=0.65)
        pygame.draw.polygon(surf, (255, 80, 25), pts)
        pygame.draw.polygon(surf, (255, 235, 120), pts, 2)


class DragonfireThrustWeapon:
    """Long Viêm Xung Kích (Dragonfire Thrust): Quét thương lửa rồng xuyên phá để lại dung nham."""
    def __init__(self):
        self.level = 0
        self.element = Element.FIRE
        self.damage = 36
        self.cooldown = 0
        self.tick = 58
        self.range_len = 160
        self.thrusts: List[DragonThrustWave] = []
        self.fused = False

    @property
    def awakened(self) -> bool:
        return self.level >= 5 or self.fused

    def upgrade(self):
        self.level += 1
        if self.level == 1:
            return
        self.damage += 11
        self.range_len += 18
        self.tick = max(28, self.tick - 5)

    def update(self, player, enemies, particles, damage_numbers, fire_trail=None, sfx=None):
        if self.level <= 0 and not self.fused:
            return
        self.cooldown -= 1
        if self.cooldown <= 0:
            self.cooldown = max(18, int(self.tick * (1.0 - getattr(player, "cdr", 0.0))))
            ang = player.angle
            nearest = None
            closest_d = 360.0
            for e in enemies:
                if e.alive:
                    d = dist((player.x, player.y), (e.x, e.y))
                    if d < closest_d:
                        closest_d = d
                        nearest = e
            if nearest:
                ang = angle_to((player.x, player.y), (nearest.x, nearest.y))
            self.thrusts.append(DragonThrustWave(player.x, player.y, ang, self.damage, self.range_len))
            if self.awakened:
                # Đâm 2 tia phụ hình cánh rồng hai bên
                self.thrusts.append(DragonThrustWave(player.x, player.y, ang - 0.35, int(self.damage * 0.75), self.range_len * 0.85))
                self.thrusts.append(DragonThrustWave(player.x, player.y, ang + 0.35, int(self.damage * 0.75), self.range_len * 0.85))
            if sfx:
                sfx.play_whip()

        for t_w in self.thrusts:
            t_w.update(player, enemies, damage_numbers, particles, fire_trail)
        self.thrusts = [t_w for t_w in self.thrusts if t_w.alive]

    def draw(self, surf, cam_x, cam_y):
        if self.level <= 0 and not self.fused:
            return
        for t_w in self.thrusts:
            t_w.draw(surf, cam_x, cam_y)


