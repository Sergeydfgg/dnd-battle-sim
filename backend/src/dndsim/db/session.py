from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# MVP: SQLite файл рядом с проектом; потом вынесем в env
DATABASE_URL = "sqlite:///./dndsim.sqlite3"

engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
