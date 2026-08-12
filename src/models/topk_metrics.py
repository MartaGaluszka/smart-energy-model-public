"""Metryki trafności top-k godzin (ranking AGD / szczyt dnia)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def topk_hour_metrics(
    meta: pd.DataFrame,
    *,
    k: int = 5,
    y_true_col: str = 'y_true',
    y_pred_col: str = 'y_pred',
    day_col: str = 'day',
    hour_col: str = 'hour',
) -> dict[str, float]:
    """
    Per dzień: top-k godzin wg y_true vs top-k wg y_pred.

    Zwraca średnie po dniach:
      - topk_hit_rate: |intersection| / k
      - topk_jaccard: |intersection| / |union|
      - peak_in_topk: 1 jeśli prawdziwy szczyt dnia ∈ pred top-k
      - peak_hour_exact: 1 jeśli argmax pred == argmax true
    """
    df = meta[[day_col, hour_col, y_true_col, y_pred_col]].copy()
    hits, jacs, peak_in, peak_exact = [], [], [], []

    for _, g in df.groupby(day_col):
        if len(g) < k:
            continue
        true_top = set(g.nlargest(k, y_true_col)[hour_col].astype(int))
        pred_top = set(g.nlargest(k, y_pred_col)[hour_col].astype(int))
        inter = true_top & pred_top
        union = true_top | pred_top
        hits.append(len(inter) / k)
        jacs.append(len(inter) / len(union) if union else float('nan'))

        true_peak = int(g.loc[g[y_true_col].idxmax(), hour_col])
        pred_peak = int(g.loc[g[y_pred_col].idxmax(), hour_col])
        peak_in.append(1.0 if true_peak in pred_top else 0.0)
        peak_exact.append(1.0 if true_peak == pred_peak else 0.0)

    if not hits:
        return {
            'topk_hit_rate': float('nan'),
            'topk_jaccard': float('nan'),
            'peak_in_topk': float('nan'),
            'peak_hour_exact': float('nan'),
            'n_days_topk': 0,
        }

    return {
        'topk_hit_rate': float(np.mean(hits)),
        'topk_jaccard': float(np.nanmean(jacs)),
        'peak_in_topk': float(np.mean(peak_in)),
        'peak_hour_exact': float(np.mean(peak_exact)),
        'n_days_topk': int(len(hits)),
    }
