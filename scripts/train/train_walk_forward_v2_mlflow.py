#!/usr/bin/env python
"""
Walk-forward v2 (dopracowanie pod prezentację 7.08 / Lekcja 38).

Ulepszenia vs v1 (miesięczny expanding):
  1) krok: monthly | weekly (weekly ≈ niedzielny retrain)
  2) okno train: expanding | rolling12 (ostatnie 12 miesięcy)
  3) werdykt gap per fold + metryki peak / high-day (≥30 kWh)
  4) wykresy do prezentacji w reports/figures/

Uruchomienie:
    # pełne porównanie expanding vs rolling12 (miesięcznie) + weekly od 2026-03
    python scripts/train/train_walk_forward_v2_mlflow.py --mlflow

    # tylko monthly expanding (jak v1, szybciej)
    python scripts/train/train_walk_forward_v2_mlflow.py --step monthly --train-window expanding
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / '.env')
os.environ.setdefault('MPLCONFIGDIR', '/tmp/mpl')
os.environ.setdefault('MPLBACKEND', 'Agg')

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score

from scripts.train.train_holdout_and_ts_mlflow import (
    PEAK_HOURS,
    TS_FEATURE_COLUMNS,
    _rf_pipe,
    _xgb_pipe,
    add_nwp_time_series_features,
)
from scripts.train.train_hourly_model_tuning import MLFLOW_EXPERIMENT
from src.features.pv_features_hourly_extended import (
    HOURLY_FEATURE_COLUMNS_PRODUCTION,
    TARGET_COLUMN,
    load_hourly_training_frame_extended,
)
from src.models.pv_hourly_predictor import _metrics
from src.models.topk_metrics import topk_hour_metrics

MIN_TRAIN_DAYS = 90
ROLLING_MONTHS = 12
FIGURES = ROOT / 'reports' / 'figures'
PROCESSED = ROOT / 'data' / 'processed'


def _gap_verdict(gap: float) -> str:
    if gap < 0.15:
        return 'ok'
    if gap < 0.35:
        return 'lekkie'
    return 'przeuczony'


def _fold_labels(days: pd.Series, step: str) -> list[tuple[str, str, str]]:
    """Lista (fold_id, test_start, test_end)."""
    unique = pd.to_datetime(sorted(days.astype(str).unique()))
    out: list[tuple[str, str, str]] = []
    if step == 'monthly':
        months = sorted({d.to_period('M') for d in unique})[1:]
        for m in months:
            out.append((str(m), m.start_time.date().isoformat(), m.end_time.date().isoformat()))
    else:  # weekly — tygodnie kalendarzowe (pon–niedz), test = ten tydzień
        weeks = sorted({d.to_period('W-SUN') for d in unique})
        for w in weeks[4:]:  # pomijamy pierwsze tygodnie (za mało historii)
            start = w.start_time.date().isoformat()
            end = w.end_time.date().isoformat()
            out.append((str(w), start, end))
    return out


def _train_mask(frame: pd.DataFrame, test_start: str, train_window: str) -> pd.Series:
    before = frame['day'] < test_start
    if train_window == 'expanding':
        return before
    # rolling 12 miesięcy wstecz od test_start
    cut = (pd.Timestamp(test_start) - pd.DateOffset(months=ROLLING_MONTHS)).date().isoformat()
    return before & (frame['day'] >= cut)


def _eval_fold(pipe, frame, cols, train_mask, test_mask) -> dict:
    X_tr = frame.loc[train_mask, cols]
    y_tr = frame.loc[train_mask, TARGET_COLUMN]
    X_te = frame.loc[test_mask, cols]
    y_te = frame.loc[test_mask, TARGET_COLUMN]
    meta = frame.loc[test_mask, ['day', 'hour']].copy()

    pipe.fit(X_tr, y_tr)
    pred_tr = pipe.predict(X_tr)
    pred_te = pipe.predict(X_te)
    tr = _metrics(y_tr, pred_tr)
    te = _metrics(y_te, pred_te)
    gap = te['mae'] - tr['mae']

    meta['y_true'] = y_te.values
    meta['y_pred'] = pred_te
    meta['abs_err'] = (meta['y_true'] - meta['y_pred']).abs()
    daily_true = meta.groupby('day')['y_true'].sum()
    daily_pred = meta.groupby('day')['y_pred'].sum()
    peak = meta[meta['hour'].isin(PEAK_HOURS)]
    high_days = daily_true[daily_true >= 30].index
    high = meta[meta['day'].isin(high_days)]
    topk = topk_hour_metrics(meta, k=5)

    return {
        'train_mae': tr['mae'],
        'test_mae': te['mae'],
        'gap': gap,
        'gap_verdict': _gap_verdict(gap),
        'daily_mae': mean_absolute_error(daily_true, daily_pred),
        'daily_r2': r2_score(daily_true, daily_pred) if len(daily_true) > 1 else float('nan'),
        'peak_mae': float(peak['abs_err'].mean()) if len(peak) else float('nan'),
        'high_day_mae': float(high['abs_err'].mean()) if len(high) else float('nan'),
        'topk_hit_rate': topk['topk_hit_rate'],
        'peak_in_topk': topk['peak_in_topk'],
        'peak_hour_exact': topk['peak_hour_exact'],
        'n_train_days': int(frame.loc[train_mask, 'day'].nunique()),
        'n_test_days': int(frame.loc[test_mask, 'day'].nunique()),
        'n_high_days': int(len(high_days)),
    }


def run_walk_forward(
    *,
    name: str,
    frame: pd.DataFrame,
    cols: list[str],
    make_pipe,
    step: str,
    train_window: str,
    weekly_from: str | None,
    log_mlflow: bool,
) -> pd.DataFrame:
    frame = frame.copy()
    frame['day'] = frame['day'].astype(str)
    folds = _fold_labels(frame['day'], step)
    rows = []
    print(f'\n{"=" * 72}')
    print(f'WF v2 | {name} | step={step} | train={train_window} | folds={len(folds)}')
    print('=' * 72)

    for fold_id, start, end in folds:
        if step == 'weekly' and weekly_from and start < weekly_from:
            continue
        tr_mask = _train_mask(frame, start, train_window)
        te_mask = (frame['day'] >= start) & (frame['day'] <= end)
        n_train_days = frame.loc[tr_mask, 'day'].nunique()
        n_test_h = int(te_mask.sum())
        min_test_h = 20 if step == 'monthly' else 8
        if n_train_days < MIN_TRAIN_DAYS or n_test_h < min_test_h:
            continue

        ev = _eval_fold(make_pipe(), frame, cols, tr_mask, te_mask)
        print(
            f'  {fold_id}: train_d={ev["n_train_days"]:3d} test_d={ev["n_test_days"]:2d} '
            f'test={ev["test_mae"]:.3f} gap={ev["gap"]:+.3f}({ev["gap_verdict"]}) '
            f'peak={ev["peak_mae"]:.3f} high={ev["high_day_mae"]:.3f} '
            f'top5={ev["topk_hit_rate"]:.2f}'
        )
        rows.append({
            'model': name,
            'step': step,
            'train_window': train_window,
            'fold_id': fold_id,
            'test_start': start,
            'test_end': end,
            **ev,
        })

        if log_mlflow:
            import mlflow
            mlflow.set_experiment(MLFLOW_EXPERIMENT)
            with mlflow.start_run(run_name=f'wf2_{name}_{train_window}_{fold_id}'):
                mlflow.log_params({
                    'split': f'walk_forward_v2_{step}',
                    'train_window': train_window,
                    'fold_id': fold_id,
                    'model_name': name,
                    'n_features': len(cols),
                })
                mlflow.log_metrics({
                    'train_mae': ev['train_mae'],
                    'test_mae': ev['test_mae'],
                    'gap': ev['gap'],
                    'daily_mae': ev['daily_mae'],
                    'peak_mae': ev['peak_mae'],
                    'high_day_mae': ev['high_day_mae'] if np.isfinite(ev['high_day_mae']) else 0.0,
                })
                mlflow.set_tag('gap_verdict', ev['gap_verdict'])
                mlflow.set_tag('split', f'walk_forward_v2_{step}')

    return pd.DataFrame(rows)


def plot_results(df: pd.DataFrame) -> list[Path]:
    FIGURES.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    # 1) monthly expanding: test MAE vs miesiąc (RF vs XGB+TS)
    monthly = df[(df['step'] == 'monthly') & (df['train_window'] == 'expanding')].copy()
    if not monthly.empty:
        fig, ax = plt.subplots(figsize=(11, 4.5))
        for model, style in [('rf_production', '-o'), ('xgb_production_ts', '-s')]:
            sub = monthly[monthly['model'] == model].sort_values('fold_id')
            if sub.empty:
                continue
            ax.plot(sub['fold_id'], sub['test_mae'], style, label=model, linewidth=2, markersize=6)
        ax.axhline(0.5, color='gray', linestyle='--', alpha=0.7, label='cel 0.5 kWh/h')
        ax.set_title('Walk-forward miesięczny (expanding) — test MAE')
        ax.set_ylabel('MAE [kWh/h]')
        ax.set_xlabel('Miesiąc testowy')
        ax.tick_params(axis='x', rotation=45)
        ax.grid(True, alpha=0.3)
        ax.legend()
        fig.tight_layout()
        p = FIGURES / 'walk_forward_v2_monthly_mae.png'
        fig.savefig(p, dpi=120)
        plt.close(fig)
        paths.append(p)

    # 2) expanding vs rolling12 — średnie
    cmp = (
        df[df['step'] == 'monthly']
        .groupby(['model', 'train_window'], as_index=False)
        .agg(test_mae=('test_mae', 'mean'), gap=('gap', 'mean'), peak_mae=('peak_mae', 'mean'),
             high_day_mae=('high_day_mae', 'mean'))
    )
    if not cmp.empty:
        fig, axes = plt.subplots(1, 2, figsize=(11, 4))
        models = sorted(cmp['model'].unique())
        x = np.arange(len(models))
        width = 0.35
        for ax, metric, title in [
            (axes[0], 'test_mae', 'Średni test MAE'),
            (axes[1], 'peak_mae', 'Średni peak MAE (10–16)'),
        ]:
            exp = [cmp[(cmp['model'] == m) & (cmp['train_window'] == 'expanding')][metric].mean() for m in models]
            rol = [cmp[(cmp['model'] == m) & (cmp['train_window'] == 'rolling12')][metric].mean() for m in models]
            ax.bar(x - width / 2, exp, width, label='expanding', color='#4e79a7')
            ax.bar(x + width / 2, rol, width, label='rolling 12m', color='#f28e2b')
            ax.set_xticks(x)
            ax.set_xticklabels(models, rotation=15, ha='right')
            ax.set_title(title)
            ax.grid(True, axis='y', alpha=0.3)
            ax.legend()
        fig.suptitle('Walk-forward v2: expanding vs rolling 12 miesięcy', fontweight='bold')
        fig.tight_layout()
        p = FIGURES / 'walk_forward_v2_expanding_vs_rolling12.png'
        fig.savefig(p, dpi=120)
        plt.close(fig)
        paths.append(p)

    # 3) weekly — ostatnie foldy
    weekly = df[df['step'] == 'weekly'].copy()
    if not weekly.empty:
        fig, ax = plt.subplots(figsize=(12, 4.5))
        for model, style in [('rf_production', '-o'), ('xgb_production_ts', '-s')]:
            sub = weekly[weekly['model'] == model].sort_values('test_start')
            if sub.empty:
                continue
            ax.plot(sub['test_start'], sub['test_mae'], style, label=model, linewidth=1.8, markersize=5)
        ax.set_title('Walk-forward tygodniowy (jak niedzielny retrain) — test MAE')
        ax.set_ylabel('MAE [kWh/h]')
        ax.tick_params(axis='x', rotation=45)
        ax.grid(True, alpha=0.3)
        ax.legend()
        fig.tight_layout()
        p = FIGURES / 'walk_forward_v2_weekly_mae.png'
        fig.savefig(p, dpi=120)
        plt.close(fig)
        paths.append(p)

    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description='Walk-forward v2')
    parser.add_argument('--mlflow', action='store_true')
    parser.add_argument('--step', choices=['monthly', 'weekly', 'both'], default='both')
    parser.add_argument(
        '--train-window',
        choices=['expanding', 'rolling12', 'both'],
        default='both',
        help='Okno treningu przed każdym foldem',
    )
    parser.add_argument('--weekly-from', default='2026-03-01', help='Pierwszy tydzień (YYYY-MM-DD)')
    parser.add_argument('--models', default='rf,xgb_ts', help='rf,xgb_ts')
    args = parser.parse_args()

    lat = float(os.getenv('WEATHER_LAT', '50.06'))
    lon = float(os.getenv('WEATHER_LON', '19.94'))

    print('[1] Ramka ICON + cechy TS...')
    frame = load_hourly_training_frame_extended(
        start_date='2025-06-01', end_date='2026-07-28', latitude=lat, longitude=lon,
    )
    frame = add_nwp_time_series_features(frame)

    model_specs = []
    wanted = {m.strip() for m in args.models.split(',') if m.strip()}
    if 'rf' in wanted:
        model_specs.append(('rf_production', HOURLY_FEATURE_COLUMNS_PRODUCTION, _rf_pipe))
    if 'xgb_ts' in wanted:
        model_specs.append((
            'xgb_production_ts',
            HOURLY_FEATURE_COLUMNS_PRODUCTION + TS_FEATURE_COLUMNS,
            _xgb_pipe,
        ))

    steps = ['monthly', 'weekly'] if args.step == 'both' else [args.step]
    windows = ['expanding', 'rolling12'] if args.train_window == 'both' else [args.train_window]

    parts = []
    for step in steps:
        for train_window in windows:
            # weekly + rolling12 wystarczy expanding dla czytelności prezentacji? robimy oba
            for name, cols, make_pipe in model_specs:
                parts.append(
                    run_walk_forward(
                        name=name,
                        frame=frame,
                        cols=cols,
                        make_pipe=make_pipe,
                        step=step,
                        train_window=train_window,
                        weekly_from=args.weekly_from if step == 'weekly' else None,
                        log_mlflow=args.mlflow,
                    )
                )

    summary = pd.concat([p for p in parts if not p.empty], ignore_index=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    out = PROCESSED / 'walk_forward_v2.csv'
    summary.to_csv(out, index=False)

    print('\n' + '=' * 72)
    print('PODSUMOWANIE WF v2 (średnie po foldach)')
    print('=' * 72)
    agg = (
        summary.groupby(['model', 'step', 'train_window'], as_index=False)
        .agg(
            folds=('fold_id', 'count'),
            test_mae=('test_mae', 'mean'),
            gap=('gap', 'mean'),
            peak_mae=('peak_mae', 'mean'),
            high_day_mae=('high_day_mae', 'mean'),
            n_przeuczony=('gap_verdict', lambda s: int((s == 'przeuczony').sum())),
            n_lekkie=('gap_verdict', lambda s: int((s == 'lekkie').sum())),
            n_ok=('gap_verdict', lambda s: int((s == 'ok').sum())),
        )
        .sort_values(['step', 'test_mae'])
    )
    print(agg.to_string(index=False))
    agg_path = PROCESSED / 'walk_forward_v2_summary.csv'
    agg.to_csv(agg_path, index=False)

    paths = plot_results(summary)
    print('\nWykresy:')
    for p in paths:
        print(f'  ✓ {p}')

    if args.mlflow:
        import mlflow
        mlflow.set_experiment(MLFLOW_EXPERIMENT)
        # jeden run na wariant — wygodne porównanie w UI (Compare)
        for _, r in agg.iterrows():
            run_name = f"wf2_summary_{r['model']}_{r['step']}_{r['train_window']}"
            with mlflow.start_run(run_name=run_name):
                mlflow.log_params({
                    'split': 'walk_forward_v2_variant_summary',
                    'model_name': r['model'],
                    'step': r['step'],
                    'train_window': r['train_window'],
                    'n_folds': int(r['folds']),
                })
                mlflow.log_metrics({
                    'test_mae': float(r['test_mae']),
                    'gap': float(r['gap']),
                    'peak_mae': float(r['peak_mae']),
                    'high_day_mae': float(r['high_day_mae']) if pd.notna(r['high_day_mae']) else 0.0,
                    'n_przeuczony': float(r['n_przeuczony']),
                    'n_lekkie': float(r['n_lekkie']),
                    'n_ok': float(r['n_ok']),
                })
                mlflow.set_tag('split', 'walk_forward_v2_variant_summary')
                mlflow.set_tag('model_name', r['model'])
                mlflow.set_tag('step', r['step'])
                mlflow.set_tag('train_window', r['train_window'])
                mlflow.log_artifact(str(out))
                mlflow.log_artifact(str(agg_path))
                for p in paths:
                    mlflow.log_artifact(str(p))
        with mlflow.start_run(run_name='wf2_summary_all'):
            mlflow.log_param('split', 'walk_forward_v2_summary')
            mlflow.log_artifact(str(out))
            mlflow.log_artifact(str(agg_path))
            for p in paths:
                mlflow.log_artifact(str(p))
            row = agg[(agg['model'] == 'rf_production') & (agg['step'] == 'monthly') & (agg['train_window'] == 'expanding')]
            if not row.empty:
                mlflow.log_metrics({
                    'rf_monthly_expanding_test_mae': float(row.iloc[0]['test_mae']),
                    'rf_monthly_expanding_peak_mae': float(row.iloc[0]['peak_mae']),
                })
            row2 = agg[(agg['model'] == 'xgb_production_ts') & (agg['step'] == 'monthly') & (agg['train_window'] == 'expanding')]
            if not row2.empty:
                mlflow.log_metrics({
                    'xgb_ts_monthly_expanding_test_mae': float(row2.iloc[0]['test_mae']),
                    'xgb_ts_monthly_expanding_peak_mae': float(row2.iloc[0]['peak_mae']),
                })
        print(f'✓ MLflow: {len(agg)} wariantów + wf2_summary_all → {MLFLOW_EXPERIMENT}')

    print(f'\n✓ {out}')
    print(f'✓ {agg_path}')


if __name__ == '__main__':
    main()
