from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.auth.preferences import ExpertiseLevel


class EmailCodeRequest(BaseModel):
    email: EmailStr


class EmailCodeVerifyRequest(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^\d{6}$")


class EmailCodeSentResponse(BaseModel):
    message: str
    expires_in: int
    retry_after: int


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    expertise_level: ExpertiseLevel
    email_verified_at: datetime
    created_at: datetime
    last_login_at: datetime


class UserPreferencesUpdateRequest(BaseModel):
    expertise_level: ExpertiseLevel


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
