from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    active: Optional[bool] = True

class UserCreate(UserBase):
    password: str

class UserOut(UserBase):
    is_verified: bool
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class TokenData(BaseModel):
    sub: str
    rtp: int

    class Config:
        from_attributes = True
