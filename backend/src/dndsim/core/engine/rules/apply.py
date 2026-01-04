from __future__ import annotations

import re
from typing import List, Tuple, Literal, cast

from dndsim.core.engine.spells.registry import get_spell

from dndsim.core.engine.spells.resolve import resolve_save_spell, resolve_attack_spell
from dndsim.core.engine.spells.definitions import SaveSpell, AttackSpell

from dndsim.core.engine.rules.middleware import (
    DEFAULT_ROLL_MIDDLEWARES,
    AttackRollContext,
    SaveRollContext,
    DamageRollContext,
    apply_roll_mods,
)

from dndsim.core.engine.commands import (
    StartCombat,
    SetInitiative,
    RollInitiative,
    FinalizeInitiative,
    Attack,
    Multiattack,
    BeginTurn,
    EndTurn,
    Move,
    UseReaction,
    DeclineReaction,
    Disengage,
    Command,
    SaveEffect,
    RollDeathSave,
    Stabilize,
    Heal,
    StartConcentration,
    EndConcentration,
    CastSpell,
)

from dndsim.core.engine.events import (
    Roll,
    RollMod,
    ev_command_rejected,
    ev_turn_started,
    ev_turn_resources_reset,
    ev_turn_ended,
    ev_disengage_applied,
    ev_movement_started,
    ev_moved_step,
    ev_movement_stopped,
    ev_opportunity_attack_triggered,
    ev_reaction_window_opened,
    ev_reaction_window_closed,
    ev_attack_declared,
    ev_multiattack_declared,
    ev_attack_rolled,
    ev_hit_confirmed,
    ev_miss_confirmed,
    ev_damage_rolled,
    ev_damage_applied,
    ev_combat_started,
    ev_initiative_set,
    ev_initiative_rolled,
    ev_initiative_order_finalized,
    ev_round_started,
    ev_save_effect_declared,
    ev_saving_throw_rolled,
    ev_saving_throw_succeeded,
    ev_saving_throw_failed,
    ev_effect_damage_rolled,
    ev_effect_damage_applied,
    ev_save_effect_negated,
    ev_death_save_required,
    ev_death_save_rolled,
    ev_death_save_result,
    ev_stabilized,
    ev_died,
    ev_healed,
    ev_concentration_started,
    ev_concentration_ended,
    ev_concentration_check_triggered,
    ev_concentration_check_rolled,
    ev_concentration_maintained,
    ev_concentration_broken,
    ev_spell_cast_declared,
    ev_spell_slot_spent,
    ev_effect_ended,
)
from dndsim.core.engine.rules.validator import validate_command
from dndsim.core.engine.state import (
    EncounterState,
    ReactionWindow,
    Pos,
    effective_speed_ft,
    are_hostile,
    CombatantState,
    EffectRef,
)

from dndsim.core.engine.commands import ApplyCondition, RemoveCondition
from dndsim.core.engine.events import (
    ev_condition_applied,
    ev_condition_removed,
    ev_unconscious_state_changed,
)

AdvState = Literal["normal", "advantage", "disadvantage"]
Economy = Literal["action", "bonus", "reaction"]

_DICE_RE = re.compile(r"^\s*(\d+)d(\d+)\s*([+-]\s*\d+)?\s*$")


def _parse_dice(formula: str) -> Tuple[int, int, int]:
    m = _DICE_RE.match(formula)
    if not m:
        raise ValueError(f"Unsupported dice formula: {formula!r}")
    n = int(m.group(1))
    d = int(m.group(2))
    mod = m.group(3)
    k = int(mod.replace(" ", "")) if mod else 0
    return n, d, k


def _end_effects_by_concentration(
    state: EncounterState,
    *,
    concentration_owner_id: str,
    concentration_effect_name: str,
    reason: str,
) -> list[dict]:
    evs: list[dict] = []
    to_end = [
        ef
        for ef in state.effects.values()
        if ef.concentration_owner_id == concentration_owner_id
        and ef.concentration_effect_name == concentration_effect_name
    ]

    for ef in to_end:
        target = state.combatants.get(ef.target_id)
        removed: list[str] = []
        if target is not None:
            for cond in ef.applies_conditions:
                if cond in target.conditions:
                    target.conditions.remove(cond)
                    removed.append(cond)
                    seq, t = _bump(state)
                    evs.append(
                        ev_condition_removed(
                            seq=seq,
                            t=t,
                            round_=state.round,
                            turn_owner_id=state.turn_owner_id,
                            actor_id=None,
                            target_id=target.id,
                            condition=cond,
                            reason=f"effect_end:{ef.name}",
                        ).model_dump()
                    )

        # удаляем эффект
        state.effects.pop(ef.id, None)

        seq, t = _bump(state)
        evs.append(
            ev_effect_ended(
                seq=seq,
                t=t,
                round_=state.round,
                turn_owner_id=state.turn_owner_id,
                effect_id=ef.id,
                effect_name=ef.name,
                target_id=ef.target_id,
                reason=reason,
                removed_conditions=removed,
            ).model_dump()
        )

    return evs


def _apply_damage_with_temp_hp(
    target: CombatantState, dmg: int
) -> tuple[int, int, int]:
    """
    return (temp_hp_before, hp_before, hp_after)
    """
    temp_before = target.temp_hp
    hp_before = target.hp_current

    remaining = max(0, dmg)

    if target.temp_hp > 0 and remaining > 0:
        absorbed = min(target.temp_hp, remaining)
        target.temp_hp -= absorbed
        remaining -= absorbed

    if remaining > 0:
        target.hp_current = max(0, target.hp_current - remaining)

    return temp_before, hp_before, target.hp_current


def _roll_d20(
    state: EncounterState,
    bonus: int,
    adv_state: AdvState,
) -> Roll:
    if adv_state == "normal":
        nat = state.rng.randint(1, 20)
        total = nat + bonus
        return Roll(
            kind="d20",
            formula=f"1d20+{bonus}",
            dice=[nat],
            kept=[nat],
            mods=[RollMod(name="to_hit_bonus", value=bonus)],
            total=total,
            nat=nat,
            is_critical=(nat == 20),
            adv_state="normal",
        )

    a = state.rng.randint(1, 20)
    b = state.rng.randint(1, 20)
    kept = max(a, b) if adv_state == "advantage" else min(a, b)
    total = kept + bonus

    return Roll(
        kind="d20",
        formula=f"2d20+{bonus} ({adv_state})",
        dice=[a, b],
        kept=[kept],
        mods=[RollMod(name="to_hit_bonus", value=bonus)],
        total=total,
        nat=kept,
        is_critical=(kept == 20),
        adv_state=adv_state,
    )


def _maybe_run_concentration_check(
    state: EncounterState,
    target: CombatantState,
    *,
    damage_taken: int,
    damage_type: str | None,
    cause: str,  # "attack" | "effect"
    source_id: str | None,
) -> list[dict]:
    """
    Если target.concentration есть и он получил урон > 0:
      - если стал unconscious (hp==0) -> концентрация ломается без сейва (incapacitated)
      - иначе: CON save DC=max(10, dmg//2)
    """
    evs: list[dict] = []
    if target.concentration is None:
        return evs
    if damage_taken <= 0:
        return evs
    if target.is_dead:
        return evs

    # Если существо стало unconscious -> оно incapacitated -> концентрация сразу кончается
    if target.hp_current == 0 or "unconscious" in target.conditions:
        effect_name = target.concentration.effect_name
        target.concentration = None

        seq, t = _bump(state)
        evs.append(
            ev_concentration_broken(
                seq=seq,
                t=t,
                round_=state.round,
                combatant_id=target.id,
                dc=0,
                total=0,
                reason="incapacitated",
            ).model_dump()
        )

        seq, t = _bump(state)
        evs.append(
            ev_concentration_ended(
                seq=seq,
                t=t,
                round_=state.round,
                combatant_id=target.id,
                effect_name=effect_name,
                reason="incapacitated",
            ).model_dump()
        )
        return evs

    dc = max(10, damage_taken // 2)

    seq, t = _bump(state)
    evs.append(
        ev_concentration_check_triggered(
            seq=seq,
            t=t,
            round_=state.round,
            combatant_id=target.id,
            dc=dc,
            damage_taken=damage_taken,
            damage_type=damage_type,
            cause=cause,
            source_id=source_id,
        ).model_dump()
    )

    bonus = int(target.save_bonuses.get("con", 0))
    roll = _roll_save(state, bonus=bonus, adv_state="normal")

    seq, t = _bump(state)
    evs.append(
        ev_concentration_check_rolled(
            seq=seq,
            t=t,
            round_=state.round,
            combatant_id=target.id,
            dc=dc,
            roll=roll,
            bonus=bonus,
        ).model_dump()
    )

    if roll.total >= dc:
        seq, t = _bump(state)
        evs.append(
            ev_concentration_maintained(
                seq=seq,
                t=t,
                round_=state.round,
                combatant_id=target.id,
                dc=dc,
                total=roll.total,
            ).model_dump()
        )
        return evs

    # fail -> broken + ended
    effect_name = target.concentration.effect_name
    target.concentration = None

    seq, t = _bump(state)
    evs.append(
        ev_concentration_broken(
            seq=seq,
            t=t,
            round_=state.round,
            combatant_id=target.id,
            dc=dc,
            total=roll.total,
            reason="failed_save",
        ).model_dump()
    )

    seq, t = _bump(state)
    evs.append(
        ev_concentration_ended(
            seq=seq,
            t=t,
            round_=state.round,
            combatant_id=target.id,
            effect_name=effect_name,
            reason="failed_save",
        ).model_dump()
    )
    return evs


def _before_attack_roll(
    state: EncounterState,
    *,
    attacker: CombatantState,
    target: CombatantState,
    attack_name: str,
    source: str,  # "weapon"|"spell"
    roll: Roll,
) -> Roll:
    ctx = AttackRollContext(
        attacker_id=attacker.id,
        target_id=target.id,
        attack_name=attack_name,
        source=cast(Literal["weapon", "spell"], source),
    )
    mods = []
    for mw in DEFAULT_ROLL_MIDDLEWARES:
        mods.extend(mw.before_attack_roll(state, attacker, target, ctx, roll))
    return apply_roll_mods(roll, mods)


def _before_save_roll(
    state: EncounterState,
    *,
    roller: CombatantState,
    save_ability: str,
    source_id: str | None,
    effect_name: str,
    roll: Roll,
) -> Roll:
    ctx = SaveRollContext(
        roller_id=roller.id,
        save_ability=save_ability,
        source_id=source_id,
        effect_name=effect_name,
    )
    mods = []
    for mw in DEFAULT_ROLL_MIDDLEWARES:
        mods.extend(mw.before_save_roll(state, roller, ctx, roll))
    return apply_roll_mods(roll, mods)


def _before_damage_roll(
    state: EncounterState,
    *,
    source: CombatantState,
    target: CombatantState,
    damage_type: str,
    source_kind: str,  # "weapon"|"spell"|"effect"
    roll: Roll,
) -> Roll:
    ctx = DamageRollContext(
        source_id=source.id,
        target_id=target.id,
        damage_type=damage_type,
        source=cast(Literal["weapon", "spell", "effect"], source_kind),
    )
    mods = []
    for mw in DEFAULT_ROLL_MIDDLEWARES:
        mods.extend(mw.before_damage_roll(state, source, target, ctx, roll))
    return apply_roll_mods(roll, mods)


def _roll_save(
    state: EncounterState,
    bonus: int,
    adv_state: Literal["normal", "advantage", "disadvantage"],
) -> Roll:
    # как d20, но мод называется "save_bonus"
    if adv_state == "normal":
        nat = state.rng.randint(1, 20)
        total = nat + bonus
        return Roll(
            kind="d20",
            formula=f"1d20+{bonus} (save)",
            dice=[nat],
            kept=[nat],
            mods=[RollMod(name="save_bonus", value=bonus)],
            total=total,
            nat=nat,
            is_critical=False,
            adv_state="normal",
        )

    a = state.rng.randint(1, 20)
    b = state.rng.randint(1, 20)
    kept = max(a, b) if adv_state == "advantage" else min(a, b)
    total = kept + bonus
    return Roll(
        kind="d20",
        formula=f"2d20+{bonus} ({adv_state} save)",
        dice=[a, b],
        kept=[kept],
        mods=[RollMod(name="save_bonus", value=bonus)],
        total=total,
        nat=kept,
        is_critical=False,
        adv_state=adv_state,
    )


def _adjust_damage_for_target(
    target: CombatantState, raw: int, damage_type: str
) -> tuple[int, str | None]:
    """
    Возвращает (adjusted_damage, modifier), где modifier: "immune"|"resistant"|"vulnerable"|None
    Правила 5e:
      immune -> 0
      resistant -> половина, округление вниз
      vulnerable -> x2
    Приоритет: immunity > resistance/vulnerability.
    """
    if raw <= 0:
        return 0, None

    dt = (damage_type or "").lower().strip()

    if dt in target.damage_immunities:
        return 0, "immune"

    # Если одновременно resist и vuln (редко, но возможно) — они “взаимно нейтрализуются” (x1).
    is_res = dt in target.damage_resistances
    is_vul = dt in target.damage_vulnerabilities

    if is_res and is_vul:
        return raw, None

    if is_res:
        return raw // 2, "resistant"

    if is_vul:
        return raw * 2, "vulnerable"

    return raw, None


def _roll_damage(state: EncounterState, formula: str, crit: bool) -> Roll:
    n, d, k = _parse_dice(formula)
    dice_count = n * 2 if crit else n
    rolls = [state.rng.randint(1, d) for _ in range(dice_count)]
    total = sum(rolls) + k

    mods = []
    if k != 0:
        mods.append(RollMod(name="flat_mod", value=k))

    return Roll(
        kind="damage",
        formula=formula + (" (CRIT x2 dice)" if crit else ""),
        dice=rolls,
        kept=rolls,
        mods=mods,
        total=total,
        nat=None,
        is_critical=crit,
        adv_state="normal",
    )


def _bump(state: EncounterState) -> Tuple[int, int]:
    state.seq += 1
    state.t += 1
    return state.seq, state.t


def _adjacent(a: Pos, b: Pos) -> bool:
    dx = abs(a[0] - b[0])
    dy = abs(a[1] - b[1])
    return (dx <= 1 and dy <= 1) and not (dx == 0 and dy == 0)


def _combine_adv(*states: AdvState) -> AdvState:
    has_adv = any(s == "advantage" for s in states)
    has_dis = any(s == "disadvantage" for s in states)
    if has_adv and has_dis:
        return "normal"
    if has_adv:
        return "advantage"
    if has_dis:
        return "disadvantage"
    return "normal"


def _in_reach(attacker_pos: Pos, target_pos: Pos, reach_ft: int) -> bool:
    # MVP: reach_ft 5 => соседняя клетка (включая диагональ)
    # Для reach 10 можно будет расширить позже.
    if reach_ft <= 5:
        dx = abs(attacker_pos[0] - target_pos[0])
        dy = abs(attacker_pos[1] - target_pos[1])
        return (dx <= 1 and dy <= 1) and not (dx == 0 and dy == 0)
    # очень грубо: по квадратам
    max_squares = max(1, reach_ft // 5)
    dx = abs(attacker_pos[0] - target_pos[0])
    dy = abs(attacker_pos[1] - target_pos[1])
    return max(dx, dy) <= max_squares


def _resolve_attack(
    state: EncounterState,
    attacker_id: str,
    target_id: str,
    attack_name: str,
    *,
    context: Literal["action", "reaction"],
    attack_kind: Literal["melee", "ranged"],
    adv_state: Literal["normal", "advantage", "disadvantage"],
    economy: Economy,
    spend_action: bool,
    spend_reaction: bool,
) -> List[dict]:
    events: List[dict] = []
    attacker = state.combatants[attacker_id]
    target = state.combatants[target_id]
    profile = attacker.attacks[attack_name]

    cond_adv_sources: list[AdvState] = []

    # restrained: атакующий с restrained атакует с помехой
    if "restrained" in attacker.conditions:
        cond_adv_sources.append("disadvantage")

    # unconscious: цель -> атаки по ней с преимуществом
    if "unconscious" in target.conditions:
        cond_adv_sources.append("advantage")

    # restrained: атаки по restrained цели с преимуществом
    if "restrained" in target.conditions:
        cond_adv_sources.append("advantage")

    # prone: melee по prone с преимуществом, ranged с помехой
    if "prone" in target.conditions:
        cond_adv_sources.append(
            "advantage" if attack_kind == "melee" else "disadvantage"
        )

    final_adv: AdvState = _combine_adv(adv_state, *cond_adv_sources)  # cmd + conditions

    if spend_action:
        attacker.action_available = False
    if spend_reaction:
        attacker.reaction_available = False

    seq, t = _bump(state)
    events.append(
        ev_attack_declared(
            seq=seq,
            t=t,
            round_=state.round,
            turn_owner_id=state.turn_owner_id or attacker_id,
            attacker_id=attacker_id,
            target_id=target_id,
            attack_name=attack_name,
            attack_kind=attack_kind,
            context=context,
            economy=economy,
        ).model_dump()
    )

    atk_roll = _roll_d20(state, profile.to_hit_bonus, adv_state=final_adv)
    atk_roll = _before_attack_roll(
        state,
        attacker=attacker,
        target=target,
        attack_name=attack_name,
        source="weapon",
        roll=atk_roll,
    )

    seq, t = _bump(state)
    events.append(
        ev_attack_rolled(
            seq=seq,
            t=t,
            round_=state.round,
            turn_owner_id=state.turn_owner_id or attacker_id,
            attacker_id=attacker_id,
            target_id=target_id,
            roll=atk_roll,
            to_hit_bonus=profile.to_hit_bonus,
            target_ac=target.ac,
        ).model_dump()
    )

    # auto miss on nat1
    if atk_roll.nat == 1:
        margin = atk_roll.total - target.ac
        seq, t = _bump(state)
        events.append(
            ev_miss_confirmed(
                seq=seq,
                t=t,
                round_=state.round,
                turn_owner_id=state.turn_owner_id or attacker_id,
                attacker_id=attacker_id,
                target_id=target_id,
                margin=margin,
            ).model_dump()
        )
        return events

    hit = atk_roll.total >= target.ac
    # “unconscious”: если попадание и атакующий в 5 футах — это крит
    unconscious_crit = False
    if hit and "unconscious" in target.conditions:
        if _in_reach(attacker.position, target.position, reach_ft=5):
            unconscious_crit = True

    final_crit = atk_roll.is_critical or unconscious_crit

    margin = atk_roll.total - target.ac
    if not hit:
        seq, t = _bump(state)
        events.append(
            ev_miss_confirmed(
                seq=seq,
                t=t,
                round_=state.round,
                turn_owner_id=state.turn_owner_id or attacker_id,
                attacker_id=attacker_id,
                target_id=target_id,
                margin=margin,
            ).model_dump()
        )
        return events

    seq, t = _bump(state)
    events.append(
        ev_hit_confirmed(
            seq=seq,
            t=t,
            round_=state.round,
            turn_owner_id=state.turn_owner_id or attacker_id,
            attacker_id=attacker_id,
            target_id=target_id,
            is_critical=atk_roll.is_critical,
            margin=margin,
        ).model_dump()
    )

    dmg_roll = _roll_damage(state, profile.damage_formula, crit=final_crit)
    dmg_roll = _before_damage_roll(
        state,
        source=attacker,
        target=target,
        damage_type=profile.damage_type,
        source_kind="weapon",
        roll=dmg_roll,
    )
    seq, t = _bump(state)
    events.append(
        ev_damage_rolled(
            seq=seq,
            t=t,
            round_=state.round,
            turn_owner_id=state.turn_owner_id or attacker_id,
            attacker_id=attacker_id,
            target_id=target_id,
            roll=dmg_roll,
            damage_type=profile.damage_type,
        ).model_dump()
    )

    raw = dmg_roll.total
    adjusted, mod = _adjust_damage_for_target(target, raw, profile.damage_type)

    temp_before, hp_before, hp_after = _apply_damage_with_temp_hp(target, adjusted)

    if hp_after == 0 and "unconscious" not in target.conditions:
        target.conditions.add("unconscious")
        target.reaction_available = False

        if target.is_player_character:
            target.is_stable = False
            target.is_dead = False
            # death saves начинаются с 0/0, но не перезаписывай если уже копятся?
            # MVP: перезапускаем только если были >0 HP
            target.death_save_successes = 0
            target.death_save_failures = 0

        seq, t = _bump(state)
        events.append(
            ev_condition_applied(
                seq=seq,
                t=t,
                round_=state.round,
                turn_owner_id=state.turn_owner_id,
                actor_id=None,
                target_id=target.id,
                condition="unconscious",
                reason="hp_0",
            ).model_dump()
        )

        seq, t = _bump(state)
        events.append(
            ev_unconscious_state_changed(
                seq=seq,
                t=t,
                round_=state.round,
                target_id=target.id,
                became_unconscious=True,
                reason="hp_0",
            ).model_dump()
        )

    seq, t = _bump(state)
    events.append(
        ev_damage_applied(
            seq=seq,
            t=t,
            round_=state.round,
            turn_owner_id=state.turn_owner_id or attacker_id,
            attacker_id=attacker_id,
            target_id=target_id,
            raw=raw,
            adjusted=adjusted,
            damage_type=profile.damage_type,
            hp_before=hp_before,
            hp_after=hp_after,
        ).model_dump()
    )
    events[-1]["payload"]["modifier"] = mod
    events[-1]["payload"]["is_critical"] = final_crit  # <-- вместо параметра

    # NEW: concentration check on damage (attack)
    events.extend(
        _maybe_run_concentration_check(
            state,
            target,
            damage_taken=adjusted,  # именно фактически нанесённый урон
            damage_type=profile.damage_type,
            cause="attack",
            source_id=attacker_id,
        )
    )

    return events


def _resolve_spell_attack(
    state: EncounterState,
    *,
    caster_id: str,
    target_id: str,
    spell_name: str,
    to_hit_bonus: int,
    damage_formula: str,
    damage_type: str,
    attack_kind: Literal["melee", "ranged"],
    economy: Economy,
) -> list[dict]:
    events: list[dict] = []
    turn_owner = state.turn_owner_id or caster_id
    target = state.combatants[target_id]

    # declare (используем attack_name = spell_name)
    seq, t = _bump(state)
    events.append(
        ev_attack_declared(
            seq=seq,
            t=t,
            round_=state.round,
            turn_owner_id=turn_owner,
            attacker_id=caster_id,
            target_id=target_id,
            attack_name=spell_name,
            attack_kind=attack_kind,
            context="action",
            economy=economy,
        ).model_dump()
    )

    atk_roll = _roll_d20(state, to_hit_bonus, adv_state="normal")

    seq, t = _bump(state)
    events.append(
        ev_attack_rolled(
            seq=seq,
            t=t,
            round_=state.round,
            turn_owner_id=turn_owner,
            attacker_id=caster_id,
            target_id=target_id,
            roll=atk_roll,
            to_hit_bonus=to_hit_bonus,
            target_ac=target.ac,
        ).model_dump()
    )

    # auto miss nat1
    if atk_roll.nat == 1:
        margin = atk_roll.total - target.ac
        seq, t = _bump(state)
        events.append(
            ev_miss_confirmed(
                seq=seq,
                t=t,
                round_=state.round,
                turn_owner_id=turn_owner,
                attacker_id=caster_id,
                target_id=target_id,
                margin=margin,
            ).model_dump()
        )
        return events

    hit = atk_roll.total >= target.ac
    margin = atk_roll.total - target.ac

    if not hit:
        seq, t = _bump(state)
        events.append(
            ev_miss_confirmed(
                seq=seq,
                t=t,
                round_=state.round,
                turn_owner_id=turn_owner,
                attacker_id=caster_id,
                target_id=target_id,
                margin=margin,
            ).model_dump()
        )
        return events

    # hit
    final_crit = bool(atk_roll.is_critical)

    seq, t = _bump(state)
    events.append(
        ev_hit_confirmed(
            seq=seq,
            t=t,
            round_=state.round,
            turn_owner_id=turn_owner,
            attacker_id=caster_id,
            target_id=target_id,
            is_critical=final_crit,
            margin=margin,
        ).model_dump()
    )

    dmg_roll = _roll_damage(state, damage_formula, crit=final_crit)
    seq, t = _bump(state)
    events.append(
        ev_damage_rolled(
            seq=seq,
            t=t,
            round_=state.round,
            turn_owner_id=turn_owner,
            attacker_id=caster_id,
            target_id=target_id,
            roll=dmg_roll,
            damage_type=damage_type,
        ).model_dump()
    )

    raw = int(dmg_roll.total)
    adjusted, mod = _adjust_damage_for_target(target, raw, damage_type)

    temp_before, hp_before, hp_after = _apply_damage_with_temp_hp(target, adjusted)

    # unconscious
    if hp_after == 0 and "unconscious" not in target.conditions:
        target.conditions.add("unconscious")
        target.reaction_available = False
        if target.is_player_character:
            target.is_stable = False
            target.is_dead = False
            target.death_save_successes = 0
            target.death_save_failures = 0

        seq, t = _bump(state)
        events.append(
            ev_condition_applied(
                seq=seq,
                t=t,
                round_=state.round,
                turn_owner_id=state.turn_owner_id,
                actor_id=None,
                target_id=target.id,
                condition="unconscious",
                reason="hp_0",
            ).model_dump()
        )

        seq, t = _bump(state)
        events.append(
            ev_unconscious_state_changed(
                seq=seq,
                t=t,
                round_=state.round,
                target_id=target.id,
                became_unconscious=True,
                reason="hp_0",
            ).model_dump()
        )

    # damage applied
    seq, t = _bump(state)
    events.append(
        ev_damage_applied(
            seq=seq,
            t=t,
            round_=state.round,
            turn_owner_id=turn_owner,
            attacker_id=caster_id,
            target_id=target_id,
            raw=raw,
            adjusted=adjusted,
            damage_type=damage_type,
            hp_before=hp_before,
            hp_after=hp_after,
        ).model_dump()
    )
    events[-1]["payload"]["modifier"] = mod
    events[-1]["payload"]["is_critical"] = final_crit

    # concentration check on target
    events.extend(
        _maybe_run_concentration_check(
            state,
            target,
            damage_taken=adjusted,
            damage_type=damage_type,
            cause="attack",
            source_id=caster_id,
        )
    )

    return events


def apply_command(
    state: EncounterState, cmd: Command
) -> Tuple[EncounterState, List[dict]]:
    """
    Возвращаем (state, events_as_dicts).
    При ошибке валидации возвращаем CommandRejected и НЕ меняем state.
    """
    vr = validate_command(state, cmd)
    if not vr.ok:
        e = vr.errors[0]
        seq, t = _bump(state)
        rej = ev_command_rejected(
            seq=seq,
            t=t,
            round_=state.round,
            turn_owner_id=state.turn_owner_id,
            actor_id=getattr(cmd, "combatant_id", None)
            or getattr(cmd, "attacker_id", None)
            or getattr(cmd, "mover_id", None)
            or getattr(cmd, "reactor_id", None),
            command=cmd.model_dump(),
            code=e.code,
            message=e.message,
            meta=e.meta,
        ).model_dump()
        return state, [rej]

    events: List[dict] = []

    if isinstance(cmd, StartCombat):
        state.combat_started = True
        state.initiative_finalized = False
        state.initiatives.clear()
        state.initiative_order.clear()
        state.turn_owner_id = None
        state.round = 1
        state.phase = "setup_initiative"

        seq, t = _bump(state)
        events.append(ev_combat_started(seq=seq, t=t, round_=state.round).model_dump())
        return state, events

    if isinstance(cmd, SetInitiative):
        state.initiatives[cmd.combatant_id] = int(cmd.initiative)

        seq, t = _bump(state)
        events.append(
            ev_initiative_set(
                seq=seq,
                t=t,
                round_=state.round,
                combatant_id=cmd.combatant_id,
                initiative=int(cmd.initiative),
            ).model_dump()
        )
        return state, events

    if isinstance(cmd, RollInitiative):
        # инициатива: d20 + bonus (обычно Dex mod; MVP — передаём)
        roll = _roll_d20(state, bonus=cmd.bonus, adv_state="normal")
        state.initiatives[cmd.combatant_id] = roll.total

        seq, t = _bump(state)
        events.append(
            ev_initiative_rolled(
                seq=seq,
                t=t,
                round_=state.round,
                combatant_id=cmd.combatant_id,
                roll=roll,
                bonus=cmd.bonus,
            ).model_dump()
        )
        return state, events

    if isinstance(cmd, FinalizeInitiative):
        # детерминированная сортировка: initiative desc, tie-breaker по combatant_id
        items = sorted(
            state.initiatives.items(),
            key=lambda kv: (-kv[1], kv[0]),
        )
        state.initiative_order = [cid for cid, _ in items]
        state.turn_owner_id = state.initiative_order[0]
        state.initiative_finalized = True
        state.phase = "idle"
        state.round = 1

        seq, t = _bump(state)
        events.append(
            ev_initiative_order_finalized(
                seq=seq,
                t=t,
                round_=state.round,
                order=[{"combatant_id": cid, "initiative": ini} for cid, ini in items],
            ).model_dump()
        )

        seq, t = _bump(state)
        events.append(
            ev_round_started(
                seq=seq, t=t, round_=state.round, turn_owner_id=state.turn_owner_id
            ).model_dump()
        )

        return state, events

    if isinstance(cmd, ApplyCondition):
        target = state.combatants[cmd.target_id]
        if cmd.condition not in target.conditions:
            target.conditions.add(cmd.condition)

            # если стало unconscious — сразу "обнулим" реакцию (чтобы не реагировал в этом же ходу)
            if cmd.condition == "unconscious":
                target.reaction_available = False

            seq, t = _bump(state)
            events.append(
                ev_condition_applied(
                    seq=seq,
                    t=t,
                    round_=state.round,
                    turn_owner_id=state.turn_owner_id,
                    actor_id=None,
                    target_id=cmd.target_id,
                    condition=cmd.condition,
                    reason="effect",
                ).model_dump()
            )
        return state, events

    if isinstance(cmd, RemoveCondition):
        target = state.combatants[cmd.target_id]
        if cmd.condition in target.conditions:
            target.conditions.remove(cmd.condition)

            seq, t = _bump(state)
            events.append(
                ev_condition_removed(
                    seq=seq,
                    t=t,
                    round_=state.round,
                    turn_owner_id=state.turn_owner_id,
                    actor_id=None,
                    target_id=cmd.target_id,
                    condition=cmd.condition,
                    reason="effect",
                ).model_dump()
            )
        return state, events

    if isinstance(cmd, StartConcentration):
        c = state.combatants[cmd.combatant_id]
        source_id = cmd.source_id or cmd.combatant_id

        # если уже было — заканчиваем старое
        if c.concentration is not None:
            prev = c.concentration.effect_name
            c.concentration = None
            seq, t = _bump(state)
            events.append(
                ev_concentration_ended(
                    seq=seq,
                    t=t,
                    round_=state.round,
                    combatant_id=c.id,
                    effect_name=prev,
                    reason="replaced",
                ).model_dump()
            )

        c.concentration = EffectRef(
            effect_name=cmd.effect_name, source_id=source_id, started_round=state.round
        )

        seq, t = _bump(state)
        events.append(
            ev_concentration_started(
                seq=seq,
                t=t,
                round_=state.round,
                combatant_id=c.id,
                effect_name=cmd.effect_name,
                source_id=source_id,
            ).model_dump()
        )
        return state, events

    if isinstance(cmd, EndConcentration):
        c = state.combatants[cmd.combatant_id]
        prev = c.concentration.effect_name if c.concentration else None
        c.concentration = None

        seq, t = _bump(state)
        events.append(
            ev_concentration_ended(
                seq=seq,
                t=t,
                round_=state.round,
                combatant_id=c.id,
                effect_name=prev,
                reason=cmd.reason,
            ).model_dump()
        )

        if prev:
            events.extend(
                _end_effects_by_concentration(
                    state,
                    concentration_owner_id=c.id,
                    concentration_effect_name=prev,
                    reason="concentration_ended",
                )
            )

        return state, events

    if isinstance(cmd, SaveEffect):
        source = state.combatants[cmd.source_id]
        turn_owner = state.turn_owner_id or cmd.source_id

        # тратим экономику
        if cmd.economy == "action":
            source.action_available = False
            # важно: чтобы не смешивалось с Attack action
            source.attack_action_started = False
            source.attack_action_remaining = 0
        else:
            source.bonus_available = False

        seq, t = _bump(state)
        events.append(
            ev_save_effect_declared(
                seq=seq,
                t=t,
                round_=state.round,
                turn_owner_id=turn_owner,
                actor_id=cmd.source_id,
                source_id=cmd.source_id,
                target_ids=cmd.target_ids,
                effect_name=cmd.effect_name,
                save_ability=cmd.save_ability,
                dc=cmd.dc,
                adv_state=cmd.adv_state,
                on_success=cmd.on_success,
                damage_type=cmd.damage_type,
                damage_formula=cmd.damage_formula,
                economy=cmd.economy,
            ).model_dump()
        )

        for tid in cmd.target_ids:
            target = state.combatants[tid]

            bonus = int(target.save_bonuses.get(cmd.save_ability, 0))
            save_roll = _roll_save(state, bonus=bonus, adv_state=cmd.adv_state)
            save_roll = _before_save_roll(
                state,
                roller=target,
                save_ability=cmd.save_ability,
                source_id=cmd.source_id,
                effect_name=cmd.effect_name,
                roll=save_roll,
            )

            seq, t = _bump(state)
            events.append(
                ev_saving_throw_rolled(
                    seq=seq,
                    t=t,
                    round_=state.round,
                    turn_owner_id=turn_owner,
                    actor_id=tid,
                    source_id=cmd.source_id,
                    target_id=tid,
                    effect_name=cmd.effect_name,
                    roll=save_roll,
                    save_ability=cmd.save_ability,
                    dc=cmd.dc,
                    bonus=bonus,
                ).model_dump()
            )

            success = save_roll.total >= cmd.dc
            margin = save_roll.total - cmd.dc

            if success:
                seq, t = _bump(state)
                events.append(
                    ev_saving_throw_succeeded(
                        seq=seq,
                        t=t,
                        round_=state.round,
                        turn_owner_id=turn_owner,
                        actor_id=tid,
                        source_id=cmd.source_id,
                        target_id=tid,
                        effect_name=cmd.effect_name,
                        margin=margin,
                    ).model_dump()
                )

                if cmd.on_success == "none":
                    seq, t = _bump(state)
                    events.append(
                        ev_save_effect_negated(
                            seq=seq,
                            t=t,
                            round_=state.round,
                            turn_owner_id=turn_owner,
                            actor_id=tid,
                            source_id=cmd.source_id,
                            target_id=tid,
                            effect_name=cmd.effect_name,
                        ).model_dump()
                    )
                    continue
            else:
                seq, t = _bump(state)
                events.append(
                    ev_saving_throw_failed(
                        seq=seq,
                        t=t,
                        round_=state.round,
                        turn_owner_id=turn_owner,
                        actor_id=tid,
                        source_id=cmd.source_id,
                        target_id=tid,
                        effect_name=cmd.effect_name,
                        margin=margin,
                    ).model_dump()
                )

            # Урон бросаем (и логируем) независимо от успеха/провала (кроме on_success="none")
            dmg_roll = _roll_damage(state, cmd.damage_formula, crit=False)
            dmg_roll = _before_damage_roll(
                state,
                source=source,
                target=target,
                damage_type=cmd.damage_type,
                source_kind="effect",
                roll=dmg_roll,
            )

            seq, t = _bump(state)
            events.append(
                ev_effect_damage_rolled(
                    seq=seq,
                    t=t,
                    round_=state.round,
                    turn_owner_id=turn_owner,
                    actor_id=cmd.source_id,
                    source_id=cmd.source_id,
                    target_id=tid,
                    effect_name=cmd.effect_name,
                    roll=dmg_roll,
                    damage_type=cmd.damage_type,
                ).model_dump()
            )

            raw = int(dmg_roll.total)

            # 1) сначала эффект сейва (half/full)
            if success:
                # cmd.on_success == "half" (т.к. "none" уже continue)
                adjusted_base = raw // 2
            else:
                adjusted_base = raw

            # 2) потом resist/vuln/immune по типу урона
            adjusted_final, mod = _adjust_damage_for_target(
                target, adjusted_base, cmd.damage_type
            )

            # применяем урон (по adjusted_final)
            temp_before, hp_before, hp_after = _apply_damage_with_temp_hp(
                target, adjusted_final
            )

            seq, t = _bump(state)
            events.append(
                ev_effect_damage_applied(
                    seq=seq,
                    t=t,
                    round_=state.round,
                    turn_owner_id=turn_owner,
                    actor_id=cmd.source_id,
                    source_id=cmd.source_id,
                    target_id=tid,
                    effect_name=cmd.effect_name,
                    raw=raw,
                    adjusted=adjusted_base,  # после сейва
                    damage_type=cmd.damage_type,
                    hp_before=hp_before,
                    hp_after=hp_after,
                ).model_dump()
            )

            # доп. поля (если фабрика не поддерживает их параметрами)
            events[-1]["payload"].update(
                {
                    "adjusted_final": adjusted_final,  # после resist/vuln/immune
                    "modifier": mod,  # None|"immune"|"resistant"|"vulnerable"
                }
            )

            # NEW: concentration check on damage (effect)
            events.extend(
                _maybe_run_concentration_check(
                    state,
                    target,
                    damage_taken=adjusted_final,
                    damage_type=cmd.damage_type,
                    cause="effect",
                    source_id=cmd.source_id,
                )
            )

            # hp=0 => unconscious (если ещё не было)
            if hp_after == 0 and "unconscious" not in target.conditions:
                target.conditions.add("unconscious")
                target.reaction_available = False

                if target.is_player_character:
                    target.is_stable = False
                    target.is_dead = False
                    # death saves начинаются с 0/0, но не перезаписывай если уже копятся?
                    # MVP: перезапускаем только если были >0 HP
                    target.death_save_successes = 0
                    target.death_save_failures = 0

                seq, t = _bump(state)
                events.append(
                    ev_condition_applied(
                        seq=seq,
                        t=t,
                        round_=state.round,
                        turn_owner_id=state.turn_owner_id,
                        actor_id=None,
                        target_id=target.id,
                        condition="unconscious",
                        reason="hp_0",
                    ).model_dump()
                )

                seq, t = _bump(state)
                events.append(
                    ev_unconscious_state_changed(
                        seq=seq,
                        t=t,
                        round_=state.round,
                        target_id=target.id,
                        became_unconscious=True,
                        reason="hp_0",
                    ).model_dump()
                )

        return state, events

    if isinstance(cmd, BeginTurn):
        c = state.combatants[cmd.combatant_id]
        state.phase = "in_turn"

        # если PC на 0 hp, не stable и не dead — в этот ход нужен death save
        if (
            c.is_player_character
            and c.hp_current == 0
            and (not c.is_dead)
            and (not c.is_stable)
        ):
            seq, t = _bump(state)
            events.append(
                ev_death_save_required(
                    seq=seq, t=t, round_=state.round, combatant_id=c.id
                ).model_dump()
            )

        c.action_available = True
        c.bonus_available = True
        c.reaction_available = True
        c.movement_remaining_ft = effective_speed_ft(c)
        c.no_opportunity_attacks_until_turn_end = False

        c.attack_action_started = False
        c.attack_action_remaining = 0

        seq, t = _bump(state)
        events.append(
            ev_turn_started(
                seq=seq, t=t, round_=state.round, turn_owner_id=cmd.combatant_id
            ).model_dump()
        )

        seq, t = _bump(state)
        events.append(
            ev_turn_resources_reset(
                seq=seq,
                t=t,
                round_=state.round,
                turn_owner_id=cmd.combatant_id,
                action=c.action_available,
                bonus=c.bonus_available,
                reaction=c.reaction_available,
                movement_ft=c.movement_remaining_ft,
            ).model_dump()
        )

        return state, events

    if isinstance(cmd, Disengage):
        c = state.combatants[cmd.combatant_id]
        c.action_available = False
        c.no_opportunity_attacks_until_turn_end = True

        seq, t = _bump(state)
        events.append(
            ev_disengage_applied(
                seq=seq,
                t=t,
                round_=state.round,
                turn_owner_id=state.turn_owner_id or cmd.combatant_id,
                combatant_id=cmd.combatant_id,
            ).model_dump()
        )
        return state, events

    if isinstance(cmd, CastSpell):
        caster = state.combatants[cmd.caster_id]
        spell = get_spell(cmd.spell_name)
        turn_owner = state.turn_owner_id or cmd.caster_id

        # тратим economy
        if spell.economy == "action":
            caster.action_available = False
            # не смешиваем с Attack action
            caster.attack_action_started = False
            caster.attack_action_remaining = 0
        elif spell.economy == "bonus":
            caster.bonus_available = False
        else:
            caster.reaction_available = False

        seq, t = _bump(state)
        events.append(
            ev_spell_cast_declared(
                seq=seq,
                t=t,
                round_=state.round,
                turn_owner_id=turn_owner,
                caster_id=cmd.caster_id,
                spell_name=cmd.spell_name,
                slot_level=cmd.slot_level,
                target_ids=cmd.target_ids,
            ).model_dump()
        )

        # тратим слот (если не cantrip)
        if spell.min_slot_level != 0:
            before = int(caster.spell_slots_current.get(cmd.slot_level, 0))
            caster.spell_slots_current[cmd.slot_level] = max(0, before - 1)
            after = caster.spell_slots_current[cmd.slot_level]

            seq, t = _bump(state)
            events.append(
                ev_spell_slot_spent(
                    seq=seq,
                    t=t,
                    round_=state.round,
                    caster_id=cmd.caster_id,
                    slot_level=cmd.slot_level,
                    before=before,
                    after=after,
                ).model_dump()
            )

        # концентрация (если нужно)
        if spell.concentration:
            # если уже была концентрация — завершаем старую + её эффекты
            if caster.concentration is not None:
                prev_effect_name = caster.concentration.effect_name
                caster.concentration = None

                seq, t = _bump(state)
                events.append(
                    ev_concentration_ended(
                        seq=seq,
                        t=t,
                        round_=state.round,
                        combatant_id=caster.id,
                        effect_name=prev_effect_name,
                        reason="replaced",
                    ).model_dump()
                )

                # ✅ NEW: снять все эффекты, которые привязаны к этой концентрации
                events.extend(
                    _end_effects_by_concentration(
                        state,
                        concentration_owner_id=caster.id,  # ✅ owner = caster
                        concentration_effect_name=prev_effect_name,  # ✅ старый effect name
                        reason="concentration_replaced",
                    )
                )

            # стартуем новую концентрацию на текущем спелле
            caster.concentration = EffectRef(
                effect_name=spell.name,
                source_id=caster.id,
                started_round=state.round,
            )

            seq, t = _bump(state)
            events.append(
                ev_concentration_started(
                    seq=seq,
                    t=t,
                    round_=state.round,
                    combatant_id=caster.id,
                    effect_name=spell.name,
                    source_id=caster.id,
                ).model_dump()
            )

        # --- резолв спелла (вынесено) ---
        if spell.kind == "save":
            dc = int(caster.spell_save_dc or 0)
            events.extend(
                resolve_save_spell(
                    state,
                    caster=caster,
                    spell=cast(SaveSpell, spell),
                    target_ids=cmd.target_ids,
                    dc=dc,
                    turn_owner_id=turn_owner,
                    bump=_bump,
                    roll_save=_roll_save,
                    roll_damage=_roll_damage,
                    adjust_damage_for_target=_adjust_damage_for_target,
                    maybe_run_concentration_check=_maybe_run_concentration_check,
                    before_save_roll=_before_save_roll,
                    before_damage_roll=_before_damage_roll,
                )
            )
            return state, events

        # attack spell
        target_id = cmd.target_ids[0]
        bonus = int(caster.spell_attack_bonus or 0)
        events.extend(
            resolve_attack_spell(
                state,
                caster=caster,
                spell=cast(AttackSpell, spell),
                target_id=target_id,
                to_hit_bonus=bonus,
                turn_owner_id=turn_owner,
                bump=_bump,
                roll_d20=_roll_d20,
                roll_damage=_roll_damage,
                adjust_damage_for_target=_adjust_damage_for_target,
                maybe_run_concentration_check=_maybe_run_concentration_check,
                before_attack_roll=_before_attack_roll,
                before_damage_roll=_before_damage_roll,
            )
        )
        return state, events

    if isinstance(cmd, Attack):
        attacker = state.combatants[cmd.attacker_id]

        # --- ACTION economy (Attack action: может дать несколько атак благодаря Extra Attack) ---
        if cmd.economy == "action":
            if not attacker.attack_action_started:
                # Первая атака в Attack action: тратим Action один раз
                attacker.action_available = False
                attacker.attack_action_started = True

                # Сколько атак останется после этой?
                # attacks_per_action=2 => remaining=1 (ещё одна атака)
                attacks_per_action = max(
                    1, int(getattr(attacker, "attacks_per_action", 1))
                )
                attacker.attack_action_remaining = max(0, attacks_per_action - 1)
            else:
                # Продолжение Attack action: тратим "слот атаки" внутри того же Action
                attacker.attack_action_remaining = max(
                    0, attacker.attack_action_remaining - 1
                )

            events.extend(
                _resolve_attack(
                    state,
                    cmd.attacker_id,
                    cmd.target_id,
                    cmd.attack_name,
                    context="action",
                    attack_kind=cmd.attack_kind,
                    adv_state=cmd.adv_state,
                    economy="action",
                    spend_action=False,  # Action уже списали выше (только один раз)
                    spend_reaction=False,
                )
            )
            return state, events

        # --- BONUS economy (Bonus Action attack) ---
        attacker.bonus_available = False

        events.extend(
            _resolve_attack(
                state,
                cmd.attacker_id,
                cmd.target_id,
                cmd.attack_name,
                context="action",
                attack_kind=cmd.attack_kind,
                adv_state=cmd.adv_state,
                economy="bonus",
                spend_action=False,
                spend_reaction=False,
            )
        )
        return state, events

    if isinstance(cmd, Multiattack):
        attacker = state.combatants[cmd.attacker_id]
        target_id = cmd.target_id
        turn_owner = state.turn_owner_id or cmd.attacker_id

        ma = attacker.multiattacks[cmd.multiattack_name]

        # Multiattack тратит Action (и не должен смешиваться с Attack action / Extra Attack)
        attacker.action_available = False
        attacker.attack_action_started = False
        attacker.attack_action_remaining = 0

        seq, t = _bump(state)
        events.append(
            ev_multiattack_declared(
                seq=seq,
                t=t,
                round_=state.round,
                turn_owner_id=turn_owner,
                attacker_id=cmd.attacker_id,
                target_id=target_id,
                multiattack_name=cmd.multiattack_name,
                attacks=ma.attacks,
            ).model_dump()
        )

        # Каждая атака внутри multiattack — отдельный набор событий атаки
        for attack_name in ma.attacks:
            events.extend(
                _resolve_attack(
                    state,
                    cmd.attacker_id,
                    target_id,
                    attack_name,
                    context="action",
                    attack_kind="melee",  # MVP: как правило melee, позже можно хранить kind в профиле
                    adv_state=cmd.adv_state,
                    economy="action",  # логируем как action
                    spend_action=False,  # action уже потрачен multiattack'ом
                    spend_reaction=False,
                )
            )

        return state, events

    if isinstance(cmd, Move):
        mover = state.combatants[cmd.mover_id]
        turn_owner = state.turn_owner_id or cmd.mover_id

        seq, t = _bump(state)
        events.append(
            ev_movement_started(
                seq=seq,
                t=t,
                round_=state.round,
                turn_owner_id=turn_owner,
                mover_id=cmd.mover_id,
                from_pos=mover.position,
                path=cmd.path,
            ).model_dump()
        )

        cur = mover.position
        for nxt in cmd.path:
            # стоимость шага (MVP: 5 футов за клетку)
            step_cost = 5

            # проверка OA: если Disengage активен — не триггерим
            if not mover.no_opportunity_attacks_until_turn_end:
                for enemy_id, enemy in state.combatants.items():
                    if enemy_id == mover.id:
                        continue
                    if not are_hostile(enemy, mover):
                        continue
                    if enemy.hp_current <= 0:
                        continue
                    if not enemy.reaction_available:
                        continue
                    # если врасплох и первый ход ещё не завершён — реакции запрещены
                    if enemy.surprised and not enemy.has_taken_first_turn:
                        continue

                    # OA триггерится, если шаг выводит из досягаемости 5 футов
                    reach = 5
                    was_in = _in_reach(enemy.position, cur, reach_ft=reach)
                    will_be_in = _in_reach(enemy.position, nxt, reach_ft=reach)

                    if was_in and not will_be_in:
                        # ВАЖНО: OA происходит прямо перед выходом из досягаемости,
                        # поэтому шаг "nxt" не выполняем, оставляем mover на cur.
                        window_id = state.new_window_id()
                        state.reaction_window = ReactionWindow(
                            id=window_id,
                            trigger="opportunity_attack",
                            mover_id=mover.id,
                            threatened_by_id=enemy.id,
                            reach_ft=reach,
                        )
                        state.phase = "reaction_window"

                        seq, t = _bump(state)
                        events.append(
                            ev_opportunity_attack_triggered(
                                seq=seq,
                                t=t,
                                round_=state.round,
                                turn_owner_id=turn_owner,
                                mover_id=mover.id,
                                threatened_by_id=enemy.id,
                                reach_ft=reach,
                            ).model_dump()
                        )

                        seq, t = _bump(state)
                        events.append(
                            ev_reaction_window_opened(
                                seq=seq,
                                t=t,
                                round_=state.round,
                                turn_owner_id=turn_owner,
                                window_id=window_id,
                                trigger="opportunity_attack",
                                eligible_reactors=[enemy.id],
                                context={
                                    "mover_id": mover.id,
                                    "threatened_by_id": enemy.id,
                                    "reach_ft": reach,
                                },
                            ).model_dump()
                        )

                        seq, t = _bump(state)
                        events.append(
                            ev_movement_stopped(
                                seq=seq,
                                t=t,
                                round_=state.round,
                                turn_owner_id=turn_owner,
                                mover_id=mover.id,
                                reason="reaction_window",
                            ).model_dump()
                        )

                        return state, events

            # применяем шаг
            mover.position = nxt
            mover.movement_remaining_ft -= step_cost

            seq, t = _bump(state)
            events.append(
                ev_moved_step(
                    seq=seq,
                    t=t,
                    round_=state.round,
                    turn_owner_id=turn_owner,
                    mover_id=mover.id,
                    from_pos=cur,
                    to_pos=nxt,
                    cost_ft=step_cost,
                ).model_dump()
            )

            cur = nxt

        seq, t = _bump(state)
        events.append(
            ev_movement_stopped(
                seq=seq,
                t=t,
                round_=state.round,
                turn_owner_id=turn_owner,
                mover_id=mover.id,
                reason="command_end",
            ).model_dump()
        )

        return state, events

    if isinstance(cmd, UseReaction):
        # сейчас у нас только opportunity_attack
        rw = state.reaction_window
        assert rw is not None

        reactor_id = cmd.reactor_id
        mover_id = rw.mover_id

        # закрываем окно реакции ПОСЛЕ резолва, но флаг окна держим пока генерим события
        events.extend(
            _resolve_attack(
                state,
                reactor_id,
                mover_id,
                cmd.attack_name,
                context="reaction",
                attack_kind="melee",
                adv_state=cmd.adv_state,
                economy="reaction",
                spend_action=False,
                spend_reaction=True,
            )
        )

        window_id = rw.id
        state.reaction_window = None
        state.phase = "in_turn"

        seq, t = _bump(state)
        events.append(
            ev_reaction_window_closed(
                seq=seq,
                t=t,
                round_=state.round,
                turn_owner_id=state.turn_owner_id or reactor_id,
                window_id=window_id,
                closed_by="reaction_used",
            ).model_dump()
        )

        return state, events

    if isinstance(cmd, DeclineReaction):
        rw = state.reaction_window
        assert rw is not None
        window_id = rw.id

        state.reaction_window = None
        state.phase = "in_turn"

        seq, t = _bump(state)
        events.append(
            ev_reaction_window_closed(
                seq=seq,
                t=t,
                round_=state.round,
                turn_owner_id=state.turn_owner_id or cmd.reactor_id,
                window_id=window_id,
                closed_by="declined",
            ).model_dump()
        )

        return state, events

    if isinstance(cmd, RollDeathSave):
        c = state.combatants[cmd.combatant_id]

        nat = state.rng.randint(1, 20)
        roll = Roll(
            kind="d20",
            formula="1d20 (death save)",
            dice=[nat],
            kept=[nat],
            mods=[],
            total=nat,
            nat=nat,
            is_critical=False,
            adv_state="normal",
        )

        seq, t = _bump(state)
        events.append(
            ev_death_save_rolled(
                seq=seq, t=t, round_=state.round, combatant_id=c.id, roll=roll
            ).model_dump()
        )

        # nat 20: приходит в сознание с 1 HP
        if nat == 20:
            hp_before = c.hp_current
            c.hp_current = 1
            c.death_save_successes = 0
            c.death_save_failures = 0
            c.is_stable = False
            # снимаем unconscious
            if "unconscious" in c.conditions:
                c.conditions.remove("unconscious")

            seq, t = _bump(state)
            events.append(
                ev_death_save_result(
                    seq=seq,
                    t=t,
                    round_=state.round,
                    combatant_id=c.id,
                    successes=c.death_save_successes,
                    failures=c.death_save_failures,
                    outcome="revived",
                ).model_dump()
            )
            return state, events

        # nat 1: 2 провала
        if nat == 1:
            c.death_save_failures += 2
            outcome = "crit_fail"
        elif nat >= 10:
            c.death_save_successes += 1
            outcome = "success"
        else:
            c.death_save_failures += 1
            outcome = "fail"

        # dead?
        if c.death_save_failures >= 3:
            c.is_dead = True
            outcome2 = "dead"
            seq, t = _bump(state)
            events.append(
                ev_death_save_result(
                    seq=seq,
                    t=t,
                    round_=state.round,
                    combatant_id=c.id,
                    successes=c.death_save_successes,
                    failures=c.death_save_failures,
                    outcome=outcome,
                ).model_dump()
            )
            seq, t = _bump(state)
            events.append(
                ev_died(
                    seq=seq,
                    t=t,
                    round_=state.round,
                    target_id=c.id,
                    reason="death_saves",
                ).model_dump()
            )
            return state, events

        # stabilized?
        if c.death_save_successes >= 3:
            c.is_stable = True
            c.death_save_successes = 0
            c.death_save_failures = 0

            seq, t = _bump(state)
            events.append(
                ev_death_save_result(
                    seq=seq,
                    t=t,
                    round_=state.round,
                    combatant_id=c.id,
                    successes=3,
                    failures=0,
                    outcome="stabilized",
                ).model_dump()
            )
            seq, t = _bump(state)
            events.append(
                ev_stabilized(
                    seq=seq,
                    t=t,
                    round_=state.round,
                    healer_id=None,
                    target_id=c.id,
                    reason="death_saves",
                ).model_dump()
            )
            return state, events

        seq, t = _bump(state)
        events.append(
            ev_death_save_result(
                seq=seq,
                t=t,
                round_=state.round,
                combatant_id=c.id,
                successes=c.death_save_successes,
                failures=c.death_save_failures,
                outcome=outcome,
            ).model_dump()
        )
        return state, events

    if isinstance(cmd, Stabilize):
        healer = state.combatants[cmd.healer_id]
        target = state.combatants[cmd.target_id]

        healer.action_available = False

        target.is_stable = True
        target.death_save_successes = 0
        target.death_save_failures = 0

        seq, t = _bump(state)
        events.append(
            ev_stabilized(
                seq=seq,
                t=t,
                round_=state.round,
                healer_id=cmd.healer_id,
                target_id=cmd.target_id,
                reason="stabilize_action",
            ).model_dump()
        )
        return state, events

    if isinstance(cmd, Heal):
        target = state.combatants[cmd.target_id]

        if cmd.healer_id is not None:
            healer = state.combatants[cmd.healer_id]
            healer.action_available = False

        hp_before = target.hp_current
        target.hp_current = min(target.hp_max, target.hp_current + max(0, cmd.amount))
        hp_after = target.hp_current

        # если подняли выше 0 — снимаем dying-статус
        if hp_after > 0:
            target.is_stable = False
            target.death_save_successes = 0
            target.death_save_failures = 0
            if "unconscious" in target.conditions:
                target.conditions.remove("unconscious")

        seq, t = _bump(state)
        events.append(
            ev_healed(
                seq=seq,
                t=t,
                round_=state.round,
                healer_id=cmd.healer_id,
                target_id=cmd.target_id,
                amount=cmd.amount,
                hp_before=hp_before,
                hp_after=hp_after,
            ).model_dump()
        )
        return state, events

    if isinstance(cmd, EndTurn):
        owner = state.turn_owner_id or cmd.combatant_id
        c = state.combatants[owner]

        c.has_taken_first_turn = True
        c.no_opportunity_attacks_until_turn_end = False

        seq, t = _bump(state)
        events.append(
            ev_turn_ended(
                seq=seq, t=t, round_=state.round, turn_owner_id=owner
            ).model_dump()
        )

        state.phase = "idle"

        if state.initiative_order:
            idx = state.initiative_order.index(owner)
            next_idx = idx + 1
            if next_idx >= len(state.initiative_order):
                state.round += 1
                next_idx = 0
            state.turn_owner_id = state.initiative_order[next_idx]

        return state, events

    # На всякий случай (хотя валидатор уже ловит)
    seq, t = _bump(state)
    events.append(
        ev_command_rejected(
            seq=seq,
            t=t,
            round_=state.round,
            turn_owner_id=state.turn_owner_id,
            actor_id=None,
            command=cmd.model_dump(),
            code="UNKNOWN_COMMAND",
            message="Unhandled command",
            meta={},
        ).model_dump()
    )
    return state, events
