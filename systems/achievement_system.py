"""Achievement and Toast notification system."""
from dataclasses import dataclass
from typing import List, Optional
import pygame

from core.config import (
    ACHIEVEMENT_DEFS,
    ACHIEVEMENT_TEXT_KEYS,
    AchievementDef,
    AchievementID,
    _DEF_BY_ID,
    get_sys_font,
)
from core.i18n import T

TOAST_W        = 300
TOAST_H        = 60
TOAST_DURATION = 210
TOAST_SLIDE    = 18
TOAST_FADE     = 30
TOAST_PAD_R    = 16
TOAST_PAD_B    = 70

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

