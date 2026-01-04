from dndsim.core.engine.state import EncounterState, CombatantState
from dndsim.core.engine.commands import BeginTurn, CastSpell
from dndsim.core.engine.rules.apply import apply_command
from dndsim.core.engine.spells.registry import clear_registry, register_spell
from dndsim.core.engine.spells.definitions import SaveSpell, AttackSpell


def _rej_code(ev: list[dict]) -> str:
    rej = [e for e in ev if e["type"] == "CommandRejected"]
    assert rej
    return rej[0]["payload"]["code"]


def test_cast_save_spell_requires_spell_save_dc():
    clear_registry()
    register_spell(
        SaveSpell(
            name="test_save",
            economy="action",
            concentration=False,
            min_slot_level=0,
            target_mode="single",
            save_ability="wis",
            on_success="half",
            damage_formula="1d4+0",
            damage_type="force",
        )
    )

    state = EncounterState().with_seed(1)
    caster = CombatantState(
        id="C", name="C", ac=10, hp_current=10, hp_max=10
    )  # dc отсутствует
    target = CombatantState(
        id="T", name="T", ac=10, hp_current=10, hp_max=10, save_bonuses={"wis": 0}
    )
    state.combatants["C"] = caster
    state.combatants["T"] = target
    state.initiative_order = ["C", "T"]
    state.turn_owner_id = "C"

    state, _ = apply_command(state, BeginTurn(combatant_id="C"))
    state, ev = apply_command(
        state,
        CastSpell(
            caster_id="C", spell_name="test_save", target_ids=["T"], slot_level=0
        ),
    )
    assert _rej_code(ev) == "MISSING_SPELL_SAVE_DC"


def test_cast_attack_spell_requires_spell_attack_bonus():
    clear_registry()
    register_spell(
        AttackSpell(
            name="test_attack",
            economy="action",
            concentration=False,
            min_slot_level=0,
            target_mode="single",
            attack_kind="ranged",
            damage_formula="1d4+0",
            damage_type="force",
        )
    )

    state = EncounterState().with_seed(1)
    caster = CombatantState(
        id="C", name="C", ac=10, hp_current=10, hp_max=10, spell_save_dc=13
    )  # bonus отсутствует
    target = CombatantState(id="T", name="T", ac=10, hp_current=10, hp_max=10)
    state.combatants["C"] = caster
    state.combatants["T"] = target
    state.initiative_order = ["C", "T"]
    state.turn_owner_id = "C"

    state, _ = apply_command(state, BeginTurn(combatant_id="C"))
    state, ev = apply_command(
        state,
        CastSpell(
            caster_id="C", spell_name="test_attack", target_ids=["T"], slot_level=0
        ),
    )
    assert _rej_code(ev) == "MISSING_SPELL_ATTACK_BONUS"
