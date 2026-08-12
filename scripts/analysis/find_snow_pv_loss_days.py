"""
Zimowe dni: dobra pogoda (radiacja) vs bardzo niska produkcja PV — kandydaci na śnieg.

Metoda:
  - PV liczone tylko 9-16h (agregacja historyczna), bez nocnych artefaktów FoxESS.
  - UWAGA: Rzeczywista produkcja zależy od długości dnia (5-20h latem, 7-15h zimą).
  - Oczekiwana produkcja = radiacja × referencyjny yield z jasnych, czystych dni zimą.
  - Kontekst śniegu: opady przy temp. max ≤ 1°C lub opady w ostatnich 3 dniach przy mrozie.
  - Wykluczamy dni z dużym artefaktem importu (FoxESS), żeby nie mylić z ładowaniem baterii.

Uruchomienie:
    python scripts/find_snow_pv_loss_days.py
    python scripts/find_snow_pv_loss_days.py --csv data/processed/snow_pv_loss_days.csv
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

from src.data.household_context import ML_BATTERY_START
from src.data.weather_api import load_daily_pv, load_daily_pv_daytime, load_daily_weather

load_dotenv()

DB_PATH = os.getenv('DATABASE_PATH', 'data/energy_model.db')
START = os.getenv('SNOW_PV_START', ML_BATTERY_START.isoformat())
END = os.getenv('SNOW_PV_END', date.today().isoformat())
LOCATION = os.getenv('WEATHER_LOCATION')

WINTER_MONTHS = {'12', '01', '02'}
REF_CLOUD_MAX = 35
REF_RADIATION_MIN = 0.7
REF_PV_DAYTIME_MIN = 6.0
REF_ARTIFACT_MAX = 5.0
REF_NIGHT_MAX = 1.5
YIELD_RATIO_MAX = 0.40
DEFICIT_MIN_KWH = 3.0
ARTIFACT_EXCLUDE = 5.0
NIGHT_EXCLUDE = 2.0
SNOW_TEMP_MAX_C = 1.0


def _winter_mask(days: pd.Series) -> pd.Series:
    return days.str[5:7].isin(WINTER_MONTHS)


def _reference_yield(df: pd.DataFrame) -> float:
    ref = df[
        (df['cloud_cover_avg'] < REF_CLOUD_MAX)
        & (df['radiation_kwh_m2'] > REF_RADIATION_MIN)
        & (df['pv_kwh_daytime'] > REF_PV_DAYTIME_MIN)
        & (df['pv_kwh_artifact'] < REF_ARTIFACT_MAX)
        & (df['pv_kwh_night_pos'] < REF_NIGHT_MAX)
    ]
    if ref.empty:
        raise ValueError('Brak referencyjnych jasnych dni zimą — rozszerz okres analizy.')
    return (ref['pv_kwh_daytime'] / ref['radiation_kwh_m2']).median()


def build_winter_table(db_path: str, start: str, end: str, location: str | None) -> pd.DataFrame:
    weather = load_daily_weather(db_path, start, end, location)
    pv = load_daily_pv(db_path, start, end)
    daytime = load_daily_pv_daytime(db_path, start, end)

    df = weather.merge(pv, on='day').merge(daytime, on='day')
    df = df[_winter_mask(df['day'])].copy().sort_values('day').reset_index(drop=True)

    df['likely_snow_mm'] = np.where(df['temp_max'] <= SNOW_TEMP_MAX_C, df['precip_mm'], 0.0)
    df['cold_day'] = df['temp_avg'] < 2.0
    df['snow_mm_3d'] = df['likely_snow_mm'].rolling(3, min_periods=1).sum()
    df['precip_mm_3d'] = df['precip_mm'].rolling(3, min_periods=1).sum()
    df['snow_yesterday_mm'] = df['likely_snow_mm'].shift(1).fillna(0)

    ref_yield = _reference_yield(df)
    df['ref_yield_kwh_per_kwh_m2'] = ref_yield
    df['pv_expected_daytime'] = df['radiation_kwh_m2'] * ref_yield
    df['pv_deficit_kwh'] = df['pv_expected_daytime'] - df['pv_kwh_daytime']
    df['yield_ratio'] = df['pv_kwh_daytime'] / df['radiation_kwh_m2'].clip(lower=0.05)
    df['yield_pct_of_ref'] = 100 * df['yield_ratio'] / ref_yield
    df['prev_yield_pct'] = df['yield_pct_of_ref'].shift(1)

    df['is_sunny'] = (
        (df['radiation_kwh_m2'] >= 0.7)
        | ((df['cloud_cover_avg'] < 55) & (df['radiation_kwh_m2'] >= 0.5))
    )
    df['low_vs_expected'] = (
        (df['yield_pct_of_ref'] < YIELD_RATIO_MAX * 100)
        & (df['pv_deficit_kwh'] > DEFICIT_MIN_KWH)
    )
    df['snow_context'] = (
        (df['likely_snow_mm'] > 0)
        | (df['snow_mm_3d'] >= 1.0)
        | ((df['precip_mm_3d'] > 2.0) & df['cold_day'])
        | (df['snow_yesterday_mm'] > 0)
        | (
            (df['prev_yield_pct'] < 25)
            & (df['radiation_kwh_m2'] >= 0.9)
            & df['cold_day']
        )
    )
    df['foxess_clean'] = (
        (df['pv_kwh_artifact'] < ARTIFACT_EXCLUDE)
        & (df['pv_kwh_night_pos'] < NIGHT_EXCLUDE)
    )

    df['snow_confidence'] = (
        (df['likely_snow_mm'] > 0).astype(int) * 2
        + (df['snow_mm_3d'] >= 2.0).astype(int) * 2
        + (df['snow_yesterday_mm'] > 0).astype(int)
        + (df['temp_avg'] < 0).astype(int)
        + (df['cloud_cover_avg'] < 55).astype(int)
        + ((df['prev_yield_pct'] < 25) & (df['radiation_kwh_m2'] >= 0.9)).astype(int)
    )
    return df


def _display_cols() -> list[str]:
    return [
        'day', 'pv_kwh_daytime', 'pv_expected_daytime', 'pv_deficit_kwh',
        'yield_pct_of_ref', 'radiation_kwh_m2', 'cloud_cover_avg',
        'precip_mm', 'likely_snow_mm', 'snow_mm_3d', 'temp_avg',
        'snow_confidence',
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description='Zimowe dni: słońce vs brak PV (śnieg)')
    parser.add_argument('--csv', help='Zapisz wyniki do CSV')
    args = parser.parse_args()

    df = build_winter_table(DB_PATH, START, END, LOCATION)
    ref = df['ref_yield_kwh_per_kwh_m2'].iloc[0]
    ref_days = df[
        (df['cloud_cover_avg'] < REF_CLOUD_MAX)
        & (df['radiation_kwh_m2'] > REF_RADIATION_MIN)
        & (df['pv_kwh_daytime'] > REF_PV_DAYTIME_MIN)
        & (df['pv_kwh_artifact'] < REF_ARTIFACT_MAX)
    ]

    candidates = df[
        df['is_sunny'] & df['low_vs_expected'] & df['snow_context'] & df['foxess_clean']
    ].sort_values(['snow_confidence', 'pv_deficit_kwh'], ascending=False)

    all_sunny_low = df[
        df['is_sunny'] & df['low_vs_expected'] & df['foxess_clean']
    ].sort_values('pv_deficit_kwh', ascending=False)

    print('=' * 72)
    print('Zimowe dni: słońce (radiacja) vs brak produkcji PV — kandydaci na śnieg')
    print(f'Okres: {START} – {END} | dni zimowe: {len(df)}')
    print(f'Referencyjny yield (agregacja 9-16h): {ref:.2f} kWh PV / kWh/m² radiacji')
    print(f'Dni referencyjne ({len(ref_days)}):', ', '.join(ref_days['day'].tolist()))
    print('=' * 72)

    cols = _display_cols()
    labels = {
        'pv_kwh_daytime': 'pv_9_16_agg',  # agregacja historyczna
        'pv_expected_daytime': 'oczekiwane',
        'pv_deficit_kwh': 'deficyt',
        'yield_pct_of_ref': 'yield_%',
        'radiation_kwh_m2': 'radiacja',
        'cloud_cover_avg': 'chmury_%',
        'precip_mm': 'opady_mm',
        'likely_snow_mm': 'snieg_mm',
        'snow_mm_3d': 'snieg_3d',
        'temp_avg': 'temp_C',
        'snow_confidence': 'pewnosc',
    }

    print('\n🎯 Najlepsi kandydaci (słońce + niski PV + kontekst śniegu + czysty FoxESS):')
    if candidates.empty:
        print('   (brak — spróbuj rozszerzyć okres lub obniżyć progi)')
    else:
        print(candidates[cols].rename(columns=labels).to_string(index=False))

    print('\n📋 Wszystkie czyste dni: słońce ale yield < 40% normy:')
    print(all_sunny_low[cols].rename(columns=labels).to_string(index=False))

    print('\n💡 Interpretacja:')
    print('   • yield_% << 100 przy wysokiej radiacji → panele mogły być zasypane.')
    print('   • snieg_mm = opady w dniu z temp. < 2°C (proxy, nie pomiar grubości pokrywy).')
    print('   • Przykład do pracy: 2025-12-15 — radiacja 1,23 kWh/m², PV (agregacja 9-16h) tylko 1,4 kWh;')
    print('     dzień wcześniej (13 XII) przy podobnej radiacji: 10,2 kWh.')

    if args.csv:
        os.makedirs(os.path.dirname(args.csv) or '.', exist_ok=True)
        out = all_sunny_low.copy()
        candidate_days = set(candidates['day'])
        out['snow_candidate'] = out['day'].isin(candidate_days)
        out.to_csv(args.csv, index=False)
        print(f'\nZapisano: {args.csv}')


if __name__ == '__main__':
    main()
