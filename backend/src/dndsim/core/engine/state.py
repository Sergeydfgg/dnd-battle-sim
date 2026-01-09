from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from random import Random
from uuid import uuid4
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal, Dict, Set

Pos = Tuple[int, int]

Ability = Literal["str", "dex", "con", "int", "wis", "cha"]


class EffectRef(BaseModel):
    effect_name: str
    source_id: str
    started_round: int


class ActiveEffect(BaseModel):
    id: str
    name: str  # "hold_person"
    source_id: str  # кто наложил
    target_id: str  # на кого
    started_round: int
    duration_rounds: Optional[int] = None

    # если эффект держится концентрацией кастера:
    concentration_owner_id: Optional[str] = None
    concentration_effect_name: Optional[str] = None

    # MVP: какие conditions он включает
    applies_conditions: Set[str] = Field(default_factory=set)


@dataclass
class AttackProfile:
    name: str
    to_hit_bonus: int
    damage_formula: str
    damage_type: str = "slashing"
    reach_ft: int = 5

    # NEW: экономика атаки
    uses_action: bool = True
    uses_bonus_action: bool = False


@dataclass
class MultiattackProfile:
    name: str
    attacks: list[str]  # список attack_name из attacks[]


@dataclass
class ReactionWindow:
    id: str
    trigger: str  # "opportunity_attack"
    mover_id: str
    threatened_by_id: str
    reach_ft: int = 5


@dataclass
class CombatantState:
    id: str
    name: str
    ac: int
    hp_current: int
    hp_max: int
    temp_hp: int = 0
    speed_ft: int = 30
    side: str | None = None  # "party" | "enemies" | ... | None (не задано)

    # --- spellcasting (MVP) ---
    spellcasting_ability: Optional[Ability] = None

    # ЯВНО задаём числа (как сейчас в тестах):
    spell_save_dc: Optional[int] = None
    spell_attack_bonus: Optional[int] = None

    # spell slots
    spell_slots_current: Dict[int, int] = field(default_factory=dict)
    spell_slots_max: Dict[int, int] = field(default_factory=dict)

    concentration: EffectRef | None = None

    # NEW: бонусы спасбросков (STR/DEX/CON/INT/WIS/CHA)
    save_bonuses: Dict[str, int] = field(default_factory=dict)

    # NEW: сопротивления/уязвимости/иммунитеты по типам урона
    damage_resistances: set[str] = field(default_factory=set)
    damage_vulnerabilities: set[str] = field(default_factory=set)
    damage_immunities: set[str] = field(default_factory=set)

    # NEW: применять ли PC-правила (death saves)
    is_player_character: bool = False

    # NEW: death saves (актуально, если hp=0 и dying)
    death_save_successes: int = 0
    death_save_failures: int = 0
    is_stable: bool = False  # stabilized (не умирает, но unconscious)
    is_dead: bool = False  # мёртв

    # NEW: Extra Attack: сколько атак даёт Attack action
    attacks_per_action: int = 1

    # NEW: состояние Attack action в рамках текущего хода
    attack_action_started: bool = False
    attack_action_remaining: int = (
        0  # сколько атак ещё можно сделать в этом Attack action
    )

    # NEW: multiattacks (как у монстров)
    multiattacks: Dict[str, MultiattackProfile] = field(default_factory=dict)

    position: Pos = (0, 0)

    conditions: set[str] = field(default_factory=set)

    # ресурсы хода
    action_available: bool = True
    bonus_available: bool = True
    reaction_available: bool = True
    movement_remaining_ft: int = 0

    # NEW: initiative bonus (если хочешь хранить как поле, а не вычислять)
    initiative_bonus: int = 0

    # NEW: resources (универсальные ресурсы)
    resources_current: dict[str, int] = field(default_factory=dict)
    resources_max: dict[str, int] = field(default_factory=dict)

    # статусы (минимум)
    surprised: bool = False
    has_taken_first_turn: bool = False

    # действие "Отход" (Disengage) — отменяет OA до конца хода
    no_opportunity_attacks_until_turn_end: bool = False

    attacks: Dict[str, AttackProfile] = field(default_factory=dict)


@dataclass
class EncounterState:
    model_config = ConfigDict(arbitrary_types_allowed=True)
    round: int = 1
    turn_owner_id: Optional[str] = None
    initiative_order: List[str] = field(default_factory=list)

    phase: str = (
        "idle"  # idle | in_turn | reaction_window | finished | setup_initiative
    )

    seq: int = 0
    t: int = 0

    combatants: Dict[str, CombatantState] = field(default_factory=dict)

    rng_seed: int = 0
    rng: Random = field(default_factory=Random)

    reaction_window: Optional[ReactionWindow] = None

    # --- NEW: initiative/start combat ---
    combat_started: bool = False
    initiative_finalized: bool = False
    initiatives: Dict[str, int] = field(default_factory=dict)

    effects: dict[str, ActiveEffect] = field(default_factory=dict)

    _effect_seq: int = 1

    def with_seed(self, seed: int) -> "EncounterState":
        self.rng_seed = seed
        self.rng = Random(seed)
        return self

    def new_window_id(self) -> str:
        return str(uuid4())

    def new_effect_id(self) -> str:
        eid = f"E{self._effect_seq}"
        self._effect_seq += 1
        return eid


def effective_speed_ft(c: CombatantState) -> int:
    if "unconscious" in c.conditions:
        return 0
    if "grappled" in c.conditions:
        return 0
    if "restrained" in c.conditions:
        return 0
    return c.speed_ft


def are_hostile(a: CombatantState, b: CombatantState) -> bool:
    """
    Если side не задан (None) — сохраняем старое поведение: считаем всех враждебными.
    Если side задан у обоих — враждебны, когда side отличается.
    """
    if a.side is None or b.side is None:
        return True
    return a.side != b.side


def ability_mod(score: int) -> int:
    return (score - 10) // 2
