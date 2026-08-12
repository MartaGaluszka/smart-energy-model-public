"""
Outlook dzienny vs ścieżka hybrydowa (FoxESS minione + model przyszłe).

Problem (29.07.2026 midday): hybryda podmienia rano na FoxESS (OK na wykresie),
ale suma dnia spada (27.7), bo model zawyżył rano — wygląda jak „pogorszenie prognozy”.
Surowy model dnia (~32.6) był bliżej finału (~36).

Zasada:
  - godziny: nadal hybryda (`predicted_kwh`)
  - **suma dnia (KPI / archiwum)**: do późnego dnia → `predicted_kwh_raw`;
    gdy większość godzin to już FoxESS → ścieżka hybrydowa
"""

from __future__ import annotations

import os
from typing import Any

import pandas as pd


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == '':
        return default
    return float(raw)


def day_outlook_totals(
    group: pd.DataFrame,
    *,
    adjust_applied: bool = False,
) -> dict[str, Any]:
    """
    Policz sumy dnia i wybierz outlook.

    Returns keys: raw_kwh, hybrid_path_kwh, outlook_kwh, outlook_mode,
                  n_hours, n_actual, actual_past_kwh
    """
    g = group.copy()
    if 'predicted_kwh_raw' not in g.columns:
        g['predicted_kwh_raw'] = g['predicted_kwh'].astype(float)
    path_col = (
        'predicted_kwh_adjusted'
        if 'predicted_kwh_adjusted' in g.columns
        else 'predicted_kwh'
    )

    raw_kwh = float(g['predicted_kwh_raw'].sum())
    hybrid_path_kwh = float(g[path_col].sum())
    n_hours = int(len(g))
    n_actual = 0
    actual_past = 0.0
    if 'prediction_source' in g.columns:
        actual_mask = g['prediction_source'] == 'foxess_actual'
        n_actual = int(actual_mask.sum())
        actual_past = float(g.loc[actual_mask, 'predicted_kwh'].sum())

    late_frac = _env_float('FORECAST_HYBRID_LATE_FRAC', 0.65)
    late = n_hours > 0 and (n_actual / n_hours) >= late_frac

    if adjust_applied:
        outlook_kwh = hybrid_path_kwh
        mode = 'adjusted'
    elif late:
        outlook_kwh = hybrid_path_kwh
        mode = 'hybrid_path'
    else:
        # Rano / południe: nie karz sumy dnia za podmianę FoxESS na zawyżone rano
        outlook_kwh = raw_kwh
        mode = 'model_raw'

    return {
        'raw_kwh': raw_kwh,
        'hybrid_path_kwh': hybrid_path_kwh,
        'outlook_kwh': outlook_kwh,
        'outlook_mode': mode,
        'n_hours': n_hours,
        'n_actual': n_actual,
        'actual_past_kwh': actual_past,
    }
