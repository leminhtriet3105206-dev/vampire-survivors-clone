# -*- coding: utf-8 -*-
"""
Legendary Survival - Modular Game Client
=========================================
Architectural Layout (Phase 1 Refactoring):
  - core/      : Config, Save System, Procedural Audio, Localization, WebBridge
  - spatial/   : Spatial Hash Grid (O(1) collision detection), Math utilities
  - pooling/   : Zero-allocation Object Pools (Particles, DamageNumbers, Projectiles)
  - gfx/       : Biome terrain, Procedural Sprites, Caching, VFX
  - entities/  : Player, Enemy, Boss, Companions (Drone, Turret, SoulMinion)
  - weapons/   : 13 Weapons, Synergy Tree, Mythic Fusions, Ultimates
  - items/     : XPGem, GoldCoin, HealthPotion, ExpMagnet, Chest
  - systems/   : SpawnManager, AchievementManager, QuestManager
  - ui/        : Widgets, Menu Screens, Upgrade Cards
  - engine.py  : Game class and loop orchestrator
"""
import asyncio
import json
import sys
from typing import Any, Dict, Optional

# Platform guard for Emscripten WebAssembly and Pygbag
IS_EMSCRIPTEN = sys.platform == "emscripten"

# ---------------------------------------------------------------------------
# Cầu nối WebAssembly / Pygbag (Emscripten <-> Legendary Survival Web Hub)
# ---------------------------------------------------------------------------
class WebBridge:
    """Cầu nối dữ liệu hai chiều giữa game Pygame (WebAssembly) và Web Hub."""

    @staticmethod
    def get_user() -> Optional[Dict[str, Any]]:
        """Đọc thông tin người chơi từ Web Hub (localStorage 'ls_bridge_user')."""
        if not (sys.platform == "emscripten"):
            return None
        try:
            import platform

            raw = platform.window.localStorage.getItem("ls_bridge_user")
            if raw:
                data = json.loads(str(raw))
                if isinstance(data, dict):
                    return data
        except Exception as e:
            print("[WebBridge] Lỗi đọc ls_bridge_user:", e)
        return None

    @staticmethod
    def post_message(data: Dict[str, Any]) -> None:
        """Gửi thông điệp tới Web Hub qua postMessage và lưu vào localStorage."""
        payload = json.dumps(data, ensure_ascii=False)
        if sys.platform == "emscripten":
            try:
                import platform

                platform.window.parent.postMessage(payload, "*")
            except Exception as e:
                print("[WebBridge] Lỗi postMessage:", e)
            try:
                import platform

                platform.window.localStorage.setItem("ls_match_result", payload)
            except Exception:
                pass
        else:
            pass

    @staticmethod
    def notify_gold(delta: int, total: int) -> None:
        """Thông báo cập nhật vàng theo thời gian thực tới Web Hub."""
        WebBridge.post_message({
            "type": "LS_GOLD_UPDATE",
            "goldDelta": int(delta),
            "totalGold": int(total),
        })

    @staticmethod
    def notify_match_end(
        mode: str,
        result: str,
        kills: int,
        time_survived: int,
        level: int,
        gold_earned: int,
        wave: int,
        total_gold: int,
    ) -> None:
        """Lưu kết quả trận đấu về MongoDB và Match History của Web Hub."""
        WebBridge.post_message({
            "type": "LS_MATCH_END",
            "mode": mode,
            "result": result,
            "kills": int(kills),
            "timeSurvived": int(time_survived),
            "levelReached": int(level),
            "goldEarned": int(gold_earned),
            "wave": int(wave),
            "totalGold": int(total_gold),
        })


from core import (
    ANIME_SKIN_BY_ID,
    ANIME_SKINS,
    C_BG,
    C_BOOMERANG,
    C_CYAN,
    C_GREEN,
    C_GRID,
    C_HP,
    C_HP_BG,
    C_ICE,
    C_LIGHTNING,
    C_ORANGE,
    C_PLAYER,
    C_PLAYER_DARK,
    C_PURPLE,
    C_RED,
    C_UI_BG,
    C_WHITE,
    C_XP,
    C_XP_BG,
    C_YELLOW,
    CHARACTER_DEFS,
    FPS,
    GameState,
    LANG,
    PERM_UPGRADE_DEFS,
    SAVE_FILE_PATH,
    SCREEN_H,
    SCREEN_W,
    STRINGS,
    TILE,
    WORLD_H,
    WORLD_W,
    AchievementDef,
    AchievementID,
    ACHIEVEMENT_DEFS,
    ACHIEVEMENT_TEXT_KEYS,
    QuestType,
    SaveData,
    CloudSaveSyncManager,
    SoundEngine,
    DynamicMusicDirector,
    Element,
    ElementalReaction,
    ElementalSynergyManager,
    T,
    draw_icon_coin,
    draw_icon_heart,
    draw_icon_magnet,
    draw_icon_shield,
    draw_icon_skull,
    draw_icon_star,
    draw_icon_sword,
    draw_wrapped_text,
    get_save_file_path,
    get_skin_cost,
    get_sys_font,
    get_vn_font,
    toggle_lang,
)
from entities import (
    Boss,
    Drone,
    Enemy,
    EnemyType,
    Player,
    SoulMinion,
    Turret,
    FlockingSeparation,
    KitingBehavior,
    ExploderChargeBehavior,
    SummonerOrbitBehavior,
    enemy_damage_multiplier,
    enemy_hp_multiplier,
    enemy_speed_multiplier,
)
from gfx import (
    AmbientParticle,
    ShockwaveRing,
    apply_hit_flash_mask,
    draw_additive_glow,
    draw_biome_props,
    draw_character_procedural_sprite,
    draw_jagged_lightning_arc,
    draw_magic_circle,
    get_arcane_tile_chunk,
    get_drop_shadow,
    get_player_glow_surface,
    get_slash_scratch_surf,
    get_vignette_surface,
)
from items import Chest, ChestDrop, ExpMagnet, GoldCoin, HealthPotion, XPGem
from pooling import (
    DamageNumberPool,
    ObjectPool,
    ParticlePool,
    PooledDamageNumber,
    PooledParticle,
    PooledProjectile,
    ProjectilePool,
)
from spatial import (
    SpatialHashGrid,
    angle_to,
    clamp,
    dist,
    dist_sq,
    dist_to_segment,
    in_radius_sq,
    norm,
)
from systems import (
    AchievementManager,
    GestureRecognizer,
    GestureType,
    Quest,
    QuestManager,
    SpawnManager,
    _Toast,
)
from ui import (
    Button,
    CampaignScreen,
    CharacterScreen,
    LobbyScreen,
    MainMenu,
    SettingsScreen,
    SkinShopScreen,
    Slider,
    UpgradeScreen,
    campaign_target_wave,
)
from weapons import (
    ActiveUltimate,
    AuraWeapon,
    BoomerangWeapon,
    DragonfireThrustWeapon,
    FamiliarWeapon,
    FireTrailWeapon,
    IceWandWeapon,
    JudgementHammerWeapon,
    LightningStaffWeapon,
    OrbWeapon,
    PhantomArrowWeapon,
    SkeletalLegionWeapon,
    UpgradeType,
    VoidSingularityWeapon,
    WhipWeapon,
    deal_player_damage,
    get_recipe_hint,
    get_upgrade_def,
)
from engine import Game

# SoundEngine mixer initialization guard reference:
# [SoundEngine] Mixer init deferred/skipped:

# Backward-compatibility aliases
Particle = PooledParticle
DamageNumber = PooledDamageNumber
Projectile = PooledProjectile


class _MainModule(sys.modules[__name__].__class__):
    @property
    def LANG(self):
        import core.i18n
        return core.i18n.LANG

    @LANG.setter
    def LANG(self, val):
        import core.i18n
        core.i18n.LANG = val


sys.modules[__name__].__class__ = _MainModule


# WebBridge synchronization hook reference:
# self._sync_web_bridge() applies web user equipped skin and self.admin_buffs


async def main():
    """Hàm khởi chạy chính của trò chơi, hỗ trợ cả Python Desktop và Pygbag (WebAssembly)."""
    game = Game()
    # Pygbag / WebAssembly cooperative async frame yield
    await asyncio.sleep(0)
    await game.run()


if __name__ == "__main__":
    asyncio.run(main())
