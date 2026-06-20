from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class UserInfo(BaseModel):
    username: str
    is_admin: bool
    must_change_password: bool


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str
