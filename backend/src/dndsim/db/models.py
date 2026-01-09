from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from sqlalchemy import Column, Integer, Text
from sqlalchemy.orm import relationship
from .base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Creature(Base):
    __tablename__ = "creatures"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)

    # всё содержимое существа (ac/hp/attacks/spellcasting/...) кладём сюда
    data_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Encounter(Base):
    __tablename__ = "encounters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class EncounterSave(Base):
    __tablename__ = "encounter_saves"

    id = Column(Integer, primary_key=True)
    encounter_id = Column(Integer, ForeignKey("encounter.id"))
    label = Column(String, nullable=True)
    state_json = Column(Text, nullable=False)  # хранение сериализованного состояния
    events_json = Column(Text, nullable=False)  # хранение списка событий
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    encounter = relationship("Encounter", back_populates="saves")
