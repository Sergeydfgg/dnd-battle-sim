from __future__ import annotations
from typing import Dict
from dndsim.core.engine.spells.definitions import SpellDefinition

_SPELLS: Dict[str, SpellDefinition] = {}


def register_spell(spell: SpellDefinition) -> None:
    _SPELLS[spell.name] = spell


def get_spell(name: str) -> SpellDefinition:
    return _SPELLS[name]


def clear_registry() -> None:
    _SPELLS.clear()
