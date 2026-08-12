"""Testy inżynierii cech — bez bazy danych."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.features.clearness import add_clearness_features, haurwitz_ghi_wm2
from src.features.nwp_time_series import TS_FEATURE_COLUMNS, add_nwp_time_series_features
from src.features.panel_geometry import approximate_poa_wm2, incidence_cosine
from src.features.pv_features_hourly_extended import calculate_sun_features


class TestClearness:
    def test_haurwitz_ghi_zero_when_sun_below_horizon(self):
        assert haurwitz_ghi_wm2(0.0) == 0.0

    def test_clearness_ratio_for_sunny_noon(self):
        df = pd.DataFrame([
            {'day': '2026-06-21', 'hour': 12, 'radiation_wm2': 800.0},
        ])
        out = add_clearness_features(df, latitude=50.06, longitude=19.94)
        assert out['ghi_clear_wm2'].iloc[0] > 500
        assert 0.5 < out['clearness'].iloc[0] <= 1.5


class TestPanelGeometry:
    def test_incidence_cosine_south_panel_at_noon(self):
        cos_i = incidence_cosine(
            sun_elev_deg=60.0,
            sun_az_deg=180.0,
            tilt_deg=35.0,
            panel_az_deg=180.0,
        )
        assert cos_i == pytest.approx(0.96, abs=0.05)

    def test_approximate_poa_zero_when_incidence_zero(self):
        assert approximate_poa_wm2(500.0, incidence_cos=0.0, sun_elev_deg=30.0) == 0.0


class TestNwpTimeSeries:
    def test_lag_features_no_leakage_at_first_hour(self):
        df = pd.DataFrame([
            {'day': '2026-07-01', 'hour': 8, 'radiation_wm2': 100.0, 'cloud_cover_pct': 20.0},
            {'day': '2026-07-01', 'hour': 9, 'radiation_wm2': 200.0, 'cloud_cover_pct': 30.0},
            {'day': '2026-07-01', 'hour': 10, 'radiation_wm2': 300.0, 'cloud_cover_pct': 40.0},
        ])
        out = add_nwp_time_series_features(df)
        first = out[out['hour'] == 8].iloc[0]
        assert first['radiation_lag1'] == 0.0
        assert first['cloud_lag1'] == 0.0
        assert set(TS_FEATURE_COLUMNS).issubset(out.columns)


class TestSunFeatures:
    def test_calculate_sun_features_marks_noon_as_daylight(self):
        df = pd.DataFrame([{'day': '2026-06-21', 'hour': 12}])
        out = calculate_sun_features(df, latitude=50.06, longitude=19.94)
        assert out['is_daylight'].iloc[0] == 1
        assert out['day_length_hours'].iloc[0] > 10
