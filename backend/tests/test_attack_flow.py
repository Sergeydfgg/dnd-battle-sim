from dndsim.core.engine.state import EncounterState, CombatantState, AttackProfile
from dndsim.core.engine.commands import BeginTurn, Attack, EndTurn
from dndsim.core.engine.rules.apply import apply_command


def test_attack_flow_seeded_hit():
    # seed подобран так, чтобы было предсказуемо:
    # random.Random(1234).randint(1,20) == 15
    # затем randint(1,8) == 2
    state = EncounterState().with_seed(1234)

    attacker = CombatantState(
        id="A",
        name="Attacker",
        ac=14,
        hp_current=20,
        hp_max=20,
        speed_ft=30,
        attacks={
            "sword": AttackProfile(
                name="sword",
                to_hit_bonus=5,
                damage_formula="1d8+3",
                damage_type="slashing",
            )
        },
    )
    target = CombatantState(
        id="B",
        name="Target",
        ac=13,
        hp_current=20,
        hp_max=20,
        speed_ft=30,
    )

    state.combatants["A"] = attacker
    state.combatants["B"] = target
    state.initiative_order = ["A", "B"]
    state.turn_owner_id = "A"

    # BeginTurn
    state, ev1 = apply_command(state, BeginTurn(combatant_id="A"))
    assert [e["type"] for e in ev1] == ["TurnStarted", "TurnResourcesReset"]

    # Attack
    state, ev2 = apply_command(
        state, Attack(attacker_id="A", target_id="B", attack_name="sword")
    )
    types = [e["type"] for e in ev2]
    assert types == [
        "AttackDeclared",
        "AttackRolled",
        "HitConfirmed",
        "DamageRolled",
        "DamageApplied",
    ]

    atk_rolled = ev2[1]["payload"]["roll"]
    assert atk_rolled["nat"] == 15
    assert atk_rolled["total"] == 20  # 15 + 5
    assert ev2[2]["payload"]["is_critical"] is False

    dmg_rolled = ev2[3]["payload"]["roll"]
    assert dmg_rolled["dice"] == [2]
    assert dmg_rolled["total"] == 5  # 2 + 3

    applied = ev2[4]["payload"]
    assert applied["hp_before"] == 20
    assert applied["hp_after"] == 15  # 20 - 5

    # EndTurn
    state, ev3 = apply_command(state, EndTurn(combatant_id="A"))
    assert [e["type"] for e in ev3] == ["TurnEnded"]
    assert state.turn_owner_id == "B"
