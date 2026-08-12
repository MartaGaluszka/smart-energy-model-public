"""Testy poprawności danych — licznik FoxESS, CSV Tauron, kontekst domu."""

from __future__ import annotations

from datetime import date

import pytest

from src.data.foxess_pv_total import hybrid_daily_delta, report_value_suspicious
from src.data.household_context import classify_period, is_ml_pv_forecast_period
from src.data.import_meter_csv import _flow_type, _parse_datetime


class TestHybridDailyDelta:
    def test_continuous_counter_uses_max_minus_min(self):
        assert hybrid_daily_delta(mn=100.0, mx=125.5, last_val=125.5, prev_last=90.0) == pytest.approx(25.5)

    def test_gap_day_uses_last_minus_prev_last(self):
        assert hybrid_daily_delta(mn=0.0, mx=50.0, last_val=150.0, prev_last=120.0) == pytest.approx(30.0)

    def test_rejects_negative_delta(self):
        assert hybrid_daily_delta(mn=10.0, mx=8.0, last_val=8.0, prev_last=5.0) is None

    def test_rejects_unrealistic_high_delta(self):
        assert hybrid_daily_delta(mn=0.0, mx=600.0, last_val=600.0, prev_last=0.0) is None


class TestReportSuspicious:
    def test_report_below_timeseries_threshold_is_suspicious(self):
        assert report_value_suspicious(16.0, timeseries_kwh=20.0, pv_power_kwh=None) is True

    def test_report_aligned_with_timeseries_is_ok(self):
        assert report_value_suspicious(19.5, timeseries_kwh=20.0, pv_power_kwh=None) is False


class TestMeterCsvParsing:
    def test_parse_datetime_hour_24_rolls_to_next_day(self):
        assert _parse_datetime('2025-05-01 24:00') == '2025-05-02 00:00:00'

    def test_flow_type_classifies_import_and_export(self):
        assert _flow_type('pobrana po zbilansowaniu') == 'import'
        assert _flow_type('oddana po zbilansowaniu') == 'export'


class TestHouseholdContext:
    def test_classify_period_renovation_summer_2025(self):
        assert classify_period(date(2025, 7, 15)) == 'renovation'

    def test_ml_pv_forecast_period_starts_2026(self):
        assert is_ml_pv_forecast_period(date(2026, 3, 1)) is True
        assert is_ml_pv_forecast_period(date(2025, 12, 1)) is False
