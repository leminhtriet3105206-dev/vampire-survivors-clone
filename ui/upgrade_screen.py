"""Level-up card selection and skill fusion presentation screen."""
import random
from typing import Any, List, Optional, Tuple
import pygame

from core.config import C_YELLOW, SCREEN_H, SCREEN_W, draw_wrapped_text, get_sys_font
from core.i18n import T
from weapons.upgrades import (
    FUSION_RECIPES,
    FUSION_TYPES,
    UpgradeType,
    get_recipe_hint,
    get_upgrade_def,
)

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

        card_w, card_h = 330, 230
        gap = 24
        total_w = len(self.choices) * card_w + (len(self.choices) - 1) * gap
        start_x = SCREEN_W // 2 - total_w // 2
        cy = SCREEN_H // 2 - card_h // 2 + 18

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
            bg_alpha = 245 if hovering else 205
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
                      (cx + card_w // 2 - name_surf.get_width() // 2, cy + 14))

            if lv_str:
                lv_col = (255, 90, 90) if is_fusion else ((255, 215, 70) if will_awaken else (150, 220, 255))
                lbl_txt = f"{lv_str}  {T('awakened_tag')}" if will_awaken else lv_str
                lv_s = self.font_sm.render(lbl_txt, True, lv_col)
                surf.blit(lv_s, (cx + card_w // 2 - lv_s.get_width() // 2, cy + 46))

            desc_r = pygame.Rect(cx + 12, cy + 74, card_w - 24, 44)
            draw_wrapped_text(surf, desc, self.font_med, (230, 225, 245), desc_r, align="center", line_spacing=2, max_lines=2)

            # Hiển thị công thức Hợp Nhất (Synergy Recipe Hint) tự động xuống dòng 2 dòng sạch sẽ
            if recipe_hint:
                rh_col = (255, 210, 80) if is_fusion else (195, 165, 255)
                rh_r = pygame.Rect(cx + 10, cy + 124, card_w - 20, 36)
                draw_wrapped_text(surf, recipe_hint, self.font_hint, rh_col, rh_r, align="center", line_spacing=2, max_lines=2)

            key_badge = self.font_hint.render(f"Phím [{i + 1}]", True, (165, 160, 210))
            surf.blit(key_badge, (cx + card_w // 2 - key_badge.get_width() // 2, cy + 168))

            if hovering:
                hint = self.font_sm.render(T("click_hint"), True, (255, 230, 120))
                surf.blit(hint,
                          (cx + card_w // 2 - hint.get_width() // 2, cy + 196))

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

