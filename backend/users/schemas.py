from datetime import datetime

from pydantic import BaseModel


class UserCreate(BaseModel):
    username: str


class UserResponse(BaseModel):
    id: str
    username: str
    is_admin: bool
    must_change_password: bool
    created_at: datetime
    games_played: int
    games_won: int
    games_lost: int
    win_rate: float | None
    capots_won: int
    generales_won: int
    contracts_taken: int
    contracts_made: int
    contract_success_rate: float | None

    model_config = {"from_attributes": True}


class UserWithTempPassword(BaseModel):
    user: UserResponse
    temp_password: str


class UserStatsResponse(BaseModel):
    username: str
    games_played: int
    games_won: int
    games_lost: int
    win_rate: float | None
    capots_won: int
    generales_won: int
    contracts_taken: int
    contracts_made: int
    contract_success_rate: float | None

    model_config = {"from_attributes": True}
