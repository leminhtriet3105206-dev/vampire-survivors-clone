"""WebBridge: Two-way communication between Pygame (Pygbag / WASM) and the Web Hub."""
import json
import sys
from typing import Any, Dict, Optional

IS_EMSCRIPTEN = sys.platform == "emscripten"


class WebBridge:
    """Two-way bridge between Pygame WebAssembly runtime and Legendary Survival Web Hub."""

    @staticmethod
    def get_user() -> Optional[Dict[str, Any]]:
        """Read player info from Web Hub (localStorage 'ls_bridge_user')."""
        if not IS_EMSCRIPTEN:
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
        """Send message to Web Hub via window.postMessage and persist to localStorage."""
        payload = json.dumps(data, ensure_ascii=False)
        if IS_EMSCRIPTEN:
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
            # Standalone desktop mode
            pass

    @staticmethod
    def notify_gold(delta: int, total: int) -> None:
        """Real-time gold update notification to Web Hub."""
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
        """Post match results to MongoDB / Web Hub match history."""
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

