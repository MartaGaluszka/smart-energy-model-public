#!/usr/bin/env python
"""
Analiza serii pochmurnych dni (wiosna / lato / jesień) — wpływ na baterię.

Domyślnie dwa raporty w jednym uruchomieniu:
  - DEV  — okno treningowe RF (rolling 12 mies., jak train_hourly_model_tuning.py)
  - OOS  — dni po train_end do dziś (operacyjne)

Metoda:
  - Pochmurny (meteo): średnie zachmurzenie w godzinach dziennych ≥ próg (domyślnie 70%)
  - Combo: pochmurny + niska PV (< 50% mediany sezonu lub < p25)
  - Serie liczone na pełnej osi czasu w obrębie każdego bloku

Uruchomienie:
    python scripts/analyze_cloudy_streaks.py
    python scripts/analyze_cloudy_streaks.py --single --from 2025-06-01 --to 2026-05-31
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import date

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

from src.data.weather_api import load_daily_pv, load_daily_pv_daytime, load_daily_weather
from src.features.pv_features_hourly_extended import get_sunrise_sunset
from src.models.ml_train_window import format_train_window, oos_window, resolve_train_window

load_dotenv()

DB_PATH = os.getenv('DATABASE_PATH', 'data/energy_model.db')
DEFAULT_CSV = 'data/processed/cloudy_streak_analysis.csv'
CLOUDY_THRESH_DEFAULT = float(os.getenv('FORECAST_CLOUDY_THRESHOLD_PCT', '70'))
LOW_PV_ABSOLUTE_KWH = float(os.getenv('CLOUDY_STREAK_LOW_PV_KWH', '10'))

SEASONS = {
    'wiosna': {3, 4, 5},
    'lato': {6, 7, 8},
    'jesień': {9, 10, 11},
}
SEASON_ORDER = ['wiosna', 'lato', 'jesień']
FULL_DAYS_PER_SEASON = {'wiosna': 92, 'lato': 92, 'jesień': 91}


def season_of(day: str) -> str | None:
    month = int(day[5:7])
    for name, months in SEASONS.items():
        if month in months:
            return name
    return None


def streak_positions(flags: pd.Series) -> pd.Series:
    pos: list[int] = []
    run = 0
    for value in flags.astype(bool):
        if value:
            run += 1
            pos.append(run)
        else:
            run = 0
            pos.append(0)
    return pd.Series(pos, index=flags.index)


def daylight_cloud_cover(
    hourly: pd.DataFrame,
    day: str,
    latitude: float,
    longitude: float,
) -> float:
    try:
        sunrise, sunset = get_sunrise_sunset(latitude, longitude, day)
        hour_start = max(5, int(sunrise.hour))
        hour_end = min(21, int(sunset.hour) + 1)
    except Exception:
        hour_start, hour_end = 9, 16

    subset = hourly[
        (hourly['day'] == day)
        & (hourly['hour'] >= hour_start)
        & (hourly['hour'] <= hour_end)
    ]
    if subset.empty:
        return np.nan
    return float(subset['cloud_cover_percent'].mean())


def collect_runs(df: pd.DataFrame, mask_col: str, min_len: int = 2) -> list[list[pd.Series]]:
    runs: list[list[pd.Series]] = []
    current: list[pd.Series] = []
    for _, row in df.sort_values('day').iterrows():
        if row[mask_col]:
            current.append(row)
        else:
            if len(current) >= min_len:
                runs.append(current)
            current = []
    if len(current) >= min_len:
        runs.append(current)
    return runs


def build_analysis_table(
    db_path: str,
    start: str,
    end: str,
    *,
    ml_period: str,
    location: str | None,
    latitude: float,
    longitude: float,
    cloud_threshold: float,
    low_pv_kwh: float,
) -> pd.DataFrame:
    weather = load_daily_weather(
        db_path, start, end, location, latitude=latitude, longitude=longitude,
    )
    pv = load_daily_pv(db_path, start, end)
    pv_day = load_daily_pv_daytime(
        db_path, start, end, latitude=latitude, longitude=longitude,
    )

    df = weather.merge(pv, on='day').merge(pv_day, on='day')
    df['season'] = df['day'].map(season_of)
    df = df[df['season'].notna()].sort_values('day').reset_index(drop=True)
    if df.empty:
        df['ml_period'] = ml_period
        return df

    conn = sqlite3.connect(db_path)
    query = '''
        SELECT date(timestamp) AS day,
               CAST(strftime('%H', timestamp) AS INTEGER) AS hour,
               cloud_cover_percent
        FROM weather_data
        WHERE date(timestamp) BETWEEN ? AND ?
          AND data_source LIKE 'OpenMeteo%'
    '''
    params: list = [start, end]
    if location:
        query += ' AND location = ?'
        params.append(location)
    hourly = pd.read_sql_query(query, conn, params=params)
    conn.close()

    df['cloud_daylight_avg'] = df['day'].map(
        lambda d: daylight_cloud_cover(hourly, d, latitude, longitude)
    )

    season_stats = df.groupby('season')['pv_kwh_solar'].agg(
        ['median', 'mean', lambda s: s.quantile(0.25)],
    )
    season_stats.columns = ['pv_median', 'pv_mean', 'pv_p25']
    df = df.merge(season_stats, on='season')

    df['cloudy_meteo'] = df['cloud_daylight_avg'] >= cloud_threshold
    df['low_pv'] = (
        (df['pv_kwh_solar'] < 0.5 * df['pv_median'])
        | (df['pv_kwh_solar'] < df['pv_p25'])
    )
    df['cloudy_combo'] = df['cloudy_meteo'] & df['low_pv']
    df['low_pv_absolute'] = df['pv_kwh_solar'] < low_pv_kwh

    for col in ['cloudy_meteo', 'low_pv', 'cloudy_combo', 'low_pv_absolute']:
        df[f'streak_{col}'] = streak_positions(df[col])

    df['ml_period'] = ml_period
    return df


def _format_run(run: list[pd.Series]) -> str:
    days = [str(x['day']) for x in run]
    pvs = [round(float(x['pv_kwh_solar']), 1) for x in run]
    clouds = [round(float(x['cloud_daylight_avg'])) for x in run]
    return (
        f"    {days[0]}→{days[-1]} ({len(days)}d)  "
        f"PV={pvs}  chm={clouds}%  suma={sum(pvs):.1f} kWh"
    )


def print_report(
    df: pd.DataFrame,
    *,
    period_label: str,
    start: str,
    end: str,
    cloud_threshold: float,
    low_pv_kwh: float,
) -> None:
    print('\n' + '=' * 72)
    print(
        f'[{period_label}]  {start} → {end}  |  {len(df)} dni  |  '
        f'próg chmur ≥ {cloud_threshold:.0f}%'
    )
    print('=' * 72)

    if df.empty:
        print('  Brak dni w tym okresie.')
        return

    print('\n## Pokrycie + mediana PV')
    for season in SEASON_ORDER:
        sub = df[df['season'] == season]
        if sub.empty:
            print(f'  {season:8s}: brak danych')
            continue
        print(
            f"  {season:8s}: {len(sub):3d} dni ({sub['day'].min()} → {sub['day'].max()})  "
            f"med PV={sub['pv_kwh_solar'].median():.1f} kWh"
        )

    stats = df.groupby('season')[['pv_median', 'pv_mean', 'pv_p25']].first()
    print('\n## Progi niskiej PV (<50% mediany lub <p25)')
    print(stats.round(1).to_string())

    print('\n## Pochmurne dni (meteo) + pozycja w serii')
    for season in SEASON_ORDER:
        sub = df[df['season'] == season]
        if sub.empty:
            continue
        cloudy = int(sub['cloudy_meteo'].sum())
        d2 = int((sub['streak_cloudy_meteo'] == 2).sum())
        d3p = int((sub['streak_cloudy_meteo'] >= 3).sum())
        print(
            f"  {season:8s}: pochmurne {cloudy:3d}/{len(sub)} ({100 * cloudy / len(sub):.0f}%)  "
            f"| 2. dzień = {d2:2d}  |  3.+ = {d3p:2d}  |  razem 2.+ = {d2 + d3p}"
        )

    print('\n## Combo (pochmurne + niska PV) + pozycja w serii')
    for season in SEASON_ORDER:
        sub = df[df['season'] == season]
        if sub.empty:
            continue
        combo = int(sub['cloudy_combo'].sum())
        d2 = int((sub['streak_cloudy_combo'] == 2).sum())
        d3p = int((sub['streak_cloudy_combo'] >= 3).sum())
        print(
            f"  {season:8s}: combo {combo:3d}/{len(sub)}  "
            f"| 2. = {d2:2d}  |  3.+ = {d3p:2d}  |  razem 2.+ = {d2 + d3p}"
        )

    summer = df[df['season'] == 'lato']
    if not summer.empty:
        low10 = int(summer['low_pv_absolute'].sum())
        streak2 = int((summer['streak_low_pv_absolute'] >= 2).sum())
        print(f'\n## Lato: PV < {low_pv_kwh:.0f} kWh/dzień')
        print(f"  dni: {low10}/{len(summer)} ({100 * low10 / len(summer):.0f}%)  |  2.+ dzień serii: {streak2}")

    for label, col in [('METEO', 'cloudy_meteo'), ('COMBO', 'cloudy_combo')]:
        print(f'\n=== Serie ≥2 dni ({label}) ===')
        for season in SEASON_ORDER:
            runs = [
                run for run in collect_runs(df, col)
                if season_of(str(run[0]['day'])) == season
            ]
            print(f'\n  {season}: {len(runs)} serii')
            for run in runs:
                print(_format_run(run))

    print(f'\n=== Lato: serie PV < {low_pv_kwh:.0f} kWh (≥2 dni) ===')
    summer_runs: list[list[pd.Series]] = []
    current: list[pd.Series] = []
    for _, row in df.sort_values('day').iterrows():
        if row['low_pv_absolute'] and row['season'] == 'lato':
            current.append(row)
        else:
            if len(current) >= 2:
                summer_runs.append(current)
            if not (row['low_pv_absolute'] and row['season'] == 'lato'):
                current = []
    if len(current) >= 2:
        summer_runs.append(current)

    if not summer_runs:
        print('  brak serii')
    for run in summer_runs:
        days = [str(x['day']) for x in run]
        pvs = [round(float(x['pv_kwh_solar']), 1) for x in run]
        print(f"  {days[0]}→{days[-1]} ({len(days)}d)  PV={pvs}  suma={sum(pvs):.1f} kWh")

    print('\n## Ekstrapolacja roczna (combo, 2.+ dzień serii)')
    for season in SEASON_ORDER:
        sub = df[df['season'] == season]
        if sub.empty:
            continue
        observed = len(sub)
        second_plus = int((sub['streak_cloudy_combo'] >= 2).sum())
        rate = second_plus / observed
        annual = rate * FULL_DAYS_PER_SEASON[season]
        print(
            f"  {season:8s}: {second_plus} dni 2.+ / {observed} obs  →  ~{annual:.0f} dni/rok"
        )


def run_dual_report(
    *,
    location: str | None,
    latitude: float,
    longitude: float,
    cloud_threshold: float,
    low_pv_kwh: float,
    through: str | None = None,
) -> pd.DataFrame:
    dev_start, dev_end = resolve_train_window()
    through = through or date.today().isoformat()

    print('=' * 72)
    print('ANALIZA POCHMURNYCH DNI — DEV (RF) + OOS (operacyjny)')
    print(f'Okno DEV: {format_train_window(dev_start, dev_end)}')
    oos = oos_window(dev_end, through=through)
    if oos:
        print(f'Okno OOS: {oos[0]} → {oos[1]}')
    else:
        print('Okno OOS: brak dni po train_end')

    df_dev = build_analysis_table(
        DB_PATH, dev_start, dev_end,
        ml_period='dev',
        location=location,
        latitude=latitude,
        longitude=longitude,
        cloud_threshold=cloud_threshold,
        low_pv_kwh=low_pv_kwh,
    )
    print_report(
        df_dev,
        period_label='DEV — zbiór treningowy RF',
        start=dev_start,
        end=dev_end,
        cloud_threshold=cloud_threshold,
        low_pv_kwh=low_pv_kwh,
    )

    frames = [df_dev]
    if oos:
        df_oos = build_analysis_table(
            DB_PATH, oos[0], oos[1],
            ml_period='oos',
            location=location,
            latitude=latitude,
            longitude=longitude,
            cloud_threshold=cloud_threshold,
            low_pv_kwh=low_pv_kwh,
        )
        print_report(
            df_oos,
            period_label='OOS — prognoza operacyjna',
            start=oos[0],
            end=oos[1],
            cloud_threshold=cloud_threshold,
            low_pv_kwh=low_pv_kwh,
        )
        frames.append(df_oos)

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def main() -> None:
    parser = argparse.ArgumentParser(description='Analiza serii pochmurnych dni (PV + bateria)')
    parser.add_argument(
        '--single',
        action='store_true',
        help='Jeden raport (--from / --to); domyślnie DEV+OOS',
    )
    parser.add_argument('--from', dest='start', default='2025-06-01', help='Początek (--single)')
    parser.add_argument('--to', dest='end', default=date.today().isoformat(), help='Koniec (--single)')
    parser.add_argument('--csv', default=DEFAULT_CSV, help='Ścieżka CSV z wynikami dziennymi')
    parser.add_argument(
        '--cloud-threshold',
        type=float,
        default=CLOUDY_THRESH_DEFAULT,
        help='Próg zachmurzenia dziennego (%%), domyślnie 70',
    )
    parser.add_argument(
        '--low-pv-kwh',
        type=float,
        default=LOW_PV_ABSOLUTE_KWH,
        help='Próg absolutnie niskiej PV latem [kWh], domyślnie 10',
    )
    parser.add_argument('--no-csv', action='store_true', help='Nie zapisuj CSV')
    args = parser.parse_args()

    latitude = float(os.getenv('WEATHER_LAT', '50.06'))
    longitude = float(os.getenv('WEATHER_LON', '19.94'))
    location = os.getenv('WEATHER_LOCATION') or None

    if args.single:
        df = build_analysis_table(
            DB_PATH,
            args.start,
            args.end,
            ml_period='custom',
            location=location,
            latitude=latitude,
            longitude=longitude,
            cloud_threshold=args.cloud_threshold,
            low_pv_kwh=args.low_pv_kwh,
        )
        if df.empty:
            print(f'Brak danych w okresie {args.start} → {args.end}')
            sys.exit(1)
        print_report(
            df,
            period_label='CUSTOM',
            start=args.start,
            end=args.end,
            cloud_threshold=args.cloud_threshold,
            low_pv_kwh=args.low_pv_kwh,
        )
    else:
        df = run_dual_report(
            location=location,
            latitude=latitude,
            longitude=longitude,
            cloud_threshold=args.cloud_threshold,
            low_pv_kwh=args.low_pv_kwh,
            through=args.end,
        )
        if df.empty:
            print('Brak danych do analizy.')
            sys.exit(1)

    if not args.no_csv:
        os.makedirs(os.path.dirname(args.csv) or '.', exist_ok=True)
        df.to_csv(args.csv, index=False)
        print(f'\n✓ CSV: {args.csv}  (kolumna ml_period: dev / oos / custom)')


if __name__ == '__main__':
    main()
