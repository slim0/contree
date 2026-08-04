from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=8)


class UserInfo(BaseModel):
    username: str
    is_admin: bool
    must_change_password: bool


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str
