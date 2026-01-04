from dndsim.core.engine.state import EncounterState, CombatantState
from dndsim.core.engine.commands import BeginTurn, CastSpell
from dndsim.core.engine.rules.apply import apply_command
from dndsim.core.engine.spells.registry import clear_registry, register_spell
from dndsim.core.engine.spells.definitions import SaveSpell


def test_cast_spell_spends_slot_and_starts_concentration():
    clear_registry()
    register_spell(
        SaveSpell(
            name="hold_person",
            economy="action",
            concentration=True,
            min_slot_level=2,
            target_mode="single",
            save_ability="wis",
            on_success="none",
            damage_formula="1d1+0",
            damage_type="psychic",
        )
    )

    state = EncounterState().with_seed(1)

    caster = CombatantState(
        id="C",
        name="Caster",
        ac=10,
        hp_current=10,
        hp_max=10,
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

    assert state.combatants["C"].spell_slots_current[2] == 0
    assert state.combatants["C"].concentration is not None

    types = [e["type"] for e in ev]
    assert "SpellCastDeclared" in types
    assert "SpellSlotSpent" in types
    assert "ConcentrationStarted" in types
