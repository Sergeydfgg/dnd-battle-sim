from dndsim.core.engine.state import EncounterState, CombatantState, AttackProfile
from dndsim.core.engine.commands import BeginTurn, Attack
from dndsim.core.engine.rules.apply import apply_command


def test_bonus_action_attack_consumes_bonus():
    state = EncounterState().with_seed(1234)

    a = CombatantState(
        id="A",
        name="A",
        ac=10,
        hp_current=20,
        hp_max=20,
        attacks={
            "dagger_offhand": AttackProfile(
                name="dagger_offhand",
                to_hit_bonus=5,
                damage_formula="1d4+0",
                uses_action=False,
                uses_bonus_action=True,
            )
        },
    )
    b = CombatantState(id="B", name="B", ac=10, hp_current=20, hp_max=20)

    state.combatants["A"] = a
    state.combatants["B"] = b
    state.initiative_order = ["A", "B"]
    state.turn_owner_id = "A"

    state, _ = apply_command(state, BeginTurn(combatant_id="A"))

    state, ev1 = apply_command(
        state,
        Attack(
            attacker_id="A",
            target_id="B",
            attack_name="dagger_offhand",
            economy="bonus",
        ),
    )
    assert ev1[0]["type"] == "AttackDeclared"
    assert state.combatants["A"].bonus_available is False

    state, ev2 = apply_command(
        state,
        Attack(
            attacker_id="A",
            target_id="B",
            attack_name="dagger_offhand",
            economy="bonus",
        ),
    )
    assert ev2[0]["type"] == "CommandRejected"
    assert ev2[0]["payload"]["code"] == "NO_BONUS_ACTION"
