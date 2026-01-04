from dndsim.core.engine.state import EncounterState, CombatantState
from dndsim.core.engine.commands import BeginTurn, Stabilize
from dndsim.core.engine.rules.apply import apply_command


def test_stabilize_sets_stable_and_consumes_action():
    state = EncounterState().with_seed(1)

    healer = CombatantState(id="H", name="Healer", ac=10, hp_current=10, hp_max=10)
    target = CombatantState(
        id="P",
        name="PC",
        ac=10,
        hp_current=0,
        hp_max=10,
        is_player_character=True,
        conditions={"unconscious"},
    )

    state.combatants["H"] = healer
    state.combatants["P"] = target
    state.initiative_order = ["H", "P"]
    state.turn_owner_id = "H"

    state, _ = apply_command(state, BeginTurn(combatant_id="H"))
    state, ev = apply_command(state, Stabilize(healer_id="H", target_id="P"))

    assert state.combatants["H"].action_available is False
    assert state.combatants["P"].is_stable is True
    assert state.combatants["P"].death_save_successes == 0
    assert state.combatants["P"].death_save_failures == 0
    assert [e["type"] for e in ev] == ["Stabilized"]
