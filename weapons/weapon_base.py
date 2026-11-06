"""Base weapon utilities, elemental damage calculation, and synergy triggers."""
import random
from typing import Any, List, Optional, Tuple
import pygame

from core.config import C_GREEN, C_WHITE
from core.elements import Element, ElementalReaction, ElementalSynergyManager
from pooling.damage_number_pool import DamageNumberPool, PooledDamageNumber


def deal_player_damage(
    player: Any,
    enemy: Any,
    base_damage: int,
    damage_numbers: Any,
    default_color: tuple,
    element: Element = Element.NONE,
    all_enemies: Optional[Any] = None,
    particles: Optional[list] = None,
    shockwaves: Optional[list] = None,
    sfx: Optional[Any] = None,
) -> int:
    """
    Combat damage resolution with combat juice and Elemental Synergy:
      - Multipliers: Player damage_mult, Rage potion, Cuồng Huyết perk
      - Elemental interactions: Freeze shatter bonus (+30%), Superconduct/Corrupt armor shred
      - Crits: Enlarged Golden/Red crit text with '!' and micro screen shake
      - Life Steal on kill and Ultimate charging
      - Elemental reaction triggers (Melt, Superconduct, Overload, Abyssal Pyre, Plasma Surge)
    """
    dmult = getattr(player, "damage_mult", 1.0)
    if getattr(player, "potion_rage_timer", 0) > 0:
        dmult *= 1.6
    if getattr(player, "perk_cuong_huyet", False) and getattr(player, "hp", 100) < getattr(player, "max_hp", 100) * 0.4:
        dmult *= 1.35

    dmg = int(base_damage * dmult)

    # Superconduct & Corrupt armor shred bonus
    shred = getattr(enemy, "defense_shred", 1.0)
    if shred < 1.0 and getattr(enemy, "defense_shred_timer", 0) > 0:
        dmg = int(dmg / max(0.2, shred))

    # Frozen shatter bonus (+30% damage to frozen targets)
    if getattr(enemy, "frozen_timer", 0) > 0:
        dmg = int(dmg * 1.30)

    is_crit = False
    crit_chance = getattr(player, "crit_chance", 0.0)
    if crit_chance > 0 and random.random() < crit_chance:
        dmg = int(dmg * 2.0)
        is_crit = True

    enemy.take_damage(dmg)

    # Trigger Elemental Synergy reactions
    if element != Element.NONE and getattr(enemy, "alive", True):
        ElementalSynergyManager.apply_element(
            target=enemy,
            new_element=element,
            potency=dmg,
            all_enemies=all_enemies,
            particles=particles,
            damage_numbers=damage_numbers,
            shockwaves=shockwaves,
            sfx=sfx,
        )

    if player is not None and hasattr(player, "charge_ult"):
        player.charge_ult(min(1.2, dmg * 0.02) + (2.2 if not getattr(enemy, "alive", True) else 0.0))

    if is_crit:
        crit_col = (255, 85, 65) if random.random() < 0.4 else (255, 235, 55)
        if hasattr(damage_numbers, "spawn"):
            damage_numbers.spawn(enemy.x, enemy.y - 10, dmg, crit_col, scale=1.35, life=54, is_crit=True)
        else:
            num = PooledDamageNumber(enemy.x, enemy.y - 10, dmg, crit_col, scale=1.35, life=54, is_crit=True)
            damage_numbers.append(num)
        if player is not None:
            player.micro_shake = max(getattr(player, "micro_shake", 0), 3)
    else:
        if hasattr(damage_numbers, "spawn"):
            damage_numbers.spawn(enemy.x, enemy.y - 4, dmg, C_WHITE, scale=1.0, life=42)
        else:
            num = PooledDamageNumber(enemy.x, enemy.y - 4, dmg, C_WHITE, scale=1.0, life=42)
            damage_numbers.append(num)

    # Lifesteal on kill
    if not getattr(enemy, "alive", True) and getattr(player, "lifesteal_on_kill", 0) > 0:
        heal = player.lifesteal_on_kill
        if player.hp < player.max_hp:
            player.hp = min(player.max_hp, player.hp + heal)
            if hasattr(damage_numbers, "spawn"):
                damage_numbers.spawn(player.x, player.y - 24, heal, C_GREEN, scale=1.1, is_heal=True)
            else:
                num = PooledDamageNumber(player.x, player.y - 24, heal, C_GREEN, scale=1.1, is_heal=True)
                damage_numbers.append(num)

    return dmg
