#!/usr/bin/env python3
"""
Prognoza produkcji PV: dziś + kolejne dni + ranking godzin na urządzenia.

Target modelu: domyślnie ΔPVEnergyTotal (jak w app); opcjonalnie ∫pvPower.
Bez filtra baterii, bez post-processingu mnożnikowego.

Użycie (macOS: poza venv nie ma `python`):
    ./venv/bin/python mlops/forecast_pv.py
    ./venv/bin/python mlops/forecast_pv.py --days 3 --sync
    ./venv/bin/python mlops/forecast_pv.py --retrain
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()


def _format_recommendations(recs) -> str:
    lines = []
    current_day = None
    for r in recs:
        if r.day != current_day:
            current_day = r.day
            lines.append(f'\n📅 {r.day}')
            lines.append('-' * 50)
        apps = ', '.join(r.appliances) if r.appliances else '(za mało PV — poczekaj na słońce)'
        lines.append(
            f'  #{r.rank}  {r.hour:02d}:00  '
            f'~{r.predicted_kwh:.2f} kWh/h  →  {apps}'
        )
    return '\n'.join(lines)


def main():
    import argparse

    from src.models.pv_hourly_predictor import (
        DEFAULT_MODEL_PATH,
        PVHourlyPredictor,
        train_and_save,
    )

    parser = argparse.ArgumentParser(description='Prognoza PV (pvPower / PVEnergyTotal)')
    parser.add_argument('--days', type=int, default=3, help='Liczba dni prognozy (domyślnie 3)')
    parser.add_argument('--top', type=int, default=5, help='Top N godzin na dzień')
    parser.add_argument('--retrain', action='store_true', help='Wytrenuj model przed prognozą')
    parser.add_argument('--sync', action='store_true', help='Pobierz brakujące dane przed prognozą')
    parser.add_argument(
        '--run-label',
        default=os.getenv('FORECAST_RUN_LABEL', 'manual'),
        help='Etykieta runu w archiwum (daily, midday, manual)',
    )
    parser.add_argument(
        '--no-operational-adjust',
        action='store_true',
        help='Wyłącz korektę intraday + profil błędu (surowy model ML)',
    )
    parser.add_argument(
        '--out',
        default='data/processed/pv_forecast.csv',
        help='Ścieżka CSV prognozy (CS4 shadow: pv_forecast_cs4.csv)',
    )
    parser.add_argument(
        '--model-path',
        default=None,
        help='Ścieżka .joblib (domyślnie PV_HOURLY_MODEL_PATH / produkcja 16 cech)',
    )
    args = parser.parse_args()

    if args.sync:
        from mlops.sync_data import sync_weather
        sync_weather()

    model_path = args.model_path or os.getenv('PV_HOURLY_MODEL_PATH', DEFAULT_MODEL_PATH)

    print('=' * 70)
    print('PROGNOZA PRODUKCJI PV — pvPower (bez filtra baterii)')
    print('=' * 70)

    if args.retrain or not os.path.exists(model_path):
        print('\n[1] Trening modelu...')
        report = train_and_save()
        print(f'    Test MAE: {report.test_mae:.3f} kWh/h')
        print(f'    {report.verdict}')
        predictor = PVHourlyPredictor(model_path=model_path)
        predictor.load()
    else:
        predictor = PVHourlyPredictor(model_path=model_path)
        predictor.load()
        n_feat = len(predictor.feature_columns) if predictor.feature_columns else '?'
        print(f'\n[1] Ładowanie modelu ({n_feat} cech) ← {model_path}')
        if predictor.report:
            print(f'    Test MAE: {predictor.report.test_mae:.3f} kWh/h')
            print(f'    {predictor.report.verdict}')

    print(f'\n[2] Prognoza na {args.days} dni (hybryda + korekta operacyjna)...')
    try:
        predictions, recs = predictor.recommend_appliances(
            days_ahead=args.days,
            top_n_per_day=args.top,
            hybrid_today=True,
            use_actual_pv=True,
            operational_adjust=not args.no_operational_adjust,
        )
    except ValueError as e:
        print(f'\n❌ {e}')
        print('   Uruchom: ./venv/bin/python mlops/sync_data.py --weather')
        sys.exit(1)

    if predictions.empty:
        print('❌ Brak prognozy — sprawdź dane pogodowe w bazie.')
        sys.exit(1)

    adjust_report = getattr(predictions, 'attrs', {}).get('intraday_adjust_report')

    from src.models.forecast_error_profile import profile_summary
    from src.models.intraday_forecast_adjust import format_adjust_report

    if not args.no_operational_adjust:
        print(f'\n[2b] Korekta operacyjna (własny algorytm intraday):')
        print(format_adjust_report(adjust_report) or '  (brak raportu)')
        print(f'  {profile_summary()}')

    value_col = 'predicted_kwh_adjusted' if 'predicted_kwh_adjusted' in predictions.columns else 'predicted_kwh'

    from src.models.hybrid_outlook import day_outlook_totals

    adjust_applied = bool(
        adjust_report is not None and getattr(adjust_report, 'applied', False)
    )

    print('\n[3] Suma dzienna (outlook dnia ≠ ścieżka hybrydowa godzin):')
    for day, group in predictions.groupby('day'):
        outlook = day_outlook_totals(group, adjust_applied=adjust_applied)
        future = group
        if 'prediction_source' in group.columns:
            future = group[group['prediction_source'] == 'model']
        peak_col = value_col if value_col in future.columns else 'predicted_kwh'
        peak_row = (
            future.loc[future[peak_col].idxmax()]
            if not future.empty
            else group.loc[group[peak_col].idxmax()]
        )
        line = (
            f'    {day}: ~{outlook["outlook_kwh"]:.1f} kWh [{outlook["outlook_mode"]}]  '
            f'(szczyt {int(peak_row["hour"]):02d}:00 = {peak_row[peak_col]:.2f} kWh/h)'
        )
        if abs(outlook['raw_kwh'] - outlook['outlook_kwh']) > 0.05:
            line += f'  [model raw ~{outlook["raw_kwh"]:.1f}]'
        if abs(outlook['hybrid_path_kwh'] - outlook['outlook_kwh']) > 0.05:
            line += f'  [hybryda ścieżka ~{outlook["hybrid_path_kwh"]:.1f}]'
        if outlook['actual_past_kwh'] > 0:
            line += f'  [{outlook["actual_past_kwh"]:.1f} kWh FoxESS + reszta]'
        print(line)

    print('\n[4] Najlepsze godziny na urządzenia (ranking konserwatywny):')
    print(_format_recommendations(recs))

    os.makedirs('data/processed', exist_ok=True)
    out_path = args.out
    predictions.to_csv(out_path, index=False)
    print(f'\n💾 Zapisano: {out_path}')

    from src.models.forecast_archive import archive_forecast

    archive_path, history_path = archive_forecast(predictions, run_label=args.run_label)
    print(f'📦 Archiwum: {archive_path}')
    print(f'📋 Historia: {history_path}')


if __name__ == '__main__':
    main()
