#!/usr/bin/env python
"""
Smoke test: timeseries delta (PVEnergyTotal) + czysta prognoza RF (pvPower).

Uruchomienie:
    python tests/test_pv_pipeline_smoke.py
    python tests/test_pv_pipeline_smoke.py --day 2026-07-14
"""

from __future__ import annotations

import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()


def test_timeseries_delta(target_day: str) -> None:
    from src.data.foxess_pv_total import (
        get_actual_pv_total_from_report,
        get_actual_pv_total_from_timeseries,
        resolve_actual_pv_total,
    )

    print('=' * 60)
    print(f'[1] Timeseries delta (hybrid) — {target_day}')
    print('=' * 60)

    ts_kwh = get_actual_pv_total_from_timeseries(target_day)
    report_kwh = get_actual_pv_total_from_report(target_day)
    resolved, source = resolve_actual_pv_total(target_day)

    print(f'  get_actual_pv_total_from_timeseries(): {ts_kwh} kWh')
    print(f'  get_actual_pv_total_from_report():     {report_kwh} kWh')
    print(f'  resolve_actual_pv_total():             {resolved} kWh  [{source}]')

    if ts_kwh is None:
        raise SystemExit('FAIL: brak wyniku z timeseries — sprawdź foxess_timeseries / PVEnergyTotal')

    if ts_kwh <= 0 or ts_kwh > 500:
        raise SystemExit(f'FAIL: timeseries delta poza sensownym zakresem: {ts_kwh}')

    if report_kwh is not None and abs(ts_kwh - report_kwh) / report_kwh > 0.05:
        print(f'  ⚠️  Różnica ts vs report > 5% ({abs(ts_kwh - report_kwh):.2f} kWh) — OK jeśli <15%')
    else:
        print('  ✓ ts ↔ report zgodne (±5%)')

    print('  OK: hybrid delta bez błędów Pandas/SQLite')


def test_ml_dry_run(target_day: str) -> None:
    from src.models.pv_hourly_predictor import DEFAULT_MODEL_PATH, PVHourlyPredictor

    print()
    print('=' * 60)
    print('[2] Dry-run ML — Random Forest (target pvPower, bez kalibracji)')
    print('=' * 60)

    # Usunięty moduł kalibracji nie powinien istnieć w projekcie
    try:
        importlib.import_module('src.models.pv_calibration')
        raise SystemExit('FAIL: src.models.pv_calibration nadal istnieje — kalibracja nie usunięta')
    except ModuleNotFoundError:
        print('  ✓ brak src.models.pv_calibration (calibrate_pv_total usunięte)')

    predictor = PVHourlyPredictor()
    predictor.load(DEFAULT_MODEL_PATH)
    print(f'  ✓ model załadowany: {DEFAULT_MODEL_PATH}')
    if predictor.report:
        print(f'    Test MAE: {predictor.report.test_mae:.3f} kWh/h')

    db_path = os.getenv('DATABASE_PATH', 'data/energy_model.db')

    # Jeden wiersz z realnej pogody (południe, dzień testowy)
    from src.models.pv_hourly_predictor import build_forecast_feature_frame

    frame = build_forecast_feature_frame(
        db_path,
        [target_day],
        latitude=predictor.latitude,
        longitude=predictor.longitude,
        location=predictor.location,
        hybrid_today=False,
    )
    if frame.empty:
        raise SystemExit(f'FAIL: brak cech pogodowych dla {target_day}')

    sample = frame.loc[frame['hour'] == 12].head(1)
    if sample.empty:
        sample = frame.head(1)

    missing = [c for c in predictor.feature_columns if c not in sample.columns]
    if missing:
        raise SystemExit(f'FAIL: brak kolumn cech: {missing}')

    X = sample[predictor.feature_columns]
    pred = float(predictor.pipeline.predict(X)[0])
    pred = max(pred, 0.0)

    print(f'  Przykładowy wiersz: {target_day} {int(sample.iloc[0]["hour"]):02d}:00')
    print(f'  radiation_wm2={sample.iloc[0]["radiation_wm2"]:.0f}, '
          f'cloud_cover_pct={sample.iloc[0]["cloud_cover_pct"]:.0f}%')
    print(f'  predict() → {pred:.3f} kWh/h  (skala pvPower, bez post-processingu)')

    if pred <= 0 or pred > 10:
        raise SystemExit(f'FAIL: predykcja godzinowa poza oczekiwanym zakresem pvPower: {pred}')

    # Suma dzienna z tego samego dnia (dry-run pełnej doby)
    full = frame[predictor.feature_columns]
    daily_sum = float(predictor.pipeline.predict(full).clip(min=0).sum())
    print(f'  Suma godzinowa (dry-run dzień): {daily_sum:.1f} kWh')

    if daily_sum < 5 or daily_sum > 80:
        raise SystemExit(f'FAIL: suma dzienna poza skalą pvPower (~10–40 kWh): {daily_sum}')

    # Upewnij się, że forecast_pv nie importuje kalibracji
    import ast
    import pathlib

    forecast_py = pathlib.Path('mlops/forecast_pv.py').read_text(encoding='utf-8')
    if 'calibrate' in forecast_py.lower():
        raise SystemExit('FAIL: mlops/forecast_pv.py nadal odnosi się do kalibracji')

    tree = ast.parse(forecast_py)
    imports = {
        node.names[0].name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    print(f'  ✓ forecast_pv.py bez kalibracji (importy m.in. pv_hourly_predictor)')

    print('  OK: predykcja czysta RF, skala pvPower')


def test_operational_adjust() -> None:
    import os

    import pandas as pd
    from datetime import datetime

    from src.models.forecast_error_profile import build_error_profile, hourly_correction_factor
    from src.models.intraday_forecast_adjust import apply_operational_adjustment

    print()
    print('=' * 60)
    print('[3] Korekta operacyjna (conditional intraday)')
    print('=' * 60)

    build_error_profile()
    assert hourly_correction_factor(12) > 0
    print('  ✓ forecast_error_profile zbudowany')

    # Duży błąd rano + wysokie chmury → conditional OK, skala na D+0
    sample = pd.DataFrame([
        {
            'day': '2026-07-16', 'hour': 8, 'predicted_kwh': 1.0, 'predicted_kwh_raw': 2.0,
            'prediction_source': 'foxess_actual', 'cloud_cover_pct': 80.0,
        },
        {
            'day': '2026-07-16', 'hour': 9, 'predicted_kwh': 1.5, 'predicted_kwh_raw': 3.0,
            'prediction_source': 'foxess_actual', 'cloud_cover_pct': 75.0,
        },
        {
            'day': '2026-07-16', 'hour': 10, 'predicted_kwh': 3.0, 'predicted_kwh_raw': 3.0,
            'prediction_source': 'model', 'cloud_cover_pct': 70.0,
        },
        {
            'day': '2026-07-17', 'hour': 10, 'predicted_kwh': 4.0, 'predicted_kwh_raw': 4.0,
            'prediction_source': 'model', 'cloud_cover_pct': 80.0,
        },
    ])
    prev = os.environ.get('FORECAST_OPERATIONAL_ADJUST')
    os.environ['FORECAST_OPERATIONAL_ADJUST'] = '1'
    try:
        out, report = apply_operational_adjustment(sample, as_of=datetime(2026, 7, 16, 10, 0, 0))
        assert 'predicted_kwh_adjusted' in out.columns
        assert report is not None and report.conditional_triggered
        future = out[(out['day'] == '2026-07-16') & (out['hour'] == 10)].iloc[0]
        assert float(future['predicted_kwh_adjusted']) < float(future['predicted_kwh_raw'])
        # D+1: bez skali / cloudy mimo wysokiego cloud w wierszu
        d1 = out[(out['day'] == '2026-07-17') & (out['hour'] == 10)].iloc[0]
        assert float(d1['predicted_kwh_adjusted']) == float(d1['predicted_kwh_raw'])
        print(f'  ✓ conditional OK scale={report.blended_scale:.2f}, D+0 adj={future["predicted_kwh_adjusted"]:.2f}, D+1 raw={d1["predicted_kwh_adjusted"]:.2f}')

        # Słoneczny dzień, mały błąd rano → bypass (baza hybrydowa)
        sunny = pd.DataFrame([
            {
                'day': '2026-07-20', 'hour': 8, 'predicted_kwh': 2.0, 'predicted_kwh_raw': 2.1,
                'prediction_source': 'foxess_actual', 'cloud_cover_pct': 20.0,
            },
            {
                'day': '2026-07-20', 'hour': 9, 'predicted_kwh': 3.0, 'predicted_kwh_raw': 3.1,
                'prediction_source': 'foxess_actual', 'cloud_cover_pct': 25.0,
            },
            {
                'day': '2026-07-20', 'hour': 10, 'predicted_kwh': 4.0, 'predicted_kwh_raw': 4.0,
                'prediction_source': 'model', 'cloud_cover_pct': 30.0,
            },
        ])
        out2, report2 = apply_operational_adjustment(sunny, as_of=datetime(2026, 7, 20, 10, 0, 0))
        assert report2 is not None and not report2.conditional_triggered
        assert report2.reason.startswith('conditional_skip')
        fut2 = out2[out2['hour'] == 10].iloc[0]
        assert float(fut2['predicted_kwh_adjusted']) == float(fut2['predicted_kwh'])
        print(f'  ✓ conditional skip ({report2.reason})')
    finally:
        if prev is None:
            os.environ.pop('FORECAST_OPERATIONAL_ADJUST', None)
        else:
            os.environ['FORECAST_OPERATIONAL_ADJUST'] = prev
    print('  OK: warstwa operacyjna (conditional)')

    from src.models.hybrid_outlook import day_outlook_totals

    # Midday-style: 6/15 actual → outlook = raw (nie zaniżona ścieżka hybrydowa)
    mid = pd.DataFrame([
        {'day': '2026-07-29', 'hour': h,
         'predicted_kwh': 1.0 if h < 12 else 2.0,
         'predicted_kwh_raw': 2.0,
         'prediction_source': 'foxess_actual' if h < 12 else 'model'}
        for h in range(6, 21)
    ])
    o = day_outlook_totals(mid, adjust_applied=False)
    assert o['outlook_mode'] == 'model_raw'
    assert abs(o['outlook_kwh'] - o['raw_kwh']) < 1e-6
    print(f'  ✓ hybrid outlook midday → {o["outlook_mode"]} ({o["outlook_kwh"]:.1f} kWh)')


def main() -> None:
    import argparse
    from datetime import date, timedelta

    parser = argparse.ArgumentParser(description='Smoke test PVEnergyTotal + RF pvPower')
    parser.add_argument(
        '--day',
        default=(date.today() - timedelta(days=1)).isoformat(),
        help='Dzień testowy (domyślnie wczoraj)',
    )
    args = parser.parse_args()

    test_timeseries_delta(args.day)
    test_ml_dry_run(args.day)
    test_operational_adjust()

    print()
    print('=' * 60)
    print('WSZYSTKIE TESTY OK')
    print('=' * 60)


if __name__ == '__main__':
    main()
