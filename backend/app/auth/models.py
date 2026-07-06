"""Request/response schemas for auth."""

from pydantic import BaseModel, Field


class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    invite_code: str = ""
    """Only checked on /register, and only when the server has INVITE_CODE configured."""


class UserPublic(BaseModel):
    id: str
    username: str
    created_at: str
