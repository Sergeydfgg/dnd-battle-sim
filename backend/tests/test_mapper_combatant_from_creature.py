from dndsim.core.adapters.mapper import CombatantOverrides, combatant_from_creature


def test_combatant_from_creature_maps_key_fields():
    creature = {
        "name": "Goblin",
        "ac": 15,
        "hp_max": 7,
        "temp_hp": 2,
        "resources": {"rage": 0},
        "is_pc": False,
        "attacks_per_action": 1,
        "initiative_bonus": 2,
        "attacks": [
            {
                "name": "Scimitar",
                "to_hit": 4,
                "damage": "1d6+2",
                "damage_type": "slashing",
            }
        ],
        "resistances": [],
        "vulnerabilities": [],
        "immunities": [],
        "save_bonuses": {"dex": 2},
    }

    c = combatant_from_creature(
        creature,
        combatant_id="goblin-1",
        side="monsters",
        position=(3, 5),
    )

    # ключевые ожидания (остальное может зависеть от схемы CombatantState)
    assert c.id == "goblin-1"
    assert c.name == "Goblin"
    assert c.side == "monsters"
    assert c.ac == 15
    assert c.hp_max == 7
    assert c.hp_current == 7
    assert c.temp_hp == 2
    assert c.attacks_per_action == 1
    assert c.initiative_bonus == 2

    # новые проверки под вашу модель:
    assert isinstance(c.damage_resistances, set)
    assert isinstance(c.attacks, dict)
    assert "Scimitar" in c.attacks


def test_combatant_from_creature_overrides_hp_and_temp():
    creature = {"name": "Fighter", "ac": 18, "hp_max": 12, "temp_hp": 0}

    c = combatant_from_creature(
        creature,
        combatant_id="pc-1",
        side="party",
        overrides=CombatantOverrides(hp_current=5, temp_hp=3, is_player_character=True),
    )

    assert c.hp_current == 5
    assert c.temp_hp == 3
    # is_pc может быть либо прямым полем, либо лежать в meta/tags/flags
    direct_is_pc = getattr(c, "is_pc", None)
    if direct_is_pc is None:
        meta = (
            getattr(c, "meta", None)
            or getattr(c, "tags", None)
            or getattr(c, "flags", None)
            or {}
        )
        direct_is_pc = meta.get("is_pc")

    assert c.is_player_character is True
