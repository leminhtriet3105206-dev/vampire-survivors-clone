"""Cloud Save & Leaderboard Synchronization Engine for Legendary Survival.

Supports bidirectional reconciliation between local persistent SaveData
and the Node.js / Express / MongoDB backend ecosystem:
  - Optimistic concurrency and union merging (no progress loss across devices)
  - PyInstaller (.exe) HTTP sync via urllib.request (zero external pip dependencies)
  - Pygbag / WebAssembly sync via WebBridge postMessage and localStorage
  - Global leaderboard fetching & score submission
  - Real-time achievement validation and diamond reward claiming
"""
import json
import os
import sys
from typing import Any, Dict, List, Optional
import urllib.request
import urllib.error

from core.config import IS_EMSCRIPTEN, AchievementID
from core.save_system import SaveData
from core.web_bridge import WebBridge


class CloudSaveSyncManager:
    """Manages cloud save synchronization, remote achievements, and leaderboard queries."""

    DEFAULT_BACKEND_URL: str = "http://localhost:3000"

    def __init__(self, backend_url: Optional[str] = None, auth_token: Optional[str] = None):
        self.backend_url = (backend_url or os.environ.get("LS_BACKEND_URL") or self.DEFAULT_BACKEND_URL).rstrip("/")
        self.auth_token = auth_token or os.environ.get("LS_AUTH_TOKEN") or ""
        self.last_sync_status: str = "idle"
        self.last_sync_error: Optional[str] = None

    def set_auth_token(self, token: str) -> None:
        """Update active JWT authentication token."""
        self.auth_token = str(token).strip()

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "LegendarySurvival-Client/2.0",
        }
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    def sync(self, save_data: SaveData, gold_earned: int = 0) -> Optional[Dict[str, Any]]:
        """
        Reconcile local SaveData with MongoDB backend cloud save:
          - Uploads local high scores, unlocked characters, permanent levels, achievements
          - Receives merged state from server and updates local SaveData
          - Reconciles gold earned from battle
        """
        if IS_EMSCRIPTEN:
            # WebAssembly environment: post to parent iframe
            payload = {
                "type": "LS_CLOUD_SYNC",
                "highScore": save_data.high_scores.get("best_kills", 0),
                "unlockedChars": sorted(list(save_data.unlocked_ids)),
                "permLevels": dict(save_data.perm_upgrades),
                "achievements": [a.name for a in save_data.unlocked_achievements if isinstance(a, AchievementID)],
                "campaignProgress": int(save_data.campaign_unlocked_level),
                "goldEarned": int(gold_earned),
            }
            WebBridge.post_message(payload)
            self.last_sync_status = "synced_wasm"
            return {"success": True, "mode": "wasm"}

        if not self.auth_token:
            self.last_sync_status = "offline_no_token"
            return None

        url = f"{self.backend_url}/api/users/me/save"
        payload = {
            "highScore": save_data.high_scores.get("best_kills", 0),
            "unlockedChars": sorted(list(save_data.unlocked_ids)),
            "permLevels": dict(save_data.perm_upgrades),
            "achievements": [a.name for a in save_data.unlocked_achievements if isinstance(a, AchievementID)],
            "campaignProgress": int(save_data.campaign_unlocked_level),
            "goldEarned": max(0, int(gold_earned)),
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers=self._get_headers(),
                method="PUT",
            )
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            if data.get("success"):
                cloud = data.get("cloudSave", {})
                currencies = data.get("currencies", {})

                # Merge back into local SaveData
                if "gold" in currencies:
                    save_data.total_gold = max(save_data.total_gold, int(currencies["gold"]))

                if "unlockedChars" in cloud and isinstance(cloud["unlockedChars"], list):
                    save_data.unlocked_ids.update(cloud["unlockedChars"])

                if "campaignProgress" in cloud:
                    save_data.campaign_unlocked_level = max(
                        save_data.campaign_unlocked_level, int(cloud["campaignProgress"])
                    )

                if "permLevels" in cloud and isinstance(cloud["permLevels"], dict):
                    for k, v in cloud["permLevels"].items():
                        if k in save_data.perm_upgrades:
                            save_data.perm_upgrades[k] = max(save_data.perm_upgrades[k], int(v))

                if "achievements" in cloud and isinstance(cloud["achievements"], list):
                    for ach_str in cloud["achievements"]:
                        if ach_str in AchievementID.__members__:
                            save_data.unlocked_achievements.add(AchievementID[ach_str])

                save_data.save()
                self.last_sync_status = "synced"
                self.last_sync_error = None
                return data

        except Exception as e:
            self.last_sync_status = "error"
            self.last_sync_error = str(e)
            return None

    def fetch_cloud_save(self) -> Optional[Dict[str, Any]]:
        """Download latest cloud save document from MongoDB."""
        if not self.auth_token:
            return None

        url = f"{self.backend_url}/api/users/me/save"
        try:
            req = urllib.request.Request(url, headers=self._get_headers(), method="GET")
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            self.last_sync_error = str(e)
            return None

    def fetch_leaderboard(
        self,
        mode: str = "all",
        sort_by: str = "rp",
        limit: int = 25,
    ) -> Optional[List[Dict[str, Any]]]:
        """Fetch global survivor leaderboard with filtering options."""
        url = f"{self.backend_url}/api/users/leaderboard?mode={mode}&sortBy={sort_by}&limit={limit}"
        try:
            req = urllib.request.Request(url, headers=self._get_headers(), method="GET")
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("leaderboard", [])
        except Exception as e:
            self.last_sync_error = str(e)
            return None

    def submit_achievement(self, achievement_id: str) -> Optional[Dict[str, Any]]:
        """Claim backend rewards for an unlocked achievement."""
        if not self.auth_token:
            return None

        url = f"{self.backend_url}/api/users/me/achievements"
        payload = {"achievementId": str(achievement_id)}
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers=self._get_headers(),
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            self.last_sync_error = str(e)
            return None

