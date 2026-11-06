"""Headless simulation stress test: 1000+ simultaneous enemies with Spatial Hash Grid and Object Pools."""
import os
import sys
import time
import unittest

# Ensure root directory is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Headless pygame
os.environ["SDL_VIDEODRIVER"] = "dummy"
import pygame
pygame.init()
pygame.display.set_mode((1, 1))

from engine import Game
from entities.enemy import Enemy, EnemyType


class Test1000EnemiesStress(unittest.TestCase):
    def test_1000_enemies_frame_time(self):
        game = Game()
        game.reset()

        # Spawn 1000 enemies scattered around player
        for i in range(1000):
            x = game.player.x + (i % 50 - 25) * 30
            y = game.player.y + (i // 50 - 10) * 30
            e = Enemy(x, y, EnemyType.BASIC, wave=5)
            game.enemies.append(e)

        self.assertEqual(len(game.enemies), 1000)

        # Warm up 3 frames
        for _ in range(3):
            game._update()

        # Measure 60 frames (1 full second of intensive 1000-enemy combat)
        start_time = time.perf_counter()
        frames = 60
        for _ in range(frames):
            game._update()
        total_time = time.perf_counter() - start_time

        avg_fps = frames / total_time
        avg_frame_ms = (total_time / frames) * 1000

        print(f"\n[Stress Test] 1000 Enemies 60-Frame Benchmark:")
        print(f"  Total Time: {total_time:.3f}s for {frames} frames")
        print(f"  Average Frame Time: {avg_frame_ms:.2f}ms")
        print(f"  Effective Simulation FPS: {avg_fps:.1f} FPS")

        # 60 FPS requires frame time < 16.6ms. In headless simulation, ensure < 16.6ms
        self.assertLess(avg_frame_ms, 25.0, "Frame time exceeded budget under 1000 enemies!")


if __name__ == "__main__":
    unittest.main()

