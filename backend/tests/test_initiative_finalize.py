from dndsim.core.engine.state import EncounterState, CombatantState
from dndsim.core.engine.commands import StartCombat, SetInitiative, FinalizeInitiative
from dndsim.core.engine.rules.apply import apply_command


def test_initiative_finalize_sets_order_and_turn_owner():
    state = EncounterState().with_seed(1)

    state.combatants["A"] = CombatantState(
        id="A", name="A", ac=10, hp_current=10, hp_max=10
    )
    state.combatants["B"] = CombatantState(
        id="B", name="B", ac=10, hp_current=10, hp_max=10
    )
    state.combatants["C"] = CombatantState(
        id="C", name="C", ac=10, hp_current=10, hp_max=10
    )

    state, ev = apply_command(state, StartCombat())
    assert [e["type"] for e in ev] == ["CombatStarted"]
    assert state.phase == "setup_initiative"

    state, _ = apply_command(state, SetInitiative(combatant_id="A", initiative=12))
    state, _ = apply_command(state, SetInitiative(combatant_id="B", initiative=18))
    state, _ = apply_command(
        state, SetInitiative(combatant_id="C", initiative=18)
    )  # tie

    state, ev = apply_command(state, FinalizeInitiative())
    assert [e["type"] for e in ev] == ["InitiativeOrderFinalized", "RoundStarted"]

    # tie-breaker: по combatant_id (B < C)
    assert state.initiative_order == ["B", "C", "A"]
    assert state.turn_owner_id == "B"
    assert state.round == 1
    assert state.initiative_finalized is True
