"""
Model godzinowy PV — trening, zapis i prognoza 1–2 dni do przodu.

Prognoza wykorzystuje:
- Open-Meteo forecast (pogoda w bazie lub świeże pobranie)
- Cechy słoneczne (wschód/zachód) z astral
- Heurystyki śniegu/mgły dla dni bez pomiarów PV
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from typing import Any, Optional

import joblib
import numpy as np
import pandas as pd
import sqlite3
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline

from src.features.pv_features_hourly_extended import (
    HOURLY_FEATURE_COLUMNS_PRODUCTION,
    TARGET_COLUMN,
    calculate_sun_features,
    load_hourly_pv_dynamic,
    load_hourly_training_frame_extended,
)

DEFAULT_MODEL_PATH = 'models/pv_hourly_model.joblib'

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def resolve_model_path(path: str | None = None) -> str:
    """Ścieżka do .joblib — względna zawsze względem katalogu projektu (nie cwd)."""
    raw = path or os.getenv('PV_HOURLY_MODEL_PATH', DEFAULT_MODEL_PATH)
    if os.path.isabs(raw):
        return raw
    return os.path.join(_PROJECT_ROOT, raw)


def metadata_path_for(joblib_path: str) -> str:
    """Plik metadata.json obok artefaktu .joblib (metryki + hiperparametry modelu)."""
    if joblib_path.endswith('.joblib'):
        return joblib_path[:-7] + '.metadata.json'
    return f'{joblib_path}.metadata.json'


def _json_safe(value: Any) -> Any:
    if isinstance(value, (np.integer, np.floating)):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value

# Regularyzacja RF (wdrożenie — wybrane przez GridSearch min-gap)
RF_N_ESTIMATORS = 200
RF_MAX_DEPTH = 6
RF_MIN_SAMPLES_LEAF = 20
RF_MIN_SAMPLES_SPLIT = 20
RF_MAX_FEATURES = 1.0
RF_RANDOM_STATE = 42

# Typowe moce urządzeń domowych [kW] — do rekomendacji godzin
APPLIANCE_PROFILES = {
    'pralka': {'min_kw': 1.5, 'duration_h': 2.0, 'label': 'Pralka'},
    'suszarka': {'min_kw': 2.0, 'duration_h': 1.5, 'label': 'Suszarka'},
    'zmywarka': {'min_kw': 1.2, 'duration_h': 2.0, 'label': 'Zmywarka'},
    'gotowanie': {'min_kw': 1.5, 'duration_h': 1.0, 'label': 'Gotowanie (płyta/oven)'},
}


@dataclass
class ApplianceRecommendation:
    day: str
    hour: int
    predicted_kwh: float
    predicted_kw: float
    appliances: list[str]
    rank: int


@dataclass
class TrainingReport:
    train_mae: float
    test_mae: float
    gap: float
    cv_mae: float
    cv_std: float
    test_minus_cv: float
    daily_mae: float
    daily_r2: float
    verdict: str
    n_train: int
    n_test: int


def _default_pipeline(
    *,
    max_depth: int = RF_MAX_DEPTH,
    min_samples_leaf: int = RF_MIN_SAMPLES_LEAF,
    min_samples_split: int = RF_MIN_SAMPLES_SPLIT,
    max_features=RF_MAX_FEATURES,
    n_estimators: int = RF_N_ESTIMATORS,
) -> Pipeline:
    return Pipeline([
        ('imputer', SimpleImputer(strategy='median')),
        ('model', RandomForestRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            min_samples_leaf=min_samples_leaf,
            min_samples_split=min_samples_split,
            max_features=max_features,
            random_state=RF_RANDOM_STATE,
            n_jobs=-1,
        )),
    ])


def _metrics(y_true, y_pred) -> dict:
    return {
        'mae': mean_absolute_error(y_true, y_pred),
        'rmse': float(np.sqrt(mean_squared_error(y_true, y_pred))),
        'r2': r2_score(y_true, y_pred),
    }


def _overfit_verdict(gap: float, test_minus_cv: float, test_mae: float) -> str:
    if gap < 0.4 and abs(test_minus_cv) < 0.15:
        return '✅ Model NIE jest przeuczony'
    if gap < 0.7 and abs(test_minus_cv) < 0.3:
        return '⚠️  Lekkie przeuczenie (akceptowalne)'
    return '❌ Model przeuczony'


def load_weather_hourly(
    db_path: str,
    start_date: str,
    end_date: str,
    location: str | None = None,
    *,
    data_source_like: str = '%forecast%',
) -> pd.DataFrame:
    """Godzinowa pogoda z weather_data (archiwum lub prognoza)."""
    conn = sqlite3.connect(db_path)
    location_filter = 'AND location = ?' if location else ''
    params: list = [start_date, end_date, data_source_like]
    if location:
        params.append(location)

    query = f"""
    SELECT
        DATE(timestamp) AS day,
        CAST(strftime('%H', timestamp) AS INTEGER) AS hour,
        AVG(temperature_celsius) AS temp_c,
        AVG(humidity_percent) AS humidity_pct,
        AVG(cloud_cover_percent) AS cloud_cover_pct,
        AVG(cloud_cover_low_percent) AS cloud_cover_low_pct,
        AVG(cloud_cover_mid_percent) AS cloud_cover_mid_pct,
        AVG(solar_radiation_wm2) AS radiation_wm2,
        AVG(wind_speed_ms) AS wind_speed_ms,
        AVG(visibility_m) AS visibility_m,
        AVG(snow_depth_m) AS snow_depth_m,
        AVG(precipitation_mm) AS precip_mm
    FROM weather_data
    WHERE DATE(timestamp) BETWEEN ? AND ?
      AND data_source LIKE ?
      AND CAST(strftime('%H', timestamp) AS INTEGER) BETWEEN 5 AND 21
      {location_filter}
    GROUP BY DATE(timestamp), hour
    ORDER BY day, hour
    """
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    if not df.empty:
        if 'cloud_cover_low_pct' in df.columns:
            df['cloud_cover_low_pct'] = df['cloud_cover_low_pct'].fillna(df['cloud_cover_pct'])
        else:
            df['cloud_cover_low_pct'] = df['cloud_cover_pct']
        if 'cloud_cover_mid_pct' in df.columns:
            df['cloud_cover_mid_pct'] = df['cloud_cover_mid_pct'].fillna(df['cloud_cover_pct'])
        else:
            df['cloud_cover_mid_pct'] = df['cloud_cover_pct']
    return df


def load_forecast_weather_hourly(
    db_path: str,
    start_date: str,
    end_date: str,
    location: str | None = None,
) -> pd.DataFrame:
    """Godzinowa prognoza pogody z weather_data (OpenMeteo-forecast)."""
    return load_weather_hourly(
        db_path, start_date, end_date, location, data_source_like='%forecast%',
    )


def load_archive_weather_hourly(
    db_path: str,
    start_date: str,
    end_date: str,
    location: str | None = None,
) -> pd.DataFrame:
    """Godzinowe obserwacje/archiwum z weather_data (OpenMeteo-archive)."""
    return load_weather_hourly(
        db_path, start_date, end_date, location, data_source_like='%archive%',
    )


def _is_past_hour(day: str, hour: int, as_of: datetime) -> bool:
    d = date.fromisoformat(day)
    if d < as_of.date():
        return True
    if d > as_of.date():
        return False
    return hour < as_of.hour


def load_hybrid_weather_hourly(
    db_path: str,
    start_date: str,
    end_date: str,
    location: str | None = None,
    as_of: datetime | None = None,
) -> pd.DataFrame:
    """Dziś: archiwum dla minionych godzin, prognoza dla reszty; jutro+: prognoza."""
    as_of = as_of or datetime.now()
    archive = load_archive_weather_hourly(db_path, start_date, end_date, location)
    forecast = load_forecast_weather_hourly(db_path, start_date, end_date, location)

    if forecast.empty and archive.empty:
        return pd.DataFrame()

    grid_days = pd.date_range(start_date, end_date, freq='D')
    records = []
    for d in grid_days:
        day = d.date().isoformat()
        for hour in range(5, 22):
            records.append({'day': day, 'hour': hour})
    grid = pd.DataFrame(records)

    archive = archive.rename(columns={
        c: f'{c}_arc' for c in archive.columns if c not in ('day', 'hour')
    })
    forecast = forecast.rename(columns={
        c: f'{c}_fc' for c in forecast.columns if c not in ('day', 'hour')
    })
    merged = grid.merge(archive, on=['day', 'hour'], how='left')
    merged = merged.merge(forecast, on=['day', 'hour'], how='left')

    weather_cols = [
        'temp_c', 'humidity_pct', 'cloud_cover_pct', 'radiation_wm2',
        'wind_speed_ms', 'visibility_m', 'snow_depth_m', 'precip_mm',
    ]
    rows = []
    for _, row in merged.iterrows():
        day, hour = str(row['day']), int(row['hour'])
        use_archive = _is_past_hour(day, hour, as_of)
        picked = {}
        source = 'forecast'
        for col in weather_cols:
            arc = row.get(f'{col}_arc')
            fc = row.get(f'{col}_fc')
            if use_archive and pd.notna(arc):
                picked[col] = arc
                source = 'archive'
            elif pd.notna(fc):
                picked[col] = fc
            elif pd.notna(arc):
                picked[col] = arc
                source = 'archive'
            else:
                picked[col] = np.nan
        rows.append({'day': day, 'hour': hour, 'weather_source': source, **picked})

    return pd.DataFrame(rows)


def load_actual_pv_hourly(
    db_path: str,
    day: str,
    as_of: datetime | None = None,
) -> pd.DataFrame:
    """Rzeczywista produkcja FoxESS dla danego dnia (godziny już minione)."""
    as_of = as_of or datetime.now()
    if date.fromisoformat(day) > as_of.date():
        return pd.DataFrame(columns=['day', 'hour', TARGET_COLUMN])

    pv = load_hourly_pv_dynamic(db_path, day, day)
    if pv.empty:
        return pd.DataFrame(columns=['day', 'hour', TARGET_COLUMN])

    if date.fromisoformat(day) == as_of.date():
        pv = pv[pv['hour'] < as_of.hour].copy()
    return pv[['day', 'hour', TARGET_COLUMN]]


def _daily_weather_from_hourly(hourly: pd.DataFrame) -> pd.DataFrame:
    """Agregacja godzinowej prognozy do dziennej (flagi śniegu/mgły)."""
    if hourly.empty:
        return pd.DataFrame()

    g = hourly.groupby('day')
    daily = g.agg(
        temp_avg=('temp_c', 'mean'),
        humidity_avg=('humidity_pct', 'mean'),
        cloud_cover_avg=('cloud_cover_pct', 'mean'),
        radiation_daytime_kwh_m2=('radiation_wm2', lambda s: s.sum() / 1000.0),
        visibility_min_m=('visibility_m', 'min'),
        precip_mm=('precip_mm', 'sum'),
        snow_depth_m_max=('snow_depth_m', 'max'),
    ).reset_index()

    daily['humidity_daytime_avg'] = g['humidity_pct'].mean().values
    return daily


def _forecast_snow_flags(daily: pd.DataFrame) -> pd.DataFrame:
    """Heurystyka śniegu na panelach z prognozy pogody."""
    df = daily.copy()
    snow = (
        df['snow_depth_m_max'].fillna(0) > 0.05
    ) & (df['temp_avg'].fillna(10) < 2.0)
    df['snow_on_panels'] = snow.astype(int)
    df['snow_on_panels_prev'] = df['snow_on_panels'].shift(1).fillna(0).astype(int)
    return df[['day', 'snow_on_panels', 'snow_on_panels_prev']]


def _forecast_fog_flags(daily: pd.DataFrame) -> pd.DataFrame:
    """Heurystyka mgły z prognozy (bez pomiarów PV)."""
    df = daily.copy()
    humid = df['humidity_daytime_avg'].fillna(df['humidity_avg'])
    df['likely_fog_day'] = (
        (df['radiation_daytime_kwh_m2'] >= 0.35)
        & (humid >= 85)
        & (
            df['visibility_min_m'].fillna(99999) < 2000
        )
        & (df['precip_mm'].fillna(0) <= 1.0)
    ).astype(int)
    return df[['day', 'likely_fog_day']]


def build_forecast_feature_frame(
    db_path: str,
    forecast_dates: list[str],
    latitude: float = 50.06,
    longitude: float = 19.94,
    location: str | None = None,
    as_of: datetime | None = None,
    hybrid_today: bool = True,
) -> pd.DataFrame:
    """Zbuduj macierz cech dla dni prognozy (bez kolumny target).

    hybrid_today=True: dla bieżącego dnia minione godziny biorą pogodę z archiwum.
    """
    if not forecast_dates:
        return pd.DataFrame()

    as_of = as_of or datetime.now()
    start = min(forecast_dates)
    end = max(forecast_dates)
    today_str = as_of.date().isoformat()

    if hybrid_today and today_str in forecast_dates:
        weather = load_hybrid_weather_hourly(db_path, start, end, location, as_of=as_of)
    else:
        weather = load_forecast_weather_hourly(db_path, start, end, location)
        weather['weather_source'] = 'forecast'

    if weather.empty:
        raise ValueError(
            f'Brak prognozy pogody w bazie dla {start}–{end}. '
            'Uruchom: python mlops/sync_data.py --weather'
        )

    # Siatka godzin 5–21 dla każdego dnia prognozy
    records = []
    for day in forecast_dates:
        for hour in range(5, 22):
            records.append({'day': day, 'hour': hour})
    grid = pd.DataFrame(records)

    df = grid.merge(
        weather.drop(columns=['weather_source'], errors='ignore'),
        on=['day', 'hour'],
        how='left',
    )
    if 'weather_source' in weather.columns:
        df = df.merge(weather[['day', 'hour', 'weather_source']], on=['day', 'hour'], how='left')
    else:
        df['weather_source'] = 'forecast'
    df = calculate_sun_features(df, latitude=latitude, longitude=longitude)

    from src.features.clearness import add_clearness_features
    df = add_clearness_features(df, latitude=latitude, longitude=longitude)

    if 'cloud_cover_low_pct' not in df.columns:
        df['cloud_cover_low_pct'] = df.get('cloud_cover_pct')
    if 'cloud_cover_mid_pct' not in df.columns:
        df['cloud_cover_mid_pct'] = df.get('cloud_cover_pct')
    df['cloud_cover_low_pct'] = df['cloud_cover_low_pct'].fillna(df['cloud_cover_pct'])
    df['cloud_cover_mid_pct'] = df['cloud_cover_mid_pct'].fillna(df['cloud_cover_pct'])

    dt = pd.to_datetime(df['day'])
    doy = dt.dt.dayofyear
    df['doy_sin'] = np.sin(2 * np.pi * doy / 365.25)
    df['doy_cos'] = np.cos(2 * np.pi * doy / 365.25)
    df['month'] = dt.dt.month

    daily = _daily_weather_from_hourly(weather)
    snow = _forecast_snow_flags(daily)
    fog = _forecast_fog_flags(daily)
    df = df.merge(snow, on='day', how='left')
    df = df.merge(fog, on='day', how='left')
    df['snow_on_panels'] = df['snow_on_panels'].fillna(0).astype(int)
    df['snow_on_panels_prev'] = df['snow_on_panels_prev'].fillna(0).astype(int)
    df['likely_fog_day'] = df['likely_fog_day'].fillna(0).astype(int)

    df = df.loc[df['is_daylight'] == 1].copy()
    df = df.loc[df['radiation_wm2'].notna()].reset_index(drop=True)
    return df


def _appliances_for_hour(predicted_kwh: float) -> list[str]:
    """Które urządzenia można sensownie uruchomić przy danej produkcji [kWh/h ≈ kW]."""
    kw = max(predicted_kwh, 0.0)
    return [
        profile['label']
        for profile in APPLIANCE_PROFILES.values()
        if kw >= profile['min_kw']
    ]


def rank_hours_for_appliances(
    predictions: pd.DataFrame,
    top_n_per_day: int = 5,
    future_only: bool = True,
) -> list[ApplianceRecommendation]:
    """Ranking godzin z najwyższą prognozą PV — rekomendacje urządzeń."""
    recs: list[ApplianceRecommendation] = []
    df = predictions
    if future_only and 'prediction_source' in df.columns:
        df = df[df['prediction_source'] == 'model']
    for day, group in df.groupby('day'):
        top = group.nlargest(top_n_per_day, 'predicted_kwh')
        for rank, (_, row) in enumerate(top.iterrows(), 1):
            kwh = float(row['predicted_kwh'])
            recs.append(ApplianceRecommendation(
                day=str(day),
                hour=int(row['hour']),
                predicted_kwh=kwh,
                predicted_kw=kwh,
                appliances=_appliances_for_hour(kwh),
                rank=rank,
            ))
    return recs


class PVHourlyPredictor:
    """Pipeline treningu i prognozy godzinowej produkcji PV."""

    def __init__(self, model_path: str = DEFAULT_MODEL_PATH):
        self.model_path = resolve_model_path(model_path)
        self.pipeline: Pipeline | None = None
        self.feature_columns = list(HOURLY_FEATURE_COLUMNS_PRODUCTION)
        self.latitude = 50.06
        self.longitude = 19.94
        self.location: str | None = None
        self.report: TrainingReport | None = None

    def train(
        self,
        db_path: str | None = None,
        test_start: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> TrainingReport:
        self.latitude = latitude or float(os.getenv('WEATHER_LAT', '50.06'))
        self.longitude = longitude or float(os.getenv('WEATHER_LON', '19.94'))
        self.location = os.getenv('WEATHER_LOCATION')
        test_start = test_start or os.getenv('ML_TEST_START', '2026-02-01')

        frame = load_hourly_training_frame_extended(
            db_path=db_path,
            latitude=self.latitude,
            longitude=self.longitude,
        )

        train_mask = frame['day'] < test_start
        test_mask = frame['day'] >= test_start

        X_train = frame.loc[train_mask, self.feature_columns]
        y_train = frame.loc[train_mask, TARGET_COLUMN]
        X_test = frame.loc[test_mask, self.feature_columns]
        y_test = frame.loc[test_mask, TARGET_COLUMN]
        meta_train = frame.loc[train_mask, ['day', 'hour']]
        meta_test = frame.loc[test_mask, ['day', 'hour']]

        self.pipeline = _default_pipeline()
        self.pipeline.fit(X_train, y_train)

        train_pred = self.pipeline.predict(X_train)
        test_pred = self.pipeline.predict(X_test)
        train_m = _metrics(y_train, train_pred)
        test_m = _metrics(y_test, test_pred)
        gap = test_m['mae'] - train_m['mae']

        groups = meta_train['day']
        cv = GroupKFold(n_splits=5)
        cv_scores = []
        for train_idx, val_idx in cv.split(X_train, y_train, groups=groups):
            fold = _default_pipeline()
            fold.fit(X_train.iloc[train_idx], y_train.iloc[train_idx])
            val_pred = fold.predict(X_train.iloc[val_idx])
            cv_scores.append(mean_absolute_error(y_train.iloc[val_idx], val_pred))

        cv_mean = float(np.mean(cv_scores))
        cv_std = float(np.std(cv_scores))
        test_minus_cv = test_m['mae'] - cv_mean

        test_with_pred = meta_test.copy()
        test_with_pred['y_true'] = y_test.values
        test_with_pred['y_pred'] = test_pred
        daily_true = test_with_pred.groupby('day')['y_true'].sum()
        daily_pred = test_with_pred.groupby('day')['y_pred'].sum()
        daily_mae = mean_absolute_error(daily_true, daily_pred)
        daily_r2 = r2_score(daily_true, daily_pred)

        verdict = _overfit_verdict(gap, test_minus_cv, test_m['mae'])
        self.report = TrainingReport(
            train_mae=train_m['mae'],
            test_mae=test_m['mae'],
            gap=gap,
            cv_mae=cv_mean,
            cv_std=cv_std,
            test_minus_cv=test_minus_cv,
            daily_mae=daily_mae,
            daily_r2=daily_r2,
            verdict=verdict,
            n_train=len(y_train),
            n_test=len(y_test),
        )
        return self.report

    def _build_metadata(self, extra_metadata: dict | None = None) -> dict:
        meta: dict[str, Any] = {
            'saved_at': datetime.now().isoformat(timespec='seconds'),
            'model_path': self.model_path,
            'algorithm': 'RandomForestRegressor',
            'target': TARGET_COLUMN,
            'n_features': len(self.feature_columns or []),
            'feature_columns': list(self.feature_columns or []),
            'latitude': self.latitude,
            'longitude': self.longitude,
            'location': self.location,
        }
        if self.pipeline is not None:
            model_step = self.pipeline.named_steps.get('model')
            if model_step is not None:
                meta['hyperparameters'] = _json_safe(model_step.get_params())
        if self.report is not None:
            meta['metrics'] = _json_safe(asdict(self.report))
        if extra_metadata:
            meta.update(_json_safe(extra_metadata))
        return meta

    def write_metadata_sidecar(self, extra_metadata: dict | None = None) -> str:
        """Zapis metadata.json obok .joblib (bez ponownego zapisu modelu)."""
        if self.pipeline is None:
            raise RuntimeError('Model niezaładowany — użyj load() lub train().')
        meta_path = metadata_path_for(self.model_path)
        os.makedirs(os.path.dirname(meta_path) or '.', exist_ok=True)
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(self._build_metadata(extra_metadata), f, ensure_ascii=False, indent=2)
            f.write('\n')
        return meta_path

    def save(self, path: str | None = None, *, extra_metadata: dict | None = None) -> str:
        if self.pipeline is None:
            raise RuntimeError('Najpierw wytrenuj model (train()).')
        path = resolve_model_path(path or self.model_path)
        self.model_path = path
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        joblib.dump({
            'pipeline': self.pipeline,
            'feature_columns': self.feature_columns,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'location': self.location,
            'report': self.report,
        }, path)
        self.write_metadata_sidecar(extra_metadata)
        return path

    def load(self, path: str | None = None) -> None:
        path = resolve_model_path(path or self.model_path)
        self.model_path = path
        if not os.path.exists(path):
            raise FileNotFoundError(
                f'Brak zapisanego modelu: {path}. Uruchom: '
                'PYTHONPATH=$PWD python scripts/train_hourly_model_tuning.py'
            )
        data = joblib.load(path)
        self.pipeline = data['pipeline']
        self.feature_columns = data['feature_columns']
        self.latitude = data.get('latitude', 50.06)
        self.longitude = data.get('longitude', 19.90)
        self.location = data.get('location')
        self.report = data.get('report')

    def predict_days(
        self,
        days_ahead: int = 3,
        db_path: str | None = None,
        from_date: date | None = None,
        hybrid_today: bool = True,
        use_actual_pv: bool = True,
        as_of: datetime | None = None,
    ) -> pd.DataFrame:
        if self.pipeline is None:
            raise RuntimeError('Model niezaładowany — użyj load() lub train().')

        db_path = db_path or os.getenv('DATABASE_PATH', 'data/energy_model.db')
        as_of = as_of or datetime.now()
        base = from_date or as_of.date()
        # days_ahead=3 → dziś + jutro + pojutrze (d=0,1,2)
        forecast_dates = [
            (base + timedelta(days=d)).isoformat()
            for d in range(0, days_ahead)
        ]

        features = build_forecast_feature_frame(
            db_path,
            forecast_dates,
            latitude=self.latitude,
            longitude=self.longitude,
            location=self.location,
            as_of=as_of,
            hybrid_today=hybrid_today,
        )

        # Shadow XGB+TS: lag/rolling NWP (bez targetu PV)
        from src.features.nwp_time_series import TS_FEATURE_COLUMNS, add_nwp_time_series_features
        if any(c in self.feature_columns for c in TS_FEATURE_COLUMNS):
            features = add_nwp_time_series_features(features)

        missing = [c for c in self.feature_columns if c not in features.columns]
        if missing:
            raise ValueError(f'Brak kolumn cech w prognozie: {missing}')

        X = features[self.feature_columns]
        pred = np.clip(self.pipeline.predict(X), 0, None)

        out = features[['day', 'hour', 'radiation_wm2', 'cloud_cover_pct',
                        'sunrise_hour', 'sunset_hour', 'is_daylight']].copy()
        if 'weather_source' in features.columns:
            out['weather_source'] = features['weather_source']
        out['predicted_kwh'] = pred
        out['predicted_kw'] = pred
        out['predicted_kwh_raw'] = pred.copy()
        out['prediction_source'] = 'model'

        if use_actual_pv and hybrid_today:
            today_str = as_of.date().isoformat()
            actuals = load_actual_pv_hourly(db_path, today_str, as_of=as_of)
            if not actuals.empty:
                actual_map = actuals.set_index('hour')[TARGET_COLUMN]
                today_mask = out['day'] == today_str
                for hour, kwh in actual_map.items():
                    hmask = today_mask & (out['hour'] == hour)
                    out.loc[hmask, 'predicted_kwh'] = float(kwh)
                    out.loc[hmask, 'predicted_kw'] = float(kwh)
                    out.loc[hmask, 'prediction_source'] = 'foxess_actual'

        return out.sort_values(['day', 'hour']).reset_index(drop=True)

    def recommend_appliances(
        self,
        days_ahead: int = 3,
        top_n_per_day: int = 5,
        db_path: str | None = None,
        hybrid_today: bool = True,
        use_actual_pv: bool = True,
        operational_adjust: bool = True,
        as_of: datetime | None = None,
    ) -> tuple[pd.DataFrame, list[ApplianceRecommendation]]:
        predictions = self.predict_days(
            days_ahead=days_ahead,
            db_path=db_path,
            hybrid_today=hybrid_today,
            use_actual_pv=use_actual_pv,
            as_of=as_of,
        )
        adjust_report = None
        if operational_adjust:
            from src.models.intraday_forecast_adjust import (
                apply_operational_adjustment,
                rank_hours_conservative,
            )
            predictions, adjust_report = apply_operational_adjustment(predictions, as_of=as_of)
            predictions.attrs['intraday_adjust_report'] = adjust_report
            recs = rank_hours_conservative(predictions, top_n_per_day=top_n_per_day)
        else:
            recs = rank_hours_for_appliances(predictions, top_n_per_day=top_n_per_day)
        return predictions, recs


def train_and_save(
    model_path: str = DEFAULT_MODEL_PATH,
    db_path: str | None = None,
) -> TrainingReport:
    predictor = PVHourlyPredictor(model_path=model_path)
    report = predictor.train(db_path=db_path)
    predictor.save()
    return report


def load_predictor(model_path: str = DEFAULT_MODEL_PATH) -> PVHourlyPredictor:
    predictor = PVHourlyPredictor(model_path=model_path)
    predictor.load()
    return predictor
