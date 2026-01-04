from dndsim.core.engine.state import EncounterState, CombatantState, AttackProfile
from dndsim.core.engine.commands import BeginTurn, StartConcentration, Attack
from dndsim.core.engine.rules.apply import apply_command


def test_concentration_maintained_with_high_con_save():
    state = EncounterState().with_seed(1)

    caster = CombatantState(
        id="C",
        name="Caster",
        ac=10,
        hp_current=20,
        hp_max=20,
        save_bonuses={"con": 100},
    )
    attacker = CombatantState(
        id="A",
        name="Attacker",
        ac=10,
        hp_current=20,
        hp_max=20,
        attacks={
            "small_hit": AttackProfile(
                name="small_hit",
                to_hit_bonus=100,
                damage_formula="1d1+0",
                damage_type="piercing",
            )
        },
    )

    state.combatants["C"] = caster
    state.combatants["A"] = attacker
    state.initiative_order = ["C", "A"]
    state.turn_owner_id = "C"

    state, _ = apply_command(state, BeginTurn(combatant_id="C"))
    state, _ = apply_command(
        state, StartConcentration(combatant_id="C", effect_name="bless")
    )

    state.turn_owner_id = "A"
    state, _ = apply_command(state, BeginTurn(combatant_id="A"))
    state, ev = apply_command(
        state,
        Attack(
            attacker_id="A", target_id="C", attack_name="small_hit", economy="action"
        ),
    )

    assert state.combatants["C"].concentration is not None
    assert any(e["type"] == "ConcentrationMaintained" for e in ev)
