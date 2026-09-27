#!/usr/bin/env python
"""
Podsumowanie dual report po weekly train (shuffle + L30 soft gate).

Czyta data/processed/weekly_dual_metrics.csv (ostatnie wiersze per feature_set)
oraz ewent. hourly_model_tuning_summary_*.csv.

Uruchomienie (po train_dual_weekly.sh):
    PYTHONPATH=$PWD python scripts/train/weekly_dual_gate_report.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pandas as pd

from src.models.weekly_dual_metrics import (
    HISTORY_CSV,
    SOFT_GATE_L30_HIGH,
    SOFT_GATE_L30_LOW,
    soft_gate_l30,
)

FEATURE_ORDER = ('production', 'cs4', 'xgb_ts')


def _latest_by_feature(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df['_i'] = range(len(df))
    idx = df.groupby('feature_set', as_index=False)['_i'].max()['_i']
    return df.loc[idx].sort_values('feature_set')


def main() -> int:
    print('')
    print('=' * 72)
    print('WEEKLY DUAL GATE SUMMARY (shuffle + L30 soft)')
    print('=' * 72)
    print(
        f'Soft gate L30: strefa {SOFT_GATE_L30_LOW:.2f}–{SOFT_GATE_L30_HIGH:.2f} '
        '→ INFO/WATCH, hard_reject=False (X 2026)'
    )
    print('Shuffle gate: Δ vs prev weekly (REVIEW jeśli > +0.02) — bez auto-rollback')
    print('Prod .joblib: expanding full window (L30 nie ucina treningu)')
    print('')

    if not HISTORY_CSV.exists():
        print(f'⚠️  Brak {HISTORY_CSV} — uruchom weekly train najpierw.')
        return 1

    df = pd.read_csv(HISTORY_CSV)
    if df.empty:
        print('⚠️  Historia pusta.')
        return 1

    latest = _latest_by_feature(df)
    print(
        f'{"set":12s} {"shuf MAE":>9s} {"L30 MAE":>9s} {"soft":>6s} '
        f'{"shufGate":>9s} {"Δshuf":>8s}  holdout'
    )
    print('-' * 72)
    any_watch = False
    any_review = False
    for fs in FEATURE_ORDER:
        row = latest[latest['feature_set'].astype(str) == fs]
        if row.empty:
            # fallback: last row matching
            continue
        r = row.iloc[0]
        shuf = r.get('shuffle_test_mae')
        l30 = r.get('l30_test_mae')
        soft = soft_gate_l30(None if pd.isna(l30) else float(l30))
        if soft['status'] == 'WATCH':
            any_watch = True
        sg = str(r.get('shuffle_gate', '—'))
        if sg == 'REVIEW':
            any_review = True
        delta = r.get('shuffle_gate_delta')
        delta_s = f'{float(delta):+.3f}' if pd.notna(delta) else '—'
        hold = f'{r.get("l30_hold_start", "?")}→{r.get("l30_hold_end", "?")}'
        shuf_s = f'{float(shuf):.3f}' if pd.notna(shuf) else '—'
        l30_s = f'{float(l30):.3f}' if pd.notna(l30) else '—'
        print(
            f'{fs:12s} {shuf_s:>9s} {l30_s:>9s} {soft["status"]:>6s} '
            f'{sg:>9s} {delta_s:>8s}  {hold}'
        )

    print('-' * 72)
    print(
        'Werdykt okresowy: dual reporting ON — L30 nie powoduje REJECT. '
        + ('Shuffle REVIEW → dopisz do notatki weekly (primary bez auto-zmian). ' if any_review else '')
        + ('L30 WATCH → obserwacja sezonu. ' if any_watch else 'L30 w normie INFO. ')
    )
    print(f'Historia: {HISTORY_CSV}')
    print('=' * 72)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
