"""Comprehensive Unit Tests for Phase 2: Advanced Gameplay & Dynamic Audio.

Validates:
  1. Elemental Synergy Tree (Elemental affiliations, Reaction cross-triggers, Status effects)
  2. Combat bonuses (Freeze shatter +30%, Superconduct defense shred -40%)
  3. Modular AI Behaviors (Flocking separation, Ranged kiting, Exploder sprint & detonation, Summoner orbit)
  4. Dynamic Music Director (Layer buffer synthesis, Real-time intensity crossfading, Master volume)
  5. Weapons system elemental affiliations
"""
import math
import os
import sys
import unittest

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
pygame.init()

from core.elements import (
    Element,
    ElementalReaction,
    ElementalSynergyManager,
    StatusInstance,
)
from core.dynamic_audio import DynamicMusicDirector
from core.config import FPS, SCREEN_W, SCREEN_H
from entities.enemy import Enemy, EnemyType
from entities.ai_behaviors import (
    FlockingSeparation,
    KitingBehavior,
    ExploderChargeBehavior,
    SummonerOrbitBehavior,
)
from spatial.spatial_grid import SpatialHashGrid
from weapons.weapon_base import deal_player_damage
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


class MockPlayer:
    def __init__(self, x=400.0, y=400.0, hp=100, max_hp=100):
        self.x = float(x)
        self.y = float(y)
        self.hp = hp
        self.max_hp = max_hp
        self.radius = 16
        self.damage_mult = 1.0
        self.crit_chance = 0.0
        self.cdr = 0.0
        self.micro_shake = 0
        self.ult_charge = 0.0

    def charge_ult(self, amount):
        self.ult_charge += amount

    def take_damage(self, amount):
        self.hp -= amount


class ElementalSynergyTests(unittest.TestCase):
    """Tests for elemental reactions, status afflictions, and damage scaling."""

    def test_elemental_reaction_matrix(self):
        check = ElementalSynergyManager.check_reaction
        self.assertEqual(check(Element.FIRE, Element.ICE), ElementalReaction.MELT)
        self.assertEqual(check(Element.ICE, Element.FIRE), ElementalReaction.MELT)
        self.assertEqual(check(Element.ICE, Element.LIGHTNING), ElementalReaction.SUPERCONDUCT)
        self.assertEqual(check(Element.LIGHTNING, Element.ICE), ElementalReaction.SUPERCONDUCT)
        self.assertEqual(check(Element.FIRE, Element.LIGHTNING), ElementalReaction.OVERLOAD)
        self.assertEqual(check(Element.LIGHTNING, Element.FIRE), ElementalReaction.OVERLOAD)
        self.assertEqual(check(Element.FIRE, Element.VOID), ElementalReaction.ABYSSAL_PYRE)
        self.assertEqual(check(Element.VOID, Element.FIRE), ElementalReaction.ABYSSAL_PYRE)
        self.assertEqual(check(Element.LIGHTNING, Element.VOID), ElementalReaction.PLASMA_SURGE)
        self.assertEqual(check(Element.VOID, Element.LIGHTNING), ElementalReaction.PLASMA_SURGE)
        self.assertEqual(check(Element.FIRE, Element.FIRE), ElementalReaction.NONE)
        self.assertEqual(check(Element.NONE, Element.FIRE), ElementalReaction.NONE)

    def test_freeze_shatter_damage_bonus(self):
        player = MockPlayer()
        enemy_normal = Enemy(100, 100, EnemyType.BASIC, wave=1)
        enemy_frozen = Enemy(100, 100, EnemyType.BASIC, wave=1)
        enemy_frozen.frozen_timer = 60

        dmg_numbers = []
        dmg_normal = deal_player_damage(player, enemy_normal, 100, dmg_numbers, (255, 255, 255))
        dmg_frozen = deal_player_damage(player, enemy_frozen, 100, dmg_numbers, (255, 255, 255))

        # Frozen target takes +30% shatter bonus damage
        self.assertEqual(dmg_normal, 100)
        self.assertEqual(dmg_frozen, 130)

    def test_superconduct_defense_shred(self):
        player = MockPlayer()
        enemy = Enemy(100, 100, EnemyType.BASIC, wave=1)
        dmg_numbers = []

        # Inflict ICE first
        ElementalSynergyManager.apply_element(enemy, Element.ICE, potency=50, damage_numbers=dmg_numbers)
        self.assertIn(Element.ICE, enemy.elemental_statuses)

        # Trigger SUPERCONDUCT via LIGHTNING
        reaction = ElementalSynergyManager.apply_element(
            enemy, Element.LIGHTNING, potency=50, damage_numbers=dmg_numbers
        )
        self.assertEqual(reaction, ElementalReaction.SUPERCONDUCT)
        # Defense shred applied: takes 40% more damage (factor 0.6)
        self.assertLess(enemy.defense_shred, 1.0)
        self.assertGreater(enemy.defense_shred_timer, 0)

        # Subsequent hit deals increased damage due to defense shred
        shredded_dmg = deal_player_damage(player, enemy, 100, dmg_numbers, (255, 255, 255))
        self.assertGreater(shredded_dmg, 100)

    def test_melt_thermal_shock_reaction(self):
        enemy = Enemy(100, 100, EnemyType.BASIC, wave=1)
        enemy.hp = 1000
        dmg_numbers = []

        ElementalSynergyManager.apply_element(enemy, Element.FIRE, potency=40, damage_numbers=dmg_numbers)
        reaction = ElementalSynergyManager.apply_element(
            enemy, Element.ICE, potency=40, damage_numbers=dmg_numbers
        )
        self.assertEqual(reaction, ElementalReaction.MELT)
        # Melt reaction inflicts 2.5x potency burst damage (40 * 2.5 = 100)
        self.assertLessEqual(enemy.hp, 900)

    def test_overload_knockback(self):
        enemy = Enemy(200, 200, EnemyType.BASIC, wave=1)
        enemy.hp = 1000
        enemy.kbx = 0.0
        enemy.kby = 0.0
        dmg_numbers = []

        ElementalSynergyManager.apply_element(enemy, Element.FIRE, potency=50, damage_numbers=dmg_numbers)
        reaction = ElementalSynergyManager.apply_element(
            enemy, Element.LIGHTNING, potency=50, damage_numbers=dmg_numbers
        )
        self.assertEqual(reaction, ElementalReaction.OVERLOAD)
        # Overload creates explosive impulse
        self.assertTrue(abs(enemy.kbx) > 0 or abs(enemy.kby) > 0)


class ModularAITests(unittest.TestCase):
    """Tests for flocking separation, kiting, exploder sprint/blast, and summoner orbit."""

    def test_flocking_separation_pushes_overlapping_enemies_apart(self):
        grid = SpatialHashGrid(cell_size=100)
        e1 = Enemy(200.0, 200.0, EnemyType.BASIC, wave=1)
        e2 = Enemy(206.0, 200.0, EnemyType.BASIC, wave=1)  # Only 6 units away
        grid.insert(e1)
        grid.insert(e2)

        sep_x, sep_y = FlockingSeparation.compute(e1, grid, separation_radius=28.0)
        # e2 is to the right (+x), so e1 should receive a push to the left (-x)
        self.assertLess(sep_x, 0.0)

    def test_kiting_behavior_maintains_standoff_distance(self):
        player = MockPlayer(x=300.0, y=300.0)
        # Enemy too close (d = 100, preferred = 260) -> should retreat away
        e_close = Enemy(300.0, 400.0, EnemyType.RANGED, wave=1)
        vx, vy = KitingBehavior.compute_velocity(e_close, player, 3.0)
        # Moving away from player: player is at y=300, enemy at y=400 -> vy should be positive (+y)
        self.assertGreater(vy, 0.0)

        # Enemy too far (d = 500, preferred = 260) -> should approach
        e_far = Enemy(300.0, 800.0, EnemyType.RANGED, wave=1)
        vx2, vy2 = KitingBehavior.compute_velocity(e_far, player, 3.0)
        # Moving towards player: vy should be negative (-y)
        self.assertLess(vy2, 0.0)

    def test_exploder_arms_and_charges(self):
        player = MockPlayer(x=200.0, y=200.0)
        exploder = Enemy(220.0, 200.0, EnemyType.EXPLODER, wave=1)  # 20 units away (within arming radius 65)
        self.assertFalse(exploder.exploder_armed)

        # Update exploder
        ExploderChargeBehavior.update_exploder(exploder, player, 2.5)
        self.assertTrue(exploder.exploder_armed)
        self.assertGreater(exploder.exploder_fuse, 0)

    def test_exploder_detonation_damages_player_and_kills_self(self):
        player = MockPlayer(x=200.0, y=200.0, hp=100)
        exploder = Enemy(210.0, 200.0, EnemyType.EXPLODER, wave=1)
        exploder.exploder_armed = True
        exploder.exploder_fuse = 1  # Detonation on next frame

        dmg_numbers = []
        shockwaves = []
        particles = []
        vx, vy, is_dead = ExploderChargeBehavior.update_exploder(
            exploder,
            player,
            3.0,
            all_enemies=[exploder],
            particles=particles,
            damage_numbers=dmg_numbers,
            shockwaves=shockwaves,
        )
        self.assertTrue(is_dead)
        self.assertFalse(exploder.alive)
        self.assertLess(player.hp, 100)
        self.assertGreater(len(shockwaves), 0)

    def test_summoner_orbit_maintains_circling_radius(self):
        player = MockPlayer(x=400.0, y=400.0)
        summoner = Enemy(400.0, 720.0, EnemyType.NECROMANCER, wave=1)  # ~320 units away
        vx, vy = SummonerOrbitBehavior.compute_velocity(summoner, player, 2.0)
        # Tangential motion gives a non-zero velocity vector
        spd = math.hypot(vx, vy)
        self.assertAlmostEqual(spd, 2.0, places=1)


class DynamicMusicDirectorTests(unittest.TestCase):
    """Tests for procedural layered dynamic BGM synthesis and threat scaling."""

    def setUp(self):
        self.director = DynamicMusicDirector()

    def test_buffer_synthesis_generates_all_4_layers(self):
        self.director.prepare_buffers()
        for idx in range(4):
            buf = self.director._raw_buffers[idx]
            self.assertIsNotNone(buf)
            # 4 seconds at 44100 Hz, 16-bit mono = 44100 * 4 * 2 = 352,800 bytes
            expected_bytes = int(self.director.SR * self.director.LOOP_DURATION) * 2
            self.assertEqual(len(buf), expected_bytes)

    def test_dynamic_intensity_scaling_calm_state(self):
        self.director.active = True
        self.director.update(enemy_count=5, boss_count=0, player_hp_pct=1.0)
        # Layer 0 ambient baseline active, higher layers quiet
        self.assertGreater(self.director.target_volumes[0], 0.5)
        self.assertEqual(self.director.target_volumes[1], 0.0)
        self.assertEqual(self.director.target_volumes[2], 0.0)
        self.assertEqual(self.director.target_volumes[3], 0.0)

    def test_dynamic_intensity_scaling_swarm_escalation(self):
        self.director.active = True
        self.director.update(enemy_count=120, boss_count=0, player_hp_pct=1.0)
        # High enemy density raises Layer 1 (Pulse) and Layer 2 (Swarm Climax)
        self.assertEqual(self.director.target_volumes[1], 1.0)
        self.assertEqual(self.director.target_volumes[2], 1.0)
        self.assertEqual(self.director.target_volumes[3], 0.0)

    def test_dynamic_intensity_scaling_boss_presence(self):
        self.director.active = True
        self.director.update(enemy_count=10, boss_count=1, player_hp_pct=1.0)
        # Boss presence activates Layer 3 (Boss Cataclysm)
        self.assertEqual(self.director.target_volumes[3], 1.0)

    def test_dynamic_intensity_scaling_low_player_health(self):
        self.director.active = True
        self.director.update(enemy_count=10, boss_count=0, player_hp_pct=0.20)
        # Critical HP triggers urgent climax layer even at low enemy counts
        self.assertEqual(self.director.target_volumes[2], 1.0)


class WeaponElementalAffiliationTests(unittest.TestCase):
    """Verify all weapons are tagged with appropriate core elements."""

    def test_weapon_elemental_mapping(self):
        weapons = [
            (AuraWeapon(), Element.FIRE),
            (WhipWeapon(), Element.FIRE),
            (FireTrailWeapon(), Element.FIRE),
            (DragonfireThrustWeapon(), Element.FIRE),
            (IceWandWeapon(), Element.ICE),
            (PhantomArrowWeapon(), Element.ICE),
            (LightningStaffWeapon(), Element.LIGHTNING),
            (JudgementHammerWeapon(), Element.LIGHTNING),
            (OrbWeapon(), Element.LIGHTNING),
            (VoidSingularityWeapon(), Element.VOID),
            (BoomerangWeapon(), Element.VOID),
            (SkeletalLegionWeapon(), Element.VOID),
        ]
        for wpn, expected_elem in weapons:
            self.assertEqual(
                getattr(wpn, "element", Element.NONE),
                expected_elem,
                f"Weapon {wpn.__class__.__name__} expected element {expected_elem}",
            )


if __name__ == "__main__":
    unittest.main()
