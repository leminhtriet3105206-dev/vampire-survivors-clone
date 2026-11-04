# -*- coding: utf-8 -*-
"""
Vampire Survivors Clone - Python / Pygame (Bản Tiếng Việt)
==========================================================
Điều khiển:
  WASD / Phím mũi tên  -> di chuyển
  ESC                  -> thoát / menu chính
  P                    -> tạm dừng
  L                    -> đổi ngôn ngữ
  M                    -> bật / tắt âm thanh

Tính năng:
  - Hệ thống vũ khí tự động tấn công (roi, cầu phép, hào quang, boomerang, gậy sét, đũa băng)
  - Hệ thống quái xuất hiện theo đợt (wave), tăng dần độ khó
  - Hệ thống XP, thăng cấp và chọn lựa nâng cấp kỹ năng
  - Thanh máu, thanh kinh nghiệm, đồng hồ thời gian
  - Hiệu ứng hạt (particle) và số sát thương nhảy nổi
  - Nhiều loại quái vật và Boss kịch tính
"""

import pygame
import math
import random
import sys
import os
import json
import array
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from enum import Enum, auto
import audio_settings

SAVE_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "save_data.json")

# ---------------------------------------------------------------------------
# Cấu hình Font hệ thống hỗ trợ tiếng Việt (Windows / macOS / Linux)
# ---------------------------------------------------------------------------
FONT_NAMES = "segoeui,arial,tahoma,timesnewroman,dejavusans"

def get_sys_font(size: int, bold: bool = False, italic: bool = False) -> pygame.font.Font:
    """Khởi tạo font hệ thống hỗ trợ tiếng Việt có dấu mượt mà, tránh lỗi ô vuông ký tự."""
    if not pygame.font.get_init():
        pygame.font.init()
    return pygame.font.SysFont(FONT_NAMES, size, bold=bold, italic=italic)

# ---------------------------------------------------------------------------
# Başarım sistemi
# ---------------------------------------------------------------------------
TOAST_W        = 300
TOAST_H        = 60
TOAST_DURATION = 210
TOAST_SLIDE    = 18
TOAST_FADE     = 30
TOAST_PAD_R    = 16
TOAST_PAD_B    = 70

class AchievementID(Enum):
    FIRST_BLOOD     = auto()
    MONSTER_SLAYER  = auto()
    SURVIVOR        = auto()
    RICH            = auto()
    BOSS_HUNTER     = auto()
    TREASURE_SEEKER = auto()


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
_DEF_BY_ID: dict = {d.id: d for d in ACHIEVEMENT_DEFS}

# Toast metni T() ile çözülür; tanım içindeki title/desc yalnızca yedek değerdir.
ACHIEVEMENT_TEXT_KEYS: dict = {
    AchievementID.FIRST_BLOOD:     ("ach_first_blood_title",     "ach_first_blood_desc"),
    AchievementID.MONSTER_SLAYER:  ("ach_monster_slayer_title",  "ach_monster_slayer_desc"),
    AchievementID.SURVIVOR:        ("ach_survivor_title",        "ach_survivor_desc"),
    AchievementID.RICH:            ("ach_rich_title",            "ach_rich_desc"),
    AchievementID.BOSS_HUNTER:     ("ach_boss_hunter_title",     "ach_boss_hunter_desc"),
    AchievementID.TREASURE_SEEKER: ("ach_treasure_seeker_title", "ach_treasure_seeker_desc"),
}


@dataclass
class _Toast:
    ach_id: AchievementID
    timer:  int = TOAST_DURATION

    @property
    def slide_offset(self) -> float:
        frames_elapsed = TOAST_DURATION - self.timer
        if frames_elapsed < TOAST_SLIDE:
            return TOAST_W * (1.0 - frames_elapsed / TOAST_SLIDE)
        return 0.0

    @property
    def alpha(self) -> int:
        if self.timer < TOAST_FADE:
            return int(255 * self.timer / TOAST_FADE)
        return 255

    def update(self) -> bool:
        self.timer -= 1
        return self.timer > 0


class AchievementManager:
    def __init__(self, save, sfx=None) -> None:
        self._save   = save
        self._sfx    = sfx
        self._queue: List[_Toast]      = []
        self._active: Optional[_Toast] = None
        self._f_label = None
        self._f_title = None
        self._f_desc  = None

    def notify_kill(self, total_kills: int) -> None:
        if total_kills >= 1:
            self._unlock(AchievementID.FIRST_BLOOD)
        if total_kills >= 100:
            self._unlock(AchievementID.MONSTER_SLAYER)

    def notify_boss_kill(self) -> None:
        self._unlock(AchievementID.BOSS_HUNTER)

    def notify_chest_open(self) -> None:
        self._save.chest_opens += 1
        if self._save.chest_opens >= 10:
            self._unlock(AchievementID.TREASURE_SEEKER)

    def notify_time(self, elapsed_secs: int) -> None:
        if elapsed_secs >= 600:
            self._unlock(AchievementID.SURVIVOR)

    def notify_gold(self, session_gold: int) -> None:
        if self._save.total_gold + self._save.lifetime_gold + session_gold >= 1000:
            self._unlock(AchievementID.RICH)

    def _unlock(self, aid: AchievementID) -> None:
        if aid in self._save.unlocked_achievements:
            return
        self._save.unlocked_achievements.add(aid)
        self._queue.append(_Toast(ach_id=aid))
        if self._sfx is not None:
            self._sfx.play_achievement()

    def _tick_queue(self) -> None:
        if self._active is not None:
            if not self._active.update():
                self._active = None
        if self._active is None and self._queue:
            self._active = self._queue.pop(0)

    def draw(self, surf, screen_w: int, screen_h: int) -> None:
        self._tick_queue()
        if self._active is None:
            return
        if self._f_label is None:
            self._f_label = get_sys_font(12)
            self._f_title = get_sys_font(15, bold=True)
            self._f_desc  = get_sys_font(13)
        toast = self._active
        defn  = _DEF_BY_ID[toast.ach_id]
        alpha = toast.alpha
        tx = int(screen_w - TOAST_W - TOAST_PAD_R + toast.slide_offset)
        ty = screen_h - TOAST_H - TOAST_PAD_B
        bg = pygame.Surface((TOAST_W, TOAST_H), pygame.SRCALPHA)
        bg.fill((18, 14, 35, int(220 * alpha / 255)))
        surf.blit(bg, (tx, ty))
        border = pygame.Surface((TOAST_W, TOAST_H), pygame.SRCALPHA)
        border.set_alpha(alpha)
        pygame.draw.rect(border, (200, 170, 50), (0, 0, TOAST_W, TOAST_H), 2, border_radius=6)
        surf.blit(border, (tx, ty))
        strip = pygame.Surface((4, TOAST_H - 4), pygame.SRCALPHA)
        strip.fill((220, 190, 60, alpha))
        surf.blit(strip, (tx + 2, ty + 2))
        text_x = tx + 14
        label_s = self._f_label.render(T("ach_unlocked"), True, (200, 170, 50))
        label_s.set_alpha(alpha)
        surf.blit(label_s, (text_x, ty + 7))
        title_key, desc_key = ACHIEVEMENT_TEXT_KEYS[defn.id]
        name  = T(title_key)
        title = f"{defn.icon}  {name}" if defn.icon else name
        title_s = self._f_title.render(title, True, (240, 235, 255))
        title_s.set_alpha(alpha)
        surf.blit(title_s, (text_x, ty + 22))
        desc_s = self._f_desc.render(T(desc_key), True, (160, 155, 195))
        desc_s.set_alpha(alpha)
        surf.blit(desc_s, (text_x, ty + 40))

    def all_statuses(self) -> List[tuple]:
        return [(defn, defn.id in self._save.unlocked_achievements) for defn in ACHIEVEMENT_DEFS]

# ---------------------------------------------------------------------------
# Görev sistemi
# ---------------------------------------------------------------------------
class QuestType(Enum):
    KILL    = auto()
    SURVIVE = auto()
    GOLD    = auto()


@dataclass
class Quest:
    qtype:    QuestType
    target:   int
    reward:   int
    progress: int  = 0
    done:     bool = False
    notified: bool = False

    def advance(self, amount: int = 1):
        if self.done:
            return False
        self.progress = min(self.target, self.progress + amount)
        if self.progress >= self.target:
            self.done = True
            return True
        return False

    def label(self) -> str:
        if self.qtype == QuestType.KILL:
            return T("quest_kill", n=self.target)
        elif self.qtype == QuestType.SURVIVE:
            return T("quest_survive", n=self.target)
        else:
            return T("quest_gold", n=self.target)

    def progress_str(self) -> str:
        return f"{min(self.progress, self.target)}/{self.target}"


def draw_collapse_arrow(surf, rect, collapsed, hovered=False):
    """Panel başlığındaki aç/kapa oku: kapalıyken sağa, açıkken aşağı bakar."""
    cx, cy = rect.center
    color  = (230, 220, 255) if hovered else (180, 160, 255)
    if collapsed:
        pts = [(cx - 3, cy - 5), (cx - 3, cy + 5), (cx + 4, cy)]
    else:
        pts = [(cx - 5, cy - 3), (cx + 5, cy - 3), (cx, cy + 4)]
    pygame.draw.polygon(surf, color, pts)


class QuestManager:
    MAX_ACTIVE      = 4
    UNLOCK_INTERVAL = 120
    PANEL_X         = 16
    PANEL_W         = 230
    NOTIF_DURATION  = 180

    def __init__(self):
        self.quests:       List[Quest] = []
        self.completed:    List[Quest] = []
        self.pending_pool: List[Quest] = []
        self.next_unlock_tick = self.UNLOCK_INTERVAL * 60
        self.notif_queue:     List[list] = []
        self.new_quest_notif: List[list] = []
        self._font_title = None
        self._font_item  = None
        self._font_prog  = None
        self.collapsed   = False                 # panel içeriği gizli mi
        self.toggle_rect: Optional[pygame.Rect] = None
        self._build_initial()

    def _make_quest(self, qtype: QuestType, tier: int) -> Quest:
        if qtype == QuestType.KILL:
            targets = [20,  50,  100, 200]
            rewards = [30,  60,  100, 180]
        elif qtype == QuestType.SURVIVE:
            targets = [2,   4,   7,   12]
            rewards = [25,  55,  90,  160]
        else:
            targets = [50,  120, 250, 500]
            rewards = [35,  70,  110, 200]
        t = max(0, min(3, tier))
        return Quest(qtype=qtype, target=targets[t], reward=rewards[t])

    def _build_initial(self):
        types = [QuestType.KILL, QuestType.SURVIVE, QuestType.GOLD]
        random.shuffle(types)
        for qt in types:
            self.quests.append(self._make_quest(qt, tier=0))
        pool_defs = [
            (QuestType.KILL,    1), (QuestType.SURVIVE, 1), (QuestType.GOLD,    1),
            (QuestType.KILL,    2), (QuestType.SURVIVE, 2), (QuestType.GOLD,    2),
            (QuestType.KILL,    3), (QuestType.SURVIVE, 3), (QuestType.GOLD,    3),
        ]
        random.shuffle(pool_defs)
        for qt, tier in pool_defs:
            self.pending_pool.append(self._make_quest(qt, tier))

    def update(self, tick: int, kills_delta: int, gold_delta: int, elapsed_secs: int):
        newly_done: List[Quest] = []
        for q in self.quests:
            if q.done:
                continue
            if q.qtype == QuestType.KILL and kills_delta > 0:
                if q.advance(kills_delta):
                    newly_done.append(q)
            elif q.qtype == QuestType.SURVIVE:
                mins = elapsed_secs // 60
                q.progress = min(q.target, mins)
                if q.progress >= q.target:
                    q.done = True
                    newly_done.append(q)
            elif q.qtype == QuestType.GOLD and gold_delta > 0:
                if q.advance(gold_delta):
                    newly_done.append(q)

        for q in newly_done:
            if not q.notified:
                q.notified = True
                self.notif_queue.append(
                    [T("quest_complete_notif", r=q.reward), self.NOTIF_DURATION, q.reward])
                self.completed.append(q)

        self.notif_queue     = [[m, t - 1, r] for m, t, r in self.notif_queue     if t > 1]
        self.new_quest_notif = [[m, t - 1]    for m, t    in self.new_quest_notif if t > 1]

        if (tick >= self.next_unlock_tick
                and self.pending_pool
                and len([q for q in self.quests if not q.done]) < self.MAX_ACTIVE):
            new_q = self.pending_pool.pop(0)
            self.quests.append(new_q)
            self.new_quest_notif.append([T("quest_new"), self.NOTIF_DURATION])
            self.next_unlock_tick = tick + self.UNLOCK_INTERVAL * 60

    def collect_rewards(self) -> int:
        total = sum(q.reward for q in self.completed)
        self.completed.clear()
        return total

    def draw_panel(self, surf, screen_h: int):
        if self._font_title is None:
            self._font_title = get_sys_font(14, bold=True)
            self._font_item  = get_sys_font(13)
            self._font_prog  = get_sys_font(12)

        active = [q for q in self.quests if not q.done][:self.MAX_ACTIVE]
        if not active:
            self.toggle_rect = None
            return

        ROW_H   = 44
        PAD     = 6
        panel_h = 26 if self.collapsed else 22 + len(active) * ROW_H + PAD
        px      = self.PANEL_X
        py      = 65
        self.toggle_rect = pygame.Rect(px + self.PANEL_W - 26, py + 1, 24, 20)

        panel_s = pygame.Surface((self.PANEL_W, panel_h), pygame.SRCALPHA)
        panel_s.fill((12, 10, 22, 180))
        surf.blit(panel_s, (px, py))
        pygame.draw.rect(surf, (70, 60, 120), (px, py, self.PANEL_W, panel_h), 1, border_radius=4)

        title_s = self._font_title.render(T("quests_title"), True, (180, 160, 255))
        surf.blit(title_s, (px + PAD, py + 4))
        draw_collapse_arrow(surf, self.toggle_rect, self.collapsed,
                            self.toggle_rect.collidepoint(pygame.mouse.get_pos()))
        if self.collapsed:
            return

        for i, q in enumerate(active):
            ry = py + 22 + i * ROW_H
            row_s = pygame.Surface((self.PANEL_W - 2, ROW_H - 2), pygame.SRCALPHA)
            row_s.fill((20, 18, 40, 100))
            surf.blit(row_s, (px + 1, ry))

            lbl = self._font_item.render(q.label(), True, (200, 195, 240))
            surf.blit(lbl, (px + PAD, ry + 3))

            bar_w = self.PANEL_W - PAD * 2 - 50
            bar_h = 6
            bar_x = px + PAD
            bar_y = ry + 22
            ratio = q.progress / q.target if q.target > 0 else 0
            pygame.draw.rect(surf, (40, 35, 60), (bar_x, bar_y, bar_w, bar_h), border_radius=3)
            if ratio > 0:
                fill_c = (100, 220, 120) if ratio > 0.75 else (80, 160, 255)
                pygame.draw.rect(surf, fill_c,
                                 (bar_x, bar_y, int(bar_w * ratio), bar_h), border_radius=3)
            pygame.draw.rect(surf, (60, 55, 90), (bar_x, bar_y, bar_w, bar_h), 1, border_radius=3)

            prog_s = self._font_prog.render(q.progress_str(), True, (140, 135, 180))
            surf.blit(prog_s, (bar_x + bar_w + 4, bar_y - 2))

            rew_s = self._font_prog.render(T("quest_reward", r=q.reward), True, (255, 215, 0))
            surf.blit(rew_s, (px + self.PANEL_W - rew_s.get_width() - PAD, ry + 3))

    def draw_notifications(self, surf, screen_w: int, start_y: int = 80):
        if self._font_title is None:
            return
        font_notif = get_sys_font(20, bold=True)
        offset_y = start_y
        for msg, t, *_ in self.notif_queue:
            alpha  = min(255, t * 4)
            ns     = font_notif.render(msg, True, (255, 215, 0))
            ns.set_alpha(alpha)
            nx = screen_w // 2 - ns.get_width() // 2
            ny = offset_y
            bg_s = pygame.Surface((ns.get_width() + 24, ns.get_height() + 8), pygame.SRCALPHA)
            bg_s.fill((10, 8, 20, min(180, alpha)))
            bg_s.set_alpha(alpha)
            surf.blit(bg_s, (nx - 12, ny - 4))
            surf.blit(ns, (nx, ny))
            offset_y += ns.get_height() + 12

        font_new = get_sys_font(17, bold=True)
        for msg, t in self.new_quest_notif:
            alpha = min(255, t * 5)
            ns    = font_new.render(msg, True, (120, 200, 255))
            ns.set_alpha(alpha)
            surf.blit(ns, (screen_w - ns.get_width() - 16, 76))

# ---------------------------------------------------------------------------
# Hệ thống ngôn ngữ / Dil sistemi (VI / EN / TR)
# ---------------------------------------------------------------------------
LANG = "VI"  # Ngôn ngữ khởi đầu mặc định: Tiếng Việt
_last_non_en = "TR"

STRINGS = {
    "VI": {
        "title":                 "Vampire Survivors Clone",
        "paused":                "TẠM DỪNG TRÒ CHƠI",
        "pause_title":           "TẠM DỪNG TRÒ CHƠI",
        "pause_resume":          "Tiếp tục",
        "pause_restart":         "Chơi lại",
        "pause_settings":        "Cài đặt âm thanh / Hiệu ứng",
        "pause_main_menu":       "Về Menu Chính",
        "shake_on":              "Rung màn hình: BẬT",
        "shake_off":             "Rung màn hình: TẮT",
        "vfx_high":              "Hiệu ứng VFX: ĐẦY ĐỦ",
        "vfx_low":               "Hiệu ứng VFX: TỐI ƯU",
        "game_over":             "TRÒ CHƠI KẾT THÚC",
        "time":                  "Thời gian",
        "level":                 "Cấp",
        "kill":                  "Hạ gục",
        "wave":                  "Đợt",
        "restart":               "[R] Chơi lại   [ESC] Menu chính",
        "controls":              "WASD: Di chuyển  ESC/P: Tạm dừng  L: Ngôn ngữ  M: Âm thanh",
        "controls_btn":          "Điều khiển",
        "controls_title":        "BẢNG ĐIỀU KHIỂN",
        "close":                 "Đóng",
        "ctl_move":              ("WASD / Phím mũi tên", "Di chuyển (SPACE/SHIFT: Lướt)"),
        "ctl_pause":             ("ESC / P", "Mở Menu Tạm dừng / Tiếp tục"),
        "ctl_lang":              ("L", "Đổi ngôn ngữ"),
        "ctl_sound":             ("M", "Bật / Tắt âm thanh"),
        "ctl_upgrade":           ("1 / 2 / 3 hoặc Chuột", "Chọn nâng cấp / Hợp nhất"),
        "ctl_restart":           ("R", "Chơi lại nhanh"),
        "ctl_menu":              ("Mũi tên Lên/Xuống + Enter", "Điều khiển Menu Tạm dừng"),
        "weapons":               "Kiếm Lv{w}  Hư Không Lv{o}  Thánh Quang Lv{a}  Lưỡi Hái Lv{b}  Giáp {ar}  Hồi phục {r}",
        "weapons_title":         "Kỹ năng & Hợp Nhất",
        "wpn_whip":              "Trảm Huyết Nguyệt",
        "wpn_void":              "Hố Đen Hư Không",
        "wpn_arrow":             "Mưa Tên Độc Ảnh",
        "wpn_hammer":            "Phán Quyết Ánh Sáng",
        "wpn_orb":               "Khiên Tinh Cầu",
        "wpn_aura":              "Trường Lực Thánh",
        "wpn_boomerang":         "Lưỡi Hái Tử Thần",
        "wpn_lightning":         "Bão Sấm Sét",
        "wpn_ice":               "Tên Lửa Tinh Vân",
        "wpn_fire_trail":        "Vệt Lửa Địa Ngục",
        "wpn_familiar":          "Tinh Linh Hộ Vệ",
        "wpn_armor":             "Giáp",
        "wpn_regen":             "Hồi phục",
        "level_up":              "LÊN CẤP!",
        "choose":                "Chọn kỹ năng (Đạt Lv5 hai kỹ năng tương thích để HỢP NHẤT THẦN THOẠI)",
        "click_hint":            "Nhấp chuột hoặc [1/2/3]",
        "awakened_tag":          "★ THỨC TỈNH ★",
        "fusion_tag":            "★ KỸ NĂNG HỢP NHẤT ★",
        "recipe_prefix":         "Công thức Hợp Nhất: ",
        "hp":                    "HP",
        "lv":                    "LV",
        "xp":                    "XP",
        "muted":                 "Âm thanh: TẮT",
        "unmuted":               "Âm thanh: BẬT",
        "lang_label":            "VI",
        "ach_unlocked":          "MỞ KHÓA THÀNH TỰU!",
        "ach_first_blood_title": "Chiến công đầu",
        "ach_first_blood_desc":  "Tiêu diệt kẻ địch đầu tiên",
        "ach_monster_slayer_title": "Thợ săn quái vật",
        "ach_monster_slayer_desc": "Tiêu diệt 100 kẻ địch",
        "ach_survivor_title":    "Kẻ sống sót",
        "ach_survivor_desc":     "Sống sót trong 10 phút",
        "ach_rich_title":        "Đại gia",
        "ach_rich_desc":         "Tích lũy 1000 vàng",
        "ach_boss_hunter_title": "Thợ săn Boss",
        "ach_boss_hunter_desc":  "Tiêu diệt Boss đầu tiên",
        "ach_treasure_seeker_title": "Kẻ tìm kho báu",
        "ach_treasure_seeker_desc": "Mở 10 rương báu",
        "upgrade_names": {
            "MAX_HP":                  "Huyết Lực Cường Hóa",
            "SPEED":                   "Bộ Pháp Thần Tốc",
            "WHIP":                    "Trảm Huyết Nguyệt",
            "VOID_SINGULARITY":        "Hố Đen Hư Không",
            "PHANTOM_ARROW":           "Mưa Tên Độc Ảnh",
            "JUDGEMENT_HAMMER":        "Phán Quyết Ánh Sáng",
            "ORB":                     "Khiên Tinh Cầu",
            "AURA":                    "Trường Lực Thánh",
            "BOOMERANG":               "Lưỡi Hái Tử Thần",
            "LIGHTNING_STAFF":         "Bão Sấm Sét",
            "ICE_WAND":                "Tên Lửa Tinh Vân",
            "FIRE_TRAIL":              "Vệt Lửa Địa Ngục",
            "FAMILIAR":                "Tinh Linh Hộ Vệ",
            "RECOVERY":                "Suối Nguồn Sinh Mệnh",
            "ARMOR":                   "Chiến Giáp Cổ Ngữ",
            "FUSION_BLOOD_DOMAIN":     "Huyết Ngục Vĩnh Hằng",
            "FUSION_COSMIC_TEMPEST":   "Bão Từ Trường Vũ Trụ",
            "FUSION_REAPER_HURRICANE": "Cơn Lốc Tử Thần",
            "FUSION_SOLAR_APOCALYPSE": "Thánh Phạt Thái Dương",
        },
        "upgrade_descs": {
            "MAX_HP":                  "+40 máu tối đa & hồi máu",
            "SPEED":                   "+10% tốc độ di chuyển",
            "WHIP":                    "Chém bán nguyệt gây xuất huyết & hút máu",
            "VOID_SINGULARITY":        "Cầu hố đen hút quái & phát nổ hư không",
            "PHANTOM_ARROW":           "Tên độc nảy giữa quái & đặt bẫy bóng đêm",
            "JUDGEMENT_HAMMER":        "Búa thánh xoay xoắn ốc & giáng cột sáng",
            "ORB":                     "Khiên tinh cầu xoay & co giãn quanh thân",
            "AURA":                    "Làm chậm & thiêu đốt kẻ địch xung quanh",
            "BOOMERANG":               "Lưỡi hái tử thần xoay vòng cung trở về",
            "LIGHTNING_STAFF":         "Sét chuỗi giật ưu tiên mục tiêu máu cao",
            "ICE_WAND":                "Đạn tự dẫn đường & đóng băng kẻ địch",
            "FIRE_TRAIL":              "Để lại vệt lửa địa ngục thiêu đốt mặt đất",
            "FAMILIAR":                "Triệu hồi tinh linh bắn đạn ma thuật hỗ trợ",
            "RECOVERY":                "+1 HP/giây hồi phục sinh lực",
            "ARMOR":                   "+2 Giáp giảm sát thương nhận vào",
            "FUSION_BLOOD_DOMAIN":     "[HỢP NHẤT] Lãnh địa huyết kim chém & rút máu toàn màn hình",
            "FUSION_COSMIC_TEMPEST":   "[HỢP NHẤT] Siêu hố đen phóng bão sét chuỗi khắp chiến trường",
            "FUSION_REAPER_HURRICANE": "[HỢP NHẤT] Đại lưỡi hái phân tách thành mưa tên độc & bẫy",
            "FUSION_SOLAR_APOCALYPSE": "[HỢP NHẤT] Búa thần rải lửa thánh & giáng thiên phạt thái dương",
        },
        "biome_0":               "Nghĩa Địa Cổ Đại",
        "biome_1":               "Hầm Ngục Huyết Nguyệt",
        "biome_2":               "Rừng Hư Không",
        "biome_label":           "Bản đồ: {b} (Nhấn [B] đổi)",
        "swarm_alert":           "⚠ ĐỢT TẤN CÔNG DỒN DẬP! ⚠",
        "boss_lich":             "CHÚA TỂ XƯƠNG (LICH KING)",
        "boss_demon":            "ÁC QUỶ VỰC THẲM (ABYSSAL DEMON LORD)",
        # Menu
        "menu_play":             "Bắt đầu chơi",
        "menu_campaign":         "Chiến dịch",
        "menu_settings":         "Cài đặt",
        "menu_chars":            "Nhân vật",
        "menu_skins":            "Cửa Hàng Trang Phục",
        "skin_shop_title":       "CỬA HÀNG TRANG PHỤC ANIME",
        "skin_shop_sub":         "Mở khóa & Trang bị ngoại hình Anime huyền thoại kèm biến đổi hiệu ứng kỹ năng (VFX)!",
        "skin_equip":            "Trang Bị",
        "skin_equipped":         "Đang Dùng",
        "skin_default_btn":      "Ngoại Hình Mặc Định",
        "skin_using_default":    "Đang Dùng Mặc Định",
        "skin_buy_fmt":          "Mua ({cost} Vàng)",
        "item_magnet_pickup":    "⚡ NAM CHÂM TỪ TRƯỜNG! ⚡",
        "menu_quit":             "Thoát",
        "menu_back":             "Quay lại",
        "main_menu":             "Menu chính",
        "campaign_title":        "Chế độ Chiến dịch",
        "campaign_level":        "Màn {n}",
        "target_wave":           "Mục tiêu Đợt {n}",
        "completed":             "HOÀN THÀNH",
        "level_completed":       "HOÀN THÀNH MÀN CHƠI!",
        "next_level":            "Màn tiếp theo",
        "menu_sound":            "Âm thanh",
        "vol_master":            "Âm lượng tổng",
        "vol_music":             "Nhạc nền",
        "vol_sfx":               "Hiệu ứng âm thanh",
        "vol_coin":              "Âm thanh tiền vàng",
        "menu_sound_on":         "BẬT",
        "menu_sound_off":        "TẮT",
        "menu_fullscreen":       "Toàn màn hình",
        "menu_fs_on":            "BẬT",
        "menu_fs_off":           "TẮT",
        "boss_fight":            "BOSS XUẤT HIỆN!",
        "boss_tag":              "TRÙM",
        "gold":                  "Vàng",
        "high_score":            "Kỷ lục: Hạ {k} | Đợt {w} | {t}",
        "perm_upgrades":         "CƯỜNG HÓA VĨNH VIỄN (LƯU TỰ ĐỘNG)",
        "perm_hp":               "Sinh Mệnh",
        "perm_dmg":              "Sát Thương",
        "perm_spd":              "Tốc Độ",
        "perm_gold":             "Thu Nhập Vàng",
        "drone_turret":          "Drone: {d}  Tháp pháo: {t}",
        # Nhiệm vụ
        "quests_title":          "NHIỆM VỤ",
        "quest_kill":            "Tiêu diệt {n} kẻ địch",
        "quest_survive":         "Sống sót {n} phút",
        "quest_gold":            "Thu thập {n} vàng",
        "quest_reward":          "+{r} Vàng",
        "quest_done":            "HOÀN THÀNH",
        "quest_new":             "NHIỆM VỤ MỚI!",
        "quest_complete_notif":  "Nhiệm vụ hoàn thành! +{r} Vàng",
        "locked":                "KHÓA",
        "buy":                   "Mở khóa",
        "owned":                 "CHỌN",
        "not_enough":            "Không đủ vàng!",
        "selected":              "ĐANG CHỌN",
        "char_names": {
            "warrior":           "Huyết Kiếm Sĩ",
            "mage":              "Pháp Sư Tinh Vân",
            "rogue":             "Thợ Săn Bóng Đêm",
            "paladin":           "Thánh Kỵ Sĩ",
        },
        "char_subtitles": {
            "warrior":           "Crimson Berserker",
            "mage":              "Astral Arcanist",
            "rogue":             "Cyber-Shadow Ranger",
            "paladin":           "Solar Paladin",
        },
        "char_descs": {
            "warrior":           "+60 Máu, +2 Giáp | Khởi đầu: Trảm Huyết Nguyệt",
            "mage":              "-20% Hồi chiêu | Khởi đầu: Hố Đen Hư Không",
            "rogue":             "+25% Tốc độ, 30% Chí mạng | Khởi đầu: Mưa Tên Độc Ảnh",
            "paladin":           "+80 Máu, +4 Giáp, +2 Hồi phục | Khởi đầu: Phán Quyết Ánh Sáng",
        },
        "char_passives": {
            "warrior":           "Độc quyền: Trảm Huyết Nguyệt (Xuất huyết & Hút máu)",
            "mage":              "Độc quyền: Hố Đen Hư Không (Hút quái & Nổ Nova)",
            "rogue":             "Độc quyền: Mưa Tên Độc Ảnh (Nảy mục tiêu & Bẫy độc)",
            "paladin":           "Độc quyền: Phán Quyết Ánh Sáng (Búa xoắn ốc & Thiên phạt)",
        },
    },
    "TR": {
        "title":         "Vampire Survivors Clone",
        "paused":        "DURAKLATILDI",
        "pause_title":   "OYUN DURAKLATILDI",
        "pause_resume":  "Devam Et",
        "pause_restart": "Yeniden Başla",
        "pause_settings":"Ses / Efekt Ayarları",
        "pause_main_menu":"Ana Menüye Dön",
        "shake_on":      "Ekran Sarsıntısı: AÇIK",
        "shake_off":     "Ekran Sarsıntısı: KAPALI",
        "vfx_high":      "VFX: YÜKSEK",
        "vfx_low":       "VFX: DÜŞÜK",
        "game_over":     "GAME OVER",
        "time":          "Süre",
        "level":         "Level",
        "kill":          "Kill",
        "wave":          "Dalga",
        "restart":       "[R] Yeniden Başla   [ESC] Çıkış",
        "controls":      "WASD: Hareket  P/ESC: Duraklat  L: Dil  M: Ses",
        "controls_btn":  "Kontroller",
        "controls_title": "KONTROLLER",
        "close":         "Kapat",
        "ctl_move":      ("WASD / Yön tuşları", "Hareket"),
        "ctl_pause":     ("ESC / P", "Duraklat / Devam"),
        "ctl_lang":      ("L", "Dil değiştir"),
        "ctl_sound":     ("M", "Sesi aç / kapat"),
        "ctl_upgrade":   ("1 / 2 / 3 veya tık", "Yükseltme seç"),
        "ctl_restart":   ("R", "Yeniden başla"),
        "ctl_menu":      ("ESC", "Duraklatma Menüsü"),
        "weapons":       "Kırbaç Lv{w}  Orb Lv{o}  Aura Lv{a}  Boomerang Lv{b}  Zırh {ar}  Regen {r}",
        "weapons_title": "Yetenekler & Sinerji",
        "wpn_whip":      "Kanlı Ay kesişi",
        "wpn_void":      "Boşluk Tekilliği",
        "wpn_arrow":     "Hayalet Ok Yağmuru",
        "wpn_hammer":    "Işık Çekici",
        "wpn_orb":       "Kalkan Küresi",
        "wpn_aura":      "Kutsal Aura",
        "wpn_boomerang": "Ölüm Tırpanı",
        "wpn_lightning": "Yıldırım Fırtınası",
        "wpn_ice":       "Astral Füze",
        "wpn_fire_trail":"Cehennem İzi",
        "wpn_familiar":  "Ruh Muhafızı",
        "wpn_armor":     "Zırh",
        "wpn_regen":     "Regen",
        "level_up":      "SEVİYE ATLADINIZ",
        "choose":        "Bir güçlendirme seçin",
        "click_hint":    "Tıkla veya [1/2/3]",
        "fusion_tag":    "★ MİTİK BİRLEŞİM ★",
        "recipe_prefix": "Birleşim: ",
        "hp":            "HP",
        "lv":            "LV",
        "xp":            "XP",
        "muted":         "Ses: KAPALI",
        "unmuted":       "Ses: AÇIK",
        "lang_label":    "TR",
        "ach_unlocked":  "BAŞARIM AÇILDI!",
        "ach_first_blood_title":     "İlk Kan",
        "ach_first_blood_desc":      "İlk düşmanı öldür",
        "ach_monster_slayer_title":  "Canavar Avcısı",
        "ach_monster_slayer_desc":   "100 düşman öldür",
        "ach_survivor_title":        "Hayatta Kalan",
        "ach_survivor_desc":         "10 dakika hayatta kal",
        "ach_rich_title":            "Zengin",
        "ach_rich_desc":             "1000 altın biriktir",
        "ach_boss_hunter_title":     "Boss Avcısı",
        "ach_boss_hunter_desc":      "İlk boss'u öldür",
        "ach_treasure_seeker_title": "Hazine Avcısı",
        "ach_treasure_seeker_desc":  "10 sandık aç",
        "upgrade_names": {
            "MAX_HP":                  "Maks Sağlık",
            "SPEED":                   "Hız",
            "WHIP":                    "Kanlı Ay Kesişi",
            "VOID_SINGULARITY":        "Boşluk Tekilliği",
            "PHANTOM_ARROW":           "Hayalet Ok Yağmuru",
            "JUDGEMENT_HAMMER":        "Yargı Çekici",
            "ORB":                     "Kalkan Küresi",
            "AURA":                    "Kutsal Aura",
            "BOOMERANG":               "Ölüm Tırpanı",
            "LIGHTNING_STAFF":         "Yıldırım Fırtınası",
            "ICE_WAND":                "Astral Füzeler",
            "FIRE_TRAIL":              "Cehennem Ateşi İzi",
            "FAMILIAR":                "Ruh Muhafızı",
            "RECOVERY":                "Rejenerasyon",
            "ARMOR":                   "Zırh",
            "FUSION_BLOOD_DOMAIN":     "Ebedi Kan Alanı",
            "FUSION_COSMIC_TEMPEST":   "Kozmik Fırtına",
            "FUSION_REAPER_HURRICANE": "Azrail Kasırgası",
            "FUSION_SOLAR_APOCALYPSE": "Güneş Kıyameti",
        },
        "upgrade_descs": {
            "MAX_HP":                  "+40 maks sağlık",
            "SPEED":                   "+10% hareket hızı",
            "WHIP":                    "Kanama & can çalma kesişi",
            "VOID_SINGULARITY":        "Düşmanları çeken kara delik",
            "PHANTOM_ARROW":           "Sekmeli oklar & gölge tuzakları",
            "JUDGEMENT_HAMMER":        "Sarmal çekiç & kutsal ışık",
            "ORB":                     "Dönen koruyucu küreler",
            "AURA":                    "Alan & hasar artışı",
            "BOOMERANG":               "Hasar, hız & menzil artışı",
            "LIGHTNING_STAFF":         "Hasar & zincirleme yıldırım",
            "ICE_WAND":                "Hasar & yavaşlatma artışı",
            "FIRE_TRAIL":              "Yerde yanan ateş izi bırakır",
            "FAMILIAR":                "Büyü atan yardımcı ruh çağırır",
            "RECOVERY":                "+1 HP/sn kazanım",
            "ARMOR":                   "Hasar azaltma",
            "FUSION_BLOOD_DOMAIN":     "[BİRLEŞİM] Ekran boyu kan alanı & can çekme",
            "FUSION_COSMIC_TEMPEST":   "[BİRLEŞİM] Yıldırım saçan dev kara delikler",
            "FUSION_REAPER_HURRICANE": "[BİRLEŞİM] Ok saçan dev ölüm tırpanları",
            "FUSION_SOLAR_APOCALYPSE": "[BİRLEŞİM] Kutsal ateş & güneş sütunları",
        },
        "biome_0":        "Lanetli Mezarlık",
        "biome_1":        "Kanlı Ay Zindanı",
        "biome_2":        "Hiçlik Ormanı",
        "biome_label":    "Harita: {b} ([B])",
        "swarm_alert":    "⚠ SÜRÜ SALDIRISI! ⚠",
        "boss_lich":      "KEMİK KRAL (LICH KING)",
        "boss_demon":     "HİÇLİK İBLİSİ (DEMON LORD)",
        # Menü / yeni özellik metinleri (TR)
        "menu_play":      "Oyuna Başla",
        "menu_campaign":  "Campaign",
        "menu_settings":  "Ayarlar",
        "menu_chars":     "Karakterler",
        "menu_skins":     "Kostüm Mağazası",
        "skin_shop_title":"ANİME KOSTÜM MAĞAZASI",
        "skin_shop_sub":  "Efsanevi Anime kostümlerini açın ve özel yetenek efektlerini kuşanın!",
        "skin_equip":     "Kuşan",
        "skin_equipped":  "Kuşanıldı",
        "skin_default_btn":"Varsayılan Görünüm",
        "skin_using_default":"Varsayılan Aktif",
        "skin_buy_fmt":   "Satın Al ({cost} Altın)",
        "item_magnet_pickup": "⚡ MANYETİK ÇEKİM! ⚡",
        "menu_quit":      "Çıkış",
        "menu_back":      "Geri",
        "main_menu":      "Ana Menü",
        "campaign_title": "Campaign Mode",
        "campaign_level": "Level {n}",
        "target_wave":    "Target Wave {n}",
        "completed":      "TAMAMLANDI",
        "level_completed":"LEVEL COMPLETED",
        "next_level":     "Next Level",
        "menu_sound":     "Ses",
        "vol_master":     "Ana Ses",
        "vol_music":      "Müzik Sesi",
        "vol_sfx":        "Efekt Sesi",
        "vol_coin":       "Altın Sesi",
        "menu_sound_on":  "AÇIK",
        "menu_sound_off": "KAPALI",
        "menu_fullscreen":"Tam Ekran",
        "menu_fs_on":     "AÇIK",
        "menu_fs_off":    "KAPALI",
        "boss_fight":     "BOSS SAVAŞI!",
        "boss_tag":       "BOSS",
        "gold":           "Altın",
        "drone_turret":   "Drone: {d}  Taret: {t}",
        # Görev sistemi
        "quests_title":         "GÖREVLER",
        "quest_kill":           "{n} düşman öldür",
        "quest_survive":        "{n} dakika hayatta kal",
        "quest_gold":           "{n} altın kazan",
        "quest_reward":         "+{r} Altın",
        "quest_done":           "TAMAMLANDI",
        "quest_new":            "YENİ GÖREV!",
        "quest_complete_notif": "Görev Tamamlandı! +{r} Altın",
        "locked":         "KİLİTLİ",
        "buy":            "Satın Al",
        "owned":          "SAHİP",
        "not_enough":     "Yetersiz Altın",
        "selected":       "SEÇİLDİ",
        "restart":        "[R] Yeniden Başla   [ESC] Menü",
        "controls":       "WASD: Hareket  P: Duraklat  M: Ses  ESC: Menü",
        "char_names": {
            "warrior": "Kızıl Berserker",
            "mage":    "Astral Büyücü",
            "rogue":   "Gölge Korucu",
            "paladin": "Güneş Paladini",
        },
        "char_subtitles": {
            "warrior": "Crimson Berserker",
            "mage":    "Astral Arcanist",
            "rogue":   "Cyber-Shadow Ranger",
            "paladin": "Solar Paladin",
        },
        "char_descs": {
            "warrior": "+60 HP, +2 Zırh | Kanlı Ay Kesişi",
            "mage":    "-20% Bekleme | Boşluk Tekilliği",
            "rogue":   "+25% Hız, 30% Kritik | Hayalet Ok",
            "paladin": "+80 HP, +4 Zırh, +2 Regen | Yargı Çekici",
        },
        "char_passives": {
            "warrior": "Pasif: Öldürmede Can Çalma & Kanama",
            "mage":    "Pasif: -20% Bekleme Süresi & Nova",
            "rogue":   "Pasif: 30% Kritik x2 & Gölge Tuzakları",
            "paladin": "Pasif: Sarmal Çekiç & Kutsal Darbe",
        },
        "awakened_tag":  "★ UYANIŞ ★",
        "high_score":    "Rekor: {k} Leş | Dalga {w} | {t}",
        "perm_upgrades": "KALICI GÜÇLENDİRMELER",
        "perm_hp":       "Maks HP",
        "perm_dmg":      "Hasar",
        "perm_spd":      "Hız",
        "perm_gold":     "Altın Bonusu",
    },
    "EN": {
        "title":         "Vampire Survivors Clone",
        "paused":        "PAUSED",
        "pause_title":   "GAME PAUSED",
        "pause_resume":  "Resume",
        "pause_restart": "Restart",
        "pause_settings":"Sound / VFX Settings",
        "pause_main_menu":"Main Menu",
        "shake_on":      "Screen Shake: ON",
        "shake_off":     "Screen Shake: OFF",
        "vfx_high":      "VFX Quality: HIGH",
        "vfx_low":       "VFX Quality: LOW",
        "game_over":     "GAME OVER",
        "time":          "Time",
        "level":         "Level",
        "kill":          "Kills",
        "wave":          "Wave",
        "restart":       "[R] Restart   [ESC] Main Menu",
        "controls":      "WASD: Move  ESC/P: Pause  L: Language  M: Sound",
        "controls_btn":  "Controls",
        "controls_title": "CONTROLS",
        "close":         "Close",
        "ctl_move":      ("WASD / Arrow keys", "Move (SPACE/SHIFT: Dash)"),
        "ctl_pause":     ("ESC / P", "Toggle Pause Menu"),
        "ctl_lang":      ("L", "Switch language"),
        "ctl_sound":     ("M", "Sound on / off"),
        "ctl_upgrade":   ("1 / 2 / 3 or click", "Pick upgrade / Fusion"),
        "ctl_restart":   ("R", "Quick Restart"),
        "ctl_menu":      ("Up/Down + Enter", "Navigate Pause Menu"),
        "weapons":       "Whip Lv{w}  Orb Lv{o}  Aura Lv{a}  Boomerang Lv{b}  Armor {ar}  Regen {r}",
        "weapons_title": "Skills & Synergies",
        "wpn_whip":      "Blood Moon Slash",
        "wpn_void":      "Void Singularity",
        "wpn_arrow":     "Phantom Volley",
        "wpn_hammer":    "Judgement Hammer",
        "wpn_orb":       "Orbiting Shields",
        "wpn_aura":      "Sacred Aura",
        "wpn_boomerang": "Boomerang Scythe",
        "wpn_lightning": "Thunderstorm",
        "wpn_ice":       "Astral Missiles",
        "wpn_fire_trail":"Hellfire Trail",
        "wpn_familiar":  "Arcane Familiar",
        "wpn_armor":     "Armor",
        "wpn_regen":     "Regen",
        "level_up":      "LEVEL UP",
        "choose":        "Choose a skill (Reach Lv5 on 2 compatible skills to FUSE)",
        "click_hint":    "Click or [1/2/3]",
        "awakened_tag":  "★ AWAKENED ★",
        "fusion_tag":    "★ MYTHIC FUSION ★",
        "recipe_prefix": "Fusion Recipe: ",
        "hp":            "HP",
        "lv":            "LV",
        "xp":            "XP",
        "muted":         "Sound: OFF",
        "unmuted":       "Sound: ON",
        "lang_label":    "EN",
        "ach_unlocked":  "ACHIEVEMENT UNLOCKED!",
        "ach_first_blood_title":     "First Blood",
        "ach_first_blood_desc":      "Kill your first enemy",
        "ach_monster_slayer_title":  "Monster Slayer",
        "ach_monster_slayer_desc":   "Kill 100 enemies",
        "ach_survivor_title":        "Survivor",
        "ach_survivor_desc":         "Survive for 10 minutes",
        "ach_rich_title":            "Rich",
        "ach_rich_desc":             "Collect 1000 gold",
        "ach_boss_hunter_title":     "Boss Hunter",
        "ach_boss_hunter_desc":      "Kill your first boss",
        "ach_treasure_seeker_title": "Treasure Seeker",
        "ach_treasure_seeker_desc":  "Open 10 chests",
        "upgrade_names": {
            "MAX_HP":                  "Crimson Vitality",
            "SPEED":                   "Phantom Stride",
            "WHIP":                    "Blood Moon Slash",
            "VOID_SINGULARITY":        "Void Singularity",
            "PHANTOM_ARROW":           "Phantom Arrow Volley",
            "JUDGEMENT_HAMMER":        "Judgement Hammer",
            "ORB":                     "Orbiting Shields",
            "AURA":                    "Sacred Aura",
            "BOOMERANG":               "Boomerang Scythe",
            "LIGHTNING_STAFF":         "Thunderstorm",
            "ICE_WAND":                "Astral Missiles",
            "FIRE_TRAIL":              "Hellfire Trail",
            "FAMILIAR":                "Arcane Familiar",
            "RECOVERY":                "Holy Recovery",
            "ARMOR":                   "Runic Plate",
            "FUSION_BLOOD_DOMAIN":     "Eternal Blood Domain",
            "FUSION_COSMIC_TEMPEST":   "Cosmic Tempest",
            "FUSION_REAPER_HURRICANE": "Reaper's Hurricane",
            "FUSION_SOLAR_APOCALYPSE": "Solar Apocalypse",
        },
        "upgrade_descs": {
            "MAX_HP":                  "+40 max health & heal",
            "SPEED":                   "+10% move speed",
            "WHIP":                    "Crimson crescent slash: bleed & lifesteal",
            "VOID_SINGULARITY":        "Gravity orb pulls foes & explodes in nova",
            "PHANTOM_ARROW":           "Bouncing cursed arrows & shadow traps",
            "JUDGEMENT_HAMMER":        "Spiraling golden hammer & holy smite beams",
            "ORB":                     "Orbiting shields expand & contract",
            "AURA":                    "Slows & burns enemies inside",
            "BOOMERANG":               "Curving reaper scythe return",
            "LIGHTNING_STAFF":         "Chain-lightning on high-HP foes",
            "ICE_WAND":                "Homing arcane shards & freeze",
            "FIRE_TRAIL":              "Leaves burning hellfire pools behind you",
            "FAMILIAR":                "Summons spirit familiars firing bolts",
            "RECOVERY":                "+1 HP/s recovery",
            "ARMOR":                   "Reduce incoming damage",
            "FUSION_BLOOD_DOMAIN":     "[FUSION] Crimson-gold domain slashes & drains all foes",
            "FUSION_COSMIC_TEMPEST":   "[FUSION] Black holes shoot chain lightning screen-wide",
            "FUSION_REAPER_HURRICANE": "[FUSION] Giant scythes split into homing phantom arrows",
            "FUSION_SOLAR_APOCALYPSE": "[FUSION] Spiraling hammers leave solar fire & smite beams",
        },
        "biome_0":        "Cursed Graveyard",
        "biome_1":        "Blood Moon Dungeon",
        "biome_2":        "Corrupted Abyss Forest",
        "biome_label":    "Biome: {b} ([B] switch)",
        "swarm_alert":    "⚠ RELENTLESS SWARM INCOMING! ⚠",
        "boss_lich":      "LICH KING",
        "boss_demon":     "ABYSSAL DEMON LORD",
        # Menu / new features (EN)
        "menu_play":      "Play",
        "menu_campaign":  "Campaign",
        "menu_settings":  "Settings",
        "menu_chars":     "Characters",
        "menu_skins":     "Anime Skin Shop",
        "skin_shop_title":"ANIME SKIN SHOP & WARDROBE",
        "skin_shop_sub":  "Unlock & Equip iconic Anime skins with custom aura & skill VFX!",
        "skin_equip":     "Equip",
        "skin_equipped":  "Equipped",
        "skin_default_btn":"Default Class Look",
        "skin_using_default":"Default Active",
        "skin_buy_fmt":   "Buy ({cost} Gold)",
        "item_magnet_pickup": "⚡ MAGNETIC VACUUM! ⚡",
        "menu_quit":      "Quit",
        "menu_back":      "Back",
        "main_menu":      "Main Menu",
        "campaign_title": "Campaign Mode",
        "campaign_level": "Level {n}",
        "target_wave":    "Target Wave {n}",
        "completed":      "COMPLETED",
        "level_completed":"LEVEL COMPLETED",
        "next_level":     "Next Level",
        "menu_sound":     "Sound",
        "vol_master":     "Master Volume",
        "vol_music":      "Music Volume",
        "vol_sfx":        "SFX Volume",
        "vol_coin":       "Coin Volume",
        "menu_sound_on":  "ON",
        "menu_sound_off": "OFF",
        "menu_fullscreen":"Fullscreen",
        "menu_fs_on":     "ON",
        "menu_fs_off":    "OFF",
        "boss_fight":     "BOSS FIGHT!",
        "boss_tag":       "BOSS",
        "gold":           "Gold",
        "high_score":     "Best: {k} Kills | Wave {w} | {t}",
        "perm_upgrades":  "PERMANENT UPGRADES (AUTO-SAVED)",
        "perm_hp":        "Max HP",
        "perm_dmg":       "Damage",
        "perm_spd":       "Speed",
        "perm_gold":      "Gold Bonus",
        "drone_turret":   "Drone: {d}  Turret: {t}",
        # Quest system
        "quests_title":         "QUESTS",
        "quest_kill":           "Kill {n} enemies",
        "quest_survive":        "Survive {n} minutes",
        "quest_gold":           "Earn {n} gold",
        "quest_reward":         "+{r} Gold",
        "quest_done":           "COMPLETED",
        "quest_new":            "NEW QUEST!",
        "quest_complete_notif": "Quest Done! +{r} Gold",
        "locked":         "LOCKED",
        "buy":            "Unlock",
        "owned":          "SELECT",
        "not_enough":     "Not Enough Gold!",
        "selected":       "SELECTED",
        "restart":        "[R] Restart   [ESC] Menu",
        "controls":       "WASD: Move  P: Pause  M: Sound  ESC: Menu",
        "char_names": {
            "warrior": "Crimson Berserker",
            "mage":    "Astral Arcanist",
            "rogue":   "Cyber-Shadow Ranger",
            "paladin": "Solar Paladin",
        },
        "char_subtitles": {
            "warrior": "Huyết Kiếm Sĩ",
            "mage":    "Pháp Sư Tinh Vân",
            "rogue":   "Thợ Săn Bóng Đêm",
            "paladin": "Thánh Kỵ Sĩ",
        },
        "char_descs": {
            "warrior": "+60 HP, +2 Armor | Lifesteal Cleave",
            "mage":    "-20% Cooldown | Void Orb Lv2 & Missiles",
            "rogue":   "+25% Speed, 30% Crit, Piercing Bolts",
            "paladin": "+80 HP, +4 Armor, +2 Regen | Sacred Aura",
        },
        "char_passives": {
            "warrior": "Passive: Lifesteal on Kill & Greatsword Cleave",
            "mage":    "Passive: +20% CDR & Homing Arcane Missiles",
            "rogue":   "Passive: 30% Crit Chance (2x) & Digital Clones",
            "paladin": "Passive: Sacred Aura Burn/Slow & Thunder Strike",
        },
    },
}

def T(key, **kwargs):
    """Mevcut dilde string döndürür / Trả về chuỗi theo ngôn ngữ hiện tại."""
    global _last_non_en
    if LANG in ("VI", "TR"):
        _last_non_en = LANG
    s = STRINGS.get(LANG, STRINGS["VI"]).get(key)
    if s is None:
        # Thiếu khóa ở ngôn ngữ hiện tại -> thử Tiếng Việt, cuối cùng trả về chính khóa
        s = STRINGS["VI"].get(key, key)
    if kwargs and isinstance(s, str):
        try:
            s = s.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            # Placeholder không khớp tham số -> định dạng an toàn, placeholder thiếu giữ nguyên
            class _SafeDict(dict):
                def __missing__(self, k):
                    return "{" + k + "}"
            try:
                s = s.format_map(_SafeDict(**kwargs))
            except (IndexError, ValueError):
                pass
    return s

def toggle_lang():
    global LANG, _last_non_en
    if LANG in ("VI", "TR"):
        _last_non_en = LANG
        LANG = "EN"
    else:
        LANG = _last_non_en

# ---------------------------------------------------------------------------
# Ses motoru (prosedürel — harici dosya gerektirmez)
# ---------------------------------------------------------------------------
class SoundEngine:
    SR = 44100

    def __init__(self, settings_path=None):
        pygame.mixer.pre_init(self.SR, -16, 1, 512)
        pygame.mixer.init()
        self.muted   = False
        self._settings_path = settings_path
        self.volumes = audio_settings.load_settings(settings_path)
        self._cache: dict = {}
        self._last_play: dict = {}
        self._bg_channel: Optional[pygame.mixer.Channel] = None
        self._bg_sound: Optional[pygame.mixer.Sound] = None
        self._start_bg()

    # --- Ses seviyesi ayarları ---
    # Seviye yalnızca Sound.set_volume ile uygulanır (kanal sesi 1.0 kalır);
    # mute ayrı bir mekanizmadır ve seviyeleri değiştirmez.
    def _gain(self, key):
        eff = audio_settings.effective_volumes(self.volumes)
        return eff["coin"] if key == 'coin' else eff["sfx"]

    def set_volume(self, name, percent):
        if name in audio_settings.KEYS:
            self.volumes[name] = audio_settings.clamp_percent(
                percent, self.volumes[name])
            self._apply_volumes()

    def _apply_volumes(self):
        for key, snd in self._cache.items():
            snd.set_volume(self._gain(key))
        if self._bg_sound:
            self._bg_sound.set_volume(
                audio_settings.effective_volumes(self.volumes)["music"])

    def save_volumes(self):
        return audio_settings.save_settings(self.volumes, self._settings_path)

    # --- Sinyal üreticiler ---
    def _sine_buf(self, freq, dur, vol=0.45, attack=0.01, decay_exp=1.0):
        n   = int(self.SR * dur)
        buf = array.array('h')
        for i in range(n):
            t   = i / self.SR
            env = min(t / attack, 1.0) * max(0.0, 1.0 - (t / dur) ** decay_exp)
            s   = int(vol * env * 32767 * math.sin(2 * math.pi * freq * t))
            buf.append(s)
        return bytes(buf)

    def _sweep_buf(self, f0, f1, dur, vol=0.4):
        n   = int(self.SR * dur)
        buf = array.array('h')
        ph  = 0.0
        for i in range(n):
            t    = i / self.SR
            env  = max(0.0, 1.0 - t / dur)
            freq = f0 + (f1 - f0) * (t / dur)
            ph  += 2 * math.pi * freq / self.SR
            s    = int(vol * env * 32767 * math.sin(ph))
            buf.append(s)
        return bytes(buf)

    def _tone_seq_buf(self, notes, vol=0.3, shimmer=0.0):
        """notes: [(freq, dur)] sırayla çalınır; her nota kendi içinde söner.
        shimmer: son notanın bir oktav üstüne eklenen hafif katman (0 = yok)."""
        buf = array.array('h')
        last = len(notes) - 1
        for k, (freq, dur) in enumerate(notes):
            n = int(self.SR * dur)
            for i in range(n):
                t   = i / self.SR
                env = min(t / 0.004, 1.0) * math.exp(-4.0 * t / dur)
                w   = math.sin(2 * math.pi * freq * t) + 0.25 * math.sin(4 * math.pi * freq * t)
                if shimmer and k == last:
                    w += shimmer * math.sin(4 * math.pi * freq * t)
                buf.append(int(max(-1.0, min(1.0, vol * env * w)) * 32767))
        return bytes(buf)

    def _noise_buf(self, dur, vol=0.35):
        n   = int(self.SR * dur)
        buf = array.array('h')
        for i in range(n):
            env = max(0.0, 1.0 - i / n)
            s   = int(vol * env * 32767 * (random.random() * 2 - 1))
            buf.append(s)
        return bytes(buf)

    def _make(self, key, fn):
        if key not in self._cache:
            data = fn()
            snd  = pygame.mixer.Sound(buffer=data)
            snd.set_volume(self._gain(key))
            self._cache[key] = snd
        return self._cache[key]

    def _play(self, snd):
        if not self.muted:
            snd.play()

    def _throttled(self, key, min_ms):
        """Ses azaltma: yalnızca sesi sınırlar, oyun mantığını etkilemez.
        Sessizdeyken zaman damgasını tüketmez; aynı key min_ms içinde
        tekrar çalınmaz (üst üste binmeyi önler)."""
        if self.muted:
            return False
        now = pygame.time.get_ticks()
        if now - self._last_play.get(key, -min_ms) < min_ms:
            return False
        self._last_play[key] = now
        return True

    # --- Oyun sesleri ---
    def play_coin(self):
        if self._throttled('coin', 70):
            self._play(self._make('coin',
                lambda: self._tone_seq_buf([(988, 0.05), (1319, 0.11)], 0.3)))

    def play_achievement(self):
        if self._throttled('ach', 400):
            self._play(self._make('ach',
                lambda: self._tone_seq_buf(
                    [(523, 0.09), (659, 0.09), (784, 0.09), (1047, 0.28)],
                    0.35, shimmer=0.3)))

    def play_hit(self):
        self._play(self._make('hit',
            lambda: self._noise_buf(0.08, 0.3)))

    def play_whip(self):
        self._play(self._make('whip',
            lambda: self._sweep_buf(600, 150, 0.14, 0.5)))

    def play_orb(self):
        self._play(self._make('orb',
            lambda: self._sine_buf(520, 0.12, 0.35)))

    def play_aura(self):
        self._play(self._make('aura',
            lambda: self._sine_buf(180, 0.18, 0.25, decay_exp=2)))

    def play_xp(self):
        self._play(self._make('xp',
            lambda: self._sweep_buf(400, 900, 0.12, 0.3)))

    def play_levelup(self):
        self._play(self._make('lvlup',
            lambda: self._sweep_buf(500, 1400, 0.35, 0.5)))

    def play_damage(self):
        self._play(self._make('dmg',
            lambda: self._sweep_buf(200, 80, 0.18, 0.45)))

    def play_lightning(self):
        self._play(self._make('lightning',
            lambda: self._sweep_buf(1400, 300, 0.12, 0.45)))

    def play_ice(self):
        self._play(self._make('ice',
            lambda: self._sine_buf(1700, 0.08, 0.35, attack=0.005, decay_exp=1.5)))

    def play_death(self):
        self._play(self._make('death',
            lambda: self._noise_buf(0.5, 0.55)))

    # --- Arka plan müziği (prosedürel loop) ---
    def _build_bg(self):
        """Ambient drone + ritim: tamamen kod ile üretilir."""
        dur   = 4.0
        n     = int(self.SR * dur)
        buf   = array.array('h')
        notes = [110, 138.6, 164.8, 130.8]  # Am pentatonik
        for i in range(n):
            t    = i / self.SR
            beat = t * 2  # 120 BPM
            # Drone katmanı
            drone = (math.sin(2*math.pi*55*t) * 0.18 +
                     math.sin(2*math.pi*110*t) * 0.12 +
                     math.sin(2*math.pi*220*t) * 0.06)
            # Melodi
            note_idx = int(beat * 2) % len(notes)
            freq     = notes[note_idx]
            env_m    = 0.5 + 0.5 * math.sin(beat * math.pi)
            melody   = math.sin(2*math.pi*freq*t) * 0.10 * env_m
            # Ritim (düşük frekans pulse)
            kick = math.sin(2*math.pi*80*t) * math.exp(-8 * (beat % 1)) * 0.15
            val  = int((drone + melody + kick) * 32767 * 0.6)
            val  = max(-32767, min(32767, val))
            buf.append(val)
        return bytes(buf)

    def _start_bg(self):
        try:
            data = self._build_bg()
            snd  = pygame.mixer.Sound(buffer=data)
            snd.set_volume(audio_settings.effective_volumes(self.volumes)["music"])
            self._bg_sound   = snd
            self._bg_channel = snd.play(loops=-1)
        except Exception:
            self._bg_channel = None

    def toggle_mute(self):
        self.muted = not self.muted
        if self._bg_channel:
            if self.muted:
                pygame.mixer.pause()
            else:
                pygame.mixer.unpause()

# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------
SCREEN_W, SCREEN_H = 1280, 720
FPS = 60
TILE = 64
WORLD_W, WORLD_H = 4000, 4000

# Renkler
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
# Yardımcı
# ---------------------------------------------------------------------------
def lerp(a, b, t):
    return a + (b - a) * t

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])

def norm(dx, dy):
    d = math.hypot(dx, dy)
    if d == 0:
        return 0.0, 0.0
    return dx / d, dy / d

def angle_to(src, dst):
    return math.atan2(dst[1] - src[1], dst[0] - src[0])

# ---------------------------------------------------------------------------
# Procedural Art, Caching, Shadows, Masks & Environment VFX
# ---------------------------------------------------------------------------
_SHADOW_CACHE: Dict[Tuple[int, int, int], pygame.Surface] = {}
_TILE_CHUNK_CACHE: Dict[int, pygame.Surface] = {}
_VIGNETTE_CACHE: Optional[pygame.Surface] = None


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
    """Tạo mặt nạ silhouette trắng (pygame.mask.from_surface) khi nhận sát thương (100ms)."""
    try:
        mask = pygame.mask.from_surface(sprite_surf, 30)
        return mask.to_surface(setcolor=(255, 255, 255, 245), unsetcolor=(0, 0, 0, 0))
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


class AmbientParticle:
    """Hạt bụi ma thuật / tàn lửa trôi nổi trong môi trường Dark Fantasy."""
    __slots__ = ('x', 'y', 'vx', 'vy', 'size', 'alpha', 'color', 'phase')

    def __init__(self, cam_x=0.0, cam_y=0.0):
        self.x = cam_x + random.uniform(0, SCREEN_W)
        self.y = cam_y + random.uniform(0, SCREEN_H)
        self.vx = random.uniform(-0.35, 0.35)
        self.vy = random.uniform(-0.65, -0.15)
        self.size = random.choice([1, 2, 2, 3])
        self.alpha = random.randint(45, 135)
        self.color = random.choice([
            (255, 120, 50),   # tàn lửa đỏ cam
            (160, 90, 255),   # bụi hư không tím
            (70, 220, 255),   # tinh vân lam
            (255, 215, 90),   # bụi vàng cổ ngữ
        ])
        self.phase = random.uniform(0, math.tau)

    def update(self, cam_x: float, cam_y: float):
        self.phase += 0.04
        self.x += self.vx + math.sin(self.phase) * 0.2
        self.y += self.vy
        # Giữ hạt trong vùng camera
        if self.x < cam_x - 20:
            self.x += SCREEN_W + 40
        elif self.x > cam_x + SCREEN_W + 20:
            self.x -= SCREEN_W + 40
        if self.y < cam_y - 20:
            self.y += SCREEN_H + 40
        elif self.y > cam_y + SCREEN_H + 20:
            self.y -= SCREEN_H + 40

    def draw(self, surf: pygame.Surface, cam_x: float, cam_y: float):
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        if 0 <= sx < SCREEN_W and 0 <= sy < SCREEN_H:
            twinkle = int(self.alpha * (0.65 + 0.35 * math.sin(self.phase * 2.0)))
            r, g, b = self.color
            if self.size >= 2:
                glow = pygame.Surface((self.size * 4, self.size * 4), pygame.SRCALPHA)
                pygame.draw.circle(glow, (r, g, b, twinkle // 2),
                                   (self.size * 2, self.size * 2), self.size * 2)
                surf.blit(glow, (sx - self.size * 2, sy - self.size * 2))
            pygame.draw.circle(surf, (r, g, b), (sx, sy), self.size)


class ShockwaveRing:
    """Vòng sóng xung kích lan tỏa khi lên cấp hoặc thức tỉnh kỹ năng."""
    def __init__(self, x: float, y: float, color: tuple, max_radius: int = 220,
                 duration: int = 36, width: int = 5):
        self.x = float(x)
        self.y = float(y)
        self.color = color
        self.max_radius = max_radius
        self.duration = duration
        self.life = duration
        self.width = width

    def update(self) -> bool:
        self.life -= 1
        return self.life > 0

    def draw(self, surf: pygame.Surface, cam_x: float, cam_y: float):
        progress = 1.0 - (self.life / max(1, self.duration))
        # Ease-out cubic
        eased = 1.0 - (1.0 - progress) ** 3
        r = max(4, int(self.max_radius * eased))
        alpha = int(245 * (1.0 - progress))
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        if -r <= sx <= SCREEN_W + r and -r <= sy <= SCREEN_H + r:
            ring_s = pygame.Surface((r * 2 + 8, r * 2 + 8), pygame.SRCALPHA)
            w = max(1, int(self.width * (1.0 - progress * 0.6)))
            pygame.draw.circle(ring_s, (*self.color[:3], alpha), (r + 4, r + 4), r, w)
            if r > 12:
                pygame.draw.circle(ring_s, (255, 255, 255, alpha // 2),
                                   (r + 4, r + 4), max(2, r - 4), 1)
            surf.blit(ring_s, (sx - r - 4, sy - r - 4))


# ---------------------------------------------------------------------------
# Danh mục Trang Phục Anime Huyền Thoại (Anime Skins Catalog & VFX Twist)
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
        "primary": (255, 215, 40),     # Hào quang Ki vàng rực
        "secondary": (45, 215, 255),   # Tia Ki Kamehameha xanh lam
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
        "primary": (255, 145, 25),     # Chakra Cửu Vĩ cam hoàng kim
        "secondary": (105, 240, 255),  # Phong Độn Rasenshuriken
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
        "primary": (185, 70, 255),     # Hư Thức: Tử (Hollow Purple)
        "secondary": (45, 210, 255),   # Thuật Thức Thuận Chuyển: Thương (Blue)
        "vfx_primary": (185, 70, 255),
        "vfx_secondary": (45, 210, 255),
        "core": (255, 55, 105),        # Thuật Thức Nghịch Chuyển: Hách (Red)
    },
    {
        "id": "luffy",
        "name": "Vua Hải Tặc Thần Mặt Trời",
        "anime_tag": "One Piece — Luffy Gear 5 / Haki Bá Vương",
        "desc": "Mũ Rơm đeo sau lưng, tóc trắng phát sáng và dải mây thần Nika uốn lượn quanh vai cùng tia sét Haki Bá Vương.",
        "vfx_desc": "VFX: Sét Đen-Đỏ Haki Bá Vương & Mây Trắng Thần Nika",
        "cost": 450,
        "color": (245, 240, 255),
        "primary": (245, 240, 255),    # Mây trắng Thần Mặt Trời Nika
        "secondary": (255, 30, 65),    # Sét Đen-Đỏ Haki Bá Vương
        "vfx_primary": (245, 240, 255),
        "vfx_secondary": (255, 30, 65),
        "core": (255, 215, 85),
    },
]

ANIME_SKIN_BY_ID = {s["id"]: s for s in ANIME_SKINS}


def get_skin_cost(sdef: dict) -> int:
    """Giá Vàng an toàn của một trang phục: đọc "cost" hoặc "price", mặc định 0, không âm."""
    raw = sdef.get("cost", sdef.get("price", 0)) if isinstance(sdef, dict) else 0
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 0


def get_skin_vfx_colors(player, default_primary: tuple, default_secondary: tuple) -> Tuple[tuple, tuple]:
    """Trả về cặp màu (primary, secondary) đã biến đổi theo Trang Phục Anime đang mặc."""
    skin_id = getattr(player, "skin_id", "default") if player is not None else "default"
    if skin_id in ANIME_SKIN_BY_ID:
        s = ANIME_SKIN_BY_ID[skin_id]
        return s["primary"], s["secondary"]
    return default_primary, default_secondary


_ADDITIVE_GLOW_CACHE: Dict[Tuple[int, Tuple[int, int, int]], pygame.Surface] = {}


def draw_additive_glow(surf: pygame.Surface, sx: int, sy: int, radius: int,
                       color: tuple, intensity: float = 0.65) -> None:
    """Vẽ quầng sáng neon đa lớp sử dụng BLEND_RGB_ADD (được cache để giữ 60 FPS)."""
    radius = max(4, min(140, (int(radius) // 2) * 2))
    r, g, b = color[:3]
    cr = min(255, max(0, int(r * intensity)))
    cg = min(255, max(0, int(g * intensity)))
    cb = min(255, max(0, int(b * intensity)))
    key = (radius, (cr // 8 * 8, cg // 8 * 8, cb // 8 * 8))
    if key not in _ADDITIVE_GLOW_CACHE:
        if len(_ADDITIVE_GLOW_CACHE) > 256:
            _ADDITIVE_GLOW_CACHE.clear()
        gs = pygame.Surface((radius * 2, radius * 2))
        gs.fill((0, 0, 0))
        c = (radius, radius)
        pygame.draw.circle(gs, (key[1][0] // 3, key[1][1] // 3, key[1][2] // 3), c, radius)
        pygame.draw.circle(gs, (int(key[1][0] * 0.65), int(key[1][1] * 0.65), int(key[1][2] * 0.65)), c, int(radius * 0.62))
        pygame.draw.circle(gs, key[1], c, max(2, int(radius * 0.3)))
        _ADDITIVE_GLOW_CACHE[key] = gs
    glow_s = _ADDITIVE_GLOW_CACHE[key]
    surf.blit(glow_s, (sx - radius, sy - radius), special_flags=pygame.BLEND_RGB_ADD)


def draw_jagged_lightning_arc(
    surf: pygame.Surface,
    p1: Tuple[int, int],
    p2: Tuple[int, int],
    outer_color: tuple,
    core_color: tuple = C_WHITE,
    width: int = 3,
    branches: bool = True,
    dark_haki: bool = False,
) -> None:
    """Vẽ tia sét phân nhánh gấp khúc (Midpoint Displacement + Outer Glow)."""
    x1, y1 = p1
    x2, y2 = p2
    length = math.hypot(x2 - x1, y2 - y1)
    steps = max(4, min(9, int(length // 26) + 3))
    jitter = min(22, max(6, int(length * 0.11)))
    pts = [(x1, y1)]
    for i in range(1, steps):
        t = i / steps
        bx = int(x1 + (x2 - x1) * t + random.randint(-jitter, jitter))
        by = int(y1 + (y2 - y1) * t + random.randint(-jitter, jitter))
        pts.append((bx, by))
    pts.append((x2, y2))

    # Lớp hào quang ngoài của tia sét
    pygame.draw.lines(surf, outer_color[:3], False, pts, width + 3)
    if dark_haki:
        # Sét đen-đỏ Haki Bá Vương (One Piece Gear 5)
        pygame.draw.lines(surf, (18, 4, 12), False, pts, max(2, width))
    else:
        pygame.draw.lines(surf, core_color[:3], False, pts, max(1, width - 1))

    # Nhánh sét phụ (Side branches)
    if branches and len(pts) >= 4:
        for idx in range(1, len(pts) - 1, 2):
            bx, by = pts[idx]
            ang = math.atan2(y2 - y1, x2 - x1) + random.choice([-0.75, 0.75])
            blen = random.uniform(14, 30)
            b_mid = (int(bx + math.cos(ang) * (blen * 0.5) + random.randint(-5, 5)),
                     int(by + math.sin(ang) * (blen * 0.5) + random.randint(-5, 5)))
            b_end = (int(bx + math.cos(ang) * blen), int(by + math.sin(ang) * blen))
            pygame.draw.lines(surf, outer_color[:3], False, [(bx, by), b_mid, b_end], max(1, width - 1))


def draw_magic_circle(surf: pygame.Surface, sx: int, sy: int, radius: int,
                      color: tuple, angle: float, alpha: int = 165) -> None:
    """Vẽ vòng ma pháp hình học xoay tròn (Hexagram / Arcane Geometric Seal)."""
    if radius < 6 or sx + radius < 0 or sx - radius > SCREEN_W or sy + radius < 0 or sy - radius > SCREEN_H:
        return
    ms = pygame.Surface((radius * 2 + 6, radius * 2 + 6), pygame.SRCALPHA)
    c = (radius + 3, radius + 3)
    rgba = (*color[:3], clamp(alpha, 0, 255))
    pygame.draw.circle(ms, rgba, c, radius, 2)
    pygame.draw.circle(ms, (*C_WHITE, clamp(alpha // 2, 0, 255)), c, int(radius * 0.74), 1)
    # Hai tam giác lồng nhau tạo ngôi sao 6 cánh (Hexagram)
    for tri in (0.0, math.pi / 3.0):
        pts = [
            (c[0] + int(math.cos(angle + tri + k * (math.tau / 3)) * (radius - 2)),
             c[1] + int(math.sin(angle + tri + k * (math.tau / 3)) * (radius - 2)))
            for k in range(3)
        ]
        pygame.draw.polygon(ms, rgba, pts, 1)
    surf.blit(ms, (sx - radius - 3, sy - radius - 3))


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
            "warrior": (230, 45, 65),
            "mage":    (175, 85, 255),
            "rogue":   (40, 245, 170),
            "paladin": (255, 215, 75),
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
            fr = (r + 12) + int(math.sin(tick * 0.35 + fi * 1.7) * 5)
            flame_pts.append((cx + int(math.cos(fa) * (fr * 0.85)), cy - 4 + int(math.sin(fa) * (fr * 1.15))))
        pygame.draw.polygon(char_surf, (255, 215, 35, 75), flame_pts)
        pygame.draw.polygon(char_surf, (255, 245, 130, 175), flame_pts, 2)
        # Đám mây Cân Đẩu Vân vàng dưới chân (Flying Nimbus)
        for c_off in (-10, 0, 10):
            pygame.draw.circle(char_surf, (255, 220, 65, 210), (cx + c_off, cy + r - 1), 7)
        # Giày võ thuật xanh lam & Võ phục cam-xanh (Orange/Blue Martial Arts Gi)
        pygame.draw.ellipse(char_surf, (25, 75, 185), (cx - 9, cy + r - 6 + int(leg_swing), 7, 9))
        pygame.draw.ellipse(char_surf, (25, 75, 185), (cx + 2, cy + r - 6 - int(leg_swing), 7, 9))
        pygame.draw.rect(char_surf, (245, 105, 20), (cx - r + 2, cy - 5, (r - 2) * 2, r + 4), border_radius=5)
        # Áo lót & đai lưng xanh lam
        pygame.draw.polygon(char_surf, (25, 85, 205), [(cx - 6, cy - 5), (cx + 6, cy - 5), (cx, cy + 3)])
        pygame.draw.rect(char_surf, (20, 65, 175), (cx - r + 2, cy + 4, (r - 2) * 2, 4))
        # Khuôn mặt & Mắt xanh ngọc Super Saiyan
        pygame.draw.circle(char_surf, (245, 200, 165), (cx, cy - 10), r - 5)
        pygame.draw.line(char_surf, (40, 235, 215), (cx - 5 + face_x, cy - 10 + face_y), (cx - 1 + face_x, cy - 9 + face_y), 3)
        pygame.draw.line(char_surf, (40, 235, 215), (cx + 1 + face_x, cy - 9 + face_y), (cx + 5 + face_x, cy - 10 + face_y), 3)
        # Mái tóc dựng đứng vàng kim Super Saiyan huyền thoại (Iconic Spiky Golden Hair)
        hair_spikes = [
            [(cx - 9, cy - 13), (cx - 22, cy - 19), (cx - 6, cy - 19)],
            [(cx - 7, cy - 15), (cx - 17, cy - 30), (cx - 2, cy - 21)],
            [(cx - 4, cy - 17), (cx - 3, cy - 36), (cx + 4, cy - 17)],
            [(cx + 2, cy - 21), (cx + 16, cy - 31), (cx + 7, cy - 15)],
            [(cx + 6, cy - 19), (cx + 22, cy - 19), (cx + 9, cy - 13)],
        ]
        for sp in hair_spikes:
            pygame.draw.polygon(char_surf, (255, 225, 45), sp)
            pygame.draw.polygon(char_surf, (255, 250, 175), sp, 1)
        # Quả cầu Kamehameha xanh lam tụ lực ở tay
        kx, ky = cx + int(aim_cos * 14), cy + int(aim_sin * 12)
        pygame.draw.circle(char_surf, (40, 200, 255, 180), (kx, ky), 7)
        pygame.draw.circle(char_surf, C_WHITE, (kx, ky), 4)

    elif skin_id == "naruto":
        # 2. NINJA LÀNG LÁ - CỬU VĨ (Naruto — Six Paths / Kurama Mode)
        # 6 Cầu Đạo Ngọc (Truth-Seeking Orbs) bay lơ lửng thành vòng tròn phía sau lưng
        for oi in range(6):
            oa = tick * 0.05 + oi * (math.tau / 6)
            ox = cx + int(math.cos(oa) * (r + 10))
            oy = cy - 6 + int(math.sin(oa) * (r + 8))
            pygame.draw.circle(char_surf, (15, 12, 22), (ox, oy), 4)
            pygame.draw.circle(char_surf, (255, 175, 45), (ox, oy), 4, 1)
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
        # Thân áo Chakra vàng cam với họa tiết Lục Đạo câu ngọc đen (Black Magatama markings)
        pygame.draw.rect(char_surf, (255, 155, 25), (cx - r + 2, cy - 5, (r - 2) * 2, r + 4), border_radius=5)
        pygame.draw.line(char_surf, (20, 18, 25), (cx, cy - 4), (cx, cy + r - 2), 3)
        for mx_off in (-6, 0, 6):
            pygame.draw.circle(char_surf, (20, 18, 25), (cx + mx_off, cy - 1), 2)
        # Đầu, Băng trán Ninja Làng Lá & Râu Cửu Vĩ
        pygame.draw.circle(char_surf, (250, 205, 170), (cx, cy - 10), r - 5)
        pygame.draw.rect(char_surf, (35, 40, 55), (cx - 10, cy - 16, 20, 5), border_radius=2)
        pygame.draw.rect(char_surf, (200, 210, 225), (cx - 6, cy - 15, 12, 3))
        # Mắt Tiên Nhân Cửu Vĩ vàng cam
        pygame.draw.circle(char_surf, (255, 190, 30), (cx - 4 + face_x, cy - 9 + face_y), 2)
        pygame.draw.circle(char_surf, (255, 190, 30), (cx + 4 + face_x, cy - 9 + face_y), 2)
        # Tóc vàng nhọn + 2 sừng Chakra Lục Đạo
        for sx_h in (-8, -4, 0, 4, 8):
            pygame.draw.polygon(char_surf, (255, 220, 45), [(cx + sx_h - 3, cy - 15), (cx + sx_h, cy - 26), (cx + sx_h + 3, cy - 15)])
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
        # Đồng phục Chú Thuật Sư cổ cao màu đen tím than
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
        # Mái tóc bạch kim dựng ngược (Spiky White Hair)
        for sx_h in (-9, -5, 0, 5, 9):
            pygame.draw.polygon(char_surf, (245, 248, 255), [
                (cx + sx_h - 4, cy - 14),
                (cx + sx_h + int(sway_x * 2), cy - 28 - (3 if sx_h == 0 else 0)),
                (cx + sx_h + 4, cy - 14),
            ])
        # Hai quả cầu Chú Lực: Thương (Xanh) & Hách (Đỏ) xoay quanh hai tay
        bx_orb = cx + int(math.cos(angle - 0.5) * 16)
        by_orb = cy + int(math.sin(angle - 0.5) * 14)
        rx_orb = cx + int(math.cos(angle + 0.5) * 16)
        ry_orb = cy + int(math.sin(angle + 0.5) * 14)
        pygame.draw.circle(char_surf, (35, 195, 255), (bx_orb, by_orb), 5)
        pygame.draw.circle(char_surf, C_WHITE, (bx_orb, by_orb), 2)
        pygame.draw.circle(char_surf, (255, 45, 85), (rx_orb, ry_orb), 5)
        pygame.draw.circle(char_surf, C_WHITE, (rx_orb, ry_orb), 2)

    elif skin_id == "luffy":
        # 4. VUA HẢI TẶC THẦN MẶT TRỜI (One Piece — Luffy Gear 5 Nika)
        # Dải lụa mây trắng Thần Mặt Trời Nika bay uốn lượn quanh vai (Cloud Scarf / Hagoromo)
        for ci in range(7):
            ca = -math.pi * 0.85 + (math.pi * 0.7 * ci / 6.0)
            cloud_x = cx + int(math.cos(ca) * (r + 8)) + int(sway_x * 3)
            cloud_y = cy - 6 + int(math.sin(ca) * (r + 7))
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
        # Mái tóc mây trắng bồng bềnh phát sáng (Glowing White Cloud Hair)
        for hx_off, hy_off, hr in [(-7, -18, 6), (0, -21, 7), (7, -18, 6), (-3, -24, 5), (4, -23, 5)]:
            pygame.draw.circle(char_surf, (255, 255, 255), (cx + hx_off, cy + hy_off), hr)
        # Tia sét Đen-Đỏ Haki Bá Vương nổ quanh tay (Conqueror's Haki Lightning)
        hx_w, hy_w = cx + int(aim_cos * 14), cy + int(aim_sin * 12)
        pygame.draw.line(char_surf, (255, 25, 60), (cx, cy), (hx_w, hy_w), 4)
        pygame.draw.line(char_surf, (20, 5, 12), (cx, cy), (hx_w, hy_w), 2)

    else:
        # =====================================================================
        # NGOẠI HÌNH MẶC ĐỊNH THEO 4 HỆ PHÁI RPG (DEFAULT CLASS OUTLOOK)
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


# ---------------------------------------------------------------------------
# Particle (Hỗ trợ tia lửa định hướng & lõi sáng rực)
# ---------------------------------------------------------------------------
class Particle:
    __slots__ = ('x', 'y', 'vx', 'vy', 'life', 'max_life', 'color', 'size', 'dir_spark')

    def __init__(self, x, y, color, speed=2.0, size=4, life=30, angle=None, spread=0.45):
        self.x, self.y = float(x), float(y)
        ang = angle + random.uniform(-spread, spread) if angle is not None else random.uniform(0, math.tau)
        s = random.uniform(speed * 0.45, speed * 1.15)
        self.vx = math.cos(ang) * s
        self.vy = math.sin(ang) * s
        self.life = life
        self.max_life = life
        self.color = color
        self.size = size
        self.dir_spark = angle is not None

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vx *= 0.91
        self.vy *= 0.91
        self.life -= 1
        return self.life > 0

    def draw(self, surf, cam_x, cam_y):
        t = self.life / max(1, self.max_life)
        r, g, b = self.color[:3]
        s = max(1, int(self.size * t))
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        if -12 < sx < SCREEN_W + 12 and -12 < sy < SCREEN_H + 12:
            if self.dir_spark and t > 0.35:
                tx = int(sx - self.vx * 2.4)
                ty = int(sy - self.vy * 2.4)
                pygame.draw.line(surf, (r, g, b), (tx, ty), (sx, sy), max(1, s))
                pygame.draw.circle(surf, C_WHITE, (sx, sy), max(1, s // 2))
            else:
                pygame.draw.circle(surf, (r, g, b), (sx, sy), s)
                if s >= 3:
                    pygame.draw.circle(surf, C_WHITE, (sx, sy), max(1, s // 2))


# ---------------------------------------------------------------------------
# DamageNumber (Trắng: Thường | Vàng/Đỏ lớn + '!': Chí mạng | Xanh lá '+HP': Hồi máu)
# ---------------------------------------------------------------------------
class DamageNumber:
    def __init__(self, x, y, value, color=C_WHITE, scale=1.0, life=48,
                 is_crit: bool = False, is_heal: bool = False,
                 text_override: Optional[str] = None):
        self.x = float(x) + random.uniform(-6, 6)
        self.y = float(y)
        self.is_crit = is_crit
        self.is_heal = is_heal
        if text_override is not None:
            self.value = text_override
            scale = max(scale, 1.18)
        elif is_heal:
            val_str = str(value)
            if not val_str.startswith("+"):
                val_str = f"+{val_str}"
            if "HP" not in val_str.upper():
                val_str = f"{val_str} HP"
            self.value = val_str
            if color == C_WHITE:
                color = (85, 255, 130)
            scale = max(scale, 1.15)
        elif is_crit:
            val_str = str(value)
            if not val_str.endswith("!"):
                val_str = f"{val_str}!"
            self.value = val_str
            if color == C_WHITE:
                color = (255, 225, 55)
            scale = max(scale, 1.38)
        else:
            self.value = value
        self.vx = random.uniform(-0.45, 0.45)
        self.vy = -1.75 if scale <= 1.05 else -2.35
        self.life = life
        self.max_life = life
        self.color = color
        self.scale = scale

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vx *= 0.94
        self.vy *= 0.94
        self.life -= 1
        return self.life > 0

    def draw(self, surf, cam_x, cam_y, font):
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        if sx < -80 or sx > SCREEN_W + 80 or sy < -40 or sy > SCREEN_H + 40:
            return
        alpha = clamp(int(self.life / max(1, self.max_life) * 255), 0, 255)
        text = font.render(str(self.value), True, self.color)
        shadow = font.render(str(self.value), True, (12, 8, 22))
        if self.scale > 1.05:
            w = max(8, int(text.get_width() * self.scale))
            h = max(8, int(text.get_height() * self.scale))
            text = pygame.transform.smoothscale(text, (w, h))
            shadow = pygame.transform.smoothscale(shadow, (w, h))
        text.set_alpha(alpha)
        shadow.set_alpha(alpha)
        surf.blit(shadow, (sx - text.get_width() // 2 + 2, sy + 2))
        surf.blit(text, (sx - text.get_width() // 2, sy))


# ---------------------------------------------------------------------------
# Vũ khí & Kỹ năng chủ động (Multi-Layered Glow, Ribbon Trails & Magic Circles)
# ---------------------------------------------------------------------------
class Projectile:
    def __init__(self, x, y, angle, speed, damage, lifetime, color, size=6,
                 pierce=1):
        self.x, self.y = float(x), float(y)
        self.angle = angle
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.damage = damage
        self.life = lifetime
        self.max_life = lifetime
        self.color = color
        self.size = size
        self.pierce = pierce
        self.hit_set: set = set()
        self.alive = True
        self.is_enemy = False
        self.trail: List[Tuple[float, float]] = []

    def update(self):
        self.trail.append((self.x, self.y))
        if len(self.trail) > 6:
            self.trail.pop(0)
        self.x += self.vx
        self.y += self.vy
        self.life -= 1
        if self.life <= 0:
            self.alive = False

    def draw(self, surf, cam_x, cam_y):
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        if -30 < sx < SCREEN_W + 30 and -30 < sy < SCREEN_H + 30:
            r, g, b = self.color[:3]
            # Vẽ đuôi ánh sáng chuyển động (Glowing Motion Ribbon Trail)
            if not self.is_enemy and len(self.trail) >= 2:
                for idx, (tx, ty) in enumerate(self.trail):
                    tsx, tsy = int(tx - cam_x), int(ty - cam_y)
                    tr_r = max(1, int(self.size * (idx + 1) / (len(self.trail) + 1)))
                    pygame.draw.circle(surf, (r // 2, g // 2, b // 2), (tsx, tsy), tr_r)
                # Vòng ma pháp nhỏ khi vừa khai hỏa (Magic Circle on Firing)
                age = self.max_life - self.life
                if age < 10:
                    ox, oy = int(self.trail[0][0] - cam_x), int(self.trail[0][1] - cam_y)
                    draw_magic_circle(surf, ox, oy, 14 + age, self.color, age * 0.25, 180 - age * 16)

            draw_additive_glow(surf, sx, sy, self.size * 3, self.color, 0.55)
            pygame.draw.circle(surf, self.color, (sx, sy), self.size)
            pygame.draw.circle(surf, C_WHITE, (sx, sy), max(2, self.size // 2))


def deal_player_damage(player, enemy, base_damage: int, damage_numbers: list,
                       default_color: tuple) -> int:
    """
    Tính toán sát thương của người chơi kèm hiệu ứng Chữ Nổi Chiến Đấu (Combat Juice):
      - Đòn đánh thường: Chữ trắng rõ nét (White normal hit)
      - Đòn chí mạng (Crit): Chữ Vàng/Đỏ phóng lớn kèm dấu '!' + rung màn hình vi mô
      - Hồi máu: Chữ Xanh lá '+HP'
    """
    dmg = int(base_damage * getattr(player, "damage_mult", 1.0))
    is_crit = False
    crit_chance = getattr(player, "crit_chance", 0.0)
    if crit_chance > 0 and random.random() < crit_chance:
        dmg = int(dmg * 2.0)
        is_crit = True
    enemy.take_damage(dmg)
    if is_crit:
        crit_col = (255, 85, 65) if random.random() < 0.4 else (255, 235, 55)
        damage_numbers.append(DamageNumber(enemy.x, enemy.y - 10, f"{dmg}!", crit_col, scale=1.35, life=54))
        if player is not None:
            player.micro_shake = max(getattr(player, "micro_shake", 0), 3)
    else:
        damage_numbers.append(DamageNumber(enemy.x, enemy.y - 4, dmg, C_WHITE, scale=1.0, life=42))
    # Nội tại Huyết Kiếm Sĩ: Hút máu khi kết liễu kẻ địch
    if not enemy.alive and getattr(player, "lifesteal_on_kill", 0) > 0:
        heal = player.lifesteal_on_kill
        if player.hp < player.max_hp:
            player.hp = min(player.max_hp, player.hp + heal)
            damage_numbers.append(DamageNumber(player.x, player.y - 24, f"+{heal} HP", C_GREEN, scale=1.1))
    return dmg


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
                    deal_player_damage(player, e, self.damage, damage_numbers, col)
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
                            deal_player_damage(player, e, b.damage, damage_numbers, b.color)
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
                            dealt = deal_player_damage(player, e, int(self.damage * (1.35 if self.fused else 1.0)), damage_numbers, col)
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
            slash_s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
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
                    deal_player_damage(player, e, max(4, self.damage // 3), damage_numbers, col)

        # Khi Hợp Nhất (Cosmic Tempest): Phóng sét chuỗi liên tục từ Hố Đen
        if self.fused and self.life % 14 == 0:
            nearby = [e for e in enemies if e.alive and dist((self.x, self.y), (e.x, e.y)) < self.pull_radius * 1.45]
            nearby.sort(key=lambda e: dist((self.x, self.y), (e.x, e.y)))
            for t_e in nearby[:4]:
                self.lightning_arcs.append(((self.x, self.y), (t_e.x, t_e.y)))
                deal_player_damage(player, t_e, int(self.damage * 0.65), damage_numbers, sub_col)

        # Phát nổ Arcane Nova khi hết thời gian tồn tại
        if self.life <= 0:
            self.nova_timer = 16
            nova_col, _ = get_skin_vfx_colors(player, (255, 215, 80) if self.fused else (195, 95, 255), (110, 235, 255))
            hit_cnt = 0
            for e in enemies:
                if e.alive and dist((self.x, self.y), (e.x, e.y)) < self.pull_radius * 1.15 + e.radius:
                    deal_player_damage(player, e, int(self.damage * 1.8), damage_numbers, nova_col)
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
                        deal_player_damage(player, sub_e, self.damage, damage_numbers, self.col)
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
                    deal_player_damage(player, e, self.damage, damage_numbers, col)
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
                        deal_player_damage(player, e, self.damage, damage_numbers, col)
                        # Giáng cột sáng Thánh Phạt (Holy Smite Beam) tại vị trí va chạm
                        self.smite_beams.append((e.x, e.y, 14))
                        for sub_e in enemies:
                            if sub_e.alive and dist((e.x, e.y), (sub_e.x, sub_e.y)) < (65 if self.fused else 45):
                                deal_player_damage(player, sub_e, max(6, self.damage // 2), damage_numbers, sub_col)
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
                    deal_player_damage(player, e, self.damage, damage_numbers, col)
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
                    deal_player_damage(player, e, self.damage, damage_numbers, col)
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
                deal_player_damage(player, e, self.damage, damage_numbers, col)
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
            deal_player_damage(player, nxt, int(self.damage * 0.7), damage_numbers, sub_col)
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
                deal_player_damage(player, e, self.damage, damage_numbers, col)
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
# Hệ thống Nâng cấp & Hợp Nhất Kỹ Năng (Skill Synergy & Mythic Fusion)
# ---------------------------------------------------------------------------
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
    """Trả về dòng gợi ý công thức Hợp Nhất cho kỹ năng trên thẻ Level-Up."""
    names = STRINGS[LANG]["upgrade_names"]
    for a, b, fus in FUSION_RECIPES:
        if ut == a:
            return f"★ Hợp nhất: + {names[b.name]} Lv5 ➔ {names[fus.name]}"
        if ut == b:
            return f"★ Hợp nhất: + {names[a.name]} Lv5 ➔ {names[fus.name]}"
        if ut == fus:
            return f"★ {names[a.name]} Lv5 + {names[b.name]} Lv5 ★"
    return ""

# ---------------------------------------------------------------------------
# Düşman tipleri
# ---------------------------------------------------------------------------
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
    return 1.0 + max(0, wave) * 0.09

def enemy_damage_multiplier(wave: int) -> float:
    return 1.0 + max(0, wave) * 0.02

class Enemy:
    def __init__(self, x, y, etype: EnemyType, wave: int):
        self.x, self.y = float(x), float(y)
        self.etype = etype
        self.wave = wave
        d = ENEMY_DEFS[etype]
        self.max_hp = int(d['hp'] * enemy_hp_multiplier(wave))
        self.hp     = self.max_hp
        self.speed  = d['speed']
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
        self.hp -= amount
        self.hit_flash = 6  # 100ms @ 60 FPS
        self.squash_timer = 8
        self.kbx += random.uniform(-2, 2)
        self.kby += random.uniform(-2, 2)
        if self.hp <= 0:
            self.alive = False

    def update(self, player, projectiles_out, summoned_out=None):
        self.anim_phase += 0.18
        if self.squash_timer > 0:
            self.squash_timer -= 1

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

        if self.etype == EnemyType.EXPLODER:
            if self.exploder_armed:
                effective_speed = 0.0
                self.exploder_fuse -= 1
                if self.exploder_fuse <= 0:
                    if d <= 90 + player.radius:
                        player.take_damage(20)
                    self.alive = False
            elif d <= 80:
                self.exploder_armed = True
                self.exploder_fuse = FPS
                effective_speed = 0.0

        if d > 0 and effective_speed > 0:
            vx = (dx / d) * effective_speed
            vy = (dy / d) * effective_speed
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

        bob = int(math.sin(self.anim_phase) * 2.2)
        canvas_s = r * 2 + 24
        esurf = pygame.Surface((canvas_s, canvas_s), pygame.SRCALPHA)
        ecx, ecy = canvas_s // 2, canvas_s // 2

        if self.etype == EnemyType.EXPLODER and self.exploder_armed and (self.exploder_fuse // 6) % 2 == 0:
            base_c = (255, 50, 50)
        elif self.frozen_timer > 0:
            base_c = C_ICE
        elif self.burn_timer > 0 and (self.burn_timer // 5) % 2 == 0:
            base_c = (255, 130, 40)
        elif self.slow_timer > 0:
            base_c = tuple(int(c * 0.7 + 130 * 0.3) for c in self.color)
        else:
            base_c = self.color

        dark_c = tuple(max(0, int(c * 0.52)) for c in base_c)
        eye_off = 2 if self.vx_last >= 0 else -2

        # Vẽ chi tiết 4 nguyên mẫu Quái Vật Dark Fantasy (Multi-layered procedural sprites)
        if self.etype in (EnemyType.TANK, EnemyType.EXPLODER):
            # 4. Hiệp Sĩ Hắc Ám (Dark Knight - Elite): Giáp sắt đen nặng, mũ sừng, khiên chắn & cổ ngữ tím phát sáng
            armor_dark = (26, 24, 34) if self.frozen_timer <= 0 else dark_c
            armor_mid = (46, 42, 62) if self.frozen_timer <= 0 else base_c
            rune_col = (195, 75, 255) if self.etype == EnemyType.TANK else (255, 85, 55)
            # Thân giáp tấm
            pygame.draw.rect(esurf, armor_dark, (ecx - r + 2, ecy - r + 4, (r - 2) * 2, (r - 2) * 2), border_radius=5)
            pygame.draw.rect(esurf, armor_mid, (ecx - r + 4, ecy - r + 6, (r - 4) * 2, (r - 4) * 2), border_radius=4)
            pygame.draw.rect(esurf, (150, 145, 175), (ecx - r + 2, ecy - r + 4, (r - 2) * 2, (r - 2) * 2), 2, border_radius=5)
            # Mũ sắt có sừng nhọn (Horned Helmet)
            pygame.draw.polygon(esurf, (175, 170, 195), [(ecx - r + 3, ecy - r + 6), (ecx - r - 5, ecy - r - 5), (ecx - 4, ecy - r + 4)])
            pygame.draw.polygon(esurf, (175, 170, 195), [(ecx + r - 3, ecy - r + 6), (ecx + r + 5, ecy - r - 5), (ecx + 4, ecy - r + 4)])
            # Khiên chắn bên tay trái & cổ ngữ phát sáng ở ngực
            sh_x = ecx - r - 2 if self.vx_last < 0 else ecx + r - 7
            pygame.draw.rect(esurf, (32, 28, 44), (sh_x, ecy - 4, 9, 14), border_radius=3)
            pygame.draw.rect(esurf, rune_col, (sh_x, ecy - 4, 9, 14), 1, border_radius=3)
            pygame.draw.line(esurf, rune_col, (ecx, ecy - 3), (ecx, ecy + 7), 2)
            pygame.draw.line(esurf, rune_col, (ecx - 4, ecy + 2), (ecx + 4, ecy + 2), 2)
            # Đôi mắt đỏ/tím sau khe mũ giáp
            pygame.draw.circle(esurf, (255, 65, 95), (ecx - 4 + eye_off, ecy - 4), 2)
            pygame.draw.circle(esurf, (255, 65, 95), (ecx + 4 + eye_off, ecy - 4), 2)

        elif self.etype in (EnemyType.RANGED, EnemyType.NECROMANCER):
            # 3. Hồn Ma Ác Quỷ (Wraith/Ghost): Áo choàng bóng ma bán trong suốt, hạt linh hồn bay theo & mắt xanh lam rực sáng
            wisp_col = (80, 235, 255) if self.etype == EnemyType.RANGED else (195, 95, 255)
            cloak_rgba = (*dark_c, 185)
            inner_rgba = (*base_c, 210)
            wave_tail = int(math.sin(self.anim_phase * 1.8) * 3)
            # Áo choàng ma quái tua rua phía dưới
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
            # Hốc mũ trùm tối thẫm
            pygame.draw.circle(esurf, (14, 10, 24, 235), (ecx + eye_off // 2, ecy - 3), max(5, r // 2))
            # Hạt linh hồn trôi nổi quanh thân (trailing ghostly particles)
            for wi in range(2):
                wa = self.anim_phase * 1.4 + wi * math.pi
                wx = ecx + int(math.cos(wa) * (r + 3))
                wy = ecy + int(math.sin(wa) * (r * 0.6)) + 3
                pygame.draw.circle(esurf, (*wisp_col, 175), (wx, wy), 2)
            # Mắt xanh cyan phát sáng
            pygame.draw.circle(esurf, wisp_col, (ecx - 3 + eye_off, ecy - 4), 2)
            pygame.draw.circle(esurf, wisp_col, (ecx + 3 + eye_off, ecy - 4), 2)

        elif self.etype in (EnemyType.FAST, EnemyType.RUNNER):
            # 2. Dơi Hút Máu (Vampire Bat): Đôi cánh dơi tím đen vỗ liên tục & răng nanh đỏ rực
            flap = int(math.sin(self.anim_phase * 2.8) * (r * 0.75))
            wing_c = (68, 22, 95) if self.frozen_timer <= 0 else dark_c
            wing_edge = (145, 50, 185) if self.frozen_timer <= 0 else base_c
            # Cánh trái & cánh phải vỗ theo nhịp sin
            l_wing = [(ecx - 3, ecy), (ecx - r - 7, ecy - 5 - flap), (ecx - r - 2, ecy + 5 - flap // 2), (ecx - 4, ecy + 4)]
            r_wing = [(ecx + 3, ecy), (ecx + r + 7, ecy - 5 - flap), (ecx + r + 2, ecy + 5 - flap // 2), (ecx + 4, ecy + 4)]
            pygame.draw.polygon(esurf, wing_c, l_wing)
            pygame.draw.polygon(esurf, wing_edge, l_wing, 1)
            pygame.draw.polygon(esurf, wing_c, r_wing)
            pygame.draw.polygon(esurf, wing_edge, r_wing, 1)
            # Thân dơi & đôi tai nhọn
            pygame.draw.circle(esurf, (38, 16, 52), (ecx, ecy), max(5, r - 2))
            pygame.draw.polygon(esurf, (58, 22, 78), [(ecx - 5, ecy - 5), (ecx - 7, ecy - r - 3), (ecx - 1, ecy - 6)])
            pygame.draw.polygon(esurf, (58, 22, 78), [(ecx + 5, ecy - 5), (ecx + 7, ecy - r - 3), (ecx + 1, ecy - 6)])
            # Mắt đỏ máu & 2 chiếc răng nanh sắc nhọn
            pygame.draw.circle(esurf, (255, 40, 60), (ecx - 3 + eye_off // 2, ecy - 2), 2)
            pygame.draw.circle(esurf, (255, 40, 60), (ecx + 3 + eye_off // 2, ecy - 2), 2)
            pygame.draw.line(esurf, (255, 230, 230), (ecx - 2, ecy + 2), (ecx - 2, ecy + 5), 1)
            pygame.draw.line(esurf, (255, 230, 230), (ecx + 2, ecy + 2), (ecx + 2, ecy + 5), 1)

        else:
            # 1. Bộ Xương Khô (Skeleton Warrior - BASIC / SUMMONED_MINION): Khung xương sườn, đầu lâu, thanh kiếm rỉ sét & dáng đi lắc lư
            bone_c = (220, 215, 200) if self.frozen_timer <= 0 else base_c
            bone_shadow = (145, 138, 125) if self.frozen_timer <= 0 else dark_c
            rattle = int(math.sin(self.anim_phase * 2.2) * 1.5)
            # Khung xương sườn (Ribcage)
            pygame.draw.line(esurf, bone_shadow, (ecx, ecy - 2), (ecx, ecy + r - 2), 3)
            for ry_off in (0, 4, 8):
                pygame.draw.line(esurf, bone_c, (ecx - 6, ecy + ry_off), (ecx + 6, ecy + ry_off), 2)
            # Đầu lâu (Skull head)
            pygame.draw.circle(esurf, bone_c, (ecx + rattle, ecy - 5), max(6, r - 5))
            pygame.draw.circle(esurf, bone_shadow, (ecx + rattle, ecy - 5), max(6, r - 5), 1)
            pygame.draw.rect(esurf, bone_c, (ecx - 3 + rattle, ecy - 1, 6, 4))
            # Hốc mắt đỏ/lục tối
            eye_c = (255, 65, 50) if self.etype == EnemyType.BASIC else (120, 255, 140)
            pygame.draw.circle(esurf, (20, 15, 22), (ecx - 3 + rattle + eye_off // 2, ecy - 6), 2)
            pygame.draw.circle(esurf, (20, 15, 22), (ecx + 3 + rattle + eye_off // 2, ecy - 6), 2)
            pygame.draw.circle(esurf, eye_c, (ecx - 3 + rattle + eye_off // 2, ecy - 6), 1)
            pygame.draw.circle(esurf, eye_c, (ecx + 3 + rattle + eye_off // 2, ecy - 6), 1)
            # Thanh kiếm sắt rỉ sét cầm trên tay (Rusty sword)
            sw_dir = 1 if self.vx_last >= 0 else -1
            sx_hand = ecx + sw_dir * 7
            sy_hand = ecy + 2
            pygame.draw.line(esurf, (135, 90, 65), (sx_hand, sy_hand), (sx_hand + sw_dir * 7, sy_hand - 9 + bob), 3)
            pygame.draw.line(esurf, (185, 175, 165), (sx_hand, sy_hand), (sx_hand + sw_dir * 7, sy_hand - 9 + bob), 1)

        # Squash & Stretch khi nhận sát thương
        if self.squash_timer > 0:
            sq = 1.0 + 0.18 * math.sin(self.squash_timer * 0.6)
            w = max(8, int(canvas_s * sq))
            h = max(8, int(canvas_s / sq))
            esurf = pygame.transform.smoothscale(esurf, (w, h))

        # Mặt nạ silhouette trắng (100ms Hit Flash)
        if self.hit_flash > 0:
            esurf = apply_hit_flash_mask(esurf)

        rect = esurf.get_rect(center=(sx, sy + bob))
        surf.blit(esurf, rect.topleft)

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
class XPGem:
    def __init__(self, x, y, value):
        self.x, self.y = float(x), float(y)
        self.value = value
        self.alive = True
        self.bob = random.uniform(0, math.tau)
        self.magnetized = False
        self.trail: List[Tuple[float, float]] = []

    def update(self, player):
        self.bob += 0.08
        d = dist((self.x, self.y), (player.x, player.y))
        if self.magnetized or d < player.pickup_radius:
            if self.magnetized:
                self.trail.append((self.x, self.y))
                if len(self.trail) > 6:
                    self.trail.pop(0)
            dx, dy = norm(player.x - self.x, player.y - self.y)
            pull_spd = 15.5 if self.magnetized else 6.8
            self.x += dx * pull_spd
            self.y += dy * pull_spd
        if d < player.radius + 14:
            self.alive = False
            return self.value
        return 0

    def draw(self, surf, cam_x, cam_y, tick):
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y + math.sin(self.bob) * 3)
        if -24 < sx < SCREEN_W + 24 and -24 < sy < SCREEN_H + 24:
            if self.magnetized and len(self.trail) >= 2:
                for i in range(len(self.trail) - 1):
                    p1 = (int(self.trail[i][0] - cam_x), int(self.trail[i][1] - cam_y))
                    p2 = (int(self.trail[i + 1][0] - cam_x), int(self.trail[i + 1][1] - cam_y))
                    pygame.draw.line(surf, (80, 255, 220), p1, p2, max(1, i))
            sh = get_drop_shadow(10, 5, 70)
            surf.blit(sh, (sx - 5, int(self.y - cam_y) + 6))
            pygame.draw.polygon(surf, C_GREEN,
                                [(sx, sy - 8), (sx + 6, sy), (sx, sy + 8), (sx - 6, sy)])
            pygame.draw.polygon(surf, (180, 255, 200),
                                [(sx, sy - 5), (sx + 3, sy), (sx, sy + 5), (sx - 3, sy)])
            pygame.draw.polygon(surf, C_WHITE,
                                [(sx, sy - 8), (sx + 6, sy), (sx, sy + 8), (sx - 6, sy)], 1)


# ---------------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------------
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
        self.unlocked_fusions: set = set()

        self.angle = 0.0

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
        }
        return mapping.get(ut)

    @property
    def speed(self):
        mult = 2.1 if self.dash_timer > 0 else 1.0
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
        if self.invincible > 0 or self.dash_timer > 0:
            return
        dmg = max(1, amount - self.armor)
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

        # Hào quang Hồi Máu (Rising Green/Crimson Heal Aura khi nhặt Bình Máu)
        if self.heal_aura_timer > 0:
            t_ratio = self.heal_aura_timer / 38.0
            draw_additive_glow(surf, sx, sy, int(36 * (1.2 - 0.3 * t_ratio)), (80, 255, 130), intensity=0.55 * t_ratio)
            aura_s = pygame.Surface((64, 64), pygame.SRCALPHA)
            rise = int((1.0 - t_ratio) * 22)
            pygame.draw.circle(aura_s, (80, 255, 140, int(190 * t_ratio)), (32, 36 - rise // 2), 22, 2)
            pygame.draw.circle(aura_s, (255, 70, 95, int(160 * t_ratio)), (32, 32 - rise // 3), 16, 2)
            for c_i in range(3):
                cx_p = 18 + c_i * 14
                cy_p = 42 - rise - (c_i % 2) * 8
                pygame.draw.line(aura_s, (100, 255, 150, int(230 * t_ratio)), (cx_p - 4, cy_p), (cx_p + 4, cy_p), 2)
                pygame.draw.line(aura_s, (100, 255, 150, int(230 * t_ratio)), (cx_p, cy_p - 4), (cx_p, cy_p + 4), 2)
            surf.blit(aura_s, (sx - 32, sy - 32))


# ---------------------------------------------------------------------------
# Upgrade UI
# ---------------------------------------------------------------------------
class UpgradeScreen:
    def __init__(self, available, player=None):
        self.player = player
        self.hovered = None
        self.font_big  = get_sys_font(23, bold=True)
        self.font_med  = get_sys_font(15)
        self.font_sm   = get_sys_font(14, bold=True)
        self.font_hint = get_sys_font(12, bold=True)

        # Kiểm tra các Kỹ Năng Hợp Nhất Thần Thoại đủ điều kiện (2 kỹ năng thành phần đều >= Lv5)
        ready_fusions = []
        if player is not None:
            for a, b, fus in FUSION_RECIPES:
                if fus not in player.unlocked_fusions:
                    wa = player.get_weapon(a)
                    wb = player.get_weapon(b)
                    if wa and wb and wa.level >= 5 and wb.level >= 5:
                        ready_fusions.append(fus)

        base_pool = [ut for ut in available if ut not in FUSION_TYPES]
        sampled = random.sample(base_pool, min(3, len(base_pool)))
        if ready_fusions:
            self.choices = (ready_fusions + [u for u in sampled if u not in ready_fusions])[:3]
        else:
            self.choices = sampled

    def _next_level_info(self, ut: UpgradeType) -> Tuple[str, bool, bool]:
        if ut in FUSION_TYPES:
            return T("fusion_tag"), False, True
        if self.player is None:
            return "", False, False
        w = self.player.get_weapon(ut)
        if w is None:
            return "", False, False
        if w.level == 0:
            return "MỚI -> Lv.1", False, False
        nxt = w.level + 1
        return f"Lv.{w.level} -> Lv.{nxt}", (nxt == 5), False

    def draw(self, surf):
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((4, 3, 12, 190))
        surf.blit(overlay, (0, 0))

        title = self.font_big.render(T("level_up"), True, C_YELLOW)
        surf.blit(title, (SCREEN_W // 2 - title.get_width() // 2, 50))
        sub = self.font_med.render(T("choose"), True, (195, 190, 235))
        surf.blit(sub, (SCREEN_W // 2 - sub.get_width() // 2, 88))

        card_w, card_h = 315, 215
        gap = 24
        total_w = len(self.choices) * card_w + (len(self.choices) - 1) * gap
        start_x = SCREEN_W // 2 - total_w // 2
        cy = SCREEN_H // 2 - card_h // 2 + 24

        mx, my = pygame.mouse.get_pos()
        self.hovered = None

        for i, ut in enumerate(self.choices):
            cx = start_x + i * (card_w + gap)
            hovering = cx <= mx <= cx + card_w and cy <= my <= cy + card_h
            if hovering:
                self.hovered = i

            name, desc, color = get_upgrade_def(ut)
            lv_str, will_awaken, is_fusion = self._next_level_info(ut)
            recipe_hint = get_recipe_hint(ut)

            card_surf = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
            bg_alpha = 242 if hovering else 200
            if is_fusion:
                card_surf.fill((48, 12, 22, bg_alpha))
            else:
                card_surf.fill((18, 15, 34, bg_alpha))
            surf.blit(card_surf, (cx, cy))

            if is_fusion:
                # Viền Đỏ / Vàng Hoàng Kim lấp lánh cho Kỹ năng Hợp Nhất Thần Thoại
                pygame.draw.rect(surf, (255, 60, 75), (cx - 2, cy - 2, card_w + 4, card_h + 4), 3, border_radius=12)
                pygame.draw.rect(surf, (255, 215, 65), (cx, cy, card_w, card_h), 2, border_radius=10)
            else:
                border_color = (255, 215, 60) if will_awaken else (color if hovering else (85, 75, 135))
                border_w = 3 if (hovering or will_awaken) else 1
                pygame.draw.rect(surf, border_color, (cx, cy, card_w, card_h), border_w,
                                 border_radius=10)

            name_col = (255, 220, 75) if is_fusion else color
            name_surf = self.font_big.render(name, True, name_col)
            surf.blit(name_surf,
                      (cx + card_w // 2 - name_surf.get_width() // 2, cy + 16))

            if lv_str:
                lv_col = (255, 90, 90) if is_fusion else ((255, 215, 70) if will_awaken else (150, 220, 255))
                lbl_txt = f"{lv_str}  {T('awakened_tag')}" if will_awaken else lv_str
                lv_s = self.font_sm.render(lbl_txt, True, lv_col)
                surf.blit(lv_s, (cx + card_w // 2 - lv_s.get_width() // 2, cy + 52))

            desc_surf = self.font_med.render(desc, True, (230, 225, 245))
            surf.blit(desc_surf,
                      (cx + card_w // 2 - desc_surf.get_width() // 2, cy + 88))

            # Hiển thị công thức Hợp Nhất (Synergy Recipe Hint)
            if recipe_hint:
                rh_col = (255, 210, 80) if is_fusion else (195, 165, 255)
                rh_s = self.font_hint.render(recipe_hint, True, rh_col)
                surf.blit(rh_s, (cx + card_w // 2 - rh_s.get_width() // 2, cy + 128))

            key_badge = self.font_hint.render(f"Phím [{i + 1}]", True, (165, 160, 210))
            surf.blit(key_badge, (cx + card_w // 2 - key_badge.get_width() // 2, cy + 158))

            if hovering:
                hint = self.font_sm.render(T("click_hint"), True, (255, 230, 120))
                surf.blit(hint,
                          (cx + card_w // 2 - hint.get_width() // 2, cy + 182))

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.hovered is not None:
                return self.choices[self.hovered]
        if event.type == pygame.KEYDOWN:
            num_map = {pygame.K_1: 0, pygame.K_2: 1, pygame.K_3: 2}
            if event.key in num_map:
                idx = num_map[event.key]
                if idx < len(self.choices):
                    return self.choices[idx]
        return None

# ---------------------------------------------------------------------------
# SpawnManager — Aggressive Wave & Horde Scaling + Swarm Events
# ---------------------------------------------------------------------------
class SpawnManager:
    """
    Hệ thống triệu hồi quái vật Bullet-Heaven theo đợt (Aggressive Wave & Horde Scaling):
      - Tăng theo cấp số nhân cả số lượng quái tối đa trên màn hình (max_enemies) và kích thước cụm triệu hồi (batch_size: 5–20 quái/cụm).
      - Giảm mạnh thời gian hồi triệu hồi (spawn cooldown) sau mỗi đợt (wave).
      - Sự kiện Bầy Quái Bao Vây ("Đợt Tấn Công Dồn Dập!" - Swarm Event): Định kỳ phát cảnh báo viền đỏ và triệu hồi vòng vây quái tốc độ cao quanh người chơi.
    """
    def __init__(self):
        self.timer = 0
        self.wave = 0
        self.wave_timer = 0
        self.base_rate = 68  # Nhịp triệu hồi cơ bản nhanh hơn
        self.horde_cd = 0
        self.elite_timer = 0
        self.runner_timer = 0
        self.exploder_timer = 0
        self.necromancer_timer = 0
        self.swarm_alert_timer = 0
        self.max_enemies = 90
        self.batch_size = 5

    def update(self, player, enemies, tick):
        self.timer += 1
        self.wave_timer += 1
        if self.swarm_alert_timer > 0:
            self.swarm_alert_timer -= 1

        # Mỗi 25 giây tăng 1 Đợt (Wave) để nhịp độ dồn dập hơn
        wave = tick // (25 * FPS)
        self.wave = wave

        # Tăng theo hàm mũ giới hạn quái trên màn hình & kích thước bầy triệu hồi (5 -> 20)
        self.max_enemies = min(380, int(85 * (1.22 ** min(wave, 8)) + wave * 22))
        self.batch_size = min(20, 5 + int(wave * 1.8 + (wave ** 1.25) * 0.6))

        # Giảm dần thời gian chờ triệu hồi mỗi đợt
        rate = max(14, int(self.base_rate * (0.86 ** min(wave, 10)) - wave * 2))

        if self.timer >= rate:
            self.timer = 0
            if len(enemies) < self.max_enemies:
                avail = max(1, self.max_enemies - len(enemies))
                count = min(self.batch_size, avail)
                self._spawn_cluster(player, enemies, wave, count)

        # Quái Tinh Anh: Hiệp Sĩ Hắc Ám (TANK) xuất hiện sớm và dày hơn
        if wave >= 2:
            self.elite_timer += 1
            elite_rate = max(180, int(480 - wave * 28))
            if self.elite_timer >= elite_rate:
                self.elite_timer = 0
                if len(enemies) < self.max_enemies:
                    for _ in range(1 + wave // 4):
                        self._spawn(player, enemies, wave, EnemyType.TANK)
        else:
            self.elite_timer = 0

        # Dơi Hút Máu Tốc Độ Cao (RUNNER)
        if wave >= 1:
            self.runner_timer += 1
            runner_rate = max(150, int(420 - wave * 25))
            if self.runner_timer >= runner_rate:
                self.runner_timer = 0
                if len(enemies) < self.max_enemies:
                    self._spawn_cluster(player, enemies, wave, min(8, 3 + wave // 2), EnemyType.RUNNER)
        else:
            self.runner_timer = 0

        # Quái Cảm Tử (EXPLODER)
        if wave >= 3:
            self.exploder_timer += 1
            exploder_rate = max(220, int(560 - wave * 26))
            if self.exploder_timer >= exploder_rate:
                self.exploder_timer = 0
                if len(enemies) < self.max_enemies:
                    for _ in range(1 + wave // 5):
                        self._spawn(player, enemies, wave, EnemyType.EXPLODER)
        else:
            self.exploder_timer = 0

        # Pháp Sư Chiêu Hồn / Hồn Ma Ác Quỷ (NECROMANCER)
        if wave >= 3:
            self.necromancer_timer += 1
            necromancer_rate = max(260, int(680 - wave * 30))
            if self.necromancer_timer >= necromancer_rate:
                self.necromancer_timer = 0
                if len(enemies) < self.max_enemies:
                    self._spawn(player, enemies, wave, EnemyType.NECROMANCER)
        else:
            self.necromancer_timer = 0

        # Sự kiện Bầy Quái Bao Vây ("Đợt Tấn Công Dồn Dập!" - Swarm Event) mỗi 35 giây
        if tick > 0 and tick % (35 * FPS) == 0:
            self.trigger_swarm_event(player, enemies, wave)

    def trigger_swarm_event(self, player, enemies, wave):
        """Kích hoạt cảnh báo đỏ và triệu hồi vòng vây quái tốc độ cao bao quanh người chơi."""
        self.swarm_alert_timer = 190  # ~3.1 giây nháy viền đỏ & banner cảnh báo
        swarm_count = min(65, 22 + wave * 6)
        ring_r = max(SCREEN_W, SCREEN_H) * 0.54
        swarm_type = EnemyType.FAST if wave % 2 == 0 else EnemyType.RUNNER
        for i in range(swarm_count):
            ang = (math.tau / swarm_count) * i + random.uniform(-0.08, 0.08)
            dist_r = ring_r + random.uniform(-35, 45)
            sx = clamp(player.x + math.cos(ang) * dist_r, 20, WORLD_W - 20)
            sy = clamp(player.y + math.sin(ang) * dist_r, 20, WORLD_H - 20)
            etype = swarm_type if i % 4 != 0 else EnemyType.BASIC
            enemies.append(Enemy(sx, sy, etype, wave))

    def _spawn_cluster(self, player, enemies, wave, count=5, forced_type=None):
        """Triệu hồi một cụm/bầy quái (5–20 con) tụ tập quanh một điểm ở rìa màn hình."""
        margin = 160
        side = random.randint(0, 3)
        if side == 0:
            cx = player.x + random.uniform(-SCREEN_W // 2 - margin, SCREEN_W // 2 + margin)
            cy = player.y - SCREEN_H // 2 - margin
        elif side == 1:
            cx = player.x + SCREEN_W // 2 + margin
            cy = player.y + random.uniform(-SCREEN_H // 2 - margin, SCREEN_H // 2 + margin)
        elif side == 2:
            cx = player.x + random.uniform(-SCREEN_W // 2 - margin, SCREEN_W // 2 + margin)
            cy = player.y + SCREEN_H // 2 + margin
        else:
            cx = player.x - SCREEN_W // 2 - margin
            cy = player.y + random.uniform(-SCREEN_H // 2 - margin, SCREEN_H // 2 + margin)

        for _ in range(count):
            ox = random.uniform(-65, 65)
            oy = random.uniform(-65, 65)
            x = clamp(cx + ox, 16, WORLD_W - 16)
            y = clamp(cy + oy, 16, WORLD_H - 16)
            if forced_type is not None:
                etype = forced_type
            else:
                r = random.random()
                if r < 0.44:
                    etype = EnemyType.BASIC      # Bộ Xương Khô
                elif r < 0.72:
                    etype = EnemyType.FAST       # Dơi Hút Máu
                elif r < 0.90:
                    etype = EnemyType.RANGED     # Hồn Ma Ác Quỷ
                else:
                    etype = EnemyType.TANK       # Hiệp Sĩ Hắc Ám
            enemies.append(Enemy(x, y, etype, wave))

    def _spawn(self, player, enemies, wave, forced_type=None):
        self._spawn_cluster(player, enemies, wave, 1, forced_type)


# ---------------------------------------------------------------------------
# Đồng Xu Vàng Xoay 3D (Animated Spinning Gold Coin)
# ---------------------------------------------------------------------------
class GoldCoin:
    """Đồng vàng rơi ra từ quái vật và Boss với hiệu ứng xoay 3D lấp lánh."""
    def __init__(self, x, y, value):
        self.x, self.y = float(x), float(y)
        self.value  = value
        self.alive  = True
        self.bob    = random.uniform(0, math.tau)
        self.spin   = random.uniform(0, math.tau)
        self.magnetized = False
        self.trail: List[Tuple[float, float]] = []

    def update(self, player):
        self.bob  += 0.09
        self.spin += 0.16
        d = dist((self.x, self.y), (player.x, player.y))
        if self.magnetized or d < player.pickup_radius:
            if self.magnetized:
                self.trail.append((self.x, self.y))
                if len(self.trail) > 6:
                    self.trail.pop(0)
            nx, ny = norm(player.x - self.x, player.y - self.y)
            pull_spd = 15.5 if self.magnetized else 6.8
            self.x += nx * pull_spd
            self.y += ny * pull_spd
        if d < player.radius + 14:
            self.alive = False
            mult = getattr(player, "gold_mult", 1.0)
            return max(1, int(round(self.value * mult)))
        return 0

    def draw(self, surf, cam_x, cam_y):
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y + math.sin(self.bob) * 3)
        if -24 < sx < SCREEN_W + 24 and -24 < sy < SCREEN_H + 24:
            if self.magnetized and len(self.trail) >= 2:
                for i in range(len(self.trail) - 1):
                    p1 = (int(self.trail[i][0] - cam_x), int(self.trail[i][1] - cam_y))
                    p2 = (int(self.trail[i + 1][0] - cam_x), int(self.trail[i + 1][1] - cam_y))
                    pygame.draw.line(surf, (255, 225, 80), p1, p2, max(1, i))
            sh = get_drop_shadow(12, 6, 80)
            surf.blit(sh, (sx - 6, int(self.y - cam_y) + 6))
            # Chiều rộng co giãn theo cos(spin) tạo hiệu ứng đồng xu xoay 3D
            w = max(3, int(abs(math.cos(self.spin)) * 14))
            h = 14
            rect = pygame.Rect(sx - w // 2, sy - h // 2, w, h)
            pygame.draw.ellipse(surf, (255, 215, 45), rect)
            pygame.draw.ellipse(surf, (195, 135, 10), rect, 2)
            if w >= 6:
                pygame.draw.line(surf, (255, 250, 190), (sx, sy - 3), (sx, sy + 3), 2)


# ---------------------------------------------------------------------------
# Vật Phẩm Rơi Trong Trận (In-Match Collectible Item Drops):
#   1. Bình Máu (HealthPotion - HP Potion)
#   2. Nam Châm Từ Trường (ExpMagnet - Global Vacuum Magnet)
# ---------------------------------------------------------------------------
class HealthPotion:
    """
    Bình Máu (HP Potion):
    - Tỉ lệ rơi: ~4% từ quái thường, 100% từ Tinh Anh (Elite) / Đại Trùm (Boss).
    - Ngoại hình: Bình thủy tinh hồng ngọc (ruby-red flask) có nút bần, bọt khí lấp lánh
      và dấu cộng/trái tim đỏ phát sáng nhịp nhàng kèm vòng chỉ báo mặt đất.
    - Hiệu ứng khi nhặt: Hồi ngay max(30, 25% Max HP), kích hoạt hào quang hồi phục
      xanh-đỏ quanh nhân vật và nảy chữ +HP màu xanh lá.
    """
    def __init__(self, x, y, heal_amount=30):
        self.x, self.y = float(x), float(y)
        self.heal_amount = heal_amount
        self.alive = True
        self.bob = random.uniform(0, math.tau)

    def update(self, player, particles, damage_numbers, sfx=None) -> int:
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
            damage_numbers.append(DamageNumber(
                player.x, player.y - 26, actual_heal, (80, 255, 130), is_heal=True
            ))
            for i in range(14):
                ang = (math.tau / 14) * i
                col = (80, 255, 130) if i % 2 == 0 else (255, 60, 95)
                particles.append(Particle(player.x, player.y, col, speed=3.2, size=4, life=26, angle=ang, spread=0.25))
            if sfx:
                sfx.play_levelup()
            return actual_heal
        return 0

    def draw(self, surf, cam_x, cam_y, tick):
        sx = int(self.x - cam_x)
        base_sy = int(self.y - cam_y)
        sy = int(base_sy + math.sin(self.bob) * 3.5)
        if not (-28 < sx < SCREEN_W + 28 and -28 < sy < SCREEN_H + 28):
            return

        # Vòng sáng chỉ báo mặt đất (Glowing Ground Indicator)
        pulse = 0.88 + 0.12 * math.sin(self.bob * 1.5)
        ind_r = int(16 * pulse)
        ind_s = pygame.Surface((ind_r * 2 + 6, ind_r + 6), pygame.SRCALPHA)
        pygame.draw.ellipse(ind_s, (255, 45, 80, 95), (2, 2, ind_r * 2, ind_r))
        pygame.draw.ellipse(ind_s, (255, 140, 165, 175), (2, 2, ind_r * 2, ind_r), 1)
        surf.blit(ind_s, (sx - ind_r - 2, base_sy + 4))

        draw_additive_glow(surf, sx, sy, 22, (255, 40, 80), intensity=0.52)

        # Bầu bình thủy tinh hồng ngọc (Ruby-red glass flask)
        pygame.draw.circle(surf, (130, 15, 35), (sx, sy + 2), 9)
        pygame.draw.circle(surf, (235, 30, 65), (sx, sy + 2), 8)
        # Bọt khí & vệt phản quang thủy tinh
        pygame.draw.circle(surf, (255, 110, 140), (sx - 3, sy), 3)
        pygame.draw.circle(surf, (255, 240, 245), (sx - 3, sy - 1), 1)
        pygame.draw.circle(surf, (220, 240, 255), (sx, sy + 2), 9, 1)
        # Cổ bình & nút bần gỗ (Cork)
        pygame.draw.rect(surf, (200, 225, 245), (sx - 3, sy - 9, 6, 4), border_radius=1)
        pygame.draw.rect(surf, (175, 115, 55), (sx - 2, sy - 12, 4, 4), border_radius=1)

        # Biểu tượng chữ thập / trái tim nhỏ lơ lửng phía trên
        cy_cross = sy - 16 - int(abs(math.sin(self.bob)) * 3)
        pygame.draw.line(surf, (255, 80, 110), (sx - 3, cy_cross), (sx + 3, cy_cross), 2)
        pygame.draw.line(surf, (255, 80, 110), (sx, cy_cross - 3), (sx, cy_cross + 3), 2)


class ExpMagnet:
    """
    Nam Châm Từ Trường (EXP Magnet):
    - Tỉ lệ rơi: ~1.5% từ quái thường, 100% chắc chắn rơi từ Đại Trùm (Boss).
    - Ngoại hình: Nam châm hình chữ U (horseshoe magnet) với 2 cực Đỏ / Xanh phát sóng từ trường.
    - Hiệu ứng khi nhặt: Kích hoạt Hút Toàn Bản Đồ (Global Vacuum Effect) — toàn bộ Ngọc EXP
      và Đồng Vàng trên khắp bản đồ lập tức bay vút về phía người chơi với tốc độ cao kèm sóng xung kích từ trường.
    """
    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)
        self.alive = True
        self.bob = random.uniform(0, math.tau)

    def update(self, player, xp_gems, gold_coins, shockwaves, particles, damage_numbers, sfx=None) -> bool:
        self.bob += 0.09
        d = dist((self.x, self.y), (player.x, player.y))
        if d < player.pickup_radius * 0.85:
            nx, ny = norm(player.x - self.x, player.y - self.y)
            self.x += nx * 5.5
            self.y += ny * 5.5
        if d < player.radius + 15:
            self.alive = False
            # Hút toàn bộ Ngọc EXP và Đồng Vàng trên toàn bản đồ!
            for g in xp_gems:
                if g.alive:
                    g.magnetized = True
            for c in gold_coins:
                if c.alive:
                    c.magnetized = True
            shockwaves.append(ShockwaveRing(player.x, player.y, max_radius=340, color=(70, 225, 255)))
            shockwaves.append(ShockwaveRing(player.x, player.y, max_radius=220, color=(255, 70, 95)))
            damage_numbers.append(DamageNumber(
                player.x, player.y - 34, 0, (90, 240, 255), text_override=T("item_magnet_pickup")
            ))
            for i in range(18):
                ang = (math.tau / 18) * i
                col = (70, 225, 255) if i % 2 == 0 else (255, 65, 85)
                particles.append(Particle(player.x, player.y, col, speed=4.2, size=4, life=28, angle=ang, spread=0.2))
            if sfx:
                sfx.play_levelup()
            return True
        return False

    def draw(self, surf, cam_x, cam_y, tick):
        sx = int(self.x - cam_x)
        base_sy = int(self.y - cam_y)
        sy = int(base_sy + math.sin(self.bob) * 3.5)
        if not (-28 < sx < SCREEN_W + 28 and -28 < sy < SCREEN_H + 28):
            return

        # Vòng sóng từ trường dưới mặt đất (Magnetic Ground Waves)
        wave_r = 8 + int((tick * 0.6) % 14)
        ind_s = pygame.Surface((wave_r * 2 + 6, wave_r + 6), pygame.SRCALPHA)
        pygame.draw.ellipse(ind_s, (70, 220, 255, 150 - wave_r * 6), (2, 2, wave_r * 2, wave_r), 2)
        surf.blit(ind_s, (sx - wave_r - 2, base_sy + 4))

        draw_additive_glow(surf, sx, sy, 24, (70, 215, 255), intensity=0.55)

        # Thân Nam Châm chữ U (Horseshoe Magnet)
        # Vòng cung dưới màu thép xám bạc
        pygame.draw.circle(surf, (130, 145, 175), (sx, sy + 2), 9, 4)
        # Hai nhánh nam châm hướng lên: Cực Đỏ (Trái) & Cực Xanh (Phải)
        pygame.draw.rect(surf, (235, 45, 65), (sx - 9, sy - 7, 5, 9), border_radius=1)
        pygame.draw.rect(surf, (45, 155, 255), (sx + 4, sy - 7, 5, 9), border_radius=1)
        # Hai đầu cực mạ bạc trắng phát tia điện
        pygame.draw.rect(surf, (245, 250, 255), (sx - 9, sy - 9, 5, 3))
        pygame.draw.rect(surf, (245, 250, 255), (sx + 4, sy - 9, 5, 3))

        # Tia điện từ trường nhảy giữa 2 cực
        if (tick // 3) % 2 == 0:
            pygame.draw.line(surf, (140, 245, 255), (sx - 6, sy - 10), (sx, sy - 14), 2)
            pygame.draw.line(surf, (255, 255, 255), (sx, sy - 14), (sx + 6, sy - 10), 2)


# ---------------------------------------------------------------------------
# Đại Trùm Dark Fantasy: Chúa Tể Xương (Lich King) & Ác Quỷ Vực Thẳm (Abyssal Demon Lord)
# ---------------------------------------------------------------------------
class Boss:
    """
    Đại Trùm Dark Fantasy với kích thước khổng lồ (3x quái thường), hào quang động,
    vương miện/đôi cánh bay lượn, thanh máu Trùm trên đỉnh màn hình và đòn đánh AoE
    có vùng cảnh báo đỏ (telegraphed red warning circles/lines) trước khi phát nổ:
      - boss_kind == 0: Chúa Tể Xương (Lich King) - Vương miện hoàng kim hắc ám, áo choàng tử linh, vòng triệu hồi nổ cổ ngữ.
      - boss_kind == 1: Ác Quỷ Vực Thẳm (Abyssal Demon Lord) - Đôi cánh quỷ khổng lồ, sừng đại ma vương, tia lửa địa ngục cắt chéo.
    """
    BASE_HP     = 1400
    BASE_DAMAGE = 32
    BASE_SPEED  = 0.95
    RADIUS      = 45   # Lớn gấp ~3 lần quái thường (radius 14-15)
    COLOR       = (220, 30, 180)
    RING_COLOR  = (255, 80, 220)
    XP_REWARD   = 150
    GOLD_REWARD = 100

    def __init__(self, x, y, wave):
        self.x, self.y  = float(x), float(y)
        self.boss_kind  = int(wave) % 2  # 0: Chúa Tể Xương (Lich King), 1: Ác Quỷ Vực Thẳm (Abyssal Demon Lord)
        scale           = 1 + wave * 0.16
        self.max_hp     = int(self.BASE_HP * scale)
        self.hp         = self.max_hp
        self.damage     = int(self.BASE_DAMAGE * scale)
        self.speed      = self.BASE_SPEED
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
        self.hp -= amount
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
class ChestDrop(Enum):
    GOLD   = auto()
    DRONE  = auto()
    TURRET = auto()

class Chest:
    """
    Haritada rastgele konumlarda belirir.
    Oyuncu yaklaşıp üzerine yürüyünce açılır; içinden altın, drone veya taret çıkar.
    Açıldıktan sonra CHEST_RESPAWN_TICKS frame içinde yeni konumda yeniden doğar.
    """
    RADIUS           = 18
    RESPAWN_TICKS    = 1800   # 30 sn @ 60 fps
    COLOR_CLOSED     = (180, 140, 40)
    COLOR_OPEN       = (100, 80, 20)

    def __init__(self):
        self._place()
        self.open        = False
        self.respawn_cd  = 0
        self.bob         = random.uniform(0, math.tau)

    def _place(self):
        """Oyuncudan bağımsız rastgele dünya konumu."""
        self.x = float(random.randint(200, WORLD_W - 200))
        self.y = float(random.randint(200, WORLD_H - 200))

    def update(self, player):
        """
        Dönüş değeri: ChestDrop enum (ödül tipi) ya da None.
        """
        self.bob += 0.07
        if self.open:
            self.respawn_cd -= 1
            if self.respawn_cd <= 0:
                self._place()
                self.open = False
            return None
        # Açılma kontrolü
        if dist((self.x, self.y), (player.x, player.y)) < self.RADIUS + player.radius:
            self.open       = True
            self.respawn_cd = self.RESPAWN_TICKS
            # Ödül seçimi: %60 altın, %25 drone, %15 taret
            r = random.random()
            if r < 0.60:
                return ChestDrop.GOLD
            elif r < 0.85:
                return ChestDrop.DRONE
            else:
                return ChestDrop.TURRET
        return None

    def draw(self, surf, cam_x, cam_y):
        if self.open:
            return
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y + math.sin(self.bob) * 3)
        if sx + 24 < 0 or sx - 24 > SCREEN_W or sy + 24 < 0 or sy - 24 > SCREEN_H:
            return
        # Sandık gövdesi
        pygame.draw.rect(surf, self.COLOR_CLOSED, (sx - 14, sy - 10, 28, 20), border_radius=4)
        pygame.draw.rect(surf, (220, 180, 60), (sx - 14, sy - 10, 28, 20), 2, border_radius=4)
        # Kapak
        pygame.draw.rect(surf, (200, 160, 50), (sx - 14, sy - 14, 28, 8), border_radius=3)
        pygame.draw.rect(surf, (240, 200, 80), (sx - 14, sy - 14, 28, 8), 1, border_radius=3)
        # Kilit
        pygame.draw.rect(surf, (60, 50, 20), (sx - 3, sy - 4, 6, 6), border_radius=2)


# ---------------------------------------------------------------------------
# Drone (oyuncuyu takip eder, düşmanlara ateş eder)
# ---------------------------------------------------------------------------
class Drone:
    """
    Sandıktan elde edilen drone.
    Oyuncunun etrafında yörüngede döner, en yakın düşmana otomatik ateş eder.
    Birden fazla drone olabilir (liste ile yönetilir).
    """
    ORBIT_RADIUS = 70
    ORBIT_SPEED  = 0.045   # rad/frame
    SHOOT_CD     = 45
    DAMAGE       = 20
    RANGE        = 300
    COLOR        = (80, 200, 255)

    def __init__(self, index=0):
        self.index    = index          # birden fazla drone için açı offseti
        self.angle    = (math.tau / 4) * index
        self.shoot_cd = random.randint(0, self.SHOOT_CD)

    def update(self, player, enemies, projectiles_out, damage_numbers, particles):
        self.angle += self.ORBIT_SPEED
        # Pozisyon
        ox = player.x + math.cos(self.angle) * self.ORBIT_RADIUS
        oy = player.y + math.sin(self.angle) * self.ORBIT_RADIUS

        self.shoot_cd -= 1
        if self.shoot_cd <= 0:
            # En yakın düşmanı bul
            target = None
            best_d = self.RANGE
            for e in enemies:
                d = dist((ox, oy), (e.x, e.y))
                if d < best_d:
                    best_d = d
                    target = e
            if target:
                self.shoot_cd = self.SHOOT_CD
                a = angle_to((ox, oy), (target.x, target.y))
                proj = Projectile(ox, oy, a, speed=7, damage=self.DAMAGE,
                                  lifetime=50, color=self.COLOR, size=5)
                projectiles_out.append(proj)
                for _ in range(3):
                    particles.append(Particle(ox, oy, self.COLOR, speed=2, life=15))
            else:
                self.shoot_cd = self.SHOOT_CD // 2

    def draw(self, surf, cam_x, cam_y, player):
        ox = int(player.x + math.cos(self.angle) * self.ORBIT_RADIUS - cam_x)
        oy = int(player.y + math.sin(self.angle) * self.ORBIT_RADIUS - cam_y)
        # Bağlantı çizgisi
        px = int(player.x - cam_x)
        py = int(player.y - cam_y)
        pygame.draw.line(surf, (*self.COLOR, 60), (px, py), (ox, oy), 1)
        # Drone gövdesi
        glow = pygame.Surface((28, 28), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*self.COLOR, 50), (14, 14), 12)
        surf.blit(glow, (ox - 14, oy - 14))
        pygame.draw.circle(surf, self.COLOR, (ox, oy), 7)
        pygame.draw.circle(surf, C_WHITE, (ox, oy), 3)


# ---------------------------------------------------------------------------
# Taret (yerleştirilen sabit kule)
# ---------------------------------------------------------------------------
class Turret:
    """
    Sandıktan elde edilen taret.
    Oyuncunun bulunduğu yere yerleştirilir, sabit kalır, menzilindeki düşmanlara ateş eder.
    Ömrü LIFETIME frame'dir.
    """
    RANGE    = 220
    SHOOT_CD = 35
    DAMAGE   = 28
    LIFETIME = 1800   # 30 sn
    RADIUS   = 14
    COLOR    = (255, 180, 40)

    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)
        self.shoot_cd  = 0
        self.life      = self.LIFETIME
        self.alive     = True
        self.angle     = 0.0   # görselde dönen top

    def update(self, enemies, projectiles_out, damage_numbers, particles):
        self.life -= 1
        if self.life <= 0:
            self.alive = False
            return

        self.shoot_cd -= 1
        if self.shoot_cd <= 0:
            target = None
            best_d = self.RANGE
            for e in enemies:
                d = dist((self.x, self.y), (e.x, e.y))
                if d < best_d:
                    best_d = d
                    target = e
            if target:
                self.shoot_cd = self.SHOOT_CD
                self.angle    = angle_to((self.x, self.y), (target.x, target.y))
                a             = self.angle
                proj = Projectile(self.x, self.y, a, speed=8, damage=self.DAMAGE,
                                  lifetime=40, color=self.COLOR, size=5)
                projectiles_out.append(proj)
                for _ in range(3):
                    particles.append(Particle(self.x, self.y, self.COLOR, speed=2, life=12))
            else:
                self.shoot_cd = self.SHOOT_CD // 2

    def draw(self, surf, cam_x, cam_y):
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        if sx + 20 < 0 or sx - 20 > SCREEN_W or sy + 20 < 0 or sy - 20 > SCREEN_H:
            return
        # Menzil dairesi (soluk)
        range_surf = pygame.Surface((self.RANGE * 2 + 2, self.RANGE * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(range_surf, (*self.COLOR, 18),
                           (self.RANGE + 1, self.RANGE + 1), self.RANGE)
        pygame.draw.circle(range_surf, (*self.COLOR, 50),
                           (self.RANGE + 1, self.RANGE + 1), self.RANGE, 1)
        surf.blit(range_surf, (sx - self.RANGE - 1, sy - self.RANGE - 1))
        # Taban
        pygame.draw.circle(surf, (80, 60, 20), (sx, sy), self.RADIUS)
        pygame.draw.circle(surf, self.COLOR, (sx, sy), self.RADIUS - 2)
        # Namlu
        ex = sx + int(math.cos(self.angle) * (self.RADIUS + 8))
        ey = sy + int(math.sin(self.angle) * (self.RADIUS + 8))
        pygame.draw.line(surf, (255, 220, 80), (sx, sy), (ex, ey), 4)
        # Ömür çubuğu
        lf = self.life / self.LIFETIME
        bw = self.RADIUS * 2
        pygame.draw.rect(surf, (60, 40, 0), (sx - self.RADIUS, sy + self.RADIUS + 4, bw, 4))
        pygame.draw.rect(surf, self.COLOR,  (sx - self.RADIUS, sy + self.RADIUS + 4,
                                             int(bw * lf), 4))


# ---------------------------------------------------------------------------
# Hệ thống 4 Lớp Nhân Vật RPG (Dark Fantasy & Cyber-Arcane Classes)
# ---------------------------------------------------------------------------
CHARACTER_DEFS = [
    {
        "id":    "warrior",
        "name":  "Huyết Kiếm Sĩ",
        "desc":  "+60 Máu, +2 Giáp | Khởi đầu: Trảm Huyết Nguyệt",
        "cost":  0,             # Khởi đầu — miễn phí
        "color": (235, 50, 70),
        "mods":  {
            "max_hp": 60,
            "armor": 2,
            "whip_level": 1,        # DUY NHẤT 1 kỹ năng khởi đầu: Trảm Huyết Nguyệt Lv1
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
            "void_level": 1,        # DUY NHẤT 1 kỹ năng khởi đầu: Hố Đen Hư Không Lv1
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
            "arrow_level": 1,       # DUY NHẤT 1 kỹ năng khởi đầu: Mưa Tên Độc Ảnh Lv1
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
            "hammer_level": 1,      # DUY NHẤT 1 kỹ năng khởi đầu: Phán Quyết Ánh Sáng Lv1
        },
        "stats_bars": [("HP", 1.00), ("GIÁP", 0.95), ("HỒI", 0.90)],
    },
]


# ---------------------------------------------------------------------------
# Hệ thống Lưu Trữ Vĩnh Viễn (save_data.json)
# ---------------------------------------------------------------------------
PERM_UPGRADE_DEFS = [
    ("hp",   "perm_hp",   80,  5),   # +20 Max HP mỗi cấp
    ("dmg",  "perm_dmg",  100, 5),   # +8% Damage mỗi cấp
    ("spd",  "perm_spd",  90,  5),   # +5% Speed mỗi cấp
    ("gold", "perm_gold", 100, 5),   # +15% Gold mỗi cấp
]


class SaveData:
    """
    Lưu và tải dữ liệu vĩnh viễn qua file JSON (save_data.json):
      - Tổng Vàng (total_gold, lifetime_gold)
      - Các lớp nhân vật đã mở khóa (unlocked_ids, selected_id)
      - Trang phục Anime đã sở hữu & đang trang bị (owned_skins, equipped_skin)
      - Nâng cấp chỉ số vĩnh viễn (perm_upgrades)
      - Kỷ lục điểm cao (high_scores) & Tiến độ Chiến dịch / Thành tựu
    """
    def __init__(self, filepath: str = SAVE_FILE_PATH):
        self.filepath = filepath
        self.total_gold    = 0
        self.unlocked_ids  = {"warrior"}
        self.selected_id   = "warrior"
        self.owned_skins: set = {"default"}
        self.equipped_skin: str = "default"
        self.campaign_unlocked_level = 1
        self.lifetime_gold = 0
        self.unlocked_achievements = set()
        self.chest_opens = 0
        self.perm_upgrades: Dict[str, int] = {"hp": 0, "dmg": 0, "spd": 0, "gold": 0}
        self.high_scores: Dict[str, int] = {
            "best_kills": 0,
            "best_time": 0,
            "best_wave": 0,
            "best_level": 1,
        }
        self.load()

    def load(self) -> bool:
        try:
            if not os.path.exists(self.filepath):
                return False
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return False
            self.total_gold = max(0, int(data.get("total_gold", 0)))
            self.lifetime_gold = max(0, int(data.get("lifetime_gold", self.total_gold)))
            unlocked = data.get("unlocked_ids", ["warrior"])
            valid_ids = {c["id"] for c in CHARACTER_DEFS}
            self.unlocked_ids = {cid for cid in unlocked if cid in valid_ids} | {"warrior"}
            sel = data.get("selected_id", "warrior")
            self.selected_id = sel if sel in self.unlocked_ids else "warrior"

            valid_skin_ids = {s["id"] for s in ANIME_SKINS} | {"default"}
            loaded_skins = data.get("owned_skins", ["default"])
            if isinstance(loaded_skins, list):
                self.owned_skins = {sid for sid in loaded_skins if sid in valid_skin_ids} | {"default"}
            else:
                self.owned_skins = {"default"}
            eq_skin = data.get("equipped_skin", "default")
            self.equipped_skin = eq_skin if eq_skin in self.owned_skins else "default"

            self.campaign_unlocked_level = clamp(int(data.get("campaign_unlocked_level", 1)), 1, 30)
            self.chest_opens = max(0, int(data.get("chest_opens", 0)))

            ach_names = data.get("unlocked_achievements", [])
            loaded_ach = set()
            for name in ach_names:
                if isinstance(name, str) and name in AchievementID.__members__:
                    loaded_ach.add(AchievementID[name])
            self.unlocked_achievements = loaded_ach

            pu = data.get("perm_upgrades", {})
            if isinstance(pu, dict):
                for k in self.perm_upgrades:
                    self.perm_upgrades[k] = clamp(int(pu.get(k, 0)), 0, 5)

            hs = data.get("high_scores", {})
            if isinstance(hs, dict):
                for k in self.high_scores:
                    self.high_scores[k] = max(0, int(hs.get(k, self.high_scores[k])))
            return True
        except Exception:
            return False

    def save(self) -> bool:
        try:
            data = {
                "total_gold": int(self.total_gold),
                "lifetime_gold": int(self.lifetime_gold),
                "unlocked_ids": sorted(list(self.unlocked_ids)),
                "selected_id": self.selected_id,
                "owned_skins": sorted(list(self.owned_skins)),
                "equipped_skin": self.equipped_skin,
                "campaign_unlocked_level": int(self.campaign_unlocked_level),
                "chest_opens": int(self.chest_opens),
                "unlocked_achievements": [a.name for a in self.unlocked_achievements if isinstance(a, AchievementID)],
                "perm_upgrades": dict(self.perm_upgrades),
                "high_scores": dict(self.high_scores),
            }
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def record_match_stats(self, kills: int, elapsed_secs: int, wave: int, level: int):
        self.high_scores["best_kills"] = max(self.high_scores.get("best_kills", 0), int(kills))
        self.high_scores["best_time"]  = max(self.high_scores.get("best_time", 0), int(elapsed_secs))
        self.high_scores["best_wave"]  = max(self.high_scores.get("best_wave", 0), int(wave))
        self.high_scores["best_level"] = max(self.high_scores.get("best_level", 1), int(level))
        self.save()

    def unlock(self, char_id, cost):
        if self.total_gold >= cost:
            self.total_gold -= cost
            self.unlocked_ids.add(char_id)
            self.save()
            return True
        return False

    def buy_skin(self, skin_id: str, cost: int) -> bool:
        if skin_id in self.owned_skins:
            self.equipped_skin = skin_id
            self.save()
            return True
        if self.total_gold >= cost:
            self.total_gold -= cost
            self.owned_skins.add(skin_id)
            self.equipped_skin = skin_id
            self.save()
            return True
        return False

    def equip_skin(self, skin_id: str) -> bool:
        if skin_id in self.owned_skins or skin_id == "default":
            self.equipped_skin = skin_id
            self.save()
            return True
        return False

    def buy_perm_upgrade(self, key: str, base_cost: int, max_lv: int = 5) -> bool:
        cur = self.perm_upgrades.get(key, 0)
        if cur >= max_lv:
            return False
        cost = base_cost * (cur + 1)
        if self.total_gold >= cost:
            self.total_gold -= cost
            self.perm_upgrades[key] = cur + 1
            self.save()
            return True
        return False

    def complete_campaign_level(self, level):
        if 1 <= level <= 30:
            self.campaign_unlocked_level = max(
                self.campaign_unlocked_level,
                min(30, level + 1)
            )
            self.save()


def campaign_target_wave(level):
    return 10 + (level - 1) * 2


# ---------------------------------------------------------------------------
# Menü: ortak Button bileşeni
# ---------------------------------------------------------------------------
class Button:
    CLR_NORMAL   = (30, 28, 50)
    CLR_HOVER    = (60, 55, 100)
    CLR_BORDER   = (80, 75, 140)
    CLR_BORDER_H = (140, 120, 255)
    CLR_TEXT     = (200, 195, 240)
    CLR_TEXT_H   = (255, 255, 255)

    def __init__(self, x, y, w, h, label, font):
        self.base_rect = pygame.Rect(x, y, w, h)
        self.label     = label
        self.font      = font
        self.hovered   = False
        self._hover_t  = 0.0

    def update(self, mx, my):
        self.hovered = self.base_rect.collidepoint(mx, my)
        target       = 1.0 if self.hovered else 0.0
        self._hover_t += (target - self._hover_t) * 0.18

    def is_clicked(self, event):
        return (event.type == pygame.MOUSEBUTTONDOWN
                and event.button == 1
                and self.base_rect.collidepoint(event.pos))

    def draw(self, surf):
        t      = self._hover_t
        expand = int(t * 3)
        rect   = self.base_rect.inflate(expand * 2, expand * 2)
        bg     = tuple(int(a + (b - a) * t) for a, b in zip(self.CLR_NORMAL, self.CLR_HOVER))
        border = tuple(int(a + (b - a) * t) for a, b in zip(self.CLR_BORDER, self.CLR_BORDER_H))
        txtclr = tuple(int(a + (b - a) * t) for a, b in zip(self.CLR_TEXT,   self.CLR_TEXT_H))
        if t > 0.05:
            sh = pygame.Surface((rect.w + 8, rect.h + 8), pygame.SRCALPHA)
            pygame.draw.rect(sh, (0, 0, 0, int(80 * t)), sh.get_rect(), border_radius=10)
            surf.blit(sh, (rect.x - 4, rect.y + 4))
        pygame.draw.rect(surf, bg, rect, border_radius=8)
        pygame.draw.rect(surf, border, rect, 2, border_radius=8)
        ts = self.font.render(self.label, True, txtclr)
        surf.blit(ts, ts.get_rect(center=rect.center))


# ---------------------------------------------------------------------------
# Menü: yatay kaydırıcı (0-100 %)
# ---------------------------------------------------------------------------
class Slider:
    def __init__(self, x, y, w, value, font, on_change=None, on_release=None):
        self.track      = pygame.Rect(x, y, w, 8)
        self.hit        = self.track.inflate(20, 28)
        self.value      = audio_settings.clamp_percent(value)
        self.font       = font
        self.on_change  = on_change
        self.on_release = on_release
        self.dragging   = False
        self.focused    = False

    def _set_from_x(self, mx):
        frac = (mx - self.track.x) / self.track.w
        self.set_value(round(max(0.0, min(1.0, frac)) * 100))

    def set_value(self, v):
        v = audio_settings.clamp_percent(v, self.value)
        if v != self.value:
            self.value = v
            if self.on_change:
                self.on_change(v)

    def handle_event(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            self.focused = self.hit.collidepoint(ev.pos)
            if self.focused:
                self.dragging = True
                self._set_from_x(ev.pos[0])
        elif ev.type == pygame.MOUSEMOTION and self.dragging:
            self._set_from_x(ev.pos[0])
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1 and self.dragging:
            self.dragging = False
            if self.on_release:
                self.on_release(self.value)
        elif ev.type == pygame.KEYDOWN and self.focused:
            if ev.key == pygame.K_LEFT:
                self.set_value(self.value - 5)
                if self.on_release: self.on_release(self.value)
            elif ev.key == pygame.K_RIGHT:
                self.set_value(self.value + 5)
                if self.on_release: self.on_release(self.value)

    def draw(self, surf):
        pygame.draw.rect(surf, (30, 28, 50), self.track, border_radius=4)
        fill = self.track.copy()
        fill.w = int(self.track.w * self.value / 100)
        if fill.w > 0:
            pygame.draw.rect(surf, (140, 120, 255), fill, border_radius=4)
        pygame.draw.rect(surf, (80, 75, 140), self.track, 1, border_radius=4)
        hx = self.track.x + fill.w
        clr = (255, 255, 255) if (self.dragging or self.focused) else (200, 195, 240)
        pygame.draw.circle(surf, clr, (hx, self.track.centery), 9)
        txt = self.font.render(f"{self.value}%", True, (200, 195, 240))
        surf.blit(txt, txt.get_rect(midleft=(self.track.right + 24, self.track.centery)))


# ---------------------------------------------------------------------------
# GameState
# ---------------------------------------------------------------------------
class GameState(Enum):
    MENU       = auto()
    CAMPAIGN   = auto()
    SETTINGS   = auto()
    CHARACTERS = auto()
    SKIN_SHOP  = auto()
    PLAYING    = auto()


# ---------------------------------------------------------------------------
# Ana Menü
# ---------------------------------------------------------------------------
class MainMenu:
    BTN_W, BTN_H, BTN_GAP = 300, 46, 12

    def __init__(self, sfx, save: Optional[SaveData] = None):
        self.sfx  = sfx
        self.save = save
        self.tick = 0
        self.font_title = get_sys_font(62, bold=True)
        self.font_sub   = get_sys_font(20)
        self.font_btn   = get_sys_font(21, bold=True)
        self.font_gold  = get_sys_font(20, bold=True)
        self.font_ver   = get_sys_font(15, bold=True)
        self._bg_parts  = [self._new_p() for _ in range(55)]
        self._build_buttons()

    def _build_buttons(self):
        cx     = SCREEN_W // 2 - self.BTN_W // 2
        step   = self.BTN_H + self.BTN_GAP
        start  = SCREEN_H // 2 - 65
        self.buttons = {
            "play":     Button(cx, start,           self.BTN_W, self.BTN_H, T("menu_play"),     self.font_btn),
            "campaign": Button(cx, start + step,    self.BTN_W, self.BTN_H, T("menu_campaign"), self.font_btn),
            "chars":    Button(cx, start + step*2,  self.BTN_W, self.BTN_H, T("menu_chars"),    self.font_btn),
            "skins":    Button(cx, start + step*3,  self.BTN_W, self.BTN_H, T("menu_skins"),    self.font_btn),
            "settings": Button(cx, start + step*4,  self.BTN_W, self.BTN_H, T("menu_settings"), self.font_btn),
            "quit":     Button(cx, start + step*5,  self.BTN_W, self.BTN_H, T("menu_quit"),     self.font_btn),
        }

    @staticmethod
    def _new_p():
        return {"x": random.uniform(0, SCREEN_W), "y": random.uniform(0, SCREEN_H),
                "vy": random.uniform(-0.3, -0.8),  "vx": random.uniform(-0.2, 0.2),
                "size": random.uniform(1, 3),       "alpha": random.randint(30, 120),
                "color": random.choice([(120,80,255),(80,160,255),(255,100,180),(100,220,255)])}

    def _update_bg(self):
        for i, p in enumerate(self._bg_parts):
            p["x"] += p["vx"]; p["y"] += p["vy"]
            if p["y"] < -5 or not (0 <= p["x"] <= SCREEN_W):
                np = self._new_p(); np["y"] = SCREEN_H + 5
                self._bg_parts[i] = np

    def _draw_bg(self, surf):
        for p in self._bg_parts:
            s = pygame.Surface((int(p["size"]*2+2),)*2, pygame.SRCALPHA)
            pygame.draw.circle(s, (*p["color"], p["alpha"]),
                               (int(p["size"]+1),)*2, int(p["size"]))
            surf.blit(s, (int(p["x"]), int(p["y"])))

    def handle_events(self, events) -> Optional[str]:
        mx, my = pygame.mouse.get_pos()
        for btn in self.buttons.values():
            btn.update(mx, my)
        for ev in events:
            for bid, btn in self.buttons.items():
                if btn.is_clicked(ev):
                    return bid
        return None

    def draw(self, surf):
        self.tick += 1
        surf.fill((8, 6, 16))
        for y in range(0, SCREEN_H, 4):
            t = y / SCREEN_H
            pygame.draw.line(surf, (int(8+12*(1-t)), int(6+8*(1-t)), int(16+28*(1-t))),
                             (0, y), (SCREEN_W, y))
        self._update_bg(); self._draw_bg(surf)
        # Tiêu đề
        float_y  = math.sin(self.tick * 0.03) * 6
        pulse    = 0.5 + 0.5 * math.sin(self.tick * 0.05)
        tclr     = (int(160+95*pulse), int(80+60*pulse), 255)
        ts       = self.font_title.render(T("title"), True, tclr)
        sh       = self.font_title.render(T("title"), True, (20,10,40))
        ty       = int(SCREEN_H * 0.09 + float_y)
        surf.blit(sh, (SCREEN_W//2 - ts.get_width()//2 + 3, ty + 4))
        surf.blit(ts, (SCREEN_W//2 - ts.get_width()//2,     ty))
        sub = self.font_sub.render("Dark Fantasy & Cyber-Arcane Edition", True, (145, 130, 195))
        surf.blit(sub, sub.get_rect(centerx=SCREEN_W//2, y=ty + ts.get_height() + 4))
        line_y = ty + ts.get_height() + 30
        pygame.draw.line(surf, (80,60,140), (SCREEN_W//2-180, line_y), (SCREEN_W//2+180, line_y), 1)

        # Hiển thị Vàng hiện tại và Kỷ lục trên Menu chính
        if self.save is not None:
            gold_txt = self.font_gold.render(f"{T('gold')}: {self.save.total_gold}", True, C_YELLOW)
            g_rect = pygame.Rect(SCREEN_W - gold_txt.get_width() - 48, 20, gold_txt.get_width() + 32, 36)
            pygame.draw.rect(surf, (20, 16, 38), g_rect, border_radius=8)
            pygame.draw.rect(surf, (220, 180, 50), g_rect, 2, border_radius=8)
            surf.blit(gold_txt, gold_txt.get_rect(center=g_rect.center))

            hs = self.save.high_scores
            bm, bs = divmod(hs.get("best_time", 0), 60)
            hs_str = T("high_score", k=hs.get("best_kills", 0), w=hs.get("best_wave", 0) + 1, t=f"{bm:02d}:{bs:02d}")
            hs_surf = self.font_ver.render(hs_str, True, (185, 175, 230))
            surf.blit(hs_surf, hs_surf.get_rect(centerx=SCREEN_W // 2, y=SCREEN_H - 30))

        for btn in self.buttons.values():
            btn.draw(surf)
        pygame.display.flip()

    def refresh_labels(self):
        self.buttons["play"].label     = T("menu_play")
        self.buttons["campaign"].label = T("menu_campaign")
        self.buttons["chars"].label    = T("menu_chars")
        self.buttons["skins"].label    = T("menu_skins")
        self.buttons["settings"].label = T("menu_settings")
        self.buttons["quit"].label     = T("menu_quit")


# ---------------------------------------------------------------------------
# Campaign Ekranı
# ---------------------------------------------------------------------------
class CampaignScreen:
    COLS = 5
    ROWS = 6
    BTN_W, BTN_H = 150, 56
    GAP_X, GAP_Y = 22, 18

    def __init__(self, save: SaveData):
        self.save = save
        self.tick = 0
        self.font_title = get_sys_font(44, bold=True)
        self.font_btn   = get_sys_font(18, bold=True)
        self.font_sm    = get_sys_font(14, bold=True)
        self.font_back  = get_sys_font(20, bold=True)
        self._build_buttons()

    def _build_buttons(self):
        total_w = self.COLS * self.BTN_W + (self.COLS - 1) * self.GAP_X
        sx = SCREEN_W // 2 - total_w // 2
        sy = 150
        self.level_buttons = []
        for i in range(30):
            col = i % self.COLS
            row = i // self.COLS
            x = sx + col * (self.BTN_W + self.GAP_X)
            y = sy + row * (self.BTN_H + self.GAP_Y)
            self.level_buttons.append(
                Button(x, y, self.BTN_W, self.BTN_H,
                       T("campaign_level", n=i + 1), self.font_btn)
            )
        self.btn_back = Button(SCREEN_W // 2 - 100, SCREEN_H - 70,
                               200, 46, T("menu_back"), self.font_back)

    def handle_events(self, events):
        mx, my = pygame.mouse.get_pos()
        for btn in self.level_buttons:
            btn.update(mx, my)
        self.btn_back.update(mx, my)

        for ev in events:
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                return "back"
            if self.btn_back.is_clicked(ev):
                return "back"
            for i, btn in enumerate(self.level_buttons):
                level = i + 1
                if level <= self.save.campaign_unlocked_level and btn.is_clicked(ev):
                    return level
        return None

    def draw(self, surf):
        self.tick += 1
        surf.fill((8, 6, 16))
        for y in range(0, SCREEN_H, 4):
            t = y / SCREEN_H
            pygame.draw.line(surf, (int(8+12*(1-t)), int(6+8*(1-t)), int(16+28*(1-t))),
                             (0, y), (SCREEN_W, y))

        title = self.font_title.render(T("campaign_title"), True, (180,140,255))
        surf.blit(title, title.get_rect(centerx=SCREEN_W//2, y=42))
        pygame.draw.line(surf, (80,60,140), (SCREEN_W//2-220, 104), (SCREEN_W//2+220, 104), 1)

        for i, btn in enumerate(self.level_buttons):
            level = i + 1
            unlocked = level <= self.save.campaign_unlocked_level
            completed = level < self.save.campaign_unlocked_level
            btn.label = T("campaign_level", n=level)
            btn.draw(surf)
            rect = btn.base_rect

            target = self.font_sm.render(
                T("target_wave", n=campaign_target_wave(level)),
                True, (155,150,195) if unlocked else (95,90,120))
            surf.blit(target, target.get_rect(centerx=rect.centerx, y=rect.y + 34))

            if completed:
                mark = self.font_sm.render(T("completed"), True, C_GREEN)
                surf.blit(mark, mark.get_rect(centerx=rect.centerx, y=rect.y - 16))
            elif not unlocked:
                locked = self.font_sm.render(T("locked"), True, C_RED)
                cover = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
                cover.fill((0, 0, 0, 115))
                surf.blit(cover, rect.topleft)
                surf.blit(locked, locked.get_rect(center=rect.center))

        self.btn_back.draw(surf)
        pygame.display.flip()

    def refresh_labels(self):
        self.btn_back.label = T("menu_back")
        for i, btn in enumerate(self.level_buttons):
            btn.label = T("campaign_level", n=i + 1)


# ---------------------------------------------------------------------------
# Ayarlar Ekranı
# ---------------------------------------------------------------------------
class SettingsScreen:
    VOLUMES     = [("master", "vol_master"), ("music", "vol_music"),
                   ("sfx", "vol_sfx"), ("coin", "vol_coin")]
    SLIDER_Y    = 165
    SLIDER_STEP = 52
    TOGGLE_Y    = 395

    def __init__(self, sfx):
        self.sfx        = sfx
        self.fullscreen = False
        self.tick       = 0
        self.font_title = get_sys_font(44, bold=True)
        self.font_lbl   = get_sys_font(22)
        self.font_btn   = get_sys_font(20, bold=True)
        self._build_buttons()

    def _build_buttons(self):
        cx   = SCREEN_W // 2
        ry   = self.TOGGLE_Y
        step = 60
        self.sliders = []
        for i, (name, _) in enumerate(self.VOLUMES):
            sl = Slider(cx - 40, self.SLIDER_Y + i * self.SLIDER_STEP + 22, 240,
                        self.sfx.volumes[name], self.font_lbl,
                        on_change=lambda v, n=name: self.sfx.set_volume(n, v),
                        on_release=lambda v, n=name: self._released(n))
            self.sliders.append(sl)
        self.btn_sound = Button(cx - 60, ry,        120, 48, self._slbl(), self.font_btn)
        self.btn_fs    = Button(cx - 60, ry + step,  120, 48, self._flbl(), self.font_btn)
        self.btn_back  = Button(cx - 100, ry + step*2+10, 200, 48, T("menu_back"), self.font_btn)

    def _released(self, name):
        self.sfx.save_volumes()
        if name == "coin":
            self.sfx.play_coin()
        elif name in ("master", "sfx"):
            self.sfx.play_xp()

    def _slbl(self): return T("menu_sound_off") if self.sfx.muted else T("menu_sound_on")
    def _flbl(self): return T("menu_fs_on") if self.fullscreen else T("menu_fs_off")

    def handle_events(self, events) -> Optional[str]:
        mx, my = pygame.mouse.get_pos()
        for btn in (self.btn_sound, self.btn_fs, self.btn_back):
            btn.update(mx, my)
        for ev in events:
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                self.sfx.save_volumes()
                return "back"
            for sl in self.sliders:
                sl.handle_event(ev)
            if self.btn_sound.is_clicked(ev):
                self.sfx.toggle_mute(); self.btn_sound.label = self._slbl()
            elif self.btn_fs.is_clicked(ev):
                self.fullscreen = not self.fullscreen
                flags = pygame.FULLSCREEN if self.fullscreen else 0
                pygame.display.set_mode((SCREEN_W, SCREEN_H), flags)
                self.btn_fs.label = self._flbl()
            elif self.btn_back.is_clicked(ev):
                self.sfx.save_volumes()
                return "back"
        return None

    def draw(self, surf):
        self.tick += 1
        surf.fill((10, 8, 20))
        for y in range(0, SCREEN_H, 4):
            t = y / SCREEN_H
            pygame.draw.line(surf, (int(10+10*(1-t)), int(8+6*(1-t)), int(20+24*(1-t))),
                             (0, y), (SCREEN_W, y))
        title = self.font_title.render(T("menu_settings"), True, (180,140,255))
        surf.blit(title, title.get_rect(centerx=SCREEN_W//2, y=80))
        pygame.draw.line(surf, (80,60,140), (SCREEN_W//2-200, 140), (SCREEN_W//2+200, 140), 1)
        for i, (_, key) in enumerate(self.VOLUMES):
            s = self.font_lbl.render(T(key), True, (180,175,220))
            surf.blit(s, (SCREEN_W//2 - 200, self.SLIDER_Y + i * self.SLIDER_STEP + 8))
        for sl in self.sliders:
            sl.draw(surf)
        ry   = self.TOGGLE_Y
        step = 60
        lbls = [T("menu_sound"), T("menu_fullscreen")]
        for i, lbl in enumerate(lbls):
            s = self.font_lbl.render(lbl, True, (180,175,220))
            surf.blit(s, (SCREEN_W//2 - 200, ry + i * step + 12))
        self.btn_sound.draw(surf)
        self.btn_fs.draw(surf)
        self.btn_back.draw(surf)
        pygame.display.flip()

    def refresh_labels(self):
        self.btn_sound.label = self._slbl()
        self.btn_fs.label    = self._flbl()
        self.btn_back.label  = T("menu_back")


# ---------------------------------------------------------------------------
# Màn Hình Chọn Lớp Nhân Vật RPG & Cường Hóa Vĩnh Viễn
# ---------------------------------------------------------------------------
class CharacterScreen:
    """
    Hiển thị 4 Lớp Nhân Vật RPG (Huyết Kiếm Sĩ, Pháp Sư Tinh Vân, Thợ Săn Bóng Đêm, Thánh Kỵ Sĩ)
    cùng mô hình sprite động đa lớp, thanh chỉ số, nội tại và bảng Cường Hóa Vĩnh Viễn bằng Vàng.
    """
    CARD_W, CARD_H = 278, 340
    GAP            = 20

    def __init__(self, save: SaveData):
        self.save      = save
        self.tick      = 0
        self.notice    = ""
        self.notice_cd = 0
        self.font_title = get_sys_font(36, bold=True)
        self.font_name  = get_sys_font(20, bold=True)
        self.font_sub   = get_sys_font(13, italic=True)
        self.font_desc  = get_sys_font(14)
        self.font_pass  = get_sys_font(13, bold=True)
        self.font_cost  = get_sys_font(17, bold=True)
        self.font_back  = get_sys_font(20, bold=True)
        self.font_gold  = get_sys_font(20, bold=True)
        self.btn_back  = Button(SCREEN_W // 2 - 220, SCREEN_H - 60, 200, 44, T("menu_back"), self.font_back)
        self.btn_skins = Button(SCREEN_W // 2 + 20,  SCREEN_H - 60, 220, 44, T("menu_skins"), self.font_back)

    def _card_rects(self):
        total_w = len(CHARACTER_DEFS) * self.CARD_W + (len(CHARACTER_DEFS) - 1) * self.GAP
        sx      = SCREEN_W // 2 - total_w // 2
        cy      = 86
        return [pygame.Rect(sx + i * (self.CARD_W + self.GAP), cy, self.CARD_W, self.CARD_H)
                for i in range(len(CHARACTER_DEFS))]

    def _perm_rects(self):
        w, h = 265, 58
        gap = 24
        total_w = len(PERM_UPGRADE_DEFS) * w + (len(PERM_UPGRADE_DEFS) - 1) * gap
        sx = SCREEN_W // 2 - total_w // 2
        y = 478
        return [pygame.Rect(sx + i * (w + gap), y, w, h) for i in range(len(PERM_UPGRADE_DEFS))]

    def handle_events(self, events) -> Optional[str]:
        mx, my = pygame.mouse.get_pos()
        self.btn_back.update(mx, my)
        self.btn_skins.update(mx, my)
        rects = self._card_rects()
        p_rects = self._perm_rects()
        if self.notice_cd > 0:
            self.notice_cd -= 1
        for ev in events:
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                return "back"
            if self.btn_back.is_clicked(ev):
                return "back"
            if self.btn_skins.is_clicked(ev):
                return "skins"
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                for i, rect in enumerate(rects):
                    if rect.collidepoint(ev.pos):
                        cdef = CHARACTER_DEFS[i]
                        if cdef["id"] in self.save.unlocked_ids:
                            self.save.selected_id = cdef["id"]
                            self.save.save()
                        elif self.save.total_gold >= cdef["cost"]:
                            self.save.unlock(cdef["id"], cdef["cost"])
                            self.save.selected_id = cdef["id"]
                            self.save.save()
                        else:
                            self.notice    = T("not_enough")
                            self.notice_cd = 120
                for i, pr in enumerate(p_rects):
                    if pr.collidepoint(ev.pos):
                        key, _, base_cost, max_lv = PERM_UPGRADE_DEFS[i]
                        cur = self.save.perm_upgrades.get(key, 0)
                        if cur < max_lv:
                            if not self.save.buy_perm_upgrade(key, base_cost, max_lv):
                                self.notice = T("not_enough")
                                self.notice_cd = 120
        return None

    def draw(self, surf):
        self.tick += 1
        surf.fill((8, 6, 16))
        for y in range(0, SCREEN_H, 4):
            t = y / SCREEN_H
            pygame.draw.line(surf, (int(8+12*(1-t)), int(6+8*(1-t)), int(16+28*(1-t))),
                             (0, y), (SCREEN_W, y))
        title = self.font_title.render(T("menu_chars"), True, (195, 155, 255))
        surf.blit(title, title.get_rect(centerx=SCREEN_W // 2, y=22))

        gold_s = self.font_gold.render(f"{T('gold')}: {self.save.total_gold}", True, C_YELLOW)
        surf.blit(gold_s, (SCREEN_W - gold_s.get_width() - 28, 28))

        rects = self._card_rects()
        mx, my = pygame.mouse.get_pos()

        for i, (cdef, rect) in enumerate(zip(CHARACTER_DEFS, rects)):
            cid      = cdef["id"]
            owned    = cid in self.save.unlocked_ids
            selected = cid == self.save.selected_id
            hovering = rect.collidepoint(mx, my)

            bg_alpha = 235 if (hovering or selected) else 185
            card_s   = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
            card_s.fill((16, 14, 30, bg_alpha))
            surf.blit(card_s, rect.topleft)

            border_c = cdef["color"] if selected else ((195, 185, 255) if hovering else (65, 60, 110))
            border_w = 3 if selected else (2 if hovering else 1)
            pygame.draw.rect(surf, border_c, rect, border_w, border_radius=10)

            # Vẽ mô hình nhân vật procedural động trực tiếp trên thẻ bài (nếu đang chọn thì hiển thị luôn Skin Anime đang mặc)
            preview_x = rect.centerx
            preview_y = rect.y + 68
            dark_c = tuple(max(0, int(c * 0.5)) for c in cdef["color"])
            sway_x = math.sin(self.tick * 0.06 + i) * 0.65
            preview_skin = self.save.equipped_skin if selected else "default"
            draw_character_procedural_sprite(
                surf, cid, preview_x, preview_y, 18,
                cdef["color"], dark_c, math.sin(self.tick * 0.04 + i) * 0.35,
                self.tick, vx=sway_x, vy=0.0, moving=True,
                cape_sway=(sway_x, 0.2), is_preview=True,
                skin_id=preview_skin,
            )

            # Tên & Biệt danh RPG Class
            char_name = STRINGS[LANG]["char_names"].get(cid, cdef["name"])
            ns = self.font_name.render(char_name, True,
                                       cdef["color"] if owned else (140, 140, 155))
            surf.blit(ns, ns.get_rect(centerx=rect.centerx, y=rect.y + 118))

            sub_dict = STRINGS[LANG].get("char_subtitles", {})
            if cid in sub_dict:
                sub_s = self.font_sub.render(sub_dict[cid], True, (150, 145, 185))
                surf.blit(sub_s, sub_s.get_rect(centerx=rect.centerx, y=rect.y + 143))

            # Mô tả chỉ số & Nội tại
            char_desc = STRINGS[LANG]["char_descs"].get(cid, cdef["desc"])
            ds = self.font_desc.render(char_desc, True, (215, 215, 240))
            surf.blit(ds, ds.get_rect(centerx=rect.centerx, y=rect.y + 168))

            pass_dict = STRINGS[LANG].get("char_passives", {})
            if cid in pass_dict:
                ps = self.font_pass.render(pass_dict[cid], True, (255, 215, 95))
                surf.blit(ps, ps.get_rect(centerx=rect.centerx, y=rect.y + 192))

            # Thanh chỉ số (Stat Bars)
            bars = cdef.get("stats_bars", [])
            for b_i, (b_lbl, b_val) in enumerate(bars):
                by_bar = rect.y + 222 + b_i * 22
                lbl_b = self.font_desc.render(b_lbl, True, (170, 165, 205))
                surf.blit(lbl_b, (rect.x + 18, by_bar - 2))
                bx_bar = rect.x + 70
                bw_bar = rect.w - 88
                pygame.draw.rect(surf, (32, 28, 52), (bx_bar, by_bar + 3, bw_bar, 8), border_radius=4)
                pygame.draw.rect(surf, cdef["color"], (bx_bar, by_bar + 3, int(bw_bar * b_val), 8), border_radius=4)

            # Nút Chọn / Mở khóa dưới đáy thẻ
            btn_rect = pygame.Rect(rect.x + 24, rect.bottom - 42, rect.w - 48, 30)
            pygame.draw.rect(surf, (28, 24, 48), btn_rect, border_radius=6)
            pygame.draw.rect(surf, border_c, btn_rect, 1, border_radius=6)
            if selected:
                lbl_s = self.font_cost.render(T("selected"), True, C_GREEN)
            elif owned:
                lbl_s = self.font_cost.render(T("owned"), True, (160, 235, 175))
            else:
                lbl_s = self.font_cost.render(
                    f"{cdef['cost']}G - {T('buy')}", True,
                    C_YELLOW if self.save.total_gold >= cdef["cost"] else C_RED)
            surf.blit(lbl_s, lbl_s.get_rect(center=btn_rect.center))

            if not owned:
                lock_s = self.font_pass.render(T("locked"), True, (220, 100, 100))
                surf.blit(lock_s, lock_s.get_rect(centerx=rect.centerx, y=rect.y + 10))

        # Khu vực Cường Hóa Vĩnh Viễn (Permanent Stat Upgrades)
        perm_title = self.font_pass.render(T("perm_upgrades"), True, (255, 215, 90))
        surf.blit(perm_title, perm_title.get_rect(centerx=SCREEN_W // 2, y=452))
        p_rects = self._perm_rects()
        for i, (key, label_key, base_cost, max_lv) in enumerate(PERM_UPGRADE_DEFS):
            pr = p_rects[i]
            cur = self.save.perm_upgrades.get(key, 0)
            hov = pr.collidepoint(mx, my)
            pygame.draw.rect(surf, (24, 20, 44) if not hov else (40, 34, 72), pr, border_radius=8)
            pygame.draw.rect(surf, (130, 110, 220) if hov else (75, 65, 130), pr, 2 if hov else 1, border_radius=8)
            p_name = self.font_desc.render(f"{T(label_key)} Lv.{cur}/{max_lv}", True, C_WHITE)
            surf.blit(p_name, (pr.x + 12, pr.y + 8))
            if cur >= max_lv:
                c_txt = self.font_pass.render("MAX", True, C_GREEN)
            else:
                cost = base_cost * (cur + 1)
                c_txt = self.font_pass.render(f"{cost} Vàng", True,
                                              C_YELLOW if self.save.total_gold >= cost else C_RED)
            surf.blit(c_txt, (pr.right - c_txt.get_width() - 12, pr.y + 8))
            # Các ô cấp độ
            for lv_i in range(max_lv):
                pip_r = pygame.Rect(pr.x + 12 + lv_i * 46, pr.y + 34, 38, 10)
                pygame.draw.rect(surf, (255, 210, 65) if lv_i < cur else (45, 40, 70), pip_r, border_radius=3)

        self.btn_back.label = T("menu_back")
        self.btn_skins.label = T("menu_skins")
        self.btn_back.draw(surf)
        self.btn_skins.draw(surf)

        if self.notice_cd > 0:
            alpha = min(255, self.notice_cd * 4)
            ns = self.font_cost.render(self.notice, True, C_RED)
            ns.set_alpha(alpha)
            surf.blit(ns, ns.get_rect(centerx=SCREEN_W // 2, y=SCREEN_H - 92))

        pygame.display.flip()


# ---------------------------------------------------------------------------
# Cửa Hàng Trang Phục Anime & Tùy Chỉnh Ngoại Hình ("Cửa Hàng Trang Phục")
# ---------------------------------------------------------------------------
class SkinShopScreen:
    """
    Cửa Hàng Trang Phục (Anime Skin Shop & Wardrobe):
    Hiển thị 4 bộ trang phục Anime biểu tượng với mô hình nhân vật procedural động trực tiếp,
    tên Tiếng Việt, nhãn bộ Anime, mô tả biến đổi hiệu ứng kỹ năng (VFX Twist), giá Vàng
    và nút Mua / Trang Bị / Đang Dùng + nút chuyển về Ngoại Hình Mặc Định.
    """
    CARD_W, CARD_H = 278, 390
    GAP            = 20

    def __init__(self, save: SaveData, sfx=None):
        self.save      = save
        self.sfx       = sfx
        self.tick      = 0
        self.notice    = ""
        self.notice_cd = 0
        self.font_title = get_sys_font(34, bold=True)
        self.font_subt  = get_sys_font(15)
        self.font_name  = get_sys_font(17, bold=True)
        self.font_tag   = get_sys_font(13, italic=True)
        self.font_desc  = get_sys_font(13)
        self.font_vfx   = get_sys_font(13, bold=True)
        self.font_cost  = get_sys_font(16, bold=True)
        self.font_back  = get_sys_font(19, bold=True)
        self.font_gold  = get_sys_font(20, bold=True)
        self.btn_back    = Button(SCREEN_W // 2 - 250, SCREEN_H - 64, 210, 44, T("menu_back"), self.font_back)
        self.btn_default = Button(SCREEN_W // 2 - 20,  SCREEN_H - 64, 270, 44, T("skin_default_btn"), self.font_back)

    def _card_rects(self) -> List[pygame.Rect]:
        total_w = len(ANIME_SKINS) * self.CARD_W + (len(ANIME_SKINS) - 1) * self.GAP
        sx      = SCREEN_W // 2 - total_w // 2
        cy      = 106
        return [pygame.Rect(sx + i * (self.CARD_W + self.GAP), cy, self.CARD_W, self.CARD_H)
                for i in range(len(ANIME_SKINS))]

    @staticmethod
    def _wrap_text(text: str, font, max_w: int) -> List[str]:
        words = text.split()
        lines = []
        cur = ""
        for w in words:
            test = f"{cur} {w}".strip()
            if font.size(test)[0] <= max_w:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines

    def handle_events(self, events) -> Optional[str]:
        mx, my = pygame.mouse.get_pos()
        self.btn_back.update(mx, my)
        self.btn_default.update(mx, my)
        rects = self._card_rects()
        if self.notice_cd > 0:
            self.notice_cd -= 1
        for ev in events:
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                return "back"
            if self.btn_back.is_clicked(ev):
                return "back"
            if self.btn_default.is_clicked(ev):
                self.save.equip_skin("default")
                if self.sfx:
                    self.sfx.play_xp()
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                for i, rect in enumerate(rects):
                    if rect.collidepoint(ev.pos):
                        sdef = ANIME_SKINS[i]
                        sid = sdef.get("id", f"skin_{i}")
                        cost = get_skin_cost(sdef)
                        if sid in self.save.owned_skins:
                            self.save.equip_skin(sid)
                            if self.sfx:
                                self.sfx.play_levelup()
                        elif self.save.total_gold >= cost:
                            self.save.buy_skin(sid, cost)
                            if self.sfx:
                                self.sfx.play_levelup()
                        else:
                            self.notice    = T("not_enough")
                            self.notice_cd = 120
        return None

    def draw(self, surf):
        self.tick += 1
        surf.fill((8, 6, 18))
        for y in range(0, SCREEN_H, 4):
            t = y / SCREEN_H
            pygame.draw.line(surf, (int(8 + 14 * (1 - t)), int(6 + 9 * (1 - t)), int(18 + 30 * (1 - t))),
                             (0, y), (SCREEN_W, y))

        title = self.font_title.render(T("skin_shop_title"), True, (255, 215, 75))
        surf.blit(title, title.get_rect(centerx=SCREEN_W // 2, y=18))
        sub = self.font_subt.render(T("skin_shop_sub"), True, (185, 175, 230))
        surf.blit(sub, sub.get_rect(centerx=SCREEN_W // 2, y=60))

        gold_txt = self.font_gold.render(f"{T('gold')}: {self.save.total_gold}", True, C_YELLOW)
        g_rect = pygame.Rect(SCREEN_W - gold_txt.get_width() - 48, 22, gold_txt.get_width() + 32, 36)
        pygame.draw.rect(surf, (20, 16, 38), g_rect, border_radius=8)
        pygame.draw.rect(surf, (220, 180, 50), g_rect, 2, border_radius=8)
        surf.blit(gold_txt, gold_txt.get_rect(center=g_rect.center))

        rects = self._card_rects()
        mx, my = pygame.mouse.get_pos()

        for i, (sdef, rect) in enumerate(zip(ANIME_SKINS, rects)):
            sid      = sdef.get("id", f"skin_{i}")
            owned    = sid in self.save.owned_skins
            equipped = (self.save.equipped_skin == sid)
            hovering = rect.collidepoint(mx, my)
            col      = sdef.get("color", sdef.get("primary", (220, 220, 240)))
            skin_cost = get_skin_cost(sdef)

            bg_alpha = 242 if (hovering or equipped) else 195
            card_s   = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
            card_s.fill((18, 14, 34, bg_alpha))
            surf.blit(card_s, rect.topleft)

            border_c = (255, 225, 75) if equipped else (col if hovering else (75, 65, 125))
            border_w = 3 if equipped else (2 if hovering else 1)
            pygame.draw.rect(surf, border_c, rect, border_w, border_radius=12)

            # Hào quang nền phía sau mô hình Anime Skin
            preview_x = rect.centerx
            preview_y = rect.y + 78
            draw_additive_glow(surf, preview_x, preview_y, 44, sdef.get("vfx_primary", col), intensity=0.45 if (hovering or equipped) else 0.25)

            dark_c = tuple(max(0, int(c * 0.5)) for c in col)
            sway_x = math.sin(self.tick * 0.06 + i) * 0.65
            draw_character_procedural_sprite(
                surf, self.save.selected_id, preview_x, preview_y, 20,
                col, dark_c, math.sin(self.tick * 0.04 + i) * 0.35,
                self.tick, vx=sway_x, vy=0.0, moving=True,
                cape_sway=(sway_x, 0.2), is_preview=True,
                skin_id=sid,
            )

            # Tên Trang Phục Anime
            ns = self.font_name.render(sdef.get("name", sid), True, col)
            surf.blit(ns, ns.get_rect(centerx=rect.centerx, y=rect.y + 140))

            # Nhãn bộ Anime (Dragon Ball / Naruto / Jujutsu Kaisen / One Piece)
            tag_s = self.font_tag.render(sdef.get("anime_tag", ""), True, (165, 210, 255))
            surf.blit(tag_s, tag_s.get_rect(centerx=rect.centerx, y=rect.y + 165))

            # Mô tả ngoại hình (tự động xuống dòng)
            desc_lines = self._wrap_text(sdef.get("desc", ""), self.font_desc, rect.w - 28)
            for l_i, line in enumerate(desc_lines[:3]):
                ds = self.font_desc.render(line, True, (220, 215, 240))
                surf.blit(ds, ds.get_rect(centerx=rect.centerx, y=rect.y + 194 + l_i * 19))

            # Mô tả Biến Đổi Hiệu Ứng Kỹ Năng (VFX Twist)
            vfx_lines = self._wrap_text("★ " + sdef.get("vfx_desc", ""), self.font_vfx, rect.w - 24)
            for l_i, line in enumerate(vfx_lines[:2]):
                vs = self.font_vfx.render(line, True, (255, 215, 85))
                surf.blit(vs, vs.get_rect(centerx=rect.centerx, y=rect.y + 262 + l_i * 19))

            # Nút Mua / Trang Bị / Đang Dùng dưới đáy thẻ
            btn_rect = pygame.Rect(rect.x + 20, rect.bottom - 48, rect.w - 40, 34)
            btn_bg = (35, 65, 45) if equipped else ((38, 30, 68) if hovering else (26, 22, 46))
            pygame.draw.rect(surf, btn_bg, btn_rect, border_radius=8)
            pygame.draw.rect(surf, border_c, btn_rect, 2 if (equipped or hovering) else 1, border_radius=8)

            if equipped:
                lbl_s = self.font_cost.render(T("skin_equipped"), True, C_GREEN)
            elif owned:
                lbl_s = self.font_cost.render(T("skin_equip"), True, (150, 240, 255))
            else:
                can_afford = self.save.total_gold >= skin_cost
                lbl_s = self.font_cost.render(
                    T("skin_buy_fmt", cost=skin_cost),
                    True, C_YELLOW if can_afford else C_RED
                )
            surf.blit(lbl_s, lbl_s.get_rect(center=btn_rect.center))

        self.btn_back.label = T("menu_back")
        self.btn_default.label = (
            T("skin_using_default") if self.save.equipped_skin == "default" else T("skin_default_btn")
        )
        self.btn_back.draw(surf)
        self.btn_default.draw(surf)

        if self.notice_cd > 0:
            alpha = min(255, self.notice_cd * 4)
            ns = self.font_cost.render(self.notice, True, C_RED)
            ns.set_alpha(alpha)
            surf.blit(ns, ns.get_rect(centerx=SCREEN_W // 2, y=SCREEN_H - 96))

        pygame.display.flip()


# ---------------------------------------------------------------------------
# Ana oyun
# ---------------------------------------------------------------------------
# Boss spawn aralığı (saniye)
BOSS_INTERVAL = 120   # 2 dakikada bir boss

class Game:
    def __init__(self):
        global _last_non_en
        _last_non_en = "VI"
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption("Vampire Survivors Clone — Dark Fantasy & Cyber-Arcane")
        self.clock  = pygame.time.Clock()
        self.sfx    = SoundEngine()

        self.font_sm   = get_sys_font(16)
        self.font_med  = get_sys_font(22, bold=True)
        self.font_big  = get_sys_font(36, bold=True)
        self.font_dmg  = get_sys_font(15, bold=True)
        self.font_bar  = get_sys_font(12, bold=True)

        # Dữ liệu lưu trữ bền vững (save_data.json)
        self.save          = SaveData()

        # Hệ thống thành tựu
        self.ach_mgr       = AchievementManager(self.save, self.sfx)

        # State machine
        self.state         = GameState.MENU
        self.main_menu     = MainMenu(self.sfx, self.save)
        self.campaign_scr  = CampaignScreen(self.save)
        self.settings_scr  = SettingsScreen(self.sfx)
        self.char_scr      = CharacterScreen(self.save)
        self.skin_shop_scr = SkinShopScreen(self.save, self.sfx)
        self.skin_shop_return = GameState.MENU
        self.campaign_mode = False
        self.campaign_level = 1
        self.level_completed = False
        btn_y = SCREEN_H // 2 + 90
        self.btn_next_level = Button(SCREEN_W // 2 - 240, btn_y, 220, 52,
                                     T("next_level"), self.font_med)
        self.btn_completed_menu = Button(SCREEN_W // 2 + 20, btn_y, 220, 52,
                                         T("main_menu"), self.font_med)

        # Nút Điều khiển (giữa dưới) và bảng điều khiển
        self.btn_controls = Button(SCREEN_W // 2 - 65, SCREEN_H - 38, 130, 28,
                                   T("controls_btn"), self.font_sm)
        self.controls_panel = pygame.Rect(0, 0, 580, 400)
        self.controls_panel.center = (SCREEN_W // 2, SCREEN_H // 2)
        self.btn_controls_close = Button(self.controls_panel.centerx - 80,
                                         self.controls_panel.bottom - 64, 160, 44,
                                         T("close"), self.font_med)

        # Tùy chọn trong Menu Tạm Dừng (Pause Menu)
        self.shake_enabled = True
        self.vfx_high      = True
        self.biome_id      = 0
        self.pause_sel_idx = 0
        self.pause_settings_open = False

        self.reset()

    # -----------------------------------------------------------------------
    def _apply_char_mods(self):
        """Áp dụng chỉ số khởi đầu của Hệ Phái (RPG Class - Đúng 1 Kỹ năng Độc quyền Lv1) và Cường Hóa Vĩnh Viễn."""
        p    = self.player
        cdef = next((c for c in CHARACTER_DEFS if c["id"] == self.save.selected_id), CHARACTER_DEFS[0])
        mods = cdef["mods"]
        if "max_hp"            in mods: p.max_hp   += mods["max_hp"];   p.hp += mods["max_hp"]
        if "armor"             in mods: p.armor    += mods["armor"]
        if "speed_mult"        in mods: p.speed_mult += mods["speed_mult"]
        if "recovery"          in mods: p.recovery += mods["recovery"]
        if "damage_mult"       in mods: p.damage_mult += mods["damage_mult"]
        if "cdr"               in mods: p.cdr      += mods["cdr"]
        if "crit_chance"       in mods: p.crit_chance += mods["crit_chance"]
        if "bonus_pierce"      in mods: p.bonus_pierce += mods["bonus_pierce"]
        if "lifesteal_on_kill" in mods: p.lifesteal_on_kill += mods["lifesteal_on_kill"]

        skill_mod_map = [
            ("whip_level",       p.whip),
            ("void_level",       p.void_singularity),
            ("arrow_level",      p.phantom_arrow),
            ("hammer_level",     p.judgement_hammer),
            ("orb_level",        p.orb),
            ("aura_level",       p.aura),
            ("boomerang_level",  p.boomerang),
            ("lightning_level",  p.lightning_staff),
            ("ice_level",        p.ice_wand),
            ("fire_trail_level", p.fire_trail),
            ("familiar_level",   p.familiar),
        ]
        for mod_key, wpn_obj in skill_mod_map:
            if mod_key in mods:
                for _ in range(mods[mod_key]):
                    wpn_obj.upgrade()

        # Áp dụng Cường Hóa Vĩnh Viễn từ save_data.json
        pu = self.save.perm_upgrades
        if pu.get("hp", 0) > 0:
            bonus_hp = pu["hp"] * 25
            p.max_hp += bonus_hp
            p.hp     += bonus_hp
        if pu.get("dmg", 0) > 0:
            p.damage_mult += pu["dmg"] * 0.08
        if pu.get("spd", 0) > 0:
            p.speed_mult  += pu["spd"] * 0.05
        if pu.get("gold", 0) > 0:
            p.gold_mult   += pu["gold"] * 0.15

    # -----------------------------------------------------------------------
    def reset(self):
        cdef = next((c for c in CHARACTER_DEFS if c["id"] == self.save.selected_id), CHARACTER_DEFS[0])
        self.player       = Player(WORLD_W // 2, WORLD_H // 2,
                                   character_id=cdef["id"], color=cdef["color"],
                                   skin_id=self.save.equipped_skin)
        self._apply_char_mods()

        self.enemies:       List[Enemy]       = []
        self.bosses:        List[Boss]        = []
        self.enemy_projs:   List[Projectile]  = []
        self.player_projs:  List[Projectile]  = []
        self.particles:     List[Particle]    = []
        self.damage_numbers:List[DamageNumber]= []
        self.xp_gems:       List[XPGem]       = []
        self.gold_coins:    List[GoldCoin]    = []
        self.items:         List[Union[HealthPotion, ExpMagnet]] = []
        self.shockwaves:    List[ShockwaveRing] = []

        # Rương — 5 rương khởi đầu
        self.chests: List[Chest]  = [Chest() for _ in range(5)]
        # Drone và tháp pháo
        self.drones:  List[Drone]  = []
        self.turrets: List[Turret] = []

        self.spawn_mgr   = SpawnManager()
        self.tick        = 0
        self.paused      = False
        self.pause_sel_idx = 0
        self.pause_settings_open = False
        self.controls_open     = False
        self.weapons_collapsed = False
        self._weapons_toggle_rect: Optional[pygame.Rect] = None
        self.game_over   = False
        self.level_completed = False
        self.upgrade_screen: Optional[UpgradeScreen] = None
        self.kills       = 0
        self.session_gold = 0

        self.boss_alert_timer = 0
        self.screen_flash_alpha = 0
        self.screen_shake = 0

        self.quest_mgr   = QuestManager()
        self._prev_kills = 0
        self._prev_gold  = 0

        self.cam_x = self.player.x - SCREEN_W // 2
        self.cam_y = self.player.y - SCREEN_H // 2
        self.ambient_particles: List[AmbientParticle] = [
            AmbientParticle(self.cam_x, self.cam_y) for _ in range(45)
        ]

    # -----------------------------------------------------------------------
    def _flush_session_save(self):
        """Lưu toàn bộ vàng thu thập được và kỷ lục trận đấu vào save_data.json."""
        if self.session_gold > 0:
            self.save.total_gold += self.session_gold
            self.save.lifetime_gold += self.session_gold
            self.session_gold = 0
        if self.tick > 0:
            self.save.record_match_stats(
                self.kills,
                self.tick // FPS,
                self.spawn_mgr.wave + 1,
                self.player.level,
            )
        else:
            self.save.save()

    # -----------------------------------------------------------------------
    # State geçişleri
    # -----------------------------------------------------------------------
    def _go_menu(self):
        self._flush_session_save()
        self.campaign_mode = False
        self.state = GameState.MENU
        self.main_menu.refresh_labels()
        self.campaign_scr = CampaignScreen(self.save)
        self.char_scr = CharacterScreen(self.save)
        self.skin_shop_scr = SkinShopScreen(self.save, self.sfx)

    def _go_settings(self):
        self.state = GameState.SETTINGS
        self.settings_scr.refresh_labels()

    def _go_campaign(self):
        self.state = GameState.CAMPAIGN
        self.campaign_scr.refresh_labels()

    def _go_chars(self):
        self.state    = GameState.CHARACTERS
        self.char_scr = CharacterScreen(self.save)

    def _go_skins(self, return_to=GameState.MENU):
        self.skin_shop_return = return_to
        self.state = GameState.SKIN_SHOP
        self.skin_shop_scr = SkinShopScreen(self.save, self.sfx)

    def _go_playing(self, campaign_level=None):
        self.campaign_mode = campaign_level is not None
        if campaign_level is not None:
            self.campaign_level = campaign_level
        self.reset()
        self.state = GameState.PLAYING

    def _complete_campaign_level(self):
        self.level_completed = True
        self.paused = True
        self.upgrade_screen = None
        self.save.complete_campaign_level(self.campaign_level)
        self._flush_session_save()
        self.campaign_scr = CampaignScreen(self.save)

    def _go_next_campaign_level(self):
        next_level = min(30, self.campaign_level + 1)
        if next_level <= self.save.campaign_unlocked_level:
            self._go_playing(next_level)
        else:
            self._go_menu()

    # -----------------------------------------------------------------------
    def run(self):
        while True:
            self.clock.tick(FPS)
            raw = pygame.event.get()

            for ev in raw:
                if ev.type == pygame.QUIT:
                    self._flush_session_save()
                    self.sfx.save_volumes()
                    pygame.quit(); sys.exit()

            # ── MENU ───────────────────────────────────────────────────────
            if self.state == GameState.MENU:
                action = self.main_menu.handle_events(raw)
                if   action == "play":     self._go_playing()
                elif action == "campaign": self._go_campaign()
                elif action == "chars":    self._go_chars()
                elif action == "skins":    self._go_skins(GameState.MENU)
                elif action == "settings": self._go_settings()
                elif action == "quit":
                    self._flush_session_save()
                    self.sfx.save_volumes()
                    pygame.quit(); sys.exit()
                else:
                    for ev in raw:
                        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_l:
                            toggle_lang(); self.main_menu.refresh_labels()
                    self.main_menu.draw(self.screen)

            # ── CAMPAIGN ──────────────────────────────────────────────────
            elif self.state == GameState.CAMPAIGN:
                action = self.campaign_scr.handle_events(raw)
                if action == "back":
                    self._go_menu()
                elif isinstance(action, int):
                    self._go_playing(action)
                else:
                    for ev in raw:
                        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_l:
                            toggle_lang(); self.campaign_scr.refresh_labels()
                    self.campaign_scr.draw(self.screen)

            # ── SETTINGS ───────────────────────────────────────────────────
            elif self.state == GameState.SETTINGS:
                action = self.settings_scr.handle_events(raw)
                if action == "back": self._go_menu()
                else: self.settings_scr.draw(self.screen)

            # ── CHARACTERS ─────────────────────────────────────────────────
            elif self.state == GameState.CHARACTERS:
                action = self.char_scr.handle_events(raw)
                if action == "back": self._go_menu()
                elif action == "skins": self._go_skins(GameState.CHARACTERS)
                else: self.char_scr.draw(self.screen)

            # ── SKIN SHOP ──────────────────────────────────────────────────
            elif self.state == GameState.SKIN_SHOP:
                action = self.skin_shop_scr.handle_events(raw)
                if action == "back":
                    if self.skin_shop_return == GameState.CHARACTERS:
                        self._go_chars()
                    else:
                        self._go_menu()
                else:
                    self.skin_shop_scr.draw(self.screen)

            # ── PLAYING ────────────────────────────────────────────────────
            elif self.state == GameState.PLAYING:
                for ev in raw:
                    if self.level_completed:
                        mx, my = pygame.mouse.get_pos()
                        self.btn_next_level.update(mx, my)
                        self.btn_completed_menu.update(mx, my)
                        if self.btn_next_level.is_clicked(ev):
                            if self.campaign_level < 30:
                                self._go_next_campaign_level()
                            else:
                                self._go_menu()
                            break
                        if self.btn_completed_menu.is_clicked(ev):
                            self._go_menu(); break
                        continue
                    if self.controls_open:
                        if ((ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE)
                                or self.btn_controls_close.is_clicked(ev)):
                            self.controls_open = False
                        elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_l:
                            toggle_lang()
                        elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_m:
                            self.sfx.toggle_mute()
                        continue

                    # Khi đang mở Menu Tạm Dừng (Pause Menu): Điều khiển bằng Chuột & Phím Mũi tên + Enter
                    if self.paused and not self.upgrade_screen and not self.game_over:
                        if self._handle_pause_event(ev):
                            break
                        continue

                    if (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1
                            and not self.upgrade_screen and not self.game_over):
                        if self.btn_controls.is_clicked(ev):
                            self.controls_open = True
                            continue
                        wr = self._weapons_toggle_rect
                        if wr and wr.collidepoint(ev.pos):
                            self.weapons_collapsed = not self.weapons_collapsed
                            continue
                        qr = self.quest_mgr.toggle_rect
                        if qr and qr.collidepoint(ev.pos):
                            self.quest_mgr.collapsed = not self.quest_mgr.collapsed
                            continue
                    if ev.type == pygame.KEYDOWN:
                        # Phím ESC hoặc P: Bật/Tắt Menu Tạm Dừng (KHÔNG thoát game ngay lập tức!)
                        if ev.key in (pygame.K_ESCAPE, pygame.K_p):
                            if self.game_over and ev.key == pygame.K_ESCAPE:
                                self._go_menu(); break
                            elif not self.upgrade_screen and not self.game_over:
                                self.paused = not self.paused
                                self.pause_sel_idx = 0
                                self.pause_settings_open = False
                        elif ev.key == pygame.K_l:
                            toggle_lang()
                        elif ev.key == pygame.K_m:
                            self.sfx.toggle_mute()
                        elif ev.key == pygame.K_b and not self.upgrade_screen:
                            self.biome_id = (self.biome_id + 1) % 3
                        elif self.game_over and ev.key == pygame.K_r:
                            self._go_playing(self.campaign_level if self.campaign_mode else None); break
                    if self.upgrade_screen:
                        result = self.upgrade_screen.handle_event(ev)
                        if result:
                            self._apply_upgrade(result)
                            self.upgrade_screen = None
                            self.paused = False

                if self.state == GameState.PLAYING:
                    if (not self.paused and not self.game_over and not self.upgrade_screen
                            and not self.level_completed and not self.controls_open):
                        self._update()
                    self._draw()

    # -----------------------------------------------------------------------
    def _pause_btn_rects(self) -> List[pygame.Rect]:
        bw, bh = 340, 48
        bx = SCREEN_W // 2 + 25
        start_y = SCREEN_H // 2 - 75
        return [pygame.Rect(bx, start_y + i * 60, bw, bh) for i in range(4)]

    def _pause_setting_rects(self) -> List[pygame.Rect]:
        bw, bh = 340, 44
        bx = SCREEN_W // 2 + 25
        start_y = SCREEN_H // 2 - 70
        return [pygame.Rect(bx, start_y + i * 56, bw, bh) for i in range(4)]

    def _execute_pause_option(self, idx: int) -> bool:
        """Thực thi lựa chọn trong Menu Tạm Dừng. Trả về True nếu chuyển state."""
        if self.pause_settings_open:
            if idx == 0:
                self.sfx.toggle_mute()
            elif idx == 1:
                self.shake_enabled = not self.shake_enabled
            elif idx == 2:
                self.vfx_high = not self.vfx_high
            elif idx == 3:
                self.pause_settings_open = False
                self.pause_sel_idx = 2
            return False

        if idx == 0:    # Tiếp tục (Resume)
            self.paused = False
            return False
        elif idx == 1:  # Chơi lại (Restart)
            self._flush_session_save()
            self._go_playing(self.campaign_level if self.campaign_mode else None)
            return True
        elif idx == 2:  # Cài đặt âm thanh / Hiệu ứng (Settings)
            self.pause_settings_open = True
            self.pause_sel_idx = 0
            return False
        elif idx == 3:  # Về Menu Chính (Main Menu - Lưu Vàng vào save_data.json)
            self._go_menu()
            return True
        return False

    def _handle_pause_event(self, ev) -> bool:
        rects = self._pause_setting_rects() if self.pause_settings_open else self._pause_btn_rects()
        if ev.type == pygame.MOUSEMOTION:
            for i, r in enumerate(rects):
                if r.collidepoint(ev.pos):
                    self.pause_sel_idx = i
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for i, r in enumerate(rects):
                if r.collidepoint(ev.pos):
                    self.pause_sel_idx = i
                    return self._execute_pause_option(i)
        elif ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_ESCAPE, pygame.K_p):
                if self.pause_settings_open:
                    self.pause_settings_open = False
                    self.pause_sel_idx = 2
                else:
                    self.paused = False
                return False
            elif ev.key in (pygame.K_UP, pygame.K_w):
                self.pause_sel_idx = (self.pause_sel_idx - 1) % len(rects)
            elif ev.key in (pygame.K_DOWN, pygame.K_s):
                self.pause_sel_idx = (self.pause_sel_idx + 1) % len(rects)
            elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                return self._execute_pause_option(self.pause_sel_idx)
            elif ev.key == pygame.K_l:
                toggle_lang()
            elif ev.key == pygame.K_m:
                self.sfx.toggle_mute()
        return False

    # -----------------------------------------------------------------------
    def _apply_upgrade(self, ut: UpgradeType):
        p = self.player
        awakened_now = False
        fused_now = False
        new_lv = 0
        if ut == UpgradeType.MAX_HP:
            p.max_hp += 40; p.hp = min(p.max_hp, p.hp + 40)
        elif ut == UpgradeType.SPEED:
            p.speed_mult *= 1.10
        elif ut == UpgradeType.RECOVERY:
            p.recovery += 1
        elif ut == UpgradeType.ARMOR:
            p.armor += 2
        elif ut == UpgradeType.FUSION_BLOOD_DOMAIN:
            p.whip.fused = True; p.aura.fused = True
            p.unlocked_fusions.add(ut); fused_now = True
        elif ut == UpgradeType.FUSION_COSMIC_TEMPEST:
            p.void_singularity.fused = True; p.lightning_staff.fused = True
            p.unlocked_fusions.add(ut); fused_now = True
        elif ut == UpgradeType.FUSION_REAPER_HURRICANE:
            p.phantom_arrow.fused = True; p.boomerang.fused = True
            p.unlocked_fusions.add(ut); fused_now = True
        elif ut == UpgradeType.FUSION_SOLAR_APOCALYPSE:
            p.judgement_hammer.fused = True; p.fire_trail.fused = True
            p.unlocked_fusions.add(ut); fused_now = True
        else:
            w = p.get_weapon(ut)
            if w is not None:
                prev_awk = w.awakened
                w.upgrade()
                new_lv = w.level
                awakened_now = (not prev_awk) and w.awakened

        # ── Level-Up & Fusion Burst VFX ────────────────────────────────────
        title_str, _, u_color = get_upgrade_def(ut)
        burst_col = (255, 65, 80) if fused_now else ((255, 215, 70) if awakened_now else u_color)
        self.shockwaves.append(ShockwaveRing(p.x, p.y, burst_col, max_radius=150 if not (awakened_now or fused_now) else 250, duration=30, width=6))
        self.shockwaves.append(ShockwaveRing(p.x, p.y, (120, 240, 255), max_radius=95 if not (awakened_now or fused_now) else 175, duration=24, width=3))
        if awakened_now or fused_now:
            self.shockwaves.append(ShockwaveRing(p.x, p.y, (255, 220, 65), max_radius=300, duration=38, width=7))

        pt_count = 65 if fused_now else (50 if awakened_now else 32)
        if not self.vfx_high:
            pt_count //= 2
        for _ in range(pt_count):
            pt_col = random.choice([(255, 225, 80), (90, 240, 255), burst_col])
            pt = Particle(p.x + random.uniform(-18, 18), p.y + random.uniform(-10, 14),
                          pt_col, speed=random.uniform(2.5, 6.5), size=random.randint(3, 6), life=38)
            pt.vy -= random.uniform(1.2, 2.8)
            self.particles.append(pt)

        lv_suffix = f" Lv.{new_lv}" if new_lv > 0 else ""
        if fused_now:
            self.damage_numbers.append(
                DamageNumber(p.x, p.y - 58, f"★ HỢP NHẤT: {title_str.upper()} ★", (255, 225, 65), scale=1.3))
        elif awakened_now:
            self.damage_numbers.append(
                DamageNumber(p.x, p.y - 54, f"★ THỨC TỈNH: {title_str.upper()} ★", (255, 225, 80), scale=1.2))
        else:
            self.damage_numbers.append(
                DamageNumber(p.x, p.y - 44, f"▲ {title_str}{lv_suffix}", burst_col))

        p.squash_timer = 10
        self.screen_flash_alpha = 155 if fused_now else (130 if awakened_now else 80)
        self.screen_shake = 18 if fused_now else (14 if awakened_now else 7)

    # -----------------------------------------------------------------------
    def _update(self):
        self.tick += 1
        keys = pygame.key.get_pressed()
        p    = self.player

        p.update(keys, 1 / FPS)

        # Kamera
        target_cx = p.x - SCREEN_W // 2
        target_cy = p.y - SCREEN_H // 2
        self.cam_x = lerp(self.cam_x, target_cx, 0.12)
        self.cam_y = lerp(self.cam_y, target_cy, 0.12)

        # Cập nhật hạt bụi môi trường & sóng xung kích
        for ap in self.ambient_particles:
            ap.update(self.cam_x, self.cam_y)
        self.shockwaves = [sw for sw in self.shockwaves if sw.update()]
        if self.screen_flash_alpha > 0:
            self.screen_flash_alpha = max(0, self.screen_flash_alpha - 6)
        if self.screen_shake > 0:
            self.screen_shake -= 1

        # Normal spawn
        self.spawn_mgr.update(p, self.enemies, self.tick)

        if (self.campaign_mode and not self.level_completed
                and self.spawn_mgr.wave + 1 >= campaign_target_wave(self.campaign_level)):
            self._complete_campaign_level()
            return

        # ── Boss spawn ──────────────────────────────────────────────────
        if self.tick > 0 and self.tick % (BOSS_INTERVAL * FPS) == 0:
            side = random.randint(0, 3)
            if side == 0:   bx, by = p.x + random.uniform(-400,400), p.y - 500
            elif side == 1: bx, by = p.x + 600, p.y + random.uniform(-400,400)
            elif side == 2: bx, by = p.x + random.uniform(-400,400), p.y + 500
            else:           bx, by = p.x - 600, p.y + random.uniform(-400,400)
            bx = clamp(bx, 100, WORLD_W-100)
            by = clamp(by, 100, WORLD_H-100)
            self.bosses.append(Boss(bx, by, self.spawn_mgr.wave))
            self.boss_alert_timer = 240

        if self.boss_alert_timer > 0:
            self.boss_alert_timer -= 1

        # Vũ khí & Kỹ năng chủ động
        all_enemies = self.enemies + self.bosses
        p.whip.update(p, all_enemies, self.particles, self.damage_numbers, self.sfx)
        p.void_singularity.update(p, all_enemies, self.particles, self.damage_numbers, self.sfx)
        p.phantom_arrow.update(p, all_enemies, self.particles, self.damage_numbers, self.sfx)
        p.judgement_hammer.update(p, all_enemies, self.particles, self.damage_numbers, self.sfx)
        p.orb.update(p,  all_enemies, self.particles, self.damage_numbers, self.sfx)
        p.aura.update(p, all_enemies, self.particles, self.damage_numbers, self.sfx)
        p.boomerang.update(p, all_enemies, self.particles, self.damage_numbers, self.sfx)
        p.lightning_staff.update(p, all_enemies, self.particles, self.damage_numbers, self.sfx)
        p.ice_wand.update(p, all_enemies, self.particles, self.damage_numbers, self.sfx)
        p.fire_trail.update(p, all_enemies, self.particles, self.damage_numbers, self.sfx)
        p.familiar.update(p, all_enemies, self.player_projs, self.particles, self.damage_numbers)

        # Rung màn hình nhẹ khi kỹ năng Thức Tỉnh / Hợp Nhất kích hoạt hoặc khi gây Chí Mạng / đa mục tiêu
        if getattr(p, "micro_shake", 0) > 0:
            self.screen_shake = max(self.screen_shake, p.micro_shake)
            p.micro_shake = 0
        if (p.whip.awakened and p.whip.flash == 12) or (
            p.lightning_staff.awakened and any(b.flash_timer == b.STRIKE_FLASH_FRAMES for b in p.lightning_staff.active)):
            self.screen_shake = max(self.screen_shake, 4)

        # ── Drone ───────────────────────────────────────────────────────
        for drone in self.drones:
            drone.update(p, all_enemies, self.player_projs, self.damage_numbers, self.particles)

        # ── Tháp pháo ───────────────────────────────────────────────────
        for turret in self.turrets:
            turret.update(all_enemies, self.player_projs, self.damage_numbers, self.particles)
        self.turrets = [t for t in self.turrets if t.alive]

        # ── Đạn của người chơi (drone/tháp pháo) ────────────────────────
        for proj in self.player_projs:
            proj.update()
            if proj.alive:
                for e in all_enemies:
                    if e.alive and id(e) not in proj.hit_set:
                        if dist((proj.x, proj.y), (e.x, e.y)) < proj.size + e.radius:
                            e.take_damage(proj.damage)
                            proj.hit_set.add(id(e))
                            proj.pierce -= 1
                            self.damage_numbers.append(
                                DamageNumber(e.x, e.y, proj.damage, (255, 255, 255)))
                            for _ in range(4):
                                self.particles.append(
                                    Particle(proj.x, proj.y, proj.color, speed=2.8, angle=proj.angle, spread=0.7))
                            if proj.pierce <= 0:
                                proj.alive = False
                                break

        # Cập nhật kẻ địch thường
        new_ep = []
        summoned_enemies = []
        for e in self.enemies:
            e.update(p, new_ep, summoned_enemies)
        self.enemy_projs.extend(new_ep)
        self.enemies.extend(summoned_enemies)

        # Cập nhật Boss
        boss_ep = []
        for b in self.bosses:
            b.update(p, boss_ep)
        self.enemy_projs.extend(boss_ep)

        # Đạn kẻ địch
        for proj in self.enemy_projs:
            proj.update()
            if proj.alive:
                if dist((proj.x, proj.y), (p.x, p.y)) < p.radius + proj.size:
                    p.take_damage(proj.damage)
                    self.sfx.play_damage()
                    for _ in range(4):
                        self.particles.append(Particle(proj.x, proj.y, C_RED, speed=3))
                    proj.alive = False

        # Va chạm cận chiến (kẻ địch + boss)
        for e in self.enemies:
            if e.alive and dist((e.x, e.y), (p.x, p.y)) < e.radius + p.radius:
                p.take_damage(e.damage); self.sfx.play_damage()
        for b in self.bosses:
            if b.alive and dist((b.x, b.y), (p.x, p.y)) < b.radius + p.radius:
                p.take_damage(b.damage); self.sfx.play_damage()

        # Thu thập đá XP
        collected = 0
        for gem in self.xp_gems:
            collected += gem.update(p)
        if collected:
            self.sfx.play_xp()
            if p.gain_xp(collected):
                self.sfx.play_levelup(); self._trigger_levelup()

        # ── Thu thập Đồng Vàng ──────────────────────────────────────────
        coin_picked = False
        for coin in self.gold_coins:
            v = coin.update(p)
            if v:
                self.session_gold += v
                coin_picked = True
        if coin_picked:
            self.sfx.play_coin()

        # ── Thu thập Vật Phẩm Chiến Trường (Bình Máu & Nam Châm Từ Trường) ──
        for item in self.items:
            if isinstance(item, HealthPotion):
                item.update(p, self.particles, self.damage_numbers, self.sfx)
            elif isinstance(item, ExpMagnet):
                item.update(p, self.xp_gems, self.gold_coins, self.shockwaves, self.particles, self.damage_numbers, self.sfx)

        # ── Tương tác Rương ─────────────────────────────────────────────
        for chest in self.chests:
            drop = chest.update(p)
            if drop == ChestDrop.GOLD:
                amt = int(random.randint(20, 50) * p.gold_mult)
                self.session_gold += amt
                self.damage_numbers.append(
                    DamageNumber(p.x, p.y - 30, f"+{amt}G", C_YELLOW))
                self.ach_mgr.notify_chest_open()
            elif drop == ChestDrop.DRONE:
                self.drones.append(Drone(index=len(self.drones)))
                self.damage_numbers.append(
                    DamageNumber(p.x, p.y - 30, "+Drone", C_CYAN))
                self.ach_mgr.notify_chest_open()
            elif drop == ChestDrop.TURRET:
                self.turrets.append(Turret(p.x, p.y))
                self.damage_numbers.append(
                    DamageNumber(p.x, p.y - 30, "+Tháp", (255,180,40)))
                self.ach_mgr.notify_chest_open()

        # Xử lý kẻ địch bị tiêu diệt
        dead = [e for e in self.enemies if not e.alive]
        for e in dead:
            self.kills += 1
            self.sfx.play_death()
            self.xp_gems.append(XPGem(e.x, e.y, e.xp))
            # Nội tại Hút Máu khi hạ gục (Huyết Kiếm Sĩ) + chữ +HP xanh lá
            if p.lifesteal_on_kill > 0 and p.hp < p.max_hp:
                old_hp = p.hp
                p.hp = min(p.max_hp, p.hp + p.lifesteal_on_kill)
                if p.hp > old_hp:
                    self.damage_numbers.append(
                        DamageNumber(p.x, p.y - 22, p.hp - old_hp, (80, 255, 130), is_heal=True))
            # 45% rơi Đồng Vàng
            if random.random() < 0.45:
                val = random.randint(1, 5)
                self.gold_coins.append(GoldCoin(e.x, e.y, val))
            # Rơi Vật Phẩm Chiến Trường:
            # - Bình Máu (HealthPotion): 100% từ Quái Tinh Anh (TANK), ~4% từ quái thường
            # - Nam Châm Từ Trường (ExpMagnet): ~1.5% từ quái thường
            if e.etype == EnemyType.TANK or random.random() < 0.04:
                self.items.append(HealthPotion(e.x + random.uniform(-10, 10), e.y + random.uniform(-10, 10)))
            elif random.random() < 0.015:
                self.items.append(ExpMagnet(e.x + random.uniform(-10, 10), e.y + random.uniform(-10, 10)))
            for _ in range(8 if self.vfx_high else 4):
                self.particles.append(Particle(e.x, e.y, e.color, speed=3, life=40))

        # ── Xử lý Boss bị tiêu diệt ─────────────────────────────────────
        dead_bosses = [b for b in self.bosses if not b.alive]
        for b in dead_bosses:
            self.kills += 1
            self.sfx.play_death()
            self.ach_mgr.notify_boss_kill()
            self.xp_gems.append(XPGem(b.x, b.y, b.XP_REWARD))
            for _ in range(10):
                val = random.randint(10, 22)
                self.gold_coins.append(GoldCoin(
                    b.x + random.uniform(-45, 45),
                    b.y + random.uniform(-45, 45), val))
            # Boss chắc chắn rơi cả Bình Máu (100%) và Nam Châm Từ Trường (100%)!
            self.items.append(HealthPotion(b.x - 20, b.y))
            self.items.append(ExpMagnet(b.x + 20, b.y))
            self.shockwaves.append(ShockwaveRing(b.x, b.y, (255, 80, 120), max_radius=240, duration=35, width=6))
            self.screen_shake = max(self.screen_shake, 14)
            for _ in range(30):
                self.particles.append(Particle(b.x, b.y, Boss.COLOR, speed=5, life=60))
            for _ in range(15):
                self.particles.append(Particle(b.x, b.y, C_YELLOW, speed=4, life=50))

        # Dọn dẹp các đối tượng hết hạn / ngoài màn hình
        self.enemies        = [e for e in self.enemies if e.alive]
        self.bosses         = [b for b in self.bosses  if b.alive]
        self.enemy_projs    = [p2 for p2 in self.enemy_projs   if p2.alive]
        self.player_projs   = [p2 for p2 in self.player_projs  if p2.alive]
        self.particles      = [pt for pt in self.particles      if pt.update()]
        max_pts = 350 if self.vfx_high else 160
        if len(self.particles) > max_pts:
            self.particles = self.particles[-max_pts:]
        self.damage_numbers = [d  for d  in self.damage_numbers if d.update()]
        self.xp_gems        = [g  for g  in self.xp_gems        if g.alive]
        self.gold_coins     = [c  for c  in self.gold_coins     if c.alive]
        self.items          = [it for it in self.items          if it.alive]

        # Thành tựu
        elapsed_secs = self.tick // FPS
        self.ach_mgr.notify_kill(self.kills)
        self.ach_mgr.notify_time(elapsed_secs)
        self.ach_mgr.notify_gold(self.session_gold)

        # Nhiệm vụ trong trận
        if not self.game_over:
            kills_delta      = self.kills - self._prev_kills
            gold_delta       = self.session_gold - self._prev_gold
            self._prev_kills = self.kills
            self._prev_gold  = self.session_gold

            self.quest_mgr.update(self.tick, kills_delta, gold_delta, elapsed_secs)

            reward = self.quest_mgr.collect_rewards()
            if reward > 0:
                self.session_gold += reward
                self._prev_gold   += reward
                self.damage_numbers.append(
                    DamageNumber(p.x, p.y - 50, f"+{reward}G", C_YELLOW))

        # Game over
        if p.hp <= 0:
            p.hp = 0
            self.game_over = True
            self._flush_session_save()

    def _trigger_levelup(self):
        self.paused = True
        self.upgrade_screen = UpgradeScreen(list(UpgradeType), self.player)

    # -----------------------------------------------------------------------
    def _draw(self):
        surf = self.screen
        surf.fill(C_BG)
        eff_shake = self.screen_shake if self.shake_enabled else 0
        shake_x = random.randint(-eff_shake, eff_shake) if eff_shake > 0 else 0
        shake_y = random.randint(-eff_shake, eff_shake) if eff_shake > 0 else 0
        cx, cy = int(self.cam_x) + shake_x, int(self.cam_y) + shake_y

        # Nền đá cổ ngữ ma thuật tối (Cached Dark Arcane Cobblestone / Rune Grid)
        tile_chunk = get_arcane_tile_chunk(self.biome_id)
        cw, ch = tile_chunk.get_size()
        start_tx = (cx // cw) * cw
        start_ty = (cy // ch) * ch
        for gx in range(start_tx, cx + SCREEN_W + cw, cw):
            for gy in range(start_ty, cy + SCREEN_H + ch, ch):
                surf.blit(tile_chunk, (gx - cx, gy - cy))

        # Vật thể trang trí môi trường Dark Fantasy (mộ cổ, cây khô, trụ lửa, tinh thể)
        if "draw_biome_props" in globals():
            draw_biome_props(surf, cx, cy, self.biome_id, self.tick)

        # Hạt bụi ma thuật / tàn lửa môi trường
        for ap in self.ambient_particles:
            ap.draw(surf, cx, cy)

        # Tháp pháo (dưới mặt đất)
        for t in self.turrets:
            t.draw(surf, cx, cy)

        # Rương
        for chest in self.chests:
            chest.draw(surf, cx, cy)

        # Đá XP + Đồng Vàng xoay 3D + Vật Phẩm Chiến Trường (Bình Máu & Nam Châm)
        for gem in self.xp_gems:
            gem.draw(surf, cx, cy, self.tick)
        for coin in self.gold_coins:
            coin.draw(surf, cx, cy)
        for item in self.items:
            item.draw(surf, cx, cy, self.tick)

        # Vũ khí / Kỹ năng chủ động & Hợp Nhất
        self.player.fire_trail.draw(surf, cx, cy, self.tick)
        self.player.aura.draw(surf, cx, cy, self.player, self.tick)
        self.player.void_singularity.draw(surf, cx, cy, self.tick)
        self.player.phantom_arrow.draw(surf, cx, cy, self.tick)
        self.player.judgement_hammer.draw(surf, cx, cy, self.tick)
        self.player.orb.draw(surf,  cx, cy, self.player, self.tick)
        self.player.whip.draw(surf, cx, cy, self.player)
        self.player.boomerang.draw(surf, cx, cy, self.player)
        self.player.lightning_staff.draw(surf, cx, cy, self.tick)
        self.player.ice_wand.draw(surf, cx, cy, self.tick)
        self.player.familiar.draw(surf, cx, cy, self.player, self.tick)

        # Sóng xung kích (Level-up Burst / Boss death)
        for sw in self.shockwaves:
            sw.draw(surf, cx, cy)

        # Drone
        for drone in self.drones:
            drone.draw(surf, cx, cy, self.player)

        # Kẻ địch
        for e in self.enemies:
            e.draw(surf, cx, cy)

        # Boss
        for b in self.bosses:
            b.draw(surf, cx, cy)

        # Đạn
        for proj in self.enemy_projs:
            proj.draw(surf, cx, cy)
        for proj in self.player_projs:
            proj.draw(surf, cx, cy)

        # Hạt hiệu ứng + Số sát thương
        for pt in self.particles:
            pt.draw(surf, cx, cy)
        for dn in self.damage_numbers:
            dn.draw(surf, cx, cy, self.font_dmg)

        # Nhân vật người chơi
        self.player.draw(surf, cx, cy, self.tick)

        # Hiệu ứng tối góc màn hình (Dark Vignette) & hào quang ánh sáng quanh nhân vật
        psx = int(self.player.x - cx)
        psy = int(self.player.y - cy)
        glow_r = 75
        glow_s = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow_s, (*self.player.color, 22), (glow_r, glow_r), glow_r)
        surf.blit(glow_s, (psx - glow_r, psy - glow_r))
        surf.blit(get_vignette_surface(), (0, 0))

        # Viền đỏ cảnh báo khi Đợt Tấn Công Dồn Dập (Swarm Event) diễn ra
        if getattr(self.spawn_mgr, "swarm_alert_timer", 0) > 0:
            self._draw_swarm_alert(surf)

        # Chớp sáng màn hình khi lên cấp / thức tỉnh kỹ năng
        if self.screen_flash_alpha > 0:
            fl_s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            fl_s.fill((220, 235, 255, min(255, self.screen_flash_alpha)))
            surf.blit(fl_s, (0, 0))

        # UI
        self._draw_ui(surf)

        # Cảnh báo Boss
        if self.boss_alert_timer > 0:
            self._draw_boss_alert(surf)

        if self.upgrade_screen:
            self.upgrade_screen.draw(surf)
        if self.level_completed:
            self._draw_level_completed(surf)
        elif self.paused and not self.upgrade_screen:
            self._draw_pause(surf)
        if self.game_over:
            self._draw_game_over(surf)
        if self.controls_open:
            self._draw_controls(surf)

        pygame.display.flip()

    # -----------------------------------------------------------------------
    def _draw_swarm_alert(self, surf):
        t = getattr(self.spawn_mgr, "swarm_alert_timer", 0)
        pulse = int(abs(math.sin(t * 0.18)) * 160) + 45
        pygame.draw.rect(surf, (255, 25, 40), (0, 0, SCREEN_W, SCREEN_H), 6)
        if (t // 6) % 2 == 0:
            s_txt = self.font_med.render(T("swarm_alert"), True, (255, 70, 80))
            s_txt.set_alpha(min(255, pulse + 40))
            surf.blit(s_txt, s_txt.get_rect( center=(SCREEN_W // 2, 118)))

    # -----------------------------------------------------------------------
    def _draw_ui(self, surf):
        p = self.player

        # HP çubuğu
        bar_w = 220
        bar_h = 18
        bx, by = 16, 16
        pygame.draw.rect(surf, C_HP_BG, (bx, by, bar_w, bar_h), border_radius=4)
        fill = int(bar_w * p.hp / p.max_hp)
        pygame.draw.rect(surf, C_HP, (bx, by, fill, bar_h), border_radius=4)
        pygame.draw.rect(surf, (200,200,200), (bx, by, bar_w, bar_h), 1, border_radius=4)
        hp_s = self.font_bar.render(f"{T('hp')}  {p.hp}/{p.max_hp}", True, C_WHITE)
        surf.blit(hp_s, hp_s.get_rect(midleft=(bx + 6, by + bar_h // 2)))

        # XP çubuğu
        bar_h2 = 16
        bx2, by2 = 16, 42
        pygame.draw.rect(surf, C_XP_BG, (bx2, by2, bar_w, bar_h2), border_radius=4)
        fill2 = int(bar_w * p.xp / p.xp_needed)
        pygame.draw.rect(surf, C_XP, (bx2, by2, fill2, bar_h2), border_radius=4)
        pygame.draw.rect(surf, (200,200,200), (bx2, by2, bar_w, bar_h2), 1, border_radius=4)
        xp_s = self.font_bar.render(
            f"{T('lv')} {p.level}  {T('xp')} {p.xp}/{p.xp_needed}", True, C_WHITE)
        surf.blit(xp_s, xp_s.get_rect(midleft=(bx2 + 6, by2 + bar_h2 // 2)))

        # Süre, dalga, kill (üst orta)
        elapsed = self.tick // FPS
        mins, secs = divmod(elapsed, 60)
        wave = self.spawn_mgr.wave
        info = self.font_med.render(
            f"{mins:02d}:{secs:02d}   {T('wave')} {wave+1}   {T('kill')} {self.kills}",
            True, C_YELLOW)
        surf.blit(info, (SCREEN_W//2 - info.get_width()//2, 12))

        # Tên bản đồ hiện tại (Biome) dưới đồng hồ
        b_name = T(f"biome_{self.biome_id}")
        b_lbl = self.font_bar.render(T("biome_label", b=b_name), True, (175, 165, 220))
        surf.blit(b_lbl, (SCREEN_W // 2 - b_lbl.get_width() // 2, 38))

        # Thanh máu Boss khổng lồ ở phía trên màn hình nếu có Boss xuất hiện
        if self.bosses:
            b = self.bosses[0]
            bw, bh = 440, 18
            bbx = SCREEN_W // 2 - bw // 2
            bby = 62
            pygame.draw.rect(surf, (35, 10, 25), (bbx - 2, bby - 2, bw + 4, bh + 4), border_radius=6)
            pygame.draw.rect(surf, (90, 15, 35), (bbx, bby, bw, bh), border_radius=5)
            bfill = int(bw * max(0, b.hp) / max(1, b.max_hp))
            b_col = (255, 50, 90) if getattr(b, "boss_kind", 0) == 1 else (195, 70, 255)
            pygame.draw.rect(surf, b_col, (bbx, bby, bfill, bh), border_radius=5)
            pygame.draw.rect(surf, (255, 215, 90), (bbx - 2, bby - 2, bw + 4, bh + 4), 2, border_radius=6)
            b_title = T("boss_demon") if getattr(b, "boss_kind", 0) == 1 else T("boss_lich")
            bt_s = self.font_bar.render(f"☠ {b_title}: {b.hp}/{b.max_hp}", True, C_WHITE)
            surf.blit(bt_s, bt_s.get_rect(center=(SCREEN_W // 2, bby + bh // 2)))

        self._draw_weapons_panel(surf)

        # Sağ üst: ses + dil
        mute_label = T("muted") if self.sfx.muted else T("unmuted")
        mute_col   = (200,80,80) if self.sfx.muted else (80,200,80)
        ml = self.font_sm.render(f"{mute_label}  |  {T('lang_label')}", True, mute_col)
        surf.blit(ml, (SCREEN_W - ml.get_width() - 12, 16))

        # Vàng hiện tại trên HUD (kèm biểu tượng đồng xu vàng)
        total_g = self.save.total_gold + self.session_gold
        gold_s = self.font_sm.render(
            f"{T('gold')}: {total_g} (+{self.session_gold})", True, C_YELLOW)
        gold_r = pygame.Rect(0, 0, gold_s.get_width() + 34, 26)
        gold_r.topright = (SCREEN_W - 12, 42)
        gold_bg = pygame.Surface(gold_r.size, pygame.SRCALPHA)
        gold_bg.fill((12, 10, 22, 195))
        surf.blit(gold_bg, gold_r.topleft)
        pygame.draw.rect(surf, (220, 180, 60), gold_r, 1, border_radius=5)
        pygame.draw.circle(surf, (255, 210, 50), (gold_r.x + 13, gold_r.centery), 6)
        pygame.draw.circle(surf, (255, 245, 160), (gold_r.x + 13, gold_r.centery), 6, 1)
        surf.blit(gold_s, gold_s.get_rect(midleft=(gold_r.x + 24, gold_r.centery)))

        if self.campaign_mode:
            c_s = self.font_sm.render(
                f"{T('campaign_level', n=self.campaign_level)}  |  "
                f"{T('target_wave', n=campaign_target_wave(self.campaign_level))}",
                True, (180, 175, 230))
            surf.blit(c_s, (SCREEN_W - c_s.get_width() - 12, 74))

        # Drone / Tháp pháo
        if self.drones or self.turrets:
            dt_s = self.font_sm.render(
                T("drone_turret", d=len(self.drones), t=len(self.turrets)),
                True, (180,220,255))
            surf.blit(dt_s, (16, SCREEN_H - 44))

        # Kontroller butonu (alt orta)
        mx, my = pygame.mouse.get_pos()
        self.btn_controls.label = T("controls_btn")
        self.btn_controls.update(mx, my)
        self.btn_controls.draw(surf)

        # Başarım toast bildirimi
        self.ach_mgr.draw(surf, SCREEN_W, SCREEN_H)

        # Görev paneli ve bildirimleri
        self.quest_mgr.draw_panel(surf, SCREEN_H)
        self.quest_mgr.draw_notifications(surf, SCREEN_W, 80)

    # -----------------------------------------------------------------------
    def _draw_weapons_panel(self, surf):
        p = self.player

        if not hasattr(self, "_wpn_font_title"):
            self._wpn_font_title = get_sys_font(14, bold=True)
            self._wpn_font_row   = get_sys_font(13)

        def _fmt_lv(w):
            if getattr(w, "fused", False):
                return "★HỢP NHẤT"
            return "★MAX" if getattr(w, "awakened", False) else f"Lv{w.level}/5"

        all_skills = [
            (T("wpn_whip"),       p.whip),
            (T("wpn_void"),       p.void_singularity),
            (T("wpn_arrow"),      p.phantom_arrow),
            (T("wpn_hammer"),     p.judgement_hammer),
            (T("wpn_orb"),        p.orb),
            (T("wpn_aura"),       p.aura),
            (T("wpn_boomerang"),  p.boomerang),
            (T("wpn_lightning"),  p.lightning_staff),
            (T("wpn_ice"),        p.ice_wand),
            (T("wpn_fire_trail"), p.fire_trail),
            (T("wpn_familiar"),   p.familiar),
        ]
        # Chỉ hiển thị các kỹ năng đã mở khóa (level >= 1 hoặc đã hợp nhất)
        rows = [(lbl, _fmt_lv(w)) for lbl, w in all_skills if w.level >= 1 or getattr(w, "fused", False)]
        rows.append((T("wpn_armor"), f"{p.armor}"))
        rows.append((T("wpn_regen"), f"{p.recovery}"))

        PANEL_W  = 210
        ROW_H    = 19
        PAD      = 6
        panel_h  = 26 if self.weapons_collapsed else 22 + len(rows) * ROW_H + PAD

        px = SCREEN_W - PANEL_W - 16
        py = 104 if self.campaign_mode else 80
        self._weapons_toggle_rect = pygame.Rect(px + PANEL_W - 26, py + 1, 24, 20)

        panel_s = pygame.Surface((PANEL_W, panel_h), pygame.SRCALPHA)
        panel_s.fill((12, 10, 22, 180))
        surf.blit(panel_s, (px, py))
        pygame.draw.rect(surf, (70, 60, 120), (px, py, PANEL_W, panel_h), 1, border_radius=4)

        title_s = self._wpn_font_title.render(T("weapons_title"), True, (180, 160, 255))
        surf.blit(title_s, (px + PAD, py + 4))
        draw_collapse_arrow(surf, self._weapons_toggle_rect, self.weapons_collapsed,
                            self._weapons_toggle_rect.collidepoint(pygame.mouse.get_pos()))
        if self.weapons_collapsed:
            return

        for i, (label, value_str) in enumerate(rows):
            ry = py + 22 + i * ROW_H
            lbl_s = self._wpn_font_row.render(str(label), True, (200, 195, 240))
            surf.blit(lbl_s, (px + PAD, ry))
            v_col = (255, 85, 95) if "HỢP NHẤT" in value_str else ((255, 190, 60) if "★" in value_str else C_YELLOW)
            val_s = self._wpn_font_row.render(value_str, True, v_col)
            surf.blit(val_s, (px + PANEL_W - val_s.get_width() - PAD, ry))

    # -----------------------------------------------------------------------
    def _draw_boss_alert(self, surf):
        """Ekranın ortasında kırmızı yanıp sönen BOSS FIGHT! bildirimi."""
        t      = self.boss_alert_timer
        alpha  = int(min(255, t * 3))
        strip = pygame.Surface((SCREEN_W, 80), pygame.SRCALPHA)
        strip.fill((80, 0, 20, min(160, alpha)))
        surf.blit(strip, (0, SCREEN_H // 2 - 40))
        if (t // 8) % 2 == 0:
            font = get_sys_font(52, bold=True)
            txt  = font.render(T("boss_fight"), True, (255, 60, 80))
            txt.set_alpha(alpha)
            surf.blit(txt, txt.get_rect(center=(SCREEN_W//2, SCREEN_H//2)))

    # -----------------------------------------------------------------------
    def _draw_pause(self, surf):
        """Menu Tạm Dừng Trò Chơi (In-Game Pause Menu) với đầy đủ thông tin Hệ Phái, Kỹ năng & 4 nút tương tác."""
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((6, 4, 16, 195))
        surf.blit(overlay, (0, 0))

        panel = pygame.Rect(0, 0, 790, 440)
        panel.center = (SCREEN_W // 2, SCREEN_H // 2)
        p_surf = pygame.Surface(panel.size, pygame.SRCALPHA)
        p_surf.fill((18, 14, 34, 242))
        surf.blit(p_surf, panel.topleft)
        pygame.draw.rect(surf, (145, 115, 240), panel, 2, border_radius=14)
        pygame.draw.rect(surf, (255, 210, 70), panel.inflate(-8, -8), 1, border_radius=11)

        title = self.font_big.render(T("pause_title"), True, C_YELLOW)
        surf.blit(title, title.get_rect(centerx=panel.centerx, y=panel.y + 18))

        # Cột Trái: Thông tin Hệ Phái, Cấp độ, Vàng & Kỹ năng/Hợp Nhất hiện tại
        left_r = pygame.Rect(panel.x + 24, panel.y + 74, 355, 340)
        pygame.draw.rect(surf, (26, 22, 48), left_r, border_radius=10)
        pygame.draw.rect(surf, (85, 70, 150), left_r, 1, border_radius=10)

        p = self.player
        c_name = STRINGS[LANG]["char_names"].get(p.character_id, p.character_id)
        draw_character_procedural_sprite(
            surf, p.character_id, left_r.x + 48, left_r.y + 52, 20,
            p.color, p.dark_color, 0.0, pygame.time.get_ticks() // 16, is_preview=True,
            skin_id=p.skin_id,
        )
        cn_s = self.font_med.render(c_name, True, p.color)
        surf.blit(cn_s, (left_r.x + 92, left_r.y + 20))
        stat_s = self.font_sm.render(
            f"{T('level')}: {p.level}   |   {T('gold')}: {self.save.total_gold + self.session_gold}",
            True, C_YELLOW)
        surf.blit(stat_s, (left_r.x + 92, left_r.y + 50))
        hp_info = self.font_sm.render(
            f"HP: {p.hp}/{p.max_hp}  |  {T('wave')}: {self.spawn_mgr.wave + 1}  |  {T('kill')}: {self.kills}",
            True, (205, 200, 240))
        surf.blit(hp_info, (left_r.x + 92, left_r.y + 74))

        pygame.draw.line(surf, (75, 65, 130), (left_r.x + 14, left_r.y + 104), (left_r.right - 14, left_r.y + 104), 1)
        sk_hdr = self.font_sm.render(T("weapons_title") + ":", True, (180, 220, 255))
        surf.blit(sk_hdr, (left_r.x + 16, left_r.y + 112))

        skill_items = [
            (T("wpn_whip"),       p.whip,             (255, 70, 90)),
            (T("wpn_void"),       p.void_singularity, (185, 90, 255)),
            (T("wpn_arrow"),      p.phantom_arrow,    (50, 255, 175)),
            (T("wpn_hammer"),     p.judgement_hammer, (255, 215, 70)),
            (T("wpn_orb"),        p.orb,              C_CYAN),
            (T("wpn_aura"),       p.aura,             C_PURPLE),
            (T("wpn_boomerang"),  p.boomerang,        C_CYAN),
            (T("wpn_lightning"),  p.lightning_staff,  C_LIGHTNING),
            (T("wpn_ice"),        p.ice_wand,         C_ICE),
            (T("wpn_fire_trail"), p.fire_trail,       (255, 110, 40)),
            (T("wpn_familiar"),   p.familiar,         (140, 235, 255)),
        ]
        active_sk = [(n, w, c) for n, w, c in skill_items if w.level >= 1 or getattr(w, "fused", False)]
        sy = left_r.y + 138
        for s_name, w, s_col in active_sk[:7]:
            pygame.draw.circle(surf, s_col, (left_r.x + 26, sy + 9), 6)
            pygame.draw.circle(surf, C_WHITE, (left_r.x + 26, sy + 9), 6, 1)
            tag = "★ HỢP NHẤT" if getattr(w, "fused", False) else ("★ THỨC TỈNH" if w.awakened else f"Lv.{w.level}/5")
            row_s = self.font_sm.render(f"{s_name} — {tag}", True, (255, 215, 75) if getattr(w, "fused", False) else C_WHITE)
            surf.blit(row_s, (left_r.x + 40, sy))
            sy += 26

        # Cột Phải: 4 Nút tương tác (Hỗ trợ Chuột & Phím Mũi tên Lên/Xuống + Enter)
        if self.pause_settings_open:
            rects = self._pause_setting_rects()
            labels = [
                T("muted") if self.sfx.muted else T("unmuted"),
                T("shake_on") if self.shake_enabled else T("shake_off"),
                T("vfx_high") if self.vfx_high else T("vfx_low"),
                T("menu_back"),
            ]
        else:
            rects = self._pause_btn_rects()
            labels = [
                T("pause_resume"),
                T("pause_restart"),
                T("pause_settings"),
                T("pause_main_menu"),
            ]

        for i, r in enumerate(rects):
            sel = (i == self.pause_sel_idx)
            bg_c = (65, 50, 125) if sel else (32, 26, 62)
            bd_c = (255, 215, 75) if sel else (95, 80, 165)
            pygame.draw.rect(surf, bg_c, r, border_radius=9)
            pygame.draw.rect(surf, bd_c, r, 3 if sel else 1, border_radius=9)
            prefix = "▶ " if sel else ""
            lbl_s = self.font_med.render(prefix + labels[i], True, C_YELLOW if sel else C_WHITE)
            surf.blit(lbl_s, lbl_s.get_rect(center=r.center))

        hint_s = self.font_bar.render("Mũi tên Lên/Xuống + Enter hoặc Nhấp chuột  |  [ESC] Tiếp tục", True, (170, 165, 210))
        surf.blit(hint_s, hint_s.get_rect(centerx=panel.centerx, bottom=panel.bottom - 10))

    # -----------------------------------------------------------------------
    def _draw_controls(self, surf):
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 175))
        surf.blit(overlay, (0, 0))

        panel = self.controls_panel
        panel_s = pygame.Surface((panel.w, panel.h), pygame.SRCALPHA)
        panel_s.fill((*C_UI_BG[:3], 235))
        surf.blit(panel_s, panel.topleft)
        pygame.draw.rect(surf, (120, 100, 220), panel, 2, border_radius=8)

        title = self.font_big.render(T("controls_title"), True, C_YELLOW)
        surf.blit(title, title.get_rect(centerx=panel.centerx, y=panel.y + 20))

        rows = ["ctl_move", "ctl_pause", "ctl_lang", "ctl_sound",
                "ctl_upgrade", "ctl_restart", "ctl_menu"]
        ry = panel.y + 80
        for key in rows:
            keys_txt, desc = T(key)
            k_s = self.font_sm.render(keys_txt, True, (180, 160, 255))
            d_s = self.font_sm.render(desc, True, (200, 195, 240))
            surf.blit(k_s, (panel.x + 32, ry))
            surf.blit(d_s, (panel.x + 230, ry))
            ry += 30

        mx, my = pygame.mouse.get_pos()
        self.btn_controls_close.label = T("close")
        self.btn_controls_close.update(mx, my)
        self.btn_controls_close.draw(surf)

    # -----------------------------------------------------------------------
    def _draw_level_completed(self, surf):
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 175))
        surf.blit(overlay, (0, 0))

        panel = pygame.Rect(0, 0, 560, 260)
        panel.center = (SCREEN_W // 2, SCREEN_H // 2)
        panel_s = pygame.Surface((panel.w, panel.h), pygame.SRCALPHA)
        panel_s.fill((*C_UI_BG[:3], 230))
        surf.blit(panel_s, panel.topleft)
        pygame.draw.rect(surf, (120, 100, 220), panel, 2, border_radius=8)

        title = self.font_big.render(T("level_completed"), True, C_YELLOW)
        surf.blit(title, title.get_rect(centerx=panel.centerx, y=panel.y + 38))

        sub = self.font_med.render(
            f"{T('campaign_level', n=self.campaign_level)}  -  "
            f"{T('target_wave', n=campaign_target_wave(self.campaign_level))}",
            True, (200, 195, 240))
        surf.blit(sub, sub.get_rect(centerx=panel.centerx, y=panel.y + 92))

        mx, my = pygame.mouse.get_pos()
        self.btn_next_level.update(mx, my)
        self.btn_completed_menu.update(mx, my)
        self.btn_next_level.label = T("next_level")
        self.btn_completed_menu.label = T("main_menu")
        self.btn_next_level.draw(surf)
        self.btn_completed_menu.draw(surf)

    # -----------------------------------------------------------------------
    def _draw_game_over(self, surf):
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        surf.blit(overlay, (0, 0))
        elapsed = self.tick // FPS
        mins, secs = divmod(elapsed, 60)
        lines = [
            (T("game_over"),                         self.font_big, C_RED),
            (f"{T('time')}: {mins:02d}:{secs:02d}",  self.font_med, C_WHITE),
            (f"{T('level')}: {self.player.level}",   self.font_med, C_YELLOW),
            (f"{T('kill')}: {self.kills}",            self.font_med, C_ORANGE),
            (f"{T('gold')}: {self.save.total_gold}",self.font_med, C_YELLOW),
            ("",                                      self.font_sm,  C_WHITE),
            (T("restart"),                            self.font_med, (160,160,200)),
        ]
        total_h = sum(f.size("X")[1] + 10 for _, f, _ in lines)
        y = SCREEN_H // 2 - total_h // 2
        for txt, font, color in lines:
            s = font.render(txt, True, color)
            surf.blit(s, (SCREEN_W//2 - s.get_width()//2, y))
            y += font.size("X")[1] + 10


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    Game().run()
