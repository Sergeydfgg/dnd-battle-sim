from dndsim.core.engine.state import EncounterState, CombatantState, AttackProfile
from dndsim.core.engine.commands import BeginTurn, Move
from dndsim.core.engine.rules.apply import apply_command


def test_surprised_creature_does_not_get_opportunity_attack_before_its_first_turn_ends():
    state = EncounterState().with_seed(1234)

    mover = CombatantState(
        id="A",
        name="Mover",
        ac=13,
        hp_current=20,
        hp_max=20,
        speed_ft=30,
        position=(0, 0),
    )

    reactor = CombatantState(
        id="B",
        name="Reactor",
        ac=13,
        hp_current=20,
        hp_max=20,
        speed_ft=30,
        position=(1, 0),  # рядом
        surprised=True,  # ВРАСПЛОХ
        has_taken_first_turn=False,
        attacks={
            "claw": AttackProfile(name="claw", to_hit_bonus=5, damage_formula="1d8+3")
        },
    )

    state.combatants["A"] = mover
    state.combatants["B"] = reactor
    state.initiative_order = ["A", "B"]
    state.turn_owner_id = "A"

    state, _ = apply_command(state, BeginTurn(combatant_id="A"))

    # Путь: (0,0)->(0,1)->(0,2)
    # Обычно второй шаг вызвал бы OA от B, но B surprised и не может реагировать
    state, ev = apply_command(state, Move(mover_id="A", path=[(0, 1), (0, 2)]))

    types = [e["type"] for e in ev]
    assert types == ["MovementStarted", "MovedStep", "MovedStep", "MovementStopped"]

    assert state.reaction_window is None
    assert state.combatants["A"].position == (0, 2)
