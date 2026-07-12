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

    def verify_credentials(self, username: str, password: str) -> User | None:
        """Vérifie les identifiants via PocketBase (qui gère le hachage)."""
        record = self._pb.verify_credentials(username, password)
        return User.from_record(record) if record else None

    def delete(self, user: User) -> None:
        self._pb.delete(user.id)
