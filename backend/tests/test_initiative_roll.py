from dndsim.core.engine.state import EncounterState, CombatantState
from dndsim.core.engine.commands import StartCombat, RollInitiative, FinalizeInitiative
from dndsim.core.engine.rules.apply import apply_command


def test_roll_initiative_is_deterministic_with_seed():
    state = EncounterState().with_seed(1234)

    state.combatants["A"] = CombatantState(
        id="A", name="A", ac=10, hp_current=10, hp_max=10
    )
    state.combatants["B"] = CombatantState(
        id="B", name="B", ac=10, hp_current=10, hp_max=10
    )

    state, _ = apply_command(state, StartCombat())

    # Random(1234).randint(1,20) == 15 (для A)
    state, ev_a = apply_command(state, RollInitiative(combatant_id="A", bonus=2))
    assert ev_a[0]["type"] == "InitiativeRolled"
    assert ev_a[0]["payload"]["roll"]["nat"] == 15
    assert ev_a[0]["payload"]["initiative"] == 17

    # следующий randint(1,20) для B будет детерминированным, проверим только что event есть
    state, ev_b = apply_command(state, RollInitiative(combatant_id="B", bonus=0))
    assert ev_b[0]["type"] == "InitiativeRolled"

    state, ev_fin = apply_command(state, FinalizeInitiative())
    assert [e["type"] for e in ev_fin] == ["InitiativeOrderFinalized", "RoundStarted"]
    assert state.turn_owner_id in ("A", "B")
    assert state.initiative_order[0] == state.turn_owner_id
