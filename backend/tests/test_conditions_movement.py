from dndsim.core.engine.state import EncounterState, CombatantState
from dndsim.core.engine.commands import (
    StartCombat,
    SetInitiative,
    FinalizeInitiative,
    BeginTurn,
    ApplyCondition,
    Move,
)
from dndsim.core.engine.rules.apply import apply_command


def test_grappled_blocks_move_command():
    state = EncounterState().with_seed(1)
    state.combatants["A"] = CombatantState(
        id="A", name="A", ac=10, hp_current=10, hp_max=10, position=(0, 0)
    )
    state.combatants["B"] = CombatantState(
        id="B", name="B", ac=10, hp_current=10, hp_max=10, position=(5, 5)
    )

    state, _ = apply_command(state, StartCombat())
    state, _ = apply_command(state, SetInitiative(combatant_id="A", initiative=10))
    state, _ = apply_command(state, SetInitiative(combatant_id="B", initiative=5))
    state, _ = apply_command(state, FinalizeInitiative())

    # A ходит
    state, _ = apply_command(state, BeginTurn(combatant_id="A"))
    state, _ = apply_command(state, ApplyCondition(target_id="A", condition="grappled"))

    state, ev = apply_command(state, Move(mover_id="A", path=[(0, 1)]))
    assert ev[0]["type"] == "CommandRejected"
    assert ev[0]["payload"]["code"] == "CONDITION_BLOCKS_MOVE"
