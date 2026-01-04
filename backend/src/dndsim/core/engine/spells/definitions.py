from __future__ import annotations
from typing import Annotated, Literal, Optional, Union, Set
from pydantic import BaseModel, Field

Ability = Literal["str", "dex", "con", "int", "wis", "cha"]
TargetMode = Literal["single", "aoe"]


class SpellBase(BaseModel):
    name: str
    economy: Literal["action", "bonus", "reaction"] = "action"
    concentration: bool = False
    min_slot_level: int = 1  # 0 = cantrip
    target_mode: TargetMode = "single"
    damage_formula: str = "1d6+0"
    damage_type: str = "force"

    # NEW: targeting / range (MVP)
    range_ft: int = 60
    requires_los: bool = False


class SaveSpell(SpellBase):
    kind: Literal["save"] = "save"
    save_ability: Ability
    on_success: Literal["half", "none"] = "half"  # half or negates

    # NEW: conditions on failed save (MVP)
    on_fail_conditions: Set[str] = Field(default_factory=set)


class AttackSpell(SpellBase):
    kind: Literal["attack"] = "attack"
    attack_kind: Literal["melee", "ranged"] = "ranged"


SpellDefinition = Annotated[Union[SaveSpell, AttackSpell], Field(discriminator="kind")]
