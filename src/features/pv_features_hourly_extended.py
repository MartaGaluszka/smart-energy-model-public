"""
Ulepszone cechy godzinowe PV - z dynamicznymi godzinami produkcji.

Uwzględnia:
- Wschód i zachód słońca (zmienia się z porą roku)
- Faktyczne godziny produkcji (nie sztywne 9-16h)
- Cechy temporalne: czas od wschodu, czas do zachodu
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytz
from astral import LocationInfo
from astral.sun import sun


def get_sunrise_sunset(
    latitude: float,
    longitude: float,
    date: str,
    timezone_str: str = 'Europe/Warsaw'
) -> tuple[datetime, datetime]:
    """Oblicz wschód i zachód słońca dla danej lokalizacji i daty (lokalny czas).
    
    Args:
        latitude: Szerokość geograficzna
        longitude: Długość geograficzna  
        date: Data w formacie YYYY-MM-DD
        timezone_str: Strefa czasowa (domyślnie: Europe/Warsaw dla Polski)
        
    Returns:
        (sunrise, sunset) jako datetime objects W LOKALNYM CZASIE
    """
    location = LocationInfo(latitude=latitude, longitude=longitude, timezone=timezone_str)
    date_obj = datetime.fromisoformat(date)
    tz = pytz.timezone(timezone_str)
    
    # WAŻNE: Użyj tzinfo aby dostać lokalny czas (CEST/CET), nie UTC!
    s = sun(location.observer, date=date_obj, tzinfo=tz)
    
    return s['sunrise'], s['sunset']


def calculate_sun_features(
    df: pd.DataFrame,
    latitude: float = 50.06,  # Default: okolica instalacji (przybliżone)
    longitude: float = 19.94,
) -> pd.DataFrame:
    """Dodaj cechy związane ze słońcem (wschód, zachód, długość dnia).
    
    Args:
        df: DataFrame z kolumną 'day' i 'hour'
        latitude: Szerokość geograficzna instalacji PV
        longitude: Długość geograficzna instalacji PV
        
    Returns:
        DataFrame z dodatkowymi kolumnami:
        - sunrise_hour: Godzina wschodu słońca
        - sunset_hour: Godzina zachodu słońca
        - day_length_hours: Długość dnia w godzinach
        - hours_since_sunrise: Godziny od wschodu
        - hours_until_sunset: Godziny do zachodu
        - is_daylight: Czy jest dzień (między wschodem a zachodem)
    """
    df = df.copy()
    
    # Cache dla dat (aby nie liczyć wielokrotnie dla tego samego dnia)
    sun_cache = {}
    
    def get_sun_for_day(day_str):
        if day_str not in sun_cache:
            sunrise, sunset = get_sunrise_sunset(latitude, longitude, day_str)
            sun_cache[day_str] = {
                'sunrise_hour': sunrise.hour + sunrise.minute / 60.0,
                'sunset_hour': sunset.hour + sunset.minute / 60.0,
            }
        return sun_cache[day_str]
    
    # Oblicz dla każdego wiersza
    sun_data = df['day'].apply(get_sun_for_day)
    df['sunrise_hour'] = sun_data.apply(lambda x: x['sunrise_hour'])
    df['sunset_hour'] = sun_data.apply(lambda x: x['sunset_hour'])
    df['day_length_hours'] = df['sunset_hour'] - df['sunrise_hour']
    
    # Cechy względem godziny
    df['hours_since_sunrise'] = df['hour'] - df['sunrise_hour']
    df['hours_until_sunset'] = df['sunset_hour'] - df['hour']
    df['is_daylight'] = ((df['hour'] >= df['sunrise_hour']) & 
                          (df['hour'] <= df['sunset_hour'])).astype(int)
    
    # Znormalizowana pozycja w dniu (0 = wschód, 1 = zachód)
    df['sun_position'] = np.clip(
        df['hours_since_sunrise'] / df['day_length_hours'],
        0, 1
    )
    
    return df


PVE_COUNTER_VARIABLE = 'PVEnergyTotal'
# Dodatnie skoki licznika powyżej progu uznajemy za artefakt (luka / sync), nie produkcję
_PVE_DELTA_SPIKE_KWH = 30.0


def _hourly_target_mode() -> str:
    """pve/app = ΔPVEnergyTotal (ta sama zmienna co w aplikacji); pvpower = ∫pvPower."""
    raw = (
        os.getenv('PV_HOURLY_TARGET')
        or os.getenv('PV_HOURLY_TARGET_SCALE')
        or 'pve'
    )
    raw = (raw or 'pve').strip().lower()
    if raw in ('pvpower', 'pv_power', 'power', 'raw'):
        return 'pvpower'
    # app / pve / pvenergytotal — aliasy tej samej zmiennej
    return 'pve'


def load_hourly_pv_from_pve(
    db_path: str,
    start_date: str,
    end_date: str,
    min_hour: int = 5,
    max_hour: int = 21,
    *,
    variable: str = PVE_COUNTER_VARIABLE,
) -> pd.DataFrame:
    """Godzinowa produkcja z licznika ``PVEnergyTotal`` (dodatnie delty próbek).

    To ta sama zmienna co w aplikacji FoxESS / closeout — bez skalowania pvPower.
    """
    conn = sqlite3.connect(db_path)
    try:
        # Delty tylko w obrębie dnia (PARTITION BY day) — nie przypisuj
        # skoku przez lukę sync z poprzedniego dnia do godziny 0 (25.07:
        # prev 24.07 16:00 → +3 kWh sztucznie w 00:00; max−min dnia = app).
        q = """
        WITH ordered AS (
            SELECT
                timestamp,
                DATE(timestamp) AS day,
                CAST(strftime('%H', timestamp) AS INTEGER) AS hour,
                value,
                LAG(value) OVER (
                    PARTITION BY DATE(timestamp) ORDER BY timestamp
                ) AS prev_value
            FROM foxess_timeseries
            WHERE variable = ?
              AND DATE(timestamp) >= ?
              AND DATE(timestamp) <= ?
        )
        SELECT
            day,
            hour,
            SUM(
                CASE
                    WHEN prev_value IS NULL THEN 0
                    WHEN (value - prev_value) > 0
                     AND (value - prev_value) < ?
                    THEN (value - prev_value)
                    ELSE 0
                END
            ) AS pv_kwh_hour
        FROM ordered
        WHERE hour BETWEEN ? AND ?
        GROUP BY day, hour
        HAVING pv_kwh_hour > 0.001
        ORDER BY day, hour
        """
        df = pd.read_sql_query(
            q,
            conn,
            params=(
                variable,
                start_date,
                end_date,
                _PVE_DELTA_SPIKE_KWH,
                min_hour,
                max_hour,
            ),
        )
    finally:
        conn.close()

    if df.empty:
        return df

    # Średnia moc w godzinie ≈ energia [kWh] przy oknie 1 h (do kompatybilności schematu)
    df['pv_power_avg_kw'] = df['pv_kwh_hour']
    n_days = df['day'].nunique()
    print(
        f'✓ Target godzinowy = {variable} (Δ licznika, jak w app): '
        f'{n_days} dni, {len(df)} godzin'
    )
    return df


def load_hourly_pv_dynamic(
    db_path: str,
    start_date: str,
    end_date: str,
    min_hour: int = 5,
    max_hour: int = 21,
    *,
    variable: str = 'pvPower',
    target_scale: str | None = None,
    target: str | None = None,
) -> pd.DataFrame:
    """Godzinowa produkcja PV do treningu / walidacji ML.

    Domyślnie (``PV_HOURLY_TARGET=pve``): delty licznika ``PVEnergyTotal`` —
    ta sama zmienna co w aplikacji FoxESS (bez skalowania innych odczytów).

    ``pvpower``: surowy ∫``pvPower`` (stary target, ~+10–15% vs app).

    Fallback przy ``pvpower``: ``pv1Power``+``pv2Power``, potem ``foxess_data``.
    """
    mode = (target or target_scale or _hourly_target_mode()).strip().lower()
    if mode in ('pve', 'app', 'pvenergytotal', 'pv_energy_total'):
        return load_hourly_pv_from_pve(
            db_path, start_date, end_date, min_hour=min_hour, max_hour=max_hour,
        )

    conn = sqlite3.connect(db_path)

    def _from_timeseries(var: str) -> pd.DataFrame:
        q = """
        SELECT
            DATE(timestamp) AS day,
            CAST(strftime('%H', timestamp) AS INTEGER) AS hour,
            SUM(CASE WHEN value > 0 THEN value ELSE 0 END) * 5.0 / 60.0 AS pv_kwh_hour,
            AVG(CASE WHEN value > 0 THEN value END) AS pv_power_avg_kw
        FROM foxess_timeseries
        WHERE variable = ?
          AND DATE(timestamp) >= ?
          AND DATE(timestamp) <= ?
          AND CAST(strftime('%H', timestamp) AS INTEGER) BETWEEN ? AND ?
        GROUP BY DATE(timestamp), hour
        HAVING pv_kwh_hour > 0.001
        ORDER BY day, hour
        """
        return pd.read_sql_query(q, conn, params=(var, start_date, end_date, min_hour, max_hour))

    df = _from_timeseries(variable)
    if df.empty and variable == 'pvPower':
        p1 = _from_timeseries('pv1Power').rename(columns={'pv_kwh_hour': 'p1', 'pv_power_avg_kw': 'p1kw'})
        p2 = _from_timeseries('pv2Power').rename(columns={'pv_kwh_hour': 'p2', 'pv_power_avg_kw': 'p2kw'})
        if not p1.empty or not p2.empty:
            merged = p1.merge(p2, on=['day', 'hour'], how='outer').fillna(0)
            df = pd.DataFrame({
                'day': merged['day'],
                'hour': merged['hour'],
                'pv_kwh_hour': merged['p1'] + merged['p2'],
                'pv_power_avg_kw': merged[['p1kw', 'p2kw']].mean(axis=1),
            })
            df = df[df['pv_kwh_hour'] > 0.001]

    if df.empty:
        query = f"""
        SELECT
            DATE(timestamp) AS day,
            CAST(strftime('%H', timestamp) AS INTEGER) AS hour,
            SUM(CASE WHEN pv_energy_kwh > 0 THEN pv_energy_kwh ELSE 0 END) AS pv_kwh_hour,
            AVG(CASE WHEN pv_power_kw > 0 THEN pv_power_kw END) AS pv_power_avg_kw
        FROM foxess_data
        WHERE DATE(timestamp) >= '{start_date}'
          AND DATE(timestamp) <= '{end_date}'
          AND hour BETWEEN {min_hour} AND {max_hour}
        GROUP BY DATE(timestamp), hour
        HAVING pv_kwh_hour > 0.001
        ORDER BY day, hour
        """
        df = pd.read_sql_query(query, conn)

    conn.close()
    return df


# Rozszerzone cechy (z dodanymi cechami słonecznymi)
HOURLY_FEATURE_COLUMNS_EXTENDED = [
    'hour',  # Godzina dnia
    'doy_sin', 'doy_cos',  # Dzień roku (cykliczny)
    'month',  # Miesiąc
    'temp_c',  # Temperatura
    'humidity_pct',  # Wilgotność
    'cloud_cover_pct',  # Zachmurzenie
    'radiation_wm2',  # Promieniowanie
    'wind_speed_ms',  # Wiatr
    # NOWE cechy słoneczne:
    'sunrise_hour',  # Godzina wschodu słońca
    'sunset_hour',  # Godzina zachodu słońca
    'day_length_hours',  # Długość dnia
    'hours_since_sunrise',  # Czas od wschodu
    'hours_until_sunset',  # Czas do zachodu
    'sun_position',  # Pozycja słońca (0-1)
    'is_daylight',  # Czy jest dzień
    # Flagi śniegu (z modelu topnienia):
    'snow_on_panels',  # Czy śnieg blokuje panele (ten dzień)
    'snow_on_panels_prev',  # Czy śnieg blokował panele (poprzedni dzień)
    # Flaga mgły (z kalibracji):
    'likely_fog_day',  # Czy dzień mgłowy (wilgotność + niska widoczność)
]

# Rekomendowany zestaw produkcyjny (ablacja 2026-07: bez doy_sin, doy_cos, month)
# CS4 (19 cech) = kandydat — gate ACCEPT 2026-07-26, ale produkcja zostaje przy 16
HOURLY_FEATURE_COLUMNS_PRODUCTION = [
    'hour',
    'temp_c', 'humidity_pct', 'cloud_cover_pct', 'radiation_wm2', 'wind_speed_ms',
    'sunrise_hour', 'sunset_hour', 'day_length_hours',
    'hours_since_sunrise', 'hours_until_sunset', 'sun_position', 'is_daylight',
    'snow_on_panels', 'snow_on_panels_prev', 'likely_fog_day',
]

# CS4 (kandydat): production + warstwy chmur + clearness — models/pv_hourly_model_cs4.joblib
HOURLY_FEATURE_COLUMNS_CS4 = HOURLY_FEATURE_COLUMNS_PRODUCTION + [
    'cloud_cover_low_pct',
    'cloud_cover_mid_pct',
    'clearness',
]

# Eksperyment (po tygodniu obserwacji): + geometria paneli — NIE w produkcji do ACCEPT
from src.features.panel_geometry import PANEL_GEOMETRY_COLUMNS  # noqa: E402

HOURLY_FEATURE_COLUMNS_WITH_PANEL = (
    HOURLY_FEATURE_COLUMNS_PRODUCTION + PANEL_GEOMETRY_COLUMNS
)

HOURLY_FEATURE_COLUMNS_CS4_WITH_PANEL = (
    HOURLY_FEATURE_COLUMNS_CS4 + PANEL_GEOMETRY_COLUMNS
)

# Godzinowy target: domyślnie ΔPVEnergyTotal (jak w app); opcjonalnie ∫pvPower
TARGET_COLUMN = 'pv_kwh_hour'

def load_hourly_training_frame_extended(
    db_path: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    location: str | None = None,
    latitude: float = 50.06,
    longitude: float = 19.94,
    use_snow_melt: bool = True,  # używaj modelu topnienia śniegu dla flag snow_on_panels
    use_fog_flags: bool = True,  # DODANO: używaj kalibracji mgły
) -> pd.DataFrame:
    """Wczytaj ramkę danych godzinowych z dynamicznymi godzinami i cechami słonecznymi.
    
    Args:
        use_snow_melt: Jeśli True, używa modelu topnienia śniegu dla flag snow_on_panels
        use_fog_flags: Jeśli True, używa kalibracji mgły dla flag likely_fog_day
    """
    
    from src.models.ml_train_window import resolve_ml_dates

    db_path = db_path or os.getenv('DATABASE_PATH', 'data/energy_model.db')
    if not os.path.isabs(db_path):
        _root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        candidate = os.path.join(_root, db_path)
        if os.path.exists(candidate) and os.path.getsize(candidate) > 1_000_000:
            db_path = candidate
        else:
            db_path = os.path.join(_root, 'data', 'energy_model.db')
    location = location if location is not None else os.getenv('WEATHER_LOCATION')
    start_date, end_date = resolve_ml_dates(start_date, end_date, db_path)
    
    # Wczytaj dane z szerszym zakresem godzin (5-21h)
    pv = load_hourly_pv_dynamic(db_path, start_date, end_date, min_hour=5, max_hour=21)
    
    # Pobierz pogodę dla wszystkich godzin (rozszerzone)
    # Modyfikuj query w load_hourly_weather aby pobierać 5-21h
    conn = sqlite3.connect(db_path)
    location_filter = f"AND location = '{location}'" if location else ""
    
    query = f"""
    SELECT 
        DATE(timestamp) as day,
        CAST(strftime('%H', timestamp) AS INTEGER) as hour,
        AVG(temperature_celsius) as temp_c,
        AVG(humidity_percent) as humidity_pct,
        AVG(cloud_cover_percent) as cloud_cover_pct,
        AVG(cloud_cover_low_percent) as cloud_cover_low_pct,
        AVG(cloud_cover_mid_percent) as cloud_cover_mid_pct,
        AVG(solar_radiation_wm2) as radiation_wm2,
        AVG(wind_speed_ms) as wind_speed_ms
    FROM weather_data
    WHERE DATE(timestamp) >= '{start_date}'
      AND DATE(timestamp) <= '{end_date}'
      AND hour BETWEEN 5 AND 21
      {location_filter}
    GROUP BY DATE(timestamp), hour
    """
    
    weather = pd.read_sql_query(query, conn)
    conn.close()
    
    # Merge
    df = pv.merge(weather, on=['day', 'hour'], how='inner')

    # Warstwy chmur: braki ← całkowite zachmurzenie
    if 'cloud_cover_low_pct' in df.columns:
        df['cloud_cover_low_pct'] = df['cloud_cover_low_pct'].fillna(df['cloud_cover_pct'])
    else:
        df['cloud_cover_low_pct'] = df['cloud_cover_pct']
    if 'cloud_cover_mid_pct' in df.columns:
        df['cloud_cover_mid_pct'] = df['cloud_cover_mid_pct'].fillna(df['cloud_cover_pct'])
    else:
        df['cloud_cover_mid_pct'] = df['cloud_cover_pct']
    
    # Dodaj cechy słoneczne
    df = calculate_sun_features(df, latitude=latitude, longitude=longitude)

    from src.features.clearness import add_clearness_features
    df = add_clearness_features(df, latitude=latitude, longitude=longitude)

    # Geometria paneli (tilt/azymut) — opcjonalnie, domyślnie wyłączone
    from src.features.panel_geometry import (
        add_panel_geometry_features,
        panel_geometry_enabled,
    )
    if panel_geometry_enabled():
        df = add_panel_geometry_features(df, latitude=latitude, longitude=longitude)
        print(
            '✓ Dodano cechy geometrii paneli '
            f'(tilt={os.getenv("PANEL_TILT_DEG", "35")}°, '
            f'azymut={os.getenv("PANEL_AZIMUTH_DEG", "180")}°)'
        )
    
    # Feature engineering (podstawowe)
    dt = pd.to_datetime(df['day'])
    doy = dt.dt.dayofyear
    df['doy_sin'] = np.sin(2 * np.pi * doy / 365.25)
    df['doy_cos'] = np.cos(2 * np.pi * doy / 365.25)
    df['month'] = dt.dt.month
    
    # Dodaj flagi śniegu (dzienne, powtórzone dla każdej godziny)
    if use_snow_melt:
        try:
            from src.features.snow_melt_model import build_melt_daily_frame, SnowMeltParams
            
            params = SnowMeltParams(
                latitude=latitude,
                longitude=longitude,
                use_dynamic_hours=True
            )
            
            melt_daily = build_melt_daily_frame(db_path, start_date, end_date, location, params=params)
            
            # Wybierz tylko potrzebne kolumny
            snow_flags = melt_daily[['day', 'snow_on_panels_melt']].rename(
                columns={'snow_on_panels_melt': 'snow_on_panels'}
            )
            
            # Dodaj poprzedni dzień
            snow_flags = snow_flags.sort_values('day')
            snow_flags['snow_on_panels_prev'] = snow_flags['snow_on_panels'].shift(1).fillna(0).astype(int)
            
            # Merge z danymi godzinowymi (każda godzina dostaje flagę z całego dnia)
            df = df.merge(snow_flags, on='day', how='left')
            df['snow_on_panels'] = df['snow_on_panels'].fillna(0).astype(int)
            df['snow_on_panels_prev'] = df['snow_on_panels_prev'].fillna(0).astype(int)
            
            print(f'✓ Dodano flagi śniegu z modelu topnienia (dni ze śniegiem: {df["snow_on_panels"].sum()} / {df["day"].nunique()})')
            
        except Exception as e:
            print(f'⚠️  Nie udało się dodać flag śniegu: {e}')
            df['snow_on_panels'] = 0
            df['snow_on_panels_prev'] = 0
    else:
        df['snow_on_panels'] = 0
        df['snow_on_panels_prev'] = 0
    
    # Dodaj flagę mgły (dzienną, powtórzoną dla każdej godziny)
    if use_fog_flags:
        try:
            from src.data.weather_api import flag_likely_fog_days, load_daily_pv_daytime, load_daily_weather
            
            # Wczytaj dzienne dane pogodowe i PV (z dynamicznymi godzinami!)
            daily_weather = load_daily_weather(db_path, start_date, end_date, location,
                                              use_dynamic_hours=True, latitude=latitude, longitude=longitude)
            daily_pv = load_daily_pv_daytime(
                db_path, start_date, end_date,
                use_dynamic_hours=True, latitude=latitude, longitude=longitude,
            )
            
            # Oblicz flagę mgły
            fog_df = flag_likely_fog_days(daily_weather, daily_pv)[['day', 'likely_fog_day']]
            fog_df['likely_fog_day'] = fog_df['likely_fog_day'].astype(int)
            
            # Merge z danymi godzinowymi (każda godzina dostaje flagę z całego dnia)
            df = df.merge(fog_df, on='day', how='left')
            df['likely_fog_day'] = df['likely_fog_day'].fillna(0).astype(int)
            
            fog_days = df['likely_fog_day'].sum()
            total_days = df['day'].nunique()
            print(f'✓ Dodano flagę mgły (dni z mgłą: {fog_days} / {total_days})')
            
        except Exception as e:
            print(f'⚠️  Nie udało się dodać flagi mgły: {e}')
            df['likely_fog_day'] = 0
    else:
        df['likely_fog_day'] = 0
    
    # Filtruj: tylko godziny z faktyczną produkcją w dzień
    valid = (
        df[TARGET_COLUMN].notna() &
        df['radiation_wm2'].notna() &
        (df['is_daylight'] == 1) &  # Tylko dzień
        (df[TARGET_COLUMN] > 0.01)  # Minimalna produkcja
    )
    
    df = df.loc[valid].copy().reset_index(drop=True)
    
    print(f'📊 Statystyki godzin produkcji:')
    print(f'   Najwcześniejsza: {df["hour"].min()}:00')
    print(f'   Najpóźniejsza: {df["hour"].max()}:00')
    print(f'   Średni wschód słońca: {df["sunrise_hour"].mean():.2f}')
    print(f'   Średni zachód słońca: {df["sunset_hour"].mean():.2f}')
    
    return df
