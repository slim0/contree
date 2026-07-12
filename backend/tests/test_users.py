"""Tests du repository utilisateurs et des routes /api/admin/*."""

from __future__ import annotations

from backend.users.repository import UserRepository

# ── UserRepository ────────────────────────────────────────────────────────────


def test_create_and_get_user(pb_client):
    repo = UserRepository(pb_client)
    user = repo.create("newuser", "pass1234", must_change_password=True)
    assert user.id is not None
    assert user.username == "newuser"
    assert user.must_change_password is True

    fetched = repo.get_by_username("newuser")
    assert fetched is not None
    assert fetched.id == user.id


def test_get_by_id(pb_client):
    repo = UserRepository(pb_client)
    user = repo.get_by_username("testuser")
    assert user is not None
    by_id = repo.get_by_id(user.id)
    assert by_id is not None
    assert by_id.username == "testuser"


def test_list_all_includes_seeded_users(pb_client):
    users = UserRepository(pb_client).list_all()
    names = [u.username for u in users]
    assert "admin" in names
    assert "testuser" in names


def test_update_password_clears_must_change(pb_client):
    repo = UserRepository(pb_client)
    user = repo.create("needschange", "tmp12345", must_change_password=True)
    updated = repo.update_password(user, "newpass123")
    assert updated.must_change_password is False


def test_verify_credentials_success(pb_client):
    repo = UserRepository(pb_client)
    user = repo.verify_credentials("testuser", "testpass123")
    assert user is not None
    assert user.username == "testuser"


def test_verify_credentials_wrong_password(pb_client):
    repo = UserRepository(pb_client)
    assert repo.verify_credentials("testuser", "wrongpass") is None


def test_delete_user(pb_client):
    repo = UserRepository(pb_client)
    user = repo.get_by_username("testuser")
    assert user is not None
    repo.delete(user)
    assert repo.get_by_username("testuser") is None


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
