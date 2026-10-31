"""Centralna pauza FoxESS Cloud API (40402) — bez wołania chmury do ``paused_until``."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

_DEFAULT_PAUSE_FILE = Path('data/.foxess_api_pause_until')


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def pause_file_path() -> Path:
    raw = os.getenv('FOXESS_PAUSE_FILE', '').strip()
    if raw:
        p = Path(raw)
        return p if p.is_absolute() else _project_root() / p
    return _project_root() / _DEFAULT_PAUSE_FILE


def _parse_until(value: str) -> datetime | None:
    text = (value or '').strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace('Z', '+00:00')[:26])
    except ValueError:
        return None


def paused_until() -> datetime | None:
    """Koniec pauzy: env ``FOXESS_SYNC_PAUSED_UNTIL`` (ISO) albo plik ``data/.foxess_api_pause_until``."""
    env_until = _parse_until(os.getenv('FOXESS_SYNC_PAUSED_UNTIL', ''))
    if env_until is not None:
        return env_until
    path = pause_file_path()
    if not path.is_file():
        return None
    try:
        return _parse_until(path.read_text(encoding='utf-8'))
    except OSError:
        return None


def is_api_paused(*, now: datetime | None = None) -> bool:
    if os.getenv('FOXESS_SYNC_DISABLED', '').strip().lower() in ('1', 'true', 'yes', 'on'):
        return True
    until = paused_until()
    if until is None:
        return False
    current = now or datetime.now()
    # Porównanie naiwne — spójne z TZ kontenera / hosta (Europe/Warsaw w compose).
    if until.tzinfo is not None and current.tzinfo is None:
        until = until.replace(tzinfo=None)
    return current < until


def pause_message() -> str:
    if os.getenv('FOXESS_SYNC_DISABLED', '').strip().lower() in ('1', 'true', 'yes', 'on'):
        return 'Sync Fox wyłączony (FOXESS_SYNC_DISABLED) — odczekaj reset limitu 40402.'
    until = paused_until()
    if until is None:
        return 'FoxESS API — brak aktywnej pauzy.'
    until_s = until.strftime('%Y-%m-%d %H:%M')
    return (
        f'Pauza FoxESS API do {until_s} (24h blokada po 40402) — używaj foxess_data w SQLite.'
    )


def set_pause_hours(hours: float = 24.0, *, now: datetime | None = None) -> datetime:
    """Zapisuje koniec pauzy w pliku (domyślnie +24 h od teraz)."""
    current = now or datetime.now()
    until = current + timedelta(hours=hours)
    path = pause_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(until.isoformat(timespec='seconds'), encoding='utf-8')
    return until


def clear_pause() -> None:
    path = pause_file_path()
    if path.is_file():
        path.unlink()


def assert_api_allowed() -> None:
    if is_api_paused():
        raise RuntimeError(pause_message())
