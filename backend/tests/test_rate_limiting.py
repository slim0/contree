"""Tests de rate limiting — vérifie que les endpoints renvoient 429 après dépassement."""

from __future__ import annotations


def test_login_rate_limit(client):
    payload = {"username": "testuser", "password": "wrongpass"}
    for _ in range(5):
        client.post("/api/auth/login", json=payload)
    r = client.post("/api/auth/login", json=payload)
    assert r.status_code == 429


def test_change_password_rate_limit(auth_client):
    payload = {"old_password": "wrong", "new_password": "nouveauPass1!"}
    for _ in range(5):
        auth_client.post("/api/auth/change-password", json=payload)
    r = auth_client.post("/api/auth/change-password", json=payload)
    assert r.status_code == 429


def test_logout_rate_limit(auth_client):
    for _ in range(10):
        auth_client.post("/api/auth/logout")
    r = auth_client.post("/api/auth/logout")
    assert r.status_code == 429


def test_me_rate_limit(auth_client):
    for _ in range(60):
        auth_client.get("/api/auth/me")
    r = auth_client.get("/api/auth/me")
    assert r.status_code == 429


def test_my_stats_rate_limit(auth_client):
    for _ in range(60):
        auth_client.get("/api/users/me/stats")
    r = auth_client.get("/api/users/me/stats")
    assert r.status_code == 429


def test_admin_list_users_rate_limit(admin_client):
    for _ in range(30):
        admin_client.get("/api/admin/users")
    r = admin_client.get("/api/admin/users")
    assert r.status_code == 429


def test_admin_create_user_rate_limit(admin_client):
    for i in range(10):
        admin_client.post("/api/admin/users", json={"username": f"user{i}"})
    r = admin_client.post("/api/admin/users", json={"username": "overflow"})
    assert r.status_code == 429


def test_admin_delete_user_rate_limit(admin_client):
    for _ in range(10):
        admin_client.delete("/api/admin/users/nonexistent")
    r = admin_client.delete("/api/admin/users/nonexistent")
    assert r.status_code == 429


def test_rate_limit_resets_between_tests_login(client):
    """Vérifie que le reset du limiter entre tests fonctionne."""
    payload = {"username": "testuser", "password": "testpass123"}
    r = client.post("/api/auth/login", json=payload)
    assert r.status_code == 200
