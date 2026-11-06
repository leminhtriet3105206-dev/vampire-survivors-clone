"""UI Widgets: Interactive buttons, animated hover states, and percentage sliders."""
from typing import Callable, Optional, Tuple
import pygame
import audio_settings


class Button:
    """Interactive button with smooth hover interpolation, drop shadows, and click handling."""

    CLR_NORMAL   = (30, 28, 50)
    CLR_HOVER    = (60, 55, 100)
    CLR_BORDER   = (80, 75, 140)
    CLR_BORDER_H = (140, 120, 255)
    CLR_TEXT     = (200, 195, 240)
    CLR_TEXT_H   = (255, 255, 255)

    __slots__ = ("base_rect", "label", "font", "hovered", "_hover_t")

    def __init__(self, x: int, y: int, w: int, h: int, label: str, font: pygame.font.Font):
        self.base_rect: pygame.Rect = pygame.Rect(x, y, w, h)
        self.label: str = label
        self.font: pygame.font.Font = font
        self.hovered: bool = False
        self._hover_t: float = 0.0

    @property
    def rect(self) -> pygame.Rect:
        return self.base_rect

    def update(self, mx: int, my: int) -> None:
        self.hovered = self.base_rect.collidepoint(mx, my)
        target = 1.0 if self.hovered else 0.0
        self._hover_t += (target - self._hover_t) * 0.18

    def is_clicked(self, event: pygame.event.Event) -> bool:
        return (
            event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 1
            and self.base_rect.collidepoint(event.pos)
        )

    def draw(self, surf: pygame.Surface) -> None:
        t = self._hover_t
        expand = int(t * 3)
        rect = self.base_rect.inflate(expand * 2, expand * 2)
        bg = tuple(int(a + (b - a) * t) for a, b in zip(self.CLR_NORMAL, self.CLR_HOVER))
        border = tuple(int(a + (b - a) * t) for a, b in zip(self.CLR_BORDER, self.CLR_BORDER_H))
        txtclr = tuple(int(a + (b - a) * t) for a, b in zip(self.CLR_TEXT, self.CLR_TEXT_H))

        if t > 0.05:
            sh = pygame.Surface((rect.w + 8, rect.h + 8), pygame.SRCALPHA)
            pygame.draw.rect(sh, (0, 0, 0, int(80 * t)), sh.get_rect(), border_radius=10)
            surf.blit(sh, (rect.x - 4, rect.y + 4))

        pygame.draw.rect(surf, bg, rect, border_radius=8)
        pygame.draw.rect(surf, border, rect, 2, border_radius=8)
        ts = self.font.render(self.label, True, txtclr)
        surf.blit(ts, ts.get_rect(center=rect.center))


class Slider:
    """Horizontal percentage slider (0-100%) with drag and keyboard control."""

    __slots__ = (
        "track",
        "hit",
        "value",
        "font",
        "on_change",
        "on_release",
        "dragging",
        "focused",
    )

    def __init__(
        self,
        x: int,
        y: int,
        w: int,
        value: int,
        font: pygame.font.Font,
        on_change: Optional[Callable[[int], None]] = None,
        on_release: Optional[Callable[[int], None]] = None,
    ):
        self.track: pygame.Rect = pygame.Rect(x, y, w, 8)
        self.hit: pygame.Rect = self.track.inflate(20, 28)
        self.value: int = audio_settings.clamp_percent(value)
        self.font: pygame.font.Font = font
        self.on_change: Optional[Callable[[int], None]] = on_change
        self.on_release: Optional[Callable[[int], None]] = on_release
        self.dragging: bool = False
        self.focused: bool = False

    def _set_from_x(self, mx: int) -> None:
        frac = (mx - self.track.x) / self.track.w
        self.set_value(round(max(0.0, min(1.0, frac)) * 100))

    def set_value(self, v: int) -> None:
        v = audio_settings.clamp_percent(v, self.value)
        if v != self.value:
            self.value = v
            if self.on_change:
                self.on_change(v)

    def handle_event(self, ev: pygame.event.Event) -> None:
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
                if self.on_release:
                    self.on_release(self.value)
            elif ev.key == pygame.K_RIGHT:
                self.set_value(self.value + 5)
                if self.on_release:
                    self.on_release(self.value)

    def draw(self, surf: pygame.Surface) -> None:
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

