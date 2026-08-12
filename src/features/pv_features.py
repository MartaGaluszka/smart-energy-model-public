"""
Macierz cech do regresji PV (target: pv_kwh_daytime).

UWAGA: pv_kwh_daytime to suma PV w godzinach wschód–zachód (dynamicznie).
       Filtr baterii (battery_power >= -0.1) stosowany przy odczycie z foxess_data.
       Dla precyzyjnych harmonogramów godzinowych użyj pv_features_hourly_extended.py.

Walidacja czasowa — bez losowego shuffle.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from src.data.household_context import (
    ML_BATTERY_START,
    is_pv_inverter_misconfigured,
    is_pv_weather_valid,
)
from src.data.weather_api import (
    flag_likely_fog_days,
    load_daily_pv,
    load_daily_pv_daytime,
    load_daily_weather,
)

# Domyślne parametry logiki śniegu (dziennie).
# Dobór: porównane w CV (GroupKFold po miesiącach) na danych projektu.
DEFAULT_SNOW_WINDOW_DAYS = 7
DEFAULT_SNOW_THAW_TEMP_C = 3.0

FEATURE_COLUMNS = [
    'radiation_daytime_kwh_m2',
    'cloud_cover_avg',
    'cloud_cover_low_avg',
    'temp_avg',
    'temp_min',
    'temp_max',
    'humidity_daytime_avg',
    'precip_mm',
    'om_snowfall_cm',
    'om_snow_depth_cm',
    'imgw_snow_depth_cm',
    # Logika śniegu na panelach (okno N dni): opad > 0 i brak odwilży (max temp < T°C)
    'snow_on_panels',
    'snow_on_panels_prev',
    # Mgła: model pogodowy „widzi” słońce (radiacja), ale PV 9–16h ma niską wydajność (wilgotność/visibility)
    'likely_fog_day',
    'rainy_day',
    'day_length_hours',
    'doy_sin',
    'doy_cos',
    'month',
]

TARGET_COLUMN = 'pv_kwh_daytime'  # suma PV w godzinach wschód–zachód (dynamicznie)


@dataclass
class TrainingSplit:
    X_train: pd.DataFrame
    X_test: pd.DataFrame
    y_train: pd.Series
    y_test: pd.Series
    meta_train: pd.DataFrame
    meta_test: pd.DataFrame
    feature_columns: list[str]
    test_start: str


def _load_imgw(db_path: str, start: str, end: str) -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(
        '''
        SELECT day, snow_depth_cm AS imgw_snow_depth_cm, temp_mean_c AS imgw_temp_mean_c
        FROM imgw_daily WHERE day BETWEEN ? AND ?
        ''',
        conn,
        params=(start, end),
    )
    conn.close()
    return df


def _is_artifact_day(row: pd.Series) -> bool:
    """Filtruje dni z anomalną produkcją PV (błąd falownika 21.04–29.05.2025).

    Poza okresem błędnej konfiguracji falownika wyłączony — zimą wysoki „artifact”
    to normalne rozładowanie baterii, nie błąd danych."""
    day_str = row.get('day')
    if day_str:
        d = date.fromisoformat(str(day_str)[:10])
        if not is_pv_inverter_misconfigured(d):
            return False

    artifact = float(row.get('pv_kwh_artifact') or 0)
    pv = float(row.get('pv_kwh_daytime') or 0)
    return artifact >= 10.0 and artifact > max(pv, 0.5) * 3.5


def apply_snow_panel_flags(
    df: pd.DataFrame,
    window_days: int | None = None,
    thaw_temp_c: float | None = None,
) -> pd.DataFrame:
    """
    Oznacza dni ze śniegiem na panelach (dzienna wersja reguły wielodniowej).

    Reguła: suma opadu śniegu w ostatnich N dniach > 0 oraz brak odwilży
    (max temp_max w oknie < T°C).
    """
    if 'temp_max' not in df.columns or 'om_snowfall_cm' not in df.columns:
        raise ValueError("Brak kolumn 'temp_max' lub 'om_snowfall_cm' do logiki śniegu.")

    window_days = int(window_days or os.getenv('SNOW_WINDOW_DAYS', str(DEFAULT_SNOW_WINDOW_DAYS)))
    thaw_temp_c = float(thaw_temp_c or os.getenv('SNOW_THAW_TEMP_C', str(DEFAULT_SNOW_THAW_TEMP_C)))

    out = df.copy()
    out['_dt'] = pd.to_datetime(out['day'])
    out = out.sort_values('_dt').reset_index(drop=True)

    max_temp = out['temp_max'].rolling(window=window_days, min_periods=1).max()
    snow_sum = out['om_snowfall_cm'].fillna(0).rolling(window=window_days, min_periods=1).sum()
    out['snow_on_panels'] = ((snow_sum > 0) & (max_temp < thaw_temp_c)).astype(int)
    out['snow_on_panels_prev'] = out['snow_on_panels'].shift(1).fillna(0).astype(int)
    out.drop(columns=['_dt'], inplace=True)
    return out


def calibrate_snow_panel_params(
    frame: pd.DataFrame,
    *,
    train_end: str | None = None,
    windows: tuple[int, ...] = (3, 5, 7),
    thaws: tuple[float, ...] = (1.0, 2.0, 3.0),
    n_splits: int = 5,
) -> tuple[int, float, pd.DataFrame]:
    """
    Dobiera okno i próg odwilży minimalizując MAE RF w GroupKFold (tylko zbiór train).

    Zwraca: (window_days, thaw_temp_c, tabela porównawcza).
    """
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.model_selection import GroupKFold, cross_val_score

    train = frame.copy()
    if train_end:
        train = train[train['day'] < train_end].copy()
    if train.empty:
        raise ValueError('Pusty zbiór do kalibracji śniegu.')

    groups = pd.to_datetime(train['day']).dt.to_period('M').astype(str)
    if groups.nunique() < n_splits:
        n_splits = max(2, groups.nunique())

    feature_base = [c for c in FEATURE_COLUMNS if c not in ('snow_on_panels', 'snow_on_panels_prev')]
    y = train[TARGET_COLUMN]

    rows: list[dict[str, float | int]] = []
    for window_days in windows:
        for thaw_temp_c in thaws:
            variant = apply_snow_panel_flags(train, window_days, thaw_temp_c)
            X = variant[feature_base + ['snow_on_panels', 'snow_on_panels_prev']]
            cv = GroupKFold(n_splits=n_splits)
            model = RandomForestRegressor(n_estimators=200, random_state=42, n_jobs=-1)
            scores = cross_val_score(
                model, X, y, groups=groups, cv=cv, scoring='neg_mean_absolute_error',
            )
            mae = -scores
            rows.append({
                'window_days': window_days,
                'thaw_temp_c': thaw_temp_c,
                'mae_mean_kwh': float(mae.mean()),
                'mae_std_kwh': float(mae.std()),
                'winter_snow_days': int(
                    variant.loc[pd.to_datetime(variant['day']).dt.month.isin([12, 1, 2]), 'snow_on_panels'].sum()
                ),
            })

    ranking = pd.DataFrame(rows).sort_values(['mae_mean_kwh', 'mae_std_kwh']).reset_index(drop=True)
    best = ranking.iloc[0]
    return int(best['window_days']), float(best['thaw_temp_c']), ranking


def load_training_frame(
    db_path: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    location: str | None = None,
    snow_window_days: int | None = None,
    snow_thaw_temp_c: float | None = None,
    snow_mode: str | None = None,
    melt_params: 'SnowMeltParams | None' = None,
) -> pd.DataFrame:
    """Dni z cechami pogodowymi + target PV w godzinach dziennych (wschód-zachód słońca).

    snow_mode: legacy (7d/3°C), melt (model topnienia), none (bez flag śniegu).
    
    UWAGA: Od teraz używamy dynamicznych godzin (wschód-zachód słońca), 
           zamiast stałego okna 9-16h. Dzięki temu zimą nie tracimy produkcji 
           o 7-8h rano, a latem uwzględniamy produkcję do 20h.
    """
    db_path = db_path or os.getenv('DATABASE_PATH', 'data/energy_model.db')
    if not os.path.isabs(db_path):
        _root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        candidate = os.path.join(_root, db_path)
        # Nie używaj pustego pliku powstałego przez SQLite w notebooks/data/
        if os.path.exists(candidate) and os.path.getsize(candidate) > 1_000_000:
            db_path = candidate
        elif os.path.exists(os.path.join(_root, 'data', 'energy_model.db')):
            db_path = os.path.join(_root, 'data', 'energy_model.db')
    location = location if location is not None else os.getenv('WEATHER_LOCATION')
    start_date = start_date or os.getenv('ML_TRAIN_START', ML_BATTERY_START.isoformat())
    end_date = end_date or os.getenv('ML_TRAIN_END', date.today().isoformat())
    
    # Współrzędne dla dynamicznych godzin
    latitude = float(os.getenv('WEATHER_LAT', '50.06'))
    longitude = float(os.getenv('WEATHER_LON', '19.94'))

    weather = load_daily_weather(db_path, start_date, end_date, location, 
                                 use_dynamic_hours=True, latitude=latitude, longitude=longitude)
    pv = load_daily_pv(db_path, start_date, end_date)
    pv_day = load_daily_pv_daytime(db_path, start_date, end_date, 
                                   use_dynamic_hours=True, latitude=latitude, longitude=longitude)
    imgw = _load_imgw(db_path, start_date, end_date)

    # Flaga mgły (heurystyka): radiacja vs niski yield PV + wilgotność/visibility.
    # Uwaga: to jest cecha pomocnicza, nie filtr jakości (nie wycina dni).
    fog = flag_likely_fog_days(weather, pv_day)[['day', 'likely_fog_day']]
    if not fog.empty:
        fog['likely_fog_day'] = fog['likely_fog_day'].astype(int)

    df = weather.merge(pv, on='day').merge(pv_day, on='day').merge(imgw, on='day', how='left')
    if not fog.empty:
        df = df.merge(fog, on='day', how='left')
        df['likely_fog_day'] = df['likely_fog_day'].fillna(0).astype(int)
    else:
        df['likely_fog_day'] = 0
    
    # Flaga deszczu: wysoka wilgotność + chmury + opady >1mm
    # (wyższa efektywność PV niż mgła przy podobnej radiacji - deszcz ma przerwy)
    humid = df['humidity_daytime_avg'].fillna(df['humidity_avg'])
    df['rainy_day'] = (
        (humid >= 90) & 
        (df['cloud_cover_avg'] >= 95) & 
        (df['precip_mm'] > 1.0)
    ).astype(int)
    
    # Długość dnia (godziny między wschodem a zachodem słońca)
    # Kluczowa dla odróżnienia wiosny od jesieni przy tej samej temperaturze/radiacji
    if 'sunset_hour' in df.columns and 'sunrise_hour' in df.columns:
        df['day_length_hours'] = df['sunset_hour'] - df['sunrise_hour']
    else:
        # Fallback: aproksymacja na podstawie doy (dzień roku) dla ~50°N
        dt = pd.to_datetime(df['day'])
        doy = dt.dt.dayofyear
        df['day_length_hours'] = 12.0 + 4.5 * np.sin(2 * np.pi * (doy - 80) / 365.25)
    df.rename(columns={
        'snowfall_cm_sum': 'om_snowfall_cm',
    }, inplace=True)
    df['om_snow_depth_cm'] = (df['snow_depth_m_max'].fillna(0) * 100).round(0)

    dt = pd.to_datetime(df['day'])
    doy = dt.dt.dayofyear
    df['doy_sin'] = np.sin(2 * np.pi * doy / 365.25)
    df['doy_cos'] = np.cos(2 * np.pi * doy / 365.25)
    df['month'] = dt.dt.month

    if snow_mode is None:
        # Domyślnie używaj model topnienia (melt) - bardziej dokładny niż legacy
        if os.getenv('SNOW_USE_MELT_MODEL', '').lower() in ('0', 'false', 'no'):
            snow_mode = 'legacy'  # tylko gdy explicite wyłączono
        else:
            snow_mode = 'melt'  # DOMYŚLNIE model topnienia

    if snow_mode == 'legacy':
        df = apply_snow_panel_flags(df, snow_window_days, snow_thaw_temp_c)
    elif snow_mode == 'melt':
        from src.features.snow_melt_model import apply_melt_snow_flags

        df = apply_melt_snow_flags(
            df, db_path, start_date, end_date, location, params=melt_params,
        )
    elif snow_mode == 'none':
        df['snow_on_panels'] = 0
        df['snow_on_panels_prev'] = 0
    else:
        raise ValueError(f"Nieznany snow_mode={snow_mode!r} (legacy | melt | none)")

    valid = df['day'].apply(lambda d: is_pv_weather_valid(date.fromisoformat(d)))
    valid &= ~df.apply(_is_artifact_day, axis=1)
    valid &= df[TARGET_COLUMN].notna()
    valid &= df['radiation_daytime_kwh_m2'].notna()

    return df.loc[valid].copy().sort_values('day').reset_index(drop=True)


def time_train_test_split(
    frame: pd.DataFrame,
    test_start: str | None = None,
    feature_columns: list[str] | None = None,
) -> TrainingSplit:
    """Podział czasowy: train < test_start, test >= test_start."""
    test_start = test_start or os.getenv('ML_TEST_START', '2026-02-01')
    features = feature_columns or FEATURE_COLUMNS

    missing = [c for c in features if c not in frame.columns]
    if missing:
        raise ValueError(f'Brak kolumn cech: {missing}')

    train = frame[frame['day'] < test_start].copy()
    test = frame[frame['day'] >= test_start].copy()
    if train.empty or test.empty:
        raise ValueError(
            f'Pusty train lub test (test_start={test_start}). '
            f'Train: {len(train)} dni, test: {len(test)} dni.'
        )

    meta_cols = ['day', TARGET_COLUMN, 'radiation_daytime_kwh_m2', 'pv_kwh_artifact']
    meta_cols = [c for c in meta_cols if c in frame.columns]

    return TrainingSplit(
        X_train=train[features],
        X_test=test[features],
        y_train=train[TARGET_COLUMN],
        y_test=test[TARGET_COLUMN],
        meta_train=train[meta_cols],
        meta_test=test[meta_cols],
        feature_columns=features,
        test_start=test_start,
    )
