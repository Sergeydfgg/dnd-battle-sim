from dndsim.core.engine.state import EncounterState, CombatantState
from dndsim.core.engine.commands import BeginTurn, CastSpell
from dndsim.core.engine.rules.apply import apply_command
from dndsim.core.engine.spells.registry import clear_registry, register_spell
from dndsim.core.engine.spells.definitions import SaveSpell, AttackSpell


def _rej(ev: list[dict]) -> dict:
    r = [e for e in ev if e["type"] == "CommandRejected"]
    assert r, f"Expected CommandRejected, got {[e['type'] for e in ev]}"
    return r[0]


def test_castspell_rejected_out_of_range():
    clear_registry()
    register_spell(
        AttackSpell(
            name="short_ray",
            economy="action",
            concentration=False,
            min_slot_level=0,  # cantrip
            target_mode="single",
            attack_kind="ranged",
            damage_formula="1d4+0",
            damage_type="force",
            range_ft=5,  # 5 ft = 1 клетка
        )
    )

    state = EncounterState().with_seed(1)

    caster = CombatantState(
        id="C",
        name="Caster",
        ac=10,
        hp_current=10,
        hp_max=10,
        position=(0, 0),
        spell_attack_bonus=5,
    )
    target = CombatantState(
        id="T",
        name="Target",
        ac=10,
        hp_current=10,
        hp_max=10,
        position=(3, 0),  # 3 клетки = 15 ft
    )

    state.combatants["C"] = caster
    state.combatants["T"] = target
    state.initiative_order = ["C", "T"]
    state.turn_owner_id = "C"

    state, _ = apply_command(state, BeginTurn(combatant_id="C"))
    state, ev = apply_command(
        state,
        CastSpell(
            caster_id="C", spell_name="short_ray", target_ids=["T"], slot_level=0
        ),
    )

    rej = _rej(ev)
    assert rej["payload"]["code"] == "OUT_OF_RANGE"


def test_castspell_single_target_requires_exactly_one_target():
    clear_registry()
    register_spell(
        SaveSpell(
            name="single_save",
            economy="action",
            concentration=False,
            min_slot_level=0,
            target_mode="single",
            save_ability="wis",
            on_success="half",
            damage_formula="1d4+0",
            damage_type="psychic",
            range_ft=60,
        )
    )

    state = EncounterState().with_seed(1)

    caster = CombatantState(
        id="C",
        name="Caster",
        ac=10,
        hp_current=10,
        hp_max=10,
        position=(0, 0),
        spell_save_dc=13,
    )
    t1 = CombatantState(
        id="T1",
        name="T1",
        ac=10,
        hp_current=10,
        hp_max=10,
        position=(1, 0),
        save_bonuses={"wis": 0},
    )
    t2 = CombatantState(
        id="T2",
        name="T2",
        ac=10,
        hp_current=10,
        hp_max=10,
        position=(1, 1),
        save_bonuses={"wis": 0},
    )

    state.combatants["C"] = caster
    state.combatants["T1"] = t1
    state.combatants["T2"] = t2
    state.initiative_order = ["C", "T1", "T2"]
    state.turn_owner_id = "C"

    state, _ = apply_command(state, BeginTurn(combatant_id="C"))
    state, ev = apply_command(
        state,
        CastSpell(
            caster_id="C",
            spell_name="single_save",
            target_ids=["T1", "T2"],
            slot_level=0,
        ),
    )

    rej = _rej(ev)
    assert rej["payload"]["code"] == "BAD_TARGET_COUNT"


def test_castspell_aoe_allows_multiple_targets_in_range():
    clear_registry()
    register_spell(
        SaveSpell(
            name="aoe_save",
            economy="action",
            concentration=False,
            min_slot_level=0,
            target_mode="aoe",
            save_ability="dex",
            on_success="half",
            damage_formula="1d4+0",
            damage_type="fire",
            range_ft=30,
        )
    )

    state = EncounterState().with_seed(1)

    caster = CombatantState(
        id="C",
        name="Caster",
        ac=10,
        hp_current=10,
        hp_max=10,
        position=(0, 0),
        spell_save_dc=13,
    )
    t1 = CombatantState(
        id="T1",
        name="T1",
        ac=10,
        hp_current=10,
        hp_max=10,
        position=(2, 0),
        save_bonuses={"dex": 0},
    )
    t2 = CombatantState(
        id="T2",
        name="T2",
        ac=10,
        hp_current=10,
        hp_max=10,
        position=(2, 1),
        save_bonuses={"dex": 0},
    )

    state.combatants["C"] = caster
    state.combatants["T1"] = t1
    state.combatants["T2"] = t2
    state.initiative_order = ["C", "T1", "T2"]
    state.turn_owner_id = "C"

    state, _ = apply_command(state, BeginTurn(combatant_id="C"))
    state, ev = apply_command(
        state,
        CastSpell(
            caster_id="C", spell_name="aoe_save", target_ids=["T1", "T2"], slot_level=0
        ),
    )

    types = [e["type"] for e in ev]
    assert "CommandRejected" not in types
    assert "SpellCastDeclared" in types
