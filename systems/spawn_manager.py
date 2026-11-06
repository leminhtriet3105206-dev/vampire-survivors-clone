"""Wave spawn management, aggressive horde scaling, and swarm events."""
import math
import random
from typing import Any, List, Optional
import pygame

from core.config import FPS, SCREEN_H, SCREEN_W, WORLD_H, WORLD_W
from entities.enemy import Enemy, EnemyType
from spatial.math_utils import clamp

class SpawnManager:
    """
    Hệ thống triệu hồi quái vật Bullet-Heaven theo đợt (Aggressive Wave & Horde Scaling):
      - Tăng theo cấp số nhân cả số lượng quái tối đa trên màn hình (max_enemies) và kích thước cụm triệu hồi (batch_size: 5–20 quái/cụm).
      - Giảm mạnh thời gian hồi triệu hồi (spawn cooldown) sau mỗi đợt (wave).
      - Sự kiện Bầy Quái Bao Vây ("Đợt Tấn Công Dồn Dập!" - Swarm Event): Định kỳ phát cảnh báo viền đỏ và triệu hồi vòng vây quái tốc độ cao quanh người chơi.
    """
    def __init__(self):
        self.timer = 0
        self.wave = 0
        self.wave_timer = 0
        self.base_rate = 68  # Nhịp triệu hồi cơ bản nhanh hơn
        self.horde_cd = 0
        self.elite_timer = 0
        self.runner_timer = 0
        self.exploder_timer = 0
        self.necromancer_timer = 0
        self.swarm_alert_timer = 0
        self.max_enemies = 90
        self.batch_size = 5

    def update(self, player, enemies, tick):
        self.timer += 1
        self.wave_timer += 1
        if self.swarm_alert_timer > 0:
            self.swarm_alert_timer -= 1

        # Mỗi 25 giây tăng 1 Đợt (Wave) để nhịp độ dồn dập hơn
        wave = tick // (25 * FPS)
        self.wave = wave

        # Tăng theo hàm mũ giới hạn quái trên màn hình & kích thước bầy triệu hồi (5 -> 20)
        self.max_enemies = min(380, int(85 * (1.22 ** min(wave, 8)) + wave * 22))
        self.batch_size = min(20, 5 + int(wave * 1.8 + (wave ** 1.25) * 0.6))

        # Giảm dần thời gian chờ triệu hồi mỗi đợt
        rate = max(14, int(self.base_rate * (0.86 ** min(wave, 10)) - wave * 2))

        if self.timer >= rate:
            self.timer = 0
            if len(enemies) < self.max_enemies:
                avail = max(1, self.max_enemies - len(enemies))
                count = min(self.batch_size, avail)
                self._spawn_cluster(player, enemies, wave, count)

        # Quái Tinh Anh: Hiệp Sĩ Hắc Ám (TANK) xuất hiện sớm và dày hơn
        if wave >= 2:
            self.elite_timer += 1
            elite_rate = max(180, int(480 - wave * 28))
            if self.elite_timer >= elite_rate:
                self.elite_timer = 0
                if len(enemies) < self.max_enemies:
                    for _ in range(1 + wave // 4):
                        self._spawn(player, enemies, wave, EnemyType.TANK)
        else:
            self.elite_timer = 0

        # Dơi Hút Máu Tốc Độ Cao (RUNNER)
        if wave >= 1:
            self.runner_timer += 1
            runner_rate = max(150, int(420 - wave * 25))
            if self.runner_timer >= runner_rate:
                self.runner_timer = 0
                if len(enemies) < self.max_enemies:
                    self._spawn_cluster(player, enemies, wave, min(8, 3 + wave // 2), EnemyType.RUNNER)
        else:
            self.runner_timer = 0

        # Quái Cảm Tử (EXPLODER)
        if wave >= 3:
            self.exploder_timer += 1
            exploder_rate = max(220, int(560 - wave * 26))
            if self.exploder_timer >= exploder_rate:
                self.exploder_timer = 0
                if len(enemies) < self.max_enemies:
                    for _ in range(1 + wave // 5):
                        self._spawn(player, enemies, wave, EnemyType.EXPLODER)
        else:
            self.exploder_timer = 0

        # Pháp Sư Chiêu Hồn / Hồn Ma Ác Quỷ (NECROMANCER)
        if wave >= 3:
            self.necromancer_timer += 1
            necromancer_rate = max(260, int(680 - wave * 30))
            if self.necromancer_timer >= necromancer_rate:
                self.necromancer_timer = 0
                if len(enemies) < self.max_enemies:
                    self._spawn(player, enemies, wave, EnemyType.NECROMANCER)
        else:
            self.necromancer_timer = 0

        # Sự kiện Bầy Quái Bao Vây ("Đợt Tấn Công Dồn Dập!" - Swarm Event) mỗi 35 giây
        if tick > 0 and tick % (35 * FPS) == 0:
            self.trigger_swarm_event(player, enemies, wave)

    def trigger_swarm_event(self, player, enemies, wave):
        """Kích hoạt cảnh báo đỏ và triệu hồi vòng vây quái tốc độ cao bao quanh người chơi."""
        self.swarm_alert_timer = 190  # ~3.1 giây nháy viền đỏ & banner cảnh báo
        swarm_count = min(65, 22 + wave * 6)
        ring_r = max(SCREEN_W, SCREEN_H) * 0.54
        swarm_type = EnemyType.FAST if wave % 2 == 0 else EnemyType.RUNNER
        for i in range(swarm_count):
            ang = (math.tau / swarm_count) * i + random.uniform(-0.08, 0.08)
            dist_r = ring_r + random.uniform(-35, 45)
            sx = clamp(player.x + math.cos(ang) * dist_r, 20, WORLD_W - 20)
            sy = clamp(player.y + math.sin(ang) * dist_r, 20, WORLD_H - 20)
            etype = swarm_type if i % 4 != 0 else EnemyType.BASIC
            enemies.append(Enemy(sx, sy, etype, wave))

    def _spawn_cluster(self, player, enemies, wave, count=5, forced_type=None):
        """Triệu hồi một cụm/bầy quái (5–20 con) tụ tập quanh một điểm ở rìa màn hình."""
        margin = 160
        side = random.randint(0, 3)
        if side == 0:
            cx = player.x + random.uniform(-SCREEN_W // 2 - margin, SCREEN_W // 2 + margin)
            cy = player.y - SCREEN_H // 2 - margin
        elif side == 1:
            cx = player.x + SCREEN_W // 2 + margin
            cy = player.y + random.uniform(-SCREEN_H // 2 - margin, SCREEN_H // 2 + margin)
        elif side == 2:
            cx = player.x + random.uniform(-SCREEN_W // 2 - margin, SCREEN_W // 2 + margin)
            cy = player.y + SCREEN_H // 2 + margin
        else:
            cx = player.x - SCREEN_W // 2 - margin
            cy = player.y + random.uniform(-SCREEN_H // 2 - margin, SCREEN_H // 2 + margin)

        for _ in range(count):
            ox = random.uniform(-65, 65)
            oy = random.uniform(-65, 65)
            x = clamp(cx + ox, 16, WORLD_W - 16)
            y = clamp(cy + oy, 16, WORLD_H - 16)
            if forced_type is not None:
                etype = forced_type
            else:
                r = random.random()
                if r < 0.44:
                    etype = EnemyType.BASIC      # Bộ Xương Khô
                elif r < 0.72:
                    etype = EnemyType.FAST       # Dơi Hút Máu
                elif r < 0.90:
                    etype = EnemyType.RANGED     # Hồn Ma Ác Quỷ
                else:
                    etype = EnemyType.TANK       # Hiệp Sĩ Hắc Ám
            enemies.append(Enemy(x, y, etype, wave))

    def _spawn(self, player, enemies, wave, forced_type=None):
        self._spawn_cluster(player, enemies, wave, 1, forced_type)


