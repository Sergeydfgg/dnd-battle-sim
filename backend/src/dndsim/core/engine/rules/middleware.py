from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Protocol, Literal

from dndsim.core.engine.events import Roll, RollMod
from dndsim.core.engine.state import EncounterState, CombatantState


# --- контексты (минимум полей; можно расширять) ---


@dataclass(frozen=True)
class AttackRollContext:
    attacker_id: str
    target_id: str
    attack_name: str
    source: Literal["weapon", "spell"]  # кто вызвал бросок


@dataclass(frozen=True)
class SaveRollContext:
    roller_id: str  # кто делает сейв
    save_ability: str
    source_id: Optional[str]  # кто заставил сейв (spell/effect)
    effect_name: str


@dataclass(frozen=True)
class DamageRollContext:
    source_id: str
    target_id: str
    damage_type: str
    source: Literal["weapon", "spell", "effect"]


# --- middleware протокол ---


class RollMiddleware(Protocol):
    def before_attack_roll(
        self,
        state: EncounterState,
        attacker: CombatantState,
        target: CombatantState,
        ctx: AttackRollContext,
        roll: Roll,
    ) -> List[RollMod]: ...

    def before_save_roll(
        self,
        state: EncounterState,
        roller: CombatantState,
        ctx: SaveRollContext,
        roll: Roll,
    ) -> List[RollMod]: ...

    def before_damage_roll(
        self,
        state: EncounterState,
        source: CombatantState,
        target: CombatantState,
        ctx: DamageRollContext,
        roll: Roll,
    ) -> List[RollMod]: ...


# --- утилита: применить модификаторы к Roll ---
def apply_roll_mods(roll: Roll, mods: List[RollMod]) -> Roll:
    if not mods:
        return roll
    roll.mods.extend(mods)
    roll.total += sum(m.value for m in mods)
    # nat / is_critical не трогаем (Bless не влияет на nat20)
    return roll


# --- пример middleware: Bless (+1d4 к атакам/сейвам) ---
class BlessMiddleware:
    def _has_bless(self, state: EncounterState, combatant_id: str) -> bool:
        # считаем, что Bless висит как ActiveEffect.name == "bless" на target_id
        for eff in state.effects.values():
            if eff.target_id == combatant_id and eff.name == "bless":
                return True
        return False

    def before_attack_roll(
        self,
        state: EncounterState,
        attacker: CombatantState,
        target: CombatantState,
        ctx: AttackRollContext,
        roll: Roll,
    ) -> List[RollMod]:
        if not self._has_bless(state, attacker.id):
            return []
        d4 = state.rng.randint(1, 4)
        return [RollMod(name="bless", value=d4)]

    def before_save_roll(
        self,
        state: EncounterState,
        roller: CombatantState,
        ctx: SaveRollContext,
        roll: Roll,
    ) -> List[RollMod]:
        if not self._has_bless(state, roller.id):
            return []
        d4 = state.rng.randint(1, 4)
        return [RollMod(name="bless", value=d4)]

    def before_damage_roll(
        self,
        state: EncounterState,
        source: CombatantState,
        target: CombatantState,
        ctx: DamageRollContext,
        roll: Roll,
    ) -> List[RollMod]:
        return []


DEFAULT_ROLL_MIDDLEWARES: List[RollMiddleware] = [
    BlessMiddleware(),
]
