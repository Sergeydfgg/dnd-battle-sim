# scaffold_engine.ps1
# Запускать из корня репозитория: .\scripts\scaffold_engine.ps1
# Если запускаете из другой папки — поправьте $Root.

$Root = (Get-Location).Path

$files = @(
  @{
    Path = "backend\src\dndsim\core\engine\events.py"
    Content = @'
from __future__ import annotations

from typing import Any, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, ConfigDict


class RollMod(BaseModel):
    name: str
    value: int


class Roll(BaseModel):
    """
    Унифицированное описание броска (d20, урон и т.п.)
    """
    roll_id: UUID = Field(default_factory=uuid4)
    kind: Literal["d20", "damage", "other"]
    formula: str
    dice: list[int]
    kept: list[int]
    mods: list[RollMod] = Field(default_factory=list)
    total: int
    adv_state: Literal["normal", "advantage", "disadvantage"] = "normal"
    nat: Optional[int] = None  # натуральный d20 (если kind="d20")
    is_critical: bool = False


class EventEnvelope(BaseModel):
    """
    Общий конверт события.
    """
    model_config = ConfigDict(extra="forbid")

    event_id: UUID = Field(default_factory=uuid4)
    seq: int
    t: int
    type: str

    round: int
    turn_owner_id: Optional[str] = None
    actor_id: Optional[str] = None

    payload: dict[str, Any] = Field(default_factory=dict)


# --- Конкретные "фабрики" событий (удобно для apply.py) ---

def ev_turn_started(*, seq: int, t: int, round_: int, turn_owner_id: str) -> EventEnvelope:
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
            "damage_type": damage_type,
            "raw": raw,
            "adjusted": adjusted,
            "hp_before": hp_before,
            "hp_after": hp_after,
        },
    )


def ev_turn_ended(*, seq: int, t: int, round_: int, turn_owner_id: str) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        t=t,
        type="TurnEnded",
        round=round_,
        turn_owner_id=turn_owner_id,
        actor_id=turn_owner_id,
        payload={"combatant_id": turn_owner_id},
    )
'@
  },
  @{
    Path = "backend\src\dndsim\core\engine\commands.py"
    Content = @'
from __future__ import annotations

from typing import Literal, Union
from pydantic import BaseModel, ConfigDict


class CommandBase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str


class BeginTurn(CommandBase):
    type: Literal["BeginTurn"] = "BeginTurn"
    combatant_id: str


class EndTurn(CommandBase):
    type: Literal["EndTurn"] = "EndTurn"
    combatant_id: str


class Attack(CommandBase):
    type: Literal["Attack"] = "Attack"
    attacker_id: str
    target_id: str
    attack_name: str
    attack_kind: Literal["melee", "ranged"] = "melee"


Command = Union[BeginTurn, EndTurn, Attack]
'@
  },
  @{
    Path = "backend\src\dndsim\core\engine\state.py"
    Content = @'
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from random import Random


@dataclass
class AttackProfile:
    name: str
    to_hit_bonus: int
    damage_formula: str  # например "1d8+3"
    damage_type: str = "slashing"


@dataclass
class CombatantState:
    id: str
    name: str
    ac: int
    hp_current: int
    hp_max: int
    speed_ft: int = 30

    # ресурсы хода
    action_available: bool = True
    bonus_available: bool = True
    reaction_available: bool = True
    movement_remaining_ft: int = 0

    # статусы (минимум)
    surprised: bool = False
    has_taken_first_turn: bool = False

    attacks: Dict[str, AttackProfile] = field(default_factory=dict)


@dataclass
class EncounterState:
    # “время”
    round: int = 1
    turn_owner_id: Optional[str] = None
    initiative_order: List[str] = field(default_factory=list)

    # фаза
    phase: str = "idle"  # "idle" | "in_turn" | "finished"

    # события (счётчики)
    seq: int = 0
    t: int = 0

    # участники
    combatants: Dict[str, CombatantState] = field(default_factory=dict)

    # RNG
    rng_seed: int = 0
    rng: Random = field(default_factory=Random)

    def with_seed(self, seed: int) -> "EncounterState":
        self.rng_seed = seed
        self.rng = Random(seed)
        return self
'@
  },
  @{
    Path = "backend\src\dndsim\core\engine\rules\validator.py"
    Content = @'
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from dndsim.core.engine.commands import Attack, BeginTurn, EndTurn, Command
from dndsim.core.engine.state import EncounterState


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
    return ValidationResult(ok=False, errors=[ValidationError(code=code, message=message, meta=meta)])


def validate_command(state: EncounterState, cmd: Command) -> ValidationResult:
    # базовые проверки существования
    if isinstance(cmd, BeginTurn):
        if cmd.combatant_id not in state.combatants:
            return _err("UNKNOWN_COMBATANT", "Unknown combatant_id", combatant_id=cmd.combatant_id)

        if state.turn_owner_id != cmd.combatant_id:
            return _err(
                "NOT_YOUR_TURN",
                "BeginTurn can be called only for current turn owner",
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
            return _err("NOT_IN_TURN", "EndTurn requires in_turn phase", phase=state.phase)
        return ValidationResult(ok=True)

    if isinstance(cmd, Attack):
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

        if state.phase != "in_turn":
            return _err("NOT_IN_TURN", "Attack requires in_turn phase", phase=state.phase)

        # surprise блок
        if attacker.surprised and not attacker.has_taken_first_turn:
            return _err("SURPRISED_BLOCK", "Surprised creature cannot take actions on its first turn")

        if not attacker.action_available:
            return _err("NO_ACTION", "No action available this turn")

        if cmd.attack_name not in attacker.attacks:
            return _err("UNKNOWN_ATTACK", "Attacker does not have this attack", attack_name=cmd.attack_name)

        return ValidationResult(ok=True, cost_preview={"action": 1})

    return _err("UNKNOWN_COMMAND", "Unhandled command type", type=getattr(cmd, "type", str(type(cmd))))
'@
  },
  @{
    Path = "backend\src\dndsim\core\engine\rules\apply.py"
    Content = @'
from __future__ import annotations

import re
from typing import List, Tuple

from dndsim.core.engine.commands import Attack, BeginTurn, EndTurn, Command
from dndsim.core.engine.events import (
    Roll, RollMod,
    ev_turn_started, ev_turn_resources_reset, ev_turn_ended,
    ev_attack_declared, ev_attack_rolled, ev_hit_confirmed, ev_miss_confirmed,
    ev_damage_rolled, ev_damage_applied,
)
from dndsim.core.engine.rules.validator import validate_command
from dndsim.core.engine.state import EncounterState


_DICE_RE = re.compile(r"^\s*(\d+)d(\d+)\s*([+-]\s*\d+)?\s*$")


def _parse_dice(formula: str) -> Tuple[int, int, int]:
    """
    '2d6+3' -> (2, 6, 3)
    """
    m = _DICE_RE.match(formula)
    if not m:
        raise ValueError(f"Unsupported dice formula: {formula!r}")
    n = int(m.group(1))
    d = int(m.group(2))
    mod = m.group(3)
    k = int(mod.replace(" ", "")) if mod else 0
    return n, d, k


def _roll_d20(state: EncounterState, bonus: int) -> Roll:
    nat = state.rng.randint(1, 20)
    total = nat + bonus
    is_crit = (nat == 20)
    return Roll(
        kind="d20",
        formula=f"1d20+{bonus}",
        dice=[nat],
        kept=[nat],
        mods=[RollMod(name="to_hit_bonus", value=bonus)],
        total=total,
        nat=nat,
        is_critical=is_crit,
        adv_state="normal",
    )


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


def apply_command(state: EncounterState, cmd: Command) -> Tuple[EncounterState, List[dict]]:
    """
    Возвращаем (new_state, events_as_dicts).
    Для MVP удобно отдавать events уже как dict (UI/тесты).
    """
    vr = validate_command(state, cmd)
    if not vr.ok:
        # В MVP: выбрасываем исключение, чтобы тесты сразу ловили ошибки.
        # Позже можно возвращать отдельное событие CommandRejected.
        e = vr.errors[0]
        raise ValueError(f"{e.code}: {e.message} ({e.meta})")

    events = []

    if isinstance(cmd, BeginTurn):
        c = state.combatants[cmd.combatant_id]
        state.phase = "in_turn"

        # reset ресурсов хода
        c.action_available = True
        c.bonus_available = True
        c.reaction_available = True
        c.movement_remaining_ft = c.speed_ft

        seq, t = _bump(state)
        events.append(ev_turn_started(seq=seq, t=t, round_=state.round, turn_owner_id=cmd.combatant_id).model_dump())

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

    if isinstance(cmd, Attack):
        attacker = state.combatants[cmd.attacker_id]
        target = state.combatants[cmd.target_id]
        profile = attacker.attacks[cmd.attack_name]

        # тратим Action
        attacker.action_available = False

        seq, t = _bump(state)
        events.append(
            ev_attack_declared(
                seq=seq,
                t=t,
                round_=state.round,
                turn_owner_id=state.turn_owner_id or cmd.attacker_id,
                attacker_id=cmd.attacker_id,
                target_id=cmd.target_id,
                attack_name=cmd.attack_name,
                attack_kind=cmd.attack_kind,
            ).model_dump()
        )

        # бросок атаки
        atk_roll = _roll_d20(state, profile.to_hit_bonus)
        seq, t = _bump(state)
        events.append(
            ev_attack_rolled(
                seq=seq,
                t=t,
                round_=state.round,
                turn_owner_id=state.turn_owner_id or cmd.attacker_id,
                attacker_id=cmd.attacker_id,
                target_id=cmd.target_id,
                roll=atk_roll,
                to_hit_bonus=profile.to_hit_bonus,
                target_ac=target.ac,
            ).model_dump()
        )

        # auto miss on nat1, auto crit on nat20 (nat20 уже в roll)
        if atk_roll.nat == 1:
            margin = atk_roll.total - target.ac
            seq, t = _bump(state)
            events.append(
                ev_miss_confirmed(
                    seq=seq,
                    t=t,
                    round_=state.round,
                    turn_owner_id=state.turn_owner_id or cmd.attacker_id,
                    attacker_id=cmd.attacker_id,
                    target_id=cmd.target_id,
                    margin=margin,
                ).model_dump()
            )
            return state, events

        hit = atk_roll.total >= target.ac
        margin = atk_roll.total - target.ac

        if not hit:
            seq, t = _bump(state)
            events.append(
                ev_miss_confirmed(
                    seq=seq,
                    t=t,
                    round_=state.round,
                    turn_owner_id=state.turn_owner_id or cmd.attacker_id,
                    attacker_id=cmd.attacker_id,
                    target_id=cmd.target_id,
                    margin=margin,
                ).model_dump()
            )
            return state, events

        # попадание
        seq, t = _bump(state)
        events.append(
            ev_hit_confirmed(
                seq=seq,
                t=t,
                round_=state.round,
                turn_owner_id=state.turn_owner_id or cmd.attacker_id,
                attacker_id=cmd.attacker_id,
                target_id=cmd.target_id,
                is_critical=atk_roll.is_critical,
                margin=margin,
            ).model_dump()
        )

        # урон
        dmg_roll = _roll_damage(state, profile.damage_formula, crit=atk_roll.is_critical)
        seq, t = _bump(state)
        events.append(
            ev_damage_rolled(
                seq=seq,
                t=t,
                round_=state.round,
                turn_owner_id=state.turn_owner_id or cmd.attacker_id,
                attacker_id=cmd.attacker_id,
                target_id=cmd.target_id,
                roll=dmg_roll,
                damage_type=profile.damage_type,
            ).model_dump()
        )

        hp_before = target.hp_current
        adjusted = max(0, dmg_roll.total)  # resist/vuln позже
        target.hp_current = max(0, target.hp_current - adjusted)
        hp_after = target.hp_current

        seq, t = _bump(state)
        events.append(
            ev_damage_applied(
                seq=seq,
                t=t,
                round_=state.round,
                turn_owner_id=state.turn_owner_id or cmd.attacker_id,
                attacker_id=cmd.attacker_id,
                target_id=cmd.target_id,
                raw=dmg_roll.total,
                adjusted=adjusted,
                damage_type=profile.damage_type,
                hp_before=hp_before,
                hp_after=hp_after,
            ).model_dump()
        )

        return state, events

    if isinstance(cmd, EndTurn):
        owner = state.turn_owner_id or cmd.combatant_id
        c = state.combatants[owner]

        # отметим, что он "первый ход" уже сделал (важно для surprise)
        c.has_taken_first_turn = True

        seq, t = _bump(state)
        events.append(ev_turn_ended(seq=seq, t=t, round_=state.round, turn_owner_id=owner).model_dump())

        # переход хода
        state.phase = "idle"
        if state.initiative_order:
            idx = state.initiative_order.index(owner)
            next_idx = idx + 1
            if next_idx >= len(state.initiative_order):
                # новый раунд
                state.round += 1
                next_idx = 0
            state.turn_owner_id = state.initiative_order[next_idx]

        return state, events

    raise ValueError(f"Unhandled command: {cmd}")
'@
  }
)

foreach ($f in $files) {
  $rel = $f.Path
  $abs = Join-Path $Root $rel
  $dir = Split-Path $abs -Parent
  if (-not (Test-Path $dir)) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
  }

  # Записываем UTF-8 без BOM (лучше для питона и git)
  $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($abs, $f.Content, $utf8NoBom)

  Write-Host "Wrote $rel"
}

Write-Host "Done."
