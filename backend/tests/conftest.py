from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from dndsim.api.main import app
from dndsim.db.base import Base
import dndsim.db.session as db_session
import dndsim.db.init_db as db_init
from dndsim.db.deps import get_db


@pytest.fixture(scope="session")
def engine():
    # SQLite in-memory (один коннект на всю сессию тестов)
    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    return eng


@pytest.fixture(scope="session")
def TestingSessionLocal(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@pytest.fixture(scope="session", autouse=True)
def _patch_db(engine, TestingSessionLocal):
    # патчим "боевые" engine/SessionLocal на тестовые
    db_session.engine = engine
    db_session.SessionLocal = TestingSessionLocal

    db_init.engine = engine

    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(TestingSessionLocal):
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
