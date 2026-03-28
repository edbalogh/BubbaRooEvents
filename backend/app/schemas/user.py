from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr


class UserRegister(BaseModel):
    email: str
    password: str
    display_name: str
    home_city: str | None = None
    home_latitude: float | None = None
    home_longitude: float | None = None
    timezone: str = "America/New_York"


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: UUID
    email: str
    display_name: str
    home_city: str | None
    home_latitude: float | None
    home_longitude: float | None
    timezone: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
