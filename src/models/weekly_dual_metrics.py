"""
Dual reporting weekly: shuffle MAE (kontrola) + chronological L30 MAE (uczciwy holdout).

Produkcja (.joblib) NIE trenuje na samym holdoucie — expanding do train_end zostaje.
L30 służy tylko do raportu / soft gate (październik 2026: informacyjnie, bez REJECT).
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import mean_absolute_error, r2_score

DEFAULT_HOLD_DAYS = 30
# Chrono holdout (raport, nie gate): stałe 90 dni — porównywalne tydzień do tygodnia
CHRONO90_HOLD_DAYS = 90
# Soft gate X 2026: typowy rząd L30 jesień — nie REJECT
SOFT_GATE_L30_LOW = 0.75
SOFT_GATE_L30_HIGH = 1.0
SHUFFLE_GATE_DELTA = 0.02

HISTORY_CSV = Path('data/processed/weekly_dual_metrics.csv')


def chronological_l30_bounds(
    train_end: str,
    *,
    hold_days: int = DEFAULT_HOLD_DAYS,
) -> tuple[str, str]:
    """Zwróć (hold_start, hold_end) włącznie — ostatnie ``hold_days`` dni do train_end."""
    end = pd.Timestamp(train_end).normalize()
    start = end - pd.Timedelta(days=hold_days - 1)
    return start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')


def chronological_fraction_masks(
    day_series: pd.Series,
    train_end: str,
    *,
    fraction: float = 0.2,
    min_test_days: int = 14,
) -> tuple[pd.Series, pd.Series, str, str]:
    """Ostatnie ``fraction`` unikalnych dni do ``train_end`` jako test (raport, nie gate).

    Train = dni ≤ train_end poza tym blokiem. Dni po train_end nie wchodzą do żadnej maski.
    """
    days = pd.to_datetime(day_series.astype(str))
    end = pd.Timestamp(train_end).normalize()
    unique = sorted({d.normalize() for d in days if pd.notna(d) and d.normalize() <= end})
    empty = pd.Series(False, index=day_series.index)
    if len(unique) < min_test_days + 1:
        return empty, empty.copy(), '', ''
    n_test = max(min_test_days, int(round(len(unique) * fraction)))
    n_test = min(n_test, len(unique) - 1)
    hold = unique[-n_test:]
    hold_set = set(hold)
    norm = days.dt.normalize()
    test_mask = norm.isin(hold_set)
    train_mask = (norm <= end) & ~test_mask
    return (
        train_mask,
        test_mask,
        hold[0].strftime('%Y-%m-%d'),
        hold[-1].strftime('%Y-%m-%d'),
    )


def chronological_l30_masks(
    day_series: pd.Series,
    train_end: str,
    *,
    hold_days: int = DEFAULT_HOLD_DAYS,
) -> tuple[pd.Series, pd.Series, str, str]:
    """
    Maski boolean (index jak day_series):
      train_chrono = day < hold_start
      test_chrono  = hold_start ≤ day ≤ train_end
    """
    hold_start, hold_end = chronological_l30_bounds(train_end, hold_days=hold_days)
    days = pd.to_datetime(day_series.astype(str))
    test_mask = (days >= pd.Timestamp(hold_start)) & (days <= pd.Timestamp(hold_end))
    train_mask = days < pd.Timestamp(hold_start)
    return train_mask, test_mask, hold_start, hold_end


def soft_gate_l30(
    mae: float | None,
    *,
    low: float = SOFT_GATE_L30_LOW,
    high: float = SOFT_GATE_L30_HIGH,
) -> dict[str, Any]:
    """
    Soft gate (okres przejściowy): L30 nigdy nie ustawia hard_reject=True.
    status: INFO | WATCH
    """
    if mae is None or (isinstance(mae, float) and np.isnan(mae)):
        return {
            'status': 'INFO',
            'hard_reject': False,
            'mae': None,
            'band': f'{low:.2f}–{high:.2f}',
            'message': 'L30 niedostępne — soft gate bez alarmu',
        }
    mae_f = float(mae)
    band = f'{low:.2f}–{high:.2f}'
    if low <= mae_f <= high:
        msg = (
            f'L30 MAE {mae_f:.3f} w oczekiwanej strefie jesień ({band}) '
            '— soft gate INFO, bez REJECT'
        )
        status = 'INFO'
    elif mae_f < low:
        msg = (
            f'L30 MAE {mae_f:.3f} poniżej strefy ({band}) — łatwiejsze okno; '
            'soft gate INFO, bez REJECT'
        )
        status = 'INFO'
    else:
        msg = (
            f'L30 MAE {mae_f:.3f} powyżej ~{high:.2f} — WATCH informacyjny; '
            'soft gate, bez REJECT (dual reporting X 2026)'
        )
        status = 'WATCH'
    return {
        'status': status,
        'hard_reject': False,
        'mae': mae_f,
        'band': band,
        'message': msg,
    }


def shuffle_gate_vs_prev(
    current_mae: float,
    prev_mae: float | None,
    *,
    threshold: float = SHUFFLE_GATE_DELTA,
) -> dict[str, Any]:
    """Twardy gate na shuffle MAE vs poprzedni weekly (jak dotychczas)."""
    if prev_mae is None or (isinstance(prev_mae, float) and np.isnan(prev_mae)):
        return {
            'status': 'ACCEPT',
            'delta': None,
            'threshold': threshold,
            'message': 'Brak poprzedniego shuffle MAE w historii — ACCEPT (pierwszy / brak bazy)',
        }
    delta = float(current_mae) - float(prev_mae)
    if delta > threshold:
        status = 'REVIEW'
        msg = (
            f'Δ shuffle Test MAE {delta:+.3f} > +{threshold:.2f} vs prev '
            f'({prev_mae:.3f} → {current_mae:.3f}) → REVIEW'
        )
    else:
        status = 'ACCEPT'
        msg = (
            f'Δ shuffle Test MAE {delta:+.3f} ≤ +{threshold:.2f} vs prev '
            f'({prev_mae:.3f} → {current_mae:.3f}) → ACCEPT'
        )
    return {
        'status': status,
        'delta': delta,
        'threshold': threshold,
        'message': msg,
    }


def evaluate_holdout_pipeline(
    pipeline,
    frame: pd.DataFrame,
    feature_columns: list[str],
    target_column: str,
    train_mask: pd.Series,
    test_mask: pd.Series,
) -> dict[str, float | int | None]:
    """Dopasuj ``clone(pipeline)`` na train_mask, oceń na test_mask (chrono L30)."""
    if int(test_mask.sum()) == 0 or int(train_mask.sum()) == 0:
        return {
            'test_mae': None,
            'train_mae': None,
            'gap': None,
            'daily_mae': None,
            'daily_r2': None,
            'test_r2': None,
            'wape': None,
            'bias': None,
            'n_train': int(train_mask.sum()),
            'n_test': int(test_mask.sum()),
            'n_test_days': 0,
        }

    X_tr = frame.loc[train_mask, feature_columns]
    y_tr = frame.loc[train_mask, target_column]
    X_te = frame.loc[test_mask, feature_columns]
    y_te = frame.loc[test_mask, target_column]
    days_te = frame.loc[test_mask, 'day']

    pipe = clone(pipeline)
    pipe.fit(X_tr, y_tr)
    pred_te = pipe.predict(X_te)
    pred_tr = pipe.predict(X_tr)

    mae_te = float(mean_absolute_error(y_te, pred_te))
    mae_tr = float(mean_absolute_error(y_tr, pred_tr))
    r2_te = float(r2_score(y_te, pred_te)) if len(y_te) > 1 else float('nan')

    daily = pd.DataFrame({
        'day': days_te.astype(str).values,
        'y': np.asarray(y_te, dtype=float),
        'p': np.asarray(pred_te, dtype=float),
    })
    g = daily.groupby('day', as_index=False).sum(numeric_only=True)
    daily_mae = float(mean_absolute_error(g['y'], g['p'])) if len(g) else float('nan')
    daily_r2 = float(r2_score(g['y'], g['p'])) if len(g) > 1 else float('nan')

    y_arr = np.asarray(y_te, dtype=float)
    p_arr = np.asarray(pred_te, dtype=float)
    y_sum = float(np.nansum(y_arr))
    # WAPE: suma |błąd| / suma produkcji — porównywalne między sezonami (w odróżnieniu od MAE)
    wape = float(np.nansum(np.abs(p_arr - y_arr)) / y_sum) if y_sum > 0 else None
    # bias: średnie (pred − real) w kWh/h; ujemny = model zaniża produkcję
    bias = float(np.nanmean(p_arr - y_arr)) if len(y_arr) else None

    return {
        'test_mae': mae_te,
        'train_mae': mae_tr,
        'gap': mae_te - mae_tr,
        'daily_mae': daily_mae,
        'daily_r2': daily_r2,
        'test_r2': r2_te,
        'wape': wape,
        'bias': bias,
        'n_train': len(y_tr),
        'n_test': len(y_te),
        'n_test_days': int(days_te.nunique()),
    }


def _empty_holdout_result() -> dict[str, float | int | None]:
    return {
        'test_mae': None,
        'train_mae': None,
        'gap': None,
        'daily_mae': None,
        'daily_r2': None,
        'test_r2': None,
        'wape': None,
        'bias': None,
        'n_train': 0,
        'n_test': 0,
        'n_test_days': 0,
    }


def evaluate_chrono90_safe(
    pipeline,
    frame: pd.DataFrame,
    feature_columns: list[str],
    target_column: str,
    train_end: str,
    *,
    hold_days: int = CHRONO90_HOLD_DAYS,
) -> tuple[dict[str, float | int | None], str, str]:
    """Chrono 90 dni (raport, nie gate) — nigdy nie przerywa treningu produkcyjnego.

    Stałe okno ``hold_days`` (nie ułamek danych), żeby tydzień do tygodnia był porównywalny.
    Przy dowolnym wyjątku (NaN w danych, puste maski, błąd fit) loguje ostrzeżenie
    i zwraca pusty wynik (``test_mae=None``), jak przy „za mało dni”.
    Zwraca ``(wynik, hold_start, hold_end)``.
    """
    try:
        tr_mask, te_mask, start, end = chronological_l30_masks(
            frame['day'], train_end, hold_days=hold_days,
        )
        result = evaluate_holdout_pipeline(
            pipeline, frame, feature_columns, target_column, tr_mask, te_mask,
        )
        return result, start, end
    except Exception as exc:  # noqa: BLE001 — raport informacyjny, nie może blokować prod
        print(
            f'⚠️  Chrono {hold_days}d pominięty (raport, nie gate): '
            f'{type(exc).__name__}: {exc}',
        )
        return _empty_holdout_result(), '', ''


def print_dual_report(
    *,
    feature_set: str,
    shuffle_mae: float,
    shuffle_daily_mae: float,
    l30: dict[str, Any],
    hold_start: str,
    hold_end: str,
    soft: dict[str, Any],
    shuffle_gate: dict[str, Any] | None = None,
    chrono90: dict[str, Any] | None = None,
    chrono90_start: str = '',
    chrono90_end: str = '',
) -> None:
    """Wypisz blok dual report do logów weekly."""
    print('')
    print('=' * 72)
    print(f'DUAL REPORT — {feature_set}')
    print('=' * 72)
    print(
        f'  Shuffle Test MAE:  {shuffle_mae:.3f} kWh/h'
        f'  |  Daily: {shuffle_daily_mae:.2f} kWh/d   [kontrola]'
    )
    l30_mae = l30.get('test_mae')
    l30_daily = l30.get('daily_mae')
    if l30_mae is None:
        print('  L30 chrono MAE:     — (za mało dni / puste okno)')
    else:
        print(
            f'  L30 chrono MAE:     {float(l30_mae):.3f} kWh/h'
            f'  |  Daily: {float(l30_daily):.2f} kWh/d'
            f'  |  dni test: {l30.get("n_test_days")}   [{hold_start} → {hold_end}]'
        )
        gap = l30.get('gap')
        if gap is not None:
            print(f'  L30 gap (te−tr):   {float(gap):+.3f} kWh/h')
    print(f'  Soft gate L30:     {soft["status"]}  (hard_reject={soft["hard_reject"]})')
    print(f'                     {soft["message"]}')
    if chrono90 is not None:
        c_mae = chrono90.get('test_mae')
        c_daily = chrono90.get('daily_mae')
        if c_mae is None:
            print('  Chrono 90d MAE:     — (za mało dni / pominięty)')
        else:
            daily_s = f'{float(c_daily):.2f}' if c_daily is not None else '—'
            print(
                f'  Chrono 90d MAE:     {float(c_mae):.3f} kWh/h'
                f'  |  Daily: {daily_s} kWh/d'
                f'  |  dni test: {chrono90.get("n_test_days")}'
                f'   [{chrono90_start} → {chrono90_end}]  [raport, nie gate]'
            )
            c_wape = chrono90.get('wape')
            c_bias = chrono90.get('bias')
            wape_s = f'{float(c_wape) * 100:.1f}%' if c_wape is not None else '—'
            if c_bias is None:
                bias_s = '—'
            else:
                direction = 'zaniża' if float(c_bias) < 0 else 'zawyża'
                bias_s = f'{float(c_bias):+.3f} kWh/h ({direction})'
            print(f'  Chrono 90d WAPE:    {wape_s}  |  bias: {bias_s}')
    if shuffle_gate is not None:
        print(f'  Shuffle gate:      {shuffle_gate["status"]}')
        print(f'                     {shuffle_gate["message"]}')
    print('  Prod .joblib:      expanding full window (L30 i chrono 90d tylko raport)')
    print('=' * 72)


def load_prev_shuffle_mae(
    feature_set: str,
    *,
    history_path: Path | str = HISTORY_CSV,
) -> float | None:
    path = Path(history_path)
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path)
    except Exception:
        return None
    if df.empty or 'feature_set' not in df.columns or 'shuffle_test_mae' not in df.columns:
        return None
    sub = df[df['feature_set'].astype(str) == str(feature_set)]
    if sub.empty:
        return None
    val = sub.iloc[-1]['shuffle_test_mae']
    if pd.isna(val):
        return None
    return float(val)


def append_dual_history(row: dict[str, Any], *, history_path: Path | str = HISTORY_CSV) -> Path:
    path = Path(history_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    out = dict(row)
    out.setdefault('recorded_at', date.today().isoformat())
    df_new = pd.DataFrame([out])
    if path.exists():
        try:
            prev = pd.read_csv(path)
            df = pd.concat([prev, df_new], ignore_index=True)
        except Exception:
            df = df_new
    else:
        df = df_new
    df.to_csv(path, index=False)
    return path
