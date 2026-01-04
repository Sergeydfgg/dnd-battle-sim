from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from dndsim.db.deps import get_db
from dndsim.db.models import Encounter, EncounterSave
from dndsim.api.schemas import (
    EncounterSaveCreate,
    EncounterSaveOut,
    EncounterSaveWithStateOut,
)


def _pack_save_payload(*, schema_version: int, state: dict, events: list[dict]) -> dict:
    return {
        "schema_version": int(schema_version),
        "state": state,
        "events": events,
    }


def _unpack_save_payload(state_json: dict) -> tuple[int, dict, list[dict]]:
    """
    Backward compatible:
    - если старые записи хранили просто state (без обёртки), то считаем schema_version=1, events=[]
    - если новые записи хранят обёртку {schema_version,state,events} — вытаскиваем поля
    """
    if isinstance(state_json, dict) and "state" in state_json:
        sv = int(state_json.get("schema_version", 1) or 1)
        st = state_json.get("state") or {}
        ev = state_json.get("events") or []
        if not isinstance(ev, list):
            ev = []
        return sv, st, ev

    # old format: just state
    return 1, (state_json if isinstance(state_json, dict) else {}), []


router = APIRouter(prefix="/encounters", tags=["encounter_saves"])


@router.post("/{encounter_id}/saves", response_model=EncounterSaveOut)
def create_save(
    encounter_id: str, payload: EncounterSaveCreate, db: Session = Depends(get_db)
):
    enc = db.get(Encounter, encounter_id)
    if not enc:
        raise HTTPException(status_code=404, detail="Encounter not found")

    obj = EncounterSave(
        encounter_id=encounter_id,
        label=payload.label,
        state_json=_pack_save_payload(
            schema_version=payload.schema_version,
            state=payload.state,
            events=payload.events,
        ),
    )

    db.add(obj)
    db.commit()
    db.refresh(obj)

    return EncounterSaveOut(
        id=obj.id,
        encounter_id=obj.encounter_id,
        label=obj.label,
        schema_version=payload.schema_version,
        created_at=obj.created_at,
    )


@router.get("/{encounter_id}/saves", response_model=list[EncounterSaveOut])
def list_saves(encounter_id: str, db: Session = Depends(get_db)):
    enc = db.get(Encounter, encounter_id)
    if not enc:
        raise HTTPException(status_code=404, detail="Encounter not found")

    items = (
        db.query(EncounterSave)
        .filter(EncounterSave.encounter_id == encounter_id)
        .order_by(EncounterSave.created_at.desc())
        .all()
    )
    return [
        EncounterSaveOut(
            id=s.id,
            encounter_id=s.encounter_id,
            label=s.label,
            schema_version=_unpack_save_payload(s.state_json)[0],
            created_at=s.created_at,
        )
        for s in items
    ]


@router.get("/{encounter_id}/saves/{save_id}", response_model=EncounterSaveWithStateOut)
def load_save(encounter_id: str, save_id: str, db: Session = Depends(get_db)):
    obj = db.get(EncounterSave, save_id)
    if not obj or obj.encounter_id != encounter_id:
        raise HTTPException(status_code=404, detail="Save not found")

    schema_version, state, events = _unpack_save_payload(obj.state_json)

    return EncounterSaveWithStateOut(
        id=obj.id,
        encounter_id=obj.encounter_id,
        label=obj.label,
        schema_version=schema_version,
        created_at=obj.created_at,
        state=state,
        events=events,
    )


@router.get("/saves/{save_id}", response_model=EncounterSaveWithStateOut)
def load_save_legacy(save_id: str, db: Session = Depends(get_db)):
    obj = db.get(EncounterSave, save_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Save not found")

    schema_version, state, events = _unpack_save_payload(obj.state_json)

    return EncounterSaveWithStateOut(
        id=obj.id,
        encounter_id=obj.encounter_id,
        label=obj.label,
        schema_version=schema_version,
        created_at=obj.created_at,
        state=state,
        events=events,
    )
