"""Warstwa DB — SQLAlchemy engine/session dla NOWYCH tabel appki (T0.8).

Uwaga (znany stan przejściowy, patrz docs/UPDATE_2026-07-26_fastapi-oauth-spike.md):
istniejące dane domenowe (FoxESS/pogoda/Tauron) są nadal czytane przez
`src/*` bezpośrednio z pliku SQLite wskazanego przez `DATABASE_PATH`
(funkcje tam używają `sqlite3.connect()` — nie zostały przepisane w tej fazie).
Ta warstwa (SQLAlchemy + `DATABASE_URL`) obsługuje wyłącznie NOWE tabele
wprowadzone dla appki mobilnej: `app_users`, `user_secrets`,
`user_tariff_overrides`, `household_events`, `roi_assumptions`,
`battery_strategy_settings`, `notifications`, `push_subscriptions`,
`advice_events`.

Lokalnie oba światy domyślnie wskazują na ten sam plik SQLite (patrz
`api/config.py::_default_database_url`), więc `sqlite3` (src/*) i SQLAlchemy
(api/*) czytają/piszą do tego samego pliku bez dodatkowej konfiguracji.
W Dockerze `DATABASE_URL` wskazuje na Postgres 16 (docker-compose.yml),
gdzie schemat tabel domenowych + appki jest już utworzony przez
`db/init/*.sql` — patrz T0.4 (`scripts/migrate_sqlite_to_postgres.py`) po
jednorazowy import danych historycznych.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from api.config import get_settings

settings = get_settings()

_connect_args = {'check_same_thread': False} if settings.DATABASE_URL.startswith('sqlite') else {}

engine = create_engine(settings.DATABASE_URL, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Tworzy brakujące tabele appki (checkfirst=True — bezpieczne wobec Postgresa
    zainicjalizowanego już przez db/init/002_app_tables.sql)."""
    from api import models  # noqa: F401 — rejestracja modeli w Base.metadata

    Base.metadata.create_all(bind=engine, checkfirst=True)


def get_db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
