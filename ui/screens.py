"""Menu screens: Main Menu, Campaign, Character Selection, Skin Shop, Lobby, and Settings."""
import math
import os
import random
from typing import Any, Dict, List, Optional, Tuple
import pygame
import audio_settings

from core.config import (
    ANIME_SKIN_BY_ID,
    ANIME_SKINS,
    C_BG,
    C_CYAN,
    C_GREEN,
    C_ORANGE,
    C_PLAYER,
    C_PLAYER_DARK,
    C_PURPLE,
    C_RED,
    C_WHITE,
    C_YELLOW,
    CHARACTER_DEFS,
    CLASS_PERKS_DEF,
    CONSUMABLES_DEF,
    GameState,
    IS_EMSCRIPTEN,
    PERM_UPGRADE_DEFS,
    SCREEN_H,
    SCREEN_W,
    draw_icon_coin,
    draw_icon_heart,
    draw_icon_shield,
    draw_icon_skull,
    draw_icon_star,
    draw_icon_sword,
    draw_wrapped_text,
    get_skin_cost,
    get_sys_font,
)
from core import i18n
from core.audio import SoundEngine
from core.i18n import LANG, STRINGS, T, toggle_lang
from core.save_system import SaveData
from core.web_bridge import WebBridge
from gfx.biome_renderer import get_drop_shadow
from gfx.sprite_cache import draw_character_procedural_sprite
from gfx.vfx import draw_additive_glow
from spatial.math_utils import clamp
from ui.widgets import Button, Slider


def campaign_target_wave(level: int) -> int:
    return 10 + (level - 1) * 2

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
                "vy": random.uniform(-0.35, -0.9), "vx": random.uniform(-0.25, 0.25),
                "size": random.uniform(1.2, 3.5),  "alpha": random.randint(40, 140),
                "color": random.choice([(255, 215, 65), (80, 225, 255), (195, 90, 255), (255, 120, 180)])}

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
        surf.fill((18, 16, 32))
        for y in range(0, SCREEN_H, 4):
            t = y / SCREEN_H
            # Royal Fantasy / Celestial Arcane gradient
            r = int(24 + (48 - 24) * t)
            g = int(28 + (32 - 28) * t)
            b = int(55 + (88 - 55) * t)
            pygame.draw.line(surf, (r, g, b), (0, y), (SCREEN_W, y))
        self._update_bg(); self._draw_bg(surf)
        # Tiêu đề LEGENDARY SURVIVAL với hiệu ứng ánh sáng hoàng kim & thiên thanh
        float_y  = math.sin(self.tick * 0.03) * 6
        pulse    = 0.5 + 0.5 * math.sin(self.tick * 0.05)
        r_c = int(255 * (0.85 + 0.15 * pulse))
        g_c = int(210 + 45 * math.sin(self.tick * 0.04))
        b_c = int(80 + 175 * (1.0 - pulse))
        tclr     = (r_c, g_c, b_c)
        title_str = "LEGENDARY SURVIVAL"
        sh       = self.font_title.render(title_str, True, (12, 10, 26))
        glow     = self.font_title.render(title_str, True, (60, 160, 255))
        ts       = self.font_title.render(title_str, True, tclr)
        ty       = int(SCREEN_H * 0.09 + float_y)
        tx       = SCREEN_W // 2 - ts.get_width() // 2
        surf.blit(sh, (tx + 4, ty + 4))
        surf.blit(glow, (tx - 1, ty - 1))
        surf.blit(ts, (tx, ty))

        sub = self.font_sub.render("Huyền Thoại Sinh Tồn — Celestial Arcane Edition", True, (160, 230, 255))
        surf.blit(sub, sub.get_rect(centerx=SCREEN_W//2, y=ty + ts.get_height() + 4))
        line_y = ty + ts.get_height() + 32
        pygame.draw.line(surf, (95, 80, 165), (SCREEN_W//2-220, line_y), (SCREEN_W//2+220, line_y), 1)
        pygame.draw.circle(surf, (255, 215, 75), (SCREEN_W//2, line_y), 4)

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
    Hiển thị 6 Lớp Nhân Vật RPG trong bố cục Lưới 3x2 (3x2 Grid) sắc nét, rộng rãi,
    tích hợp draw_wrapped_text ngăn triệt để tràn viền chữ, kèm mô hình sprite động đa lớp,
    thanh chỉ số, nội tại và bảng Cường Hóa Vĩnh Viễn bằng Vàng.
    """
    CARD_W, CARD_H = 380, 192
    GAP_X, GAP_Y   = 18, 12

    def __init__(self, save: SaveData):
        self.save      = save
        self.tick      = 0
        self.notice    = ""
        self.notice_cd = 0
        self.font_title = get_sys_font(32, bold=True)
        self.font_name  = get_sys_font(17, bold=True)
        self.font_sub   = get_sys_font(11, italic=True)
        self.font_desc  = get_sys_font(11)
        self.font_pass  = get_sys_font(11, bold=True)
        self.font_cost  = get_sys_font(13, bold=True)
        self.font_stat  = get_sys_font(10, bold=True)
        self.font_back  = get_sys_font(18, bold=True)
        self.font_gold  = get_sys_font(18, bold=True)
        self.btn_back  = Button(SCREEN_W // 2 - 230, SCREEN_H - 58, 210, 42, T("menu_back"), self.font_back)
        self.btn_skins = Button(SCREEN_W // 2 + 20,  SCREEN_H - 58, 230, 42, T("menu_skins"), self.font_back)

    def _card_rects(self) -> List[pygame.Rect]:
        total_w = 3 * self.CARD_W + 2 * self.GAP_X
        sx      = (SCREEN_W - total_w) // 2
        sy      = 62
        rects = []
        for i in range(len(CHARACTER_DEFS)):
            col = i % 3
            row = i // 3
            rx = sx + col * (self.CARD_W + self.GAP_X)
            ry = sy + row * (self.CARD_H + self.GAP_Y)
            rects.append(pygame.Rect(rx, ry, self.CARD_W, self.CARD_H))
        return rects

    def _perm_rects(self) -> List[pygame.Rect]:
        w, h = 265, 52
        gap = 18
        total_w = len(PERM_UPGRADE_DEFS) * w + (len(PERM_UPGRADE_DEFS) - 1) * gap
        sx = (SCREEN_W - total_w) // 2
        y = 484
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
        surf.fill((18, 16, 32))
        for y in range(0, SCREEN_H, 4):
            t = y / SCREEN_H
            r = int(24 + (48 - 24) * t)
            g = int(28 + (32 - 28) * t)
            b = int(55 + (88 - 55) * t)
            pygame.draw.line(surf, (r, g, b), (0, y), (SCREEN_W, y))

        title = self.font_title.render(T("menu_chars"), True, (215, 185, 255))
        surf.blit(title, title.get_rect(centerx=SCREEN_W // 2, y=16))

        gold_s = self.font_gold.render(f"{T('gold')}: {self.save.total_gold}", True, C_YELLOW)
        surf.blit(gold_s, (SCREEN_W - gold_s.get_width() - 28, 20))

        rects = self._card_rects()
        mx, my = pygame.mouse.get_pos()

        sig_weapons = {
            "warrior": "Trảm Huyết Nguyệt",
            "mage": "Hố Đen Hư Không",
            "rogue": "Mưa Tên Độc Ảnh",
            "paladin": "Phán Quyết Ánh Sáng",
            "necromancer": "Triệu Hồi Cốt Binh",
            "dragon_lancer": "Long Viêm Xung Kích",
        }

        for i, (cdef, rect) in enumerate(zip(CHARACTER_DEFS, rects)):
            cid      = cdef["id"]
            owned    = cid in self.save.unlocked_ids
            selected = cid == self.save.selected_id
            hovering = rect.collidepoint(mx, my)

            bg_alpha = 242 if (hovering or selected) else 200
            card_s   = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
            card_s.fill((20, 18, 38, bg_alpha))
            surf.blit(card_s, rect.topleft)

            border_c = (255, 220, 80) if selected else (cdef["color"] if hovering else (75, 68, 125))
            border_w = 3 if selected else (2 if hovering else 1)
            pygame.draw.rect(surf, border_c, rect, border_w, border_radius=10)

            # Cột Trái: Mô hình nhân vật procedural động + Thanh chỉ số
            preview_x = rect.x + 56
            preview_y = rect.y + 48
            dark_c = tuple(max(0, int(c * 0.5)) for c in cdef["color"])
            sway_x = math.sin(self.tick * 0.06 + i) * 0.65
            preview_skin = self.save.equipped_skin if selected else "default"
            draw_character_procedural_sprite(
                surf, cid, preview_x, preview_y, 16,
                cdef["color"], dark_c, math.sin(self.tick * 0.04 + i) * 0.35,
                self.tick, vx=sway_x, vy=0.0, moving=True,
                cape_sway=(sway_x, 0.2), is_preview=True,
                skin_id=preview_skin,
            )

            # 3 thanh chỉ số dưới avatar
            bars = cdef.get("stats_bars", [])
            for b_i, (b_lbl, b_val) in enumerate(bars[:3]):
                by_bar = rect.y + 92 + b_i * 17
                lbl_b = self.font_stat.render(b_lbl, True, (175, 170, 210))
                surf.blit(lbl_b, (rect.x + 10, by_bar - 1))
                bx_bar = rect.x + 44
                bw_bar = 60
                pygame.draw.rect(surf, (34, 30, 56), (bx_bar, by_bar + 2, bw_bar, 7), border_radius=3)
                pygame.draw.rect(surf, cdef["color"], (bx_bar, by_bar + 2, int(bw_bar * b_val), 7), border_radius=3)

            if not owned:
                lock_s = self.font_stat.render(T("locked"), True, (240, 90, 90))
                surf.blit(lock_s, (rect.x + 10, rect.y + 150))

            # Cột Phải: Tên RPG Class, Biệt danh, Kỹ năng độc quyền, Mô tả, Nội tại, Nút chọn
            cur_strings = STRINGS.get(i18n.LANG, STRINGS["VI"])
            char_name = cur_strings["char_names"].get(cid, cdef["name"])
            ns = self.font_name.render(char_name, True, cdef["color"] if owned else (150, 150, 165))
            surf.blit(ns, (rect.x + 118, rect.y + 8))

            sub_dict = cur_strings.get("char_subtitles", {})
            if cid in sub_dict:
                sub_s = self.font_sub.render(sub_dict[cid], True, (160, 155, 195))
                surf.blit(sub_s, (rect.x + 118, rect.y + 30))

            sig_name = sig_weapons.get(cid, "")
            sig_s = self.font_pass.render(f"[Kỹ năng: {sig_name}]", True, (90, 225, 255))
            surf.blit(sig_s, (rect.x + 118, rect.y + 48))

            # Mô tả & Nội tại (tự động xuống dòng chuẩn xác với draw_wrapped_text)
            char_desc = cur_strings["char_descs"].get(cid, cdef["desc"])
            desc_r = pygame.Rect(rect.x + 118, rect.y + 68, rect.w - 128, 38)
            draw_wrapped_text(surf, char_desc, self.font_desc, (215, 215, 240), desc_r, align="left", line_spacing=2, max_lines=2)

            pass_dict = cur_strings.get("char_passives", {})
            if cid in pass_dict:
                pass_r = pygame.Rect(rect.x + 118, rect.y + 110, rect.w - 128, 36)
                draw_wrapped_text(surf, pass_dict[cid], self.font_pass, (255, 215, 95), pass_r, align="left", line_spacing=2, max_lines=2)

            # Nút Chọn / Mở khóa ở góc dưới phải
            btn_rect = pygame.Rect(rect.right - 142, rect.bottom - 36, 132, 28)
            btn_bg = (38, 70, 48) if selected else ((44, 36, 75) if hovering else (28, 24, 48))
            pygame.draw.rect(surf, btn_bg, btn_rect, border_radius=6)
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

        # Khu vực Cường Hóa Vĩnh Viễn (Permanent Stat Upgrades)
        perm_title = self.font_pass.render(T("perm_upgrades"), True, (255, 215, 90))
        surf.blit(perm_title, perm_title.get_rect(centerx=SCREEN_W // 2, y=462))
        p_rects = self._perm_rects()
        for i, (key, label_key, base_cost, max_lv) in enumerate(PERM_UPGRADE_DEFS):
            pr = p_rects[i]
            cur = self.save.perm_upgrades.get(key, 0)
            hov = pr.collidepoint(mx, my)
            pygame.draw.rect(surf, (24, 20, 44) if not hov else (42, 36, 76), pr, border_radius=8)
            pygame.draw.rect(surf, (140, 120, 230) if hov else (80, 70, 135), pr, 2 if hov else 1, border_radius=8)
            p_name = self.font_desc.render(f"{T(label_key)} Lv.{cur}/{max_lv}", True, C_WHITE)
            surf.blit(p_name, (pr.x + 12, pr.y + 6))
            if cur >= max_lv:
                c_txt = self.font_pass.render("MAX", True, C_GREEN)
            else:
                cost = base_cost * (cur + 1)
                c_txt = self.font_pass.render(f"{cost} Vàng", True,
                                              C_YELLOW if self.save.total_gold >= cost else C_RED)
            surf.blit(c_txt, (pr.right - c_txt.get_width() - 12, pr.y + 6))
            for lv_i in range(max_lv):
                pip_r = pygame.Rect(pr.x + 12 + lv_i * 46, pr.y + 30, 38, 10)
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
                            if self.save.equipped_skin == sid:
                                # Đang dùng -> Nhấp để tháo trang phục về mặc định!
                                self.save.equip_skin("default")
                                if self.sfx:
                                    self.sfx.play_xp()
                            else:
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
            vfx_lines = self._wrap_text("[VFX] " + sdef.get("vfx_desc", ""), self.font_vfx, rect.w - 24)
            for l_i, line in enumerate(vfx_lines[:2]):
                vs = self.font_vfx.render(line, True, (255, 215, 85))
                surf.blit(vs, vs.get_rect(centerx=rect.centerx, y=rect.y + 262 + l_i * 19))

            # Nút Mua / Trang Bị / Đang Dùng dưới đáy thẻ
            btn_rect = pygame.Rect(rect.x + 20, rect.bottom - 48, rect.w - 40, 34)
            btn_bg = (35, 65, 45) if equipped else ((38, 30, 68) if hovering else (26, 22, 46))
            pygame.draw.rect(surf, btn_bg, btn_rect, border_radius=8)
            pygame.draw.rect(surf, border_c, btn_rect, 2 if (equipped or hovering) else 1, border_radius=8)

            if equipped:
                lbl_txt = T("skin_unequip") if hovering else T("skin_equipped")
                lbl_s = self.font_cost.render(lbl_txt, True, (255, 140, 140) if hovering else C_GREEN)
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
# Sảnh Chuẩn Bị Chiến Đấu Trước Trận Đấu (Pre-Match Preparation Lobby)
# ---------------------------------------------------------------------------
class LobbyScreen:
    """
    Sảnh Chuẩn Bị Chiến Đấu (Pre-Match Preparation Lobby):
      1. Khung Nhân Vật & Ngoại Hình: Xem trước mô hình procedural động đa lớp, chuyển đổi Hệ Phái,
         chuyển đổi hoặc Tháo Trang Phục (Unequip về mặc định).
      2. Khung Thiên Phú Đặc Quyền Hệ Phái: 3 thiên phú riêng cho mỗi Class, mở khóa bằng Vàng,
         trang bị thiên phú hoạt động trong trận đấu.
      3. Khung Vật Phẩm Tác Chiến (Shop & Túi đồ): 5 vật phẩm tactical (Bình Máu, Cuồng Nộ, Thần Tốc,
         Thiết Giáp, Hút Ngọc) mua bằng Vàng, kích hoạt bằng phím [1]-[5] khi vào trận.
      4. Nút XUẤT CHIẾN (Khởi hành trận chiến) và Nút QUAY LẠI (Về Menu chính).
    """
    def __init__(self, save: SaveData, sfx: Optional[SoundEngine] = None):
        self.save = save
        self.sfx = sfx
        self.tick = 0
        self.notice = ""
        self.notice_cd = 0

        self.font_title = get_sys_font(32, bold=True)
        self.font_sub   = get_sys_font(13)
        self.font_sec   = get_sys_font(16, bold=True)
        self.font_name  = get_sys_font(18, bold=True)
        self.font_desc  = get_sys_font(12)
        self.font_pass  = get_sys_font(12, bold=True)
        self.font_btn   = get_sys_font(15, bold=True)
        self.font_gold  = get_sys_font(19, bold=True)
        self.font_badge = get_sys_font(11, bold=True)

        self.btn_launch = Button(SCREEN_W - 310, SCREEN_H - 68, 270, 50, T("lobby_launch"), get_sys_font(21, bold=True))
        self.btn_back   = Button(40, SCREEN_H - 62, 170, 44, T("menu_back"), self.font_btn)
        self.btn_change_char = Button(48, 382, 172, 34, T("lobby_change_char"), self.font_badge)
        self.btn_change_skin = Button(228, 382, 172, 34, T("lobby_change_skin"), self.font_badge)
        self.btn_unequip_skin = Button(138, 422, 172, 28, T("lobby_unequip_skin"), self.font_badge)

        self._bg_parts = [MainMenu._new_p() for _ in range(40)]

    def _char_prev_rect(self) -> pygame.Rect:
        return pygame.Rect(40, 75, 370, 385)

    def _perks_panel_rect(self) -> pygame.Rect:
        return pygame.Rect(428, 75, 812, 385)

    def _consumables_panel_rect(self) -> pygame.Rect:
        return pygame.Rect(40, 474, 910, 168)

    def handle_events(self, events) -> Optional[str]:
        mx, my = pygame.mouse.get_pos()
        self.btn_launch.update(mx, my)
        self.btn_back.update(mx, my)
        self.btn_change_char.update(mx, my)
        self.btn_change_skin.update(mx, my)
        self.btn_unequip_skin.update(mx, my)

        if self.notice_cd > 0:
            self.notice_cd -= 1

        cid = self.save.selected_id
        unlocked_list = [c["id"] for c in CHARACTER_DEFS if c["id"] in self.save.unlocked_ids]
        if cid not in unlocked_list and unlocked_list:
            cid = unlocked_list[0]
            self.save.selected_id = cid

        cur_idx = unlocked_list.index(cid) if cid in unlocked_list else 0

        arrow_l = pygame.Rect(55, 335, 32, 32)
        arrow_r = pygame.Rect(362, 335, 32, 32)

        for ev in events:
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                return "back"
            if self.btn_back.is_clicked(ev):
                return "back"
            if self.btn_launch.is_clicked(ev):
                return "launch"
            if self.btn_change_char.is_clicked(ev):
                return "chars"
            if self.btn_change_skin.is_clicked(ev):
                return "skins"
            if self.btn_unequip_skin.is_clicked(ev):
                self.save.equip_skin("default")
                if self.sfx:
                    self.sfx.play_xp()

            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                if arrow_l.collidepoint(ev.pos):
                    nxt = unlocked_list[(cur_idx - 1) % len(unlocked_list)]
                    self.save.selected_id = nxt
                    self.save.save()
                    if self.sfx: self.sfx.play_coin()
                elif arrow_r.collidepoint(ev.pos):
                    nxt = unlocked_list[(cur_idx + 1) % len(unlocked_list)]
                    self.save.selected_id = nxt
                    self.save.save()
                    if self.sfx: self.sfx.play_coin()

                perk_defs = CLASS_PERKS_DEF.get(cid, [])
                p_panel = self._perks_panel_rect()
                card_w, card_h = 246, 305
                gap = 18
                for p_i, pdef in enumerate(perk_defs):
                    px = p_panel.x + 22 + p_i * (card_w + gap)
                    py = p_panel.y + 48
                    btn_r = pygame.Rect(px + 16, py + card_h - 48, card_w - 32, 34)
                    if btn_r.collidepoint(ev.pos):
                        pid = pdef["id"]
                        is_equipped = (self.save.class_perks.get(cid) == pid)
                        is_unlocked = (pid in self.save.unlocked_perks)
                        if is_equipped:
                            pass
                        elif is_unlocked:
                            self.save.equip_perk(cid, pid)
                            if self.sfx: self.sfx.play_levelup()
                        else:
                            if self.save.total_gold >= pdef["cost"]:
                                self.save.unlock_perk(pid, pdef["cost"])
                                self.save.equip_perk(cid, pid)
                                if self.sfx: self.sfx.play_awakened()
                            else:
                                self.notice = T("not_enough")
                                self.notice_cd = 120

                c_panel = self._consumables_panel_rect()
                item_w = 164
                i_gap = 14
                for i_i, idef in enumerate(CONSUMABLES_DEF):
                    ix = c_panel.x + 16 + i_i * (item_w + i_gap)
                    iy = c_panel.y + 36
                    buy_r = pygame.Rect(ix + 8, iy + 78, item_w - 16, 30)
                    if buy_r.collidepoint(ev.pos):
                        if self.save.buy_consumable(idef["id"], idef["cost"]):
                            if self.sfx: self.sfx.play_coin()
                        else:
                            self.notice = T("not_enough")
                            self.notice_cd = 120

        return None

    def draw(self, surf):
        self.tick += 1
        surf.fill((18, 16, 32))
        for y in range(0, SCREEN_H, 4):
            t = y / SCREEN_H
            r = int(24 + (48 - 24) * t)
            g = int(28 + (32 - 28) * t)
            b = int(55 + (88 - 55) * t)
            pygame.draw.line(surf, (r, g, b), (0, y), (SCREEN_W, y))

        for p in self._bg_parts:
            p["x"] += p["vx"]; p["y"] += p["vy"]
            if p["y"] < -5 or not (0 <= p["x"] <= SCREEN_W):
                p["x"] = random.uniform(0, SCREEN_W); p["y"] = SCREEN_H + 5
            s = pygame.Surface((int(p["size"]*2+2),)*2, pygame.SRCALPHA)
            pygame.draw.circle(s, (*p["color"], p["alpha"]),
                               (int(p["size"]+1),)*2, int(p["size"]))
            surf.blit(s, (int(p["x"]), int(p["y"])))

        title = self.font_title.render(T("lobby_title"), True, (255, 220, 80))
        surf.blit(title, (42, 16))
        sub = self.font_sub.render(T("lobby_sub"), True, (175, 170, 225))
        surf.blit(sub, (44, 50))

        gold_s = self.font_gold.render(f"{T('gold')}: {self.save.total_gold}", True, C_YELLOW)
        g_rect = pygame.Rect(SCREEN_W - gold_s.get_width() - 48, 16, gold_s.get_width() + 32, 38)
        pygame.draw.rect(surf, (22, 18, 42), g_rect, border_radius=8)
        pygame.draw.rect(surf, (225, 185, 55), g_rect, 2, border_radius=8)
        surf.blit(gold_s, gold_s.get_rect(center=g_rect.center))

        cid = self.save.selected_id
        cdef = next((c for c in CHARACTER_DEFS if c["id"] == cid), CHARACTER_DEFS[0])
        mx, my = pygame.mouse.get_pos()

        # KHUNG 1: NHÂN VẬT & NGOẠI HÌNH
        c_panel = self._char_prev_rect()
        pygame.draw.rect(surf, (22, 18, 40), c_panel, border_radius=12)
        pygame.draw.rect(surf, (85, 75, 140), c_panel, 1, border_radius=12)

        hdr1 = self.font_sec.render(T("lobby_char_sec"), True, (160, 225, 255))
        surf.blit(hdr1, (c_panel.x + 18, c_panel.y + 12))

        pv_x = c_panel.centerx
        pv_y = c_panel.y + 120
        dark_c = tuple(max(0, int(c * 0.5)) for c in cdef["color"])
        skin_id = self.save.equipped_skin
        draw_additive_glow(surf, pv_x, pv_y, 55, cdef["color"], intensity=0.35)
        sway_x = math.sin(self.tick * 0.05) * 0.6
        draw_character_procedural_sprite(
            surf, cid, pv_x, pv_y, 24,
            cdef["color"], dark_c, math.sin(self.tick * 0.04) * 0.3,
            self.tick, vx=sway_x, vy=0.0, moving=True,
            cape_sway=(sway_x, 0.25), is_preview=True,
            skin_id=skin_id,
        )

        arrow_l = pygame.Rect(55, 335, 32, 32)
        arrow_r = pygame.Rect(362, 335, 32, 32)
        for ar, symbol in [(arrow_l, "<"), (arrow_r, ">")]:
            hov = ar.collidepoint(mx, my)
            pygame.draw.rect(surf, (45, 38, 76) if hov else (30, 25, 52), ar, border_radius=6)
            pygame.draw.rect(surf, (150, 130, 230) if hov else (75, 65, 120), ar, 1, border_radius=6)
            sym_s = self.font_name.render(symbol, True, C_YELLOW if hov else C_WHITE)
            surf.blit(sym_s, sym_s.get_rect(center=ar.center))

        cur_strings = STRINGS.get(i18n.LANG, STRINGS["VI"])
        char_name = cur_strings["char_names"].get(cid, cdef["name"])
        cn_s = self.font_name.render(char_name, True, cdef["color"])
        surf.blit(cn_s, cn_s.get_rect(centerx=c_panel.centerx, y=c_panel.y + 200))

        sub_str = cur_strings.get("char_subtitles", {}).get(cid, "")
        if sub_str:
            sub_s = self.font_sub.render(sub_str, True, (160, 155, 195))
            surf.blit(sub_s, sub_s.get_rect(centerx=c_panel.centerx, y=c_panel.y + 228))

        if skin_id in ANIME_SKIN_BY_ID:
            s_name = ANIME_SKIN_BY_ID[skin_id]["name"]
            sk_s = self.font_pass.render(f"Trang phục: {s_name}", True, (255, 215, 80))
        else:
            sk_s = self.font_desc.render("Ngoại hình: Mặc Định", True, (175, 170, 210))
        surf.blit(sk_s, sk_s.get_rect(centerx=c_panel.centerx, y=c_panel.y + 252))

        desc_str = cur_strings["char_descs"].get(cid, cdef["desc"])
        desc_r = pygame.Rect(c_panel.x + 20, c_panel.y + 278, c_panel.w - 40, 48)
        draw_wrapped_text(surf, desc_str, self.font_desc, (215, 215, 240), desc_r, align="center", line_spacing=2, max_lines=2)

        self.btn_change_char.label = T("lobby_change_char")
        self.btn_change_skin.label = T("lobby_change_skin")
        self.btn_change_char.draw(surf)
        self.btn_change_skin.draw(surf)

        if skin_id != "default":
            self.btn_unequip_skin.label = T("lobby_unequip_skin")
            self.btn_unequip_skin.draw(surf)

        # KHUNG 2: THIÊN PHÚ HỆ PHÁI
        p_panel = self._perks_panel_rect()
        pygame.draw.rect(surf, (22, 18, 40), p_panel, border_radius=12)
        pygame.draw.rect(surf, (85, 75, 140), p_panel, 1, border_radius=12)

        hdr2 = self.font_sec.render(f"{T('lobby_perk_sec')} — {char_name}", True, (255, 215, 80))
        surf.blit(hdr2, (p_panel.x + 22, p_panel.y + 12))

        perk_defs = CLASS_PERKS_DEF.get(cid, [])
        active_perk_id = self.save.class_perks.get(cid, perk_defs[0]["id"] if perk_defs else "")
        card_w, card_h = 246, 305
        gap = 18

        for p_i, pdef in enumerate(perk_defs):
            px = p_panel.x + 22 + p_i * (card_w + gap)
            py = p_panel.y + 48
            card_r = pygame.Rect(px, py, card_w, card_h)
            is_equipped = (active_perk_id == pdef["id"])
            is_unlocked = (pdef["id"] in self.save.unlocked_perks)
            hov = card_r.collidepoint(mx, my)

            bg_alpha = 245 if (is_equipped or hov) else 190
            cs = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
            cs.fill((16, 14, 30, bg_alpha))
            surf.blit(cs, card_r.topleft)

            bd_col = (255, 215, 65) if is_equipped else ((120, 210, 255) if hov else (70, 60, 115))
            pygame.draw.rect(surf, bd_col, card_r, 3 if is_equipped else (2 if hov else 1), border_radius=10)

            draw_additive_glow(surf, px + card_w // 2, py + 52, 38, bd_col, intensity=0.45 if is_equipped else 0.2)
            pygame.draw.circle(surf, bd_col, (px + card_w // 2, py + 52), 24, 2)
            draw_icon_sword(surf, px + card_w // 2 - 8, py + 44, 16, bd_col)

            pname_s = self.font_name.render(pdef["name"], True, (255, 225, 80) if is_equipped else C_WHITE)
            surf.blit(pname_s, pname_s.get_rect(centerx=px + card_w // 2, y=py + 92))

            p_desc_r = pygame.Rect(px + 14, py + 128, card_w - 28, 85)
            draw_wrapped_text(surf, pdef["desc"], self.font_desc, (215, 215, 240), p_desc_r, align="center", line_spacing=3, max_lines=4)

            btn_r = pygame.Rect(px + 16, py + card_h - 48, card_w - 32, 34)
            if is_equipped:
                pygame.draw.rect(surf, (36, 75, 48), btn_r, border_radius=8)
                pygame.draw.rect(surf, (90, 240, 130), btn_r, 2, border_radius=8)
                b_lbl = self.font_btn.render(T("lobby_perk_equipped"), True, (130, 255, 160))
            elif is_unlocked:
                pygame.draw.rect(surf, (38, 48, 85) if hov else (26, 32, 58), btn_r, border_radius=8)
                pygame.draw.rect(surf, (80, 180, 255), btn_r, 1, border_radius=8)
                b_lbl = self.font_btn.render(T("lobby_perk_equip"), True, (140, 220, 255))
            else:
                can_buy = self.save.total_gold >= pdef["cost"]
                pygame.draw.rect(surf, (55, 34, 42) if can_buy else (35, 22, 28), btn_r, border_radius=8)
                pygame.draw.rect(surf, (220, 160, 60) if can_buy else (150, 60, 60), btn_r, 1, border_radius=8)
                b_lbl = self.font_btn.render(T("lobby_perk_unlock", cost=pdef["cost"]), True, C_YELLOW if can_buy else C_RED)
            surf.blit(b_lbl, b_lbl.get_rect(center=btn_r.center))

        # KHUNG 3: VẬT PHẨM TÁC CHIẾN
        s_panel = self._consumables_panel_rect()
        pygame.draw.rect(surf, (22, 18, 40), s_panel, border_radius=12)
        pygame.draw.rect(surf, (85, 75, 140), s_panel, 1, border_radius=12)

        hdr3 = self.font_sec.render(T("lobby_shop_sec"), True, (100, 240, 180))
        surf.blit(hdr3, (s_panel.x + 18, s_panel.y + 10))

        item_w = 164
        i_gap = 14
        for i_i, idef in enumerate(CONSUMABLES_DEF):
            ix = s_panel.x + 16 + i_i * (item_w + i_gap)
            iy = s_panel.y + 36
            i_rect = pygame.Rect(ix, iy, item_w, 118)
            hov = i_rect.collidepoint(mx, my)

            pygame.draw.rect(surf, (28, 24, 50) if hov else (18, 15, 34), i_rect, border_radius=8)
            pygame.draw.rect(surf, idef["color"] if hov else (65, 58, 105), i_rect, 1, border_radius=8)

            badge_s = self.font_badge.render(f"[{idef['slot']}] {idef['name']}", True, idef["color"])
            surf.blit(badge_s, (ix + 8, iy + 6))

            cur_qty = self.save.consumables.get(idef["id"], 0)
            qty_s = self.font_badge.render(f"x{cur_qty}", True, (255, 235, 120))
            surf.blit(qty_s, (ix + item_w - qty_s.get_width() - 8, iy + 6))

            desc_r = pygame.Rect(ix + 6, iy + 26, item_w - 12, 42)
            draw_wrapped_text(surf, idef["desc"], self.font_badge, (200, 195, 230), desc_r, align="center", line_spacing=2, max_lines=2)

            buy_r = pygame.Rect(ix + 8, iy + 78, item_w - 16, 30)
            can_afford = self.save.total_gold >= idef["cost"]
            b_bg = (48, 38, 76) if (can_afford and hov) else (28, 22, 48)
            pygame.draw.rect(surf, b_bg, buy_r, border_radius=6)
            pygame.draw.rect(surf, idef["color"] if can_afford else (120, 50, 50), buy_r, 1, border_radius=6)
            b_txt = self.font_badge.render(f"+ Mua ({idef['cost']}G)", True, C_YELLOW if can_afford else C_RED)
            surf.blit(b_txt, b_txt.get_rect(center=buy_r.center))

        # KHUNG 4: NÚT XUẤT CHIẾN & QUAY LẠI
        self.btn_back.label = T("menu_back")
        self.btn_launch.label = T("lobby_launch")
        self.btn_back.draw(surf)

        pulse_btn = 0.5 + 0.5 * math.sin(self.tick * 0.08)
        btn_glow = (int(255 * (0.8 + 0.2 * pulse_btn)), int(190 + 55 * pulse_btn), int(50 * (1 - pulse_btn)))
        pygame.draw.rect(surf, btn_glow, self.btn_launch.rect.inflate(6, 6), 2, border_radius=12)
        self.btn_launch.draw(surf)

        if self.notice_cd > 0:
            alpha = min(255, self.notice_cd * 4)
            ns = self.font_name.render(self.notice, True, C_RED)
            ns.set_alpha(alpha)
            surf.blit(ns, ns.get_rect(centerx=SCREEN_W // 2, y=SCREEN_H - 85))

        pygame.display.flip()


# ---------------------------------------------------------------------------
# Ana oyun
# ---------------------------------------------------------------------------
# Boss spawn aralığı (saniye)
BOSS_INTERVAL = 120   # 2 dakikada bir boss

