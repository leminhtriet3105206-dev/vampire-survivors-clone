"""Core game configuration, constants, colors, definitions, and vector icon renderers."""
from dataclasses import dataclass
from enum import Enum, auto
import math
import os
import sys
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import pygame

# ---------------------------------------------------------------------------
# Platform & Dimensions
# ---------------------------------------------------------------------------
IS_EMSCRIPTEN = sys.platform == "emscripten"

SCREEN_W, SCREEN_H = 1280, 720
FPS = 60
TILE = 64
WORLD_W, WORLD_H = 4000, 4000

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
C_BG          = (12, 10, 18)
C_GRID        = (22, 20, 32)
C_PLAYER      = (120, 220, 255)
C_PLAYER_DARK = (60, 140, 180)
C_HP_BG       = (60, 20, 20)
C_HP          = (220, 60, 60)
C_XP_BG       = (20, 40, 20)
C_XP          = (80, 220, 100)
C_UI_BG       = (15, 14, 25, 200)
C_WHITE       = (255, 255, 255)
C_YELLOW      = (255, 230, 80)
C_ORANGE      = (255, 140, 40)
C_PURPLE      = (180, 80, 255)
C_CYAN        = (60, 230, 255)
C_RED         = (255, 60, 60)
C_GREEN       = (80, 220, 100)
C_BOOMERANG   = (100, 255, 180)
C_LIGHTNING   = (255, 245, 120)
C_ICE         = (150, 220, 255)

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class GameState(Enum):
    MENU       = auto()
    CAMPAIGN   = auto()
    SETTINGS   = auto()
    CHARACTERS = auto()
    SKIN_SHOP  = auto()
    LOBBY      = auto()
    PLAYING    = auto()


class AchievementID(Enum):
    FIRST_BLOOD     = auto()
    MONSTER_SLAYER  = auto()
    SURVIVOR        = auto()
    RICH            = auto()
    BOSS_HUNTER     = auto()
    TREASURE_SEEKER = auto()


class QuestType(Enum):
    KILL_COUNT     = auto()
    SURVIVE_TIME   = auto()
    COLLECT_GOLD   = auto()
    REACH_LEVEL    = auto()
    OPEN_CHESTS    = auto()
    DEFEAT_BOSS    = auto()


# ---------------------------------------------------------------------------
# Achievements
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class AchievementDef:
    id:    AchievementID
    icon:  str
    title: str
    desc:  str


ACHIEVEMENT_DEFS: List[AchievementDef] = [
    AchievementDef(AchievementID.FIRST_BLOOD,     "", "Chiến công đầu",   "Tiêu diệt kẻ địch đầu tiên"),
    AchievementDef(AchievementID.MONSTER_SLAYER,  "", "Thợ săn quái vật", "Tiêu diệt 100 kẻ địch"),
    AchievementDef(AchievementID.SURVIVOR,        "", "Kẻ sống sót",      "Sống sót trong 10 phút"),
    AchievementDef(AchievementID.RICH,            "", "Đại gia",          "Tích lũy 1000 vàng"),
    AchievementDef(AchievementID.BOSS_HUNTER,     "", "Thợ săn Boss",     "Tiêu diệt Boss đầu tiên"),
    AchievementDef(AchievementID.TREASURE_SEEKER, "", "Kẻ tìm kho báu",   "Mở 10 rương báu"),
]
_DEF_BY_ID: Dict[AchievementID, AchievementDef] = {d.id: d for d in ACHIEVEMENT_DEFS}

ACHIEVEMENT_TEXT_KEYS: Dict[AchievementID, Tuple[str, str]] = {
    AchievementID.FIRST_BLOOD:     ("ach_first_blood_title",     "ach_first_blood_desc"),
    AchievementID.MONSTER_SLAYER:  ("ach_monster_slayer_title",  "ach_monster_slayer_desc"),
    AchievementID.SURVIVOR:        ("ach_survivor_title",        "ach_survivor_desc"),
    AchievementID.RICH:            ("ach_rich_title",            "ach_rich_desc"),
    AchievementID.BOSS_HUNTER:     ("ach_boss_hunter_title",     "ach_boss_hunter_desc"),
    AchievementID.TREASURE_SEEKER: ("ach_treasure_seeker_title", "ach_treasure_seeker_desc"),
}

# ---------------------------------------------------------------------------
# Character Definitions
# ---------------------------------------------------------------------------
CHARACTER_DEFS = [
    {
        "id":    "warrior",
        "name":  "Huyết Kiếm Sĩ",
        "desc":  "+60 Máu, +2 Giáp | Khởi đầu: Trảm Huyết Nguyệt",
        "cost":  0,
        "color": (235, 50, 70),
        "mods":  {
            "max_hp": 60,
            "armor": 2,
            "whip_level": 1,
            "lifesteal_on_kill": 3,
            "damage_mult": 0.10,
        },
        "stats_bars": [("HP", 0.90), ("ST", 0.85), ("TỐC", 0.60)],
    },
    {
        "id":    "mage",
        "name":  "Pháp Sư Tinh Vân",
        "desc":  "-20% Hồi chiêu | Khởi đầu: Hố Đen Hư Không",
        "cost":  150,
        "color": (185, 85, 255),
        "mods":  {
            "void_level": 1,
            "cdr": 0.20,
            "damage_mult": 0.15,
        },
        "stats_bars": [("HP", 0.55), ("ST", 0.95), ("CDR", 0.90)],
    },
    {
        "id":    "rogue",
        "name":  "Thợ Săn Bóng Đêm",
        "desc":  "+25% Tốc độ, 30% Chí mạng | Khởi đầu: Mưa Tên Độc Ảnh",
        "cost":  200,
        "color": (45, 245, 175),
        "mods":  {
            "speed_mult": 0.25,
            "crit_chance": 0.30,
            "bonus_pierce": 2,
            "arrow_level": 1,
        },
        "stats_bars": [("HP", 0.60), ("CRIT", 0.95), ("TỐC", 0.95)],
    },
    {
        "id":    "paladin",
        "name":  "Thánh Kỵ Sĩ",
        "desc":  "+80 Máu, +4 Giáp, +2 Hồi phục | Khởi đầu: Phán Quyết Ánh Sáng",
        "cost":  300,
        "color": (255, 215, 75),
        "mods":  {
            "max_hp": 80,
            "armor": 4,
            "recovery": 2,
            "hammer_level": 1,
        },
        "stats_bars": [("HP", 1.00), ("GIÁP", 0.95), ("HỒI", 0.90)],
    },
    {
        "id":    "necromancer",
        "name":  "Tử Linh Pháp Sư",
        "desc":  "+40 Máu, +20% Sát thương, +1 Xuyên | Khởi đầu: Triệu Hồi Cốt Binh",
        "cost":  350,
        "color": (40, 220, 180),
        "mods":  {
            "max_hp": 40,
            "damage_mult": 0.20,
            "bonus_pierce": 1,
            "skeletal_level": 1,
        },
        "stats_bars": [("HP", 0.70), ("ST", 0.95), ("XUYÊN", 0.90)],
    },
    {
        "id":    "dragon_lancer",
        "name":  "Long Chiến Binh",
        "desc":  "+70 Máu, +3 Giáp, +15% Tốc độ | Khởi đầu: Long Viêm Xung Kích",
        "cost":  450,
        "color": (255, 95, 45),
        "mods":  {
            "max_hp": 70,
            "armor": 3,
            "speed_mult": 0.15,
            "damage_mult": 0.15,
            "dragon_level": 1,
        },
        "stats_bars": [("HP", 0.95), ("GIÁP", 0.85), ("TỐC", 0.80)],
    },
]

# ---------------------------------------------------------------------------
# Anime Skins
# ---------------------------------------------------------------------------
ANIME_SKINS = [
    {
        "id": "saiyan",
        "name": "Chiến Binh Siêu Saiyan",
        "anime_tag": "Dragon Ball — Goku / Super Saiyan",
        "desc": "Tóc vàng dựng đứng rực cháy, võ phục cam-xanh Quy Tiên Nhân, Cân Đẩu Vân và luồng Ki hoàng kim bùng nổ.",
        "vfx_desc": "VFX: Chưởng Ki Xanh Lam (Kamehameha) & Hào Quang Vàng Rực",
        "cost": 250,
        "color": (255, 215, 40),
        "primary": (255, 215, 40),
        "secondary": (45, 215, 255),
        "vfx_primary": (255, 215, 40),
        "vfx_secondary": (45, 215, 255),
        "core": (255, 255, 225),
    },
    {
        "id": "naruto",
        "name": "Ninja Làng Lá - Cửu Vĩ",
        "anime_tag": "Naruto — Lục Đạo / Kurama Mode",
        "desc": "Băng trán Làng Lá, áo choàng Chakra Cửu Vĩ cam hoàng kim khắc ấn Magatama và 6 Hắc Cầu Đạo Ngọc lơ lửng.",
        "vfx_desc": "VFX: Phong Độn Rasenshuriken & Áo Choàng Chakra Cửu Vĩ",
        "cost": 300,
        "color": (255, 145, 25),
        "primary": (255, 145, 25),
        "secondary": (105, 240, 255),
        "vfx_primary": (255, 145, 25),
        "vfx_secondary": (105, 240, 255),
        "core": (255, 240, 165),
    },
    {
        "id": "gojo",
        "name": "Chú Thuật Sư Vô Hạ Hạn",
        "anime_tag": "Jujutsu Kaisen — Gojo Satoru / Lục Nhãn",
        "desc": "Tóc trắng dựng, băng bịt mắt đen lộ tia sáng Lục Nhãn xanh neon và hào quang không gian Vô Lượng Không Xứ.",
        "vfx_desc": "VFX: Chú Lực Thương (Xanh) - Hách (Đỏ) - Tử (Tím Hư Không)",
        "cost": 400,
        "color": (185, 70, 255),
        "primary": (185, 70, 255),
        "secondary": (45, 210, 255),
        "vfx_primary": (185, 70, 255),
        "vfx_secondary": (45, 210, 255),
        "core": (255, 55, 105),
    },
    {
        "id": "luffy",
        "name": "Vua Hải Tặc Thần Mặt Trời",
        "anime_tag": "One Piece — Luffy Gear 5 / Haki Bá Vương",
        "desc": "Mũ Rơm đeo sau lưng, tóc trắng phát sáng và dải mây thần Nika uốn lượn quanh vai cùng tia sét Haki Bá Vương.",
        "vfx_desc": "VFX: Sét Đen-Đỏ Haki Bá Vương & Mây Trắng Thần Nika",
        "cost": 450,
        "color": (245, 240, 255),
        "primary": (245, 240, 255),
        "secondary": (255, 30, 65),
        "vfx_primary": (245, 240, 255),
        "vfx_secondary": (255, 30, 65),
        "core": (255, 215, 85),
    },
]

ANIME_SKIN_BY_ID = {s["id"]: s for s in ANIME_SKINS}


def get_skin_cost(sdef: dict) -> int:
    """Safe cost extraction."""
    raw = sdef.get("cost", sdef.get("price", 0))
    try:
        return max(0, int(raw))
    except (ValueError, TypeError):
        return 0


# ---------------------------------------------------------------------------
# Permanent Upgrades
# ---------------------------------------------------------------------------
PERM_UPGRADE_DEFS = [
    ("hp",   "perm_hp",   80,  5),
    ("dmg",  "perm_dmg",  100, 5),
    ("spd",  "perm_spd",  90,  5),
    ("gold", "perm_gold", 100, 5),
]

# ---------------------------------------------------------------------------
# Class Perks & Combat Consumables (Lobby System)
# ---------------------------------------------------------------------------
CLASS_PERKS_DEF = {
    "warrior": [
        {"id": "cuong_huyet", "name": "Cuồng Huyết", "desc": "+25% sát thương khi HP dưới 50%", "cost": 100},
        {"id": "kiem_khi_rong", "name": "Kiếm Khí Rộng", "desc": "+30% phạm vi Trảm Huyết Nguyệt", "cost": 100},
        {"id": "bat_khuat", "name": "Bất Khuất", "desc": "+4 Giáp & +1 HP/giây hồi phục", "cost": 100},
    ],
    "mage": [
        {"id": "hu_khong_rong", "name": "Hư Không Bành Trướng", "desc": "+30% phạm vi Hố Đen Hư Không", "cost": 100},
        {"id": "thoi_gian_gian_no", "name": "Thời Gian Giãn Nở", "desc": "+1.5s duy trì hố đen", "cost": 100},
        {"id": "khai_phong_tinh_van", "name": "Khai Phóng Tinh Vân", "desc": "+15% tốc chạy & +10% hồi chiêu", "cost": 100},
    ],
    "rogue": [
        {"id": "am_bo_than_toc", "name": "Ám Bộ Thần Tốc", "desc": "+20% tốc độ chạy & +15% chí mạng", "cost": 100},
        {"id": "mua_ten_doc_hoan", "name": "Mưa Tên Độc Hoàn", "desc": "Mưa tên độc nảy thêm +2 lần", "cost": 100},
        {"id": "bay_hac_am", "name": "Bẫy Hắc Ám", "desc": "Bẫy bóng đêm gây thêm +40% sát thương", "cost": 100},
    ],
    "paladin": [
        {"id": "thanh_quang_ho_the", "name": "Thánh Quang Hộ Thể", "desc": "+60 Máu tối đa & hồi đầy máu", "cost": 100},
        {"id": "thien_phat_sam_set", "name": "Thiên Phạt Sấm Sét", "desc": "Búa thánh giáng thêm 1 cột sáng", "cost": 100},
        {"id": "khien_than_bat_hoai", "name": "Khiên Thần Bất Hoại", "desc": "+6 Giáp & kháng đẩy lùi", "cost": 100},
    ],
    "necromancer": [
        {"id": "bat_hon_doat_menh", "name": "Bạt Hồn Đoạt Mệnh", "desc": "+30% tốc độ di chuyển Cốt Binh", "cost": 100},
        {"id": "hon_no_lien_hoan", "name": "Hồn Nổ Liên Hoàn", "desc": "Bán kính tia hồn nổ +40%", "cost": 100},
        {"id": "quan_doan_bat_diet", "name": "Quân Đoàn Bất Diệt", "desc": "Tối đa triệu hồi thêm +2 cốt binh", "cost": 100},
    ],
    "dragon_lancer": [
        {"id": "no_long_xuat_the", "name": "Nộ Long Xuất Thế", "desc": "+25% sát thương đâm thương lửa", "cost": 100},
        {"id": "dung_nham_soi_trao", "name": "Dung Nham Sôi Trào", "desc": "Nham thạch tồn tại thêm +50% thời gian", "cost": 100},
        {"id": "long_lan_ho_the", "name": "Long Lân Hộ Thể", "desc": "Giảm 15% sát thương nhận vào & phản đòn", "cost": 100},
    ],
}

CONSUMABLES_DEF = [
    {"id": "potion_hp",     "slot": "1", "name": "Bình Máu",         "cost": 30, "desc": "Hồi +80 HP ngay lập tức",        "color": (50, 225, 90)},
    {"id": "potion_dmg",    "slot": "2", "name": "Thuốc Cuồng Nộ",    "cost": 40, "desc": "+50% Sát thương trong 10s",     "color": (255, 60, 60)},
    {"id": "potion_spd",    "slot": "3", "name": "Thuốc Thần Tốc",    "cost": 30, "desc": "+60% Tốc độ chạy trong 8s",     "color": (60, 215, 255)},
    {"id": "potion_armor",  "slot": "4", "name": "Thuốc Thiết Giáp",  "cost": 50, "desc": "Bất tử & +25 Giáp trong 6s",    "color": (255, 215, 70)},
    {"id": "potion_magnet", "slot": "5", "name": "Cuộn Hút Ngọc",     "cost": 60, "desc": "Hút toàn bộ Ngọc XP & Vàng",    "color": (210, 80, 255)},
]

# ---------------------------------------------------------------------------
# Typography & Cached Fonts
# ---------------------------------------------------------------------------
FONT_NAMES = "segoeui,arial,tahoma,verdana,calibri,timesnewroman,dejavusans"
_FONT_CACHE: Dict[Tuple[str, int, bool, bool], pygame.font.Font] = {}


def get_vn_font(size: int, bold: bool = False, italic: bool = False) -> pygame.font.Font:
    """Load high-legibility Unicode font with caching."""
    if not pygame.font.get_init():
        pygame.font.init()

    key = ("vn", size, bold, italic)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]

    vn_candidates = ["segoeui", "segoe ui", "arial", "tahoma", "verdana", "calibri", "dejavusans", "timesnewroman"]
    f = None
    for fname in vn_candidates:
        try:
            f = pygame.font.SysFont(fname, size, bold=bold, italic=italic)
            if f is not None:
                break
        except Exception:
            continue
    if f is None:
        f = pygame.font.SysFont(FONT_NAMES, size, bold=bold, italic=italic)

    _FONT_CACHE[key] = f
    return f

get_sys_font = get_vn_font


def draw_wrapped_text(
    surf: pygame.Surface,
    text: str,
    font: pygame.font.Font,
    color: Union[Tuple[int, int, int], Tuple[int, int, int, int]],
    rect: pygame.Rect,
    align: str = "center",
    line_spacing: int = 4,
    max_lines: int = 0,
) -> int:
    """Draw word-wrapped text within bounding rectangle with clipping protection."""
    if not text:
        return 0
    words = text.split(" ")
    lines: List[str] = []
    cur_words: List[str] = []

    for word in words:
        if not word:
            continue
        test_line = " ".join(cur_words + [word])
        w, _ = font.size(test_line)
        if w <= rect.width or not cur_words:
            cur_words.append(word)
        else:
            lines.append(" ".join(cur_words))
            cur_words = [word]
    if cur_words:
        lines.append(" ".join(cur_words))

    if max_lines > 0 and len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and font.size(last + "...")[0] > rect.width:
            last = last[:-1]
        lines[-1] = (last.rstrip() + "...") if last else "..."

    line_h = font.get_linesize()
    total_h = len(lines) * line_h + max(0, len(lines) - 1) * line_spacing
    cur_y = rect.y

    for line in lines:
        if cur_y + line_h > rect.bottom and max_lines == 0:
            break
        txt_s = font.render(line, True, color)
        if align == "center":
            tx = rect.centerx - txt_s.get_width() // 2
        elif align == "right":
            tx = rect.right - txt_s.get_width()
        else:
            tx = rect.left
        surf.blit(txt_s, (tx, cur_y))
        cur_y += line_h + line_spacing

    return total_h


# ---------------------------------------------------------------------------
# Procedural Vector Icons (Zero image loading, perfect 60 FPS scaling)
# ---------------------------------------------------------------------------
def draw_icon_heart(surf: pygame.Surface, x: int, y: int, size: int = 14, color: tuple = (255, 60, 80)):
    s = max(8, size)
    r = s // 4
    pygame.draw.circle(surf, color, (x + r, y + r), r)
    pygame.draw.circle(surf, color, (x + s - r, y + r), r)
    pts = [(x, y + r), (x + s, y + r), (x + s // 2, y + s)]
    pygame.draw.polygon(surf, color, pts)


def draw_icon_sword(surf: pygame.Surface, x: int, y: int, size: int = 14, color: tuple = (255, 215, 80)):
    s = max(8, size)
    pygame.draw.line(surf, (245, 245, 255), (x + 3, y + s - 3), (x + s - 3, y + 3), 3)
    pygame.draw.line(surf, color, (x + 2, y + s - 6), (x + 6, y + s - 2), 2)
    pygame.draw.circle(surf, color, (x + 2, y + s - 2), 2)


def draw_icon_shield(surf: pygame.Surface, x: int, y: int, size: int = 14, color: tuple = (100, 190, 255)):
    s = max(8, size)
    pts = [
        (x + 2, y + 2),
        (x + s - 2, y + 2),
        (x + s - 2, y + s // 2),
        (x + s // 2, y + s - 1),
        (x + 2, y + s // 2),
    ]
    pygame.draw.polygon(surf, color, pts)
    pygame.draw.polygon(surf, (255, 255, 255), pts, 1)


def draw_icon_coin(surf: pygame.Surface, x: int, y: int, size: int = 14):
    r = max(4, size // 2)
    cx, cy = x + r, y + r
    pygame.draw.circle(surf, (255, 210, 45), (cx, cy), r)
    pygame.draw.circle(surf, (255, 245, 160), (cx, cy), r, 1)
    pygame.draw.circle(surf, (220, 165, 25), (cx, cy), max(2, r - 3))


def draw_icon_magnet(surf: pygame.Surface, x: int, y: int, size: int = 14):
    s = max(10, size)
    arc_rect = pygame.Rect(x + 2, y + 2, s - 4, s - 4)
    pygame.draw.arc(surf, (255, 50, 60), arc_rect, 0, math.pi, 3)
    pygame.draw.line(surf, (255, 50, 60), (arc_rect.left + 1, arc_rect.centery), (arc_rect.left + 1, arc_rect.bottom), 3)
    pygame.draw.line(surf, (60, 140, 255), (arc_rect.right - 2, arc_rect.centery), (arc_rect.right - 2, arc_rect.bottom), 3)


def draw_icon_star(surf: pygame.Surface, x: int, y: int, size: int = 14, color: tuple = (255, 220, 60)):
    s = max(8, size)
    cx, cy = x + s // 2, y + s // 2
    r_outer = s // 2
    r_inner = r_outer * 0.45
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * (math.pi / 5)
        rad = r_outer if i % 2 == 0 else r_inner
        pts.append((cx + int(math.cos(ang) * rad), cy + int(math.sin(ang) * rad)))
    pygame.draw.polygon(surf, color, pts)


def draw_icon_skull(surf: pygame.Surface, x: int, y: int, size: int = 14, color: tuple = (255, 80, 80)):
    s = max(8, size)
    cx, cy = x + s // 2, y + s // 2 - 1
    r = s // 3 + 1
    pygame.draw.circle(surf, color, (cx, cy), r)
    pygame.draw.rect(surf, color, (cx - r + 2, cy + 2, (r - 2) * 2, 4))
    pygame.draw.circle(surf, (15, 10, 20), (cx - 2, cy), 1)
    pygame.draw.circle(surf, (15, 10, 20), (cx + 2, cy), 1)

