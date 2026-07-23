from backend.pocketbase.client import PocketBaseClient
from backend.users.models import User


class UserRepository:
    """Seul point d'accès aux comptes utilisateurs — proxie vers PocketBase."""

    def __init__(self, pb: PocketBaseClient) -> None:
        self._pb = pb

    def get_by_id(self, user_id: str) -> User | None:
        record = self._pb.get_by_id(user_id)
        return User.from_record(record) if record else None

    def get_by_username(self, username: str) -> User | None:
        record = self._pb.get_by_username(username)
        return User.from_record(record) if record else None

    def list_all(self) -> list[User]:
        return [User.from_record(r) for r in self._pb.list_all()]

    def count(self) -> int:
        return self._pb.count()

    def create(
        self,
        username: str,
        password: str,
        is_admin: bool = False,
        must_change_password: bool = True,
    ) -> User:
        record = self._pb.create(username, password, is_admin, must_change_password)
        return User.from_record(record)

    def update_password(self, user: User, new_password: str) -> User:
        record = self._pb.set_password(user.id, new_password)
        return User.from_record(record)

    def increment_stats(self, user_id: str, increments: dict[str, int]) -> User:
        """increments = {"games_played": 1, "games_won": 1, ...}. Effet de bord non
        critique : les appelants doivent avaler les exceptions (voir backend/api/stats.py)
        plutôt que de laisser un échec de stats interrompre une partie en cours.

        Limite acceptée : rien n'empêche aujourd'hui un même joueur de rejoindre deux
        parties actives simultanément (memory_store.join_room ne vérifie l'unicité que
        par room_id) — dans ce cas non-nominal, deux incréments concurrents sur le même
        utilisateur pourraient se chevaucher.
        """
        record = self._pb.increment_stats(user_id, increments)
        return User.from_record(record)

    def verify_credentials(self, username: str, password: str) -> User | None:
        """Vérifie les identifiants via PocketBase (qui gère le hachage)."""
        record = self._pb.verify_credentials(username, password)
        return User.from_record(record) if record else None

    def delete(self, user: User) -> None:
        self._pb.delete(user.id)
