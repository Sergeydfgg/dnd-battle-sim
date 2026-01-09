from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, ConfigDict

Ability = Literal["str", "dex", "con", "int", "wis", "cha"]

ResourceRefresh = Literal["turn", "short_rest", "long_rest", "encounter"]


class PosDTO(BaseModel):
    x: int = 0
    y: int = 0


class EncounterInitRequest(BaseModel):
    label: str = "init"
    reset_existing: bool = False


class EncounterRuntimeResponse(BaseModel):
    encounter_id: int
    save_id: int
    state: Dict[str, Any]
    events_delta: List[Dict[str, Any]] = Field(default_factory=list)


class AddCombatantRequest(BaseModel):
    creature_id: int
    side: str
    position: PosDTO = Field(default_factory=PosDTO)
    combatant_id: Optional[str] = None
    # overrides передаём как dict, чтобы не зависеть от конкретного класса overrides
    overrides: Optional[Dict[str, Any]] = None
    label: str = "add"


class ApplyCommandRequest(BaseModel):
    command: Dict[str, Any]
    label: str = "cmd"


class GetEncounterStateResponse(BaseModel):
    encounter_id: int
    save_id: int
    state: Dict[str, Any]
    # для MVP можно не возвращать весь лог, только снапшот


class ResourceSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max: int = Field(ge=0)
    current: int = Field(ge=0)
    refresh: ResourceRefresh


class AbilityScores(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    str: int = Field(ge=1, le=30)
    dex: int = Field(ge=1, le=30)
    con: int = Field(ge=1, le=30)

    # ВАЖНО: внутреннее имя int_ чтобы не ломать Pydantic,
    # но в JSON хотим ключ "int"
    int_: int = Field(ge=1, le=30, alias="int")

    wis: int = Field(ge=1, le=30)
    cha: int = Field(ge=1, le=30)


# ---- Creature payload (то, что будем хранить в data_json) ----


class AttackSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    to_hit_bonus: int
    damage_formula: str
    damage_type: str = "slashing"
    reach_ft: int = 5

    uses_action: bool = True
    uses_bonus_action: bool = False

    # OPTIONAL (на будущее): чтобы UI/движок мог считать бонусы сам
    ability_used: Optional[Ability] = None  # str/dex и т.д.
    proficient: Optional[bool] = None  # добавлять ли proficiency к атаке
    damage_bonus: Optional[int] = None  # плоский бонус к урону (если нужен)
    add_ability_mod_to_damage: Optional[bool] = (
        None  # добавлять ли модификатор характеристики в урон
    )


class SpellcastingSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    spellcasting_ability: Optional[Ability] = None
    spell_save_dc: Optional[int] = None
    spell_attack_bonus: Optional[int] = None

    # slots: {1: 4, 2: 2, ...}
    spell_slots_current: Dict[int, int] = Field(default_factory=dict)
    spell_slots_max: Dict[int, int] = Field(default_factory=dict)

    # MVP: просто список имен спеллов из registry
    spells_known: List[str] = Field(default_factory=list)


class CreatureData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(default=1, ge=1)

    ac: int
    hp_max: int
    speed_ft: int = 30

    # NEW: статы (можно сделать дефолтными "10" для простоты)
    ability_scores: AbilityScores = Field(
        default_factory=lambda: AbilityScores(
            str=10, dex=10, con=10, int=10, wis=10, cha=10
        )
    )

    # NEW: prof bonus (опционально, но пригодится)
    proficiency_bonus: Optional[int] = Field(default=None, ge=0, le=10)

    # NEW: профы в сейвах (пока не используем, но храним)
    save_proficiencies: List[Ability] = Field(default_factory=list)

    # Пока оставим ручные бонусы (движок уже использует)
    save_bonuses: Dict[str, int] = Field(default_factory=dict)

    damage_resistances: List[str] = Field(default_factory=list)
    damage_vulnerabilities: List[str] = Field(default_factory=list)
    damage_immunities: List[str] = Field(default_factory=list)

    attacks: Dict[str, AttackSpec] = Field(default_factory=dict)
    spellcasting: Optional[SpellcastingSpec] = None

    # NEW: temp hp
    temp_hp: int = Field(default=0, ge=0)

    # OPTIONAL: инициатива (если None — UI/движок потом сможет считать из DEX)
    initiative_bonus: Optional[int] = Field(default=None, ge=-20, le=20)

    # NEW: флаг PC-правил и Extra Attack
    is_player_character: bool = False
    attacks_per_action: int = Field(default=1, ge=1, le=4)

    # NEW: универсальные ресурсы класса (rage/ki/action_surge/etc)
    resources: Dict[str, ResourceSpec] = Field(default_factory=dict)


# ---- API DTOs ----


class CreatureCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    data: CreatureData


class CreatureUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    data: Optional[CreatureData] = None


class CreatureOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    data: CreatureData
    created_at: datetime
    updated_at: datetime


class EncounterCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str


class EncounterOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    created_at: datetime
    updated_at: datetime


class EncounterSaveCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: Optional[str] = None
    schema_version: int = Field(default=1, ge=1)

    state: Dict[str, Any]  # сериализованный EncounterState (JSON)
    events: List[Dict[str, Any]] = Field(default_factory=list)  # лог событий для UI


class EncounterSaveOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    encounter_id: str
    label: Optional[str] = None
    schema_version: int = Field(default=1, ge=1)
    created_at: datetime


class EncounterSaveWithStateOut(EncounterSaveOut):
    state: Dict[str, Any]
    events: List[Dict[str, Any]] = Field(default_factory=list)
