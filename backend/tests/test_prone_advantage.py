from dndsim.core.engine.state import EncounterState, CombatantState, AttackProfile
from dndsim.core.engine.commands import BeginTurn, Attack, ApplyCondition
from dndsim.core.engine.rules.apply import apply_command


def test_melee_attack_against_prone_is_advantage():
    # seed 42: d20s = 4,1 -> advantage keeps 4
    state = EncounterState().with_seed(42)

    a = CombatantState(
        id="A",
        name="A",
        ac=10,
        hp_current=10,
        hp_max=10,
        position=(0, 0),
        attacks={
            "sword": AttackProfile(name="sword", to_hit_bonus=5, damage_formula="1d8+0")
        },
    )
    b = CombatantState(
        id="B", name="B", ac=9, hp_current=10, hp_max=10, position=(1, 0)
    )

    state.combatants["A"] = a
    state.combatants["B"] = b
    state.initiative_order = ["A", "B"]
    state.turn_owner_id = "A"

    state, _ = apply_command(state, BeginTurn(combatant_id="A"))
    state, _ = apply_command(state, ApplyCondition(target_id="B", condition="prone"))

    state, ev = apply_command(
        state,
        Attack(
            attacker_id="A",
            target_id="B",
            attack_name="sword",
            attack_kind="melee",
            adv_state="normal",
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
