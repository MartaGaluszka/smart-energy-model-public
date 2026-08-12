"""Archiwum prognoz PV — porównania „wczoraj na dziś”."""

from __future__ import annotations

import os
from datetime import datetime

import pandas as pd

from src.models.forecast_time import format_forecast_ts, normalize_run_at_column
from src.models.hybrid_outlook import day_outlook_totals

ARCHIVE_DIR = 'data/processed/forecasts'
HISTORY_FILE = os.path.join(ARCHIVE_DIR, 'forecast_history.csv')


def archive_forecast(
    predictions: pd.DataFrame,
    *,
    run_label: str = 'manual',
) -> tuple[str, str]:
    """
    Zapisuje kopię prognozy z timestampem + dopisuje skrót do forecast_history.csv.

    Returns:
        (path_csv, path_history)
    """
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    run_at = datetime.now()
    stamp = run_at.strftime('%Y%m%d_%H%M%S')
    csv_path = os.path.join(ARCHIVE_DIR, f'pv_forecast_{stamp}.csv')
    predictions.to_csv(csv_path, index=False)

    adjust_applied = False
    report = getattr(predictions, 'attrs', {}).get('intraday_adjust_report')
    if report is not None and getattr(report, 'applied', False):
        adjust_applied = True

    history_rows = []
    for day, group in predictions.groupby('day'):
        future = group
        if 'prediction_source' in group.columns:
            future = group[group['prediction_source'] == 'model']
        peak_col = (
            'predicted_kwh_adjusted'
            if 'predicted_kwh_adjusted' in future.columns
            else 'predicted_kwh'
        )
        peak_row = (
            future.loc[future[peak_col].idxmax()]
            if not future.empty
            else group.loc[group[peak_col].idxmax()]
        )
        outlook = day_outlook_totals(group, adjust_applied=adjust_applied)
        history_rows.append({
            'run_at': format_forecast_ts(run_at),
            'run_label': run_label,
            'target_day': str(day),
            # KPI / karty: outlook (raw do późnego dnia; hybryda wieczorem)
            'predicted_kwh': round(outlook['outlook_kwh'], 2),
            'predicted_kwh_raw': round(outlook['raw_kwh'], 2),
            'predicted_kwh_adjusted': round(outlook['hybrid_path_kwh'], 2),
            'predicted_kwh_hybrid': round(outlook['hybrid_path_kwh'], 2),
            'outlook_mode': outlook['outlook_mode'],
            'actual_kwh_in_forecast': round(outlook['actual_past_kwh'], 2),
            'peak_hour': int(peak_row['hour']),
            'peak_kwh': round(float(peak_row[peak_col]), 3),
        })

    history_df = pd.DataFrame(history_rows)
    if os.path.exists(HISTORY_FILE):
        prev = pd.read_csv(HISTORY_FILE)
        history_df = pd.concat([prev, history_df], ignore_index=True)
    history_df = normalize_run_at_column(history_df, 'run_at')
    history_df.to_csv(HISTORY_FILE, index=False)
    return csv_path, HISTORY_FILE
