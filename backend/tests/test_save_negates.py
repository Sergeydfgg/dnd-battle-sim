from dndsim.core.engine.state import EncounterState, CombatantState
from dndsim.core.engine.commands import BeginTurn, SaveEffect
from dndsim.core.engine.rules.apply import apply_command


def test_save_negates_on_success():
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

    # DC=1 => практически всегда успех, on_success="none" => без урона
    state, ev = apply_command(
        state,
        SaveEffect(
            source_id="C",
            target_ids=["T"],
            effect_name="sleep_like",
            save_ability="dex",
            dc=1,
            damage_formula="1d1+0",
            damage_type="psychic",
            on_success="none",
            economy="action",
        ),
    )

    types = [e["type"] for e in ev]
    assert types == [
        "SaveEffectDeclared",
        "SavingThrowRolled",
        "SavingThrowSucceeded",
        "SaveEffectNegated",
    ]
    assert state.combatants["T"].hp_current == 10
