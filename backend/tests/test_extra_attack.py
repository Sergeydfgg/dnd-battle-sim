from dndsim.core.engine.state import EncounterState, CombatantState, AttackProfile
from dndsim.core.engine.commands import BeginTurn, Attack
from dndsim.core.engine.rules.apply import apply_command


def test_extra_attack_allows_two_action_attacks():
    state = EncounterState().with_seed(1234)

    a = CombatantState(
        id="A",
        name="A",
        ac=10,
        hp_current=20,
        hp_max=20,
        attacks_per_action=2,  # Extra Attack
        attacks={
            "sword": AttackProfile(
                name="sword", to_hit_bonus=5, damage_formula="1d8+0", uses_action=True
            )
        },
    )
    b = CombatantState(id="B", name="B", ac=10, hp_current=20, hp_max=20)

    state.combatants["A"] = a
    state.combatants["B"] = b
    state.initiative_order = ["A", "B"]
    state.turn_owner_id = "A"

    state, _ = apply_command(state, BeginTurn(combatant_id="A"))

    # 1-я атака действием: тратит action и стартует Attack action
    state, ev1 = apply_command(
        state,
        Attack(attacker_id="A", target_id="B", attack_name="sword", economy="action"),
    )
    assert ev1[0]["type"] == "AttackDeclared"
    assert state.combatants["A"].action_available is False
    assert state.combatants["A"].attack_action_started is True
    assert state.combatants["A"].attack_action_remaining == 1

    # 2-я атака тем же действием: разрешена
    state, ev2 = apply_command(
        state,
        Attack(attacker_id="A", target_id="B", attack_name="sword", economy="action"),
    )
    assert ev2[0]["type"] == "AttackDeclared"
    assert state.combatants["A"].attack_action_remaining == 0

    # 3-я атака в рамках того же хода должна быть запрещена
    state, ev3 = apply_command(
        state,
        Attack(attacker_id="A", target_id="B", attack_name="sword", economy="action"),
    )
    assert ev3[0]["type"] == "CommandRejected"
    assert ev3[0]["payload"]["code"] == "NO_ATTACKS_REMAINING"
