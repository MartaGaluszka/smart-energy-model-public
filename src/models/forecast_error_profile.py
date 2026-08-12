"""
Profil błędu operacyjnego prognozy PV — budowany z własnych plików walidacji.

Źródło: data/processed/forecasts/forecast_validation_hourly.csv
(wieczorne porównanie prognoza vs pvPower z FoxESS).

Wynik: współczynniki korekty per godzina (median actual/predicted).
Bez zewnętrznych bibliotek ani kopiowania kodu z innych projektów.
"""

from __future__ import annotations

import os
from datetime import datetime

import numpy as np
import pandas as pd

from src.models.forecast_validation import HOURLY_VALIDATION_FILE

DEFAULT_PROFILE_PATH = 'data/processed/forecast_error_profile.csv'
DEFAULT_MIN_SAMPLES = 3


def _profile_path() -> str:
    return os.getenv('FORECAST_ERROR_PROFILE_PATH', DEFAULT_PROFILE_PATH)


def build_error_profile(
    hourly_validation_path: str | None = None,
    output_path: str | None = None,
    min_samples: int | None = None,
) -> pd.DataFrame:
    """
    Zbuduj profil błędu godzinowego z historycznej walidacji operacyjnej.

    Dla każdej godziny 5–21: median(actual/predicted) gdy obie > 0.
    """
    hourly_validation_path = hourly_validation_path or HOURLY_VALIDATION_FILE
    output_path = output_path or _profile_path()
    min_samples = min_samples or int(os.getenv('FORECAST_ERROR_MIN_SAMPLES', str(DEFAULT_MIN_SAMPLES)))

    if not os.path.exists(hourly_validation_path):
        return _empty_profile(output_path)

    raw = pd.read_csv(hourly_validation_path)
    required = {'predicted_hour', 'predicted_kwh', 'actual_pv_ml_kwh'}
    if not required.issubset(raw.columns):
        return _empty_profile(output_path)

    df = raw.copy()
    df['predicted_hour'] = df['predicted_hour'].astype(int)
    df['predicted_kwh'] = pd.to_numeric(df['predicted_kwh'], errors='coerce')
    df['actual_pv_ml_kwh'] = pd.to_numeric(df['actual_pv_ml_kwh'], errors='coerce')
    df = df[
        df['predicted_kwh'].notna()
        & df['actual_pv_ml_kwh'].notna()
        & (df['predicted_kwh'] > 0.05)
        & (df['actual_pv_ml_kwh'] >= 0)
    ].copy()

    if df.empty:
        return _empty_profile(output_path)

    df['ratio'] = df['actual_pv_ml_kwh'] / df['predicted_kwh']

    rows = []
    for hour in range(5, 22):
        sub = df[df['predicted_hour'] == hour]
        n = len(sub)
        if n >= min_samples:
            ratio = float(np.median(sub['ratio']))
            ratio = float(np.clip(ratio, 0.2, 2.0))
        else:
            ratio = 1.0
        rows.append({
            'hour': hour,
            'n_samples': n,
            'correction_factor': round(ratio, 4),
            'median_actual_kwh': round(float(sub['actual_pv_ml_kwh'].median()), 3) if n else None,
            'median_predicted_kwh': round(float(sub['predicted_kwh'].median()), 3) if n else None,
        })

    profile = pd.DataFrame(rows)
    profile['built_at'] = datetime.now().isoformat(timespec='seconds')
    profile['source_file'] = hourly_validation_path
    profile['n_validation_rows'] = len(df)

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    profile.to_csv(output_path, index=False)
    return profile


def _empty_profile(output_path: str) -> pd.DataFrame:
    profile = pd.DataFrame([
        {'hour': h, 'n_samples': 0, 'correction_factor': 1.0}
        for h in range(5, 22)
    ])
    profile['built_at'] = datetime.now().isoformat(timespec='seconds')
    profile['source_file'] = ''
    profile['n_validation_rows'] = 0
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    profile.to_csv(output_path, index=False)
    return profile


def load_error_profile(path: str | None = None) -> pd.DataFrame | None:
    path = path or _profile_path()
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    if df.empty or 'hour' not in df.columns:
        return None
    return df


def hourly_correction_factor(hour: int, profile: pd.DataFrame | None = None) -> float:
    """Współczynnik korekty dla godziny (1.0 = brak korekty z profilu)."""
    if profile is None:
        profile = load_error_profile()
    if profile is None or profile.empty:
        return 1.0
    row = profile[profile['hour'] == int(hour)]
    if row.empty:
        return 1.0
    val = row.iloc[0].get('correction_factor', 1.0)
    try:
        return float(np.clip(float(val), 0.2, 2.0))
    except (TypeError, ValueError):
        return 1.0


def profile_summary(profile: pd.DataFrame | None = None) -> str:
    if profile is None:
        profile = load_error_profile()
    if profile is None or profile.empty:
        return 'Profil błędu: brak (domyślnie 1.0 dla wszystkich godzin)'
    n = int(profile.get('n_validation_rows', pd.Series([0])).iloc[0] or 0)
    built = profile.get('built_at', pd.Series(['?'])).iloc[0]
    weak = profile[
        (profile['n_samples'] >= DEFAULT_MIN_SAMPLES)
        & (profile['correction_factor'] < 0.85)
    ]
    hours = ', '.join(f"{int(r['hour']):02d}h×{r['correction_factor']:.2f}" for _, r in weak.head(5).iterrows())
    tail = f' | słabsze godziny: {hours}' if hours else ''
    return f'Profil błędu: {n} wierszy walidacji, built {built}{tail}'
