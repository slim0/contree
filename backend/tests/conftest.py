"""Fixtures partagées pour tous les tests backend.

Les tests tournent contre une vraie instance PocketBase (binaire `pocketbase`
sur le PATH, ou `POCKETBASE_BIN`), démarrée une fois par session de tests sur
un port libre avec un data-dir temporaire. L'isolation entre tests se fait en
recréant les comptes de test (admin/testuser/testuser2) à chaque test, plutôt
qu'en isolant une base en mémoire.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from starlette.testclient import TestClient

from backend.api.limiter import limiter
from backend.auth.service import create_token
from backend.main import app
from backend.pocketbase.client import PocketBaseClient, get_pb_client
from backend.users.repository import UserRepository

TEST_ADMIN = "admin"
TEST_USER = "testuser"
TEST_USER2 = "testuser2"

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MIGRATIONS_DIR = _REPO_ROOT / "pocketbase" / "pb_migrations"
_POCKETBASE_BIN = os.getenv("POCKETBASE_BIN", "pocketbase")

_SU_EMAIL = "test-superuser@contree.local"
_SU_PASSWORD = "test-superuser-password-123"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def pb_server() -> Iterator[dict]:
    """Démarre une instance PocketBase jetable pour toute la session de tests."""
    data_dir = tempfile.mkdtemp(prefix="contree-pb-test-")
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"

    subprocess.run(
        [
            _POCKETBASE_BIN,
            "superuser",
            "upsert",
            _SU_EMAIL,
            _SU_PASSWORD,
            "--dir",
            data_dir,
            "--migrationsDir",
            str(_MIGRATIONS_DIR),
        ],
        check=True,
        capture_output=True,
    )

    proc = subprocess.Popen(
        [
            _POCKETBASE_BIN,
            "serve",
            f"--http=127.0.0.1:{port}",
            "--dir",
            data_dir,
            "--migrationsDir",
            str(_MIGRATIONS_DIR),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        deadline = time.monotonic() + 15
        ready = False
        while time.monotonic() < deadline:
            try:
                if httpx.get(f"{base_url}/api/health", timeout=1.0).status_code == 200:
                    ready = True
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.2)
        if not ready:
            out = proc.stdout.read().decode() if proc.stdout else ""
            proc.kill()
            raise RuntimeError(f"PocketBase de test n'a pas démarré à temps :\n{out}")

        yield {"base_url": base_url, "email": _SU_EMAIL, "password": _SU_PASSWORD}
    finally:
        proc.kill()
        proc.wait(timeout=5)
        shutil.rmtree(data_dir, ignore_errors=True)


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Réinitialise le compteur du rate limiter entre chaque test."""
    yield
    if hasattr(limiter, "_storage") and hasattr(limiter._storage, "reset"):
        limiter._storage.reset()


@pytest.fixture(autouse=True)
def pb_client(pb_server) -> Iterator[PocketBaseClient]:
    """Client PocketBase avec les comptes de test recréés pour chaque test."""
    pb = PocketBaseClient(
        base_url=pb_server["base_url"],
        superuser_email=pb_server["email"],
        superuser_password=pb_server["password"],
    )
    for record in pb.list_all():
        pb.delete(record["id"])

    repo = UserRepository(pb)
    repo.create(TEST_ADMIN, "Adm1n!pass", is_admin=True, must_change_password=False)
    repo.create(TEST_USER, "testpass123", must_change_password=False)
    repo.create(TEST_USER2, "testpass456", must_change_password=False)

    app.dependency_overrides[get_pb_client] = lambda: pb

    with (
        patch("backend.main._wait_for_pocketbase"),
        patch("backend.main._bootstrap_admin"),
    ):
        yield pb

    app.dependency_overrides.pop(get_pb_client, None)


@pytest.fixture
def client(pb_client):
    with TestClient(app) as c:
        yield c


def _make_token(pb_client: PocketBaseClient, username: str) -> str:
    user = UserRepository(pb_client).get_by_username(username)
    assert user, f"Utilisateur '{username}' introuvable dans PocketBase de test"
    return create_token(
        user.id, user.username, user.is_admin, user.must_change_password
    )


@pytest.fixture
def admin_client(pb_client):
    token = _make_token(pb_client, TEST_ADMIN)
    with TestClient(app, cookies={"access_token": token}) as c:
        yield c


@pytest.fixture
def auth_client(pb_client):
    token = _make_token(pb_client, TEST_USER)
    with TestClient(app, cookies={"access_token": token}) as c:
        yield c


@pytest.fixture
def auth_client2(pb_client):
    token = _make_token(pb_client, TEST_USER2)
    with TestClient(app, cookies={"access_token": token}) as c:
        yield c
