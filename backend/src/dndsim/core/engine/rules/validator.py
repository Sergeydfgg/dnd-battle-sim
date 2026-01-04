from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from dndsim.core.engine.spells.registry import get_spell

from dndsim.core.engine.commands import (
    ApplyCondition,
    RemoveCondition,
    StartCombat,
    SetInitiative,
    RollInitiative,
    FinalizeInitiative,
    Attack,
    BeginTurn,
    EndTurn,
    Move,
    UseReaction,
    DeclineReaction,
    Disengage,
    Command,
    Multiattack,
    SaveEffect,
    RollDeathSave,
    Stabilize,
    Heal,
    StartConcentration,
    EndConcentration,
    CastSpell,
)


from dndsim.core.engine.state import EncounterState


def _grid_distance_ft(a: tuple[int, int], b: tuple[int, int]) -> int:
    # 5e на клетчатой карте: считаем по Chebyshev (как reach/move у тебя уже)
    return max(abs(a[0] - b[0]), abs(a[1] - b[1])) * 5


@dataclass
class ValidationError:
    code: str
    message: str
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    ok: bool
    errors: List[ValidationError] = field(default_factory=list)
    cost_preview: Dict[str, Any] = field(default_factory=dict)


def _err(code: str, message: str, **meta: Any) -> ValidationResult:
    return ValidationResult(
        ok=False, errors=[ValidationError(code=code, message=message, meta=meta)]
    )


def _adjacent(a: tuple[int, int], b: tuple[int, int]) -> bool:
    dx = abs(a[0] - b[0])
    dy = abs(a[1] - b[1])
    return (dx <= 1 and dy <= 1) and not (dx == 0 and dy == 0)


def validate_command(state: EncounterState, cmd: Command) -> ValidationResult:
    # --- Reaction window gating ---
    if state.reaction_window is not None:
        # Пока окно открыто — разрешены только UseReaction / DeclineReaction
        if not isinstance(cmd, (UseReaction, DeclineReaction)):
            return _err(
                "REACTION_WINDOW_OPEN", "A reaction window is open; resolve it first"
            )

    if isinstance(cmd, StartCombat):
        if state.combat_started:
            return _err("COMBAT_ALREADY_STARTED", "Combat already started")
        if len(state.combatants) == 0:
            return _err("NO_COMBATANTS", "Cannot start combat with zero combatants")
        if state.phase != "idle":
            return _err(
                "BAD_PHASE", "StartCombat requires idle phase", phase=state.phase
            )
        return ValidationResult(ok=True)

    if isinstance(cmd, SetInitiative):
        if not state.combat_started:
            return _err("COMBAT_NOT_STARTED", "Call StartCombat first")
        if state.initiative_finalized:
            return _err("INITIATIVE_FINALIZED", "Initiative already finalized")
        if cmd.combatant_id not in state.combatants:
            return _err(
                "UNKNOWN_COMBATANT",
                "Unknown combatant_id",
                combatant_id=cmd.combatant_id,
            )
        return ValidationResult(ok=True)

    if isinstance(cmd, RollInitiative):
        if not state.combat_started:
            return _err("COMBAT_NOT_STARTED", "Call StartCombat first")
        if state.initiative_finalized:
            return _err("INITIATIVE_FINALIZED", "Initiative already finalized")
        if cmd.combatant_id not in state.combatants:
            return _err(
                "UNKNOWN_COMBATANT",
                "Unknown combatant_id",
                combatant_id=cmd.combatant_id,
            )
        return ValidationResult(ok=True)

    if isinstance(cmd, FinalizeInitiative):
        if not state.combat_started:
            return _err("COMBAT_NOT_STARTED", "Call StartCombat first")
        if state.initiative_finalized:
            return _err("INITIATIVE_FINALIZED", "Initiative already finalized")
        missing = [
            cid for cid in state.combatants.keys() if cid not in state.initiatives
        ]
        if missing:
            return _err(
                "MISSING_INITIATIVE",
                "Not all combatants have initiative set/rolled",
                missing=missing,
            )
        return ValidationResult(ok=True)

    if isinstance(cmd, ApplyCondition):
        if cmd.target_id not in state.combatants:
            return _err(
                "UNKNOWN_COMBATANT", "Target not found", target_id=cmd.target_id
            )
        return ValidationResult(ok=True)

    if isinstance(cmd, RemoveCondition):
        if cmd.target_id not in state.combatants:
            return _err(
                "UNKNOWN_COMBATANT", "Target not found", target_id=cmd.target_id
            )
        return ValidationResult(ok=True)

    if isinstance(cmd, BeginTurn):
        if cmd.combatant_id not in state.combatants:
            return _err(
                "UNKNOWN_COMBATANT",
                "Unknown combatant_id",
                combatant_id=cmd.combatant_id,
            )
        if state.turn_owner_id != cmd.combatant_id:
            return _err(
                "NOT_YOUR_TURN",
                "BeginTurn only for current turn owner",
                turn_owner_id=state.turn_owner_id,
                combatant_id=cmd.combatant_id,
            )
        if state.phase == "in_turn":
            return _err("ALREADY_IN_TURN", "Turn already started")
        return ValidationResult(ok=True)

    if isinstance(cmd, EndTurn):
        if cmd.combatant_id != state.turn_owner_id:
            return _err(
                "NOT_YOUR_TURN",
                "EndTurn only by turn owner",
                turn_owner_id=state.turn_owner_id,
                combatant_id=cmd.combatant_id,
            )
        if state.phase != "in_turn":
            return _err(
                "NOT_IN_TURN", "EndTurn requires in_turn phase", phase=state.phase
            )
        return ValidationResult(ok=True)

    if isinstance(cmd, Disengage):
        if cmd.combatant_id != state.turn_owner_id:
            return _err(
                "NOT_YOUR_TURN",
                "Disengage only by turn owner",
                turn_owner_id=state.turn_owner_id,
                combatant_id=cmd.combatant_id,
            )
        if state.phase != "in_turn":
            return _err(
                "NOT_IN_TURN", "Disengage requires in_turn phase", phase=state.phase
            )
        c = state.combatants.get(cmd.combatant_id)
        if c is None:
            return _err(
                "UNKNOWN_COMBATANT",
                "Combatant not found",
                combatant_id=cmd.combatant_id,
            )
        if c.surprised and not c.has_taken_first_turn:
            return _err(
                "SURPRISED_BLOCK",
                "Surprised creature cannot take actions on its first turn",
            )
        if not c.action_available:
            return _err("NO_ACTION", "No action available this turn")
        return ValidationResult(ok=True, cost_preview={"action": 1})

    if isinstance(cmd, SaveEffect):
        if cmd.source_id != state.turn_owner_id:
            return _err(
                "NOT_YOUR_TURN",
                "SaveEffect only by turn owner",
                turn_owner_id=state.turn_owner_id,
                source_id=cmd.source_id,
            )

        source = state.combatants.get(cmd.source_id)
        if source is None:
            return _err(
                "UNKNOWN_COMBATANT", "Source not found", source_id=cmd.source_id
            )

        if state.phase != "in_turn":
            return _err(
                "NOT_IN_TURN", "SaveEffect requires in_turn phase", phase=state.phase
            )

        if source.surprised and not source.has_taken_first_turn:
            return _err(
                "SURPRISED_BLOCK",
                "Surprised creature cannot take actions on its first turn",
            )

        if "unconscious" in source.conditions:
            return _err(
                "CONDITION_BLOCKS_ACTION", "Unconscious creature cannot take actions"
            )

        # цели должны существовать
        missing = [tid for tid in cmd.target_ids if tid not in state.combatants]
        if missing:
            return _err("UNKNOWN_TARGETS", "Some targets not found", missing=missing)

        # экономика
        if cmd.economy == "action":
            if not source.action_available:
                return _err("NO_ACTION", "No action available this turn")
            return ValidationResult(ok=True, cost_preview={"action": 1})

        if not source.bonus_available:
            return _err("NO_BONUS_ACTION", "No bonus action available this turn")
        return ValidationResult(ok=True, cost_preview={"bonus": 1})

    if isinstance(cmd, RollDeathSave):
        # ход этого существа
        if cmd.combatant_id != state.turn_owner_id:
            return _err(
                "NOT_YOUR_TURN",
                "Death save can be rolled only by the turn owner",
                turn_owner_id=state.turn_owner_id,
                combatant_id=cmd.combatant_id,
            )

        c = state.combatants.get(cmd.combatant_id)
        if c is None:
            return _err(
                "UNKNOWN_COMBATANT",
                "Combatant not found",
                combatant_id=cmd.combatant_id,
            )

        if state.phase != "in_turn":
            return _err(
                "NOT_IN_TURN", "Death save requires in_turn phase", phase=state.phase
            )

        # только для PC
        if not c.is_player_character:
            return _err(
                "NOT_A_PC",
                "Death saves apply only to player characters",
                combatant_id=c.id,
            )

        # должен быть на 0 hp
        if c.hp_current != 0:
            return _err(
                "NOT_DYING",
                "Death save requires hp_current == 0",
                hp_current=c.hp_current,
            )

        # не мёртв
        if c.is_dead:
            return _err(
                "ALREADY_DEAD", "Cannot roll death save while dead", combatant_id=c.id
            )

        # не стабилен
        if c.is_stable:
            return _err(
                "ALREADY_STABLE",
                "Stable creature does not roll death saves",
                combatant_id=c.id,
            )

        return ValidationResult(ok=True, cost_preview={"death_save": 1})

    if isinstance(cmd, Stabilize):
        # лечащий должен быть владельцем хода
        if cmd.healer_id != state.turn_owner_id:
            return _err(
                "NOT_YOUR_TURN",
                "Stabilize can be used only by the turn owner",
                turn_owner_id=state.turn_owner_id,
                healer_id=cmd.healer_id,
            )

        healer = state.combatants.get(cmd.healer_id)
        target = state.combatants.get(cmd.target_id)
        if healer is None or target is None:
            return _err(
                "UNKNOWN_COMBATANT",
                "Healer or target not found",
                healer_id=cmd.healer_id,
                target_id=cmd.target_id,
            )

        if state.phase != "in_turn":
            return _err(
                "NOT_IN_TURN", "Stabilize requires in_turn phase", phase=state.phase
            )

        # лечащий не должен быть без сознания
        if "unconscious" in healer.conditions:
            return _err(
                "CONDITION_BLOCKS_ACTION",
                "Unconscious creature cannot take actions",
                healer_id=healer.id,
            )

        # экономия: нужен Action
        if not healer.action_available:
            return _err(
                "NO_ACTION", "No action available this turn", healer_id=healer.id
            )

        # цель должна быть PC на 0 hp
        if not target.is_player_character:
            return _err(
                "TARGET_NOT_PC",
                "Stabilize (MVP) applies only to PCs",
                target_id=target.id,
            )

        if target.hp_current != 0:
            return _err(
                "TARGET_NOT_DYING",
                "Target must have hp_current == 0",
                hp_current=target.hp_current,
            )

        if target.is_dead:
            return _err(
                "TARGET_DEAD", "Cannot stabilize a dead target", target_id=target.id
            )

        if target.is_stable:
            return _err(
                "TARGET_ALREADY_STABLE", "Target is already stable", target_id=target.id
            )

        return ValidationResult(ok=True, cost_preview={"action": 1})

    if isinstance(cmd, Heal):
        target = state.combatants.get(cmd.target_id)
        if target is None:
            return _err(
                "UNKNOWN_COMBATANT", "Target not found", target_id=cmd.target_id
            )

        if cmd.amount <= 0:
            return _err("BAD_AMOUNT", "Heal amount must be > 0", amount=cmd.amount)

        # ✅ healer_id=None: разрешаем как системное лечение (тесты/эффекты)
        if cmd.healer_id is None:
            return ValidationResult(ok=True, cost_preview={"heal": cmd.amount})

        # healer_id задан: это действие в ход
        if cmd.healer_id != state.turn_owner_id:
            return _err(
                "NOT_YOUR_TURN",
                "Heal can be used only by the turn owner",
                turn_owner_id=state.turn_owner_id,
                healer_id=cmd.healer_id,
            )

        healer = state.combatants.get(cmd.healer_id)
        if healer is None:
            return _err(
                "UNKNOWN_COMBATANT", "Healer not found", healer_id=cmd.healer_id
            )

        if state.phase != "in_turn":
            return _err(
                "NOT_IN_TURN",
                "Heal (with healer) requires in_turn phase",
                phase=state.phase,
            )

        if "unconscious" in healer.conditions:
            return _err(
                "CONDITION_BLOCKS_ACTION",
                "Unconscious creature cannot take actions",
                healer_id=healer.id,
            )

        if not healer.action_available:
            return _err(
                "NO_ACTION", "No action available this turn", healer_id=healer.id
            )

        return ValidationResult(ok=True, cost_preview={"action": 1})

    if isinstance(cmd, StartConcentration):
        if cmd.combatant_id != state.turn_owner_id:
            return _err(
                "NOT_YOUR_TURN",
                "StartConcentration only by turn owner",
                turn_owner_id=state.turn_owner_id,
                combatant_id=cmd.combatant_id,
            )

        c = state.combatants.get(cmd.combatant_id)
        if c is None:
            return _err(
                "UNKNOWN_COMBATANT",
                "Combatant not found",
                combatant_id=cmd.combatant_id,
            )

        if state.phase != "in_turn":
            return _err(
                "NOT_IN_TURN",
                "StartConcentration requires in_turn phase",
                phase=state.phase,
            )

        if c.is_dead:
            return _err(
                "ALREADY_DEAD", "Dead creature cannot concentrate", combatant_id=c.id
            )

        if "unconscious" in c.conditions:
            return _err(
                "INCAPACITATED",
                "Unconscious creature cannot start concentration",
                combatant_id=c.id,
            )

        return ValidationResult(ok=True, cost_preview={"concentration": "start"})

    if isinstance(cmd, EndConcentration):
        if cmd.combatant_id != state.turn_owner_id:
            return _err(
                "NOT_YOUR_TURN",
                "EndConcentration only by turn owner",
                turn_owner_id=state.turn_owner_id,
                combatant_id=cmd.combatant_id,
            )

        c = state.combatants.get(cmd.combatant_id)
        if c is None:
            return _err(
                "UNKNOWN_COMBATANT",
                "Combatant not found",
                combatant_id=cmd.combatant_id,
            )

        if state.phase != "in_turn":
            return _err(
                "NOT_IN_TURN",
                "EndConcentration requires in_turn phase",
                phase=state.phase,
            )

        if c.concentration is None:
            return _err(
                "NO_CONCENTRATION", "Combatant is not concentrating", combatant_id=c.id
            )

        return ValidationResult(ok=True, cost_preview={"concentration": "end"})

    if isinstance(cmd, CastSpell):
        if cmd.caster_id != state.turn_owner_id:
            return _err(
                "NOT_YOUR_TURN",
                "CastSpell only by turn owner",
                turn_owner_id=state.turn_owner_id,
                caster_id=cmd.caster_id,
            )

        caster = state.combatants.get(cmd.caster_id)
        if caster is None:
            return _err(
                "UNKNOWN_COMBATANT", "Caster not found", caster_id=cmd.caster_id
            )

        if state.phase != "in_turn":
            return _err(
                "NOT_IN_TURN", "CastSpell requires in_turn phase", phase=state.phase
            )

        if caster.surprised and not caster.has_taken_first_turn:
            return _err(
                "SURPRISED_BLOCK",
                "Surprised creature cannot take actions on its first turn",
            )

        if caster.is_dead:
            return _err("DEAD", "Dead creature cannot act")

        if "unconscious" in caster.conditions:
            return _err(
                "CONDITION_BLOCKS_ACTION", "Unconscious creature cannot cast spells"
            )

        # spell must exist
        try:
            spell = get_spell(cmd.spell_name)
        except KeyError:
            return _err(
                "UNKNOWN_SPELL", "Spell not registered", spell_name=cmd.spell_name
            )

        # проверки нужных кастерских статов
        if spell.kind == "save":
            if caster.spell_save_dc is None or int(caster.spell_save_dc) <= 0:
                return _err(
                    "MISSING_SPELL_SAVE_DC",
                    "Caster has no spell_save_dc set",
                    caster_id=caster.id,
                )
        else:  # attack
            if caster.spell_attack_bonus is None:
                return _err(
                    "MISSING_SPELL_ATTACK_BONUS",
                    "Caster has no spell_attack_bonus set",
                    caster_id=caster.id,
                )

        # target rules
        if not cmd.target_ids:
            return _err("NO_TARGETS", "CastSpell requires at least one target")

        if spell.target_mode == "single" and len(cmd.target_ids) != 1:
            return _err(
                "BAD_TARGET_COUNT",
                "Single-target spell requires exactly 1 target",
                target_mode=spell.target_mode,
                count=len(cmd.target_ids),
            )

        # ensure targets exist
        for tid in cmd.target_ids:
            if tid not in state.combatants:
                return _err("UNKNOWN_TARGET", "Target not found", target_id=tid)

        # economy availability
        if spell.economy == "action":
            if not caster.action_available:
                return _err("NO_ACTION", "No action available this turn")
            cost = {"action": 1}
        elif spell.economy == "bonus":
            if not caster.bonus_available:
                return _err("NO_BONUS_ACTION", "No bonus action available this turn")
            cost = {"bonus": 1}
        else:  # reaction
            if not caster.reaction_available:
                return _err("NO_REACTION", "No reaction available")
            cost = {"reaction": 1}

        # slot checks (cantrip min_slot_level==0)
        if spell.min_slot_level != 0:
            if cmd.slot_level < spell.min_slot_level:
                return _err(
                    "SLOT_TOO_LOW",
                    "Slot level too low for this spell",
                    slot_level=cmd.slot_level,
                    min_slot_level=spell.min_slot_level,
                )
            cur = int(caster.spell_slots_current.get(cmd.slot_level, 0))
            if cur <= 0:
                return _err(
                    "NO_SPELL_SLOT",
                    "No spell slots of this level remaining",
                    slot_level=cmd.slot_level,
                )

        # --- range check (MVP) ---
        # Проверяем: каждый target должен быть в пределах spell.range_ft от caster.
        # (Для AoE по-хорошему range считается до точки, но пока target_ids задаются уже "попавшими в AoE".)
        caster_pos = caster.position
        for tid in cmd.target_ids:
            target = state.combatants[tid]
            dist = _grid_distance_ft(caster_pos, target.position)
            if dist > int(spell.range_ft):
                return _err(
                    "OUT_OF_RANGE",
                    "Target is out of spell range",
                    spell_name=cmd.spell_name,
                    range_ft=int(spell.range_ft),
                    distance_ft=dist,
                    caster_id=caster.id,
                    target_id=tid,
                    caster_pos=caster_pos,
                    target_pos=target.position,
                )

        return ValidationResult(ok=True, cost_preview=cost)

    if isinstance(cmd, Attack):
        # 1) чей ход
        if cmd.attacker_id != state.turn_owner_id:
            return _err(
                "NOT_YOUR_TURN",
                "Attack only by turn owner",
                turn_owner_id=state.turn_owner_id,
                attacker_id=cmd.attacker_id,
            )

        attacker = state.combatants.get(cmd.attacker_id)
        target = state.combatants.get(cmd.target_id)
        if attacker is None or target is None:
            return _err(
                "UNKNOWN_COMBATANT",
                "Attacker or target not found",
                attacker_id=cmd.attacker_id,
                target_id=cmd.target_id,
            )

        # 2) фаза
        if state.phase != "in_turn":
            return _err(
                "NOT_IN_TURN", "Attack requires in_turn phase", phase=state.phase
            )

        # 3) surprise
        if attacker.surprised and not attacker.has_taken_first_turn:
            return _err(
                "SURPRISED_BLOCK",
                "Surprised creature cannot take actions on its first turn",
            )

        # 4) состояния, запрещающие действие
        if "unconscious" in attacker.conditions:
            return _err(
                "CONDITION_BLOCKS_ACTION", "Unconscious creature cannot take actions"
            )

        # 5) есть ли такая атака у атакующего
        if cmd.attack_name not in attacker.attacks:
            return _err(
                "UNKNOWN_ATTACK",
                "Attacker does not have this attack",
                attack_name=cmd.attack_name,
            )

        profile = attacker.attacks[cmd.attack_name]

        # ---------- ACTION атака (Attack action, включая Extra Attack) ----------
        if cmd.economy == "action":
            # эта атака вообще может быть action-атакой?
            if not profile.uses_action:
                return _err(
                    "ATTACK_NOT_ACTION",
                    "This attack can't be used as an Action",
                    attack_name=cmd.attack_name,
                )

            # Если Attack action ещё НЕ начат — нужен свободный Action
            if not attacker.attack_action_started:
                if not attacker.action_available:
                    return _err("NO_ACTION", "No action available this turn")
                # валидатор ОК: это будет “первая атака” в Attack action
                return ValidationResult(
                    ok=True,
                    cost_preview={"economy": "action", "attack_action_step": "start"},
                )

            # Если Attack action УЖЕ начат — должны оставаться атаки
            if attacker.attack_action_remaining <= 0:
                return _err(
                    "NO_ATTACKS_REMAINING", "No attacks remaining in this Attack action"
                )

            return ValidationResult(
                ok=True,
                cost_preview={"economy": "action", "attack_action_step": "continue"},
            )

        # ---------- BONUS ACTION атака ----------
        # cmd.economy == "bonus"
        if not profile.uses_bonus_action:
            return _err(
                "ATTACK_NOT_BONUS",
                "This attack can't be used as a Bonus Action",
                attack_name=cmd.attack_name,
            )

        if not attacker.bonus_available:
            return _err("NO_BONUS_ACTION", "No bonus action available this turn")

        return ValidationResult(ok=True, cost_preview={"economy": "bonus"})

    if isinstance(cmd, Multiattack):
        if cmd.attacker_id != state.turn_owner_id:
            return _err(
                "NOT_YOUR_TURN",
                "Multiattack only by turn owner",
                turn_owner_id=state.turn_owner_id,
                attacker_id=cmd.attacker_id,
            )

        attacker = state.combatants.get(cmd.attacker_id)
        target = state.combatants.get(cmd.target_id)
        if attacker is None or target is None:
            return _err(
                "UNKNOWN_COMBATANT",
                "Attacker or target not found",
                attacker_id=cmd.attacker_id,
                target_id=cmd.target_id,
            )

        if state.phase != "in_turn":
            return _err(
                "NOT_IN_TURN", "Multiattack requires in_turn phase", phase=state.phase
            )

        if attacker.surprised and not attacker.has_taken_first_turn:
            return _err(
                "SURPRISED_BLOCK",
                "Surprised creature cannot take actions on its first turn",
            )

        if "unconscious" in attacker.conditions:
            return _err(
                "CONDITION_BLOCKS_ACTION", "Unconscious creature cannot take actions"
            )

        if not attacker.action_available:
            return _err("NO_ACTION", "No action available this turn")

        if cmd.multiattack_name not in attacker.multiattacks:
            return _err(
                "UNKNOWN_MULTIATTACK",
                "Attacker does not have this multiattack",
                multiattack_name=cmd.multiattack_name,
            )

        profile = attacker.multiattacks[cmd.multiattack_name]
        missing = [a for a in profile.attacks if a not in attacker.attacks]
        if missing:
            return _err(
                "MULTIATTACK_MISSING_ATTACKS",
                "Multiattack references missing attacks",
                missing=missing,
            )

        return ValidationResult(ok=True, cost_preview={"action": 1})

    if isinstance(cmd, Move):
        if cmd.mover_id != state.turn_owner_id:
            return _err(
                "NOT_YOUR_TURN",
                "Move only by turn owner",
                turn_owner_id=state.turn_owner_id,
                mover_id=cmd.mover_id,
            )
        mover = state.combatants.get(cmd.mover_id)
        if mover is None:
            return _err("UNKNOWN_COMBATANT", "Mover not found", mover_id=cmd.mover_id)
        if "unconscious" in mover.conditions:
            return _err("CONDITION_BLOCKS_MOVE", "Unconscious creature cannot move")
        if "grappled" in mover.conditions:
            return _err("CONDITION_BLOCKS_MOVE", "Grappled creature cannot move")
        if "restrained" in mover.conditions:
            return _err("CONDITION_BLOCKS_MOVE", "Restrained creature cannot move")
        if state.phase != "in_turn":
            return _err("NOT_IN_TURN", "Move requires in_turn phase", phase=state.phase)
        if mover.surprised and not mover.has_taken_first_turn:
            return _err(
                "SURPRISED_BLOCK", "Surprised creature cannot move on its first turn"
            )

        if not cmd.path:
            return _err("EMPTY_PATH", "Move path is empty")

        # проверим, что путь идёт соседними клетками
        cur = mover.position
        steps = 0
        for p in cmd.path:
            if not _adjacent(cur, p):
                return _err(
                    "INVALID_PATH",
                    "Move path must be step-by-step adjacent",
                    from_pos=cur,
                    to_pos=p,
                )
            steps += 1
            cur = p

        cost_ft = steps * 5
        if mover.movement_remaining_ft < cost_ft:
            return _err(
                "NO_MOVEMENT",
                "Not enough movement remaining",
                needed_ft=cost_ft,
                remaining_ft=mover.movement_remaining_ft,
            )

        return ValidationResult(ok=True, cost_preview={"movement_ft": cost_ft})

    if isinstance(cmd, UseReaction):
        if state.reaction_window is None:
            return _err("NO_REACTION_WINDOW", "No reaction window is open")
        rw = state.reaction_window

        if cmd.reactor_id != rw.threatened_by_id:
            return _err(
                "NOT_ELIGIBLE_REACTOR",
                "This reactor is not eligible for the current window",
                reactor_id=cmd.reactor_id,
                eligible=rw.threatened_by_id,
            )

        reactor = state.combatants.get(cmd.reactor_id)
        mover = state.combatants.get(rw.mover_id)

        if reactor is None or mover is None:
            return _err(
                "UNKNOWN_COMBATANT",
                "Reactor or mover not found",
                reactor_id=cmd.reactor_id,
                mover_id=rw.mover_id,
            )

        if "unconscious" in reactor.conditions:
            return _err(
                "CONDITION_BLOCKS_REACTION",
                "Unconscious creature cannot take reactions",
            )

        # surprise блок реакций: нельзя реакции, пока не закончится первый ход
        if reactor.surprised and not reactor.has_taken_first_turn:
            return _err(
                "SURPRISED_BLOCK_REACTION",
                "Surprised creature cannot take reactions until its first turn ends",
            )

        if not reactor.reaction_available:
            return _err("NO_REACTION", "No reaction available")

        if cmd.attack_name not in reactor.attacks:
            return _err(
                "UNKNOWN_ATTACK",
                "Reactor does not have this attack",
                attack_name=cmd.attack_name,
            )

        return ValidationResult(ok=True, cost_preview={"reaction": 1})

    if isinstance(cmd, DeclineReaction):
        if state.reaction_window is None:
            return _err("NO_REACTION_WINDOW", "No reaction window is open")
        rw = state.reaction_window
        if cmd.reactor_id != rw.threatened_by_id:
            return _err(
                "NOT_ELIGIBLE_REACTOR",
                "This reactor is not eligible for the current window",
                reactor_id=cmd.reactor_id,
                eligible=rw.threatened_by_id,
            )
        return ValidationResult(ok=True)

    return _err(
        "UNKNOWN_COMMAND",
        "Unhandled command type",
        type=getattr(cmd, "type", str(type(cmd))),
    )
