"""Daily and weekly Quest management system."""
from dataclasses import dataclass, field
from enum import Enum, auto
import math
import random
from typing import Any, Dict, List, Optional
import pygame

from core.config import (
    C_GREEN,
    C_RED,
    C_WHITE,
    C_YELLOW,
    QuestType,
    get_sys_font,
)
from core.i18n import T

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

