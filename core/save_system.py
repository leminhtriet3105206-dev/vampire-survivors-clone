"""Persistent save data system with atomic write safety and PyInstaller / WASM path handling."""
import json
import os
import sys
from typing import Dict, Optional, Set

from core.config import (
    ANIME_SKINS,
    CHARACTER_DEFS,
    AchievementID,
    IS_EMSCRIPTEN,
)
from spatial.math_utils import clamp


def get_save_file_path(filename: str = "save_data.json") -> str:
    """
    Determine safe persistent save path for Python source, Pygbag (Web), and PyInstaller (.exe).
    When frozen with PyInstaller (--onefile), __file__ points to the temporary _MEIxxxxxx folder.
    This resolves to sys.executable's directory with APPDATA fallback on permission error.
    """
    if sys.platform == "emscripten":
        return f"/tmp/{filename}"

    if getattr(sys, "frozen", False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    save_path = os.path.join(base_dir, filename)

    try:
        os.makedirs(base_dir, exist_ok=True)
        test_file = os.path.join(base_dir, f".write_test_{os.getpid()}.tmp")
        with open(test_file, "w") as f:
            f.write("ok")
        if os.path.exists(test_file):
            os.remove(test_file)
        return save_path
    except (OSError, PermissionError):
        if sys.platform == "win32":
            appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
        elif sys.platform == "darwin":
            appdata = os.path.expanduser("~/Library/Application Support")
        else:
            appdata = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
        fallback_dir = os.path.join(appdata, "VampireSurvivorsClone")
        try:
            os.makedirs(fallback_dir, exist_ok=True)
            return os.path.join(fallback_dir, filename)
        except Exception:
            return save_path


SAVE_FILE_PATH = get_save_file_path("save_data.json")


class SaveData:
    """
    Persistent game state:
      - Gold balances (total_gold, lifetime_gold)
      - Unlocked & selected character classes
      - Owned & equipped anime skins
      - Permanent stat upgrades (perm_upgrades)
      - High scores & Campaign progress
      - Unlocked achievements & Quest stats
    """

    def __init__(self, filepath: Optional[str] = None):
        self.filepath = filepath or get_save_file_path("save_data.json")
        self.total_gold: int = 0
        self.lifetime_gold: int = 0
        self.unlocked_ids: Set[str] = {"warrior"}
        self.selected_id: str = "warrior"
        self.owned_skins: Set[str] = {"default"}
        self.equipped_skin: str = "default"
        self.campaign_unlocked_level: int = 1
        self.unlocked_achievements: Set[AchievementID] = set()
        self.chest_opens: int = 0
        self.perm_upgrades: Dict[str, int] = {"hp": 0, "dmg": 0, "spd": 0, "gold": 0}
        self.high_scores: Dict[str, int] = {
            "best_kills": 0,
            "best_time": 0,
            "best_wave": 0,
            "best_level": 1,
        }
        self.class_perks: Dict[str, str] = {
            "warrior": "cuong_huyet",
            "mage": "hu_khong_rong",
            "rogue": "am_bo_than_toc",
            "paladin": "thanh_quang_ho_the",
            "necromancer": "bat_hon_doat_menh",
            "dragon_lancer": "no_long_xuat_the",
        }
        self.unlocked_perks: Set[str] = {
            "cuong_huyet",
            "hu_khong_rong",
            "am_bo_than_toc",
            "thanh_quang_ho_the",
            "bat_hon_doat_menh",
            "no_long_xuat_the",
        }
        self.consumables: Dict[str, int] = {
            "potion_hp": 2,
            "potion_dmg": 1,
            "potion_spd": 1,
            "potion_armor": 1,
            "potion_magnet": 1,
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

            self.campaign_unlocked_level = int(clamp(int(data.get("campaign_unlocked_level", 1)), 1, 30))
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
                    self.perm_upgrades[k] = int(clamp(int(pu.get(k, 0)), 0, 5))

            hs = data.get("high_scores", {})
            if isinstance(hs, dict):
                for k in self.high_scores:
                    self.high_scores[k] = max(0, int(hs.get(k, self.high_scores[k])))

            cp = data.get("class_perks", {})
            if isinstance(cp, dict):
                self.class_perks.update({str(k): str(v) for k, v in cp.items()})

            up = data.get("unlocked_perks", [])
            if isinstance(up, list):
                self.unlocked_perks.update({str(x) for x in up})

            con = data.get("consumables", {})
            if isinstance(con, dict):
                for k in self.consumables:
                    if k in con:
                        self.consumables[k] = max(0, int(con[k]))
            return True
        except Exception:
            return False

    def save(self) -> bool:
        try:
            folder = os.path.dirname(self.filepath)
            if folder:
                os.makedirs(folder, exist_ok=True)
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
                "class_perks": dict(self.class_perks),
                "unlocked_perks": sorted(list(self.unlocked_perks)),
                "consumables": dict(self.consumables),
            }
            tmp_path = f"{self.filepath}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.filepath)
            return True
        except Exception as e:
            print("[SaveData] Lỗi lưu dữ liệu:", e)
            return False

    def buy_consumable(self, item_key: str, cost: int) -> bool:
        if self.total_gold >= cost:
            self.total_gold -= cost
            self.consumables[item_key] = self.consumables.get(item_key, 0) + 1
            self.save()
            return True
        return False

    def use_consumable(self, item_key: str) -> bool:
        if self.consumables.get(item_key, 0) > 0:
            self.consumables[item_key] -= 1
            self.save()
            return True
        return False

    def unlock_perk(self, perk_id: str, cost: int) -> bool:
        if self.total_gold >= cost:
            self.total_gold -= cost
            self.unlocked_perks.add(perk_id)
            self.save()
            return True
        return False

    def equip_perk(self, char_id: str, perk_id: str):
        self.class_perks[char_id] = perk_id
        self.save()

    def record_match_stats(self, kills: int, elapsed_secs: int, wave: int, level: int):
        self.high_scores["best_kills"] = max(self.high_scores.get("best_kills", 0), int(kills))
        self.high_scores["best_time"] = max(self.high_scores.get("best_time", 0), int(elapsed_secs))
        self.high_scores["best_wave"] = max(self.high_scores.get("best_wave", 0), int(wave))
        self.high_scores["best_level"] = max(self.high_scores.get("best_level", 1), int(level))
        self.save()

    def unlock(self, char_id: str, cost: int) -> bool:
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

    def complete_campaign_level(self, level: int):
        if 1 <= level <= 30:
            self.campaign_unlocked_level = max(
                self.campaign_unlocked_level,
                min(30, level + 1),
            )
            self.save()


