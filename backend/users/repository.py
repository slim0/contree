from sqlalchemy.orm import Session
from backend.db.models import User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, user_id: int) -> User | None:
        return self._db.get(User, user_id)

    def get_by_username(self, username: str) -> User | None:
        return self._db.query(User).filter(User.username == username).first()

    def list_all(self) -> list[User]:
        return self._db.query(User).order_by(User.created_at).all()

    def count(self) -> int:
        return self._db.query(User).count()

    def create(
        self,
        username: str,
        hashed_password: str,
        is_admin: bool = False,
        must_change_password: bool = True,
    ) -> User:
        user = User(
            username=username,
            hashed_password=hashed_password,
            is_admin=is_admin,
            must_change_password=must_change_password,
        )
        self._db.add(user)
        self._db.commit()
        self._db.refresh(user)
        return user

    def update_password(self, user: User, hashed_password: str) -> User:
        user.hashed_password = hashed_password
        user.must_change_password = False
        self._db.commit()
        self._db.refresh(user)
        return user

    def delete(self, user: User) -> None:
        self._db.delete(user)
        self._db.commit()
