from dndsim.core.engine.state import EncounterState, CombatantState
from dndsim.core.engine.commands import BeginTurn, SaveEffect
from dndsim.core.engine.rules.apply import apply_command


def test_save_fail_applies_full_damage():
    state = EncounterState().with_seed(1)

    caster = CombatantState(id="C", name="Caster", ac=10, hp_current=10, hp_max=10)
    target = CombatantState(
        id="T", name="Target", ac=10, hp_current=10, hp_max=10, save_bonuses={"dex": 0}
    )

    state.combatants["C"] = caster
    state.combatants["T"] = target
    state.initiative_order = ["C", "T"]
    state.turn_owner_id = "C"

    state, _ = apply_command(state, BeginTurn(combatant_id="C"))

    # DC=30 => провал гарантирован
    state, ev = apply_command(
        state,
        SaveEffect(
            source_id="C",
            target_ids=["T"],
            effect_name="acid_splash",
            save_ability="dex",
            dc=30,
            damage_formula="1d1+0",
            damage_type="acid",
            on_success="half",
            economy="action",
        ),
    )

    types = [e["type"] for e in ev]
    assert types[:3] == ["SaveEffectDeclared", "SavingThrowRolled", "SavingThrowFailed"]
    assert state.combatants["T"].hp_current == 9
