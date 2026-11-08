from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.enums import AdminRole


class LoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class AdminOut(BaseModel):
    """What the admin area may know about the signed-in person. Never the password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: AdminRole
    created_at: datetime
