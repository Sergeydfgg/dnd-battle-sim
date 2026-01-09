from __future__ import annotations

import json
import uuid
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List, Tuple

from fastapi import APIRouter, Depends, HTTPException
from pydantic import TypeAdapter
from sqlalchemy.orm import Session

from dndsim.api.schemas import (  # type: ignore
    AddCombatantRequest,
    ApplyCommandRequest,
    EncounterInitRequest,
    EncounterRuntimeResponse,
    GetEncounterStateResponse,
)
from dndsim.core.adapters.mapper import combatant_from_creature  # type: ignore
from dndsim.core.engine.commands import Command
from dndsim.core.engine.rules.apply import apply_command as engine_apply
from dndsim.core.persistence.runtime_store.load_latest_snapshot import (
    load_latest_snapshot,
)  # type: ignore
from dndsim.core.persistence.runtime_store.save_snapshot import save_snapshot  # type: ignore

from dndsim.core.persistence.state_codec import encounter_state_to_dict
from dndsim.db.deps import get_db  # type: ignore
from dndsim.db.models import Creature, Encounter  # type: ignore

router = APIRouter(prefix="/encounters", tags=["encounter-runtime"])


def _safe_dict(obj: Any) -> Dict[str, Any]:
    """
    Аккуратно превращает объект в dict (для событий/ORM fallback),
    чтобы не ловить bytes-ключи и ругань Pylance.
    """
    if obj is None:
        return {}

    if isinstance(obj, dict):
        return {str(k): v for k, v in obj.items()}

    md = getattr(obj, "model_dump", None)
    if callable(md):
        out = md()
        if isinstance(out, dict):
            return {str(k): v for k, v in out.items()}
        try:
            return {str(k): v for k, v in dict(out).items()}  # type: ignore[arg-type]
        except Exception:
            return {}

    dct = getattr(obj, "dict", None)
    if callable(dct):
        out = dct()
        if isinstance(out, dict):
            return {str(k): v for k, v in out.items()}
        try:
            return {str(k): v for k, v in dict(out).items()}  # type: ignore[arg-type]
        except Exception:
            return {}

    if is_dataclass(obj) and not isinstance(obj, type):
        out = asdict(obj)
        return {str(k): v for k, v in out.items()} if isinstance(out, dict) else {}

    # fallback: берём только “простые” атрибуты
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
        # не тащим relationship’ы SQLAlchemy и большие вложения
        if isinstance(v, (str, int, float, bool)) or v is None:
            res[str(k)] = v
    return res


def _make_empty_encounter_state():
    from dndsim.core.engine.state import EncounterState

    return EncounterState()


def _extract_creature_payload(creature_row: Any) -> Dict[str, Any]:
    """
    Достаём json-полезную нагрузку из Creature ORM:
    data / data_json / payload / payload_json / state_json
    """
    for key in ("data", "data_json", "payload", "payload_json", "state_json"):
        if hasattr(creature_row, key):
            val = getattr(creature_row, key)
            if isinstance(val, dict):
                return val
            if isinstance(val, str):
                try:
                    parsed = json.loads(val)
                    if isinstance(parsed, dict):
                        return parsed
                except Exception:
                    pass
    return _safe_dict(creature_row)


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

    state_obj = _make_empty_encounter_state()
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
        state=encounter_state_to_dict(state_obj),
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

    overrides = None
    if req.overrides:
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

    events_delta: List[Dict[str, Any]] = [
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
        events_delta=events_delta,
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
