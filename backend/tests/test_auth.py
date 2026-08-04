"""Tests du service d'authentification et des routes /api/auth/*."""

from __future__ import annotations

import jwt
import pytest

from backend.auth.service import create_token, decode_token, generate_temp_password

# ── Service unitaire ──────────────────────────────────────────────────────────


def test_generate_temp_password_length():
    pwd = generate_temp_password(12)
    assert len(pwd) == 12


def test_generate_temp_password_uniqueness():
    passwords = {generate_temp_password() for _ in range(20)}
    assert len(passwords) > 1  # très improbable d'avoir des doublons


def test_create_and_decode_token():
    token = create_token("abc123def456xyz", "alice", False, False)
    payload = decode_token(token)
    assert payload["sub"] == "abc123def456xyz"
    assert payload["username"] == "alice"
    assert payload["is_admin"] is False
    assert payload["must_change_password"] is False


def test_decode_invalid_token_raises():
    with pytest.raises(jwt.InvalidTokenError):
        decode_token("token.invalide.ici")


# ── Routes HTTP ───────────────────────────────────────────────────────────────


def test_login_success(client):
    r = client.post(
        "/api/auth/login", json={"username": "testuser", "password": "testpass123"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "testuser"
    assert body["must_change_password"] is False
    assert "access_token" in r.cookies


def test_login_wrong_password(client):
    r = client.post(
        "/api/auth/login", json={"username": "testuser", "password": "mauvais"}
    )
    assert r.status_code == 401


def test_login_unknown_user(client):
    r = client.post(
        "/api/auth/login", json={"username": "inconnu", "password": "anything"}
    )
    assert r.status_code == 401


def test_me_authenticated(auth_client):
    r = auth_client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["username"] == "testuser"


def test_me_unauthenticated(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_logout_clears_cookie(auth_client):
    r = auth_client.post("/api/auth/logout")
    assert r.status_code == 200
    # Le cookie doit être supprimé
    assert "access_token" not in r.cookies or r.cookies["access_token"] == ""


def test_change_password_success(auth_client):
    r = auth_client.post(
        "/api/auth/change-password",
        json={"old_password": "testpass123", "new_password": "nouveauPass1!"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["must_change_password"] is False
    assert "access_token" in r.cookies


def test_change_password_wrong_old(auth_client):
    r = auth_client.post(
        "/api/auth/change-password",
        json={"old_password": "mauvais", "new_password": "nouveauPass1!"},
    )
    assert r.status_code == 400


def test_change_password_too_short(auth_client):
    r = auth_client.post(
        "/api/auth/change-password",
        json={"old_password": "testpass123", "new_password": "court"},
    )
    assert r.status_code == 400


def test_change_password_unauthenticated(client):
    r = client.post(
        "/api/auth/change-password",
        json={"old_password": "testpass123", "new_password": "nouveauPass1!"},
    )
    assert r.status_code == 401


# ── Auto-inscription + validation admin ───────────────────────────────────────


def test_register_creates_unapproved_user_blocked_at_login(client):
    r = client.post(
        "/api/auth/register",
        json={"username": "newplayer", "password": "chosenPass1"},
    )
    assert r.status_code == 201
    assert "access_token" not in r.cookies  # pas de login automatique

    # Compte non approuvé : login refusé (403), même avec le bon mot de passe.
    r = client.post(
        "/api/auth/login",
        json={"username": "newplayer", "password": "chosenPass1"},
    )
    assert r.status_code == 403


def test_register_then_approve_allows_login(client, admin_client):
    client.post(
        "/api/auth/register",
        json={"username": "waiting", "password": "chosenPass1"},
    )
    r = admin_client.post("/api/admin/users/waiting/approve")
    assert r.status_code == 200
    assert r.json()["is_approved"] is True

    r = client.post(
        "/api/auth/login",
        json={"username": "waiting", "password": "chosenPass1"},
    )
    assert r.status_code == 200
    assert "access_token" in r.cookies


def test_register_duplicate_username_returns_409(client):
    r = client.post(
        "/api/auth/register",
        json={"username": "testuser", "password": "chosenPass1"},
    )
    assert r.status_code == 409


def test_register_password_too_short_rejected(client):
    r = client.post(
        "/api/auth/register",
        json={"username": "shorty", "password": "court"},
    )
    assert r.status_code == 422


def test_admin_created_user_can_login_immediately(admin_client, client):
    r = admin_client.post("/api/admin/users", json={"username": "byadmin"})
    assert r.status_code == 201
    temp = r.json()["temp_password"]

    r = client.post(
        "/api/auth/login", json={"username": "byadmin", "password": temp}
    )
    assert r.status_code == 200
