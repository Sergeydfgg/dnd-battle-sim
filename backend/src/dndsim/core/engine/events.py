from __future__ import annotations

from typing import Any, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, ConfigDict


class RollMod(BaseModel):
    name: str
    value: int


class Roll(BaseModel):
    roll_id: UUID = Field(default_factory=uuid4)
    kind: Literal["d20", "damage", "other"]
    formula: str
    dice: list[int]
    kept: list[int]
    mods: list[RollMod] = Field(default_factory=list)
    total: int
    adv_state: Literal["normal", "advantage", "disadvantage"] = "normal"
    nat: Optional[int] = None
    is_critical: bool = False


class EventEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: UUID = Field(default_factory=uuid4)
    seq: int
    t: int
    type: str

    round: int
    turn_owner_id: Optional[str] = None
    actor_id: Optional[str] = None

    payload: dict[str, Any] = Field(default_factory=dict)


def ev_command_rejected(
    *,
    seq: int,
    t: int,
    round_: int,
    turn_owner_id: Optional[str],
    actor_id: Optional[str],
    command: dict,
    code: str,
    message: str,
    meta: dict,
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="CommandRejected",
        round=round_,
        turn_owner_id=turn_owner_id,
        actor_id=actor_id,
        payload={
            "command": command,
            "code": code,
            "message": message,
            "meta": meta,
        },
    )


def ev_combat_started(*, seq: int, t: int, round_: int) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="CombatStarted",
        round=round_,
        turn_owner_id=None,
        actor_id=None,
        payload={},
    )


def ev_initiative_set(
    *, seq: int, t: int, round_: int, combatant_id: str, initiative: int
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="InitiativeSet",
        round=round_,
        turn_owner_id=None,
        actor_id=combatant_id,
        payload={"combatant_id": combatant_id, "initiative": initiative},
    )


def ev_initiative_rolled(
    *, seq: int, t: int, round_: int, combatant_id: str, roll: Roll, bonus: int
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="InitiativeRolled",
        round=round_,
        turn_owner_id=None,
        actor_id=combatant_id,
        payload={
            "combatant_id": combatant_id,
            "roll": roll.model_dump(),
            "bonus": bonus,
            "initiative": roll.total,
        },
    )


def ev_initiative_order_finalized(
    *, seq: int, t: int, round_: int, order: list[dict]
) -> EventEnvelope:
    # order: [{"combatant_id": "...", "initiative": 12}, ...]
    return EventEnvelope(
        seq=seq,
        t=t,
        type="InitiativeOrderFinalized",
        round=round_,
        turn_owner_id=None,
        actor_id=None,
        payload={"order": order},
    )


def ev_round_started(
    *, seq: int, t: int, round_: int, turn_owner_id: str
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="RoundStarted",
        round=round_,
        turn_owner_id=turn_owner_id,
        actor_id=None,
        payload={"round": round_},
    )


def ev_turn_started(
    *, seq: int, t: int, round_: int, turn_owner_id: str
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="TurnStarted",
        round=round_,
        turn_owner_id=turn_owner_id,
        actor_id=turn_owner_id,
        payload={"combatant_id": turn_owner_id},
    )


def ev_turn_resources_reset(
    *,
    seq: int,
    t: int,
    round_: int,
    turn_owner_id: str,
    action: bool,
    bonus: bool,
    reaction: bool,
    movement_ft: int,
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="TurnResourcesReset",
        round=round_,
        turn_owner_id=turn_owner_id,
        actor_id=turn_owner_id,
        payload={
            "combatant_id": turn_owner_id,
            "action": action,
            "bonus": bonus,
            "reaction": reaction,
            "movement_ft": movement_ft,
        },
    )


def ev_disengage_applied(
    *, seq: int, t: int, round_: int, turn_owner_id: str, combatant_id: str
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="DisengageApplied",
        round=round_,
        turn_owner_id=turn_owner_id,
        actor_id=combatant_id,
        payload={"combatant_id": combatant_id},
    )


def ev_movement_started(
    *, seq: int, t: int, round_: int, turn_owner_id: str, mover_id: str, from_pos, path
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="MovementStarted",
        round=round_,
        turn_owner_id=turn_owner_id,
        actor_id=mover_id,
        payload={"mover_id": mover_id, "from": from_pos, "planned_path": path},
    )


def ev_moved_step(
    *,
    seq: int,
    t: int,
    round_: int,
    turn_owner_id: str,
    mover_id: str,
    from_pos,
    to_pos,
    cost_ft: int,
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="MovedStep",
        round=round_,
        turn_owner_id=turn_owner_id,
        actor_id=mover_id,
        payload={
            "mover_id": mover_id,
            "from": from_pos,
            "to": to_pos,
            "cost_ft": cost_ft,
            "tags": [],
        },
    )


def ev_movement_stopped(
    *, seq: int, t: int, round_: int, turn_owner_id: str, mover_id: str, reason: str
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="MovementStopped",
        round=round_,
        turn_owner_id=turn_owner_id,
        actor_id=mover_id,
        payload={"mover_id": mover_id, "reason": reason},
    )


def ev_opportunity_attack_triggered(
    *,
    seq: int,
    t: int,
    round_: int,
    turn_owner_id: str,
    mover_id: str,
    threatened_by_id: str,
    reach_ft: int,
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="OpportunityAttackTriggered",
        round=round_,
        turn_owner_id=turn_owner_id,
        actor_id=threatened_by_id,
        payload={
            "mover_id": mover_id,
            "threatened_by_id": threatened_by_id,
            "reach_ft": reach_ft,
        },
    )


def ev_reaction_window_opened(
    *,
    seq: int,
    t: int,
    round_: int,
    turn_owner_id: str,
    window_id: str,
    trigger: str,
    eligible_reactors: list[str],
    context: dict,
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="ReactionWindowOpened",
        round=round_,
        turn_owner_id=turn_owner_id,
        actor_id=None,
        payload={
            "window_id": window_id,
            "trigger": trigger,
            "eligible_reactors": eligible_reactors,
            "context": context,
        },
    )


def ev_reaction_window_closed(
    *, seq: int, t: int, round_: int, turn_owner_id: str, window_id: str, closed_by: str
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="ReactionWindowClosed",
        round=round_,
        turn_owner_id=turn_owner_id,
        actor_id=None,
        payload={"window_id": window_id, "closed_by": closed_by},
    )


def ev_attack_declared(
    *,
    seq: int,
    t: int,
    round_: int,
    turn_owner_id: str,
    attacker_id: str,
    target_id: str,
    attack_name: str,
    attack_kind: Literal["melee", "ranged"] = "melee",
    context: Literal["action", "reaction"] = "action",
    economy: Literal["action", "bonus", "reaction"] = "action",
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="AttackDeclared",
        round=round_,
        turn_owner_id=turn_owner_id,
        actor_id=attacker_id,
        payload={
            "attacker_id": attacker_id,
            "target_id": target_id,
            "attack_name": attack_name,
            "attack_kind": attack_kind,
            "context": context,
            "economy": economy,
        },
    )


def ev_multiattack_declared(
    *,
    seq: int,
    t: int,
    round_: int,
    turn_owner_id: str,
    attacker_id: str,
    target_id: str,
    multiattack_name: str,
    attacks: list[str],
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="MultiattackDeclared",
        round=round_,
        turn_owner_id=turn_owner_id,
        actor_id=attacker_id,
        payload={
            "attacker_id": attacker_id,
            "target_id": target_id,
            "multiattack_name": multiattack_name,
            "attacks": attacks,
        },
    )


def ev_attack_rolled(
    *,
    seq: int,
    t: int,
    round_: int,
    turn_owner_id: str,
    attacker_id: str,
    target_id: str,
    roll: Roll,
    to_hit_bonus: int,
    target_ac: int,
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="AttackRolled",
        round=round_,
        turn_owner_id=turn_owner_id,
        actor_id=attacker_id,
        payload={
            "attacker_id": attacker_id,
            "target_id": target_id,
            "roll": roll.model_dump(),
            "to_hit_bonus": to_hit_bonus,
            "target_ac": target_ac,
        },
    )


def ev_hit_confirmed(
    *,
    seq: int,
    t: int,
    round_: int,
    turn_owner_id: str,
    attacker_id: str,
    target_id: str,
    is_critical: bool,
    margin: int,
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="HitConfirmed",
        round=round_,
        turn_owner_id=turn_owner_id,
        actor_id=attacker_id,
        payload={
            "attacker_id": attacker_id,
            "target_id": target_id,
            "is_critical": is_critical,
            "margin": margin,
        },
    )


def ev_miss_confirmed(
    *,
    seq: int,
    t: int,
    round_: int,
    turn_owner_id: str,
    attacker_id: str,
    target_id: str,
    margin: int,
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="MissConfirmed",
        round=round_,
        turn_owner_id=turn_owner_id,
        actor_id=attacker_id,
        payload={"attacker_id": attacker_id, "target_id": target_id, "margin": margin},
    )


def ev_damage_rolled(
    *,
    seq: int,
    t: int,
    round_: int,
    turn_owner_id: str,
    attacker_id: str,
    target_id: str,
    roll: Roll,
    damage_type: str,
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="DamageRolled",
        round=round_,
        turn_owner_id=turn_owner_id,
        actor_id=attacker_id,
        payload={
            "attacker_id": attacker_id,
            "target_id": target_id,
            "roll": roll.model_dump(),
            "damage_type": damage_type,
        },
    )


def ev_damage_applied(
    *,
    seq: int,
    t: int,
    round_: int,
    turn_owner_id: str,
    attacker_id: str,
    target_id: str,
    raw: int,
    adjusted: int,
    damage_type: str,
    hp_before: int,
    hp_after: int,
    is_critical: bool = False,  # ✅ добавили
    modifier: str | None = None,  # (опционально)
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="DamageApplied",
        round=round_,
        turn_owner_id=turn_owner_id,
        actor_id=attacker_id,
        payload={
            "attacker_id": attacker_id,
            "target_id": target_id,
            "raw": raw,
            "adjusted": adjusted,
            "damage_type": damage_type,
            "hp_before": hp_before,
            "hp_after": hp_after,
            "is_critical": is_critical,
            "modifier": modifier,
        },
    )


def ev_turn_ended(
    *, seq: int, t: int, round_: int, turn_owner_id: str
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="TurnEnded",
        round=round_,
        turn_owner_id=turn_owner_id,
        actor_id=turn_owner_id,
        payload={"combatant_id": turn_owner_id},
    )


def ev_condition_applied(
    *,
    seq: int,
    t: int,
    round_: int,
    turn_owner_id,
    actor_id,
    target_id: str,
    condition: str,
    reason: str = "effect",
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="ConditionApplied",
        round=round_,
        turn_owner_id=turn_owner_id,
        actor_id=actor_id,
        payload={"target_id": target_id, "condition": condition, "reason": reason},
    )


def ev_condition_removed(
    *,
    seq: int,
    t: int,
    round_: int,
    turn_owner_id,
    actor_id,
    target_id: str,
    condition: str,
    reason: str = "effect",
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="ConditionRemoved",
        round=round_,
        turn_owner_id=turn_owner_id,
        actor_id=actor_id,
        payload={"target_id": target_id, "condition": condition, "reason": reason},
    )


def ev_unconscious_state_changed(
    *,
    seq: int,
    t: int,
    round_: int,
    target_id: str,
    became_unconscious: bool,
    reason: str,
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="UnconsciousStateChanged",
        round=round_,
        turn_owner_id=None,
        actor_id=None,
        payload={
            "target_id": target_id,
            "became_unconscious": became_unconscious,
            "reason": reason,
        },
    )


def ev_save_effect_declared(
    *,
    seq: int,
    t: int,
    round_: int,
    turn_owner_id,
    actor_id: str,
    source_id: str,
    target_ids: list[str],
    effect_name: str,
    save_ability: str,
    dc: int,
    adv_state: str,
    on_success: str,
    damage_type: str,
    damage_formula: str,
    economy: str,
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="SaveEffectDeclared",
        round=round_,
        turn_owner_id=turn_owner_id,
        actor_id=actor_id,
        payload={
            "source_id": source_id,
            "target_ids": target_ids,
            "effect_name": effect_name,
            "save_ability": save_ability,
            "dc": dc,
            "adv_state": adv_state,
            "on_success": on_success,
            "damage_type": damage_type,
            "damage_formula": damage_formula,
            "economy": economy,
        },
    )


def ev_saving_throw_rolled(
    *,
    seq: int,
    t: int,
    round_: int,
    turn_owner_id,
    actor_id: str,
    source_id: str,
    target_id: str,
    effect_name: str,
    roll: Roll,
    save_ability: str,
    dc: int,
    bonus: int,
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="SavingThrowRolled",
        round=round_,
        turn_owner_id=turn_owner_id,
        actor_id=actor_id,
        payload={
            "source_id": source_id,
            "target_id": target_id,
            "effect_name": effect_name,
            "save_ability": save_ability,
            "dc": dc,
            "bonus": bonus,
            "roll": roll.model_dump(),
        },
    )


def ev_saving_throw_succeeded(
    *,
    seq: int,
    t: int,
    round_: int,
    turn_owner_id,
    actor_id: str,
    source_id: str,
    target_id: str,
    effect_name: str,
    margin: int,
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="SavingThrowSucceeded",
        round=round_,
        turn_owner_id=turn_owner_id,
        actor_id=actor_id,
        payload={
            "source_id": source_id,
            "target_id": target_id,
            "effect_name": effect_name,
            "margin": margin,
        },
    )


def ev_saving_throw_failed(
    *,
    seq: int,
    t: int,
    round_: int,
    turn_owner_id,
    actor_id: str,
    source_id: str,
    target_id: str,
    effect_name: str,
    margin: int,
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="SavingThrowFailed",
        round=round_,
        turn_owner_id=turn_owner_id,
        actor_id=actor_id,
        payload={
            "source_id": source_id,
            "target_id": target_id,
            "effect_name": effect_name,
            "margin": margin,
        },
    )


def ev_effect_damage_rolled(
    *,
    seq: int,
    t: int,
    round_: int,
    turn_owner_id,
    actor_id: str,
    source_id: str,
    target_id: str,
    effect_name: str,
    roll: Roll,
    damage_type: str,
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="EffectDamageRolled",
        round=round_,
        turn_owner_id=turn_owner_id,
        actor_id=actor_id,
        payload={
            "source_id": source_id,
            "target_id": target_id,
            "effect_name": effect_name,
            "damage_type": damage_type,
            "roll": roll.model_dump(),
        },
    )


def ev_effect_damage_applied(
    *,
    seq: int,
    t: int,
    round_: int,
    turn_owner_id,
    actor_id: str,
    source_id: str,
    target_id: str,
    effect_name: str,
    raw: int,
    adjusted: int,
    damage_type: str,
    hp_before: int,
    hp_after: int,
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="EffectDamageApplied",
        round=round_,
        turn_owner_id=turn_owner_id,
        actor_id=actor_id,
        payload={
            "source_id": source_id,
            "target_id": target_id,
            "effect_name": effect_name,
            "damage_type": damage_type,
            "raw": raw,
            "adjusted": adjusted,
            "hp_before": hp_before,
            "hp_after": hp_after,
        },
    )


def ev_save_effect_negated(
    *,
    seq: int,
    t: int,
    round_: int,
    turn_owner_id,
    actor_id: str,
    source_id: str,
    target_id: str,
    effect_name: str,
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="SaveEffectNegated",
        round=round_,
        turn_owner_id=turn_owner_id,
        actor_id=actor_id,
        payload={
            "source_id": source_id,
            "target_id": target_id,
            "effect_name": effect_name,
        },
    )


def ev_death_save_required(
    *, seq: int, t: int, round_: int, combatant_id: str
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="DeathSaveRequired",
        round=round_,
        turn_owner_id=combatant_id,
        actor_id=combatant_id,
        payload={"combatant_id": combatant_id},
    )


def ev_death_save_rolled(
    *, seq: int, t: int, round_: int, combatant_id: str, roll: Roll
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="DeathSaveRolled",
        round=round_,
        turn_owner_id=combatant_id,
        actor_id=combatant_id,
        payload={"combatant_id": combatant_id, "roll": roll.model_dump()},
    )


def ev_death_save_result(
    *,
    seq: int,
    t: int,
    round_: int,
    combatant_id: str,
    successes: int,
    failures: int,
    outcome: str,
) -> EventEnvelope:
    # outcome: "success"|"fail"|"crit_success"|"crit_fail"|"stabilized"|"dead"|"revived"
    return EventEnvelope(
        seq=seq,
        t=t,
        type="DeathSaveResult",
        round=round_,
        turn_owner_id=combatant_id,
        actor_id=combatant_id,
        payload={
            "combatant_id": combatant_id,
            "successes": successes,
            "failures": failures,
            "outcome": outcome,
        },
    )


def ev_stabilized(
    *, seq: int, t: int, round_: int, healer_id: str | None, target_id: str, reason: str
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="Stabilized",
        round=round_,
        turn_owner_id=None,
        actor_id=healer_id,
        payload={"healer_id": healer_id, "target_id": target_id, "reason": reason},
    )


def ev_died(
    *, seq: int, t: int, round_: int, target_id: str, reason: str
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="Died",
        round=round_,
        turn_owner_id=None,
        actor_id=None,
        payload={"target_id": target_id, "reason": reason},
    )


def ev_healed(
    *,
    seq: int,
    t: int,
    round_: int,
    healer_id: str | None,
    target_id: str,
    amount: int,
    hp_before: int,
    hp_after: int,
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="Healed",
        round=round_,
        turn_owner_id=None,
        actor_id=healer_id,
        payload={
            "healer_id": healer_id,
            "target_id": target_id,
            "amount": amount,
            "hp_before": hp_before,
            "hp_after": hp_after,
        },
    )


def ev_concentration_started(
    *,
    seq: int,
    t: int,
    round_: int,
    combatant_id: str,
    effect_name: str,
    source_id: str,
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="ConcentrationStarted",
        round=round_,
        turn_owner_id=combatant_id,
        actor_id=combatant_id,
        payload={
            "combatant_id": combatant_id,
            "effect_name": effect_name,
            "source_id": source_id,
        },
    )


def ev_concentration_ended(
    *,
    seq: int,
    t: int,
    round_: int,
    combatant_id: str,
    effect_name: str | None,
    reason: str,
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="ConcentrationEnded",
        round=round_,
        turn_owner_id=combatant_id,
        actor_id=combatant_id,
        payload={
            "combatant_id": combatant_id,
            "effect_name": effect_name,
            "reason": reason,
        },
    )


def ev_concentration_check_triggered(
    *,
    seq: int,
    t: int,
    round_: int,
    combatant_id: str,
    dc: int,
    damage_taken: int,
    damage_type: str | None,
    cause: str,
    source_id: str | None,
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="ConcentrationCheckTriggered",
        round=round_,
        turn_owner_id=combatant_id,
        actor_id=combatant_id,
        payload={
            "combatant_id": combatant_id,
            "dc": dc,
            "damage_taken": damage_taken,
            "damage_type": damage_type,
            "cause": cause,  # "attack" | "effect"
            "source_id": source_id,  # кто нанёс урон
        },
    )


def ev_concentration_check_rolled(
    *, seq: int, t: int, round_: int, combatant_id: str, dc: int, roll: Roll, bonus: int
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="ConcentrationCheckRolled",
        round=round_,
        turn_owner_id=combatant_id,
        actor_id=combatant_id,
        payload={
            "combatant_id": combatant_id,
            "dc": dc,
            "bonus": bonus,
            "roll": roll.model_dump(),
        },
    )


def ev_concentration_maintained(
    *, seq: int, t: int, round_: int, combatant_id: str, dc: int, total: int
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="ConcentrationMaintained",
        round=round_,
        turn_owner_id=combatant_id,
        actor_id=combatant_id,
        payload={"combatant_id": combatant_id, "dc": dc, "total": total},
    )


def ev_concentration_broken(
    *,
    seq: int,
    t: int,
    round_: int,
    combatant_id: str,
    dc: int,
    total: int,
    reason: str,
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="ConcentrationBroken",
        round=round_,
        turn_owner_id=combatant_id,
        actor_id=combatant_id,
        payload={
            "combatant_id": combatant_id,
            "dc": dc,
            "total": total,
            "reason": reason,
        },
    )


def ev_spell_cast_declared(
    *,
    seq: int,
    t: int,
    round_: int,
    turn_owner_id: str,
    caster_id: str,
    spell_name: str,
    slot_level: int,
    target_ids: list[str],
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="SpellCastDeclared",
        round=round_,
        turn_owner_id=turn_owner_id,
        actor_id=caster_id,
        payload={
            "caster_id": caster_id,
            "spell_name": spell_name,
            "slot_level": slot_level,
            "target_ids": target_ids,
        },
    )


def ev_spell_slot_spent(
    *,
    seq: int,
    t: int,
    round_: int,
    caster_id: str,
    slot_level: int,
    before: int,
    after: int,
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="SpellSlotSpent",
        round=round_,
        turn_owner_id=caster_id,
        actor_id=caster_id,
        payload={
            "caster_id": caster_id,
            "slot_level": slot_level,
            "before": before,
            "after": after,
        },
    )


def ev_effect_applied(
    *,
    seq: int,
    t: int,
    round_: int,
    turn_owner_id: str | None,
    effect_id: str,
    effect_name: str,
    source_id: str,
    target_id: str,
    concentration_owner_id: str | None,
    concentration_effect_name: str | None,
    conditions: list[str],
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="EffectApplied",
        round=round_,
        turn_owner_id=turn_owner_id,
        actor_id=source_id,
        payload={
            "effect_id": effect_id,
            "effect_name": effect_name,
            "source_id": source_id,
            "target_id": target_id,
            "concentration_owner_id": concentration_owner_id,
            "concentration_effect_name": concentration_effect_name,
            "conditions": conditions,
        },
    )


def ev_effect_ended(
    *,
    seq: int,
    t: int,
    round_: int,
    turn_owner_id: str | None,
    effect_id: str,
    effect_name: str,
    target_id: str,
    reason: str,
    removed_conditions: list[str],
) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="EffectEnded",
        round=round_,
        turn_owner_id=turn_owner_id,
        actor_id=None,
        payload={
            "effect_id": effect_id,
            "effect_name": effect_name,
            "target_id": target_id,
            "reason": reason,
            "removed_conditions": removed_conditions,
        },
    )
