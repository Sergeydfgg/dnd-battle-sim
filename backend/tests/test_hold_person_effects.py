from dndsim.core.engine.state import EncounterState, CombatantState
from dndsim.core.engine.commands import BeginTurn, CastSpell, EndConcentration
from dndsim.core.engine.rules.apply import apply_command
from dndsim.core.engine.spells.registry import clear_registry
from dndsim.core.engine.spells.library import register_core_spells


def test_hold_person_applies_paralyzed_and_removed_on_concentration_end():
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
        spell_slots_current={2: 1},
        spell_slots_max={2: 1},
    )
    # цель гарантированно провалит WIS save
    target = CombatantState(
        id="T",
        name="Target",
        ac=10,
        hp_current=10,
        hp_max=10,
        position=(1, 0),
        save_bonuses={"wis": -100},
    )

    state.combatants["C"] = caster
    state.combatants["T"] = target
    state.initiative_order = ["C", "T"]
    state.turn_owner_id = "C"

    state, _ = apply_command(state, BeginTurn(combatant_id="C"))
    state, ev = apply_command(
        state,
        CastSpell(
            caster_id="C", spell_name="hold_person", target_ids=["T"], slot_level=2
        ),
    )

    assert "paralyzed" in state.combatants["T"].conditions
    assert state.combatants["C"].concentration is not None
    assert state.effects, "Expected active effects dict to be non-empty"

    # заканчиваем концентрацию
    state, ev2 = apply_command(
        state,
        EndConcentration(combatant_id="C", reason="manual"),
    )

    assert "paralyzed" not in state.combatants["T"].conditions
    assert state.combatants["C"].concentration is None
    assert not state.effects, "Expected effects to be removed after concentration end"

    types = [e["type"] for e in ev2]
    assert "ConcentrationEnded" in types
    assert "EffectEnded" in types
