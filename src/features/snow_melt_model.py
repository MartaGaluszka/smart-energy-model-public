"""
Model fenomenologiczny topnienia / zsunięcia śniegu z dachu (bez etykiet foto).

Bilans godzinowy S_t [cm] na panelach:
    S_t = S_{t-1} + opad_na_dachu - topnienie - zsunięcie

Topnienie (godz. t):
    M_t = k_melt * max(0, T_t - T_melt) * (1 + k_rad * G_t/G_ref) * f_wilg(RH_t)

Zsunięcie: gdy T_t >= T_slide i G_t >= G_slide → S *= (1 - slide_fraction)

Kalibracja współczynników na PV (proxy stanu paneli), nie na zdjęciach.
Obserwacje foto — tylko walidacja (scripts/calibrate_snow_melt.py).

Uruchomienie (z katalogu projektu smart-energy-model):
    python scripts/calibrate_snow_melt.py

Podgląd modułu (ten plik):
    python src/features/snow_melt_model.py
"""

from __future__ import annotations

# Bezpośrednie uruchomienie pliku: python src/features/snow_melt_model.py
if __name__ == '__main__':
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import os
import sqlite3
from dataclasses import dataclass, replace
from typing import Iterable

import numpy as np
import pandas as pd

from src.features.pv_features import DEFAULT_SNOW_THAW_TEMP_C, DEFAULT_SNOW_WINDOW_DAYS, apply_snow_panel_flags

# Import dla dynamicznych godzin wschodu/zachodu słońca
try:
    from src.features.pv_features_hourly_extended import get_sunrise_sunset
    SUNRISE_SUNSET_AVAILABLE = True
except ImportError:
    SUNRISE_SUNSET_AVAILABLE = False


@dataclass(frozen=True)
class SnowMeltParams:
    """Parametry modelu — domyślne z grida kalibracji na danych projektu."""

    t_melt_c: float = 0.0
    k_melt_cm_per_h: float = 0.10
    k_rad_boost: float = 0.50
    g_ref_wm2: float = 400.0
    k_hum_boost: float = 0.35
    t_slide_c: float = 1.0
    g_slide_wm2: float = 60.0
    slide_fraction: float = 0.90
    roof_clear_cm: float = 0.5
    snowfall_to_roof: float = 0.65
    g_start_wm2: float = 25.0
    pv_start_kwh: float = 0.12
    prod_hour_start: int = 6  # fallback gdy brak sunrise/sunset
    prod_hour_end: int = 18   # fallback gdy brak sunrise/sunset
    use_dynamic_hours: bool = True  # używaj wschodu/zachodu słońca
    latitude: float = 50.06    # dla obliczenia wschodu/zachodu
    longitude: float = 19.94   # dla obliczenia wschodu/zachodu


DEFAULT_SNOW_MELT_PARAMS = SnowMeltParams()


def load_hourly_weather_pv(
    db_path: str,
    start_date: str,
    end_date: str,
    location: str | None = None,
) -> pd.DataFrame:
    """Godzinowa ramka: pogoda Open-Meteo + PV (dodatnie kWh/h).
    
    FILTR BATERII: battery_power_kw >= -0.1 (wyklucza produkcję przy rozładowaniu baterii)
    """
    conn = sqlite3.connect(db_path)
    weather_q = '''
        SELECT
            timestamp,
            date(timestamp) AS day,
            cast(strftime('%H', timestamp) AS integer) AS hour,
            temperature_celsius AS temp_c,
            humidity_percent AS humidity,
            COALESCE(solar_radiation_wm2, 0) AS radiation_wm2,
            COALESCE(snowfall_cm, 0) AS snowfall_cm,
            COALESCE(precipitation_mm, 0) AS precip_mm
        FROM weather_data
        WHERE date(timestamp) BETWEEN ? AND ?
          AND data_source LIKE 'OpenMeteo%'
    '''
    w_params: list = [start_date, end_date]
    if location:
        weather_q += ' AND location = ?'
        w_params.append(location)
    weather_q += ' ORDER BY timestamp'
    weather = pd.read_sql_query(weather_q, conn, params=w_params)

    pv = pd.read_sql_query(
        '''
        SELECT
            timestamp,
            date(timestamp) AS day,
            cast(strftime('%H', timestamp) AS integer) AS hour,
            SUM(CASE WHEN pv_energy_kwh > 0 AND COALESCE(battery_power_kw, 0) >= -0.1 
                THEN pv_energy_kwh ELSE 0 END) AS pv_kwh
        FROM foxess_data
        WHERE date(timestamp) BETWEEN ? AND ?
        GROUP BY timestamp
        ORDER BY timestamp
        ''',
        conn,
        params=(start_date, end_date),
    )
    conn.close()

    if weather.empty:
        return weather

    pv_h = (
        pv.groupby(['day', 'hour'], as_index=False)['pv_kwh']
        .sum()
    )
    df = weather.merge(pv_h, on=['day', 'hour'], how='left')
    df['pv_kwh'] = df['pv_kwh'].fillna(0.0)
    return df


def _humidity_factor(rh: float, params: SnowMeltParams) -> float:
    """Wyższa wilgotność → mokry śnieg, szybsze topnienie / ślizganie."""
    rh = 50.0 if pd.isna(rh) else float(rh)
    return 1.0 + params.k_hum_boost * max(0.0, rh / 100.0 - 0.55)


def simulate_hourly_snow(
    hourly: pd.DataFrame,
    params: SnowMeltParams | None = None,
    initial_snow_cm: float = 0.0,
) -> pd.DataFrame:
    """Symulacja S_t godzinowo; stan przenoszony między dniami."""
    params = params or DEFAULT_SNOW_MELT_PARAMS
    df = hourly.sort_values('timestamp').copy().reset_index(drop=True)

    snow_cm = np.zeros(len(df), dtype=float)
    melt_cm = np.zeros(len(df), dtype=float)
    slide_cm = np.zeros(len(df), dtype=float)
    panels_clear = np.zeros(len(df), dtype=bool)

    s = float(initial_snow_cm)
    # NOWE: licznik godzin z wysoką radiację (dla warunku 2-3h)
    high_rad_hours_today = 0
    current_day = None
    
    for i, row in df.iterrows():
        # Sprawdź, czy zaczyna się nowy dzień
        day = row.get('day')
        if day != current_day:
            current_day = day
            high_rad_hours_today = 0  # reset na nowy dzień
        
        snow_in = max(0.0, float(row.get('snowfall_cm') or 0)) * params.snowfall_to_roof
        temp = float(row.get('temp_c') or 0)
        rad = max(0.0, float(row.get('radiation_wm2') or 0))
        rh = row.get('humidity')

        # Licz godziny z wysoką radiację (dla warunku zsunięcia)
        if rad >= 150.0:  # ZMIANA 1: obniżony próg z 180 do 150 W/m²
            high_rad_hours_today += 1

        melt = (
            params.k_melt_cm_per_h
            * max(0.0, temp - params.t_melt_c)
            * (1.0 + params.k_rad_boost * rad / params.g_ref_wm2)
            * _humidity_factor(rh, params)
        )
        slide = 0.0
        s = s + snow_in - melt
        if s < 0:
            s = 0.0

        # POPRAWKA: Zsunięcie może nastąpić na 2 sposoby:
        # 1) Temperatura >= t_slide I radiacja >= g_slide (stary mechanizm)
        # 2) NOWY: Silne słońce nagrzewa panele przy temp < 0°C
        #    - Próg obniżony do 150 W/m² (z oryginalnych 60)
        #    - Bez wymogu wielogodzinnego nasłonecznienia (zbyt restrykcyjne)
        slide_condition_temp = (temp >= params.t_slide_c and rad >= params.g_slide_wm2)
        slide_condition_solar = (rad >= 150.0 and s > 0.5)  # Uproszczone: tylko próg radiacji
        
        if s > 0 and (slide_condition_temp or slide_condition_solar):
            slide = s * params.slide_fraction
            s -= slide

        snow_cm[i] = s
        melt_cm[i] = melt
        slide_cm[i] = slide
        panels_clear[i] = s < params.roof_clear_cm

    out = df.copy()
    out['snow_roof_cm'] = snow_cm
    out['snow_melt_cm'] = melt_cm
    out['snow_slide_cm'] = slide_cm
    out['panels_clear'] = panels_clear.astype(int)
    return out


def _first_hour_meeting(
    day_df: pd.DataFrame,
    *,
    mask: pd.Series,
) -> float | None:
    hits = day_df.loc[mask, 'hour']
    if hits.empty:
        return None
    return float(hits.iloc[0])


def aggregate_daily_melt(hourly_sim: pd.DataFrame, params: SnowMeltParams | None = None) -> pd.DataFrame:
    """Agregacja dzienna: flaga blokady, grubość śniegu (dynamiczne godziny), przewidywana godzina startu PV.
    
    UWAGA: Używa dynamicznych godzin wschodu/zachodu słońca jeśli params.use_dynamic_hours=True.
           Fallback do prod_hour_start/end gdy brak sunrise/sunset.
    """
    params = params or DEFAULT_SNOW_MELT_PARAMS
    rows: list[dict] = []

    for day, g in hourly_sim.groupby('day', sort=True):
        g = g.sort_values('hour')
        
        # Oblicz dynamiczne godziny dla tego dnia
        if params.use_dynamic_hours and SUNRISE_SUNSET_AVAILABLE:
            try:
                sunrise, sunset = get_sunrise_sunset(params.latitude, params.longitude, day)
                hour_start = max(5, int(sunrise.hour))  # min 5:00
                hour_end = min(20, int(sunset.hour) + 1)  # max 20:00
            except Exception:
                hour_start = params.prod_hour_start
                hour_end = params.prod_hour_end
        else:
            hour_start = params.prod_hour_start
            hour_end = params.prod_hour_end
        
        # Agregacja śniegu dla godzin produkcji (dynamiczne lub 9-16 fallback)
        prod = g[(g['hour'] >= hour_start) & (g['hour'] <= hour_end)]
        if prod.empty:
            prod = g[(g['hour'] >= 9) & (g['hour'] <= 16)]  # fallback
        snow_prod_hours = float(prod['snow_roof_cm'].mean()) if not prod.empty else float(g['snow_roof_cm'].mean())
        
        # POPRAWKA: Zamiast średniej pokrywy, użyj "majority vote"
        # Jeśli >50% godzin produkcji ma czyste panele, dzień jest czysty
        clear_hours = (prod['panels_clear'] == 1).sum() if not prod.empty else 0
        total_hours = len(prod) if not prod.empty else 1
        blocked = (clear_hours / total_hours) < 0.5  # ZMIENIONE: majority vote zamiast średniej

        pred_mask = (
            (g['hour'] >= hour_start)
            & (g['hour'] <= hour_end)
            & (g['panels_clear'] == 1)
            & (g['radiation_wm2'] >= params.g_start_wm2)
        )
        obs_mask = (
            (g['hour'] >= hour_start)
            & (g['hour'] <= hour_end)
            & (g['pv_kwh'] >= params.pv_start_kwh)
        )
        rows.append({
            'day': day,
            'snow_roof_cm_prod_hours': round(snow_prod_hours, 3),  # zmieniona nazwa
            'snow_roof_cm_max': round(float(g['snow_roof_cm'].max()), 3),
            'snow_on_panels_melt': int(blocked),
            'panels_clear_prod_hours': int(not blocked),  # zmieniona nazwa
            'pv_start_hour_pred': _first_hour_meeting(g, mask=pred_mask),
            'pv_start_hour_obs': _first_hour_meeting(g, mask=obs_mask),
            'prod_hour_start': hour_start,  # zapisz użyte godziny
            'prod_hour_end': hour_end,
        })

    return pd.DataFrame(rows)


def build_melt_daily_frame(
    db_path: str,
    start_date: str,
    end_date: str,
    location: str | None = None,
    params: SnowMeltParams | None = None,
) -> pd.DataFrame:
    """Godzinowa symulacja + agregacja dzienna."""
    hourly = load_hourly_weather_pv(db_path, start_date, end_date, location)
    if hourly.empty:
        return pd.DataFrame()
    sim = simulate_hourly_snow(hourly, params=params)
    return aggregate_daily_melt(sim, params=params)


def _pv_proxy_blocked(row: pd.Series) -> float | None:
    """Etykieta proxy z PV: 1=zablokowane, 0=odsłonięte, NaN=nie wiadomo."""
    rad = float(row.get('radiation_daytime_kwh_m2') or 0)
    pv = float(row.get('pv_kwh_daytime') or 0)
    snow7 = float(row.get('snowfall_7d_cm') or 0)
    if snow7 <= 0 or rad < 0.35:
        return None
    yld = pv / rad
    if yld < 0.18 and pv < 3.5:
        return 1.0
    if yld >= 0.38 and pv >= 2.0:
        return 0.0
    return None


def calibrate_snow_melt_params(
    daily_weather_pv: pd.DataFrame,
    *,
    winter_months: tuple[int, ...] = (11, 12, 1, 2, 3),
    k_melt_values: Iterable[float] = (0.06, 0.08, 0.10, 0.12, 0.15),
    t_melt_values: Iterable[float] = (-1.0, 0.0, 1.0),
    slide_fraction_values: Iterable[float] = (0.75, 0.85, 0.95),
    latitude: float = 50.06,
    longitude: float = 19.94,
) -> tuple[SnowMeltParams, pd.DataFrame]:
    """
    Grid search na zimowych dniach ze śniegiem — dopasowanie flagi blokady do proxy PV.

    Wymaga kolumn: day, radiation_daytime_kwh_m2, pv_kwh_daytime, om_snowfall_cm
    oraz wcześniej policzonej ramki melt (pv_start_hour_pred/obs) lub przebudowy per kombinacja.
    
    Args:
        latitude: Szerokość geograficzna (dla dynamicznych godzin)
        longitude: Długość geograficzna (dla dynamicznych godzin)
    """
    db_path = os.getenv('DATABASE_PATH', 'data/energy_model.db')
    location = os.getenv('WEATHER_LOCATION')
    start = str(daily_weather_pv['day'].min())
    end = str(daily_weather_pv['day'].max())
    hourly = load_hourly_weather_pv(db_path, start, end, location)
    if hourly.empty:
        raise ValueError('Brak danych godzinowych do kalibracji modelu topnienia.')

    base = daily_weather_pv.copy().reset_index(drop=True)
    base['snowfall_7d_cm'] = (
        base['om_snowfall_cm'].fillna(0).rolling(7, min_periods=1).sum()
    )
    base['pv_proxy_blocked'] = base.apply(_pv_proxy_blocked, axis=1)

    rows: list[dict] = []
    best_params = replace(
        DEFAULT_SNOW_MELT_PARAMS,
        latitude=latitude,
        longitude=longitude,
        use_dynamic_hours=True
    )
    best_score = float('inf')

    for t_melt in t_melt_values:
        for k_melt in k_melt_values:
            for slide_frac in slide_fraction_values:
                p = replace(
                    best_params,  # używa latitude/longitude
                    t_melt_c=float(t_melt),
                    k_melt_cm_per_h=float(k_melt),
                    slide_fraction=float(slide_frac),
                )
                sim = simulate_hourly_snow(hourly, params=p)
                melt_daily = aggregate_daily_melt(sim, params=p)
                merged = base.merge(melt_daily, on='day', how='left')

                winter = pd.to_datetime(merged['day']).dt.month.isin(winter_months)
                sub = merged[winter & merged['pv_proxy_blocked'].notna()].copy()
                if sub.empty:
                    continue

                flag_err = (sub['snow_on_panels_melt'] != sub['pv_proxy_blocked']).mean()

                t_sub = sub.dropna(subset=['pv_start_hour_pred', 'pv_start_hour_obs'])
                if len(t_sub) >= 5:
                    start_mae = (t_sub['pv_start_hour_pred'] - t_sub['pv_start_hour_obs']).abs().mean()
                else:
                    start_mae = 2.0

                score = float(flag_err) + 0.08 * float(start_mae)
                rows.append({
                    't_melt_c': t_melt,
                    'k_melt_cm_per_h': k_melt,
                    'slide_fraction': slide_frac,
                    'flag_error_rate': round(flag_err, 4),
                    'pv_start_mae_h': round(start_mae, 3),
                    'score': round(score, 4),
                })
                if score < best_score:
                    best_score = score
                    best_params = p

    ranking = pd.DataFrame(rows).sort_values('score').reset_index(drop=True)
    return best_params, ranking


def apply_melt_snow_flags(
    df: pd.DataFrame,
    db_path: str,
    start_date: str,
    end_date: str,
    location: str | None = None,
    params: SnowMeltParams | None = None,
) -> pd.DataFrame:
    """Dodaje cechy ze modelu topnienia i ustawia snow_on_panels / snow_on_panels_prev."""
    melt = build_melt_daily_frame(db_path, start_date, end_date, location, params=params)
    out = df.copy()
    
    # Usuń stare kolumny jeśli istnieją
    extra_to_drop = [
        'snow_on_panels_melt', 'snow_roof_cm_prod_hours', 'snow_roof_cm_9_16', 
        'panels_clear_prod_hours', 'panels_clear_9_16',
        'pv_start_hour_pred', 'pv_start_hour_obs', 'prod_hour_start', 'prod_hour_end',
        'snow_roof_cm_max',
    ]
    out = out.drop(columns=[c for c in extra_to_drop if c in out.columns], errors='ignore')
    
    if melt.empty:
        out['snow_on_panels'] = 0
        out['snow_on_panels_prev'] = 0
        return out

    # Wybierz tylko kolumny które faktycznie istnieją w melt
    merge_cols = ['day', 'snow_on_panels_melt']
    for col in melt.columns:
        if col not in merge_cols and col != 'day':
            merge_cols.append(col)
    
    out = out.merge(melt[merge_cols], on='day', how='left')
    out['snow_on_panels'] = out['snow_on_panels_melt'].fillna(0).astype(int)
    out['snow_on_panels_prev'] = out['snow_on_panels'].shift(1).fillna(0).astype(int)
    return out


def compare_snow_rules(
    daily_frame: pd.DataFrame,
    melt_daily: pd.DataFrame,
    *,
    legacy_window: int = DEFAULT_SNOW_WINDOW_DAYS,
    legacy_thaw: float = DEFAULT_SNOW_THAW_TEMP_C,
) -> pd.DataFrame:
    """Porównanie reguły 7d/3°C z modelem topnienia na całej ramce."""
    legacy = apply_snow_panel_flags(daily_frame, legacy_window, legacy_thaw)
    # Zachowaj kompatybilność wsteczną z kolumnami
    melt_cols = ['day', 'snow_on_panels_melt', 'pv_start_hour_pred', 'pv_start_hour_obs']
    if 'snow_roof_cm_prod_hours' in melt_daily.columns:
        melt_cols.append('snow_roof_cm_prod_hours')
        # Dodaj alias dla kompatybilności
        melt_daily['snow_roof_cm_9_16'] = melt_daily['snow_roof_cm_prod_hours']
    if 'snow_roof_cm_9_16' not in melt_cols:
        melt_cols.append('snow_roof_cm_9_16')
    
    merged = legacy.merge(
        melt_daily[melt_cols],
        on='day',
        how='left',
    )
    merged['snow_rules_agree'] = (
        merged['snow_on_panels'] == merged['snow_on_panels_melt']
    ).astype(int)
    return merged


if __name__ == '__main__':
    from dotenv import load_dotenv
    from pathlib import Path

    _root = Path(__file__).resolve().parents[2]
    load_dotenv(_root / '.env')

    db = os.getenv('DATABASE_PATH', str(_root / 'data/energy_model.db'))
    location = os.getenv('WEATHER_LOCATION')

    print('❄️ Model topnienia — podgląd (27–28.11.2025)\n')
    hourly = load_hourly_weather_pv(db, '2025-11-27', '2025-11-28', location)
    sim = simulate_hourly_snow(hourly)
    daily = aggregate_daily_melt(sim)

    # Wybierz kolumny do wyświetlenia (kompatybilność)
    cols = ['day', 'snow_on_panels_melt', 'pv_start_hour_pred', 'pv_start_hour_obs']
    if 'snow_roof_cm_prod_hours' in daily.columns:
        cols.insert(1, 'snow_roof_cm_prod_hours')
    elif 'snow_roof_cm_9_16' in daily.columns:
        cols.insert(1, 'snow_roof_cm_9_16')
    if 'prod_hour_start' in daily.columns:
        cols.extend(['prod_hour_start', 'prod_hour_end'])
    
    print(daily[cols].to_string(index=False))

    print('\nGodzinowo 28.11 (śnieg na dachu vs PV):')
    g = sim[sim['day'] == '2025-11-28'][['hour', 'snow_roof_cm', 'pv_kwh', 'radiation_wm2']]
    print(g[(g['hour'] >= 6) & (g['hour'] <= 16)].to_string(index=False))

    print('\nPełna kalibracja i walidacja foto:')
    print('  python scripts/calibrate_snow_melt.py')
