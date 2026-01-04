from dndsim.core.engine.state import EncounterState, CombatantState
from dndsim.core.engine.commands import BeginTurn, CastSpell
from dndsim.core.engine.rules.apply import apply_command
from dndsim.core.engine.spells.registry import clear_registry
from dndsim.core.engine.spells.library import register_core_spells


def test_fireball_aoe_save_half_and_full_damage():
    clear_registry()
    register_core_spells()

    state = EncounterState().with_seed(1)

    caster = CombatantState(
        id="C",
        name="Caster",
        ac=10,
        hp_current=10,
        hp_max=10,
        position=(0, 0),
        spell_save_dc=15,
        spell_slots_current={3: 1},
        spell_slots_max={3: 1},
    )

    # T1 всегда SUCCESS (огромный бонус)
    t1 = CombatantState(
        id="T1",
        name="T1",
        ac=10,
        hp_current=50,
        hp_max=50,
        position=(1, 0),
        save_bonuses={"dex": 100},
    )

    # T2 всегда FAIL (огромный отрицательный бонус)
    t2 = CombatantState(
        id="T2",
        name="T2",
        ac=10,
        hp_current=50,
        hp_max=50,
        position=(1, 1),
        save_bonuses={"dex": -100},
    )

    state.combatants["C"] = caster
    state.combatants["T1"] = t1
    state.combatants["T2"] = t2
    state.initiative_order = ["C", "T1", "T2"]
    state.turn_owner_id = "C"

    state, _ = apply_command(state, BeginTurn(combatant_id="C"))
    state, ev = apply_command(
        state,
        CastSpell(
            caster_id="C",
            spell_name="fireball",
            target_ids=["T1", "T2"],
            slot_level=3,
        ),
    )

    types = [e["type"] for e in ev]
    assert "SpellCastDeclared" in types
    assert "SaveEffectDeclared" in types
    assert "EffectDamageApplied" in types

    # найдём применения урона по каждому таргету
    applied = [e for e in ev if e["type"] == "EffectDamageApplied"]
    assert len(applied) == 2

    p1 = next(e["payload"] for e in applied if e["payload"]["target_id"] == "T1")
    p2 = next(e["payload"] for e in applied if e["payload"]["target_id"] == "T2")

    # raw одинаковый (общий ролл), adjusted_base = half/full
    assert p1["raw"] == p2["raw"]
    assert p1["adjusted"] == p1["raw"] // 2
    assert p2["adjusted"] == p2["raw"]


def test_hold_person_starts_concentration_and_has_no_damage():
    clear_registry()
    register_core_spells()

    state = EncounterState().with_seed(1)

    caster = CombatantState(
        id="C",
        name="Caster",
        ac=10,
        hp_current=10,
        hp_max=10,
        position=(0, 0),
        spell_save_dc=13,
        spell_slots_current={2: 1},
        spell_slots_max={2: 1},
    )
    target = CombatantState(
        id="T",
        name="Target",
        ac=10,
        hp_current=10,
        hp_max=10,
        position=(1, 0),
        save_bonuses={"wis": 0},
    )

    state.combatants["C"] = caster
    state.combatants["T"] = target
    state.initiative_order = ["C", "T"]
    state.turn_owner_id = "C"

    state, _ = apply_command(state, BeginTurn(combatant_id="C"))
    state, ev = apply_command(
        state,
        CastSpell(
            caster_id="C",
            spell_name="hold_person",
            target_ids=["T"],
            slot_level=2,
        ),
    )

    assert state.combatants["C"].concentration is not None
    types = [e["type"] for e in ev]
    assert "ConcentrationStarted" in types

    # у hold_person в MVP нет урона => не должно быть EffectDamageRolled/Applied
    assert "EffectDamageRolled" not in types
    assert "EffectDamageApplied" not in types


def test_guiding_bolt_is_spell_attack_flow():
    clear_registry()
    register_core_spells()

    state = EncounterState().with_seed(1)

    caster = CombatantState(
        id="C",
        name="Caster",
        ac=10,
        hp_current=20,
        hp_max=20,
        position=(0, 0),
        spell_attack_bonus=100,  # гарант попадание
        spell_slots_current={1: 1},
        spell_slots_max={1: 1},
    )
    target = CombatantState(
        id="T",
        name="Target",
        ac=10,
        hp_current=20,
        hp_max=20,
        position=(1, 0),
    )

    state.combatants["C"] = caster
    state.combatants["T"] = target
    state.initiative_order = ["C", "T"]
    state.turn_owner_id = "C"

    state, _ = apply_command(state, BeginTurn(combatant_id="C"))
    state, ev = apply_command(
        state,
        CastSpell(
            caster_id="C",
            spell_name="guiding_bolt",
            target_ids=["T"],
            slot_level=1,
        ),
    )

    types = [e["type"] for e in ev]
    assert "AttackDeclared" in types
    assert "AttackRolled" in types
    assert "HitConfirmed" in types
    assert "DamageRolled" in types
    assert "DamageApplied" in types
