"""JWT issuance/verification, password hashing, i szyfrowanie sekretów (Fernet).

Realizuje T0.14 (szyfrowanie at-rest) i TA.1 (JWT access+refresh) — patrz
docs/UPDATE_2026-07-26_fastapi-oauth-spike.md dla decyzji "własny IdP + vault".
"""

from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Literal

import jwt
from cryptography.fernet import Fernet
from passlib.context import CryptContext

from api.config import get_settings

_pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

TokenType = Literal['access', 'refresh']


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _pwd_context.verify(password, password_hash)
    except ValueError:
        return False


def create_token(subject: str, token_type: TokenType) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    if token_type == 'access':
        expires_delta = timedelta(minutes=settings.JWT_ACCESS_TOKEN_MINUTES)
    else:
        expires_delta = timedelta(days=settings.JWT_REFRESH_TOKEN_DAYS)

    payload = {
        'sub': subject,
        'type': token_type,
        'iat': now,
        'exp': now + expires_delta,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])


def _derive_fernet_key(raw: str) -> bytes:
    """Akceptuje zarówno gotowy klucz Fernet (32B base64), jak i dowolny sekret
    (np. wklejony JWT_SECRET) — w tym drugim przypadku deterministycznie derywuje
    klucz Fernet z SHA-256, żeby nie wymagać osobnego formatu w .env."""
    raw_bytes = raw.encode('utf-8')
    try:
        Fernet(raw_bytes)
        return raw_bytes
    except Exception:  # noqa: BLE001 — fallback do derywacji
        digest = hashlib.sha256(raw_bytes).digest()
        return base64.urlsafe_b64encode(digest)


_ephemeral_key_cache: bytes | None = None


def _get_fernet() -> Fernet:
    global _ephemeral_key_cache
    settings = get_settings()
    key_source = settings.SECRETS_ENCRYPTION_KEY
    if not key_source:
        # Brak klucza w .env: generujemy efemeryczny klucz procesu (dev/test only).
        # UWAGA: sekrety zaszyfrowane tym kluczem NIE przetrwają restartu procesu —
        # do produkcji ustaw SECRETS_ENCRYPTION_KEY w .env (patrz .env.example).
        if _ephemeral_key_cache is None:
            _ephemeral_key_cache = Fernet.generate_key()
        return Fernet(_ephemeral_key_cache)
    return Fernet(_derive_fernet_key(key_source))


def encrypt_secret(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode('utf-8')).decode('utf-8')


def decrypt_secret(ciphertext: str) -> str:
    return _get_fernet().decrypt(ciphertext.encode('utf-8')).decode('utf-8')
