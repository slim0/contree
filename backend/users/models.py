from dataclasses import dataclass
from datetime import datetime


@dataclass
class User:
    id: str
    username: str
    is_admin: bool
    must_change_password: bool
    created_at: datetime

    @classmethod
    def from_record(cls, record: dict) -> "User":
        return cls(
            id=record["id"],
            username=record["username"],
            is_admin=record["is_admin"],
            must_change_password=record["must_change_password"],
            created_at=datetime.fromisoformat(record["created"]),
        )
