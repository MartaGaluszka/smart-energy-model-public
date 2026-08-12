"""Auth (TA.1, TA.2, T0.12-T0.16): JWT login/refresh/logout + FoxESS API-key vault."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.deps import get_current_user, get_db
from api.errors import ApiError
from api.models import AppUser, UserSecret
from api.schemas.auth import (
    AccessTokenResponse,
    FoxLinkRequest,
    FoxLinkStatusResponse,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from api.security import create_token, decode_token, encrypt_secret, hash_password, verify_password

router = APIRouter(prefix='/api/v1/auth', tags=['auth'])


@router.post(
    '/register',
    response_model=TokenResponse,
    status_code=201,
    summary='Rejestracja użytkownika appki (dodatek MVP — nie w oryginalnym katalogu §12.3, '
    'wymagany żeby /auth/login było testowalne bez ręcznego seeda w bazie)',
)
def register(body: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    existing = db.query(AppUser).filter(AppUser.email == body.email).first()
    if existing is not None:
        raise ApiError(409, 'USER_EXISTS', 'Użytkownik z tym adresem e-mail już istnieje')

    user = AppUser(email=body.email, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)

    return TokenResponse(
        access_token=create_token(str(user.id), 'access'),
        refresh_token=create_token(str(user.id), 'refresh'),
    )


@router.post('/login', response_model=TokenResponse, summary='Login → access + refresh JWT')
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(AppUser).filter(AppUser.email == body.email).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise ApiError(401, 'INVALID_CREDENTIALS', 'Nieprawidłowy e-mail lub hasło')
    if not user.is_active:
        raise ApiError(403, 'USER_DISABLED', 'Konto nieaktywne')

    return TokenResponse(
        access_token=create_token(str(user.id), 'access'),
        refresh_token=create_token(str(user.id), 'refresh'),
    )


@router.post('/refresh', response_model=AccessTokenResponse, summary='Nowy access token z refresh tokena')
def refresh(body: RefreshRequest, db: Session = Depends(get_db)) -> AccessTokenResponse:
    try:
        payload = decode_token(body.refresh_token)
    except Exception as exc:  # noqa: BLE001
        raise ApiError(401, 'INVALID_TOKEN', f'Nieprawidłowy lub wygasły refresh token: {exc}') from exc

    if payload.get('type') != 'refresh':
        raise ApiError(401, 'INVALID_TOKEN_TYPE', 'Wymagany refresh token')

    user = db.get(AppUser, int(payload['sub']))
    if user is None or not user.is_active:
        raise ApiError(401, 'USER_NOT_FOUND', 'Użytkownik nie istnieje lub jest nieaktywny')

    return AccessTokenResponse(access_token=create_token(str(user.id), 'access'))


@router.post(
    '/logout',
    response_model=MessageResponse,
    summary='Unieważnienie sesji (MVP: stateless — brak persystentnej blacklisty refresh tokenów, patrz TODO w kodzie)',
)
def logout(body: LogoutRequest, current_user: AppUser = Depends(get_current_user)) -> MessageResponse:
    # TODO (Faza 1+): tabela revoked_tokens / krótszy TTL refresh + rotacja, jeśli
    # potrzebna twarda rewokacja. MVP: klient kasuje tokeny lokalnie (Secure Storage).
    return MessageResponse(message='Wylogowano (tokeny należy usunąć po stronie klienta).')


@router.post('/fox/link', response_model=FoxLinkStatusResponse, summary='Powiązanie zaszyfrowanego API key FoxESS')
def link_fox(
    body: FoxLinkRequest,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FoxLinkStatusResponse:
    secret = db.query(UserSecret).filter(
        UserSecret.user_id == current_user.id, UserSecret.provider == 'foxess'
    ).first()

    encrypted_key = encrypt_secret(body.api_key)
    encrypted_sn = encrypt_secret(body.device_sn) if body.device_sn else None

    if secret is None:
        secret = UserSecret(
            user_id=current_user.id,
            provider='foxess',
            encrypted_value=encrypted_key,
            device_sn_encrypted=encrypted_sn,
        )
        db.add(secret)
    else:
        secret.encrypted_value = encrypted_key
        secret.device_sn_encrypted = encrypted_sn
        secret.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(secret)

    return FoxLinkStatusResponse(linked=True, linked_at=secret.updated_at.isoformat())


@router.delete('/fox/link', response_model=FoxLinkStatusResponse, summary='Odłączenie konta FoxESS')
def unlink_fox(current_user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)) -> FoxLinkStatusResponse:
    secret = db.query(UserSecret).filter(
        UserSecret.user_id == current_user.id, UserSecret.provider == 'foxess'
    ).first()
    if secret is not None:
        db.delete(secret)
        db.commit()

    return FoxLinkStatusResponse(linked=False, linked_at=None)
