"""Konfiguracja FastAPI (pydantic-settings) — T0.10a.

Wszystkie ustawienia mają rozsądne wartości domyślne pod lokalny dev
(bez Dockera, bez Postgresa) — patrz .env.example, sekcja "FastAPI backend".
"""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _default_database_url() -> str:
    """Domyślnie: ten sam plik SQLite co reszta projektu (DATABASE_PATH).

    Dzięki temu nowe tabele appki (app_users, notifications, ...) i istniejące
    tabele domenowe (foxess_data, weather_data, ...) żyją w jednym pliku lokalnie,
    tak jak w docelowym Postgresie w Dockerze (patrz db/init/*.sql).
    """
    sqlite_path = os.getenv('DATABASE_PATH', 'data/energy_model.db')
    if not os.path.isabs(sqlite_path):
        sqlite_path = os.path.join(_PROJECT_ROOT, sqlite_path)
    return f'sqlite:///{sqlite_path}'


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    APP_NAME: str = 'Smart Energy API'
    APP_VERSION: str = '0.1.0'

    DATABASE_URL: str = _default_database_url()
    DATABASE_PATH: str = os.getenv('DATABASE_PATH', 'data/energy_model.db')

    JWT_SECRET: str = 'dev-only-change-me-not-for-production'
    JWT_ALGORITHM: str = 'HS256'
    JWT_ACCESS_TOKEN_MINUTES: int = 30
    JWT_REFRESH_TOKEN_DAYS: int = 7

    # Fernet key do szyfrowania sekretów (FoxESS API key) w user_secrets.
    # Brak w env -> wygenerowany efemerycznie przy starcie procesu (patrz get_settings()).
    SECRETS_ENCRYPTION_KEY: str = ''

    CORS_ORIGINS: str = 'http://localhost:8100,http://localhost,capacitor://localhost,ionic://localhost'

    PV_HOURLY_MODEL_PATH: str = os.getenv('PV_HOURLY_MODEL_PATH', 'models/pv_hourly_model.joblib')

    @property
    def cors_origins_list(self) -> list[str]:
        origins = [o.strip() for o in self.CORS_ORIGINS.split(',') if o.strip()]
        return origins or ['*']

    @property
    def model_path_resolved(self) -> str:
        path = self.PV_HOURLY_MODEL_PATH
        if not os.path.isabs(path):
            path = os.path.join(_PROJECT_ROOT, path)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
