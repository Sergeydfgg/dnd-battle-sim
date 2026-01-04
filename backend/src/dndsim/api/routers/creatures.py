from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from dndsim.db.deps import get_db
from dndsim.db.models import Creature
from dndsim.api.schemas import CreatureCreate, CreatureUpdate, CreatureOut, CreatureData

router = APIRouter(prefix="/creatures", tags=["creatures"])


@router.get("", response_model=list[CreatureOut])
def list_creatures(db: Session = Depends(get_db)):
    items = db.query(Creature).order_by(Creature.created_at.desc()).all()
    return [
        CreatureOut(
            id=c.id,
            name=c.name,
            data=CreatureData.model_validate(c.data_json),
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in items
    ]


@router.post("", response_model=CreatureOut)
def create_creature(payload: CreatureCreate, db: Session = Depends(get_db)):
    obj = Creature(
        name=payload.name,
        data_json=payload.data.model_dump(by_alias=True),
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return CreatureOut(
        id=obj.id,
        name=obj.name,
        data=CreatureData.model_validate(obj.data_json),
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    )


@router.get("/{creature_id}", response_model=CreatureOut)
def get_creature(creature_id: str, db: Session = Depends(get_db)):
    obj = db.get(Creature, creature_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Creature not found")

    return CreatureOut(
        id=obj.id,
        name=obj.name,
        data=CreatureData.model_validate(obj.data_json),
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    )


@router.patch("/{creature_id}", response_model=CreatureOut)
def patch_creature(
    creature_id: str, payload: CreatureUpdate, db: Session = Depends(get_db)
):
    obj = db.get(Creature, creature_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Creature not found")

    if payload.name is not None:
        obj.name = payload.name
    if payload.data is not None:
        obj.data_json = payload.data.model_dump(by_alias=True)

    db.add(obj)
    db.commit()
    db.refresh(obj)

    return CreatureOut(
        id=obj.id,
        name=obj.name,
        data=CreatureData.model_validate(obj.data_json),
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    )


@router.put("/{creature_id}", response_model=CreatureOut)
def update_creature(
    creature_id: str, payload: CreatureUpdate, db: Session = Depends(get_db)
):
    obj = db.get(Creature, creature_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Creature not found")

    if payload.name is not None:
        obj.name = payload.name
    if payload.data is not None:
        obj.data_json = payload.data.model_dump(by_alias=True)

    db.add(obj)
    db.commit()
    db.refresh(obj)

    return CreatureOut(
        id=obj.id,
        name=obj.name,
        data=CreatureData.model_validate(obj.data_json),
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    )
