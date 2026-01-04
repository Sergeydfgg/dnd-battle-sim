from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from dndsim.db.deps import get_db
from dndsim.db.models import Encounter
from dndsim.api.schemas import EncounterCreate, EncounterOut

router = APIRouter(prefix="/encounters", tags=["encounters"])


@router.get("", response_model=list[EncounterOut])
def list_encounters(db: Session = Depends(get_db)):
    items = db.query(Encounter).order_by(Encounter.created_at.desc()).all()
    return [
        EncounterOut(
            id=e.id,
            name=e.name,
            created_at=e.created_at,
            updated_at=e.updated_at,
        )
        for e in items
    ]


@router.get("/{encounter_id}", response_model=EncounterOut)
def get_encounter(encounter_id: str, db: Session = Depends(get_db)):
    obj = db.get(Encounter, encounter_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Encounter not found")

    return EncounterOut(
        id=obj.id,
        name=obj.name,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    )


@router.post("", response_model=EncounterOut)
def create_encounter(payload: EncounterCreate, db: Session = Depends(get_db)):
    obj = Encounter(name=payload.name)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return EncounterOut(
        id=obj.id,
        name=obj.name,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    )
