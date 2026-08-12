"""
Okno treningowe ML — expanding do 24 miesięcy, potem rolling 24 miesięcy.

Fazy:
  1. Expanding — od ML_TRAIN_MIN_START (2025-06-01) do train_end (rosnące okno)
  2. Rolling 24m — gdy zebrano ≥ ML_TRAIN_ROLLING_AFTER_MONTHS, ostatnie 24 miesiące

Używane przez train_hourly_model_tuning.py i analyze_cloudy_streaks.py (raport DEV/OOS).
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date, timedelta

import pandas as pd

DEFAULT_MIN_START = '2025-06-01'
DEFAULT_ROLLING_AFTER_MONTHS = 24
DEFAULT_ROLLING_WINDOW_MONTHS = 24


def get_last_foxess_day(db_path: str | None = None) -> date | None:
    """Ostatni dzień z danymi PV w foxess_data."""
    db_path = db_path or os.getenv('DATABASE_PATH', 'data/energy_model.db')
    if not os.path.exists(db_path):
        return None
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        '''
        SELECT MAX(date(timestamp))
        FROM foxess_data
        WHERE pv_energy_kwh IS NOT NULL
        '''
    ).fetchone()
    conn.close()
    if not row or row[0] is None:
        return None
    return date.fromisoformat(str(row[0]))


def _resolve_train_end(
    env_end: str,
    db_path: str,
) -> date:
    if env_end.lower() not in ('', 'auto'):
        return date.fromisoformat(env_end)

    yesterday = date.today() - timedelta(days=1)
    last_db = get_last_foxess_day(db_path)
    if last_db is None:
        return yesterday
    return min(yesterday, last_db)


def train_window_mode(
    train_start: str,
    train_end: str,
    *,
    min_start: str | None = None,
) -> str:
    """'expanding' | 'rolling' | 'fixed'."""
    min_start = min_start or os.getenv('ML_TRAIN_MIN_START', DEFAULT_MIN_START)
    if train_start != min_start:
        return 'fixed'
    rolling_after = int(os.getenv('ML_TRAIN_ROLLING_AFTER_MONTHS', str(DEFAULT_ROLLING_AFTER_MONTHS)))
    floor = date.fromisoformat(min_start)
    end = date.fromisoformat(train_end)
    expand_until = pd.Timestamp(floor) + pd.DateOffset(months=rolling_after)
    if pd.Timestamp(end) < expand_until:
        return 'expanding'
    return 'rolling'


def resolve_train_window(
    db_path: str | None = None,
    *,
    rolling_after_months: int | None = None,
    rolling_window_months: int | None = None,
    min_start: str | None = None,
    train_end: str | None = None,
    train_start: str | None = None,
) -> tuple[str, str]:
    """
    Zwróć (train_start, train_end) jako YYYY-MM-DD.

    Domyślnie (ML_TRAIN_START=auto):
      - train_end=auto → wczoraj lub ostatni dzień FoxESS
      - < 24 mies. od min_start → expanding (start = ML_TRAIN_MIN_START)
      - ≥ 24 mies. → rolling ostatnich 24 miesięcy (min. min_start)
    """
    db_path = db_path or os.getenv('DATABASE_PATH', 'data/energy_model.db')
    rolling_after = rolling_after_months or int(
        os.getenv('ML_TRAIN_ROLLING_AFTER_MONTHS', str(DEFAULT_ROLLING_AFTER_MONTHS))
    )
    rolling_window = rolling_window_months or int(
        os.getenv('ML_TRAIN_MONTHS', str(DEFAULT_ROLLING_WINDOW_MONTHS))
    )
    min_start = min_start or os.getenv('ML_TRAIN_MIN_START', DEFAULT_MIN_START)

    env_end = (train_end if train_end is not None else os.getenv('ML_TRAIN_END', 'auto')).strip()
    env_start = (train_start if train_start is not None else os.getenv('ML_TRAIN_START', 'auto')).strip()

    end = _resolve_train_end(env_end, db_path)
    floor = date.fromisoformat(min_start)

    if env_start.lower() in ('', 'auto'):
        expand_until = pd.Timestamp(floor) + pd.DateOffset(months=rolling_after)
        if pd.Timestamp(end) < expand_until:
            start = floor
        else:
            rolling_start = (
                pd.Timestamp(end) - pd.DateOffset(months=rolling_window) + pd.Timedelta(days=1)
            ).date()
            start = max(floor, rolling_start)
    else:
        start = date.fromisoformat(env_start)

    if start > end:
        raise ValueError(
            f'Niepoprawne okno treningowe: start={start} > end={end}. '
            'Sprawdź ML_TRAIN_START / ML_TRAIN_END lub uzupełnij dane FoxESS.'
        )

    return start.isoformat(), end.isoformat()


def format_train_window(train_start: str, train_end: str) -> str:
    """Opis okna do logów."""
    mode = train_window_mode(train_start, train_end)
    labels = {
        'expanding': 'expanding (od min_start, rośnie)',
        'rolling': f'rolling ({os.getenv("ML_TRAIN_MONTHS", "24")} mies.)',
        'fixed': 'stałe (jawnie ustawione daty)',
    }
    return f'{train_start} → {train_end} [{labels.get(mode, mode)}]'


def resolve_ml_dates(
    start_date: str | None = None,
    end_date: str | None = None,
    db_path: str | None = None,
) -> tuple[str, str]:
    """Zamień ML_TRAIN_* (w tym 'auto') na konkretne YYYY-MM-DD."""
    start_raw = (start_date or os.getenv('ML_TRAIN_START', 'auto')).strip()
    end_raw = (end_date or os.getenv('ML_TRAIN_END', 'auto')).strip()

    if start_raw.lower() not in ('', 'auto') and end_raw.lower() not in ('', 'auto'):
        return start_raw, end_raw

    return resolve_train_window(
        db_path,
        train_start=None if start_raw.lower() in ('', 'auto') else start_raw,
        train_end=None if end_raw.lower() in ('', 'auto') else end_raw,
    )


def oos_window(train_end: str, *, through: str | None = None) -> tuple[str, str] | None:
    """Okno OOS: dzień po train_end → through (domyślnie dziś). None gdy brak dni."""
    through = through or date.today().isoformat()
    start = (pd.Timestamp(train_end) + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
    if start > through:
        return None
    return start, through
