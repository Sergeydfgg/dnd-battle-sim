from dndsim.core.engine.state import EncounterState, CombatantState
from dndsim.core.engine.commands import Heal
from dndsim.core.engine.rules.apply import apply_command


def test_heal_removes_unconscious_and_resets_death_saves():
    state = EncounterState().with_seed(1)

    target = CombatantState(
        id="P",
        name="PC",
        ac=10,
        hp_current=0,
        hp_max=10,
        is_player_character=True,
        conditions={"unconscious"},
        death_save_successes=2,
        death_save_failures=1,
        is_stable=False,
    )
    state.combatants["P"] = target

    state, ev = apply_command(state, Heal(healer_id=None, target_id="P", amount=5))

    assert state.combatants["P"].hp_current == 5
    assert "unconscious" not in state.combatants["P"].conditions
    assert state.combatants["P"].death_save_successes == 0
    assert state.combatants["P"].death_save_failures == 0
    assert state.combatants["P"].is_stable is False
    assert ev[0]["type"] == "Healed"
