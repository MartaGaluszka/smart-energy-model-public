"""Testy poprawności danych — licznik FoxESS, CSV Tauron, kontekst domu."""

from __future__ import annotations

from datetime import date, datetime
import sqlite3
from pathlib import Path

import pytest

from src.data.foxess_pv_total import hybrid_daily_delta, report_value_suspicious
from src.features.pv_features_hourly_extended import load_hourly_pv_from_pve
from src.models.pv_hourly_predictor import TARGET_COLUMN, load_actual_pv_hourly
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


class TestHourlyPveSkipsZeroReadings:
    def test_zero_between_samples_does_not_drop_production(self, tmp_path: Path):
        db = tmp_path / 'pve.db'
        conn = sqlite3.connect(db)
        conn.execute(
            '''
            CREATE TABLE foxess_timeseries (
                timestamp TEXT, device_sn TEXT, variable TEXT, value REAL
            )
            '''
        )
        # Licznik 100 → 101.2, z odczytem 0 między próbkami. Skok 0 → 100.9
        # przekroczyłby próg odrzucenia i suma wyniosłaby 0.7 zamiast 1.2.
        rows = [
            ('2026-09-30 10:00:00', 100.0),
            ('2026-09-30 10:05:00', 100.4),
            ('2026-09-30 10:05:30', 0.0),
            ('2026-09-30 10:10:00', 100.9),
            ('2026-09-30 10:15:00', 101.2),
            ('2026-09-30 11:00:00', 141.2),
        ]
        conn.executemany(
            'INSERT INTO foxess_timeseries VALUES (?, ?, ?, ?)',
            [(ts, 'REDACTED', 'PVEnergyTotal', val) for ts, val in rows],
        )
        conn.commit()
        conn.close()

        df = load_hourly_pv_from_pve(str(db), '2026-09-30', '2026-09-30', min_hour=0, max_hour=23)
        by_hour = dict(zip(df['hour'].astype(int), df['pv_kwh_hour']))
        assert by_hour[10] == pytest.approx(1.2)
        assert 11 not in by_hour

        # Run 16:00 wstawia te same godziny jako pomiar miniony (godziny < as_of).
        spliced = load_actual_pv_hourly(
            str(db), '2026-09-30', as_of=datetime(2026, 9, 30, 16, 0),
        )
        assert spliced[TARGET_COLUMN].sum() == pytest.approx(1.2)


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
