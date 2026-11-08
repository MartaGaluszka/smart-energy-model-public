"""
Outlook dzienny vs ścieżka hybrydowa (FoxESS minione + model przyszłe).

Problem (29.07.2026 midday): hybryda podmienia rano na FoxESS (OK na wykresie),
ale suma dnia spada (27.7), bo model zawyżył rano — wygląda jak „pogorszenie prognozy”.
Surowy model dnia (~32.6) był bliżej finału (~36).

Zasada:
  - godziny: nadal hybryda (`predicted_kwh`)
  - **suma dnia (KPI / archiwum)**:
      hybryda (FoxESS minione + model reszty), gdy jest wyższa niż raw
      (archiwum potrafi ściemnić już minione godziny poniżej licznika, 08.11);
      inaczej raw do późnego dnia (29.07: Fox niższy niż model rano);
      gdy większość godzin to już FoxESS → hybryda
      gdy suma FoxESS / suma raw na minionych godzinach < 0.70 (co najmniej 2 godziny)
      i godziny od 12 jeszcze z modelu mają średnią chmurę ≥ 50% oraz
      średnie promieniowanie < 185 W/m² → hybryda (`hybrid_cloudy`);
      29.07 i jasne południe (wysokie promieniowanie albo Fox blisko modelu) zostają na raw
"""

from __future__ import annotations

import os
from typing import Any

import pandas as pd


def _midday_cloud_persists(g: pd.DataFrame) -> bool:
    """Ciemny ranek potwierdzony licznikiem i pochmurna, słaba reszta dnia.

    Próg jest na sumie godzin FoxESS, nie na pojedynczych godzinach.
    Popołudnie to ``hour >= 12``, nie numer wiersza.
    """
    needed = ('prediction_source', 'hour', 'cloud_cover_pct', 'radiation_wm2', 'predicted_kwh_raw')
    if any(col not in g.columns for col in needed):
        return False
    fox = g[g['prediction_source'] == 'foxess_actual']
    if len(fox) < 2:
        return False
    raw_past = float(fox['predicted_kwh_raw'].sum())
    if raw_past < 0.5:
        return False
    ratio = float(fox['predicted_kwh'].sum()) / raw_past
    if ratio >= _env_float('FORECAST_MIDDAY_FOX_RATIO', 0.70):
        return False
    fut = g[(g['hour'] >= 12) & (g['prediction_source'] != 'foxess_actual')]
    cloud = fut['cloud_cover_pct'].dropna()
    rad = fut['radiation_wm2'].dropna()
    if cloud.empty or rad.empty:
        return False
    return (
        float(cloud.mean()) >= _env_float('FORECAST_MIDDAY_CLOUD_PCT', 50.0)
        and float(rad.mean()) < _env_float('FORECAST_MIDDAY_FUTURE_RAD_MAX', 185.0)
    )


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
    elif hybrid_path_kwh > raw_kwh:
        outlook_kwh = hybrid_path_kwh
        mode = 'hybrid_path'
    elif _midday_cloud_persists(g):
        outlook_kwh = hybrid_path_kwh
        mode = 'hybrid_cloudy'
    else:
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
