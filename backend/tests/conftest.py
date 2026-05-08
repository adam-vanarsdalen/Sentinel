from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db import models  # noqa: F401
from app.main import app


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def client(db_session: Session) -> TestClient:
    def _get_db_override():
        yield db_session

    app.dependency_overrides.clear()
    from app.db.session import get_db

    app.dependency_overrides[get_db] = _get_db_override

    # Disable Redis rate limiting in tests
    import app.api.routes.gateway as gw
    import app.api.routes.auth as auth

    gw.enforce_rate_limits = lambda **kwargs: None  # type: ignore[assignment]
    auth.enforce_login_rate_limits = lambda **kwargs: None  # type: ignore[assignment]

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def client_no_raise(db_session: Session) -> TestClient:
    def _get_db_override():
        yield db_session

    app.dependency_overrides.clear()
    from app.db.session import get_db

    app.dependency_overrides[get_db] = _get_db_override

    # Disable Redis rate limiting in tests
    import app.api.routes.gateway as gw
    import app.api.routes.auth as auth

    gw.enforce_rate_limits = lambda **kwargs: None  # type: ignore[assignment]
    auth.enforce_login_rate_limits = lambda **kwargs: None  # type: ignore[assignment]

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def new_id() -> str:
    return str(uuid.uuid4())
