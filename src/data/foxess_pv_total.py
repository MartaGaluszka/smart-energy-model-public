"""
PVEnergyTotal z FoxESS — Δ licznika timeseries (= Produkcja w app) + raport dzienny.

Liczniki kWh w foxess_timeseries są skumulowane (lifetime). Dzienna energia (hybrid):
  - max − min w dniu, gdy min > 0 (ciągły licznik)
  - last(dzień) − last(dzień−1), gdy min = 0 (luka / reset)

``resolve_actual_pv_total`` preferuje Δ timeseries (zgodność z app).
Raport ``generation`` nie jest metryką produkcji app — nie używać.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date

import numpy as np
import pandas as pd

PVE_COUNTER_VARIABLE = 'PVEnergyTotal'

# Raport < 95% wartości z licznika timeseries → uznaj za podejrzany
# (27.07: report PVE 16.1 vs Δts 18.6 ≈ 86% — przy 0.85 błędnie zostawał raport)
REPORT_VS_TS_RATIO = float(os.getenv('FOXESS_REPORT_TS_MIN_RATIO', '0.95'))
# Raport < 40% sumy pvPower przy pvPower > 2 kWh → podejrzany
REPORT_VS_PVPOWER_RATIO = float(os.getenv('FOXESS_REPORT_PVPOWER_MIN_RATIO', '0.40'))
PVPOWER_SANITY_MIN_KWH = float(os.getenv('FOXESS_PVPOWER_SANITY_MIN_KWH', '2.0'))


def hybrid_daily_delta(
    mn: float,
    mx: float,
    last_val: float,
    prev_last: float | None,
) -> float | None:
    """Oblicz dzienną energię z odczytów licznika skumulowanego (jeden dzień)."""
    if mn > 0:
        delta = mx - mn
    elif prev_last is not None and not np.isnan(prev_last):
        delta = last_val - prev_last
    else:
        return None

    if delta is None or np.isnan(delta) or delta < 0 or delta > 500:
        return None
    return float(delta)


def _day_counter_stats(
    conn: sqlite3.Connection,
    target_day: str,
    variable: str = PVE_COUNTER_VARIABLE,
) -> tuple[float, float, float, int] | None:
    """min, max, last, n_samples dla jednego dnia."""
    rows = conn.execute(
        '''
        SELECT value FROM foxess_timeseries
        WHERE variable = ? AND date(timestamp) = ?
        ORDER BY timestamp
        ''',
        (variable, target_day),
    ).fetchall()
    if not rows:
        return None
    values = pd.Series([r[0] for r in rows], dtype=float)
    values = pd.to_numeric(values, errors='coerce').dropna()
    if values.empty:
        return None
    return float(values.min()), float(values.max()), float(values.iloc[-1]), len(values)


def _prev_day_last_counter(
    conn: sqlite3.Connection,
    target_day: str,
    variable: str = PVE_COUNTER_VARIABLE,
) -> float | None:
    row = conn.execute(
        '''
        SELECT value FROM foxess_timeseries
        WHERE variable = ? AND date(timestamp) < ?
        ORDER BY timestamp DESC
        LIMIT 1
        ''',
        (variable, target_day),
    ).fetchone()
    if not row or row[0] is None:
        return None
    return float(row[0])


def get_actual_pv_total_from_timeseries(
    target_day: str | None = None,
    db_path: str | None = None,
    *,
    variable: str = PVE_COUNTER_VARIABLE,
) -> float | None:
    """
    PVEnergyTotal z licznika foxess_timeseries (metoda hybrid).

    Returns:
        Dzienna produkcja [kWh] lub None, gdy brak danych.
    """
    target_day = target_day or date.today().isoformat()
    db_path = db_path or os.getenv('DATABASE_PATH', 'data/energy_model.db')
    if not os.path.exists(db_path):
        return None

    conn = sqlite3.connect(db_path)
    try:
        stats = _day_counter_stats(conn, target_day, variable)
        if stats is None:
            return None
        mn, mx, last_val, _ = stats
        prev_last = _prev_day_last_counter(conn, target_day, variable)
        return hybrid_daily_delta(mn, mx, last_val, prev_last)
    finally:
        conn.close()


def get_actual_pv_total_from_report(
    target_day: str | None = None,
    db_path: str | None = None,
) -> float | None:
    """PVEnergyTotal z foxess_report_daily (API get_report)."""
    target_day = target_day or date.today().isoformat()
    db_path = db_path or os.getenv('DATABASE_PATH', 'data/energy_model.db')
    if not os.path.exists(db_path):
        return None

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        '''
        SELECT total_kwh FROM foxess_report_daily
        WHERE report_date = ? AND variable = ?
        ORDER BY total_kwh DESC
        LIMIT 1
        ''',
        (target_day, PVE_COUNTER_VARIABLE),
    ).fetchone()
    conn.close()

    if not row or row[0] is None:
        return None
    val = float(row[0])
    return val if val > 0 else None


def report_value_suspicious(
    report_kwh: float,
    *,
    timeseries_kwh: float | None,
    pv_power_kwh: float | None,
) -> bool:
    """Czy raport dzienny wygląda na niepełny lub błędny."""
    if timeseries_kwh is not None and timeseries_kwh > 0.5:
        if report_kwh < timeseries_kwh * REPORT_VS_TS_RATIO:
            return True
    if (
        pv_power_kwh is not None
        and pv_power_kwh >= PVPOWER_SANITY_MIN_KWH
        and report_kwh < pv_power_kwh * REPORT_VS_PVPOWER_RATIO
    ):
        return True
    return False


def resolve_actual_pv_total(
    target_day: str | None = None,
    db_path: str | None = None,
    *,
    actual_kwh_override: float | None = None,
    pv_power_daily_kwh: float | None = None,
) -> tuple[float | None, str]:
    """
    Jedna metryka = Produkcja z app FoxESS.

    Preferencja: Δ PVEnergyTotal (timeseries) → raport dzienny PVE → override.
    Raport ``generation`` NIE jest używany (często zaniża vs app).
    Gdy raport PVE jest podejrzanie niski względem licznika — zostaje timeseries.

    Returns:
        (kwh, source) gdzie source ∈ timeseries | report | override | none
    """
    target_day = target_day or date.today().isoformat()

    if actual_kwh_override is not None and actual_kwh_override > 0:
        return float(actual_kwh_override), 'override'

    report = get_actual_pv_total_from_report(target_day, db_path)
    ts = get_actual_pv_total_from_timeseries(target_day, db_path)

    # Timeseries Δ = ta sama skala co „Produkcja” w app (potwierdzone 25–27.07)
    if ts is not None and ts > 0:
        if report is None or report <= 0:
            return ts, 'timeseries'
        if report_value_suspicious(
            report,
            timeseries_kwh=ts,
            pv_power_kwh=pv_power_daily_kwh,
        ):
            return ts, 'timeseries'
        # Zgodne z raportem — i tak bierzemy licznik (stabilniejszy na niepełnych dniach)
        return ts, 'timeseries'

    if report is not None and report > 0:
        return report, 'report'

    return None, 'none'


def build_daily_counter_table(
    conn: sqlite3.Connection,
    variable: str = PVE_COUNTER_VARIABLE,
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    """Tabela dzienna (wszystkie dni) — używana przez compare_foxess_metrics."""
    where = ['variable = ?']
    params: list = [variable]
    if start:
        where.append('date(timestamp) >= ?')
        params.append(start)
    if end:
        where.append('date(timestamp) <= ?')
        params.append(end)

    df = pd.read_sql(
        f'''
        SELECT date(timestamp) AS day, timestamp, value
        FROM foxess_timeseries
        WHERE {' AND '.join(where)}
        ORDER BY timestamp
        ''',
        conn,
        params=params,
    )
    if df.empty:
        return pd.DataFrame(columns=['day', f'ts_{variable}'])

    df['value'] = pd.to_numeric(df['value'], errors='coerce')
    agg = df.groupby('day', as_index=False).agg(
        mn=('value', 'min'),
        mx=('value', 'max'),
        last_val=('value', 'last'),
        n=('value', 'count'),
    )
    agg['day_dt'] = pd.to_datetime(agg['day'])
    agg = agg.sort_values('day_dt').reset_index(drop=True)
    agg['prev_last'] = agg['last_val'].shift(1)
    agg[f'ts_{variable}'] = agg.apply(
        lambda r: hybrid_daily_delta(r['mn'], r['mx'], r['last_val'], r['prev_last']),
        axis=1,
    )
    return agg[['day', f'ts_{variable}', 'n']].rename(columns={'n': f'n_{variable}'})
