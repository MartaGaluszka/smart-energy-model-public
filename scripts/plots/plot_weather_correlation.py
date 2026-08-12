#!/usr/bin/env python
"""
Macierz korelacji: WSZYSTKIE cechy z API pogodowego (Open-Meteo w weather_data)
vs target ΔPVEnergyTotal (pv_kwh_hour).

Źródło: kolumny faktycznie pobierane w HOURLY_VARS / zapisywane w SQLite.
pressure_hpa i sunshine_duration_min są w schemacie, ale API ich nie ładuje → odpadną.

Uruchomienie:
    PYTHONPATH=$PWD python scripts/plot_weather_correlation.py
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.data.household_context import DEVELOPMENT_END, development_date_range
from src.features.pv_features_hourly_extended import (
    HOURLY_FEATURE_COLUMNS_PRODUCTION,
    TARGET_COLUMN,
    load_hourly_training_frame_extended,
)

DB_PATH = os.getenv('DATABASE_PATH', 'data/energy_model.db')
OUT_PNG = 'reports/figures/weather_correlation_matrix.png'
OUT_CSV = 'data/processed/weather_correlation_vs_target.csv'

# Wszystkie numeryczne pola pogodowe w DB (= to, co Open-Meteo u Was zapisuje)
WEATHER_COLUMNS = [
    'temperature_celsius',
    'humidity_percent',
    'pressure_hpa',
    'solar_radiation_wm2',
    'sunshine_duration_min',
    'cloud_cover_percent',
    'cloud_cover_low_percent',
    'cloud_cover_mid_percent',
    'cloud_cover_high_percent',
    'visibility_m',
    'wind_speed_ms',
    'wind_direction_deg',
    'precipitation_mm',
    'snowfall_cm',
    'snow_depth_m',
]

# Mapowanie DB → nazwa w modelu produkcyjnym (jeśli jest)
DB_TO_MODEL = {
    'temperature_celsius': 'temp_c',
    'humidity_percent': 'humidity_pct',
    'solar_radiation_wm2': 'radiation_wm2',
    'cloud_cover_percent': 'cloud_cover_pct',
    'wind_speed_ms': 'wind_speed_ms',
}


def _load_weather_hourly(db_path: str, start: str, end: str) -> pd.DataFrame:
    """Godzina jak w load_hourly_training_frame_extended (strftime na timestamp z DB — bez tz shift)."""
    avgs = ', '.join(f'AVG({c}) AS {c}' for c in WEATHER_COLUMNS)
    conn = sqlite3.connect(db_path)
    df = pd.read_sql(
        f'''
        SELECT
            DATE(timestamp) AS day,
            CAST(strftime('%H', timestamp) AS INTEGER) AS hour,
            {avgs}
        FROM weather_data
        WHERE location = 'home'
          AND data_source LIKE '%archive%'
          AND DATE(timestamp) BETWEEN ? AND ?
          AND CAST(strftime('%H', timestamp) AS INTEGER) BETWEEN 5 AND 21
        GROUP BY DATE(timestamp), hour
        ORDER BY day, hour
        ''',
        conn,
        params=(start, end),
    )
    conn.close()
    return df


def main() -> None:
    os.makedirs('docs', exist_ok=True)
    os.makedirs('data/processed', exist_ok=True)

    start, _ = development_date_range()
    end = DEVELOPMENT_END.isoformat()
    print(f'Okno: {start} → {end} | źródło: OpenMeteo-archive')

    print('[1] Target PV + daylight (jak frame treningowy)...')
    frame = load_hourly_training_frame_extended(
        DB_PATH, start, end, 'home', use_fog_flags=False, use_snow_melt=False,
    )
    frame = frame[frame['is_daylight'] == 1].copy()

    print('[2] Wszystkie kolumny pogodowe (archive)...')
    weather = _load_weather_hourly(DB_PATH, start, end)
    if weather.empty:
        raise SystemExit('Brak weather_data archive w zakresie.')

    merged = frame[['day', 'hour', TARGET_COLUMN]].merge(weather, on=['day', 'hour'], how='inner')
    print(f'  Join: {len(merged)} godzin')
    # sanity: radiacja z frame vs raw weather
    if 'radiation_wm2' in frame.columns:
        check = frame[['day', 'hour', 'radiation_wm2']].merge(
            weather[['day', 'hour', 'solar_radiation_wm2']], on=['day', 'hour'],
        )
        r = check['radiation_wm2'].corr(check['solar_radiation_wm2'])
        print(f'  Sanity radiation_wm2 vs solar_radiation_wm2: r={r:.3f} (oczekiwane ≈1.0)')

    data = merged[[TARGET_COLUMN] + WEATHER_COLUMNS].apply(pd.to_numeric, errors='coerce')
    usable = [TARGET_COLUMN]
    dropped = []
    for c in WEATHER_COLUMNS:
        s = data[c]
        n = int(s.notna().sum())
        std = float(s.std(skipna=True)) if n else float('nan')
        if n < 50 or not np.isfinite(std) or std == 0:
            dropped.append((c, n, std))
            continue
        usable.append(c)
    data = data[usable]

    if dropped:
        print('\nPominięte (brak danych / stała):')
        for c, n, std in dropped:
            print(f'  - {c}: n_valid={n}, std={std}')

    print('[3] Korelacja Pearson...')
    corr = data.corr(method='pearson')

    target_corr = (
        corr[TARGET_COLUMN]
        .drop(labels=[TARGET_COLUMN], errors='ignore')
        .dropna()
        .sort_values(key=lambda s: s.abs(), ascending=False)
    )

    rank = pd.DataFrame({
        'weather_feature': target_corr.index,
        'corr_vs_pv_kwh_hour': target_corr.values,
        'abs_corr': target_corr.abs().values,
        'in_production_model': [
            DB_TO_MODEL.get(f, f) in HOURLY_FEATURE_COLUMNS_PRODUCTION
            for f in target_corr.index
        ],
        'model_name': [DB_TO_MODEL.get(f, '') for f in target_corr.index],
    })
    rank.to_csv(OUT_CSV, index=False)
    print(f'✓ {OUT_CSV}')

    print('\n=== Ranking vs pv_kwh_hour ===')
    print(rank.to_string(index=False))

    # pełna macierz wszystkich użytecznych cech pogodowych
    fig, ax = plt.subplots(figsize=(11, 9))
    sns.heatmap(
        corr,
        annot=True,
        fmt='.2f',
        cmap='RdBu_r',
        center=0,
        vmin=-1,
        vmax=1,
        square=True,
        ax=ax,
        annot_kws={'size': 8},
        cbar_kws={'shrink': 0.75},
    )
    ax.set_title(
        f'Korelacja cech Open-Meteo vs {TARGET_COLUMN}\n'
        f'daylight · archive · {start} → {end}'
    )
    plt.xticks(rotation=45, ha='right', fontsize=8)
    plt.yticks(fontsize=8)
    plt.tight_layout()
    fig.savefig(OUT_PNG, dpi=150)
    plt.close()
    print(f'✓ {OUT_PNG}')

    print('\n=== Werdykt ===')
    not_in_model = rank[(~rank['in_production_model']) & (rank['abs_corr'] >= 0.15)]
    if len(not_in_model):
        print('W API / DB, ale NIE w 16 cechach produkcyjnych (|r|≥0.15):')
        print(not_in_model.to_string(index=False))
    else:
        print('Brak silnych cech pogodowych poza produkcyjnymi (|r|≥0.15).')

    in_model = rank[rank['in_production_model']]
    print('\nJuż w modelu (16 cech):')
    print(in_model.to_string(index=False))


if __name__ == '__main__':
    main()
