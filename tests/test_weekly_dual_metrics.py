"""Testy dual report / soft gate L30 (bez pełnego treningu RF)."""

from __future__ import annotations

import pandas as pd

from src.models.weekly_dual_metrics import (
    chronological_l30_bounds,
    chronological_l30_masks,
    shuffle_gate_vs_prev,
    soft_gate_l30,
)


def test_chronological_l30_bounds_inclusive_30_days():
    start, end = chronological_l30_bounds('2026-09-26', hold_days=30)
    assert end == '2026-09-26'
    assert start == '2026-08-28'


def test_chronological_l30_masks():
    days = pd.Series(['2026-08-01', '2026-08-28', '2026-09-15', '2026-09-26', '2026-10-01'])
    tr, te, hs, he = chronological_l30_masks(days, '2026-09-26', hold_days=30)
    assert hs == '2026-08-28' and he == '2026-09-26'
    assert list(tr.astype(bool)) == [True, False, False, False, False]
    assert list(te.astype(bool)) == [False, True, True, True, False]


def test_soft_gate_l30_never_hard_reject():
    for mae in (None, 0.5, 0.8, 0.9, 1.2, float('nan')):
        g = soft_gate_l30(mae)
        assert g['hard_reject'] is False
        assert g['status'] in ('INFO', 'WATCH')


def test_soft_gate_band_and_watch():
    assert soft_gate_l30(0.80)['status'] == 'INFO'
    assert soft_gate_l30(0.70)['status'] == 'INFO'
    assert soft_gate_l30(1.05)['status'] == 'WATCH'


def test_shuffle_gate_review_threshold():
    g = shuffle_gate_vs_prev(0.677, 0.652, threshold=0.02)
    assert g['status'] == 'REVIEW'
    assert abs(g['delta'] - 0.025) < 1e-9
    g2 = shuffle_gate_vs_prev(0.652, 0.666, threshold=0.02)
    assert g2['status'] == 'ACCEPT'
    g3 = shuffle_gate_vs_prev(0.677, None)
    assert g3['status'] == 'ACCEPT'
