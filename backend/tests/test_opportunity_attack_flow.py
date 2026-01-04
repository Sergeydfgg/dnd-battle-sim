from dndsim.core.engine.state import EncounterState, CombatantState, AttackProfile
from dndsim.core.engine.commands import BeginTurn, Move, UseReaction
from dndsim.core.engine.rules.apply import apply_command


def test_move_triggers_oa_then_reaction_attack():
    # seed 1234 => d20=15, затем для 1d8 => 2 (как в первом тесте)
    state = EncounterState().with_seed(1234)

    mover = CombatantState(
        id="A",
        name="Mover",
        ac=13,
        hp_current=20,
        hp_max=20,
        speed_ft=30,
        position=(0, 0),
    )

    reactor = CombatantState(
        id="B",
        name="Reactor",
        ac=13,
        hp_current=20,
        hp_max=20,
        speed_ft=30,
        position=(1, 0),  # рядом с A
        attacks={
            "claw": AttackProfile(
                name="claw",
                to_hit_bonus=5,
                damage_formula="1d8+3",
                damage_type="slashing",
            )
        },
    )

    state.combatants["A"] = mover
    state.combatants["B"] = reactor

    state.initiative_order = ["A", "B"]
    state.turn_owner_id = "A"

    # Начало хода A
    state, ev1 = apply_command(state, BeginTurn(combatant_id="A"))
    assert [e["type"] for e in ev1] == ["TurnStarted", "TurnResourcesReset"]

    # A пытается уйти: (0,0)->(0,1)->(0,2)
    # ВАЖНО: на шаге (0,1)->(0,2) A покидает досягаемость B (5 футов),
    # поэтому движение прерывается до выполнения шага (0,2).
    state, ev2 = apply_command(state, Move(mover_id="A", path=[(0, 1), (0, 2)]))
    types2 = [e["type"] for e in ev2]
    assert types2 == [
        "MovementStarted",
        "MovedStep",
        "OpportunityAttackTriggered",
        "ReactionWindowOpened",
        "MovementStopped",
    ]

    # после первого шага A на (0,1), второй шаг не выполнен из-за окна реакции
    assert state.combatants["A"].position == (0, 1)
    assert state.reaction_window is not None
    assert state.reaction_window.trigger == "opportunity_attack"
    assert state.reaction_window.threatened_by_id == "B"

    # B использует реакцию: opportunity attack по A
    state, ev3 = apply_command(state, UseReaction(reactor_id="B", attack_name="claw"))
    types3 = [e["type"] for e in ev3]
    assert types3 == [
        "AttackDeclared",
        "AttackRolled",
        "HitConfirmed",
        "DamageRolled",
        "DamageApplied",
        "ReactionWindowClosed",
    ]

    # Проверим детерминированные числа
    atk_rolled = ev3[1]["payload"]["roll"]
    assert atk_rolled["nat"] == 15
    assert atk_rolled["total"] == 20  # 15 + 5

    dmg_rolled = ev3[3]["payload"]["roll"]
    assert dmg_rolled["dice"] == [2]
    assert dmg_rolled["total"] == 5

    # A получил урон
    assert state.combatants["A"].hp_current == 15
    # окно реакции закрыто
    assert state.reaction_window is None
