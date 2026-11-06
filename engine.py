"""Game engine bootstrap, game loop, and subsystem orchestrator for Legendary Survival."""
import array
import asyncio
from enum import Enum, auto
import json
import math
import os
import random
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
import pygame
import audio_settings

# Core Configuration, Bridges, Audio, Localization
from core.config import (
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
    IS_EMSCRIPTEN,
    PERM_UPGRADE_DEFS,
    SCREEN_H,
    SCREEN_W,
    TILE,
    WORLD_H,
    WORLD_W,
    draw_icon_coin,
    draw_icon_heart,
    draw_icon_magnet,
    draw_icon_shield,
    draw_icon_skull,
    draw_icon_star,
    draw_icon_sword,
    draw_wrapped_text,
    get_skin_cost,
    get_sys_font,
    get_vn_font,
)
from core.audio import SoundEngine
from core.i18n import LANG, STRINGS, T, toggle_lang
from core.save_system import SaveData, get_save_file_path, SAVE_FILE_PATH
from core.cloud_save import CloudSaveSyncManager
from core.web_bridge import WebBridge

# Spatial Hashing and Math
from spatial.math_utils import (
    angle_to,
    clamp,
    dist,
    dist_sq,
    dist_to_segment,
    in_radius_sq,
    lerp,
    norm,
)
from spatial.spatial_grid import SpatialHashGrid

# Object Pooling
from pooling.damage_number_pool import (
    DamageNumberPool,
    PooledDamageNumber,
    get_cached_damage_surfaces,
)
from pooling.particle_pool import ParticlePool, PooledParticle
from pooling.projectile_pool import ProjectilePool, PooledProjectile

# Graphics and Visual Effects
from gfx.biome_renderer import (
    apply_hit_flash_mask,
    draw_biome_props,
    get_arcane_tile_chunk,
    get_drop_shadow,
    get_player_glow_surface,
    get_slash_scratch_surf,
    get_vignette_surface,
)
from gfx.sprite_cache import (
    _ENEMY_FLASH_CACHE,
    _ENEMY_SPRITE_CACHE,
    draw_character_procedural_sprite,
    get_skin_vfx_colors,
)
from gfx.vfx import (
    AmbientParticle,
    ShockwaveRing,
    draw_additive_glow,
    draw_jagged_lightning_arc,
    draw_magic_circle,
)

# Entities
from entities.boss import Boss
from entities.companions import Drone, SoulMinion, Turret
from entities.enemy import (
    Enemy,
    EnemyType,
    enemy_damage_multiplier,
    enemy_hp_multiplier,
    enemy_speed_multiplier,
)
from entities.player import Player

# Weapons, Skills, and Ultimates
from weapons.all_weapons import (
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
    VoidSingularityWeapon,
    WhipWeapon,
)
from weapons.ultimates import ActiveUltimate
from weapons.upgrades import UpgradeType, get_recipe_hint, get_upgrade_def
from weapons.weapon_base import deal_player_damage

# Items and Drops
from items.chest import Chest, ChestDrop
from items.consumables import ExpMagnet, HealthPotion
from items.drops import GoldCoin, XPGem

# Systems
from systems.achievement_system import AchievementManager, _Toast
from systems.gesture_recognition import GestureRecognizer, GestureType
from systems.quest_system import Quest, QuestManager, QuestType, draw_collapse_arrow
from systems.spawn_manager import SpawnManager

# UI
from ui.screens import (
    CampaignScreen,
    CharacterScreen,
    LobbyScreen,
    MainMenu,
    SettingsScreen,
    SkinShopScreen,
    campaign_target_wave,
)
from ui.widgets import Button, Slider
from ui.upgrade_screen import UpgradeScreen

# Aliases for zero-allocation pooling
Particle = PooledParticle
DamageNumber = PooledDamageNumber
Projectile = PooledProjectile

# Boss spawn aralığı (saniye)
BOSS_INTERVAL = 120   # 2 dakikada bir boss

class Game:
    def __init__(self):
        global _last_non_en
        _last_non_en = "VI"
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption("Legendary Survival")
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
        self.char_return   = GameState.MENU
        self.skin_shop_scr = SkinShopScreen(self.save, self.sfx)
        self.skin_shop_return = GameState.MENU
        self.lobby_scr     = LobbyScreen(self.save, self.sfx)
        self._consumable_rects: List[pygame.Rect] = []
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
        self.controls_panel = pygame.Rect(0, 0, 580, 440)
        self.controls_panel.center = (SCREEN_W // 2, SCREEN_H // 2)
        self.btn_controls_close = Button(self.controls_panel.centerx - 80,
                                         self.controls_panel.bottom - 60, 160, 44,
                                         T("close"), self.font_med)

        # Tùy chọn trong Menu Tạm Dừng (Pause Menu)
        self.shake_enabled = True
        self.vfx_high      = True
        self.biome_id      = 0
        self.pause_sel_idx = 0
        self.pause_settings_open = False

        # Cầu nối Web Hub (WebBridge) & Cloud Save Sync & Computer Vision Gestures
        self.admin_buffs = {}
        self.web_username = "Survivor"
        self.cloud_sync = CloudSaveSyncManager()
        self.gesture_rec = GestureRecognizer(enabled=False)
        self._sync_web_bridge()

        # Spatial Partitioning and Object Pools for 1000+ Concurrent Entities
        self.spatial_grid = SpatialHashGrid(cell_size=120)
        self.particle_pool = ParticlePool(initial_capacity=1000)
        self.damage_pool = DamageNumberPool(initial_capacity=300)
        self.projectile_pool = ProjectilePool(initial_capacity=500)

        self.reset()

    def _sync_web_bridge(self):
        """Đồng bộ thông tin người chơi, trang phục và Admin Buffs từ Web Hub."""
        user = WebBridge.get_user()
        if not user:
            return
        self.web_username = str(user.get("username", "Survivor"))
        if "gold" in user:
            self.save.total_gold = max(0, int(user["gold"]))
        eq_skin = user.get("equippedSkin")
        if eq_skin:
            mapped_skin = self._map_web_skin_slug(eq_skin)
            self.save.owned_skins.add(mapped_skin)
            self.save.equipped_skin = mapped_skin
        self.admin_buffs = user.get("adminBuffs", {})

    def _map_web_skin_slug(self, slug: str) -> str:
        """Chuyển đổi slug trang phục của Web Hub thành ID trang phục Pygame."""
        s = str(slug).lower().strip()
        slug_map = {
            "golden-saiyan": "saiyan",
            "saiyan": "saiyan",
            "shadow-shinobi": "naruto",
            "naruto": "naruto",
            "infinity-sorcerer": "gojo",
            "gojo": "gojo",
            "rubber-pirate-king": "luffy",
            "luffy": "luffy",
            "flame-slayer": "flame",
            "thunder-hunter": "thunder",
            "soul-reaper": "reaper",
            "titan-scout": "titan",
            "default": "default",
        }
        return slug_map.get(s, s if s in ANIME_SKIN_BY_ID else "default")

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
            ("skeletal_level",   p.skeletal_legion),
            ("dragon_level",     p.dragonfire_thrust),
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

        # Áp dụng Thiên Phú Đặc Quyền Hệ Phái (Class Perks từ Sảnh Chờ / save_data.json)
        active_perk = self.save.class_perks.get(cdef["id"], "")
        p.active_perk = active_perk
        if active_perk == "cuong_huyet":
            p.perk_cuong_huyet = True
        elif active_perk == "kiem_khi_rong":
            p.whip.range += 55
        elif active_perk == "bat_khuat":
            p.armor += 4
            p.recovery += 1
        elif active_perk == "hu_khong_rong":
            p.void_singularity.pull_radius += 45
        elif active_perk == "khai_phong_tinh_van":
            p.speed_mult += 0.15
            p.cdr += 0.10
        elif active_perk == "am_bo_than_toc":
            p.speed_mult += 0.20
            p.crit_chance += 0.15
        elif active_perk == "mua_ten_doc_hoan":
            p.phantom_arrow.bounces += 2
        elif active_perk == "bay_hac_am":
            p.damage_mult += 0.15
        elif active_perk == "thanh_quang_ho_the":
            p.max_hp += 60
            p.hp += 60
        elif active_perk == "khien_than_bat_hoai":
            p.armor += 6
        elif active_perk == "no_long_xuat_the":
            p.dragonfire_thrust.damage += 12
        elif active_perk == "long_lan_ho_the":
            p.perk_damage_reduction = 0.15

        # Áp dụng Admin GM Buffs từ Web Hub
        if hasattr(self, "admin_buffs") and isinstance(self.admin_buffs, dict):
            bonus_hp = int(self.admin_buffs.get("bonusHp", 0))
            bonus_dmg = int(self.admin_buffs.get("bonusDamage", 0))
            if bonus_hp > 0:
                p.max_hp += bonus_hp
                p.hp += bonus_hp
            if bonus_dmg > 0:
                p.damage_mult += bonus_dmg / 100.0

    # -----------------------------------------------------------------------
    def reset(self):
        self._sync_web_bridge()
        cdef = next((c for c in CHARACTER_DEFS if c["id"] == self.save.selected_id), CHARACTER_DEFS[0])
        self.player       = Player(WORLD_W // 2, WORLD_H // 2,
                                   character_id=cdef["id"], color=cdef["color"],
                                   skin_id=self.save.equipped_skin)
        self._apply_char_mods()

        self.enemies:       List[Enemy]       = []
        self.bosses:        List[Boss]        = []
        self.spatial_grid.clear()
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
        self.magnet_drop_cd = 0
        self.active_ultimates: List[ActiveUltimate] = []

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
        """Lưu toàn bộ vàng thu thập được và kỷ lục trận đấu vào save_data.json và Web Hub."""
        earned_gold = self.session_gold
        if self.session_gold > 0:
            self.save.total_gold += self.session_gold
            self.save.lifetime_gold += self.session_gold
            self.session_gold = 0
        if self.tick > 0:
            time_survived = self.tick // FPS
            wave_num = self.spawn_mgr.wave + 1
            level_num = self.player.level
            kills_num = self.kills
            result_str = "defeat" if self.game_over else ("victory" if self.level_completed else "completed")
            self.save.record_match_stats(
                kills_num,
                time_survived,
                wave_num,
                level_num,
            )
            WebBridge.notify_match_end(
                mode="solo",
                result=result_str,
                kills=kills_num,
                time_survived=time_survived,
                level=level_num,
                gold_earned=earned_gold,
                wave=wave_num,
                total_gold=self.save.total_gold,
            )
            if hasattr(self, "cloud_sync"):
                self.cloud_sync.sync(self.save, gold_earned=earned_gold)
        else:
            self.save.save()
            if hasattr(self, "cloud_sync"):
                self.cloud_sync.sync(self.save, gold_earned=0)

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
        self.lobby_scr = LobbyScreen(self.save, self.sfx)
        self.sfx.play_menu_bgm()

    def _go_lobby(self):
        self.state = GameState.LOBBY
        self.lobby_scr = LobbyScreen(self.save, self.sfx)
        self.sfx.play_menu_bgm()

    def _go_settings(self):
        self.state = GameState.SETTINGS
        self.settings_scr.refresh_labels()

    def _go_campaign(self):
        self.state = GameState.CAMPAIGN
        self.campaign_scr.refresh_labels()

    def _go_chars(self, return_to=GameState.MENU):
        self.char_return = return_to
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
        self.sfx.play_battle_bgm()

    def _use_consumable_slot(self, slot_idx: int) -> bool:
        """Kích hoạt vật phẩm tác chiến từ ô phím tắt [1]-[5] hoặc nhấp chuột."""
        p = self.player
        if slot_idx == 0:  # potion_hp
            if self.save.use_consumable("potion_hp"):
                heal = min(80, p.max_hp - p.hp)
                p.hp += heal
                p.heal_aura_timer = 40
                if self.sfx: self.sfx.play_chime()
                self.damage_numbers.append(DamageNumber(p.x, p.y - 28, f"+{heal or 80} HP", (80, 255, 130), scale=1.35, life=50))
                return True
        elif slot_idx == 1:  # potion_dmg
            if self.save.use_consumable("potion_dmg"):
                p.potion_rage_timer = 600
                if self.sfx: self.sfx.play_awakened()
                self.shockwaves.append(ShockwaveRing(p.x, p.y, (255, 60, 70), max_radius=160, duration=28, width=5))
                self.damage_numbers.append(DamageNumber(p.x, p.y - 28, "CUỒNG NỘ! (+60% DMG)", (255, 70, 70), scale=1.3, life=55))
                return True
        elif slot_idx == 2:  # potion_spd
            if self.save.use_consumable("potion_spd"):
                p.potion_speed_timer = 480
                if self.sfx: self.sfx.play_whoosh()
                self.shockwaves.append(ShockwaveRing(p.x, p.y, (60, 220, 255), max_radius=140, duration=24, width=4))
                self.damage_numbers.append(DamageNumber(p.x, p.y - 28, "THẦN TỐC! (+60% SPD)", (60, 220, 255), scale=1.3, life=55))
                return True
        elif slot_idx == 3:  # potion_armor
            if self.save.use_consumable("potion_armor"):
                p.potion_armor_timer = 360
                p.invincible = max(p.invincible, 360)
                if self.sfx: self.sfx.play_awakened()
                self.shockwaves.append(ShockwaveRing(p.x, p.y, (255, 215, 80), max_radius=150, duration=26, width=5))
                self.damage_numbers.append(DamageNumber(p.x, p.y - 28, "BẤT TỬ! (6 GIÂY)", (255, 225, 90), scale=1.3, life=55))
                return True
        elif slot_idx == 4:  # potion_magnet
            if self.save.use_consumable("potion_magnet"):
                for gem in self.xp_gems:
                    gem.magnetized = True
                for coin in self.gold_coins:
                    coin.magnetized = True
                if self.sfx: self.sfx.play_coin()
                self.shockwaves.append(ShockwaveRing(p.x, p.y, (190, 90, 255), max_radius=320, duration=35, width=6))
                self.damage_numbers.append(DamageNumber(p.x, p.y - 28, "TỪ TRƯỜNG TOÀN BẢN ĐỒ!", (210, 120, 255), scale=1.3, life=55))
                return True
        return False

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
    async def run(self):
        while True:
            self.clock.tick(FPS)
            await asyncio.sleep(0)
            raw = pygame.event.get()

            for ev in raw:
                if ev.type == pygame.QUIT:
                    self._flush_session_save()
                    self.sfx.save_volumes()
                    pygame.quit(); sys.exit()

            # ── MENU ───────────────────────────────────────────────────────
            if self.state == GameState.MENU:
                action = self.main_menu.handle_events(raw)
                if   action == "play":     self._go_lobby()
                elif action == "campaign": self._go_campaign()
                elif action == "chars":    self._go_chars(GameState.MENU)
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

            # ── LOBBY ──────────────────────────────────────────────────────
            elif self.state == GameState.LOBBY:
                action = self.lobby_scr.handle_events(raw)
                if action == "launch":
                    self._go_playing()
                elif action == "back":
                    self._go_menu()
                elif action == "chars":
                    self._go_chars(GameState.LOBBY)
                elif action == "skins":
                    self._go_skins(GameState.LOBBY)
                else:
                    for ev in raw:
                        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_l:
                            toggle_lang()
                    self.lobby_scr.draw(self.screen)

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
                if action == "back":
                    if self.char_return == GameState.LOBBY:
                        self._go_lobby()
                    else:
                        self._go_menu()
                elif action == "skins":
                    self._go_skins(GameState.CHARACTERS)
                else:
                    self.char_scr.draw(self.screen)

            # ── SKIN SHOP ──────────────────────────────────────────────────
            elif self.state == GameState.SKIN_SHOP:
                action = self.skin_shop_scr.handle_events(raw)
                if action == "back":
                    if self.skin_shop_return == GameState.CHARACTERS:
                        self._go_chars(self.char_return)
                    elif self.skin_shop_return == GameState.LOBBY:
                        self._go_lobby()
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
                            and not self.upgrade_screen and not self.game_over and not self.paused):
                        for s_idx, cr in enumerate(self._consumable_rects):
                            if cr.collidepoint(ev.pos):
                                self._use_consumable_slot(s_idx)
                                break
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
                        # Phím tắt dùng Vật Phẩm Tác Chiến [1]-[5] khi đang chiến đấu (tránh xung đột khi chọn thẻ nâng cấp)
                        if not self.upgrade_screen and not self.game_over and not self.paused:
                            if ev.key in (pygame.K_1, pygame.K_KP1):
                                self._use_consumable_slot(0)
                            elif ev.key in (pygame.K_2, pygame.K_KP2):
                                self._use_consumable_slot(1)
                            elif ev.key in (pygame.K_3, pygame.K_KP3):
                                self._use_consumable_slot(2)
                            elif ev.key in (pygame.K_4, pygame.K_KP4):
                                self._use_consumable_slot(3)
                            elif ev.key in (pygame.K_5, pygame.K_KP5):
                                self._use_consumable_slot(4)

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
                        elif ev.key in (pygame.K_r, pygame.K_q) and not self.upgrade_screen and not self.game_over and not self.paused:
                            self._trigger_ultimate()
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

            # Nhường quyền cho Browser Event Loop (Pygbag WebAssembly 60 FPS)
            await asyncio.sleep(0)

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
                DamageNumber(p.x, p.y - 58, f"[HỢP NHẤT] {title_str.upper()}", (255, 225, 65), scale=1.3))
        elif awakened_now:
            self.damage_numbers.append(
                DamageNumber(p.x, p.y - 54, f"[THỨC TỈNH] {title_str.upper()}", (255, 225, 80), scale=1.2))
        else:
            self.damage_numbers.append(
                DamageNumber(p.x, p.y - 44, f"[+] {title_str}{lv_suffix}", burst_col))

        p.squash_timer = 10
        self.screen_flash_alpha = 155 if fused_now else (130 if awakened_now else 80)
        self.screen_shake = 18 if fused_now else (14 if awakened_now else 7)

    # -----------------------------------------------------------------------
    def _trigger_ultimate(self):
        """Kích hoạt Kỹ Năng Tối Thượng tương ứng với Hệ Phái khi thanh nạp đạt 100%."""
        p = self.player
        if p.ult_charge < p.ult_max:
            return
        p.ult_charge = 0.0
        self.screen_shake = 20
        self.screen_flash_alpha = 185
        self.sfx.play_awakened()
        ult = ActiveUltimate(p.character_id, p, self.spawn_mgr.wave)
        self.active_ultimates.append(ult)
        title_map = {
            "warrior": "TRẢM HUYẾT NGUYỆT LIÊN HOÀN",
            "mage": "THIÊN THẠCH HƯ KHÔNG",
            "rogue": "TIỄN ẢNH BÓNG ĐÊM",
            "paladin": "THÁNH QUANG BẢO HỘ",
            "necromancer": "THỦY TRIỀU TỬ LINH",
            "dragon_lancer": "HƠI THỞ THÁNH LONG",
        }
        ult_name = title_map.get(p.character_id, "KỸ NĂNG TỐI THƯỢNG")
        self.damage_numbers.append(
            DamageNumber(p.x, p.y - 65, f"[ULT] {ult_name}!", (255, 230, 80), scale=1.35))

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

        # Dynamic procedural BGM intensity scaling
        if hasattr(self.sfx, "dynamic_music"):
            self.sfx.dynamic_music.update(
                enemy_count=len(self.enemies),
                boss_count=len(self.bosses),
                player_hp_pct=(p.hp / max(1, p.max_hp)),
            )

        # Computer Vision & Webcam Gesture Input (Phase 4)
        if hasattr(self, "gesture_rec") and self.gesture_rec.enabled:
            gesture = self.gesture_rec.poll_gesture()
            if gesture == GestureType.OPEN_PALM:
                self._trigger_ultimate()
            elif gesture == GestureType.CLOSED_FIST:
                self._use_consumable_slot(0)  # Potion HP
            elif gesture == GestureType.PEACE_SIGN:
                self._use_consumable_slot(2)  # Potion Speed Dash

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
        if self.magnet_drop_cd > 0:
            self.magnet_drop_cd -= 1

        # Cập nhật Spatial Hash Grid cho O(1) va chạm siêu tốc
        self.spatial_grid.clear()
        self.spatial_grid.insert_many(self.enemies)
        if self.bosses:
            self.spatial_grid.insert_many(self.bosses)

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
        p.skeletal_legion.update(p, all_enemies, self.particles, self.damage_numbers, self.sfx)
        p.dragonfire_thrust.update(p, all_enemies, self.particles, self.damage_numbers, p.fire_trail, self.sfx)

        # Cập nhật các Kỹ Năng Tối Thượng (Active Ultimates)
        time_slowed = any(u.char_id == "rogue" and u.alive for u in self.active_ultimates)
        for ult in self.active_ultimates:
            ult.update(self.enemies, self.bosses, self.particles, self.damage_numbers, self.shockwaves, self.sfx, p)
        self.active_ultimates = [u for u in self.active_ultimates if u.alive]

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
                pr_x, pr_y, pr_sz = proj.x, proj.y, proj.size
                candidates = self.spatial_grid.query_radius(pr_x, pr_y, pr_sz + 40, exact=False)
                for e in candidates:
                    if getattr(e, "alive", True) and id(e) not in proj.hit_set:
                        max_d = pr_sz + e.radius
                        dx = e.x - pr_x
                        if dx > max_d or dx < -max_d:
                            continue
                        dy = e.y - pr_y
                        if dy > max_d or dy < -max_d:
                            continue
                        if dx * dx + dy * dy < max_d * max_d:
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

        # Cập nhật kẻ địch thường (Chịu hiệu ứng làm chậm 75% khi kích hoạt Tối Thượng Thợ Săn Bóng Đêm)
        new_ep = []
        summoned_enemies = []
        all_enemies = self.enemies
        for e in self.enemies:
            if time_slowed and self.tick % 4 != 0:
                continue
            e.update(
                p,
                new_ep,
                summoned_enemies,
                spatial_grid=self.spatial_grid,
                all_enemies=all_enemies,
                particles=self.particles,
                damage_numbers=self.damage_numbers,
                shockwaves=self.shockwaves,
                sfx=self.sfx,
            )
        self.enemy_projs.extend(new_ep)
        self.enemies.extend(summoned_enemies)

        # Cập nhật Boss
        boss_ep = []
        for b in self.bosses:
            if time_slowed and self.tick % 4 != 0:
                continue
            b.update(p, boss_ep)
        self.enemy_projs.extend(boss_ep)

        # Đạn kẻ địch
        px, py, pr = p.x, p.y, p.radius
        for proj in self.enemy_projs:
            proj.update()
            if proj.alive:
                max_d = pr + proj.size
                dx = px - proj.x
                if dx > max_d or dx < -max_d:
                    continue
                dy = py - proj.y
                if dy > max_d or dy < -max_d:
                    continue
                if dx * dx + dy * dy < max_d * max_d:
                    p.take_damage(proj.damage)
                    self.sfx.play_damage()
                    for _ in range(4):
                        self.particles.append(Particle(proj.x, proj.y, C_RED, speed=3))
                    proj.alive = False

        # Va chạm cận chiến (kẻ địch + boss)
        for e in self.enemies:
            if e.alive:
                max_d = e.radius + pr
                dx = e.x - px
                if dx > max_d or dx < -max_d:
                    continue
                dy = e.y - py
                if dy > max_d or dy < -max_d:
                    continue
                if dx * dx + dy * dy < max_d * max_d:
                    p.take_damage(e.damage)
                    self.sfx.play_damage()
        for b in self.bosses:
            if b.alive:
                max_d = b.radius + pr
                dx = b.x - px
                if dx > max_d or dx < -max_d:
                    continue
                dy = b.y - py
                if dy > max_d or dy < -max_d:
                    continue
                if dx * dx + dy * dy < max_d * max_d:
                    p.take_damage(b.damage)
                    self.sfx.play_damage()

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
        gold_gained = 0
        for coin in self.gold_coins:
            v = coin.update(p)
            if v:
                self.session_gold += v
                gold_gained += v
                coin_picked = True
        if coin_picked:
            self.sfx.play_coin()
            WebBridge.notify_gold(gold_gained, self.save.total_gold + self.session_gold)

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
                WebBridge.notify_gold(amt, self.save.total_gold + self.session_gold)
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
            # Nạp thanh Kỹ Năng Tối Thượng (+2.2% mỗi mạng hạ gục)
            p.charge_ult(2.2)
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
            # Rơi Vật Phẩm Chiến Trường (Đã cân bằng lại tỉ lệ và giới hạn trên bản đồ):
            # Giới hạn: Tối đa 3 Bình Máu và 1 Nam Châm cùng lúc trên bản đồ.
            potion_count = sum(1 for it in self.items if isinstance(it, HealthPotion) and it.alive)
            magnet_count = sum(1 for it in self.items if isinstance(it, ExpMagnet) and it.alive)
            if e.etype == EnemyType.TANK:
                # Quái Tinh Anh (TANK): 18% rơi Bình Máu nếu chưa đạt giới hạn 3 bình
                if potion_count < 3 and random.random() < 0.18:
                    self.items.append(HealthPotion(e.x + random.uniform(-10, 10), e.y + random.uniform(-10, 10)))
                    potion_count += 1
            else:
                # Quái thường: 0.8% rơi Bình Máu (0.5% - 1%)
                if potion_count < 3 and random.random() < 0.008:
                    self.items.append(HealthPotion(e.x + random.uniform(-10, 10), e.y + random.uniform(-10, 10)))
                    potion_count += 1
                # Quái thường: 0.15% rơi Nam Châm (0.1% - 0.2%), yêu cầu hồi chiêu 15s (900 ticks)
                elif magnet_count < 1 and self.magnet_drop_cd <= 0 and random.random() < 0.0015:
                    self.items.append(ExpMagnet(e.x + random.uniform(-10, 10), e.y + random.uniform(-10, 10)))
                    self.magnet_drop_cd = 15 * FPS
                    magnet_count += 1
            for _ in range(8 if self.vfx_high else 4):
                self.particles.append(Particle(e.x, e.y, e.color, speed=3, life=40))

        # ── Xử lý Boss bị tiêu diệt ─────────────────────────────────────
        dead_bosses = [b for b in self.bosses if not b.alive]
        for b in dead_bosses:
            self.kills += 1
            self.sfx.play_death()
            # Nạp lượng lớn thanh Kỹ Năng Tối Thượng (+25%)
            p.charge_ult(25.0)
            self.ach_mgr.notify_boss_kill()
            self.xp_gems.append(XPGem(b.x, b.y, b.XP_REWARD))
            for _ in range(10):
                val = random.randint(10, 22)
                self.gold_coins.append(GoldCoin(
                    b.x + random.uniform(-45, 45),
                    b.y + random.uniform(-45, 45), val))
            # Boss rơi Bình Máu (nếu dưới giới hạn 3 bình) và Nam Châm (nếu chưa có trên bản đồ)
            potion_count = sum(1 for it in self.items if isinstance(it, HealthPotion) and it.alive)
            magnet_count = sum(1 for it in self.items if isinstance(it, ExpMagnet) and it.alive)
            if potion_count < 3:
                self.items.append(HealthPotion(b.x - 20, b.y))
            if magnet_count < 1:
                self.items.append(ExpMagnet(b.x + 20, b.y))
                self.magnet_drop_cd = 15 * FPS
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
        max_dn = 80 if self.vfx_high else 45
        if len(self.damage_numbers) > max_dn:
            self.damage_numbers = self.damage_numbers[-max_dn:]

        self.xp_gems        = [g  for g  in self.xp_gems        if g.alive]
        if len(self.xp_gems) > 300:
            self.xp_gems.sort(key=lambda g: abs(g.x - p.x) + abs(g.y - p.y))
            while len(self.xp_gems) > 250:
                g_far = self.xp_gems.pop()
                if self.xp_gems:
                    self.xp_gems[-1].value += g_far.value

        self.gold_coins     = [c  for c  in self.gold_coins     if c.alive]
        if len(self.gold_coins) > 250:
            self.gold_coins.sort(key=lambda c: abs(c.x - p.x) + abs(c.y - p.y))
            while len(self.gold_coins) > 200:
                c_far = self.gold_coins.pop()
                if self.gold_coins:
                    self.gold_coins[-1].value += c_far.value

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
                WebBridge.notify_gold(reward, self.save.total_gold + self.session_gold)

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
        self.player.dragonfire_thrust.draw(surf, cx, cy)
        self.player.skeletal_legion.draw(surf, cx, cy, self.tick)
        for ult in self.active_ultimates:
            ult.draw(surf, cx, cy, self.tick)

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
        glow_s = get_player_glow_surface(self.player.color, glow_r)
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
            bt_s = self.font_bar.render(f"[BOSS] {b_title}: {b.hp}/{b.max_hp}", True, C_WHITE)
            surf.blit(bt_s, bt_s.get_rect(center=(SCREEN_W // 2, bby + bh // 2)))

        # Thanh nạp Kỹ Năng Tối Thượng (Ultimate Gauge) ở đáy màn hình
        ult_w, ult_h = 240, 18
        ult_x = SCREEN_W // 2 - ult_w // 2
        ult_y = SCREEN_H - 72
        pygame.draw.rect(surf, (15, 12, 26), (ult_x - 2, ult_y - 2, ult_w + 4, ult_h + 4), border_radius=6)
        pygame.draw.rect(surf, (36, 30, 56), (ult_x, ult_y, ult_w, ult_h), border_radius=5)
        ult_fill = int(ult_w * min(1.0, p.ult_charge / p.ult_max))

        if p.ult_charge >= p.ult_max:
            pulse = 0.75 + 0.25 * math.sin(self.tick * 0.18)
            glow_c = (int(255 * pulse), int(215 * pulse), int(60 * pulse))
            pygame.draw.rect(surf, glow_c, (ult_x, ult_y, ult_fill, ult_h), border_radius=5)
            pygame.draw.rect(surf, (255, 245, 160), (ult_x - 2, ult_y - 2, ult_w + 4, ult_h + 4), 2, border_radius=6)
            txt_col = C_WHITE if (self.tick // 14) % 2 == 0 else (255, 230, 80)
            ult_lbl = self.font_bar.render("SẴN SÀNG [PHÍM R]", True, txt_col)
            surf.blit(ult_lbl, ult_lbl.get_rect(center=(SCREEN_W // 2, ult_y + ult_h // 2)))
        else:
            pygame.draw.rect(surf, (85, 110, 240), (ult_x, ult_y, ult_fill, ult_h), border_radius=5)
            pygame.draw.rect(surf, (110, 95, 180), (ult_x - 2, ult_y - 2, ult_w + 4, ult_h + 4), 1, border_radius=6)
            ult_lbl = self.font_bar.render(f"[R] NẠP: {int(p.ult_charge)}%", True, (230, 230, 255))
            surf.blit(ult_lbl, ult_lbl.get_rect(center=(SCREEN_W // 2, ult_y + ult_h // 2)))

        # Thanh Vật Phẩm Tác Chiến Chiến Đấu (Tactical Consumables Quickbar)
        bar_x = SCREEN_W // 2 - 142
        bar_y = SCREEN_H - 114
        slot_w, slot_h = 52, 36
        gap = 6
        self._consumable_rects = []
        c_items = [
            ("potion_hp", "[1]", "HP", (80, 240, 120), p.heal_aura_timer > 0),
            ("potion_dmg", "[2]", "DMG", (255, 75, 80), p.potion_rage_timer > 0),
            ("potion_spd", "[3]", "SPD", (65, 215, 255), p.potion_speed_timer > 0),
            ("potion_armor", "[4]", "DEF", (255, 215, 70), p.potion_armor_timer > 0),
            ("potion_magnet", "[5]", "MAG", (190, 110, 255), False),
        ]
        for idx, (cid_key, key_lbl, name_lbl, col, is_buff_active) in enumerate(c_items):
            rx = bar_x + idx * (slot_w + gap)
            r = pygame.Rect(rx, bar_y, slot_w, slot_h)
            self._consumable_rects.append(r)
            qty = self.save.consumables.get(cid_key, 0)

            # Nền slot
            bg_col = (55, 18, 28, 220) if is_buff_active else ((22, 20, 38, 205) if qty > 0 else (14, 12, 22, 160))
            slot_s = pygame.Surface(r.size, pygame.SRCALPHA)
            slot_s.fill(bg_col)
            surf.blit(slot_s, r.topleft)

            # Viền slot
            border_c = (255, 230, 90) if is_buff_active else (col if qty > 0 else (65, 60, 90))
            border_w = 2 if (is_buff_active or qty > 0) else 1
            pygame.draw.rect(surf, border_c, r, border_w, border_radius=6)

            # Phím tắt [1]-[5]
            k_txt = self.font_bar.render(key_lbl, True, (240, 235, 255) if qty > 0 else (120, 115, 140))
            surf.blit(k_txt, (r.x + 3, r.y + 2))

            # Nhãn loại vật phẩm (HP, DMG, ...)
            n_txt = self.font_bar.render(name_lbl, True, col if qty > 0 else (130, 125, 150))
            surf.blit(n_txt, (r.x + slot_w - n_txt.get_width() - 4, r.y + 2))

            # Số lượng xN
            q_col = (255, 225, 80) if qty > 0 else (110, 105, 130)
            q_txt = self.font_bar.render(f"x{qty}", True, q_col)
            surf.blit(q_txt, (r.x + slot_w - q_txt.get_width() - 4, r.y + slot_h - q_txt.get_height() - 2))

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
                return "[HỢP NHẤT]"
            return "[MAX]" if getattr(w, "awakened", False) else f"Lv{w.level}/5"

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
            (T("wpn_skeletal"),   p.skeletal_legion),
            (T("wpn_dragon"),     p.dragonfire_thrust),
        ]
        # Chỉ hiển thị các kỹ năng đã mở khóa (level >= 1 hoặc đã hợp nhất)
        rows = [(lbl, _fmt_lv(w)) for lbl, w in all_skills if w.level >= 1 or getattr(w, "fused", False)]
        rows.append((T("wpn_armor"), f"{p.armor}"))
        rows.append((T("wpn_regen"), f"{p.recovery}"))

        PANEL_W  = 255
        ROW_H    = 20
        PAD      = 8
        panel_h  = 26 if self.weapons_collapsed else 24 + len(rows) * ROW_H + PAD

        px = SCREEN_W - PANEL_W - 15
        py = 104 if self.campaign_mode else 80
        self._weapons_toggle_rect = pygame.Rect(px + PANEL_W - 28, py + 2, 24, 20)

        panel_s = pygame.Surface((PANEL_W, panel_h), pygame.SRCALPHA)
        panel_s.fill((16, 14, 30, 195))
        surf.blit(panel_s, (px, py))
        pygame.draw.rect(surf, (85, 75, 145), (px, py, PANEL_W, panel_h), 1, border_radius=6)

        title_s = self._wpn_font_title.render(T("weapons_title"), True, (190, 175, 255))
        surf.blit(title_s, (px + PAD, py + 4))
        draw_collapse_arrow(surf, self._weapons_toggle_rect, self.weapons_collapsed,
                            self._weapons_toggle_rect.collidepoint(pygame.mouse.get_pos()))
        if self.weapons_collapsed:
            return

        for i, (label, value_str) in enumerate(rows):
            ry = py + 24 + i * ROW_H
            lbl_s = self._wpn_font_row.render(str(label), True, (215, 210, 245))
            surf.blit(lbl_s, (px + PAD, ry))
            v_col = (255, 85, 95) if "HỢP NHẤT" in value_str else ((255, 190, 60) if "[MAX]" in value_str else C_YELLOW)
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
            (T("wpn_skeletal"),   p.skeletal_legion,  (40, 230, 185)),
            (T("wpn_dragon"),     p.dragonfire_thrust, (255, 105, 30)),
        ]
        active_sk = [(n, w, c) for n, w, c in skill_items if w.level >= 1 or getattr(w, "fused", False)]
        sy = left_r.y + 138
        for s_name, w, s_col in active_sk[:7]:
            pygame.draw.circle(surf, s_col, (left_r.x + 26, sy + 9), 6)
            pygame.draw.circle(surf, C_WHITE, (left_r.x + 26, sy + 9), 6, 1)
            tag = "[HỢP NHẤT]" if getattr(w, "fused", False) else ("[THỨC TỈNH]" if w.awakened else f"Lv.{w.level}/5")
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
            prefix = "> " if sel else ""
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

        rows = ["ctl_move", "ctl_ult", "ctl_items", "ctl_pause", "ctl_lang", "ctl_sound",
                "ctl_upgrade", "ctl_restart", "ctl_menu"]
        ry = panel.y + 68
        for key in rows:
            keys_txt, desc = T(key)
            k_s = self.font_sm.render(keys_txt, True, (180, 160, 255))
            d_s = self.font_sm.render(desc, True, (200, 195, 240))
            surf.blit(k_s, (panel.x + 32, ry))
            surf.blit(d_s, (panel.x + 230, ry))
            ry += 28

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
