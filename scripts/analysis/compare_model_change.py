#!/usr/bin/env python
"""
Porównanie zmiany ML — offline + operacyjnie (protokół pracy dyplomowej).

Porównuje baseline vs kandydat na tych samych metrykach i proponuje decyzję:
  ACCEPT  — brak regresji (Test MAE w tolerancji, operacyjnie OK)
  REVIEW  — remis offline, mieszany wynik operacyjny
  REJECT  — wyraźna regresja Test MAE lub operacyjnego MAE

Przykłady:
    # Dwa pliki CSV z train_hourly_model_tuning.py
    python scripts/compare_model_change.py \\
        --change "Expanding window" \\
        --baseline data/processed/hourly_model_tuning_summary.csv \\
        --candidate data/processed/hourly_model_tuning_summary_production.csv

    # Ten sam split, dwa modele .joblib (wolniejsze, uczciwe offline)
    python scripts/compare_model_change.py \\
        --change "Retrening lipiec" \\
        --baseline-model models/pv_hourly_model_19.joblib \\
        --candidate-model models/pv_hourly_model.joblib \\
        --train-start 2025-06-01 --train-end 2026-07-15

    # Dopisz wiersz do docs/CHANGELOG_ML.md
    python scripts/compare_model_change.py ... --append-changelog
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

load_dotenv()

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

from src.features.pv_features_hourly_extended import (
    HOURLY_FEATURE_COLUMNS_PRODUCTION,
    TARGET_COLUMN,
    load_hourly_training_frame_extended,
)
from src.models.forecast_validation import VALIDATION_FILE

CHANGELOG = 'docs/CHANGELOG_ML.md'
SPLIT_RANDOM_STATE = 42
TEST_MAE_TOLERANCE = 0.02  # kWh/h — remis w granicy szumu
OPERATIONAL_TOLERANCE = 0.15  # +15% MAE operacyjnego = regresja


def _read_summary(path: str) -> dict:
    row = pd.read_csv(path).iloc[0].to_dict()
    return {
        'source': path,
        'train_start': row.get('train_start', ''),
        'train_end': row.get('train_end', ''),
        'test_mae': float(row.get('test_mae_hour', row.get('test_mae', np.nan))),
        'train_mae': float(row.get('train_mae_hour', row.get('train_mae', np.nan))),
        'gap': float(row.get('gap', np.nan)),
        'test_r2': float(row.get('test_r2_hour', row.get('test_r2', np.nan))),
        'daily_mae': float(row.get('daily_mae', np.nan)),
        'daily_r2': float(row.get('daily_r2', np.nan)),
        'n_features': row.get('n_features', row.get('feature_set', '')),
    }


def _evaluate_joblib(
    model_path: str,
    train_start: str,
    train_end: str,
) -> dict:
    lat = float(os.getenv('WEATHER_LAT', '50.06'))
    lon = float(os.getenv('WEATHER_LON', '19.94'))
    frame = load_hourly_training_frame_extended(
        start_date=train_start,
        end_date=train_end,
        latitude=lat,
        longitude=lon,
    )
    days = frame['day'].unique()
    train_days, test_days = train_test_split(
        days, test_size=0.2, random_state=SPLIT_RANDOM_STATE, shuffle=True,
    )
    tr = frame[frame['day'].isin(train_days)]
    te = frame[frame['day'].isin(test_days)]
    bundle = joblib.load(model_path)
    pipe = bundle['pipeline'] if isinstance(bundle, dict) else bundle
    feature_cols = (
        bundle.get('feature_columns', HOURLY_FEATURE_COLUMNS_PRODUCTION)
        if isinstance(bundle, dict)
        else HOURLY_FEATURE_COLUMNS_PRODUCTION
    )
    Xtr = tr[feature_cols]
    ytr = tr[TARGET_COLUMN]
    Xte = te[feature_cols]
    yte = te[TARGET_COLUMN]
    tr_p = pipe.predict(Xtr)
    te_p = pipe.predict(Xte)
    train_mae = mean_absolute_error(ytr, tr_p)
    test_mae = mean_absolute_error(yte, te_p)
    te_meta = te[['day', TARGET_COLUMN]].copy()
    te_meta['pred'] = te_p
    daily = te_meta.groupby('day').agg(actual=(TARGET_COLUMN, 'sum'), pred=('pred', 'sum'))
    return {
        'source': model_path,
        'train_start': train_start,
        'train_end': train_end,
        'test_mae': test_mae,
        'train_mae': train_mae,
        'gap': test_mae - train_mae,
        'test_r2': r2_score(yte, te_p),
        'daily_mae': mean_absolute_error(daily['actual'], daily['pred']),
        'daily_r2': r2_score(daily['actual'], daily['pred']),
        'n_features': len(feature_cols),
    }


def _operational_mae(days: int) -> dict:
    path = VALIDATION_FILE
    if not os.path.exists(path):
        return {}
    df = pd.read_csv(path)
    if df.empty:
        return {}
    df = df.sort_values('closeout_at').drop_duplicates('target_day', keep='last')
    df = df.tail(days)
    out = {'n_days': len(df)}
    for col, key in [
        ('error_vs_daily_kwh', 'mae_daily'),
        ('error_vs_midday_kwh', 'mae_midday'),
        ('best_snapshot_error_kwh', 'mae_best'),
    ]:
        if col in df.columns:
            errs = pd.to_numeric(df[col], errors='coerce').abs().dropna()
            if len(errs):
                out[key] = float(errs.mean())
    return out


def _delta(a: float | None, b: float | None) -> str:
    if a is None or b is None or (isinstance(a, float) and np.isnan(a)) or (isinstance(b, float) and np.isnan(b)):
        return '—'
    d = b - a
    sign = '+' if d >= 0 else ''
    return f'{sign}{d:.3f}'


def _decide(
    base: dict,
    cand: dict,
    op_base: dict | None,
    op_cand: dict | None,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    d_test = cand['test_mae'] - base['test_mae']
    if d_test > TEST_MAE_TOLERANCE:
        reasons.append(f'Test MAE +{d_test:.3f} (> {TEST_MAE_TOLERANCE})')
        return 'REJECT', reasons
    if d_test <= 0:
        reasons.append(f'Test MAE poprawione o {abs(d_test):.3f}')
    else:
        reasons.append(f'Test MAE remis (+{d_test:.3f} ≤ {TEST_MAE_TOLERANCE})')

    if not np.isnan(base.get('gap', np.nan)) and not np.isnan(cand.get('gap', np.nan)):
        if cand['gap'] < base['gap'] - 0.02:
            reasons.append(f'Gap spadł ({base["gap"]:.3f} → {cand["gap"]:.3f})')

    if op_base and op_cand and 'mae_best' in op_base and 'mae_best' in op_cand:
        b, c = op_base['mae_best'], op_cand['mae_best']
        if b > 0 and (c - b) / b > OPERATIONAL_TOLERANCE:
            reasons.append(f'Operacyjny MAE +{(c - b) / b * 100:.0f}%')
            return 'REJECT', reasons
        if c <= b:
            reasons.append(f'Operacyjny MAE {b:.2f} → {c:.2f} kWh/d')

    if d_test > 0:
        return 'REVIEW', reasons
    return 'ACCEPT', reasons


def _format_report(
    change: str,
    base: dict,
    cand: dict,
    op: dict,
    decision: str,
    reasons: list[str],
) -> str:
    lines = [
        f'## {change} — {date.today().isoformat()}',
        '',
        '| Metryka | Baseline | Kandydat | Δ |',
        '|---------|----------|----------|---|',
        f'| Okno treningowe | {base.get("train_start", "?")} → {base.get("train_end", "?")} '
        f'| {cand.get("train_start", "?")} → {cand.get("train_end", "?")} | |',
        f'| Test MAE [kWh/h] | {base["test_mae"]:.3f} | {cand["test_mae"]:.3f} | {_delta(base["test_mae"], cand["test_mae"])} |',
        f'| Gap | {base["gap"]:.3f} | {cand["gap"]:.3f} | {_delta(base["gap"], cand["gap"])} |',
        f'| Test R² | {base["test_r2"]:.3f} | {cand["test_r2"]:.3f} | {_delta(base["test_r2"], cand["test_r2"])} |',
        f'| Daily MAE [kWh/d] | {base["daily_mae"]:.2f} | {cand["daily_mae"]:.2f} | {_delta(base["daily_mae"], cand["daily_mae"])} |',
        f'| Źródło | `{os.path.basename(str(base.get("source", "")))}` | '
        f'`{os.path.basename(str(cand.get("source", "")))}` | |',
    ]
    if op:
        lines.extend([
            '',
            '**Operacyjnie** (forecast_validation.csv):',
            f'- dni: {op.get("n_days", 0)}',
        ])
        for k, label in [('mae_daily', 'MAE daily 5:00'), ('mae_midday', 'MAE midday'), ('mae_best', 'MAE best snapshot')]:
            if k in op:
                lines.append(f'- {label}: **{op[k]:.2f} kWh/d**')
    lines.extend([
        '',
        f'**Decyzja: {decision}**',
        '',
        'Uzasadnienie:',
        *[f'- {r}' for r in reasons],
        '',
        '---',
        '',
    ])
    return '\n'.join(lines)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description='Porównaj zmianę ML (baseline vs kandydat)')
    p.add_argument('--change', required=True, help='Krótka nazwa zmiany (np. "Expanding window")')
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--baseline', help='CSV z hourly_model_tuning_summary*.csv (baseline)')
    g.add_argument('--baseline-model', help='Ścieżka .joblib baseline')
    g2 = p.add_mutually_exclusive_group(required=True)
    g2.add_argument('--candidate', help='CSV kandydata')
    g2.add_argument('--candidate-model', help='Ścieżka .joblib kandydata')
    p.add_argument('--train-start', default='2025-06-01', help='Okno offline (modele .joblib)')
    p.add_argument('--train-end', default=None, help='Koniec okna (domyślnie auto z env)')
    p.add_argument('--operational-days', type=int, default=14, help='Ostatnie N dni walidacji operacyjnej')
    p.add_argument('--append-changelog', action='store_true', help=f'Dopisz raport do {CHANGELOG}')
    return p.parse_args()


def main() -> None:
    args = parse_args()

    if args.train_end is None:
        from src.models.ml_train_window import resolve_train_window
        _, args.train_end = resolve_train_window()

    if args.baseline:
        base = _read_summary(args.baseline)
    else:
        print(f'[offline] Ewaluacja baseline: {args.baseline_model}')
        base = _evaluate_joblib(args.baseline_model, args.train_start, args.train_end)

    if args.candidate:
        cand = _read_summary(args.candidate)
    else:
        print(f'[offline] Ewaluacja kandydat: {args.candidate_model}')
        cand = _evaluate_joblib(args.candidate_model, args.train_start, args.train_end)

    op = _operational_mae(args.operational_days)
    decision, reasons = _decide(base, cand, None, None)
    report = _format_report(args.change, base, cand, op, decision, reasons)
    print(report)

    if args.append_changelog:
        os.makedirs(os.path.dirname(CHANGELOG), exist_ok=True)
        header = (
            '# Changelog ML — porównania zmian\n\n'
            'Protokół: każda zmiana porównywana z baseline; **REJECT** gdy Test MAE '
            f'>{TEST_MAE_TOLERANCE} kWh/h lub operacyjny MAE +{OPERATIONAL_TOLERANCE * 100:.0f}%.\n\n'
            'Generowanie: `python scripts/compare_model_change.py ... --append-changelog`\n\n'
            '---\n\n'
        )
        if not os.path.exists(CHANGELOG):
            with open(CHANGELOG, 'w', encoding='utf-8') as f:
                f.write(header)
        with open(CHANGELOG, 'a', encoding='utf-8') as f:
            f.write(report)
        print(f'✓ Dopisano do {CHANGELOG}')


if __name__ == '__main__':
    main()
