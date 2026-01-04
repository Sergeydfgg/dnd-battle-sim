from dndsim.core.engine.state import (
    EncounterState,
    CombatantState,
    AttackProfile,
    MultiattackProfile,
)
from dndsim.core.engine.commands import BeginTurn, Multiattack, Attack
from dndsim.core.engine.rules.apply import apply_command


def test_multiattack_consumes_action_and_executes_attacks():
    state = EncounterState().with_seed(1234)

    monster = CombatantState(
        id="M",
        name="Monster",
        ac=12,
        hp_current=30,
        hp_max=30,
        attacks={
            "bite": AttackProfile(name="bite", to_hit_bonus=5, damage_formula="1d8+3"),
            "claw": AttackProfile(name="claw", to_hit_bonus=5, damage_formula="1d6+3"),
        },
        multiattacks={
            "multi_bite_claw": MultiattackProfile(
                name="multi_bite_claw", attacks=["bite", "claw"]
            )
        },
    )
    target = CombatantState(id="T", name="Target", ac=10, hp_current=30, hp_max=30)

    state.combatants["M"] = monster
    state.combatants["T"] = target
    state.initiative_order = ["M", "T"]
    state.turn_owner_id = "M"

    state, _ = apply_command(state, BeginTurn(combatant_id="M"))

    state, ev = apply_command(
        state,
        Multiattack(attacker_id="M", target_id="T", multiattack_name="multi_bite_claw"),
    )
    types = [e["type"] for e in ev]
    assert types[0] == "MultiattackDeclared"
    assert "AttackDeclared" in types  # будут 2 серии AttackDeclared/AttackRolled/...

    assert state.combatants["M"].action_available is False

    # Попытка обычной action-атаки после multiattack должна быть запрещена (action уже потрачен)
    state, ev2 = apply_command(
        state,
        Attack(attacker_id="M", target_id="T", attack_name="bite", economy="action"),
    )
    assert ev2[0]["type"] == "CommandRejected"
    assert ev2[0]["payload"]["code"] == "NO_ACTION"
