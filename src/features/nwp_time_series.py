"""Cechy szeregów czasowych z NWP (Lekcja 38) — bez lag targetu PV (brak leakage)."""

from __future__ import annotations

import pandas as pd

TS_FEATURE_COLUMNS = [
    'radiation_lag1',
    'cloud_lag1',
    'radiation_roll3_mean',
    'radiation_roll3_std',
    'cloud_roll3_mean',
    'cloud_roll3_std',
    'radiation_diff1',
    'cloud_diff1',
]


def add_nwp_time_series_features(df: pd.DataFrame) -> pd.DataFrame:
    """Lag / rolling / diff na pogodzie NWP — shift(1) w obrębie dnia."""
    out = df.sort_values(['day', 'hour']).copy()
    g = out.groupby('day', group_keys=False)

    out['radiation_lag1'] = g['radiation_wm2'].shift(1)
    out['cloud_lag1'] = g['cloud_cover_pct'].shift(1)

    out['radiation_roll3_mean'] = g['radiation_wm2'].transform(
        lambda s: s.shift(1).rolling(3, min_periods=1).mean()
    )
    out['radiation_roll3_std'] = g['radiation_wm2'].transform(
        lambda s: s.shift(1).rolling(3, min_periods=1).std()
    )
    out['cloud_roll3_mean'] = g['cloud_cover_pct'].transform(
        lambda s: s.shift(1).rolling(3, min_periods=1).mean()
    )
    out['cloud_roll3_std'] = g['cloud_cover_pct'].transform(
        lambda s: s.shift(1).rolling(3, min_periods=1).std()
    )

    out['radiation_diff1'] = g['radiation_wm2'].diff(1)
    out['cloud_diff1'] = g['cloud_cover_pct'].diff(1)

    for c in TS_FEATURE_COLUMNS:
        out[c] = out[c].fillna(0.0)
    return out
