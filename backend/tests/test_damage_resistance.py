from dndsim.core.engine.state import EncounterState, CombatantState, AttackProfile
from dndsim.core.engine.commands import BeginTurn, Attack
from dndsim.core.engine.rules.apply import apply_command


def test_resistance_halves_damage_rounds_down():
    state = EncounterState().with_seed(1)

    a = CombatantState(
        id="A",
        name="A",
        ac=10,
        hp_current=20,
        hp_max=20,
        attacks={
            "fire_hit": AttackProfile(
                name="fire_hit",
                to_hit_bonus=100,
                damage_formula="1d5+0",
                damage_type="fire",
            )
        },
    )
    b = CombatantState(
        id="B",
        name="B",
        ac=10,
        hp_current=20,
        hp_max=20,
        damage_resistances={"fire"},
    )

    state.combatants["A"] = a
    state.combatants["B"] = b
    state.initiative_order = ["A", "B"]
    state.turn_owner_id = "A"

    state, _ = apply_command(state, BeginTurn(combatant_id="A"))
    state, ev = apply_command(
        state,
        Attack(
            attacker_id="A", target_id="B", attack_name="fire_hit", economy="action"
        ),
    )

    # 1d5 при seed=1 даст детерминированное значение, но нам важнее сам факт деления
    # Проверим по событиям DamageApplied:
    da = [e for e in ev if e["type"] == "DamageApplied"][0]
    raw = da["payload"]["raw"]
    adjusted = da["payload"]["adjusted"]
    assert adjusted == raw // 2
    assert da["payload"]["modifier"] == "resistant"
