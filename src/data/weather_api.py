"""
Pobieranie danych pogodowych z Open-Meteo (historia + prognoza).

Dokumentacja: https://open-meteo.com/en/docs
Bez klucza API, darmowe użycie niekomercyjne.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# Filtr baterii: wyklucza pomiary PV gdy bateria się rozładowuje (artefakt księgowy FoxESS).
# Stosowany przy ODCZYCIE danych — import z API/CSV zapisuje surowe wartości bez filtra.
BATTERY_DISCHARGE_THRESHOLD_KW = -0.1
BATTERY_FILTER_SQL = f'COALESCE(battery_power_kw, 0) >= {BATTERY_DISCHARGE_THRESHOLD_KW}'
PV_SOLAR_KWH_SQL = (
    f'CASE WHEN pv_energy_kwh > 0 AND {BATTERY_FILTER_SQL} '
    f'THEN pv_energy_kwh ELSE 0 END'
)

ARCHIVE_URL = 'https://archive-api.open-meteo.com/v1/archive'
FORECAST_URL = 'https://api.open-meteo.com/v1/forecast'
TIMEZONE = 'Europe/Warsaw'

# Model pogodowy Open-Meteo (archive + forecast).
# best_match = domyślny (często „gładzi” chmury); icon_seamless lepiej łapie pochmurne dni PV.
DEFAULT_OPENMETEO_MODEL = 'best_match'

HOURLY_VARS = [
    'temperature_2m',
    'relative_humidity_2m',
    'cloud_cover',
    'cloud_cover_low',
    'cloud_cover_mid',
    'cloud_cover_high',
    'visibility',
    'precipitation',
    'snowfall',
    'snow_depth',
    'shortwave_radiation',
    'wind_speed_10m',
    'wind_direction_10m',
]

WEATHER_EXTRA_COLUMNS = {
    'snowfall_cm': 'REAL',
    'snow_depth_m': 'REAL',
    'cloud_cover_low_percent': 'REAL',
    'cloud_cover_mid_percent': 'REAL',
    'cloud_cover_high_percent': 'REAL',
    'visibility_m': 'REAL',
}


def _get_json(url: str, params: dict) -> dict:
    query = urllib.parse.urlencode(params)
    full_url = f'{url}?{query}'
    logger.debug('GET %s', full_url)
    with urllib.request.urlopen(full_url, timeout=120) as resp:
        return json.loads(resp.read().decode())


def _response_to_df(payload: dict, location: str, data_source: str) -> pd.DataFrame:
    hourly = payload.get('hourly') or {}
    times = hourly.get('time') or []
    if not times:
        return pd.DataFrame()

    df = pd.DataFrame({'timestamp': pd.to_datetime(times)})
    df['temperature_celsius'] = hourly.get('temperature_2m')
    df['humidity_percent'] = hourly.get('relative_humidity_2m')
    df['cloud_cover_percent'] = hourly.get('cloud_cover')
    df['cloud_cover_low_percent'] = hourly.get('cloud_cover_low')
    df['cloud_cover_mid_percent'] = hourly.get('cloud_cover_mid')
    df['cloud_cover_high_percent'] = hourly.get('cloud_cover_high')
    df['visibility_m'] = hourly.get('visibility')
    df['precipitation_mm'] = hourly.get('precipitation')
    df['snowfall_cm'] = hourly.get('snowfall')
    df['snow_depth_m'] = hourly.get('snow_depth')
    df['solar_radiation_wm2'] = hourly.get('shortwave_radiation')
    df['wind_speed_ms'] = hourly.get('wind_speed_10m')
    df['wind_direction_deg'] = hourly.get('wind_direction_10m')
    df['pressure_hpa'] = None
    df['sunshine_duration_min'] = None
    df['location'] = location
    df['data_source'] = data_source
    return df


def resolve_openmeteo_model(model: str | None = None) -> str | None:
    """Zwraca nazwę modelu do parametru API albo None (= domyślny best_match serwera)."""
    raw = (model if model is not None else os.getenv('OPENMETEO_MODEL', '')).strip()
    if not raw or raw.lower() in ('best_match', 'default', 'auto'):
        return None
    return raw


class OpenMeteoClient:
    """Klient Open-Meteo — historia (archive) i prognoza."""

    def __init__(
        self,
        latitude: float,
        longitude: float,
        location_label: str = 'home',
        model: str | None = None,
    ):
        self.latitude = latitude
        self.longitude = longitude
        self.location_label = location_label
        self.model = resolve_openmeteo_model(model)

    @classmethod
    def from_env(cls) -> 'OpenMeteoClient':
        lat = os.getenv('WEATHER_LAT', '50.06')
        lon = os.getenv('WEATHER_LON', '19.94')
        label = os.getenv('WEATHER_LOCATION', 'home')
        return cls(float(lat), float(lon), label, model=os.getenv('OPENMETEO_MODEL'))

    def _with_model(self, params: dict) -> dict:
        if self.model:
            params['models'] = self.model
        return params

    def fetch_archive(
        self,
        start_date: str,
        end_date: str,
        chunk_days: int = 31,
    ) -> pd.DataFrame:
        """Historia godzinowa z Archive API (reanalysis / wybrany model)."""
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()
        chunks = []
        cur = start
        model_label = self.model or DEFAULT_OPENMETEO_MODEL
        while cur <= end:
            chunk_end = min(cur + timedelta(days=chunk_days - 1), end)
            params = self._with_model({
                'latitude': self.latitude,
                'longitude': self.longitude,
                'start_date': cur.isoformat(),
                'end_date': chunk_end.isoformat(),
                'hourly': ','.join(HOURLY_VARS),
                'timezone': TIMEZONE,
            })
            payload = _get_json(ARCHIVE_URL, params)
            if payload.get('error'):
                raise RuntimeError(
                    f'Open-Meteo archive error ({model_label}): '
                    f'{payload.get("reason") or payload}'
                )
            part = _response_to_df(payload, self.location_label, 'OpenMeteo-archive')
            if not part.empty:
                chunks.append(part)
            logger.info(
                'Pobrano archiwum %s – %s (%d h, model=%s)',
                cur, chunk_end, len(part), model_label,
            )
            cur = chunk_end + timedelta(days=1)

        if not chunks:
            return pd.DataFrame()
        return pd.concat(chunks, ignore_index=True)

    def fetch_forecast(self, forecast_days: int = 3) -> pd.DataFrame:
        """Prognoza godzinowa (domyślnie 3 dni)."""
        params = self._with_model({
            'latitude': self.latitude,
            'longitude': self.longitude,
            'hourly': ','.join(HOURLY_VARS),
            'timezone': TIMEZONE,
            'forecast_days': forecast_days,
        })
        payload = _get_json(FORECAST_URL, params)
        if payload.get('error'):
            raise RuntimeError(
                f'Open-Meteo forecast error ({self.model or DEFAULT_OPENMETEO_MODEL}): '
                f'{payload.get("reason") or payload}'
            )
        return _response_to_df(payload, self.location_label, 'OpenMeteo-forecast')


def _ensure_weather_columns(conn: sqlite3.Connection) -> None:
    existing = {row[1] for row in conn.execute('PRAGMA table_info(weather_data)')}
    for col, col_type in WEATHER_EXTRA_COLUMNS.items():
        if col not in existing:
            conn.execute(f'ALTER TABLE weather_data ADD COLUMN {col} {col_type}')


def filter_forecast_preserve_archive(
    df: pd.DataFrame,
    as_of: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Usuń z prognozy godziny dzisiejsze już minione — nie nadpisuj archiwum w bazie."""
    if df.empty:
        return df
    as_of = pd.Timestamp(as_of or pd.Timestamp.now())
    ts = pd.to_datetime(df['timestamp'])
    today = as_of.normalize()
    keep = ~((ts.dt.normalize() == today) & (ts.dt.hour < as_of.hour))
    return df.loc[keep].copy()


def _ensure_weather_unique_per_source(conn: sqlite3.Connection) -> None:
    """Migracja: UNIQUE(timestamp, location) → UNIQUE(timestamp, location, data_source)."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='weather_data'"
    ).fetchone()
    if not row:
        return
    sql = row[0] or ''
    if 'UNIQUE(timestamp, location, data_source)' in sql:
        return
    if 'UNIQUE(timestamp, location)' not in sql:
        return

    conn.execute('ALTER TABLE weather_data RENAME TO weather_data_legacy')
    conn.execute('''
        CREATE TABLE weather_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME NOT NULL,
            temperature_celsius REAL,
            humidity_percent REAL,
            pressure_hpa REAL,
            solar_radiation_wm2 REAL,
            sunshine_duration_min REAL,
            cloud_cover_percent REAL,
            cloud_cover_low_percent REAL,
            cloud_cover_mid_percent REAL,
            cloud_cover_high_percent REAL,
            visibility_m REAL,
            wind_speed_ms REAL,
            wind_direction_deg REAL,
            precipitation_mm REAL,
            snowfall_cm REAL,
            snow_depth_m REAL,
            location VARCHAR(100),
            data_source VARCHAR(50),
            UNIQUE(timestamp, location, data_source)
        )
    ''')
    conn.execute('''
        INSERT OR IGNORE INTO weather_data (
            id, timestamp, temperature_celsius, humidity_percent, pressure_hpa,
            solar_radiation_wm2, sunshine_duration_min, cloud_cover_percent,
            cloud_cover_low_percent, cloud_cover_mid_percent, cloud_cover_high_percent,
            visibility_m, wind_speed_ms, wind_direction_deg, precipitation_mm,
            snowfall_cm, snow_depth_m, location, data_source
        )
        SELECT
            id, timestamp, temperature_celsius, humidity_percent, pressure_hpa,
            solar_radiation_wm2, sunshine_duration_min, cloud_cover_percent,
            cloud_cover_low_percent, cloud_cover_mid_percent, cloud_cover_high_percent,
            visibility_m, wind_speed_ms, wind_direction_deg, precipitation_mm,
            snowfall_cm, snow_depth_m, location, data_source
        FROM weather_data_legacy
    ''')
    conn.execute('DROP TABLE weather_data_legacy')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_weather_timestamp ON weather_data(timestamp)')
    conn.commit()


def save_weather_to_db(
    df: pd.DataFrame,
    db_path: str = 'data/energy_model.db',
) -> int:
    """Zapisuje lub aktualizuje rekordy w weather_data. Zwraca liczbę wierszy."""
    if df.empty:
        return 0

    conn = sqlite3.connect(db_path)
    _ensure_weather_columns(conn)
    _ensure_weather_unique_per_source(conn)
    rows = 0
    for _, r in df.iterrows():
        conn.execute(
            '''
            INSERT OR REPLACE INTO weather_data (
                timestamp, temperature_celsius, humidity_percent, pressure_hpa,
                solar_radiation_wm2, sunshine_duration_min, cloud_cover_percent,
                cloud_cover_low_percent, cloud_cover_mid_percent, cloud_cover_high_percent,
                visibility_m,
                wind_speed_ms, wind_direction_deg, precipitation_mm,
                snowfall_cm, snow_depth_m,
                location, data_source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                r['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                r.get('temperature_celsius'),
                r.get('humidity_percent'),
                r.get('pressure_hpa'),
                r.get('solar_radiation_wm2'),
                r.get('sunshine_duration_min'),
                r.get('cloud_cover_percent'),
                r.get('cloud_cover_low_percent'),
                r.get('cloud_cover_mid_percent'),
                r.get('cloud_cover_high_percent'),
                r.get('visibility_m'),
                r.get('wind_speed_ms'),
                r.get('wind_direction_deg'),
                r.get('precipitation_mm'),
                r.get('snowfall_cm'),
                r.get('snow_depth_m'),
                r['location'],
                r['data_source'],
            ),
        )
        rows += 1
    conn.commit()
    conn.close()
    return rows


def load_daily_weather(
    db_path: str,
    start_date: str,
    end_date: str,
    location: Optional[str] = None,
    use_dynamic_hours: bool = True,  # NOWE: domyślnie dynamiczne godziny
    latitude: float = 50.06,
    longitude: float = 19.94,
) -> pd.DataFrame:
    """Agregacja dzienna z weather_data.
    
    Args:
        use_dynamic_hours: Jeśli True, agreguje humidity/radiation na podstawie wschodu/zachodu słońca
                          Jeśli False, używa sztywnych godzin 9-16h (backward compatibility)
        latitude, longitude: Współrzędne dla dynamicznych godzin wschodu/zachodu
    """
    if not use_dynamic_hours:
        # Stara wersja ze sztywnymi godzinami 9-16h (backward compatibility)
        return _load_daily_weather_fixed_hours(db_path, start_date, end_date, location)
    
    # Nowa wersja z dynamicznymi godzinami
    try:
        from src.features.pv_features_hourly_extended import get_sunrise_sunset
        return _load_daily_weather_dynamic(db_path, start_date, end_date, location, latitude, longitude)
    except Exception as e:
        print(f'⚠️  Nie udało się użyć dynamicznych godzin dla mgły: {e}')
        print('   Fallback do sztywnych godzin 9-16h')
        return _load_daily_weather_fixed_hours(db_path, start_date, end_date, location)


def _load_daily_weather_fixed_hours(
    db_path: str,
    start_date: str,
    end_date: str,
    location: Optional[str] = None,
) -> pd.DataFrame:
    """Agregacja dzienna z SZTYWNYMI godzinami 9-16h (legacy, backward compatibility)."""
    conn = sqlite3.connect(db_path)
    query = '''
        SELECT
            date(timestamp) AS day,
            AVG(cloud_cover_percent) AS cloud_cover_avg,
            AVG(cloud_cover_low_percent) AS cloud_cover_low_avg,
            AVG(humidity_percent) AS humidity_avg,
            AVG(CASE
                WHEN cast(strftime('%H', timestamp) AS integer) BETWEEN 9 AND 16
                THEN humidity_percent
            END) AS humidity_daytime_avg,
            MIN(CASE WHEN visibility_m IS NOT NULL THEN visibility_m END) AS visibility_min_m,
            SUM(COALESCE(solar_radiation_wm2, 0)) AS radiation_wh_m2,
            SUM(CASE
                WHEN cast(strftime('%H', timestamp) AS integer) BETWEEN 9 AND 16
                THEN COALESCE(solar_radiation_wm2, 0)
            ELSE 0 END) AS radiation_daytime_wh_m2,
            SUM(COALESCE(precipitation_mm, 0)) AS precip_mm,
            SUM(COALESCE(snowfall_cm, 0)) AS snowfall_cm_sum,
            MAX(snow_depth_m) AS snow_depth_m_max,
            AVG(temperature_celsius) AS temp_avg,
            MIN(temperature_celsius) AS temp_min,
            MAX(temperature_celsius) AS temp_max
        FROM weather_data
        WHERE date(timestamp) BETWEEN ? AND ?
          AND data_source LIKE 'OpenMeteo%'
    '''
    params: list = [start_date, end_date]
    if location:
        query += ' AND location = ?'
        params.append(location)
    query += ' GROUP BY day ORDER BY day'
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    if not df.empty:
        df['radiation_kwh_m2'] = df['radiation_wh_m2'] / 1000.0
        df['radiation_daytime_kwh_m2'] = df['radiation_daytime_wh_m2'] / 1000.0
    return df


def _daylight_hour_bounds(
    latitude: float,
    longitude: float,
    day: str,
    *,
    fallback: tuple[int, int] = (9, 16),
) -> tuple[int, int]:
    """Godziny dzienne (wschód–zachód) jako zakres całkowity do agregacji godzinowej."""
    try:
        from src.features.pv_features_hourly_extended import get_sunrise_sunset

        sunrise, sunset = get_sunrise_sunset(latitude, longitude, day)
        hour_start = max(5, int(sunrise.hour))
        hour_end = min(21, int(sunset.hour) + 1)
        return hour_start, hour_end
    except Exception:
        return fallback


def _load_daily_weather_dynamic(
    db_path: str,
    start_date: str,
    end_date: str,
    location: Optional[str] = None,
    latitude: float = 50.06,
    longitude: float = 19.94,
) -> pd.DataFrame:
    """Agregacja dzienna z DYNAMICZNYMI godzinami wschodu/zachodu słońca.
    
    Wczytuje dane godzinowe i agreguje na podstawie rzeczywistych godzin produkcji.
    """
    conn = sqlite3.connect(db_path)
    
    # Wczytaj dane godzinowe (szerszy zakres 5-21h)
    query = '''
        SELECT
            date(timestamp) AS day,
            cast(strftime('%H', timestamp) AS integer) AS hour,
            cloud_cover_percent,
            cloud_cover_low_percent,
            humidity_percent,
            visibility_m,
            solar_radiation_wm2,
            precipitation_mm,
            snowfall_cm,
            snow_depth_m,
            temperature_celsius
        FROM weather_data
        WHERE date(timestamp) BETWEEN ? AND ?
          AND data_source LIKE 'OpenMeteo%'
          AND cast(strftime('%H', timestamp) AS integer) BETWEEN 5 AND 21
    '''
    params = [start_date, end_date]
    if location:
        query += ' AND location = ?'
        params.append(location)
    query += ' ORDER BY timestamp'
    
    hourly = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    if hourly.empty:
        return pd.DataFrame()
    
    # Oblicz wschód/zachód dla każdego dnia
    days = hourly['day'].unique()
    day_sun_times = {}
    
    for day in days:
        day_sun_times[day] = _daylight_hour_bounds(latitude, longitude, day)
    
    # Dodaj kolumnę is_daytime
    def is_daytime_hour(row):
        day = row['day']
        hour = row['hour']
        if day in day_sun_times:
            start, end = day_sun_times[day]
            return (hour >= start) and (hour <= end)
        return (hour >= 9) and (hour <= 16)
    
    hourly['is_daytime'] = hourly.apply(is_daytime_hour, axis=1)
    
    # Agreguj dziennie
    daily_rows = []
    for day, group in hourly.groupby('day'):
        daytime = group[group['is_daytime']]
        
        row = {
            'day': day,
            'cloud_cover_avg': group['cloud_cover_percent'].mean(),
            'cloud_cover_low_avg': group['cloud_cover_low_percent'].mean(),
            'humidity_avg': group['humidity_percent'].mean(),
            'humidity_daytime_avg': daytime['humidity_percent'].mean() if not daytime.empty else group['humidity_percent'].mean(),
            'visibility_min_m': group['visibility_m'].min() if group['visibility_m'].notna().any() else None,
            'radiation_wh_m2': group['solar_radiation_wm2'].fillna(0).sum(),
            'radiation_daytime_wh_m2': daytime['solar_radiation_wm2'].fillna(0).sum() if not daytime.empty else 0,
            'precip_mm': group['precipitation_mm'].fillna(0).sum(),
            'snowfall_cm_sum': group['snowfall_cm'].fillna(0).sum(),
            'snow_depth_m_max': group['snow_depth_m'].max() if group['snow_depth_m'].notna().any() else None,
            'temp_avg': group['temperature_celsius'].mean(),
            'temp_min': group['temperature_celsius'].min(),
            'temp_max': group['temperature_celsius'].max(),
        }
        daily_rows.append(row)
    
    df = pd.DataFrame(daily_rows)
    
    if not df.empty:
        df['radiation_kwh_m2'] = df['radiation_wh_m2'] / 1000.0
        df['radiation_daytime_kwh_m2'] = df['radiation_daytime_wh_m2'] / 1000.0
    
    return df


def flag_likely_fog_days(
    weather: pd.DataFrame,
    pv_daytime: pd.DataFrame,
    *,
    humidity_min: float = 85.0,
    radiation_daytime_min: float = 0.35,
    yield_ratio_of_ref_max: float = 0.25,
    visibility_fog_m: float = 2000.0,
    precip_max_mm: float = 1.0,
) -> pd.DataFrame:
    """Heurystyka „dzień mgłowy”: wysoka wilgotność + model zawyża radiację vs PV w godzinach dziennych.

    Zwraca weather z kolumnami: pv_kwh_daytime, yield_kwh_per_kwh_m2, likely_fog_day.
    """
    df = weather.merge(pv_daytime[['day', 'pv_kwh_daytime']], on='day', how='inner')
    if df.empty:
        return df

    rad = df['radiation_daytime_kwh_m2'].clip(lower=0.05)
    df['yield_kwh_per_kwh_m2'] = df['pv_kwh_daytime'] / rad

    clear = df[
        (df['cloud_cover_avg'] < 50)
        & (df['radiation_daytime_kwh_m2'] > 0.5)
        & (df['pv_kwh_daytime'] > 4)
    ]
    ref_yield = (
        clear['yield_kwh_per_kwh_m2'].median()
        if len(clear) >= 5
        else df['yield_kwh_per_kwh_m2'].quantile(0.70)
    )
    df['ref_yield_kwh_per_kwh_m2'] = ref_yield

    humid = df['humidity_daytime_avg'].fillna(df['humidity_avg'])
    low_yield = df['yield_kwh_per_kwh_m2'] < (ref_yield * yield_ratio_of_ref_max)
    sunny_model = df['radiation_daytime_kwh_m2'] >= radiation_daytime_min
    high_humidity = humid >= humidity_min
    low_visibility = df['visibility_min_m'].notna() & (df['visibility_min_m'] < visibility_fog_m)
    
    # NOWE: Wykluczamy dni z dużymi opadami (deszcz vs mgła)
    # Próg 1.0 mm: wyklucza deszcz, dopuszcza lekką mżawkę (często z mgłą)
    precip = df['precip_mm'].fillna(0)
    low_precipitation = precip <= precip_max_mm

    df['likely_fog_day'] = sunny_model & low_yield & (high_humidity | low_visibility) & low_precipitation
    return df


def load_daily_pv(
    db_path: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """Dzienna suma PV z foxess_data [kWh].

    pv_kwh — surowa suma (FoxESS generationPower, może być ujemna przy imporcie + ładowaniu baterii).
    pv_kwh_solar — tylko dodatnie próbki ORAZ bez rozładowania baterii (realna produkcja ze słońca).
    pv_kwh_artifact — wartość bezwzględna ujemnych próbek (artefakt księgowy falownika).
    
    FILTR BATERII: battery_power_kw >= -0.1 (wykluczapv_kwh_solar produkcję przy rozładowaniu baterii)
    """
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(
        '''
        SELECT
            date(timestamp) AS day,
            ROUND(SUM(COALESCE(pv_energy_kwh, 0)), 3) AS pv_kwh,
            ROUND(SUM(CASE WHEN pv_energy_kwh > 0 AND COALESCE(battery_power_kw, 0) >= -0.1 
                THEN pv_energy_kwh ELSE 0 END), 3)
                AS pv_kwh_solar,
            ROUND(SUM(CASE WHEN pv_energy_kwh < 0 THEN -pv_energy_kwh ELSE 0 END), 3)
                AS pv_kwh_artifact
        FROM foxess_data
        WHERE date(timestamp) BETWEEN ? AND ?
        GROUP BY day
        ORDER BY day
        ''',
        conn,
        params=(start_date, end_date),
    )
    conn.close()
    return df


def load_daily_pv_daytime(
    db_path: str,
    start_date: str,
    end_date: str,
    hour_start: int = 9,
    hour_end: int = 16,
    use_dynamic_hours: bool = True,
    latitude: float = 50.06,
    longitude: float = 19.94,
) -> pd.DataFrame:
    """Dzienna suma dodatniego PV w godzinach dziennych.

    UWAGA:
    - use_dynamic_hours=True (domyślnie): wschód–zachód słońca dla każdego dnia
    - use_dynamic_hours=False: stałe hour_start/hour_end (legacy 9–16h)
      Rzeczywista produkcja zależy od długości dnia (5–20h latem, 7–15h zimą).

    FILTR BATERII: battery_power_kw >= -0.1 (wyklucza produkcję przy rozładowaniu baterii)
    """
    if not use_dynamic_hours:
        # Stara metoda: stałe godziny
        conn = sqlite3.connect(db_path)
        df = pd.read_sql_query(
            f'''
            SELECT
                date(timestamp) AS day,
                ROUND(SUM(CASE
                    WHEN pv_energy_kwh > 0
                     AND COALESCE(battery_power_kw, 0) >= -0.1
                     AND cast(strftime('%H', timestamp) AS integer) BETWEEN ? AND ?
                    THEN pv_energy_kwh ELSE 0
                END), 3) AS pv_kwh_daytime,
                ROUND(SUM(CASE
                    WHEN pv_energy_kwh > 0
                     AND COALESCE(battery_power_kw, 0) >= -0.1
                     AND (cast(strftime('%H', timestamp) AS integer) < 6
                          OR cast(strftime('%H', timestamp) AS integer) >= 20)
                    THEN pv_energy_kwh ELSE 0
                END), 3) AS pv_kwh_night_pos
            FROM foxess_data
            WHERE date(timestamp) BETWEEN ? AND ?
            GROUP BY day
            ORDER BY day
            ''',
            conn,
            params=(hour_start, hour_end, start_date, end_date),
        )
        conn.close()
        return df
    
    # Dynamiczne godziny (wschód–zachód słońca) — ta sama logika co load_daily_weather()
    conn = sqlite3.connect(db_path)
    df_hourly = pd.read_sql_query(
        '''
        SELECT
            date(timestamp) AS day,
            cast(strftime('%H', timestamp) AS integer) AS hour,
            pv_energy_kwh,
            COALESCE(battery_power_kw, 0) AS battery_power_kw
        FROM foxess_data
        WHERE date(timestamp) BETWEEN ? AND ?
        ORDER BY timestamp
        ''',
        conn,
        params=(start_date, end_date),
    )
    conn.close()

    all_days = pd.date_range(start_date, end_date, freq='D').strftime('%Y-%m-%d').tolist()
    if df_hourly.empty:
        return pd.DataFrame({
            'day': all_days,
            'pv_kwh_daytime': 0.0,
            'pv_kwh_night_pos': 0.0,
        })

    sunrise_sunset_map = {
        day: _daylight_hour_bounds(latitude, longitude, day, fallback=(hour_start, hour_end))
        for day in all_days
    }

    df_hourly['hour_start'] = df_hourly['day'].map(lambda d: sunrise_sunset_map[d][0])
    df_hourly['hour_end'] = df_hourly['day'].map(lambda d: sunrise_sunset_map[d][1])
    df_hourly['pv_valid'] = np.where(
        (df_hourly['pv_energy_kwh'] > 0) & (df_hourly['battery_power_kw'] >= -0.1),
        df_hourly['pv_energy_kwh'],
        0.0,
    )

    df_daytime = df_hourly[
        (df_hourly['hour'] >= df_hourly['hour_start']) &
        (df_hourly['hour'] <= df_hourly['hour_end'])
    ]
    daytime_sums = (
        df_daytime.groupby('day')['pv_valid']
        .sum()
        .reset_index(name='pv_kwh_daytime')
    )
    daytime_sums['pv_kwh_daytime'] = daytime_sums['pv_kwh_daytime'].round(3)

    df_night = df_hourly[
        (df_hourly['hour'] < df_hourly['hour_start']) |
        (df_hourly['hour'] > df_hourly['hour_end'])
    ]
    night_sums = (
        df_night.groupby('day')['pv_valid']
        .sum()
        .reset_index(name='pv_kwh_night_pos')
    )
    night_sums['pv_kwh_night_pos'] = night_sums['pv_kwh_night_pos'].round(3)

    result = pd.DataFrame({'day': all_days})
    result = result.merge(daytime_sums, on='day', how='left')
    result = result.merge(night_sums, on='day', how='left')
    result['pv_kwh_daytime'] = result['pv_kwh_daytime'].fillna(0.0)
    result['pv_kwh_night_pos'] = result['pv_kwh_night_pos'].fillna(0.0)

    return result


def predict_pv_day_class(
    row: pd.Series,
    *,
    ref_yield_kwh_per_kwh_m2: float,
    likely_fog: bool = False,
) -> str:
    """Regułowa klasa dnia wpływająca na PV (kalibrowana na obserwacjach foto).

    Priorytet: artifact → fog → snow_panel_block → snow_landscape → clear/partial → overcast.
    Nie używa % chmur z foto — radiacja + yield + kontekst śniegu.
    """
    artifact = float(row.get('pv_kwh_artifact') or 0)
    pv = float(row.get('pv_kwh_daytime') or 0)
    rad = float(row.get('radiation_daytime_kwh_m2') or row.get('radiation_kwh_m2') or 0)
    rad = max(rad, 0.05)
    # FoxESS potrafi importować w nocy — nie oznaczaj dnia jako artifact, jeśli PV dzienne jest sensowne.
    # UWAGA: pv_kwh_daytime to agregacja w godzinach wschód–zachód (dynamicznie)
    if artifact >= 10.0 and artifact > max(pv, 0.5) * 3.5 and pv < 3.5:
        return 'artifact'

    yield_ratio = pv / rad
    ref = max(ref_yield_kwh_per_kwh_m2, 0.5)
    yield_pct = yield_ratio / ref

    om_snow = float(row.get('om_snowfall_cm') or row.get('snowfall_cm_sum') or 0)
    om_depth = float(row.get('om_snow_depth_cm') or 0)
    if om_depth <= 1.5 and row.get('snow_depth_m_max') is not None:
        om_depth = float(row.get('snow_depth_m_max') or 0) * 100
    imgw = row.get('imgw_snow_depth_cm')
    imgw_depth = float(imgw) if pd.notna(imgw) else 0.0
    snow_depth = max(om_depth, imgw_depth)
    has_snow = snow_depth >= 3 or om_snow >= 1.0
    snow_in_region = om_depth >= 6 or imgw_depth >= 5 or snow_depth >= 10

    sunny_enough = rad >= 0.45
    low_yield = yield_pct < 0.35 or pv < 2.0

    if sunny_enough and low_yield and (
        (has_snow and pv < 2.0) or (pv < 1.0 and rad >= 0.5)
    ):
        return 'snow_panel_block'

    if likely_fog:
        return 'fog'

    # Zimowy szczyt produkcji — przed regułami śniegu (3 II).
    if pv >= 14.0 and rad >= 1.6 and yield_pct >= 0.95:
        return 'clear_sunny'

    if snow_in_region and pv >= 4.0 and yield_pct >= 0.35:
        return 'snow_landscape'

    if has_snow and pv >= 4.0 and rad >= 1.4:
        return 'snow_landscape'

    # Typ B: dobry yield mimo śniegu w API (26 I, 1 II).
    if has_snow and yield_pct >= 0.70 and (snow_in_region or rad >= 1.4):
        return 'snow_landscape'

    if has_snow and yield_pct >= 0.95 and pv >= 8.0:
        return 'snow_landscape'

    if pv >= 8.0 and rad >= 0.85:
        return 'clear_sunny'

    if pv >= 6.0 and rad >= 0.80:
        cloud = float(row.get('cloud_cover_avg') or 0)
        if cloud >= 70 and rad < 1.15 and pv < 9.0:
            return 'overcast_white'
        return 'partial_cloud'

    if rad < 0.55 and pv < 4.0:
        cloud = float(row.get('cloud_cover_avg') or 0)
        if cloud >= 85 and pv < 5.0:
            return 'overcast_white'
        return 'overcast_heavy'

    cloud = float(row.get('cloud_cover_avg') or 0)
    if rad < 1.05 and pv < 8.0 and cloud >= 65:
        return 'overcast_white'

    if not has_snow and pv >= 2.0:
        return 'no_snow'

    return 'unknown'


def forecast_pv_day_class(
    row: pd.Series,
    *,
    pv_proxy_kwh: float,
    ref_yield_kwh_per_kwh_m2: float,
    likely_fog: bool = False,
) -> str:
    """Klasa dnia do korekty prognozy ML — bez rzeczywistej PV (używa pv_proxy, np. pred RF)."""
    rad = float(row.get('radiation_daytime_kwh_m2') or row.get('radiation_kwh_m2') or 0)
    rad = max(rad, 0.05)
    pv = max(float(pv_proxy_kwh), 0.0)
    ref = max(ref_yield_kwh_per_kwh_m2, 0.5)
    yield_pct = (pv / rad) / ref

    om_snow = float(row.get('om_snowfall_cm') or row.get('snowfall_cm_sum') or 0)
    om_depth = float(row.get('om_snow_depth_cm') or 0)
    if om_depth <= 1.5 and row.get('snow_depth_m_max') is not None:
        om_depth = float(row.get('snow_depth_m_max') or 0) * 100
    imgw = row.get('imgw_snow_depth_cm')
    imgw_depth = float(imgw) if pd.notna(imgw) else 0.0
    snow_depth = max(om_depth, imgw_depth)
    has_snow = snow_depth >= 3 or om_snow >= 1.0
    snow_in_region = om_depth >= 6 or imgw_depth >= 5 or snow_depth >= 10

    sunny_enough = rad >= 0.45

    if likely_fog:
        return 'fog'

    if snow_in_region and rad >= 0.55 and pv >= 2.5:
        return 'snow_landscape'

    if has_snow and pv >= 4.0 and rad >= 1.4:
        return 'snow_landscape'

    if has_snow and yield_pct >= 0.70 and (snow_in_region or rad >= 1.4):
        return 'snow_landscape'

    if has_snow and yield_pct >= 0.95 and pv >= 7.0:
        return 'snow_landscape'

    # RF zaniżony przez śnieg w cechach — podbij w korekcie (Typ B w prognozie).
    if has_snow and rad >= 0.45 and pv < 0.72 * rad * ref:
        return 'snow_landscape'

    if pv >= 12.0 and rad >= 1.6 and yield_pct >= 0.85:
        return 'clear_sunny'

    if sunny_enough and has_snow and pv < 2.5 and yield_pct < 0.22:
        return 'snow_panel_block'

    if pv >= 7.0 and rad >= 0.85:
        return 'clear_sunny'

    if pv >= 5.0 and rad >= 0.75:
        cloud = float(row.get('cloud_cover_avg') or 0)
        if cloud >= 70 and rad < 1.15 and pv < 9.0:
            return 'overcast_white'
        return 'partial_cloud'

    if rad < 0.55 and pv < 4.0:
        cloud = float(row.get('cloud_cover_avg') or 0)
        if cloud >= 85 and pv < 5.0:
            return 'overcast_white'
        return 'overcast_heavy'

    cloud = float(row.get('cloud_cover_avg') or 0)
    if rad < 1.05 and pv < 8.0 and cloud >= 65:
        return 'overcast_white'

    if not has_snow and pv >= 2.0:
        return 'no_snow'

    return 'unknown'


def likely_fog_forecast(
    row: pd.Series,
    pv_proxy_kwh: float,
    *,
    ref_yield_kwh_per_kwh_m2: float,
    humidity_min: float = 85.0,
    radiation_daytime_min: float = 0.35,
    yield_ratio_of_ref_max: float = 0.30,
) -> bool:
    """Mgła w trybie prognozy — wilgotność + niski yield liczony z pv_proxy."""
    rad = float(row.get('radiation_daytime_kwh_m2') or 0)
    if rad < radiation_daytime_min:
        return False
    humid = row.get('humidity_daytime_avg')
    if humid is None or pd.isna(humid):
        humid = row.get('humidity_avg')
    humid = float(humid or 0)
    ref = max(ref_yield_kwh_per_kwh_m2, 0.5)
    yield_ratio = max(float(pv_proxy_kwh), 0.0) / max(rad, 0.05)
    low_yield = yield_ratio < ref * yield_ratio_of_ref_max
    return humid >= humidity_min and low_yield


def apply_pv_rule_correction(
    y_pred: np.ndarray,
    rows: pd.DataFrame,
    *,
    ref_yield_kwh_per_kwh_m2: float,
    correction_factors: dict[str, float],
) -> np.ndarray:
    """Korekta predykcji ML regułami pogodowymi (Typ A/B, mgła, pochmurność)."""
    corrected = np.zeros(len(y_pred), dtype=float)
    ref_raw = ref_yield_kwh_per_kwh_m2
    ref = float(ref_raw) if pd.notna(ref_raw) and ref_raw > 0 else 0.5
    ref = max(ref, 0.5)

    for i, (_, row) in enumerate(rows.iterrows()):
        rf = max(float(y_pred[i]), 0.0)
        rad = max(float(row.get('radiation_daytime_kwh_m2') or 0), 0.05)
        rad_baseline = rad * ref
        fog = likely_fog_forecast(row, rf, ref_yield_kwh_per_kwh_m2=ref)
        cls = forecast_pv_day_class(
            row,
            pv_proxy_kwh=rf,
            ref_yield_kwh_per_kwh_m2=ref,
            likely_fog=fog,
        )
        factor = correction_factors.get(cls, 1.0)

        if cls == 'snow_landscape':
            corrected[i] = max(rf * factor, 0.88 * rad_baseline)
        elif cls == 'snow_panel_block':
            corrected[i] = min(rf, rad_baseline * factor)
        elif cls == 'fog':
            corrected[i] = rf * factor
        elif cls in ('clear_sunny', 'partial_cloud') and rf < 0.72 * rad_baseline:
            corrected[i] = 0.45 * rf + 0.55 * rad_baseline
        else:
            corrected[i] = max(0.0, rf * factor)

    return corrected


def winter_reference_yield(
    weather: pd.DataFrame,
    pv_daytime: pd.DataFrame,
    pv: pd.DataFrame,
) -> float:
    """Mediana yield z jasnych zimowych dni referencyjnych.
    
    UWAGA: Używa pv_kwh_daytime (agregacja historyczna 9-16h)."""
    df = weather.merge(pv_daytime, on='day').merge(pv, on='day')
    winter = df[df['day'].str[5:7].isin({'12', '01', '02'})]
    ref = winter[
        (winter['cloud_cover_avg'] < 40)
        & (winter['radiation_daytime_kwh_m2'] > 0.7)
        & (winter['pv_kwh_daytime'] > 6)
        & (winter['pv_kwh_artifact'] < 5)
    ]
    if ref.empty:
        rad = winter['radiation_daytime_kwh_m2'].clip(lower=0.05)
        return float((winter['pv_kwh_daytime'] / rad).median())
    rad = ref['radiation_daytime_kwh_m2'].clip(lower=0.05)
    return float((ref['pv_kwh_daytime'] / rad).median())


def get_icon_forecast(
    latitude: float | None = None,
    longitude: float | None = None,
    forecast_days: int = 3,
) -> pd.DataFrame:
    """Pobiera prognozę ICON z Open-Meteo (wrapper dla ensemble).
    
    Args:
        latitude: szerokość geograficzna (domyślnie z .env)
        longitude: długość geograficzna (domyślnie z .env)
        forecast_days: liczba dni prognozy (domyślnie 3)
    
    Returns:
        DataFrame z kolumnami: timestamp, cloud_cover_percent, solar_radiation_wm2, 
        temperature_celsius, humidity_percent, itd.
    """
    if latitude is None or longitude is None:
        client = OpenMeteoClient.from_env()
        if latitude is not None:
            client.latitude = latitude
        if longitude is not None:
            client.longitude = longitude
        client.model = 'icon_seamless'
    else:
        client = OpenMeteoClient(latitude, longitude, model='icon_seamless')
    
    return client.fetch_forecast(forecast_days=forecast_days)


def get_ukmo_forecast(
    latitude: float | None = None,
    longitude: float | None = None,
    forecast_days: int = 3,
) -> pd.DataFrame:
    """Pobiera prognozę UKMO z Open-Meteo (wrapper dla ensemble).
    
    Args:
        latitude: szerokość geograficzna (domyślnie z .env)
        longitude: długość geograficzna (domyślnie z .env)
        forecast_days: liczba dni prognozy (domyślnie 3)
    
    Returns:
        DataFrame z kolumnami: timestamp, cloud_cover_percent, solar_radiation_wm2, 
        temperature_celsius, humidity_percent, itd.
    """
    if latitude is None or longitude is None:
        client = OpenMeteoClient.from_env()
        if latitude is not None:
            client.latitude = latitude
        if longitude is not None:
            client.longitude = longitude
        client.model = 'ukmo_seamless'
    else:
        client = OpenMeteoClient(latitude, longitude, model='ukmo_seamless')
    
    return client.fetch_forecast(forecast_days=forecast_days)


def get_ensemble_forecast(
    latitude: float | None = None,
    longitude: float | None = None,
    forecast_days: int = 3,
    models: list[str] | None = None,
) -> pd.DataFrame:
    """Pobiera ensemble prognozę (ICON+UKMO) — uśrednia modele.
    
    Args:
        latitude: szerokość geograficzna (domyślnie z .env)
        longitude: długość geograficzna (domyślnie z .env)
        forecast_days: liczba dni prognozy (domyślnie 3)
        models: lista modeli do ensemble (domyślnie ['icon_seamless', 'ukmo_seamless'])
    
    Returns:
        DataFrame z uśrednionymi wartościami cloud_cover_percent, solar_radiation_wm2, itd.
    """
    if models is None:
        models = ['icon_seamless', 'ukmo_seamless']
    
    if not models:
        raise ValueError('models musi zawierać co najmniej jeden model')
    
    # Pobierz prognozy z wszystkich modeli
    forecasts = []
    for model in models:
        if latitude is None or longitude is None:
            client = OpenMeteoClient.from_env()
            if latitude is not None:
                client.latitude = latitude
            if longitude is not None:
                client.longitude = longitude
            client.model = model
        else:
            client = OpenMeteoClient(latitude, longitude, model=model)
        
        df = client.fetch_forecast(forecast_days=forecast_days)
        forecasts.append(df)
    
    # Uśrednij wartości numeryczne (timestamp + location + data_source = metadata)
    ensemble = forecasts[0].copy()
    numeric_cols = [
        'temperature_celsius',
        'humidity_percent',
        'cloud_cover_percent',
        'cloud_cover_low_percent',
        'cloud_cover_mid_percent',
        'cloud_cover_high_percent',
        'visibility_m',
        'precipitation_mm',
        'snowfall_cm',
        'snow_depth_m',
        'solar_radiation_wm2',
        'wind_speed_ms',
        'wind_direction_deg',
    ]
    
    for col in numeric_cols:
        if col in ensemble.columns:
            # Uśrednij wartości z wszystkich modeli (ignoruj NaN/None)
            arrays = []
            for df in forecasts:
                if col in df.columns:
                    # Zamień None na NaN
                    arr = pd.to_numeric(df[col], errors='coerce').values
                    arrays.append(arr)
            
            if arrays:
                values = np.stack(arrays)
                ensemble[col] = np.nanmean(values, axis=0)
    
    # Oznacz jako ensemble
    ensemble['data_source'] = f'OpenMeteo-forecast-ensemble-{"+".join(models)}'
    
    return ensemble
