from dndsim.core.engine.state import EncounterState, CombatantState
from dndsim.core.engine.commands import BeginTurn, CastSpell
from dndsim.core.engine.rules.apply import apply_command
from dndsim.core.engine.spells.registry import clear_registry, register_spell
from dndsim.core.engine.spells.definitions import SaveSpell, AttackSpell


def _rejected(ev: list[dict]) -> dict:
    """Возвращает первое CommandRejected событие."""
    rej = [e for e in ev if e["type"] == "CommandRejected"]
    assert rej, f"Expected CommandRejected, got: {[e['type'] for e in ev]}"
    return rej[0]


def test_cast_spell_rejected_when_no_slot():
    clear_registry()
    register_spell(
        SaveSpell(
            name="hold_person",
            economy="action",
            concentration=True,
            min_slot_level=2,
            target_mode="single",
            save_ability="wis",
            on_success="none",
            damage_formula="1d1+0",
            damage_type="psychic",
        )
    )

    state = EncounterState().with_seed(1)

    caster = CombatantState(
        id="C",
        name="Caster",
        ac=10,
        hp_current=10,
        hp_max=10,
        spell_save_dc=13,
        # НЕТ слотов 2 уровня:
        spell_slots_current={2: 0},
        spell_slots_max={2: 1},
    )
    target = CombatantState(
        id="T",
        name="Target",
        ac=10,
        hp_current=10,
        hp_max=10,
        save_bonuses={"wis": 0},
    )

    state.combatants["C"] = caster
    state.combatants["T"] = target
    state.initiative_order = ["C", "T"]
    state.turn_owner_id = "C"

    state, _ = apply_command(state, BeginTurn(combatant_id="C"))
    state, ev = apply_command(
        state,
        CastSpell(
            caster_id="C", spell_name="hold_person", target_ids=["T"], slot_level=2
        ),
    )

    rej = _rejected(ev)
    assert rej["payload"]["code"] == "NO_SPELL_SLOT"


def test_cast_bonus_spell_rejected_when_no_bonus_action_available():
    clear_registry()
    register_spell(
        AttackSpell(
            name="quick_bolt",
            economy="bonus",
            concentration=False,
            min_slot_level=0,  # cantrip, слот не нужен
            target_mode="single",
            attack_kind="ranged",
            damage_formula="1d4+0",
            damage_type="force",
        )
    )

    state = EncounterState().with_seed(1)

    caster = CombatantState(
        id="C",
        name="Caster",
        ac=10,
        hp_current=10,
        hp_max=10,
        spell_attack_bonus=5,
    )
    target = CombatantState(
        id="T",
        name="Target",
        ac=10,
        hp_current=10,
        hp_max=10,
    )

    state.combatants["C"] = caster
    state.combatants["T"] = target
    state.initiative_order = ["C", "T"]
    state.turn_owner_id = "C"

    state, _ = apply_command(state, BeginTurn(combatant_id="C"))

    # вручную “сжигаем” бонусное действие, чтобы валидатор должен был зареджектить
    state.combatants["C"].bonus_available = False

    state, ev = apply_command(
        state,
        CastSpell(
            caster_id="C", spell_name="quick_bolt", target_ids=["T"], slot_level=0
        ),
    )

    rej = _rejected(ev)
    assert rej["payload"]["code"] == "NO_BONUS_ACTION"
