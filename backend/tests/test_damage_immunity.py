from dndsim.core.engine.state import EncounterState, CombatantState, AttackProfile
from dndsim.core.engine.commands import BeginTurn, Attack
from dndsim.core.engine.rules.apply import apply_command


def test_immunity_zeroes_damage():
    state = EncounterState().with_seed(1)

    a = CombatantState(
        id="A",
        name="A",
        ac=10,
        hp_current=20,
        hp_max=20,
        attacks={
            "poison_hit": AttackProfile(
                name="poison_hit",
                to_hit_bonus=100,
                damage_formula="1d6+0",
                damage_type="poison",
            )
        },
    )
    b = CombatantState(
        id="B",
        name="B",
        ac=10,
        hp_current=20,
        hp_max=20,
        damage_immunities={"poison"},
    )

    state.combatants["A"] = a
    state.combatants["B"] = b
    state.initiative_order = ["A", "B"]
    state.turn_owner_id = "A"

    state, _ = apply_command(state, BeginTurn(combatant_id="A"))
    state, ev = apply_command(
        state,
        Attack(
            attacker_id="A", target_id="B", attack_name="poison_hit", economy="action"
        ),
    )

    da = [e for e in ev if e["type"] == "DamageApplied"][0]
    assert da["payload"]["adjusted"] == 0
    assert da["payload"]["modifier"] == "immune"
    assert state.combatants["B"].hp_current == 20
