from __future__ import annotations

from typing import Literal, cast

from dndsim.core.engine.events import (
    ev_attack_declared,
    ev_attack_rolled,
    ev_hit_confirmed,
    ev_miss_confirmed,
    ev_damage_rolled,
    ev_damage_applied,
    ev_save_effect_declared,
    ev_saving_throw_rolled,
    ev_saving_throw_succeeded,
    ev_saving_throw_failed,
    ev_effect_damage_rolled,
    ev_effect_damage_applied,
    ev_save_effect_negated,
    ev_condition_applied,
    ev_unconscious_state_changed,
    ev_effect_applied,
)
from dndsim.core.engine.state import (
    EncounterState,
    CombatantState,
    EffectRef,
    ActiveEffect,
)
from dndsim.core.engine.events import Roll
from dndsim.core.engine.spells.definitions import SaveSpell, AttackSpell


# --- эти утилиты импортируем из apply.py (временно), пока не вынесем их в отдельный utils ---
# Чтобы не делать круговых импортов, мы будем передавать функции из apply.py как параметры.
# apply.py будет звать resolve_* и передавать ссылки на свои helpers.


def resolve_save_spell(
    state: EncounterState,
    *,
    caster: CombatantState,
    spell: SaveSpell,
    target_ids: list[str],
    dc: int,
    turn_owner_id: str,
    # helpers
    bump,
    roll_save,
    roll_damage,
    adjust_damage_for_target,
    maybe_run_concentration_check,
    before_save_roll,  # ✅ NEW
    before_damage_roll,  # ✅ NEW
) -> list[dict]:
    events: list[dict] = []

    seq, t = bump(state)
    events.append(
        ev_save_effect_declared(
            seq=seq,
            t=t,
            round_=state.round,
            turn_owner_id=turn_owner_id,
            actor_id=caster.id,
            source_id=caster.id,
            target_ids=target_ids,
            effect_name=spell.name,
            save_ability=spell.save_ability,
            dc=dc,
            adv_state="normal",
            on_success=spell.on_success,
            damage_type=spell.damage_type,
            damage_formula=spell.damage_formula,
            economy=spell.economy,
        ).model_dump()
    )

    has_damage = bool(spell.damage_formula and spell.damage_formula.strip())

    # 5e: для AoE/Save spells урон обычно роллится один раз на эффект
    shared_damage_roll = None
    if spell.damage_formula and spell.damage_formula.strip():
        shared_damage_roll = roll_damage(state, spell.damage_formula, crit=False)

        # ✅ NEW: middleware на damage roll (AoE — один общий бросок)
        # (если middleware ничего не делает — просто вернёт тот же roll)
        dummy_target = state.combatants[target_ids[0]] if target_ids else caster
        shared_damage_roll = before_damage_roll(
            state,
            source=caster,
            target=dummy_target,
            damage_type=spell.damage_type,
            source_kind="spell",
            roll=shared_damage_roll,
        )

    for tid in target_ids:
        target = state.combatants[tid]

        bonus = int(target.save_bonuses.get(spell.save_ability, 0))
        save_roll: Roll = roll_save(state, bonus=bonus, adv_state="normal")
        save_roll = before_save_roll(
            state,
            roller=target,
            save_ability=spell.save_ability,
            source_id=caster.id,
            effect_name=spell.name,
            roll=save_roll,
        )

        seq, t = bump(state)
        events.append(
            ev_saving_throw_rolled(
                seq=seq,
                t=t,
                round_=state.round,
                turn_owner_id=turn_owner_id,
                actor_id=tid,
                source_id=caster.id,
                target_id=tid,
                effect_name=spell.name,
                roll=save_roll,
                save_ability=spell.save_ability,
                dc=dc,
                bonus=bonus,
            ).model_dump()
        )

        success = save_roll.total >= dc
        margin = save_roll.total - dc

        if success:
            seq, t = bump(state)
            events.append(
                ev_saving_throw_succeeded(
                    seq=seq,
                    t=t,
                    round_=state.round,
                    turn_owner_id=turn_owner_id,
                    actor_id=tid,
                    source_id=caster.id,
                    target_id=tid,
                    effect_name=spell.name,
                    margin=margin,
                ).model_dump()
            )

            if spell.on_success == "none":
                seq, t = bump(state)
                events.append(
                    ev_save_effect_negated(
                        seq=seq,
                        t=t,
                        round_=state.round,
                        turn_owner_id=turn_owner_id,
                        actor_id=tid,
                        source_id=caster.id,
                        target_id=tid,
                        effect_name=spell.name,
                    ).model_dump()
                )
                continue
        else:
            seq, t = bump(state)
            events.append(
                ev_saving_throw_failed(
                    seq=seq,
                    t=t,
                    round_=state.round,
                    turn_owner_id=turn_owner_id,
                    actor_id=tid,
                    source_id=caster.id,
                    target_id=tid,
                    effect_name=spell.name,
                    margin=margin,
                ).model_dump()
            )

        # --- NEW: apply conditions/effect on FAIL ---
        if (not success) and getattr(spell, "on_fail_conditions", None):
            eff_id = state.new_effect_id()

            # связываем с концентрацией, если spell.concentration=True
            conc_owner = caster.id if spell.concentration else None
            conc_name = spell.name if spell.concentration else None

            state.effects[eff_id] = ActiveEffect(
                id=eff_id,
                name=spell.name,
                source_id=caster.id,
                target_id=tid,
                started_round=state.round,
                concentration_owner_id=conc_owner,
                concentration_effect_name=conc_name,
                applies_conditions=set(spell.on_fail_conditions),
            )

            seq, t = bump(state)
            events.append(
                ev_effect_applied(
                    seq=seq,
                    t=t,
                    round_=state.round,
                    turn_owner_id=turn_owner_id,
                    effect_id=eff_id,
                    effect_name=spell.name,
                    source_id=caster.id,
                    target_id=tid,
                    concentration_owner_id=conc_owner,
                    concentration_effect_name=conc_name,
                    conditions=list(spell.on_fail_conditions),
                ).model_dump()
            )

            for cond in spell.on_fail_conditions:
                if cond not in target.conditions:
                    target.conditions.add(cond)
                    seq, t = bump(state)
                    events.append(
                        ev_condition_applied(
                            seq=seq,
                            t=t,
                            round_=state.round,
                            turn_owner_id=turn_owner_id,
                            actor_id=caster.id,
                            target_id=tid,
                            condition=cond,
                            reason=f"spell:{spell.name}",
                        ).model_dump()
                    )

        # 5.2.2: если у спелла нет урона (например hold_person) — пропускаем урон целиком
        if not has_damage:
            continue

        # --- DAMAGE (AoE: общий roll, single: можно тоже общий — MVP) ---
        dmg_roll: Roll = shared_damage_roll or roll_damage(
            state, spell.damage_formula, crit=False
        )

        # если общий ролл НЕ использовался — применяем middleware на каждом индивидуальном броске
        if shared_damage_roll is None:
            dmg_roll = before_damage_roll(
                state,
                source=caster,
                target=target,
                damage_type=spell.damage_type,
                source_kind="spell",
                roll=dmg_roll,
            )

        # логируем урон (можно логировать на каждого таргета — raw будет одинаковым при shared_damage_roll)
        seq, t = bump(state)
        events.append(
            ev_effect_damage_rolled(
                seq=seq,
                t=t,
                round_=state.round,
                turn_owner_id=turn_owner_id,
                actor_id=caster.id,
                source_id=caster.id,
                target_id=tid,
                effect_name=spell.name,
                roll=dmg_roll,
                damage_type=spell.damage_type,
            ).model_dump()
        )

        raw = int(dmg_roll.total)

        # on_success уже обработан ("none" => continue выше). Здесь: half/full.
        if success and spell.on_success == "half":
            adjusted_base = raw // 2
        else:
            adjusted_base = raw

        adjusted_final, mod = adjust_damage_for_target(
            target, adjusted_base, spell.damage_type
        )

        hp_before = target.hp_current
        target.hp_current = max(0, target.hp_current - max(0, adjusted_final))
        hp_after = target.hp_current

        seq, t = bump(state)
        events.append(
            ev_effect_damage_applied(
                seq=seq,
                t=t,
                round_=state.round,
                turn_owner_id=turn_owner_id,
                actor_id=caster.id,
                source_id=caster.id,
                target_id=tid,
                effect_name=spell.name,
                raw=raw,
                adjusted=adjusted_base,
                damage_type=spell.damage_type,
                hp_before=hp_before,
                hp_after=hp_after,
            ).model_dump()
        )
        events[-1]["payload"].update(
            {"adjusted_final": adjusted_final, "modifier": mod}
        )

        # концентрация-чек у цели
        events.extend(
            maybe_run_concentration_check(
                state,
                target,
                damage_taken=adjusted_final,
                damage_type=spell.damage_type,
                cause="effect",
                source_id=caster.id,
            )
        )

        # unconscious
        if hp_after == 0 and "unconscious" not in target.conditions:
            target.conditions.add("unconscious")
            target.reaction_available = False
            if target.is_player_character:
                target.is_stable = False
                target.is_dead = False
                target.death_save_successes = 0
                target.death_save_failures = 0

            seq, t = bump(state)
            events.append(
                ev_condition_applied(
                    seq=seq,
                    t=t,
                    round_=state.round,
                    turn_owner_id=turn_owner_id,
                    actor_id=None,
                    target_id=target.id,
                    condition="unconscious",
                    reason="hp_0",
                ).model_dump()
            )

            seq, t = bump(state)
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

    return events


def resolve_attack_spell(
    state: EncounterState,
    *,
    caster: CombatantState,
    spell: AttackSpell,
    target_id: str,
    to_hit_bonus: int,
    turn_owner_id: str,
    # helpers
    bump,
    roll_d20,
    roll_damage,
    adjust_damage_for_target,
    maybe_run_concentration_check,
    before_attack_roll,  # ✅ NEW
    before_damage_roll,  # ✅ NEW
) -> list[dict]:
    events: list[dict] = []
    target = state.combatants[target_id]

    seq, t = bump(state)
    events.append(
        ev_attack_declared(
            seq=seq,
            t=t,
            round_=state.round,
            turn_owner_id=turn_owner_id,
            attacker_id=caster.id,
            target_id=target_id,
            attack_name=spell.name,
            attack_kind=spell.attack_kind,
            context="action",
            economy=spell.economy,
        ).model_dump()
    )

    atk_roll: Roll = roll_d20(state, to_hit_bonus, adv_state="normal")
    atk_roll = before_attack_roll(
        state,
        attacker=caster,
        target=target,
        attack_name=spell.name,
        source="spell",
        roll=atk_roll,
    )

    seq, t = bump(state)
    events.append(
        ev_attack_rolled(
            seq=seq,
            t=t,
            round_=state.round,
            turn_owner_id=turn_owner_id,
            attacker_id=caster.id,
            target_id=target_id,
            roll=atk_roll,
            to_hit_bonus=to_hit_bonus,
            target_ac=target.ac,
        ).model_dump()
    )

    # nat1 auto miss
    if atk_roll.nat == 1:
        margin = atk_roll.total - target.ac
        seq, t = bump(state)
        events.append(
            ev_miss_confirmed(
                seq=seq,
                t=t,
                round_=state.round,
                turn_owner_id=turn_owner_id,
                attacker_id=caster.id,
                target_id=target_id,
                margin=margin,
            ).model_dump()
        )
        return events

    hit = atk_roll.total >= target.ac
    margin = atk_roll.total - target.ac

    if not hit:
        seq, t = bump(state)
        events.append(
            ev_miss_confirmed(
                seq=seq,
                t=t,
                round_=state.round,
                turn_owner_id=turn_owner_id,
                attacker_id=caster.id,
                target_id=target_id,
                margin=margin,
            ).model_dump()
        )
        return events

    final_crit = bool(atk_roll.is_critical)

    seq, t = bump(state)
    events.append(
        ev_hit_confirmed(
            seq=seq,
            t=t,
            round_=state.round,
            turn_owner_id=turn_owner_id,
            attacker_id=caster.id,
            target_id=target_id,
            is_critical=final_crit,
            margin=margin,
        ).model_dump()
    )

    dmg_roll: Roll = roll_damage(state, spell.damage_formula, crit=final_crit)
    dmg_roll = before_damage_roll(
        state,
        source=caster,
        target=target,
        damage_type=spell.damage_type,
        source_kind="spell",
        roll=dmg_roll,
    )

    seq, t = bump(state)
    events.append(
        ev_damage_rolled(
            seq=seq,
            t=t,
            round_=state.round,
            turn_owner_id=turn_owner_id,
            attacker_id=caster.id,
            target_id=target_id,
            roll=dmg_roll,
            damage_type=spell.damage_type,
        ).model_dump()
    )

    raw = int(dmg_roll.total)
    adjusted, mod = adjust_damage_for_target(target, raw, spell.damage_type)

    hp_before = target.hp_current
    target.hp_current = max(0, target.hp_current - max(0, adjusted))
    hp_after = target.hp_current

    # unconscious
    if hp_after == 0 and "unconscious" not in target.conditions:
        target.conditions.add("unconscious")
        target.reaction_available = False
        if target.is_player_character:
            target.is_stable = False
            target.is_dead = False
            target.death_save_successes = 0
            target.death_save_failures = 0

        seq, t = bump(state)
        events.append(
            ev_condition_applied(
                seq=seq,
                t=t,
                round_=state.round,
                turn_owner_id=turn_owner_id,
                actor_id=None,
                target_id=target.id,
                condition="unconscious",
                reason="hp_0",
            ).model_dump()
        )

        seq, t = bump(state)
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

    # DamageApplied — без is_critical параметром (у тебя фабрика его не принимает)
    seq, t = bump(state)
    events.append(
        ev_damage_applied(
            seq=seq,
            t=t,
            round_=state.round,
            turn_owner_id=turn_owner_id,
            attacker_id=caster.id,
            target_id=target_id,
            raw=raw,
            adjusted=adjusted,
            damage_type=spell.damage_type,
            hp_before=hp_before,
            hp_after=hp_after,
        ).model_dump()
    )
    events[-1]["payload"]["modifier"] = mod
    events[-1]["payload"]["is_critical"] = final_crit

    # концентрация-чек у цели
    events.extend(
        maybe_run_concentration_check(
            state,
            target,
            damage_taken=adjusted,
            damage_type=spell.damage_type,
            cause="attack",
            source_id=caster.id,
        )
    )

    return events
