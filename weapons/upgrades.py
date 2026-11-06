"""Skill upgrade definitions, tier scaling, and synergy fusion recipes."""
from enum import Enum, auto
from typing import Any, Dict, Optional, Tuple

from core.config import (
    C_CYAN,
    C_GREEN,
    C_ICE,
    C_LIGHTNING,
    C_PURPLE,
    C_RED,
    C_WHITE,
    C_YELLOW,
)
from core.i18n import LANG, STRINGS, T

class UpgradeType(Enum):
    MAX_HP                  = auto()
    SPEED                   = auto()
    WHIP                    = auto()  # Trảm Huyết Nguyệt
    VOID_SINGULARITY        = auto()  # Hố Đen Hư Không
    PHANTOM_ARROW           = auto()  # Mưa Tên Độc Ảnh
    JUDGEMENT_HAMMER        = auto()  # Phán Quyết Ánh Sáng
    ORB                     = auto()  # Khiên Tinh Cầu
    AURA                    = auto()  # Trường Lực Thánh
    BOOMERANG               = auto()  # Lưỡi Hái Tử Thần
    LIGHTNING_STAFF         = auto()  # Bão Sấm Sét
    ICE_WAND                = auto()  # Tên Lửa Tinh Vân
    FIRE_TRAIL              = auto()  # Vệt Lửa Địa Ngục
    FAMILIAR                = auto()  # Tinh Linh Hộ Vệ
    SKELETAL_LEGION         = auto()  # Triệu Hồi Cốt Binh (Necromancer Lord)
    DRAGONFIRE_THRUST       = auto()  # Long Viêm Xung Kích (Dragonblood Lancer)
    RECOVERY                = auto()
    ARMOR                   = auto()
    # 4 Kỹ năng Hợp Nhất Thần Thoại (Mythic Fusions)
    FUSION_BLOOD_DOMAIN     = auto()  # Trảm Huyết Nguyệt + Trường Lực Thánh
    FUSION_COSMIC_TEMPEST   = auto()  # Hố Đen Hư Không + Bão Sấm Sét
    FUSION_REAPER_HURRICANE = auto()  # Mưa Tên Độc Ảnh + Lưỡi Hái Tử Thần
    FUSION_SOLAR_APOCALYPSE = auto()  # Phán Quyết Ánh Sáng + Vệt Lửa Địa Ngục

FUSION_TYPES = {
    UpgradeType.FUSION_BLOOD_DOMAIN,
    UpgradeType.FUSION_COSMIC_TEMPEST,
    UpgradeType.FUSION_REAPER_HURRICANE,
    UpgradeType.FUSION_SOLAR_APOCALYPSE,
}

# Danh sách công thức Hợp Nhất: (Kỹ năng A, Kỹ năng B) -> Kỹ năng Hợp Nhất
FUSION_RECIPES = [
    (UpgradeType.WHIP,             UpgradeType.AURA,            UpgradeType.FUSION_BLOOD_DOMAIN),
    (UpgradeType.VOID_SINGULARITY, UpgradeType.LIGHTNING_STAFF, UpgradeType.FUSION_COSMIC_TEMPEST),
    (UpgradeType.PHANTOM_ARROW,    UpgradeType.BOOMERANG,       UpgradeType.FUSION_REAPER_HURRICANE),
    (UpgradeType.JUDGEMENT_HAMMER, UpgradeType.FIRE_TRAIL,      UpgradeType.FUSION_SOLAR_APOCALYPSE),
]

UPGRADE_COLORS = {
    UpgradeType.MAX_HP:                  C_RED,
    UpgradeType.SPEED:                   C_YELLOW,
    UpgradeType.WHIP:                    (255, 65, 85),
    UpgradeType.VOID_SINGULARITY:        (185, 85, 255),
    UpgradeType.PHANTOM_ARROW:           (50, 255, 175),
    UpgradeType.JUDGEMENT_HAMMER:        (255, 215, 70),
    UpgradeType.ORB:                     C_CYAN,
    UpgradeType.AURA:                    C_PURPLE,
    UpgradeType.BOOMERANG:               C_CYAN,
    UpgradeType.LIGHTNING_STAFF:         C_LIGHTNING,
    UpgradeType.ICE_WAND:                C_ICE,
    UpgradeType.FIRE_TRAIL:              (255, 110, 40),
    UpgradeType.FAMILIAR:                (140, 235, 255),
    UpgradeType.SKELETAL_LEGION:         (50, 240, 195),
    UpgradeType.DRAGONFIRE_THRUST:       (255, 115, 45),
    UpgradeType.RECOVERY:                C_GREEN,
    UpgradeType.ARMOR:                   C_WHITE,
    UpgradeType.FUSION_BLOOD_DOMAIN:     (255, 50, 80),
    UpgradeType.FUSION_COSMIC_TEMPEST:   (210, 120, 255),
    UpgradeType.FUSION_REAPER_HURRICANE: (65, 255, 185),
    UpgradeType.FUSION_SOLAR_APOCALYPSE: (255, 215, 60),
}

UPGRADE_KEYS = {ut: ut.name for ut in UpgradeType}

def get_upgrade_def(ut):
    key   = UPGRADE_KEYS[ut]
    name  = STRINGS[LANG]["upgrade_names"].get(key, key)
    desc  = STRINGS[LANG]["upgrade_descs"].get(key, key)
    color = UPGRADE_COLORS.get(ut, C_YELLOW)
    return name, desc, color

def get_recipe_hint(ut: UpgradeType) -> str:
    """Trả về dòng gợi ý công thức Hợp Nhất cho kỹ năng trên thẻ Level-Up (không dùng Unicode lỗi font)."""
    names = STRINGS[LANG]["upgrade_names"]
    for a, b, fus in FUSION_RECIPES:
        if ut == a:
            return f"[+] Hợp nhất: {names[b.name]} Lv5 -> {names[fus.name]}"
        if ut == b:
            return f"[+] Hợp nhất: {names[a.name]} Lv5 -> {names[fus.name]}"
        if ut == fus:
            return f"[HỢP NHẤT] {names[a.name]} Lv5 + {names[b.name]} Lv5"
    return ""

