from datetime import datetime
from pydantic import BaseModel


class UserCreate(BaseModel):
    username: str


class UserResponse(BaseModel):
    id: int
    username: str
    is_admin: bool
    must_change_password: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserWithTempPassword(BaseModel):
    user: UserResponse
    temp_password: str
