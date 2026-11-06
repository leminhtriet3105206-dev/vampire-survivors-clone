"""Elemental Synergy Tree and Combat Reactions system for Legendary Survival.

Core Elements:
  - FIRE      : Ignite (damage over time, stacks up to 5x, spreads on death)
  - ICE       : Chill (40% slow) & Freeze (immobilize + 30% shatter damage bonus)
  - LIGHTNING : Shock (chain lightning arcing to nearby enemies)
  - VOID      : Corrupt (armor shred, gravity suction, void explosion on kill)

Elemental Reactions:
  - MELT          (FIRE + ICE)       : Thermal shock causing 2.5x critical burst damage
  - SUPERCONDUCT  (ICE + LIGHTNING)  : Cryo-electric pulse reducing all defenses by 40%
  - OVERLOAD      (FIRE + LIGHTNING) : High-yield explosive blast knocking enemies back
  - ABYSSAL_PYRE  (FIRE + VOID)      : Cursed dark flame burning maximum health percentage
  - PLASMA_SURGE  (LIGHTNING + VOID) : Chain lightning rifts pulling in adjacent targets
"""
from dataclasses import dataclass
from enum import Enum, auto
import math
import random
from typing import Any, Dict, List, Optional, Tuple
import pygame

from core.config import C_CYAN, C_ICE, C_LIGHTNING, C_RED, C_WHITE, C_YELLOW
from gfx.vfx import ShockwaveRing
from pooling.damage_number_pool import PooledDamageNumber
from pooling.particle_pool import PooledParticle
from spatial.math_utils import dist, in_radius_sq


class Element(Enum):
    NONE      = auto()
    FIRE      = auto()
    ICE       = auto()
    LIGHTNING = auto()
    VOID      = auto()


class ElementalReaction(Enum):
    NONE           = auto()
    MELT           = auto()
    SUPERCONDUCT   = auto()
    OVERLOAD       = auto()
    ABYSSAL_PYRE   = auto()
    PLASMA_SURGE   = auto()


# Color representations for visual effects
ELEMENT_COLORS = {
    Element.NONE:      (200, 200, 200),
    Element.FIRE:      (255, 75, 45),
    Element.ICE:       (75, 215, 255),
    Element.LIGHTNING: (255, 240, 75),
    Element.VOID:      (195, 75, 255),
}

REACTION_COLORS = {
    ElementalReaction.MELT:         (255, 165, 50),
    ElementalReaction.SUPERCONDUCT: (160, 235, 255),
    ElementalReaction.OVERLOAD:     (255, 60, 60),
    ElementalReaction.ABYSSAL_PYRE: (255, 40, 110),
    ElementalReaction.PLASMA_SURGE: (215, 120, 255),
}


@dataclass
class StatusInstance:
    element: Element
    duration: int
    potency: float
    stacks: int = 1
    timer: int = 0


class ElementalSynergyManager:
    """Evaluates cross-elemental reactions and manages active elemental afflictions on entities."""

    __slots__ = ("_reactions_count",)

    def __init__(self):
        self._reactions_count: int = 0

    @staticmethod
    def check_reaction(elem_a: Element, elem_b: Element) -> ElementalReaction:
        """Determine if two applied elements trigger an elemental synergy reaction."""
        pair = {elem_a, elem_b}
        if pair == {Element.FIRE, Element.ICE}:
            return ElementalReaction.MELT
        if pair == {Element.ICE, Element.LIGHTNING}:
            return ElementalReaction.SUPERCONDUCT
        if pair == {Element.FIRE, Element.LIGHTNING}:
            return ElementalReaction.OVERLOAD
        if pair == {Element.FIRE, Element.VOID}:
            return ElementalReaction.ABYSSAL_PYRE
        if pair == {Element.LIGHTNING, Element.VOID}:
            return ElementalReaction.PLASMA_SURGE
        return ElementalReaction.NONE

    @staticmethod
    def apply_element(
        target: Any,
        new_element: Element,
        potency: float,
        duration_frames: int = 180,
        all_enemies: Optional[Any] = None,
        particles: Optional[list] = None,
        damage_numbers: Optional[list] = None,
        shockwaves: Optional[list] = None,
        sfx: Optional[Any] = None,
    ) -> ElementalReaction:
        """
        Apply an element to an enemy.
        If the target already carries an opposing element, triggers a high-impact reaction.
        """
        if new_element == Element.NONE or not getattr(target, "alive", True):
            return ElementalReaction.NONE

        if not hasattr(target, "elemental_statuses"):
            target.elemental_statuses = {}

        statuses: Dict[Element, StatusInstance] = target.elemental_statuses

        # Check for reaction with any existing different element
        for existing_elem in list(statuses.keys()):
            if existing_elem != new_element:
                reaction = ElementalSynergyManager.check_reaction(existing_elem, new_element)
                if reaction != ElementalReaction.NONE:
                    # Consume the reacting element and execute reaction payload
                    del statuses[existing_elem]
                    ElementalSynergyManager.trigger_reaction_vfx(
                        target,
                        reaction,
                        potency,
                        all_enemies=all_enemies,
                        particles=particles,
                        damage_numbers=damage_numbers,
                        shockwaves=shockwaves,
                        sfx=sfx,
                    )
                    return reaction

        # No reaction: apply or refresh status stack
        if new_element in statuses:
            inst = statuses[new_element]
            inst.duration = max(inst.duration, duration_frames)
            inst.potency = max(inst.potency, potency)
            inst.stacks = min(5, inst.stacks + 1)
        else:
            statuses[new_element] = StatusInstance(
                element=new_element,
                duration=duration_frames,
                potency=potency,
                stacks=1,
            )

        # Immediate elemental effects on target
        if new_element == Element.ICE:
            target.slow_timer = max(getattr(target, "slow_timer", 0), duration_frames)
            target.slow_factor = 0.55
            # At 3+ ice stacks, freeze solid
            if statuses[new_element].stacks >= 3:
                target.frozen_timer = max(getattr(target, "frozen_timer", 0), 90)

        elif new_element == Element.FIRE:
            target.burn_timer = max(getattr(target, "burn_timer", 0), duration_frames)
            target.burn_dmg = max(getattr(target, "burn_dmg", 0), int(potency * 0.4) + 2)

        elif new_element == Element.VOID:
            # Corrupt shreds armor
            target.corrupt_timer = max(getattr(target, "corrupt_timer", 0), duration_frames)

        return ElementalReaction.NONE

    @staticmethod
    def trigger_reaction_vfx(
        target: Any,
        reaction: ElementalReaction,
        base_potency: float,
        all_enemies: Optional[Any] = None,
        particles: Optional[list] = None,
        damage_numbers: Optional[list] = None,
        shockwaves: Optional[list] = None,
        sfx: Optional[Any] = None,
    ) -> None:
        """Execute combat juice, damage burst, and particle effects for elemental reactions."""
        from gfx.vfx import ShockwaveRing
        from pooling.damage_number_pool import PooledDamageNumber
        from pooling.particle_pool import PooledParticle

        tx, ty = target.x, target.y

        if reaction == ElementalReaction.MELT:
            # Thermal Shock: 2.5x critical burst damage
            melt_dmg = int(base_potency * 2.5)
            target.take_damage(melt_dmg)
            if damage_numbers is not None:
                if hasattr(damage_numbers, "spawn"):
                    damage_numbers.spawn(tx, ty - 20, melt_dmg, (255, 160, 45), scale=1.45, text_override=f"{melt_dmg} MELT!")
                else:
                    num = PooledDamageNumber(tx, ty - 20, melt_dmg, (255, 160, 45), scale=1.45, text_override=f"{melt_dmg} MELT!")
                    damage_numbers.append(num)

            if particles is not None:
                for _ in range(12):
                    col = random.choice([(255, 80, 40), (80, 220, 255), (255, 240, 200)])
                    if hasattr(particles, "spawn"):
                        particles.spawn(tx, ty, col, speed=4.5, size=4, life=25)
                    else:
                        particles.append(PooledParticle(tx, ty, col, speed=4.5, size=4, life=25))

            if shockwaves is not None:
                shockwaves.append(ShockwaveRing(tx, ty, (255, 140, 40), max_radius=110, duration=18, width=5))

        elif reaction == ElementalReaction.SUPERCONDUCT:
            # Cryo-electric blast: shreds defense and zaps nearby enemies
            sc_dmg = int(base_potency * 1.5)
            target.take_damage(sc_dmg)
            target.defense_shred = 0.6  # Takes 40% more damage for 4 seconds
            target.defense_shred_timer = 240

            if damage_numbers is not None:
                if hasattr(damage_numbers, "spawn"):
                    damage_numbers.spawn(tx, ty - 20, sc_dmg, (160, 235, 255), scale=1.35, text_override="SUPERCONDUCT!")
                else:
                    num = PooledDamageNumber(tx, ty - 20, sc_dmg, (160, 235, 255), scale=1.35, text_override="SUPERCONDUCT!")
                    damage_numbers.append(num)

            if shockwaves is not None:
                shockwaves.append(ShockwaveRing(tx, ty, (140, 230, 255), max_radius=150, duration=22, width=6))

            # Chain to nearby enemies
            if all_enemies is not None:
                neighbors = []
                if hasattr(all_enemies, "query_radius"):
                    neighbors = all_enemies.query_radius(tx, ty, 140.0)
                elif isinstance(all_enemies, list):
                    neighbors = [e for e in all_enemies if getattr(e, "alive", True) and dist((tx, ty), (e.x, e.y)) < 140.0]

                for e in neighbors[:5]:
                    if e is not target and getattr(e, "alive", True):
                        e.take_damage(int(sc_dmg * 0.6))
                        e.defense_shred = 0.6
                        e.defense_shred_timer = 240

        elif reaction == ElementalReaction.OVERLOAD:
            # High knockback fire-lightning explosion
            ov_dmg = int(base_potency * 2.0)
            target.take_damage(ov_dmg)
            target.kbx += random.uniform(-8, 8)
            target.kby += random.uniform(-8, 8)

            if damage_numbers is not None:
                if hasattr(damage_numbers, "spawn"):
                    damage_numbers.spawn(tx, ty - 20, ov_dmg, (255, 60, 60), scale=1.4, text_override="OVERLOAD!")
                else:
                    num = PooledDamageNumber(tx, ty - 20, ov_dmg, (255, 60, 60), scale=1.4, text_override="OVERLOAD!")
                    damage_numbers.append(num)

            if shockwaves is not None:
                shockwaves.append(ShockwaveRing(tx, ty, (255, 70, 70), max_radius=180, duration=24, width=8))

            if all_enemies is not None:
                neighbors = []
                if hasattr(all_enemies, "query_radius"):
                    neighbors = all_enemies.query_radius(tx, ty, 160.0)
                elif isinstance(all_enemies, list):
                    neighbors = [e for e in all_enemies if getattr(e, "alive", True) and dist((tx, ty), (e.x, e.y)) < 160.0]

                for e in neighbors:
                    if getattr(e, "alive", True):
                        dx = e.x - tx
                        dy = e.y - ty
                        d = math.hypot(dx, dy)
                        if d > 0:
                            e.kbx += (dx / d) * 12.0
                            e.kby += (dy / d) * 12.0
                            e.take_damage(int(ov_dmg * 0.65))

        elif reaction == ElementalReaction.ABYSSAL_PYRE:
            # Dark fire: burns 15% max hp + heavy DoT
            target_max_hp = getattr(target, "max_hp", 100)
            pyre_dmg = max(int(base_potency * 1.8), int(target_max_hp * 0.15))
            target.take_damage(pyre_dmg)
            target.burn_timer = 300
            target.burn_dmg = int(base_potency * 0.8) + 10

            if damage_numbers is not None:
                if hasattr(damage_numbers, "spawn"):
                    damage_numbers.spawn(tx, ty - 20, pyre_dmg, (255, 40, 110), scale=1.45, text_override="ABYSSAL PYRE!")
                else:
                    num = PooledDamageNumber(tx, ty - 20, pyre_dmg, (255, 40, 110), scale=1.45, text_override="ABYSSAL PYRE!")
                    damage_numbers.append(num)

            if shockwaves is not None:
                shockwaves.append(ShockwaveRing(tx, ty, (220, 30, 95), max_radius=160, duration=25, width=7))

        elif reaction == ElementalReaction.PLASMA_SURGE:
            # Gravity rift + chain lightning
            ps_dmg = int(base_potency * 1.9)
            target.take_damage(ps_dmg)

            if damage_numbers is not None:
                if hasattr(damage_numbers, "spawn"):
                    damage_numbers.spawn(tx, ty - 20, ps_dmg, (215, 120, 255), scale=1.4, text_override="PLASMA SURGE!")
                else:
                    num = PooledDamageNumber(tx, ty - 20, ps_dmg, (215, 120, 255), scale=1.4, text_override="PLASMA SURGE!")
                    damage_numbers.append(num)

            if all_enemies is not None:
                neighbors = []
                if hasattr(all_enemies, "query_radius"):
                    neighbors = all_enemies.query_radius(tx, ty, 200.0)
                elif isinstance(all_enemies, list):
                    neighbors = [e for e in all_enemies if getattr(e, "alive", True) and dist((tx, ty), (e.x, e.y)) < 200.0]

                # Pull neighbors toward target (mini gravity singularity)
                for e in neighbors:
                    if e is not target and getattr(e, "alive", True):
                        e.x += (tx - e.x) * 0.35
                        e.y += (ty - e.y) * 0.35
                        e.take_damage(int(ps_dmg * 0.5))

            if shockwaves is not None:
                shockwaves.append(ShockwaveRing(tx, ty, (190, 80, 255), max_radius=200, duration=26, width=8))

        if sfx is not None and hasattr(sfx, "play_thunder"):
            sfx.play_thunder()

