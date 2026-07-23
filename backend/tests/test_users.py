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


# ── Statistiques ────────────────────────────────────────────────────────────────


def test_new_user_stats_default_to_zero(pb_client):
    repo = UserRepository(pb_client)
    user = repo.create("brandnew", "pass12345")
    assert user.games_played == 0
    assert user.games_won == 0
    assert user.games_lost == 0
    assert user.capots_won == 0
    assert user.generales_won == 0
    assert user.contracts_taken == 0
    assert user.contracts_made == 0
    assert user.win_rate is None
    assert user.contract_success_rate is None


def test_increment_stats_accumulates(pb_client):
    repo = UserRepository(pb_client)
    user = repo.get_by_username("testuser")
    assert user is not None
    repo.increment_stats(user.id, {"games_played": 1, "games_won": 1})
    repo.increment_stats(user.id, {"games_played": 1})
    updated = repo.get_by_username("testuser")
    assert updated is not None
    assert updated.games_played == 2
    assert updated.games_won == 1


def test_win_rate_and_contract_success_rate_computed(pb_client):
    repo = UserRepository(pb_client)
    user = repo.get_by_username("testuser")
    assert user is not None
    updated = repo.increment_stats(
        user.id,
        {
            "games_played": 3,
            "games_won": 2,
            "contracts_taken": 4,
            "contracts_made": 3,
        },
    )
    assert updated.win_rate == 2 / 3
    assert updated.contract_success_rate == 3 / 4


# ── Routes admin ──────────────────────────────────────────────────────────────


def test_list_users_as_admin(admin_client):
    r = admin_client.get("/api/admin/users")
    assert r.status_code == 200
    body = r.json()
    usernames = [u["username"] for u in body]
    assert "admin" in usernames
    assert "testuser" in usernames
    testuser = next(u for u in body if u["username"] == "testuser")
    assert testuser["games_played"] == 0
    assert testuser["win_rate"] is None


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


# ── Route /api/users/me/stats ───────────────────────────────────────────────────


def test_my_stats_returns_own_stats(auth_client):
    r = auth_client.get("/api/users/me/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "testuser"
    assert body["games_played"] == 0
    assert body["win_rate"] is None


def test_my_stats_reflects_increments(pb_client, auth_client):
    repo = UserRepository(pb_client)
    user = repo.get_by_username("testuser")
    assert user is not None
    repo.increment_stats(user.id, {"games_played": 1, "games_won": 1})

    r = auth_client.get("/api/users/me/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["games_played"] == 1
    assert body["games_won"] == 1
    assert body["win_rate"] == 1.0


def test_my_stats_unauthenticated(client):
    r = client.get("/api/users/me/stats")
    assert r.status_code == 401
