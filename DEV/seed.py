#!/usr/bin/env python3
"""Seed de dev : crée 4 joueurs test dans PocketBase avec must_change_password=False."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.pocketbase.client import PB_URL, get_pb_client
from backend.users.repository import UserRepository

PLAYERS = [
    {"username": "admin", "password": "tuzjIk-hyrcom-mopfa1"},
    {"username": "alice", "password": "alice1234"},
    {"username": "bob", "password": "bob12345!"},
    {"username": "charlie", "password": "charlie1"},
    {"username": "diana", "password": "diana123"},
]


def seed() -> None:
    print(f"PocketBase : {PB_URL}")
    repo = UserRepository(get_pb_client())
    for p in PLAYERS:
        username = p["username"]
        password = p["password"]
        user = repo.get_by_username(username)
        if user:
            repo.update_password(user=user, new_password=password)
            print(
                f"[update] {user.username}  (id={user.id})  mot de passe : {password}"
            )
            continue
        user = repo.create(
            username=username,
            password=password,
            is_admin=False,
            must_change_password=False,
        )
        print(f"[create] {user.username}  (id={user.id})  mot de passe : {password}")
    print("Seed terminé.")


if __name__ == "__main__":
    seed()
