#!/usr/bin/env python3
"""Seed de dev : crée 4 joueurs test en base SQLite avec must_change_password=False."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.db.database import DATABASE_URL, SessionLocal, init_db
from backend.users.repository import UserRepository
from backend.auth.service import hash_password

PLAYERS = [
    {"username": "admin",   "password": "tuzjIk-hyrcom-mopfa1"},
    {"username": "alice",   "password": "alice1234"},
    {"username": "bob",     "password": "bob12345!"},
    {"username": "charlie", "password": "charlie1"},
    {"username": "diana",   "password": "diana123"},
]


def seed() -> None:
    print(f"Base : {DATABASE_URL}")
    init_db()
    db = SessionLocal()
    try:
        repo = UserRepository(db)
        for p in PLAYERS:
            username = p["username"]
            password = p["password"]
            user = repo.get_by_username(username)
            if user:
                repo.update_password(user=user, hashed_password=hash_password(password))
                print(f"[update] {user.username}  (id={user.id})  mot de passe : {password}")
                continue
            user = repo.create(
                username=username,
                hashed_password=hash_password(password),
                is_admin=False,
                must_change_password=False,
            )
            print(f"[create] {user.username}  (id={user.id})  mot de passe : {password}")
    finally:
        db.close()
    print("Seed terminé.")


if __name__ == "__main__":
    seed()
