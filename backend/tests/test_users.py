"""Tests du repository utilisateurs et des routes /api/admin/*."""

from __future__ import annotations

from backend.auth.service import hash_password
from backend.users.repository import UserRepository

# ── UserRepository ────────────────────────────────────────────────────────────


def test_create_and_get_user(isolated_db):
    db = isolated_db()
    repo = UserRepository(db)
    user = repo.create("newuser", hash_password("pass"), must_change_password=True)
    assert user.id is not None
    assert user.username == "newuser"
    assert user.must_change_password is True

    fetched = repo.get_by_username("newuser")
    assert fetched is not None
    assert fetched.id == user.id
    db.close()


def test_get_by_id(isolated_db):
    db = isolated_db()
    repo = UserRepository(db)
    user = repo.get_by_username("testuser")
    assert user is not None
    by_id = repo.get_by_id(user.id)
    assert by_id is not None
    assert by_id.username == "testuser"
    db.close()


def test_list_all_includes_seeded_users(isolated_db):
    db = isolated_db()
    users = UserRepository(db).list_all()
    names = [u.username for u in users]
    assert "admin" in names
    assert "testuser" in names
    db.close()


def test_update_password_clears_must_change(isolated_db):
    db = isolated_db()
    repo = UserRepository(db)
    user = repo.create("needschange", hash_password("tmp"), must_change_password=True)
    updated = repo.update_password(user, hash_password("newpass"))
    assert updated.must_change_password is False
    db.close()


def test_delete_user(isolated_db):
    db = isolated_db()
    repo = UserRepository(db)
    user = repo.get_by_username("testuser")
    assert user is not None
    repo.delete(user)
    assert repo.get_by_username("testuser") is None
    db.close()


# ── Routes admin ──────────────────────────────────────────────────────────────


def test_list_users_as_admin(admin_client):
    r = admin_client.get("/api/admin/users")
    assert r.status_code == 200
    usernames = [u["username"] for u in r.json()]
    assert "admin" in usernames
    assert "testuser" in usernames


def test_list_users_forbidden_for_regular_user(auth_client):
    r = auth_client.get("/api/admin/users")
    assert r.status_code == 403


def test_list_users_unauthenticated(client):
    r = client.get("/api/admin/users")
    assert r.status_code == 401


def test_create_user_as_admin(admin_client):
    r = admin_client.post("/api/admin/users", json={"username": "nouveau"})
    assert r.status_code == 201
    body = r.json()
    assert body["user"]["username"] == "nouveau"
    assert body["user"]["must_change_password"] is True
    assert len(body["temp_password"]) == 12


def test_create_user_duplicate_returns_409(admin_client):
    r = admin_client.post("/api/admin/users", json={"username": "testuser"})
    assert r.status_code == 409


def test_delete_user_as_admin(admin_client):
    r = admin_client.delete("/api/admin/users/testuser")
    assert r.status_code == 204


def test_delete_own_account_forbidden(admin_client):
    r = admin_client.delete("/api/admin/users/admin")
    assert r.status_code == 400


def test_delete_unknown_user_returns_404(admin_client):
    r = admin_client.delete("/api/admin/users/inexistant")
    assert r.status_code == 404


def test_delete_user_forbidden_for_regular_user(auth_client):
    r = auth_client.delete("/api/admin/users/admin")
    assert r.status_code == 403
