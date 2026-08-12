#!/usr/bin/env python
"""
Macierz korelacji: FoxESS (wybrane sygnały) + cechy ML + opcjonalna geometria paneli.

Cel: zobaczyć, co koreluje z targetem ΔPVEnergyTotal (pv_kwh_hour),
ORAZ ostrzec przed cechami FoxESS, których NIE wolno wrzucać do modelu prognozy
(loads / SoC / grid — wyciek albo brak w przyszłości).

Uruchomienie:
    PYTHONPATH=$PWD python scripts/plot_feature_correlation.py
    PYTHONPATH=$PWD PANEL_GEOMETRY_FEATURES=1 python scripts/plot_feature_correlation.py
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
from src.features.panel_geometry import PANEL_GEOMETRY_COLUMNS, add_panel_geometry_features
from src.features.pv_features_hourly_extended import (
    HOURLY_FEATURE_COLUMNS_EXTENDED,
    HOURLY_FEATURE_COLUMNS_PRODUCTION,
    TARGET_COLUMN,
    load_hourly_training_frame_extended,
)

DB_PATH = os.getenv('DATABASE_PATH', 'data/energy_model.db')
OUT_PNG = 'reports/figures/feature_correlation_matrix.png'
OUT_CSV = 'data/processed/feature_correlation_vs_target.csv'

# Sygnały FoxESS warte eksploracji (średnia godzinowa mocy / stany)
FOXESS_POWER_MEAN = [
    'pvPower',
    'pv1Power',
    'pv2Power',
    'generationPower',
    'feedinPower',
    'gridConsumptionPower',
    'loadsPower',
    'batChargePower',
    'batDischargePower',
    'invBatPower',
    'meterPower',
    'SoC',
    'ambientTemperation',
    'invTemperation',
    'batTemperature',
]

# Nie używać jako FEATURE modelu prognozy (brak w D+1 albo wyciek z domu/baterii)
LEAKY_OR_UNAVAILABLE = {
    'pvPower', 'pv1Power', 'pv2Power', 'generationPower',  # prawie = target
    'feedinPower', 'gridConsumptionPower', 'loadsPower', 'meterPower',
    'batChargePower', 'batDischargePower', 'invBatPower', 'SoC',
}


def _load_foxess_hourly(db_path: str, start: str, end: str) -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    placeholders = ','.join('?' * len(FOXESS_POWER_MEAN))
    raw = pd.read_sql(
        f'''
        SELECT timestamp, variable, value
        FROM foxess_timeseries
        WHERE variable IN ({placeholders})
          AND date(timestamp) BETWEEN ? AND ?
        ''',
        conn,
        params=[*FOXESS_POWER_MEAN, start, end],
    )
    conn.close()
    if raw.empty:
        return pd.DataFrame()

    raw['timestamp'] = pd.to_datetime(raw['timestamp'], utc=True).dt.tz_convert('Europe/Warsaw')
    raw['day'] = raw['timestamp'].dt.strftime('%Y-%m-%d')
    raw['hour'] = raw['timestamp'].dt.hour
    wide = (
        raw.groupby(['day', 'hour', 'variable'], as_index=False)['value']
        .mean()
        .pivot(index=['day', 'hour'], columns='variable', values='value')
        .reset_index()
    )
    wide.columns.name = None
    return wide


def main() -> None:
    os.makedirs('docs', exist_ok=True)
    os.makedirs('data/processed', exist_ok=True)

    start, _ = development_date_range()
    end = DEVELOPMENT_END.isoformat()
    print(f'Okno: {start} → {end}')

    print('[1] Frame ML (pogoda + słońce + flagi)...')
    frame = load_hourly_training_frame_extended(
        DB_PATH, start, end, 'home', use_fog_flags=True,
    )
    # daylight only — jak trening
    if 'is_daylight' in frame.columns:
        frame = frame[frame['is_daylight'] == 1].copy()

    try:
        frame = add_panel_geometry_features(frame)
        has_panel = all(c in frame.columns for c in PANEL_GEOMETRY_COLUMNS)
    except Exception as exc:  # noqa: BLE001
        print(f'  ⚠️ geometria paneli pominięta: {exc}')
        has_panel = False

    print('[2] FoxESS godzinowo (średnie)...')
    fox = _load_foxess_hourly(DB_PATH, start, end)
    if fox.empty:
        raise SystemExit('Brak danych FoxESS w zakresie.')

    merged = frame.merge(fox, on=['day', 'hour'], how='inner')
    print(f'  Próbki po join: {len(merged)} godzin')

    ml_cols = [c for c in HOURLY_FEATURE_COLUMNS_EXTENDED if c in merged.columns]
    fox_cols = [c for c in FOXESS_POWER_MEAN if c in merged.columns]
    panel_cols = [c for c in PANEL_GEOMETRY_COLUMNS if c in merged.columns] if has_panel else []
    cols = [TARGET_COLUMN] + ml_cols + panel_cols + fox_cols
    cols = list(dict.fromkeys(cols))  # unique, keep order

    data = merged[cols].apply(pd.to_numeric, errors='coerce')
    # drop almost-constant / all-NaN
    keep = []
    for c in cols:
        s = data[c]
        if s.notna().sum() < 50:
            continue
        if s.std(skipna=True) == 0 or np.isnan(s.std(skipna=True)):
            continue
        keep.append(c)
    data = data[keep]

    print('[3] Korelacja Pearson...')
    corr = data.corr(method='pearson')

    # ranking vs target
    target_corr = (
        corr[TARGET_COLUMN]
        .drop(labels=[TARGET_COLUMN], errors='ignore')
        .dropna()
        .sort_values(key=lambda s: s.abs(), ascending=False)
    )
    rank = pd.DataFrame({
        'feature': target_corr.index,
        'corr_vs_pv_kwh_hour': target_corr.values,
        'abs_corr': target_corr.abs().values,
        'in_production_16': [f in HOURLY_FEATURE_COLUMNS_PRODUCTION for f in target_corr.index],
        'panel_geometry': [f in PANEL_GEOMETRY_COLUMNS for f in target_corr.index],
        'foxess_signal': [f in FOXESS_POWER_MEAN for f in target_corr.index],
        'unsafe_as_forecast_feature': [f in LEAKY_OR_UNAVAILABLE for f in target_corr.index],
    })
    rank.to_csv(OUT_CSV, index=False)
    print(f'✓ {OUT_CSV}')

    print('\n=== TOP korelacje z pv_kwh_hour (|r|) ===')
    print(rank.head(25).to_string(index=False))

    # heatmap — czytelny podzbiór: target + top ML/panel + top safe foxess labels for viz
    top_n = min(22, len(rank))
    viz_feats = [TARGET_COLUMN] + rank.head(top_n)['feature'].tolist()
    viz = corr.loc[viz_feats, viz_feats]

    fig, ax = plt.subplots(figsize=(12, 10))
    sns.heatmap(
        viz,
        annot=True,
        fmt='.2f',
        cmap='RdBu_r',
        center=0,
        vmin=-1,
        vmax=1,
        square=True,
        ax=ax,
        annot_kws={'size': 7},
        cbar_kws={'shrink': 0.7},
    )
    ax.set_title(
        f'Korelacja vs {TARGET_COLUMN} (daylight, {start}→{end})\n'
        f'Top {top_n} |r| — FoxESS + cechy ML'
        + (' + panel geometry' if panel_cols else '')
    )
    plt.xticks(rotation=45, ha='right', fontsize=8)
    plt.yticks(fontsize=8)
    plt.tight_layout()
    fig.savefig(OUT_PNG, dpi=150)
    plt.close()
    print(f'✓ {OUT_PNG}')

    # krótki werdykt
    print('\n=== Co z tego wynika ===')
    safe_candidates = rank[
        (~rank['unsafe_as_forecast_feature'])
        & (~rank['in_production_16'])
        & (rank['abs_corr'] >= 0.15)
    ]
    if len(safe_candidates):
        print('Kandydaci do eksperymentu (nie leak, nie w 16 cechach, |r|≥0.15):')
        print(safe_candidates.head(12).to_string(index=False))
    else:
        print('Brak silnych bezpiecznych kandydatów poza obecnym zestawem.')

    leaky = rank[rank['unsafe_as_forecast_feature'] & (rank['abs_corr'] >= 0.3)]
    if len(leaky):
        print('\nWysoka korelacja, ale NIE jako cecha prognozy D+1 (brak / wyciek):')
        print(leaky[['feature', 'corr_vs_pv_kwh_hour']].head(12).to_string(index=False))

    if panel_cols:
        pg = rank[rank['panel_geometry']]
        print('\nGeometria paneli (gdy włączona w frame):')
        print(pg[['feature', 'corr_vs_pv_kwh_hour']].to_string(index=False))
    else:
        print('\nGeometria: policzona nie weszła / wyłączona — spróbuj PANEL_GEOMETRY_FEATURES=1')


if __name__ == '__main__':
    main()
