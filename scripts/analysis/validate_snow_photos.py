"""
Walidacja dni z obserwacjami pogodowymi (opisy tekstowe) vs PV / Open-Meteo / IMGW.

Bez plików graficznych — tylko metadane w PHOTO_METADATA i CSV.

Lista obserwacji w .env (PHOTO_VALIDATION):
    PHOTO_VALIDATION=2025-11-21:snow,2025-12-13:sun,2025-12-15:fog

Etykiety: snow | sun | fog | other

Uruchomienie:
    python scripts/validate_snow_photos.py
    python scripts/validate_snow_photos.py --csv data/processed/photo_validation.csv
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from typing import List, Tuple

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

from src.data.photo_ground_truth import (
    DEFAULT_PHOTO_VALIDATION,
    PHOTO_METADATA,
    parse_photo_validation,
)
from src.data.weather_api import (
    flag_likely_fog_days,
    load_daily_pv,
    load_daily_pv_daytime,
    load_daily_weather,
)

load_dotenv()

DB_PATH = os.getenv('DATABASE_PATH', 'data/energy_model.db')
LOCATION = os.getenv('WEATHER_LOCATION')


def _snow_in_data(row: pd.Series) -> bool:
    om_snow = (row.get('om_snowfall_cm') or 0) > 0 or (row.get('om_snow_depth_cm') or 0) >= 1
    imgw = row.get('imgw_snow_depth_cm')
    imgw_snow = pd.notna(imgw) and float(imgw) > 0
    return bool(om_snow or imgw_snow)


def _assess_agreement(row: pd.Series) -> str:
    label = row.get('photo_label', 'other')
    pv = row.get('pv_kwh_daytime') or 0
    fog = bool(row.get('likely_fog_day'))
    snow_data = _snow_in_data(row)

    if label == 'snow':
        if pv < 2 and snow_data:
            return 'silna (snieg + niskie PV + API)'
        if pv < 2 and not snow_data:
            return 'czesciowa (niskie PV, slabe API sniegu)'
        if pv >= 4 and snow_data:
            return 'snieg w otoczeniu (PV OK — panele czyste?)'
        if pv >= 4 and not snow_data:
            return 'rozbieznosc (foto snieg, brak w API)'
        return 'umiarkowana'

    if label == 'sun':
        if pv >= 5 and not snow_data:
            return 'silna (wysokie PV, brak sniegu)'
        if pv >= 5:
            return 'czesciowa (PV OK, dane o sniegu w API)'
        return 'slaba (niskie PV mimo etykiety sun)'

    if label == 'fog':
        if fog or pv < 3:
            return 'silna (mgla / niskie PV)'
        return 'slaba (wysokie PV — mozliwa clearing)'

    return '—'


def build_photo_report(db_path: str, observations: List[Tuple[str, str]]) -> pd.DataFrame:
    if not observations:
        raise ValueError('Pusta lista obserwacji foto.')

    days = [d for d, _ in observations]
    labels = {d: lbl for d, lbl in observations}
    start, end = min(days), max(days)

    weather = load_daily_weather(db_path, start, end, LOCATION)
    pv = load_daily_pv(db_path, start, end)
    pv_day = load_daily_pv_daytime(db_path, start, end)

    fog = flag_likely_fog_days(weather, pv_day)
    fog_cols = ['day', 'likely_fog_day', 'yield_kwh_per_kwh_m2']
    merged = weather.merge(pv, on='day', how='left').merge(
        pv_day[['day', 'pv_kwh_daytime']], on='day', how='left'
    ).merge(fog[fog_cols], on='day', how='left')

    conn = sqlite3.connect(db_path)
    imgw = pd.read_sql_query(
        '''
        SELECT day, snow_depth_cm AS imgw_snow_depth_cm, precip_mm AS imgw_precip_mm,
               temp_mean_c AS imgw_temp_mean_c, station_name AS imgw_station
        FROM imgw_daily WHERE day BETWEEN ? AND ?
        ''',
        conn,
        params=(start, end),
    )
    conn.close()
    merged = merged.merge(imgw, on='day', how='left')

    merged = merged[merged['day'].isin(days)].copy()
    merged['photo_label'] = merged['day'].map(labels)
    for col in ('photo_time', 'photo_snow_cm', 'photo_sky', 'photo_notes'):
        merged[col] = merged['day'].map(lambda d: PHOTO_METADATA.get(d, {}).get(col))
    merged = merged.sort_values('day').reset_index(drop=True)

    merged.rename(columns={
        'snowfall_cm_sum': 'om_snowfall_cm',
        'radiation_daytime_kwh_m2': 'rad_9_16_agg_kwh_m2',  # agregacja historyczna
        'radiation_kwh_m2': 'rad_doba_kwh_m2',
        'humidity_daytime_avg': 'humidity_9_16_avg_pct',  # agregacja historyczna
        'cloud_cover_avg': 'cloud_avg_pct',
    }, inplace=True)
    merged['om_snow_depth_cm'] = (merged['snow_depth_m_max'].fillna(0) * 100).round(0)

    merged['agreement'] = merged.apply(_assess_agreement, axis=1)

    out_cols = [
        'day', 'photo_label', 'photo_time', 'photo_snow_cm', 'photo_sky', 'photo_notes',
        'agreement',
        'pv_kwh_daytime', 'pv_kwh_solar', 'pv_kwh_artifact',
        'rad_9_16_agg_kwh_m2', 'rad_doba_kwh_m2',
        'om_snowfall_cm', 'om_snow_depth_cm', 'temp_avg', 'humidity_9_16_avg_pct',
        'cloud_avg_pct', 'likely_fog_day', 'yield_kwh_per_kwh_m2',
        'imgw_snow_depth_cm', 'imgw_precip_mm', 'imgw_temp_mean_c', 'imgw_station',
    ]
    for col in out_cols:
        if col not in merged.columns:
            merged[col] = None

    return merged[out_cols]


def main() -> None:
    parser = argparse.ArgumentParser(description='Walidacja dni z fotografiami pogodowymi')
    parser.add_argument(
        '--csv',
        default=os.getenv('PHOTO_VALIDATION_CSV', 'data/processed/photo_validation.csv'),
        help='Sciezka pliku CSV wyjsciowego',
    )
    args = parser.parse_args()

    raw = os.getenv('PHOTO_VALIDATION', DEFAULT_PHOTO_VALIDATION)
    observations = parse_photo_validation(raw)

    print('=' * 72)
    print('Walidacja fotografii pogodowych vs PV / Open-Meteo / IMGW')
    print(f'Dni z PHOTO_VALIDATION: {len(observations)}')
    print('=' * 72)

    df = build_photo_report(DB_PATH, observations)

    if df.empty:
        print('❌ Brak danych w bazie dla podanych dat.')
        print('   Uruchom: python scripts/fetch_weather.py && python scripts/fetch_imgw_snow.py')
        sys.exit(1)

    missing = set(d for d, _ in observations) - set(df['day'])
    if missing:
        print(f'⚠️  Brak danych pogodowych dla: {", ".join(sorted(missing))}')

    display = df.copy()
    if 'likely_fog_day' in display.columns:
        display['likely_fog_day'] = display['likely_fog_day'].map(
            {True: 'tak', False: 'nie', None: '—'}
        )
    print(display.to_string(index=False))

    os.makedirs(os.path.dirname(args.csv) or '.', exist_ok=True)
    df.to_csv(args.csv, index=False)
    print(f'\n✅ Zapisano: {args.csv}')
    print('\n💡 Edytuj liste dni w .env: PHOTO_VALIDATION=2025-11-21:snow,2025-12-13:sun,...')


if __name__ == '__main__':
    main()
