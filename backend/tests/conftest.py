"""Fixtures partagées pour tous les tests backend."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from backend.api.limiter import limiter
from backend.auth.service import create_token, hash_password
from backend.db.database import Base, get_db
from backend.db import models as _db_models  # noqa: F401 — enregistre les modèles ORM dans Base.metadata
from backend.main import app
from backend.users.repository import UserRepository

TEST_ADMIN = "admin"
TEST_USER = "testuser"
TEST_USER2 = "testuser2"


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Réinitialise le compteur du rate limiter entre chaque test."""
    yield
    if hasattr(limiter, "_storage") and hasattr(limiter._storage, "reset"):
        limiter._storage.reset()


@pytest.fixture(autouse=True)
def isolated_db():
    """DB SQLite en mémoire pour chaque test + bootstrap des utilisateurs de test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    # Pré-créer les utilisateurs de test
    db = Session()
    try:
        repo = UserRepository(db)
        repo.create(TEST_ADMIN, hash_password("Adm1n!pass"), is_admin=True, must_change_password=False)
        repo.create(TEST_USER, hash_password("testpass123"), must_change_password=False)
        repo.create(TEST_USER2, hash_password("testpass456"), must_change_password=False)
    finally:
        db.close()

    with patch("backend.main.init_db"), patch("backend.main._bootstrap_admin"):
        yield Session

    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def client(isolated_db):
    with TestClient(app) as c:
        yield c


def _make_token(isolated_db, username: str) -> str:
    db = isolated_db()
    try:
        user = UserRepository(db).get_by_username(username)
        assert user, f"Utilisateur '{username}' introuvable dans la DB de test"
        return create_token(user.id, user.username, user.is_admin, user.must_change_password)
    finally:
        db.close()


@pytest.fixture
def admin_client(isolated_db):
    token = _make_token(isolated_db, TEST_ADMIN)
    with TestClient(app, cookies={"access_token": token}) as c:
        yield c


@pytest.fixture
def auth_client(isolated_db):
    token = _make_token(isolated_db, TEST_USER)
    with TestClient(app, cookies={"access_token": token}) as c:
        yield c


@pytest.fixture
def auth_client2(isolated_db):
    token = _make_token(isolated_db, TEST_USER2)
    with TestClient(app, cookies={"access_token": token}) as c:
        yield c
