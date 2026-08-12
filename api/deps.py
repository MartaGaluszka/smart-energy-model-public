"""Zależności FastAPI: sesja DB, bieżący użytkownik, ustawienia (T0.7, T0.8)."""

from __future__ import annotations

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from api.config import Settings, get_settings
from api.db import get_db_session
from api.errors import ApiError
from api.models import AppUser
from api.security import decode_token

_bearer_scheme = HTTPBearer(auto_error=False)


def get_db() -> Session:
    yield from get_db_session()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> AppUser:
    if credentials is None:
        raise ApiError(401, 'NOT_AUTHENTICATED', 'Brak tokena Authorization: Bearer <JWT>')

    try:
        payload = decode_token(credentials.credentials)
    except Exception as exc:  # noqa: BLE001 — jwt.InvalidTokenError i pochodne
        raise ApiError(401, 'INVALID_TOKEN', f'Nieprawidłowy lub wygasły token: {exc}') from exc

    if payload.get('type') != 'access':
        raise ApiError(401, 'INVALID_TOKEN_TYPE', 'Wymagany access token (nie refresh)')

    user_id = payload.get('sub')
    user = db.get(AppUser, int(user_id)) if user_id is not None else None
    if user is None or not user.is_active:
        raise ApiError(401, 'USER_NOT_FOUND', 'Użytkownik nie istnieje lub jest nieaktywny')

    return user


def get_app_settings() -> Settings:
    return get_settings()
