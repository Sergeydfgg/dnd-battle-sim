from dndsim.core.engine.state import (
    EncounterState,
    CombatantState,
    ActiveEffect,
    AttackProfile,
)
from dndsim.core.engine.commands import BeginTurn, Attack, SaveEffect
from dndsim.core.engine.rules.apply import apply_command


def test_bless_adds_mod_to_attack_roll():
    state = EncounterState().with_seed(1)

    a = CombatantState(
        id="A",
        name="A",
        ac=10,
        hp_current=10,
        hp_max=10,
        attacks={
            "hit": AttackProfile(name="hit", to_hit_bonus=0, damage_formula="1d1+0")
        },
    )
    b = CombatantState(
        id="B", name="B", ac=30, hp_current=10, hp_max=10
    )  # высокая КД, неважно
    state.combatants["A"] = a
    state.combatants["B"] = b
    state.initiative_order = ["A", "B"]
    state.turn_owner_id = "A"

    # Bless на A
    state.effects[state.new_effect_id()] = ActiveEffect(
        id="E1", name="bless", source_id="X", target_id="A", started_round=1
    )

    state, _ = apply_command(state, BeginTurn(combatant_id="A"))
    state, ev = apply_command(
        state,
        Attack(attacker_id="A", target_id="B", attack_name="hit", economy="action"),
    )

    ar = next(e for e in ev if e["type"] == "AttackRolled")["payload"]["roll"]
    mods = ar["mods"]
    bless = next((m for m in mods if m["name"] == "bless"), None)
    assert bless is not None
    assert 1 <= bless["value"] <= 4
    assert ar["total"] == ar["nat"] + 0 + bless["value"]


def test_bless_adds_mod_to_save_roll():
    state = EncounterState().with_seed(1)

    src = CombatantState(id="S", name="S", ac=10, hp_current=10, hp_max=10)
    tgt = CombatantState(
        id="T", name="T", ac=10, hp_current=10, hp_max=10, save_bonuses={"dex": 0}
    )
    state.combatants["S"] = src
    state.combatants["T"] = tgt
    state.initiative_order = ["S", "T"]
    state.turn_owner_id = "S"

    # Bless на T
    state.effects[state.new_effect_id()] = ActiveEffect(
        id="E1", name="bless", source_id="X", target_id="T", started_round=1
    )

    state, _ = apply_command(state, BeginTurn(combatant_id="S"))
    state, ev = apply_command(
        state,
        SaveEffect(
            source_id="S",
            target_ids=["T"],
            effect_name="test",
            save_ability="dex",
            dc=10,
            adv_state="normal",
            on_success="none",
            damage_type="fire",
            damage_formula="1d1+0",
            economy="action",
        ),
    )

    sr = next(e for e in ev if e["type"] == "SavingThrowRolled")["payload"]["roll"]
    mods = sr["mods"]
    bless = next((m for m in mods if m["name"] == "bless"), None)
    assert bless is not None
    assert 1 <= bless["value"] <= 4
    assert sr["total"] == sr["nat"] + 0 + bless["value"]
