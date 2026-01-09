from __future__ import annotations

import uuid
from dataclasses import is_dataclass, asdict
from typing import Any, Dict, List, Tuple, Optional

from pydantic import TypeAdapter
from dndsim.core.engine.commands import Command
from dndsim.core.engine.rules.apply import apply_command as engine_apply
from dndsim.core.persistence.state_codec import encounter_state_to_dict


from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from dndsim.api.schemas import (  # type: ignore
    EncounterInitRequest,
    EncounterRuntimeResponse,
    AddCombatantRequest,
    ApplyCommandRequest,
    GetEncounterStateResponse,
)
from dndsim.db.deps import get_db  # type: ignore
from dndsim.db.models import Encounter, Creature  # type: ignore

from dndsim.core.adapters.mapper import combatant_from_creature  # type: ignore
from dndsim.core.persistence.runtime_store import load_latest_snapshot, save_snapshot  # type: ignore


router = APIRouter(prefix="/encounters", tags=["encounter-runtime"])


from collections.abc import Mapping as ABCMapping
from typing import cast


def _to_dict(obj: Any) -> Dict[str, Any]:
    """
    Безопасно приводит объект к dict[str, Any]:
    - гарантирует str-ключи
    - не делает dict(out) без проверки (чтобы не ловить bytes keys)
    - не вызывает asdict на классе dataclass
    """
    if obj is None:
        return {}

    if isinstance(obj, dict):
        return {str(k): cast(Any, v) for k, v in obj.items()}

    md = getattr(obj, "model_dump", None)
    if callable(md):
        out = md()
        if isinstance(out, dict):
            return {str(k): cast(Any, v) for k, v in out.items()}
        if isinstance(out, ABCMapping):
            return {str(k): cast(Any, v) for k, v in out.items()}
        return {}

    dct = getattr(obj, "dict", None)
    if callable(dct):
        out = dct()
        if isinstance(out, dict):
            return {str(k): cast(Any, v) for k, v in out.items()}
        if isinstance(out, ABCMapping):
            return {str(k): cast(Any, v) for k, v in out.items()}
        return {}

    # dataclass instance only (важно: is_dataclass(class) тоже True)
    if is_dataclass(obj) and not isinstance(obj, type):
        out = asdict(cast(Any, obj))
        if isinstance(out, dict):
            return {str(k): cast(Any, v) for k, v in out.items()}
        return {}

    # fallback: объект с атрибутами (очень осторожно)
    res: Dict[str, Any] = {}
    for k in dir(obj):
        if k.startswith("_"):
            continue
        try:
            v = getattr(obj, k)
        except Exception:
            continue
        if callable(v):
            continue
        # не тащим большие вложения / relationship'ы
        if isinstance(v, (str, int, float, bool)) or v is None:
            res[str(k)] = v
    return res


def _make_empty_encounter_state():
    from dndsim.core.engine.state import EncounterState

    return EncounterState()


def _get_state_combatants_container(state_obj: Any) -> Dict[str, Any]:
    """
    Достаём контейнер combatants из EncounterState.
    """
    if isinstance(state_obj, dict):
        state_obj.setdefault("combatants", {})
        combatants = state_obj["combatants"]
        if isinstance(combatants, dict):
            return combatants
        state_obj["combatants"] = {}
        return state_obj["combatants"]

    if hasattr(state_obj, "combatants"):
        combatants = getattr(state_obj, "combatants")
        if isinstance(combatants, dict):
            return combatants
        # если не dict — заменим
        setattr(state_obj, "combatants", {})
        return getattr(state_obj, "combatants")

    # если нет поля — заведём как атрибут
    setattr(state_obj, "combatants", {})
    return getattr(state_obj, "combatants")


def _extract_creature_payload(creature_row: Any) -> Dict[str, Any]:
    """
    Пытаемся достать json-полезную нагрузку из Creature ORM:
    data / data_json / payload / state_json ...
    """
    for key in ("data", "data_json", "payload", "payload_json", "state_json"):
        if hasattr(creature_row, key):
            val = getattr(creature_row, key)
            if isinstance(val, dict):
                return val
            if isinstance(val, str):
                import json

                try:
                    parsed = json.loads(val)
                    if isinstance(parsed, dict):
                        return parsed
                except Exception:
                    pass
    # fallback: пробуем собрать из полей ORM
    return _to_dict(creature_row)


@router.post("/{encounter_id}/state:init", response_model=EncounterRuntimeResponse)
def init_state(
    encounter_id: int, req: EncounterInitRequest, db: Session = Depends(get_db)
):
    enc = db.query(Encounter).filter(Encounter.id == encounter_id).first()  # type: ignore
    if not enc:
        raise HTTPException(status_code=404, detail="Encounter not found")

    latest_id, latest_state_obj, _latest_events = load_latest_snapshot(db, encounter_id)
    if (
        latest_id is not None
        and latest_state_obj is not None
        and not req.reset_existing
    ):
        return EncounterRuntimeResponse(
            encounter_id=encounter_id,
            save_id=latest_id,
            state=encounter_state_to_dict(latest_state_obj),
            events_delta=[],
        )

    # создаём пустое состояние
    state_obj = _make_empty_encounter_state()
    # сохраняем
    row = save_snapshot(
        db,
        encounter_id=encounter_id,
        label=req.label,
        state=state_obj,
        events_delta=[],
    )

    return EncounterRuntimeResponse(
        encounter_id=encounter_id,
        save_id=int(row.id),  # type: ignore
        state=_to_dict(state_obj),
        events_delta=[],
    )


@router.post("/{encounter_id}/combatants:add", response_model=EncounterRuntimeResponse)
def add_combatant(
    encounter_id: int, req: AddCombatantRequest, db: Session = Depends(get_db)
):
    enc = db.query(Encounter).filter(Encounter.id == encounter_id).first()  # type: ignore
    if not enc:
        raise HTTPException(status_code=404, detail="Encounter not found")

    save_id, state_obj, _events = load_latest_snapshot(db, encounter_id)
    if save_id is None or state_obj is None:
        state_obj = _make_empty_encounter_state()

    creature_row = db.query(Creature).filter(Creature.id == req.creature_id).first()  # type: ignore
    if not creature_row:
        raise HTTPException(status_code=404, detail="Creature not found")

    creature_payload = _extract_creature_payload(creature_row)

    combatant_id = req.combatant_id or f"{req.creature_id}-{uuid.uuid4().hex[:8]}"
    pos = (req.position.x, req.position.y)

    # overrides прокидываем в mapper как есть (он уже умеет dict)
    overrides = None
    if req.overrides:
        # попробуем создать CombatantOverrides, если доступен
        try:
            from dndsim.core.adapters.mapper import CombatantOverrides  # type: ignore

            overrides = CombatantOverrides(**req.overrides)
        except Exception:
            overrides = None

    combatant = combatant_from_creature(
        creature_payload,
        combatant_id=combatant_id,
        side=req.side,
        position=pos,
        overrides=overrides,
    )
    if combatant_id in state_obj.combatants:
        raise HTTPException(
            status_code=409, detail="combatant_id already exists in encounter"
        )

    state_obj.combatants[combatant_id] = combatant

    events_delta = [
        {
            "type": "CombatantAdded",
            "combatant_id": combatant_id,
            "creature_id": req.creature_id,
            "side": req.side,
        }
    ]

    row = save_snapshot(
        db,
        encounter_id=encounter_id,
        label=req.label,
        state=state_obj,
        events_delta=events_delta,
    )

    return EncounterRuntimeResponse(
        encounter_id=encounter_id,
        save_id=int(row.id),  # type: ignore
        state=encounter_state_to_dict(state_obj),
        events_delta=[_to_dict(e) for e in events_delta],
    )


@router.post("/{encounter_id}/commands:apply", response_model=EncounterRuntimeResponse)
def apply_command(
    encounter_id: int, req: ApplyCommandRequest, db: Session = Depends(get_db)
):
    enc = db.query(Encounter).filter(Encounter.id == encounter_id).first()  # type: ignore
    if not enc:
        raise HTTPException(status_code=404, detail="Encounter not found")

    save_id, state_obj, _events = load_latest_snapshot(db, encounter_id)
    if save_id is None or state_obj is None:
        raise HTTPException(
            status_code=409,
            detail="Encounter is not initialized. Call state:init first.",
        )

    try:
        # ✅ правильный способ: Command — Union, парсим через TypeAdapter
        cmd_obj = TypeAdapter(Command).validate_python(req.command)
        new_state, events_delta = engine_apply(state_obj, cmd_obj)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Command apply failed: {e}")

    row = save_snapshot(
        db,
        encounter_id=encounter_id,
        label=req.label,
        state=new_state,
        events_delta=events_delta,
    )

    return EncounterRuntimeResponse(
        encounter_id=encounter_id,
        save_id=int(row.id),  # type: ignore
        state=encounter_state_to_dict(new_state),
        events_delta=events_delta,
    )


@router.get("/{encounter_id}/state", response_model=GetEncounterStateResponse)
def get_state(encounter_id: int, db: Session = Depends(get_db)):
    enc = db.query(Encounter).filter(Encounter.id == encounter_id).first()  # type: ignore
    if not enc:
        raise HTTPException(status_code=404, detail="Encounter not found")

    save_id, state_obj, _events = load_latest_snapshot(db, encounter_id)
    if save_id is None or state_obj is None:
        raise HTTPException(status_code=404, detail="No saved state for encounter")

    return GetEncounterStateResponse(
        encounter_id=encounter_id,
        save_id=save_id,
        state=encounter_state_to_dict(state_obj),
    )
