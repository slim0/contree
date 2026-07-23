from dataclasses import dataclass
from datetime import datetime


@dataclass
class User:
    id: str
    username: str
    is_admin: bool
    must_change_password: bool
    created_at: datetime
    games_played: int = 0
    games_won: int = 0
    games_lost: int = 0
    capots_won: int = 0
    generales_won: int = 0
    contracts_taken: int = 0
    contracts_made: int = 0

    @property
    def win_rate(self) -> float | None:
        """None (pas 0.0) tant qu'aucune partie n'a été jouée — évite un '0%' trompeur."""
        return self.games_won / self.games_played if self.games_played else None

    @property
    def contract_success_rate(self) -> float | None:
        return (
            self.contracts_made / self.contracts_taken
            if self.contracts_taken
            else None
        )

    @classmethod
    def from_record(cls, record: dict) -> "User":
        return cls(
            id=record["id"],
            username=record["username"],
            is_admin=record["is_admin"],
            must_change_password=record["must_change_password"],
            created_at=datetime.fromisoformat(record["created"]),
            games_played=record["games_played"],
            games_won=record["games_won"],
            games_lost=record["games_lost"],
            capots_won=record["capots_won"],
            generales_won=record["generales_won"],
            contracts_taken=record["contracts_taken"],
            contracts_made=record["contracts_made"],
        )
