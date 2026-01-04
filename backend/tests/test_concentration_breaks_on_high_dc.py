from dndsim.core.engine.state import EncounterState, CombatantState, AttackProfile
from dndsim.core.engine.commands import BeginTurn, StartConcentration, Attack
from dndsim.core.engine.rules.apply import apply_command


def test_concentration_breaks_on_high_damage():
    state = EncounterState().with_seed(1)

    caster = CombatantState(
        id="C",
        name="Caster",
        ac=10,
        hp_current=60,
        hp_max=60,
        save_bonuses={"con": -10},
    )
    attacker = CombatantState(
        id="A",
        name="Attacker",
        ac=10,
        hp_current=20,
        hp_max=20,
        attacks={
            "big_hit": AttackProfile(
                name="big_hit",
                to_hit_bonus=100,
                damage_formula="1d1+49",
                damage_type="slashing",
            )
        },
    )

    state.combatants["C"] = caster
    state.combatants["A"] = attacker
    state.initiative_order = ["C", "A"]
    state.turn_owner_id = "C"

    state, _ = apply_command(state, BeginTurn(combatant_id="C"))
    state, _ = apply_command(
        state, StartConcentration(combatant_id="C", effect_name="hold_person")
    )

    # ход атакующего
    state.turn_owner_id = "A"
    state, _ = apply_command(state, BeginTurn(combatant_id="A"))
    state, ev = apply_command(
        state,
        Attack(attacker_id="A", target_id="C", attack_name="big_hit", economy="action"),
    )

    assert state.combatants["C"].concentration is None
    types = [e["type"] for e in ev]
    assert "ConcentrationCheckTriggered" in types
    assert "ConcentrationBroken" in types
    assert state.combatants["C"].concentration is None
