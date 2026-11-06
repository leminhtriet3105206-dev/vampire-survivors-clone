"""Biome rendering, background tile chunks, environment props, shadows, and vignette."""
import math
import random
from typing import Dict, Optional, Tuple
import pygame

from core.config import SCREEN_W, SCREEN_H, TILE
from spatial.math_utils import clamp

_SHADOW_CACHE: Dict[Tuple[int, int, int], pygame.Surface] = {}
_TILE_CHUNK_CACHE: Dict[int, pygame.Surface] = {}
_VIGNETTE_CACHE: Optional[pygame.Surface] = None
_GLOBAL_SLASH_SURF: Optional[pygame.Surface] = None
_PLAYER_GLOW_CACHE: Dict[Tuple[tuple, int], pygame.Surface] = {}


def get_slash_scratch_surf() -> pygame.Surface:
    """Bề mặt scratch tái sử dụng cho nhát chém fullscreen, triệt tiêu phân bổ bộ nhớ 3.68MB/frame."""
    global _GLOBAL_SLASH_SURF
    if _GLOBAL_SLASH_SURF is None or _GLOBAL_SLASH_SURF.get_size() != (SCREEN_W, SCREEN_H):
        _GLOBAL_SLASH_SURF = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    _GLOBAL_SLASH_SURF.fill((0, 0, 0, 0))
    return _GLOBAL_SLASH_SURF


def get_player_glow_surface(color: tuple, glow_r: int = 75) -> pygame.Surface:
    """Cache bề mặt quầng sáng quanh nhân vật."""
    col = color[:3]
    key = (col, glow_r)
    if key not in _PLAYER_GLOW_CACHE:
        s = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*col, 22), (glow_r, glow_r), glow_r)
        _PLAYER_GLOW_CACHE[key] = s
    return _PLAYER_GLOW_CACHE[key]


def get_drop_shadow(w: int, h: int, alpha: int = 105) -> pygame.Surface:
    """Trả về bóng đổ hình elip (SRCALPHA) được cache để giữ 60 FPS."""
    w = max(4, int(w))
    h = max(4, int(h))
    key = (w, h, alpha)
    if key not in _SHADOW_CACHE:
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (0, 0, 0, alpha), (0, 0, w, h))
        if w > 8 and h > 6:
            pygame.draw.ellipse(s, (0, 0, 0, min(255, int(alpha * 1.35))),
                                (w // 6, h // 6, w - w // 3, h - h // 3))
        _SHADOW_CACHE[key] = s
    return _SHADOW_CACHE[key]


def apply_hit_flash_mask(sprite_surf: pygame.Surface) -> pygame.Surface:
    """Tạo mặt nạ silhouette trắng (100ms) bằng hòa trộn BLEND_RGB_ADD siêu tốc (tránh tạo mask)."""
    try:
        flash_surf = sprite_surf.copy()
        flash_surf.fill((255, 255, 255), special_flags=pygame.BLEND_RGB_ADD)
        return flash_surf
    except Exception:
        return sprite_surf


def get_arcane_tile_chunk(biome_id: int = 0) -> pygame.Surface:
    """
    Tạo và cache bề mặt nền theo 3 Quần Xã Dark Fantasy (256x256):
      0: Nghĩa Địa Cổ Đại (Cursed Graveyard) - Đá phiến nứt vỡ & rêu phong cổ đại
      1: Hầm Ngục Huyết Nguyệt (Blood Moon Dungeon) - Gạch hắc diện thạch & cổ ngữ máu
      2: Rừng Hư Không (Corrupted Abyss Forest) - Thảm cỏ tím thẫm & mạch tinh thể hư không
    """
    global _TILE_CHUNK_CACHE
    biome_id = int(biome_id) % 3
    if biome_id in _TILE_CHUNK_CACHE:
        return _TILE_CHUNK_CACHE[biome_id]

    chunk_size = TILE * 4  # 256x256
    surf = pygame.Surface((chunk_size, chunk_size))
    rng = random.Random(421337 + biome_id * 997)

    if biome_id == 0:
        # 1. Nghĩa Địa Cổ Đại (Cursed Graveyard): Cracked dark-slate cobblestones & mossy patches
        surf.fill((12, 14, 18))
        for ty in range(0, chunk_size, TILE):
            for tx in range(0, chunk_size, TILE):
                shade = rng.randint(-3, 4)
                base_c = (max(8, 17 + shade), max(10, 20 + shade), max(14, 25 + shade))
                pygame.draw.rect(surf, base_c, (tx + 1, ty + 1, TILE - 2, TILE - 2), border_radius=4)
                pygame.draw.rect(surf, (24, 29, 36), (tx, ty, TILE, TILE), 1)
                sub_w = TILE // 2 - 4
                sub_h = TILE // 2 - 4
                for sy_i in range(2):
                    for sx_i in range(2):
                        stx = tx + 3 + sx_i * (TILE // 2) + (3 if sy_i % 2 == 1 and sx_i == 0 else 0)
                        sty = ty + 3 + sy_i * (TILE // 2)
                        c_var = rng.randint(-3, 3)
                        stone_c = (20 + c_var, 23 + c_var, 29 + c_var)
                        pygame.draw.rect(surf, stone_c, (stx, sty, sub_w, sub_h), border_radius=3)
                        pygame.draw.rect(surf, (10, 12, 16), (stx, sty, sub_w, sub_h), 1, border_radius=3)
                        # Vết nứt trên phiến đá
                        if rng.random() < 0.45:
                            cx1, cy1 = stx + rng.randint(4, sub_w - 4), sty + rng.randint(4, sub_h - 4)
                            pygame.draw.line(surf, (9, 11, 14), (cx1, cy1), (cx1 + rng.randint(-8, 8), cy1 + rng.randint(-6, 6)), 1)
                # Đốm rêu phong xanh lục tối (mossy patches)
                for _ in range(4):
                    mx = tx + rng.randint(5, TILE - 6)
                    my = ty + rng.randint(5, TILE - 6)
                    pygame.draw.circle(surf, (22, 42, 28), (mx, my), rng.randint(2, 4))
                    pygame.draw.circle(surf, (32, 58, 38), (mx + 1, my), 1)

    elif biome_id == 1:
        # 2. Hầm Ngục Huyết Nguyệt (Blood Moon Dungeon): Dark obsidian floor tiles & glowing red summoning runes
        surf.fill((14, 7, 10))
        for ty in range(0, chunk_size, TILE):
            for tx in range(0, chunk_size, TILE):
                shade = rng.randint(-2, 3)
                base_c = (max(10, 20 + shade), max(5, 9 + shade), max(8, 14 + shade))
                pygame.draw.rect(surf, base_c, (tx + 2, ty + 2, TILE - 4, TILE - 4), border_radius=3)
                pygame.draw.rect(surf, (42, 14, 22), (tx, ty, TILE, TILE), 1)
                # Viền hắc diện thạch cắt chéo
                pygame.draw.rect(surf, (28, 11, 16), (tx + 5, ty + 5, TILE - 10, TILE - 10), 1)
                # Cổ ngữ triệu hồi đỏ rực ở các ô chẵn
                if ((tx // TILE + ty // TILE) % 2 == 0):
                    cx_t, cy_t = tx + TILE // 2, ty + TILE // 2
                    pygame.draw.circle(surf, (78, 18, 28), (cx_t, cy_t), 13, 1)
                    pygame.draw.polygon(surf, (96, 22, 34), [
                        (cx_t, cy_t - 10), (cx_t + 10, cy_t),
                        (cx_t, cy_t + 10), (cx_t - 10, cy_t)
                    ], 1)
                    pygame.draw.circle(surf, (130, 30, 45), (cx_t, cy_t), 3)
                # Mạch máu / vết nứt đỏ thẫm
                for _ in range(2):
                    px = tx + rng.randint(6, TILE - 6)
                    py = ty + rng.randint(6, TILE - 6)
                    pygame.draw.circle(surf, (65, 16, 24), (px, py), 2)

    else:
        # 3. Rừng Hư Không (Corrupted Abyss Forest): Dark purple-tinted grass & glowing abyssal veins
        surf.fill((13, 9, 22))
        for ty in range(0, chunk_size, TILE):
            for tx in range(0, chunk_size, TILE):
                shade = rng.randint(-3, 4)
                base_c = (max(8, 18 + shade), max(6, 12 + shade), max(16, 30 + shade))
                pygame.draw.rect(surf, base_c, (tx, ty, TILE, TILE))
                # Các cụm cỏ tím thẫm & rễ cây hư không
                for _ in range(7):
                    gx = tx + rng.randint(4, TILE - 5)
                    gy = ty + rng.randint(6, TILE - 5)
                    grass_c = (32 + rng.randint(0, 14), 18 + rng.randint(0, 10), 54 + rng.randint(0, 20))
                    pygame.draw.line(surf, grass_c, (gx, gy), (gx - 2, gy - 5), 1)
                    pygame.draw.line(surf, grass_c, (gx, gy), (gx + 2, gy - 4), 1)
                # Đốm bào tử & mạch tinh thể phát sáng mờ
                if rng.random() < 0.65:
                    sx_p = tx + rng.randint(8, TILE - 8)
                    sy_p = ty + rng.randint(8, TILE - 8)
                    pygame.draw.circle(surf, (55, 28, 95), (sx_p, sy_p), 3)
                    pygame.draw.circle(surf, (95, 50, 165), (sx_p, sy_p), 1)

    _TILE_CHUNK_CACHE[biome_id] = surf
    return surf


def draw_biome_props(surf: pygame.Surface, cam_x: float, cam_y: float,
                     biome_id: int, tick: int) -> None:
    """
    Vẽ các vật thể trang trí môi trường (Props) theo từng Quần Xã Dark Fantasy
    bằng băm không gian tất định (deterministic spatial hash) trên lưới 256x256:
      - Biome 0 (Nghĩa Địa Cổ Đại): Bia mộ cổ (tombstones), cây khô vặn xoắn (dead twisted trees), sương mù ma quái (eerie fog).
      - Biome 1 (Hầm Ngục Huyết Nguyệt): Vòng cổ ngữ triệu hồi đỏ, đống đầu lâu (skull piles), chậu lửa bập bùng (flickering torch braziers).
      - Biome 2 (Rừng Hư Không): Tinh thể nguyền rủa phát sáng (glowing cursed crystals), tàn tích cổ đại (ancient ruins), bào tử trôi nổi.
    """
    cell_size = 256
    biome_id = int(biome_id) % 3
    start_gx = int(cam_x // cell_size) - 1
    end_gx = int((cam_x + SCREEN_W) // cell_size) + 1
    start_gy = int(cam_y // cell_size) - 1
    end_gy = int((cam_y + SCREEN_H) // cell_size) + 1

    for gy in range(start_gy, end_gy + 1):
        for gx in range(start_gx, end_gx + 1):
            # Hash tất định cho mỗi ô (gx, gy)
            h = ((gx * 73856093) ^ (gy * 19349663) ^ (biome_id * 83492791)) & 0xFFFFFFFF
            if (h % 100) >= 68:
                continue  # Không phải ô nào cũng có prop để tránh rối mắt

            px_world = gx * cell_size + 48 + (h % (cell_size - 96))
            py_world = gy * cell_size + 48 + ((h >> 8) % (cell_size - 96))
            sx = int(px_world - cam_x)
            sy = int(py_world - cam_y)
            if sx < -60 or sx > SCREEN_W + 60 or sy < -60 or sy > SCREEN_H + 60:
                continue

            prop_kind = (h >> 16) % 2

            if biome_id == 0:
                if prop_kind == 0:
                    # Bia mộ cổ nứt vỡ + làn sương mù (Tombstone & eerie fog)
                    sh = get_drop_shadow(28, 10, 90)
                    surf.blit(sh, (sx - 14, sy + 8))
                    pygame.draw.rect(surf, (46, 52, 64), (sx - 10, sy - 14, 20, 24), border_radius=6)
                    pygame.draw.rect(surf, (70, 78, 92), (sx - 10, sy - 14, 20, 24), 2, border_radius=6)
                    # Chữ thập khắc trên bia mộ
                    pygame.draw.line(surf, (28, 32, 40), (sx, sy - 9), (sx, sy + 3), 2)
                    pygame.draw.line(surf, (28, 32, 40), (sx - 5, sy - 4), (sx + 5, sy - 4), 2)
                    # Sương mù nghĩa địa lượn lờ
                    fog_off = int(math.sin(tick * 0.03 + (h & 15)) * 6)
                    fog_s = get_drop_shadow(44, 14, 35)
                    surf.blit(fog_s, (sx - 22 + fog_off, sy + 4))
                else:
                    # Cây khô vặn xoắn (Dead twisted tree)
                    sh = get_drop_shadow(34, 12, 95)
                    surf.blit(sh, (sx - 17, sy + 12))
                    trunk_c = (38, 28, 24)
                    pygame.draw.line(surf, trunk_c, (sx, sy + 14), (sx - 2, sy - 8), 5)
                    pygame.draw.line(surf, trunk_c, (sx - 2, sy - 6), (sx - 14, sy - 20), 3)
                    pygame.draw.line(surf, trunk_c, (sx - 14, sy - 20), (sx - 20, sy - 26), 2)
                    pygame.draw.line(surf, trunk_c, (sx - 1, sy - 4), (sx + 13, sy - 18), 3)
                    pygame.draw.line(surf, trunk_c, (sx + 13, sy - 18), (sx + 18, sy - 25), 2)

            elif biome_id == 1:
                if prop_kind == 0:
                    # Chậu lửa Huyết Nguyệt bập bùng (Flickering torchlight brazier)
                    sh = get_drop_shadow(28, 12, 100)
                    surf.blit(sh, (sx - 14, sy + 8))
                    pygame.draw.polygon(surf, (45, 35, 42), [
                        (sx - 10, sy + 10), (sx + 10, sy + 10),
                        (sx + 7, sy - 2), (sx - 7, sy - 2)
                    ])
                    pygame.draw.ellipse(surf, (75, 25, 30), (sx - 11, sy - 6, 22, 8))
                    flick = int(math.sin(tick * 0.22 + (h & 31)) * 3)
                    # Ánh sáng lửa đỏ cam
                    glow_r = 22 + flick
                    glow_s = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
                    pygame.draw.circle(glow_s, (220, 45, 30, 38), (glow_r, glow_r), glow_r)
                    surf.blit(glow_s, (sx - glow_r, sy - 8 - glow_r))
                    pygame.draw.polygon(surf, (255, 90, 30), [
                        (sx - 6, sy - 3), (sx + 6, sy - 3), (sx + flick // 2, sy - 18 - abs(flick))
                    ])
                    pygame.draw.polygon(surf, (255, 210, 80), [
                        (sx - 3, sy - 3), (sx + 3, sy - 3), (sx, sy - 12 - abs(flick))
                    ])
                else:
                    # Đống đầu lâu & vòng cổ ngữ máu (Skull pile & blood rune)
                    pygame.draw.circle(surf, (110, 22, 35), (sx, sy + 2), 18, 1)
                    for ox, oy in [(-5, 3), (5, 3), (0, -3)]:
                        pygame.draw.circle(surf, (185, 175, 165), (sx + ox, sy + oy), 5)
                        pygame.draw.circle(surf, (30, 10, 15), (sx + ox - 2, sy + oy - 1), 1)
                        pygame.draw.circle(surf, (220, 30, 40), (sx + ox + 2, sy + oy - 1), 1)

            else:
                if prop_kind == 0:
                    # Tinh thể Hư Không phát sáng (Glowing cursed crystal)
                    sh = get_drop_shadow(28, 10, 95)
                    surf.blit(sh, (sx - 14, sy + 8))
                    pulse = int(35 + 20 * math.sin(tick * 0.08 + (h & 15)))
                    glow_s = pygame.Surface((44, 44), pygame.SRCALPHA)
                    pygame.draw.circle(glow_s, (165, 65, 255, pulse), (22, 22), 20)
                    surf.blit(glow_s, (sx - 22, sy - 24))
                    # 2 nhánh tinh thể tím-lam
                    pts_main = [(sx, sy - 20), (sx + 7, sy - 4), (sx + 4, sy + 10), (sx - 5, sy + 10), (sx - 7, sy - 4)]
                    pts_side = [(sx + 11, sy - 11), (sx + 14, sy + 2), (sx + 6, sy + 9), (sx + 4, sy - 2)]
                    pygame.draw.polygon(surf, (145, 55, 235), pts_main)
                    pygame.draw.polygon(surf, (215, 155, 255), pts_main, 1)
                    pygame.draw.polygon(surf, (110, 40, 195), pts_side)
                    pygame.draw.polygon(surf, (195, 130, 255), pts_side, 1)
                else:
                    # Trụ đá tàn tích cổ đại (Ancient ruin pillar)
                    sh = get_drop_shadow(30, 12, 95)
                    surf.blit(sh, (sx - 15, sy + 8))
                    pygame.draw.rect(surf, (44, 38, 58), (sx - 9, sy - 16, 18, 26), border_radius=3)
                    pygame.draw.rect(surf, (72, 62, 94), (sx - 11, sy - 18, 22, 6), border_radius=2)
                    pygame.draw.rect(surf, (72, 62, 94), (sx - 11, sy + 6, 22, 5), border_radius=2)
                    # Cổ ngữ phát sáng trên trụ đá
                    pygame.draw.line(surf, (175, 95, 255), (sx, sy - 9), (sx, sy + 2), 2)


def get_vignette_surface() -> pygame.Surface:
    """Tạo hiệu ứng tối viền màn hình (dark vignette) được cache sẵn."""
    global _VIGNETTE_CACHE
    if _VIGNETTE_CACHE is not None:
        return _VIGNETTE_CACHE
    surf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    cx, cy = SCREEN_W // 2, SCREEN_H // 2
    max_r = int(math.hypot(cx, cy))
    # Vẽ các vòng đồng tâm ở rìa màn hình để tạo hiệu ứng vignette mượt
    step = 18
    for r in range(int(max_r * 0.55), max_r + step, step):
        ratio = (r - max_r * 0.55) / max(1.0, (max_r * 0.45))
        alpha = int(clamp(ratio * ratio * 155, 0, 165))
        pygame.draw.circle(surf, (4, 3, 10, alpha), (cx, cy), r, step + 4)
    _VIGNETTE_CACHE = surf
    return surf

