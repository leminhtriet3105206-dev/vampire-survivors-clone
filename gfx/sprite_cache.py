"""Procedural character, enemy, and anime skin sprite rendering and caching."""
import math
import random
from typing import Any, Dict, Optional, Tuple
import pygame

from core.config import ANIME_SKIN_BY_ID, C_WHITE, SCREEN_W, SCREEN_H
from gfx.biome_renderer import apply_hit_flash_mask, get_drop_shadow
from gfx.vfx import draw_additive_glow, draw_jagged_lightning_arc, draw_magic_circle
from spatial.math_utils import clamp

_ENEMY_SPRITE_CACHE: Dict[Tuple[Any, bool, int, int], pygame.Surface] = {}
_ENEMY_FLASH_CACHE: Dict[Tuple[Any, bool, int, int], pygame.Surface] = {}

def get_skin_vfx_colors(player, default_primary: tuple, default_secondary: tuple) -> Tuple[tuple, tuple]:
    """Trả về cặp màu (primary, secondary) đã biến đổi theo Trang Phục Anime đang mặc."""
    skin_id = getattr(player, "skin_id", "default") if player is not None else "default"
    if skin_id in ANIME_SKIN_BY_ID:
        s = ANIME_SKIN_BY_ID[skin_id]
        return s["primary"], s["secondary"]
    return default_primary, default_secondary



def draw_character_procedural_sprite(
    surf: pygame.Surface,
    cid: str,
    sx: int,
    sy: int,
    r: int,
    color: tuple,
    dark_color: tuple,
    angle: float,
    tick: int,
    vx: float = 0.0,
    vy: float = 0.0,
    moving: bool = False,
    hit_flash: int = 0,
    invincible: int = 0,
    squash_x: float = 1.0,
    squash_y: float = 1.0,
    cape_sway: Tuple[float, float] = (0.0, 0.0),
    is_preview: bool = False,
    skin_id: str = "default",
):
    """
    Vẽ sprite nhân vật đa lớp theo phong cách Dark Fantasy & Cyber-Arcane
    HOẶC theo Trang Phục Anime Huyền Thoại (Dragon Ball, Naruto, Jujutsu Kaisen, One Piece):
      - Áo choàng bay ngược chiều di chuyển
      - Giáp trụ / Pháp bào / Võ phục Anime / Mắt phát sáng & Hào quang riêng biệt
      - Hiệu ứng nhấp nhô (bobbing), nghiêng mình (tilt) và squash-and-stretch
      - Mặt nạ trắng (pygame.mask.from_surface) khi bị trúng đòn (100ms)
    """
    # 1. Hào quang nhịp đập dưới chân nhân vật (Tùy biến theo Skin Anime nếu đang trang bị)
    pulse = 0.85 + 0.15 * math.sin(tick * 0.12)
    aura_r = int((r + 14) * pulse)
    aura_s = pygame.Surface((aura_r * 2 + 8, aura_r + 12), pygame.SRCALPHA)
    if skin_id in ANIME_SKIN_BY_ID:
        aura_col = ANIME_SKIN_BY_ID[skin_id]["primary"]
        sec_col = ANIME_SKIN_BY_ID[skin_id]["secondary"]
        draw_additive_glow(surf, sx, sy + 2, int(r * 1.9), aura_col, 0.45)
    else:
        aura_col = {
            "warrior":       (230, 45, 65),
            "mage":          (175, 85, 255),
            "rogue":         (40, 245, 170),
            "paladin":       (255, 215, 75),
            "necromancer":   (40, 230, 185),
            "dragon_lancer": (255, 105, 40),
        }.get(cid, color)
        sec_col = aura_col
    pygame.draw.ellipse(aura_s, (*aura_col, 48), (4, 4, aura_r * 2, aura_r + 2))
    pygame.draw.ellipse(aura_s, (*sec_col, 135), (4, 4, aura_r * 2, aura_r + 2), 2)
    surf.blit(aura_s, (sx - aura_r - 4, sy + r - aura_r // 2 - 2))

    # 2. Bóng đổ elip (SRCALPHA) dưới chân
    sh = get_drop_shadow(int(r * 2.3), int(r * 0.95), 115)
    surf.blit(sh, (sx - sh.get_width() // 2, sy + r - sh.get_height() // 2 + 2))

    # 3. Tính toán walk cycle bobbing & độ nghiêng
    bob_freq = 0.26 if moving else 0.09
    bob_amp = 3.2 if moving else 1.2
    bob_y = math.sin(tick * bob_freq) * bob_amp
    leg_swing = math.sin(tick * 0.32) * (5.0 if moving else 0.5)

    # Tạo canvas cục bộ để vẽ toàn bộ nhân vật (hỗ trợ squash/stretch, tilt và mask trắng)
    canvas_w, canvas_h = 104, 104
    cx, cy = canvas_w // 2, canvas_h // 2 + 6
    char_surf = pygame.Surface((canvas_w, canvas_h), pygame.SRCALPHA)

    sway_x, sway_y = cape_sway
    flutter = math.sin(tick * 0.24) * 3.5
    cape_tip_x = cx + int(sway_x * 14 + flutter)
    cape_tip_y = cy + r + 8 + int(sway_y * 8)

    aim_cos = math.cos(angle)
    aim_sin = math.sin(angle)
    face_x = int(aim_cos * 4)
    face_y = int(aim_sin * 3)

    # =========================================================================
    # CHẾ ĐỘ TRANG PHỤC ANIME (ANIME SKIN OVERRIDE)
    # =========================================================================
    if skin_id == "saiyan":
        # 1. CHIẾN BINH SIÊU SAIYAN (Dragon Ball — Goku / Super Saiyan)
        # Hào quang Ki vàng bùng cháy quanh thân (Blazing Golden Ki Aura)
        flame_pts = []
        for fi in range(12):
            fa = (math.tau / 12) * fi
            fr = (r + 13) + int(math.sin(tick * 0.35 + fi * 1.7) * 5)
            flame_pts.append((cx + int(math.cos(fa) * (fr * 0.85)), cy - 4 + int(math.sin(fa) * (fr * 1.15))))
        pygame.draw.polygon(char_surf, (255, 215, 35, 80), flame_pts)
        pygame.draw.polygon(char_surf, (255, 245, 130, 185), flame_pts, 2)
        # Tia sét Ki siêu cấp nổ lách tách quanh thân (Super Saiyan Electric Sparks)
        if tick % 4 < 3:
            for _ in range(2):
                sa = random.uniform(0, math.tau)
                sr = random.uniform(r * 0.6, r * 1.4)
                sx1 = cx + int(math.cos(sa) * sr)
                sy1 = cy + int(math.sin(sa) * sr)
                sx2 = sx1 + random.randint(-6, 6)
                sy2 = sy1 + random.randint(-6, 6)
                pygame.draw.line(char_surf, (175, 240, 255), (sx1, sy1), (sx2, sy2), 2)
        # Đám mây Cân Đẩu Vân vàng dưới chân (Flying Nimbus)
        for c_off in (-10, 0, 10):
            pygame.draw.circle(char_surf, (255, 220, 65, 210), (cx + c_off, cy + r - 1), 7)
        # Giày võ thuật xanh lam & Võ phục cam-xanh (Orange/Blue Martial Arts Gi)
        pygame.draw.ellipse(char_surf, (25, 75, 185), (cx - 9, cy + r - 6 + int(leg_swing), 7, 9))
        pygame.draw.ellipse(char_surf, (25, 75, 185), (cx + 2, cy + r - 6 - int(leg_swing), 7, 9))
        pygame.draw.rect(char_surf, (245, 105, 20), (cx - r + 2, cy - 5, (r - 2) * 2, r + 4), border_radius=5)
        # Áo lót & thắt lưng xanh lam bay phấp phới
        pygame.draw.polygon(char_surf, (25, 85, 205), [(cx - 6, cy - 5), (cx + 6, cy - 5), (cx, cy + 3)])
        pygame.draw.rect(char_surf, (20, 65, 175), (cx - r + 2, cy + 4, (r - 2) * 2, 4))
        belt_tip_x = cx + int(sway_x * 8 + flutter)
        pygame.draw.line(char_surf, (25, 80, 205), (cx - 2, cy + 6), (belt_tip_x - 3, cy + 15), 3)
        pygame.draw.line(char_surf, (25, 80, 205), (cx + 2, cy + 6), (belt_tip_x + 3, cy + 14), 3)
        # Khuôn mặt & Mắt xanh ngọc Super Saiyan
        pygame.draw.circle(char_surf, (245, 200, 165), (cx, cy - 10), r - 5)
        pygame.draw.line(char_surf, (40, 235, 215), (cx - 5 + face_x, cy - 10 + face_y), (cx - 1 + face_x, cy - 9 + face_y), 3)
        pygame.draw.line(char_surf, (40, 235, 215), (cx + 1 + face_x, cy - 9 + face_y), (cx + 5 + face_x, cy - 10 + face_y), 3)
        # Mái tóc dựng đứng vàng kim Super Saiyan đa lớp bay theo chuyển động
        hair_spikes = [
            [(cx - 9, cy - 13), (cx - 22 + int(sway_x * 3), cy - 19), (cx - 6, cy - 19)],
            [(cx - 7, cy - 15), (cx - 17 + int(sway_x * 3), cy - 30), (cx - 2, cy - 21)],
            [(cx - 4, cy - 17), (cx - 3 + int(sway_x * 3), cy - 37), (cx + 4, cy - 17)],
            [(cx + 2, cy - 21), (cx + 16 + int(sway_x * 3), cy - 31), (cx + 7, cy - 15)],
            [(cx + 6, cy - 19), (cx + 22 + int(sway_x * 3), cy - 19), (cx + 9, cy - 13)],
        ]
        for sp in hair_spikes:
            pygame.draw.polygon(char_surf, (255, 225, 45), sp)
            pygame.draw.polygon(char_surf, (255, 250, 175), sp, 1)
        # Quả cầu Kamehameha xanh lam tụ lực ở tay
        kx, ky = cx + int(aim_cos * 14), cy + int(aim_sin * 12)
        pygame.draw.circle(char_surf, (40, 200, 255, 190), (kx, ky), 7)
        pygame.draw.circle(char_surf, C_WHITE, (kx, ky), 4)

    elif skin_id == "naruto":
        # 2. NINJA LÀNG LÁ - CỬU VĨ (Naruto — Six Paths / Kurama Mode)
        # 6 Cầu Đạo Ngọc (Truth-Seeking Orbs) xoay quỹ đạo 3D phía sau lưng
        for oi in range(6):
            oa = tick * 0.06 + oi * (math.tau / 6)
            ox = cx + int(math.cos(oa) * (r + 11))
            oy = cy - 6 + int(math.sin(oa) * (r + 8) * 0.68)
            orb_s = 4 if math.sin(oa) > 0 else 3
            pygame.draw.circle(char_surf, (15, 12, 22), (ox, oy), orb_s)
            pygame.draw.circle(char_surf, (255, 175, 45), (ox, oy), orb_s, 1)
        # Áo choàng Chakra Cửu Vĩ cam-vàng rực sáng
        cape_pts = [
            (cx - r + 1, cy - 5),
            (cx + r - 1, cy - 5),
            (cape_tip_x + r + 5, cape_tip_y + 2),
            (cape_tip_x, cape_tip_y - 3),
            (cape_tip_x - r - 5, cape_tip_y + 2),
        ]
        pygame.draw.polygon(char_surf, (255, 130, 20, 210), cape_pts)
        pygame.draw.polygon(char_surf, (255, 225, 75), cape_pts, 2)
        # Dải dây băng trán ninja bay phía sau
        hb_tip_x = cx - 10 + int(sway_x * 9 - flutter)
        pygame.draw.line(char_surf, (25, 25, 35), (cx - 8, cy - 14), (hb_tip_x - 3, cy - 8), 2)
        pygame.draw.line(char_surf, (25, 25, 35), (cx - 8, cy - 14), (hb_tip_x + 1, cy - 3), 2)
        # Thân áo Chakra vàng cam với họa tiết Lục Đạo câu ngọc đen (Black Magatama markings)
        pygame.draw.rect(char_surf, (255, 155, 25), (cx - r + 2, cy - 5, (r - 2) * 2, r + 4), border_radius=5)
        pygame.draw.line(char_surf, (20, 18, 25), (cx, cy - 4), (cx, cy + r - 2), 3)
        for mx_off in (-6, 0, 6):
            pygame.draw.circle(char_surf, (20, 18, 25), (cx + mx_off, cy - 1), 2)
        # Đầu, Băng trán Ninja Làng Lá & Râu Cửu Vĩ
        pygame.draw.circle(char_surf, (250, 205, 170), (cx, cy - 10), r - 5)
        pygame.draw.rect(char_surf, (35, 40, 55), (cx - 10, cy - 16, 20, 5), border_radius=2)
        pygame.draw.rect(char_surf, (200, 210, 225), (cx - 6, cy - 15, 12, 3))
        # 3 Vệt râu cáo trên má (Whiskers)
        for wy in (-2, 0, 2):
            pygame.draw.line(char_surf, (170, 95, 45), (cx - 8, cy - 8 + wy), (cx - 4, cy - 8 + wy), 1)
            pygame.draw.line(char_surf, (170, 95, 45), (cx + 4, cy - 8 + wy), (cx + 8, cy - 8 + wy), 1)
        # Mắt Lục Đạo Tiên Nhân chữ thập vàng cam (Cross-slit Sage Mode Eyes)
        for ex in (cx - 4 + face_x, cx + 4 + face_x):
            pygame.draw.circle(char_surf, (255, 190, 30), (ex, cy - 9 + face_y), 2)
            pygame.draw.line(char_surf, (20, 10, 5), (ex, cy - 11 + face_y), (ex, cy - 7 + face_y), 1)
            pygame.draw.line(char_surf, (20, 10, 5), (ex - 2, cy - 9 + face_y), (ex + 2, cy - 9 + face_y), 1)
        # Tóc vàng nhọn + 2 sừng Chakra Lục Đạo
        for sx_h in (-8, -4, 0, 4, 8):
            pygame.draw.polygon(char_surf, (255, 220, 45), [(cx + sx_h - 3, cy - 15), (cx + sx_h + int(sway_x * 2), cy - 26), (cx + sx_h + 3, cy - 15)])
        # Rasenshuriken xoay tròn trên tay
        rx_w, ry_w = cx + int(aim_cos * 15), cy + int(aim_sin * 12)
        rs_spin = tick * 0.35
        for bi in range(4):
            ba = rs_spin + bi * (math.pi / 2)
            pygame.draw.polygon(char_surf, (165, 245, 255), [
                (rx_w, ry_w),
                (rx_w + int(math.cos(ba) * 10), ry_w + int(math.sin(ba) * 10)),
                (rx_w + int(math.cos(ba + 0.35) * 6), ry_w + int(math.sin(ba + 0.35) * 6)),
            ])
        pygame.draw.circle(char_surf, (70, 215, 255), (rx_w, ry_w), 4)

    elif skin_id == "gojo":
        # 3. CHÚ THUẬT SƯ VÔ HẠ HẠN (Jujutsu Kaisen — Gojo Satoru)
        # Vòng không gian Vô Lượng Không Xứ (Infinite Void Spatial Halo)
        pygame.draw.circle(char_surf, (165, 55, 255, 95), (cx, cy - 2), r + 9, 2)
        # Đồng phục Chú Thuật Sư cổ cao màu đen tím than có nếp gấp
        pygame.draw.ellipse(char_surf, (20, 18, 30), (cx - 9, cy + r - 6 + int(leg_swing), 7, 9))
        pygame.draw.ellipse(char_surf, (20, 18, 30), (cx + 2, cy + r - 6 - int(leg_swing), 7, 9))
        pygame.draw.rect(char_surf, (22, 20, 36), (cx - r + 2, cy - 6, (r - 2) * 2, r + 5), border_radius=5)
        pygame.draw.rect(char_surf, (55, 50, 85), (cx - r + 2, cy - 6, (r - 2) * 2, r + 5), 1, border_radius=5)
        # Cổ áo cao che cằm
        pygame.draw.rect(char_surf, (28, 25, 45), (cx - 8, cy - 9, 16, 6), border_radius=2)
        # Khuôn mặt + Băng bịt mắt đen & Ánh sáng Lục Nhãn (Six Eyes neon-blue trail)
        pygame.draw.circle(char_surf, (245, 225, 215), (cx, cy - 11), r - 5)
        pygame.draw.rect(char_surf, (12, 12, 18), (cx - 10, cy - 14, 20, 6), border_radius=2)
        pygame.draw.circle(char_surf, (45, 225, 255), (cx - 4 + face_x, cy - 11 + face_y), 2)
        pygame.draw.circle(char_surf, (45, 225, 255), (cx + 4 + face_x, cy - 11 + face_y), 2)
        pygame.draw.line(char_surf, (130, 245, 255), (cx + 4 + face_x, cy - 11 + face_y), (cx + 12 + face_x, cy - 15 + face_y), 2)
        # Mái tóc bạch kim dựng ngược bay theo gió (Spiky White Hair)
        for sx_h in (-9, -5, 0, 5, 9):
            sp_poly = [
                (cx + sx_h - 4, cy - 14),
                (cx + sx_h + int(sway_x * 2.5), cy - 28 - (4 if sx_h == 0 else 0)),
                (cx + sx_h + 4, cy - 14),
            ]
            pygame.draw.polygon(char_surf, (245, 248, 255), sp_poly)
            pygame.draw.polygon(char_surf, (200, 215, 240), sp_poly, 1)
        # Hai quả cầu Chú Lực: Thương (Xanh) & Hách (Đỏ) xoay quanh hai tay
        bx_orb = cx + int(math.cos(angle - 0.5) * 16)
        by_orb = cy + int(math.sin(angle - 0.5) * 14)
        rx_orb = cx + int(math.cos(angle + 0.5) * 16)
        ry_orb = cy + int(math.sin(angle + 0.5) * 14)
        pygame.draw.circle(char_surf, (35, 195, 255), (bx_orb, by_orb), 5)
        pygame.draw.circle(char_surf, C_WHITE, (bx_orb, by_orb), 2)
        pygame.draw.circle(char_surf, (255, 45, 85), (rx_orb, ry_orb), 5)
        pygame.draw.circle(char_surf, C_WHITE, (rx_orb, ry_orb), 2)
        # Tia sáng Tử (Hollow Purple spark) chớp nháy ở trung tâm
        if tick % 6 < 3:
            px_m = (bx_orb + rx_orb) // 2
            py_m = (by_orb + ry_orb) // 2
            pygame.draw.circle(char_surf, (215, 60, 255), (px_m, py_m), 3)
            pygame.draw.circle(char_surf, C_WHITE, (px_m, py_m), 1)

    elif skin_id == "luffy":
        # 4. VUA HẢI TẶC THẦN MẶT TRỜI (One Piece — Luffy Gear 5 Nika)
        # Dải lụa mây trắng Thần Mặt Trời Nika bay uốn lượn quanh vai (Cloud Scarf / Hagoromo)
        for ci in range(8):
            ca = -math.pi * 0.9 + (math.pi * 0.8 * ci / 7.0)
            cloud_x = cx + int(math.cos(ca) * (r + 9)) + int(sway_x * 3)
            cloud_y = cy - 6 + int(math.sin(ca) * (r + 8)) + int(flutter * 0.4)
            pygame.draw.circle(char_surf, (248, 245, 255, 235), (cloud_x, cloud_y), 6)
            pygame.draw.circle(char_surf, (215, 200, 255), (cloud_x, cloud_y), 6, 1)
        # Mũ Rơm treo sau lưng (Straw Hat slung over back)
        pygame.draw.circle(char_surf, (235, 190, 65), (cx - int(aim_cos * 6), cy - 4), 13)
        pygame.draw.circle(char_surf, (210, 40, 45), (cx - int(aim_cos * 6), cy - 4), 9, 2)
        # Trang phục trắng tinh khiết Gear 5 & Đai lưng tím
        pygame.draw.rect(char_surf, (245, 245, 255), (cx - r + 2, cy - 5, (r - 2) * 2, r + 4), border_radius=5)
        pygame.draw.rect(char_surf, (145, 55, 215), (cx - r + 2, cy + 4, (r - 2) * 2, 4))
        # Khuôn mặt cười rạng rỡ & Đôi mắt đỏ-vàng Thần Nika
        pygame.draw.circle(char_surf, (245, 200, 165), (cx, cy - 10), r - 5)
        pygame.draw.circle(char_surf, (255, 45, 75), (cx - 4 + face_x, cy - 10 + face_y), 2)
        pygame.draw.circle(char_surf, (255, 45, 75), (cx + 4 + face_x, cy - 10 + face_y), 2)
        # Mái tóc mây trắng bồng bềnh phát sáng (Glowing White Cloud Hair) nhấp nhô
        cloud_bob = math.sin(tick * 0.22) * 1.5
        for hx_off, hy_off, hr in [(-8, -18, 6), (-4, -23, 6), (0, -22, 7), (4, -23, 6), (8, -18, 6)]:
            pygame.draw.circle(char_surf, (255, 255, 255), (cx + hx_off + int(sway_x * 1.5), int(cy + hy_off + cloud_bob)), hr)
            pygame.draw.circle(char_surf, (215, 210, 245), (cx + hx_off + int(sway_x * 1.5), int(cy + hy_off + cloud_bob)), hr, 1)
        # Tia sét Đen-Đỏ Haki Bá Vương nổ lách tách quanh tay & chân (Conqueror's Haki Lightning)
        for _ in range(2):
            ha_ang = random.uniform(0, math.tau)
            ha_r1 = random.uniform(5, 18)
            hx1 = cx + int(math.cos(ha_ang) * ha_r1)
            hy1 = cy + int(math.sin(ha_ang) * ha_r1)
            hx2 = hx1 + random.randint(-8, 8)
            hy2 = hy1 + random.randint(-8, 8)
            pygame.draw.line(char_surf, (255, 25, 60), (hx1, hy1), (hx2, hy2), 3)
            pygame.draw.line(char_surf, (15, 5, 12), (hx1, hy1), (hx2, hy2), 1)

    else:
        # =====================================================================
        # NGOẠI HÌNH MẶC ĐỊNH THEO 6 HỆ PHÁI RPG (DEFAULT CLASS OUTLOOK)
        # =====================================================================
        if cid == "warrior":
            # Áo choàng chiến bào đỏ sẫm rách tả tơi (Tattered Crimson Cape)
            cape_pts = [
                (cx - r + 2, cy - 6),
                (cx + r - 2, cy - 6),
                (cape_tip_x + r + 3, cape_tip_y - 2),
                (cape_tip_x + r // 2, cape_tip_y - 7),
                (cape_tip_x, cape_tip_y + 3),
                (cape_tip_x - r // 2, cape_tip_y - 6),
                (cape_tip_x - r - 3, cape_tip_y - 1),
            ]
            pygame.draw.polygon(char_surf, (95, 14, 24), cape_pts)
            pygame.draw.polygon(char_surf, (155, 25, 40), cape_pts, 2)
        elif cid == "mage":
            halo_y = cy - r - 10
            pygame.draw.circle(char_surf, (190, 120, 255, 90), (cx, halo_y), r + 6, 2)
            for hi in range(4):
                ha = tick * 0.06 + hi * (math.tau / 4)
                hx = cx + int(math.cos(ha) * (r + 6))
                hy = halo_y + int(math.sin(ha) * (r + 6))
                pygame.draw.circle(char_surf, (100, 240, 255), (hx, hy), 3)
            cape_pts = [
                (cx - r + 1, cy - 4),
                (cx + r - 1, cy - 4),
                (cape_tip_x + r + 2, cape_tip_y),
                (cape_tip_x, cape_tip_y + 4),
                (cape_tip_x - r - 2, cape_tip_y),
            ]
            pygame.draw.polygon(char_surf, (48, 18, 90), cape_pts)
            pygame.draw.polygon(char_surf, (165, 95, 255), cape_pts, 1)
        elif cid == "rogue":
            cape_pts = [
                (cx - r + 3, cy - 5),
                (cx + r - 3, cy - 5),
                (cape_tip_x + r, cape_tip_y - 1),
                (cape_tip_x, cape_tip_y + 5),
                (cape_tip_x - r, cape_tip_y - 1),
            ]
            pygame.draw.polygon(char_surf, (12, 38, 34), cape_pts)
            pygame.draw.polygon(char_surf, (45, 245, 180), cape_pts, 1)
        elif cid == "necromancer":
            # Tà áo pháp bào tử linh rách tả tơi màu xanh ngọc bích tối
            cape_pts = [
                (cx - r + 2, cy - 5),
                (cx + r - 2, cy - 5),
                (cape_tip_x + r + 3, cape_tip_y + 4),
                (cape_tip_x, cape_tip_y + 8),
                (cape_tip_x - r - 3, cape_tip_y + 4),
            ]
            pygame.draw.polygon(char_surf, (15, 38, 38), cape_pts)
            pygame.draw.polygon(char_surf, (40, 230, 185), cape_pts, 1)
        elif cid == "dragon_lancer":
            # Áo choàng vảy rồng đỏ vàng rực lửa
            cape_pts = [
                (cx - r + 1, cy - 6),
                (cx + r - 1, cy - 6),
                (cape_tip_x + r + 6, cape_tip_y + 3),
                (cape_tip_x + 3, cape_tip_y - 2),
                (cape_tip_x, cape_tip_y + 6),
                (cape_tip_x - 3, cape_tip_y - 2),
                (cape_tip_x - r - 6, cape_tip_y + 3),
            ]
            pygame.draw.polygon(char_surf, (110, 25, 15), cape_pts)
            pygame.draw.polygon(char_surf, (255, 140, 30), cape_pts, 2)
        else:  # paladin
            pygame.draw.circle(char_surf, (255, 220, 90, 75), (cx, cy - 4), r + 7, 2)
            cape_pts = [
                (cx - r + 1, cy - 6),
                (cx + r - 1, cy - 6),
                (cape_tip_x + r + 3, cape_tip_y),
                (cape_tip_x, cape_tip_y + 4),
                (cape_tip_x - r - 3, cape_tip_y),
            ]
            pygame.draw.polygon(char_surf, (185, 135, 30), cape_pts)
            pygame.draw.polygon(char_surf, (255, 235, 140), cape_pts, 2)

        # 5. Chân bước đi (Walk cycle boots)
        pygame.draw.ellipse(char_surf, (30, 26, 40), (cx - 9, cy + r - 6 + int(leg_swing), 7, 9))
        pygame.draw.ellipse(char_surf, (30, 26, 40), (cx + 2, cy + r - 6 - int(leg_swing), 7, 9))

        # 6. Thân giáp / Pháp bào & Đầu + Mắt phát sáng + Vũ khí cầm tay
        if cid == "warrior":
            pygame.draw.rect(char_surf, (55, 14, 20), (cx - r + 1, cy - 4, (r - 1) * 2, r + 4), border_radius=6)
            pygame.draw.rect(char_surf, (175, 28, 42), (cx - r + 3, cy - 2, (r - 3) * 2, r), border_radius=4)
            pygame.draw.circle(char_surf, (130, 20, 32), (cx - r - 1, cy - 2), 6)
            pygame.draw.circle(char_surf, (130, 20, 32), (cx + r + 1, cy - 2), 6)
            pygame.draw.polygon(char_surf, (220, 190, 190), [(cx - r - 5, cy - 4), (cx - r - 1, cy - 10), (cx - r + 2, cy - 4)])
            pygame.draw.polygon(char_surf, (220, 190, 190), [(cx + r + 5, cy - 4), (cx + r + 1, cy - 10), (cx + r - 2, cy - 4)])
            pygame.draw.circle(char_surf, (45, 15, 22), (cx, cy - 9), r - 4)
            pygame.draw.circle(char_surf, (140, 24, 36), (cx, cy - 9), r - 6)
            pygame.draw.polygon(char_surf, (230, 210, 195), [(cx - 8, cy - 14), (cx - 17, cy - 25), (cx - 4, cy - 17)])
            pygame.draw.polygon(char_surf, (230, 210, 195), [(cx + 8, cy - 14), (cx + 17, cy - 25), (cx + 4, cy - 17)])
            pygame.draw.line(char_surf, (255, 50, 70), (cx - 6 + face_x, cy - 9 + face_y), (cx - 1 + face_x, cy - 8 + face_y), 3)
            pygame.draw.line(char_surf, (255, 50, 70), (cx + 1 + face_x, cy - 8 + face_y), (cx + 6 + face_x, cy - 9 + face_y), 3)
            pygame.draw.line(char_surf, (255, 220, 220), (cx - 5 + face_x, cy - 9 + face_y), (cx + 5 + face_x, cy - 9 + face_y), 1)
            hx, hy = cx + int(aim_cos * 10), cy + int(aim_sin * 8)
            tx_w = hx + int(aim_cos * 24)
            ty_w = hy + int(aim_sin * 24)
            px_n, py_n = -aim_sin, aim_cos
            blade_pts = [
                (hx + px_n * 3.5, hy + py_n * 3.5),
                (tx_w + aim_cos * 5, ty_w + aim_sin * 5),
                (hx - px_n * 3.5, hy - py_n * 3.5),
            ]
            pygame.draw.polygon(char_surf, (255, 45, 70), blade_pts)
            pygame.draw.polygon(char_surf, (255, 200, 210), blade_pts, 1)
            pygame.draw.line(char_surf, (220, 175, 65),
                             (int(hx + px_n * 7), int(hy + py_n * 7)),
                             (int(hx - px_n * 7), int(hy - py_n * 7)), 3)

        elif cid == "mage":
            robe_pts = [(cx, cy - r), (cx - r - 1, cy + r - 1), (cx + r + 1, cy + r - 1)]
            pygame.draw.polygon(char_surf, (42, 16, 82), robe_pts)
            pygame.draw.polygon(char_surf, (135, 65, 235), [(cx, cy - r + 3), (cx - r + 3, cy + r - 3), (cx + r - 3, cy + r - 3)])
            pygame.draw.line(char_surf, (100, 235, 255), (cx, cy - 4), (cx, cy + r - 3), 2)
            pygame.draw.circle(char_surf, (20, 10, 38), (cx, cy - 9), r - 5)
            pygame.draw.circle(char_surf, (90, 245, 255), (cx - 3 + face_x, cy - 9 + face_y), 2)
            pygame.draw.circle(char_surf, (90, 245, 255), (cx + 4 + face_x, cy - 9 + face_y), 2)
            pygame.draw.ellipse(char_surf, (55, 22, 105), (cx - 16, cy - r - 2, 32, 8))
            pygame.draw.ellipse(char_surf, (180, 120, 255), (cx - 16, cy - r - 2, 32, 8), 1)
            hat_pts = [(cx - 11, cy - r + 1), (cx + 11, cy - r + 1), (cx + 3, cy - r - 19)]
            pygame.draw.polygon(char_surf, (75, 32, 145), hat_pts)
            pygame.draw.polygon(char_surf, (195, 140, 255), hat_pts, 1)
            sx_w = cx + 13
            sy_w = cy - 14
            pygame.draw.line(char_surf, (180, 140, 255), (sx_w - 2, cy + 12), (sx_w, sy_w), 3)
            pygame.draw.circle(char_surf, (90, 245, 255), (sx_w, sy_w - 3), 5)
            pygame.draw.circle(char_surf, C_WHITE, (sx_w, sy_w - 3), 2)

        elif cid == "rogue":
            pygame.draw.polygon(char_surf, (16, 45, 42), [
                (cx - r + 3, cy - 4), (cx + r - 3, cy - 4),
                (cx + r - 5, cy + r - 2), (cx - r + 5, cy + r - 2)
            ])
            pygame.draw.line(char_surf, (45, 255, 180), (cx - 6, cy - 2), (cx + 6, cy + 8), 2)
            pygame.draw.line(char_surf, (45, 255, 180), (cx + 6, cy - 2), (cx - 6, cy + 8), 2)
            hood_pts = [(cx, cy - r - 7), (cx - r + 1, cy - 6), (cx - r + 4, cy + 1), (cx + r - 4, cy + 1), (cx + r - 1, cy - 6)]
            pygame.draw.polygon(char_surf, (22, 65, 56), hood_pts)
            pygame.draw.polygon(char_surf, (55, 255, 190), hood_pts, 2)
            pygame.draw.rect(char_surf, (10, 18, 22), (cx - 8 + face_x, cy - 11 + face_y, 16, 6), border_radius=3)
            pygame.draw.rect(char_surf, (50, 255, 195), (cx - 7 + face_x, cy - 10 + face_y, 14, 4), border_radius=2)
            for side_s in (-1, 1):
                bx_w = cx + int(aim_cos * 11 - aim_sin * side_s * 9)
                by_w = cy + int(aim_sin * 11 + aim_cos * side_s * 9)
                pygame.draw.line(char_surf, (80, 255, 200), (bx_w, by_w), (int(bx_w + aim_cos * 9), int(by_w + aim_sin * 9)), 3)
                px_n, py_n = -aim_sin, aim_cos
                pygame.draw.line(char_surf, (160, 255, 230),
                                 (int(bx_w + aim_cos * 5 + px_n * 5), int(by_w + aim_sin * 5 + py_n * 5)),
                                 (int(bx_w + aim_cos * 5 - px_n * 5), int(by_w + aim_sin * 5 - py_n * 5)), 2)

        elif cid == "necromancer":
            # Pháp bào tử linh & Giáp vai xương đầu lâu
            robe_pts = [(cx, cy - r), (cx - r - 1, cy + r - 1), (cx + r + 1, cy + r - 1)]
            pygame.draw.polygon(char_surf, (12, 28, 32), robe_pts)
            pygame.draw.polygon(char_surf, (30, 95, 90), [(cx, cy - r + 3), (cx - r + 3, cy + r - 3), (cx + r - 3, cy + r - 3)])
            pygame.draw.circle(char_surf, (220, 235, 230), (cx - r - 1, cy - 2), 5)
            pygame.draw.circle(char_surf, (220, 235, 230), (cx + r + 1, cy - 2), 5)
            pygame.draw.circle(char_surf, (40, 230, 185), (cx - r - 1, cy - 2), 2)
            pygame.draw.circle(char_surf, (40, 230, 185), (cx + r + 1, cy - 2), 2)
            hood_pts = [(cx, cy - r - 7), (cx - r + 1, cy - 6), (cx - r + 3, cy + 1), (cx + r - 3, cy + 1), (cx + r - 1, cy - 6)]
            pygame.draw.polygon(char_surf, (10, 22, 25), hood_pts)
            pygame.draw.polygon(char_surf, (40, 230, 185), hood_pts, 1)
            pygame.draw.circle(char_surf, (40, 245, 195), (cx - 4 + face_x, cy - 9 + face_y), 2)
            pygame.draw.circle(char_surf, (40, 245, 195), (cx + 4 + face_x, cy - 9 + face_y), 2)
            # Trượng Tử Linh cầm tay & Lửa linh hồn xoay quanh
            st_x, st_y = cx + 13, cy - 14
            pygame.draw.line(char_surf, (215, 210, 195), (st_x - 3, cy + 12), (st_x, st_y), 3)
            pygame.draw.circle(char_surf, (230, 235, 240), (st_x, st_y - 2), 5)
            pygame.draw.circle(char_surf, (40, 245, 195), (st_x, st_y - 2), 3)
            wisp_a = tick * 0.12
            pygame.draw.circle(char_surf, (120, 255, 220), (st_x + int(math.cos(wisp_a) * 6), st_y - 2 + int(math.sin(wisp_a) * 6)), 2)

        elif cid == "dragon_lancer":
            # Giáp vảy rồng đỏ vàng & Mũ giáp rồng có sừng
            pygame.draw.rect(char_surf, (95, 20, 15), (cx - r + 1, cy - 4, (r - 1) * 2, r + 4), border_radius=6)
            pygame.draw.rect(char_surf, (215, 75, 25), (cx - r + 3, cy - 2, (r - 3) * 2, r), border_radius=4)
            pygame.draw.polygon(char_surf, (255, 190, 45), [(cx - r - 5, cy - 3), (cx - r - 1, cy - 11), (cx - r + 2, cy - 3)])
            pygame.draw.polygon(char_surf, (255, 190, 45), [(cx + r + 5, cy - 3), (cx + r + 1, cy - 11), (cx + r - 2, cy - 3)])
            pygame.draw.circle(char_surf, (80, 18, 12), (cx, cy - 9), r - 4)
            pygame.draw.polygon(char_surf, (255, 185, 40), [(cx - 7, cy - 13), (cx - 15, cy - 24), (cx - 3, cy - 16)])
            pygame.draw.polygon(char_surf, (255, 185, 40), [(cx + 7, cy - 13), (cx + 15, cy - 24), (cx + 3, cy - 16)])
            pygame.draw.line(char_surf, (255, 160, 30), (cx - 6 + face_x, cy - 9 + face_y), (cx + 6 + face_x, cy - 9 + face_y), 3)
            pygame.draw.circle(char_surf, (255, 235, 140), (cx + face_x, cy - 9 + face_y), 2)
            # Ngọn Long Thương cầm tay với mũi thương rực lửa
            hx, hy = cx + int(aim_cos * 10), cy + int(aim_sin * 8)
            tx_w = hx + int(aim_cos * 26)
            ty_w = hy + int(aim_sin * 26)
            px_n, py_n = -aim_sin, aim_cos
            pygame.draw.line(char_surf, (180, 145, 60), (hx - aim_cos * 6, hy - aim_sin * 6), (tx_w, ty_w), 3)
            spear_pts = [
                (tx_w + aim_cos * 8, ty_w + aim_sin * 8),
                (tx_w + px_n * 5, ty_w + py_n * 5),
                (tx_w - px_n * 5, ty_w - py_n * 5),
            ]
            pygame.draw.polygon(char_surf, (255, 105, 30), spear_pts)
            pygame.draw.polygon(char_surf, (255, 235, 150), spear_pts, 1)

        else:  # paladin
            pygame.draw.rect(char_surf, (195, 165, 80), (cx - r - 2, cy - 5, (r + 2) * 2, r + 6), border_radius=6)
            pygame.draw.rect(char_surf, (245, 240, 220), (cx - r + 1, cy - 3, (r - 1) * 2, r + 2), border_radius=5)
            pygame.draw.rect(char_surf, (245, 190, 40), (cx - 2, cy - 2, 4, 12))
            pygame.draw.rect(char_surf, (245, 190, 40), (cx - 6, cy + 2, 12, 4))
            pygame.draw.circle(char_surf, (235, 230, 210), (cx, cy - 9), r - 4)
            pygame.draw.circle(char_surf, (245, 195, 55), (cx, cy - 9), r - 4, 2)
            pygame.draw.line(char_surf, (255, 235, 110), (cx - 5 + face_x, cy - 9 + face_y), (cx + 5 + face_x, cy - 9 + face_y), 3)
            sh_x, sh_y = cx - 13, cy + 1
            pygame.draw.polygon(char_surf, (245, 210, 75), [(sh_x - 6, sh_y - 7), (sh_x + 6, sh_y - 7), (sh_x + 6, sh_y + 2), (sh_x, sh_y + 9), (sh_x - 6, sh_y + 2)])
            pygame.draw.polygon(char_surf, C_WHITE, [(sh_x - 6, sh_y - 7), (sh_x + 6, sh_y - 7), (sh_x + 6, sh_y + 2), (sh_x, sh_y + 9), (sh_x - 6, sh_y + 2)], 2)
            hm_y = cy - 4 + int(math.sin(tick * 0.15) * 4)
            hm_x = cx + 15
            pygame.draw.line(char_surf, (190, 140, 50), (hm_x, hm_y - 6), (hm_x, hm_y + 10), 3)
            pygame.draw.rect(char_surf, (255, 220, 80), (hm_x - 7, hm_y - 11, 14, 7), border_radius=2)
            pygame.draw.rect(char_surf, C_WHITE, (hm_x - 7, hm_y - 11, 14, 7), 1, border_radius=2)

    # 7. Áp dụng Squash-and-Stretch & Nghiêng mình (Lean/Tilt)
    final_surf = char_surf
    if abs(squash_x - 1.0) > 0.02 or abs(squash_y - 1.0) > 0.02:
        new_w = max(16, int(canvas_w * squash_x))
        new_h = max(16, int(canvas_h * squash_y))
        final_surf = pygame.transform.smoothscale(final_surf, (new_w, new_h))

    if abs(vx) > 0.05 and not is_preview:
        tilt_deg = clamp(-vx * 2.8, -11.0, 11.0)
        final_surf = pygame.transform.rotate(final_surf, tilt_deg)

    # 8. Hit Flash: Mặt nạ silhouette trắng (100ms)
    if hit_flash > 0:
        final_surf = apply_hit_flash_mask(final_surf)
    elif invincible > 0 and (tick // 4) % 2 == 0:
        final_surf.set_alpha(155)

    rect = final_surf.get_rect(center=(sx, int(sy + bob_y - 4)))
    surf.blit(final_surf, rect.topleft)

