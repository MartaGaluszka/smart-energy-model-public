#!/usr/bin/env python
"""Ponowne logowanie wf2_summary_* z poprawnym Source (= ten plik / WF v2)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pandas as pd
import mlflow

from scripts.train.train_hourly_model_tuning import MLFLOW_EXPERIMENT

PROCESSED = ROOT / 'data' / 'processed'
FIGURES = ROOT / 'reports' / 'figures'


def main() -> None:
    agg = pd.read_csv(PROCESSED / 'walk_forward_v2_summary.csv')
    detail = PROCESSED / 'walk_forward_v2.csv'
    figs = sorted(FIGURES.glob('walk_forward_v2_*.png'))

    mlflow.set_tracking_uri(f'file:{ROOT / "mlruns"}')
    mlflow.set_experiment(MLFLOW_EXPERIMENT)

    for _, r in agg.iterrows():
        name = f"wf2_summary_{r['model']}_{r['step']}_{r['train_window']}"
        with mlflow.start_run(run_name=name):
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
            if detail.exists():
                mlflow.log_artifact(str(detail))
            for p in figs:
                mlflow.log_artifact(str(p))
            print('logged', name)

    print(f'done: {len(agg)} summaries → {MLFLOW_EXPERIMENT}')


if __name__ == '__main__':
    main()
