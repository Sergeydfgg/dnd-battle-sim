from dndsim.core.engine.state import EncounterState, CombatantState, AttackProfile
from dndsim.core.engine.commands import BeginTurn, Attack
from dndsim.core.engine.rules.apply import apply_command


def test_attack_with_advantage_keeps_highest_die():
    # seed 42: первые два d20 = 4 и 1
    state = EncounterState().with_seed(42)

    attacker = CombatantState(
        id="A",
        name="Attacker",
        ac=14,
        hp_current=20,
        hp_max=20,
        speed_ft=30,
        attacks={
            "sword": AttackProfile(name="sword", to_hit_bonus=5, damage_formula="1d8+3")
        },
    )
    target = CombatantState(
        id="B",
        name="Target",
        ac=9,  # 4 + 5 = 9 => попадание впритык
        hp_current=20,
        hp_max=20,
        speed_ft=30,
    )

    state.combatants["A"] = attacker
    state.combatants["B"] = target
    state.initiative_order = ["A", "B"]
    state.turn_owner_id = "A"

    state, _ = apply_command(state, BeginTurn(combatant_id="A"))
    state, ev = apply_command(
        state,
        Attack(
            attacker_id="A", target_id="B", attack_name="sword", adv_state="advantage"
        ),
    )

    assert [e["type"] for e in ev][:3] == [
        "AttackDeclared",
        "AttackRolled",
        "HitConfirmed",
    ]

    roll = ev[1]["payload"]["roll"]
    assert roll["adv_state"] == "advantage"
    assert roll["dice"] == [4, 1]
    assert roll["kept"] == [4]
    assert roll["nat"] == 4
    assert roll["total"] == 9


def test_attack_with_disadvantage_can_auto_miss_on_nat1():
    # seed 42: d20 = 4 и 1 => disadvantage keeps 1 => auto miss
    state = EncounterState().with_seed(42)

    attacker = CombatantState(
        id="A",
        name="Attacker",
        ac=14,
        hp_current=20,
        hp_max=20,
        speed_ft=30,
        attacks={
            "sword": AttackProfile(name="sword", to_hit_bonus=5, damage_formula="1d8+3")
        },
    )
    target = CombatantState(
        id="B",
        name="Target",
        ac=1,  # даже при AC=1 всё равно должен быть автопромах из-за nat1
        hp_current=20,
        hp_max=20,
        speed_ft=30,
    )

    state.combatants["A"] = attacker
    state.combatants["B"] = target
    state.initiative_order = ["A", "B"]
    state.turn_owner_id = "A"

    state, _ = apply_command(state, BeginTurn(combatant_id="A"))
    state, ev = apply_command(
        state,
        Attack(
            attacker_id="A",
            target_id="B",
            attack_name="sword",
            adv_state="disadvantage",
        ),
    )

    types = [e["type"] for e in ev]
    assert types == ["AttackDeclared", "AttackRolled", "MissConfirmed"]

    roll = ev[1]["payload"]["roll"]
    assert roll["adv_state"] == "disadvantage"
    assert roll["dice"] == [4, 1]
    assert roll["kept"] == [1]
    assert roll["nat"] == 1
