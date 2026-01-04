# backend/src/dndsim/core/engine/commands.py

from typing import Literal, Union
from pydantic import BaseModel, ConfigDict


class CommandBase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str


class BeginTurn(CommandBase):
    type: Literal["BeginTurn"] = "BeginTurn"
    combatant_id: str


class EndTurn(CommandBase):
    type: Literal["EndTurn"] = "EndTurn"
    combatant_id: str


class Attack(CommandBase):
    type: Literal["Attack"] = "Attack"
    attacker_id: str
    target_id: str
    attack_name: str
    attack_kind: Literal["melee", "ranged"] = "melee"
    adv_state: Literal["normal", "advantage", "disadvantage"] = "normal"

    # NEW:
    economy: Literal["action", "bonus"] = "action"


class Multiattack(CommandBase):
    type: Literal["Multiattack"] = "Multiattack"
    attacker_id: str
    target_id: str
    multiattack_name: str
    adv_state: Literal["normal", "advantage", "disadvantage"] = "normal"


class Disengage(CommandBase):
    type: Literal["Disengage"] = "Disengage"
    combatant_id: str


class Move(CommandBase):
    type: Literal["Move"] = "Move"
    mover_id: str
    path: list[tuple[int, int]]


class UseReaction(CommandBase):
    type: Literal["UseReaction"] = "UseReaction"
    reactor_id: str
    reaction_type: Literal["opportunity_attack"] = "opportunity_attack"
    attack_name: str
    adv_state: Literal["normal", "advantage", "disadvantage"] = "normal"


class DeclineReaction(CommandBase):
    type: Literal["DeclineReaction"] = "DeclineReaction"
    reactor_id: str


class StartCombat(CommandBase):
    type: Literal["StartCombat"] = "StartCombat"


class SetInitiative(CommandBase):
    type: Literal["SetInitiative"] = "SetInitiative"
    combatant_id: str
    initiative: int


class RollInitiative(CommandBase):
    type: Literal["RollInitiative"] = "RollInitiative"
    combatant_id: str
    bonus: int = 0  # обычно Dex mod, но в MVP передаём явно


class FinalizeInitiative(CommandBase):
    type: Literal["FinalizeInitiative"] = "FinalizeInitiative"


class ApplyCondition(CommandBase):
    type: Literal["ApplyCondition"] = "ApplyCondition"
    target_id: str
    condition: Literal["prone", "grappled", "restrained", "unconscious"]


class RemoveCondition(CommandBase):
    type: Literal["RemoveCondition"] = "RemoveCondition"
    target_id: str
    condition: Literal["prone", "grappled", "restrained", "unconscious"]


class SaveEffect(CommandBase):
    type: Literal["SaveEffect"] = "SaveEffect"

    source_id: str  # кто применил эффект (заклинатель/монстр)
    target_ids: list[str]  # список целей

    effect_name: str  # для лога/статистики (например "burning_hands")

    save_ability: Literal["str", "dex", "con", "int", "wis", "cha"]
    dc: int
    adv_state: Literal["normal", "advantage", "disadvantage"] = "normal"

    # урон
    damage_formula: str
    damage_type: str

    # поведение при успехе
    on_success: Literal["half", "none"] = "half"

    # экономия хода (чтобы позже это же использовать для spells/abilities)
    economy: Literal["action", "bonus"] = "action"


class RollDeathSave(CommandBase):
    type: Literal["RollDeathSave"] = "RollDeathSave"
    combatant_id: str


class Stabilize(CommandBase):
    type: Literal["Stabilize"] = "Stabilize"
    healer_id: str
    target_id: str


class Heal(CommandBase):
    type: Literal["Heal"] = "Heal"
    healer_id: str | None = None
    target_id: str
    amount: int


class StartConcentration(CommandBase):
    type: Literal["StartConcentration"] = "StartConcentration"
    combatant_id: str
    effect_name: str
    source_id: str | None = None  # если None -> = combatant_id


class EndConcentration(CommandBase):
    type: Literal["EndConcentration"] = "EndConcentration"
    combatant_id: str
    reason: str = "ended_by_user"


class CastSpell(CommandBase):
    type: Literal["CastSpell"] = "CastSpell"
    caster_id: str
    spell_name: str
    target_ids: list[str] = []
    slot_level: int = 1  # 0 = cantrip


Command = Union[
    StartCombat,
    SetInitiative,
    RollInitiative,
    FinalizeInitiative,
    BeginTurn,
    EndTurn,
    Attack,
    Multiattack,
    Disengage,
    Move,
    UseReaction,
    DeclineReaction,
    ApplyCondition,
    RemoveCondition,
    SaveEffect,
    RollDeathSave,
    Stabilize,
    Heal,
    StartConcentration,
    EndConcentration,
    CastSpell,
]
