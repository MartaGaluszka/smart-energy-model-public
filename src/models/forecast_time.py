"""
Jednolity format znaczników czasu w archiwum prognoz.

Kanoniczny zapis: ISO-8601 z literą T, bez strefy, dokładność do sekundy
  np. 2026-07-20T05:00:44

Odczyt: format='mixed' (akceptuje też starsze wiersze ze spacją).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

# Kanoniczny format zapisu (zgodny z datetime.isoformat(timespec='seconds'))
FORECAST_TS_FMT = '%Y-%m-%dT%H:%M:%S'


def format_forecast_ts(value: Any) -> str:
    """Zamień datetime/Timestamp/str na kanoniczny string ISO z T."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        raise ValueError('pusty timestamp')
    ts = pd.Timestamp(value)
    if pd.isna(ts):
        raise ValueError(f'nieparsowalny timestamp: {value!r}')
    return ts.strftime(FORECAST_TS_FMT)


def parse_forecast_ts(values: Any) -> pd.Timestamp | pd.Series:
    """
    Parsuj jeden timestamp lub Series/listę.
    Akceptuje zarówno 'YYYY-MM-DDTHH:MM:SS', jak i 'YYYY-MM-DD HH:MM:SS'.
    """
    if isinstance(values, (str, datetime, pd.Timestamp)):
        return pd.Timestamp(pd.to_datetime(values, format='mixed'))
    return pd.to_datetime(values, format='mixed')


def normalize_run_at_column(df: pd.DataFrame, column: str = 'run_at') -> pd.DataFrame:
    """Przepisz kolumnę na kanoniczny ISO (T). Zwraca kopię gdy trzeba."""
    if column not in df.columns or df.empty:
        return df
    out = df.copy()
    parsed = parse_forecast_ts(out[column])
    out[column] = parsed.map(format_forecast_ts)
    return out
