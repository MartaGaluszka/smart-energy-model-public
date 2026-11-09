"""Testy dual report / soft gate L30 (bez pełnego treningu RF)."""

from __future__ import annotations

import pandas as pd

from src.models.weekly_dual_metrics import (
    chronological_fraction_masks,
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


def test_chronological_fraction_last_20_percent():
    days = pd.Series([f'2026-01-{d:02d}' for d in range(1, 21)])
    tr, te, hs, he = chronological_fraction_masks(days, '2026-01-20', fraction=0.2, min_test_days=2)
    assert hs == '2026-01-17' and he == '2026-01-20'
    assert int(te.sum()) == 4
    assert int(tr.sum()) == 16
    assert not (tr & te).any()


def test_chronological_fraction_too_few_days_returns_empty():
    """Za mało dni (< min_test_days + 1): puste maski i puste granice, bez wyjątku."""
    days = pd.Series([f'2026-01-{d:02d}' for d in range(1, 11)])
    tr, te, hs, he = chronological_fraction_masks(days, '2026-01-10', fraction=0.2, min_test_days=14)
    assert hs == '' and he == ''
    assert not tr.any() and not te.any()


def test_chronological_fraction_ignores_days_after_train_end():
    """Dni po train_end nie wchodzą ani do train, ani do testu."""
    days = pd.Series([f'2026-01-{d:02d}' for d in range(1, 26)])
    tr, te, hs, he = chronological_fraction_masks(days, '2026-01-20', fraction=0.2, min_test_days=2)
    assert he == '2026-01-20'
    late = pd.to_datetime(days) > pd.Timestamp('2026-01-20')
    assert not tr[late].any()
    assert not te[late].any()
    assert int(te.sum()) == 4


def test_chronological_fraction_respects_min_test_days():
    """Mały ułamek nie schodzi poniżej min_test_days, a train nie zostaje pusty."""
    days = pd.Series([f'2026-01-{d:02d}' for d in range(1, 21)])
    tr, te, hs, _he = chronological_fraction_masks(days, '2026-01-20', fraction=0.05, min_test_days=5)
    assert int(te.sum()) == 5
    assert hs == '2026-01-16'
    assert int(tr.sum()) == 15


def test_print_dual_report_shows_chrono20_block(capsys):
    from src.models.weekly_dual_metrics import print_dual_report

    base = dict(
        feature_set='test',
        shuffle_mae=0.66,
        shuffle_daily_mae=3.0,
        l30={'test_mae': 0.8, 'daily_mae': 3.5},
        hold_start='2026-10-01',
        hold_end='2026-10-30',
        soft=soft_gate_l30(0.8),
    )
    print_dual_report(
        **base,
        chrono20={'test_mae': 0.71, 'daily_mae': 3.2, 'n_test_days': 20},
        chrono20_start='2026-10-17',
        chrono20_end='2026-11-05',
    )
    out = capsys.readouterr().out
    assert 'Chrono 20% MAE' in out
    assert '0.710' in out
    assert '2026-10-17 → 2026-11-05' in out
    assert 'raport, nie gate' in out


def test_print_dual_report_chrono20_too_few_days(capsys):
    from src.models.weekly_dual_metrics import print_dual_report

    print_dual_report(
        feature_set='test',
        shuffle_mae=0.66,
        shuffle_daily_mae=3.0,
        l30={'test_mae': 0.8, 'daily_mae': 3.5},
        hold_start='2026-10-01',
        hold_end='2026-10-30',
        soft=soft_gate_l30(0.8),
        chrono20={'test_mae': None},
    )
    assert 'za mało dni' in capsys.readouterr().out


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
