#!/usr/bin/env python3
"""
Eksperyment (diagnostyczny): czy geometria paneli (kąt padania / POA) redukuje
niedoszacowanie na dniach jasnych jesienią?

Trening tylko < --holdout-from, ocena na dniach >= --holdout-from (pogoda z archiwum),
te same hiperparametry RF co produkcja. NIE zmienia produkcji ani modeli w models/.

Warianty: baseline (16 cech produkcji) vs +geometria (tilt/azymut z listy).
Uwaga: wybór azymutu na tym samym holdoucie to strojenie na teście — wynik służy do
diagnozy kierunku; docelowe tilt/azymut powinny pochodzić z projektu instalacji.

Użycie:
    PYTHONPATH=$PWD ./venv/bin/python scripts/analysis/experiment_panel_geometry_oos.py
"""

from __future__ import annotations

import argparse
import os
import sys
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sklearn.base import clone

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
warnings.filterwarnings('ignore')
load_dotenv(ROOT / '.env')

SUNNY_MIN_KWH = 25.0


def load_frame(start: str, end: str, lat, lon, *, panel: bool, tilt: float, az: float) -> pd.DataFrame:
    os.environ['PANEL_GEOMETRY_FEATURES'] = '1' if panel else '0'
    os.environ['PANEL_TILT_DEG'] = str(tilt)
    os.environ['PANEL_AZIMUTH_DEG'] = str(az)
    from src.features.pv_features_hourly_extended import load_hourly_training_frame_extended

    fr = load_hourly_training_frame_extended(
        start_date=start, end_date=end, latitude=lat, longitude=lon,
    )
    fr['day'] = pd.to_datetime(fr['day'])
    return fr


def evaluate(fr: pd.DataFrame, pipe, cols: list[str], target: str, hold: pd.Timestamp) -> dict:
    tr = fr[fr.day < hold]
    te = fr[fr.day >= hold].copy()
    m = clone(pipe)
    m.fit(tr[cols], tr[target])
    te['pred'] = m.predict(te[cols])
    daily = te.groupby('day').agg(act=(target, 'sum'), pred=('pred', 'sum'))
    sunny = daily[daily.act >= SUNNY_MIN_KWH]
    aft = te[te.day.isin(sunny.index) & te.hour.between(14, 16)]
    mor = te[te.day.isin(sunny.index) & te.hour.between(6, 8)]
    return {
        'MAE godz. [kWh/h]': float((te.pred - te[target]).abs().mean()),
        'WAPE dnia %': float((daily.pred - daily.act).abs().sum() / daily.act.sum() * 100),
        'bias dnia %': float((daily.pred.sum() - daily.act.sum()) / daily.act.sum() * 100),
        'n jasnych': len(sunny),
        'bias jasne %': float((sunny.pred.sum() - sunny.act.sum()) / sunny.act.sum() * 100),
        'bias 14–16h jasne %': float((aft.pred.sum() - aft[target].sum()) / aft[target].sum() * 100),
        'bias 6–8h jasne %': float((mor.pred.sum() - mor[target].sum()) / mor[target].sum() * 100),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', default=str(ROOT / 'models/pv_hourly_model.joblib'))
    ap.add_argument('--start', default='2025-06-01')
    ap.add_argument('--end', default='2026-10-04')
    ap.add_argument('--holdout-from', default='2026-09-01')
    ap.add_argument('--tilt', type=float, default=35.0)
    ap.add_argument('--azimuths', default='180,200,220')
    ap.add_argument(
        '--rf-variants', action='store_true',
        help='dodatkowo: mniej regularyzowane RF (depth/leaf) na cechach produkcji',
    )
    ap.add_argument(
        '--next-hour', action='store_true',
        help='dodatkowo: radiacja/chmury z NASTĘPNEJ godziny (hipoteza: pogoda = średnia z poprzedniej godziny)',
    )
    args = ap.parse_args()

    data = joblib.load(args.model)
    base_cols = list(data['feature_columns'])
    lat, lon = data.get('latitude'), data.get('longitude')
    from src.features.panel_geometry import PANEL_GEOMETRY_COLUMNS
    from src.models.pv_hourly_predictor import TARGET_COLUMN

    hold = pd.Timestamp(args.holdout_from)
    results: dict[str, dict] = {}

    fr0 = load_frame(args.start, args.end, lat, lon, panel=False, tilt=args.tilt, az=180)
    results['baseline (16 cech)'] = evaluate(fr0, data['pipeline'], base_cols, TARGET_COLUMN, hold)

    for az in [float(x) for x in args.azimuths.split(',')]:
        fr = load_frame(args.start, args.end, lat, lon, panel=True, tilt=args.tilt, az=az)
        cols = base_cols + [c for c in PANEL_GEOMETRY_COLUMNS if c in fr.columns]
        results[f'+geometria tilt {args.tilt:.0f}° az {az:.0f}°'] = evaluate(
            fr, data['pipeline'], cols, TARGET_COLUMN, hold,
        )

    if args.next_hour:
        fr1 = fr0.sort_values(['day', 'hour']).reset_index(drop=True)
        for col, new in (('radiation_wm2', 'rad_next'), ('cloud_cover_pct', 'cloud_next')):
            nxt = fr1[['day', 'hour', col]].copy()
            nxt['hour'] = nxt['hour'] - 1
            fr1 = fr1.merge(nxt.rename(columns={col: new}), on=['day', 'hour'], how='left')
        results['+rad_next'] = evaluate(
            fr1, data['pipeline'], base_cols + ['rad_next'], TARGET_COLUMN, hold)
        results['+rad_next +cloud_next'] = evaluate(
            fr1, data['pipeline'], base_cols + ['rad_next', 'cloud_next'], TARGET_COLUMN, hold)

    if args.rf_variants:
        for depth, leaf, split in ((6, 20, 20), (10, 10, 20), (14, 5, 10), (None, 3, 6)):
            pipe = clone(data['pipeline'])
            pipe.set_params(
                model__max_depth=depth, model__min_samples_leaf=leaf,
                model__min_samples_split=split,
            )
            results[f'RF depth={depth} leaf={leaf} split={split} (16 cech)'] = evaluate(
                fr0, pipe, base_cols, TARGET_COLUMN, hold,
            )

    print(f'\nHoldout od {args.holdout_from} (trening tylko wcześniej, pogoda z archiwum)\n')
    print(pd.DataFrame(results).T.round(2).to_string())


if __name__ == '__main__':
    main()
