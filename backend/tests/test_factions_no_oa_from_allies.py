from dndsim.core.engine.state import EncounterState, CombatantState
from dndsim.core.engine.commands import BeginTurn, Move
from dndsim.core.engine.rules.apply import apply_command


def test_no_oa_from_ally_only():
    state = EncounterState().with_seed(1)

    mover = CombatantState(
        id="A",
        name="Mover",
        ac=13,
        hp_current=20,
        hp_max=20,
        speed_ft=30,
        position=(0, 0),
        side="party",
    )
    ally = CombatantState(
        id="C",
        name="Ally",
        ac=13,
        hp_current=20,
        hp_max=20,
        speed_ft=30,
        position=(1, 0),
        side="party",
    )

    state.combatants["A"] = mover
    state.combatants["C"] = ally

    state.initiative_order = ["A", "C"]
    state.turn_owner_id = "A"

    state, _ = apply_command(state, BeginTurn(combatant_id="A"))
    state, ev = apply_command(state, Move(mover_id="A", path=[(0, 1), (0, 2)]))

    assert [e["type"] for e in ev] == [
        "MovementStarted",
        "MovedStep",
        "MovedStep",
        "MovementStopped",
    ]
    assert state.reaction_window is None
    assert state.combatants["A"].position == (0, 2)
