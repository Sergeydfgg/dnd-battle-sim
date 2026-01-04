from dndsim.core.engine.state import EncounterState, CombatantState, AttackProfile
from dndsim.core.engine.commands import BeginTurn, Move
from dndsim.core.engine.rules.apply import apply_command


def test_oa_triggers_only_from_hostile_side():
    state = EncounterState().with_seed(1234)

    mover = CombatantState(
        id="A",
        name="Mover",
        ac=13,
        hp_current=20,
        hp_max=20,
        speed_ft=30,
        position=(0, 0),
        side="party",
    )
    ally = CombatantState(
        id="C",
        name="Ally",
        ac=13,
        hp_current=20,
        hp_max=20,
        speed_ft=30,
        position=(-1, 0),
        side="party",
        attacks={
            "club": AttackProfile(name="club", to_hit_bonus=3, damage_formula="1d4+1")
        },
    )
    enemy = CombatantState(
        id="B",
        name="Enemy",
        ac=13,
        hp_current=20,
        hp_max=20,
        speed_ft=30,
        position=(1, 0),
        side="enemies",
        attacks={
            "claw": AttackProfile(name="claw", to_hit_bonus=5, damage_formula="1d8+3")
        },
    )

    state.combatants["A"] = mover
    state.combatants["B"] = enemy
    state.combatants["C"] = ally

    state.initiative_order = ["A", "B", "C"]
    state.turn_owner_id = "A"

    state, _ = apply_command(state, BeginTurn(combatant_id="A"))

    # A уходит: второй шаг выводит из reach и союзника, и врага.
    # Но OA должен сработать только от врага B.
    state, ev = apply_command(state, Move(mover_id="A", path=[(0, 1), (0, 2)]))
    types = [e["type"] for e in ev]

    assert "OpportunityAttackTriggered" in types
    idx = types.index("OpportunityAttackTriggered")
    payload = ev[idx]["payload"]
    assert payload["threatened_by_id"] == "B"  # НЕ C
    assert payload["mover_id"] == "A"
