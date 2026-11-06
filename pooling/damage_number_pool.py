"""High-performance pooled Damage Numbers system with text surface caching."""
import random
from typing import Dict, List, Optional, Tuple, Union
import pygame

from pooling.object_pool import ObjectPool
from spatial.math_utils import clamp

SCREEN_W = 1280
SCREEN_H = 720
C_WHITE = (255, 255, 255)

_DAMAGE_SURF_CACHE: Dict[Tuple[str, Tuple[int, int, int], float], Tuple[pygame.Surface, pygame.Surface]] = {}


def get_cached_damage_surfaces(
    font: pygame.font.Font, text_str: str, color: Tuple[int, int, int], scale: float
) -> Tuple[pygame.Surface, pygame.Surface]:
    """Retrieve pre-rendered text and shadow surfaces to avoid per-frame CPU font rasterization."""
    col = color[:3]
    s_key = round(scale, 2)
    key = (text_str, col, s_key)
    cached = _DAMAGE_SURF_CACHE.get(key)
    if cached is not None:
        return cached

    # Prevent cache explosion
    if len(_DAMAGE_SURF_CACHE) > 512:
        _DAMAGE_SURF_CACHE.clear()

    text = font.render(text_str, True, col)
    shadow = font.render(text_str, True, (12, 8, 22))
    if s_key > 1.05:
        w = max(8, int(text.get_width() * s_key))
        h = max(8, int(text.get_height() * s_key))
        text = pygame.transform.scale(text, (w, h))
        shadow = pygame.transform.scale(shadow, (w, h))

    _DAMAGE_SURF_CACHE[key] = (text, shadow)
    return text, shadow


class PooledDamageNumber:
    """Recyclable floating combat text."""

    __slots__ = (
        "x",
        "y",
        "vx",
        "vy",
        "value",
        "is_crit",
        "is_heal",
        "scale",
        "life",
        "max_life",
        "color",
        "_pooled",
    )

    def __init__(self, *args, **kwargs):
        self.x: float = 0.0
        self.y: float = 0.0
        self.vx: float = 0.0
        self.vy: float = -1.75
        self.value: str = ""
        self.is_crit: bool = False
        self.is_heal: bool = False
        self.scale: float = 1.0
        self.life: int = 0
        self.max_life: int = 1
        self.color: Tuple[int, int, int] = C_WHITE
        self._pooled: bool = False
        if args or kwargs:
            self.reset(*args, **kwargs)

    def reset(
        self,
        x: float,
        y: float,
        value: Union[int, float, str],
        color: Tuple[int, int, int] = C_WHITE,
        scale: float = 1.0,
        life: int = 48,
        is_crit: bool = False,
        is_heal: bool = False,
        text_override: Optional[str] = None,
    ) -> "PooledDamageNumber":
        """Reinitialize combat text in-place."""
        self.x = float(x) + random.uniform(-6, 6)
        self.y = float(y)
        self.is_crit = is_crit
        self.is_heal = is_heal

        if text_override is not None:
            self.value = str(text_override)
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
            self.value = str(value)

        self.vx = random.uniform(-0.45, 0.45)
        self.vy = -1.75 if scale <= 1.05 else -2.35
        self.life = max(1, life)
        self.max_life = self.life
        self.color = color[:3] if len(color) >= 3 else C_WHITE
        self.scale = scale
        return self

    def update(self) -> bool:
        """Update position and decay life. Returns True if alive, False if expired."""
        self.x += self.vx
        self.y += self.vy
        self.vx *= 0.94
        self.vy *= 0.94
        self.life -= 1
        return self.life > 0

    def draw(self, surf: pygame.Surface, cam_x: float, cam_y: float, font: pygame.font.Font) -> None:
        """Render damage text with cached surfaces and viewport culling."""
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        if sx < -80 or sx > SCREEN_W + 80 or sy < -40 or sy > SCREEN_H + 40:
            return

        alpha = clamp(int(self.life / max(1, self.max_life) * 255), 0, 255)
        text, shadow = get_cached_damage_surfaces(font, self.value, self.color, self.scale)
        text.set_alpha(alpha)
        shadow.set_alpha(alpha)
        hw = text.get_width() // 2
        surf.blit(shadow, (sx - hw + 2, sy + 2))
        surf.blit(text, (sx - hw, sy))


class DamageNumberPool:
    """Dedicated pool manager for floating combat text."""

    __slots__ = ("_pool",)

    def __init__(self, initial_capacity: int = 300, max_size: int = 1500):
        self._pool: ObjectPool[PooledDamageNumber] = ObjectPool(
            factory=PooledDamageNumber,
            initial_capacity=initial_capacity,
            max_size=max_size,
        )

    def spawn(
        self,
        x: float,
        y: float,
        value: Union[int, float, str],
        color: Tuple[int, int, int] = C_WHITE,
        scale: float = 1.0,
        life: int = 48,
        is_crit: bool = False,
        is_heal: bool = False,
        text_override: Optional[str] = None,
    ) -> PooledDamageNumber:
        """Acquire and reset a floating damage number."""
        return self._pool.acquire(
            x=x,
            y=y,
            value=value,
            color=color,
            scale=scale,
            life=life,
            is_crit=is_crit,
            is_heal=is_heal,
            text_override=text_override,
        )

    def release(self, num: PooledDamageNumber) -> bool:
        """Return a damage number back to the pool."""
        return self._pool.release(num)

    def release_many(self, numbers: List[PooledDamageNumber]) -> int:
        """Bulk release dead damage numbers."""
        return self._pool.release_many(numbers)

    @property
    def available_count(self) -> int:
        return self._pool.available_count

    @property
    def active_count(self) -> int:
        return self._pool.active_count
