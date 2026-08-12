from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, examples=['change-me-123'])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = 'bearer'


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class MessageResponse(BaseModel):
    message: str


class FoxLinkRequest(BaseModel):
    api_key: str = Field(min_length=8, description='Klucz FoxESS Cloud Open API (portal V1 → API Management)')
    device_sn: str | None = Field(default=None, description='Numer seryjny falownika (opcjonalnie)')


class FoxLinkStatusResponse(BaseModel):
    linked: bool
    provider: str = 'foxess'
    device_sn_display: str = 'REDACTED'
    linked_at: str | None = None
