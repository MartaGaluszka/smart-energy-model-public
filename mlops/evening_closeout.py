#!/usr/bin/env python3
"""
Wieczorne domknięcie dnia — FoxESS sync + actual vs predicted.

Bez nowej prognozy PV (dzień już minął). Zapisuje wynik w:
  data/processed/forecasts/forecast_validation.csv

Uruchomienie:
    ./venv/bin/python mlops/evening_closeout.py
    ./venv/bin/python mlops/evening_closeout.py --day 2026-07-14
    ./venv/bin/python mlops/evening_closeout.py --dry-run
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    import argparse

    import pandas as pd

    parser = argparse.ArgumentParser(description='Wieczorne domknięcie: FoxESS + walidacja prognozy')
    parser.add_argument('--day', help='Dzień do walidacji (domyślnie dziś, YYYY-MM-DD)')
    parser.add_argument('--dry-run', action='store_true', help='Tylko pokaż plan, bez sync')
    parser.add_argument('--skip-sync', action='store_true', help='Pomiń sync FoxESS (tylko walidacja z bazy)')
    parser.add_argument(
        '--actual-kwh',
        type=float,
        default=None,
        help='Ręczna wartość actual_pv_total (PVEnergyTotal), gdy brak w bazie',
    )
    parser.add_argument(
        '--backfill-snapshots',
        nargs='*',
        default=[],
        metavar='LABEL=KWH',
        help='Dopisz brakujące prognozy, np. daily=20.8 midday=25.1',
    )
    parser.add_argument(
        '--if-after-sunset',
        type=int,
        default=None,
        metavar='MINUTES',
        help=(
            'Uruchom TYLKO jeśli teraz >= zachód słońca (target_day) + MINUTES — inaczej '
            'no-op, exit 0 (bez sync/zapisu). Do wywoływania często (np. co 10 min przez '
            'launchd) przez cały rok, żeby domknięcie pojawiało się zaraz po zachodzie '
            '(zmienny latem/zimą), a nie dopiero o stałej porze 22:42. Idempotentne: po '
            'pierwszym udanym uruchomieniu dla danego dnia zapisuje marker i pomija kolejne '
            'wywołania tego samego dnia (nie zużywa niepotrzebnie limitu FoxESS API).'
        ),
    )
    args = parser.parse_args()

    from datetime import date, datetime, timedelta

    target_day = args.day or date.today().isoformat()

    dynamic_marker = None
    if args.if_after_sunset is not None:
        marker_dir = 'data/processed/forecasts'
        dynamic_marker = os.path.join(marker_dir, f'.dynamic_closeout_done_{target_day}')
        if os.path.exists(dynamic_marker):
            print(f'[--if-after-sunset] {target_day}: już domknięte dziś dynamicznie — pomijam.')
            return

        lat = float(os.getenv('WEATHER_LAT', '50.06'))
        lon = float(os.getenv('WEATHER_LON', '19.94'))
        try:
            from src.features.pv_features_hourly_extended import get_sunrise_sunset

            _, sunset = get_sunrise_sunset(lat, lon, target_day)
            now = datetime.now(sunset.tzinfo)
            trigger_at = sunset + timedelta(minutes=args.if_after_sunset)
        except Exception as exc:
            print(f'[--if-after-sunset] Nie udało się policzyć zachodu słońca ({exc}) — uruchamiam mimo to.')
        else:
            if now < trigger_at:
                print(
                    f'[--if-after-sunset] {target_day}: za wcześnie — zachód {sunset.strftime("%H:%M")}, '
                    f'próg {trigger_at.strftime("%H:%M")} (+{args.if_after_sunset} min), teraz '
                    f'{now.strftime("%H:%M")}. Pomijam (exit 0).'
                )
                return
            print(
                f'[--if-after-sunset] {target_day}: zachód {sunset.strftime("%H:%M")} + '
                f'{args.if_after_sunset} min = próg {trigger_at.strftime("%H:%M")} minięty — kontynuuję.'
            )

    print('=' * 70)
    print(f'WIECZORNE DOMKNIĘCIE — {target_day}')
    print('=' * 70)

    sync_ok = True
    if not args.skip_sync and not args.dry_run:
        from mlops.sync_data import foxess_day_coverage, foxess_sync_disabled, sync_foxess

        if foxess_sync_disabled():
            print('\n[1] Sync FoxESS — pominięty (FOXESS_SYNC_DISABLED=1)')
        else:
            print('\n[1] Sync FoxESS (dziś + luki)...')
            extra_days: list[str] = []
            if target_day != date.today().isoformat():
                extra_days.append(target_day)
            sync_ok = sync_foxess(
                refresh_today=True,
                save_csv=False,
                extra_days=extra_days,
                require_complete_today=True,
            )
            if not sync_ok:
                cov = foxess_day_coverage(target_day)
                print('\n   ❌ Sync FoxESS nie udał się lub dzień wciąż niepełny.')
                if cov.get('last_timestamp'):
                    print(f'      Ostatnia próbka w bazie: {cov["last_timestamp"]}')
                print('      Walidacja poniżej może być oparta o niepełne dane.')
    elif args.dry_run:
        print('\n[1] Sync FoxESS — pominięty (dry-run)')
    else:
        print('\n[1] Sync FoxESS — pominięty (--skip-sync)')

    print('\n[2] Walidacja: rzeczywistość vs prognozy...')
    from src.models.forecast_validation import backfill_history_snapshots, record_evening_closeout

    snapshots: dict[str, float] = {}
    for item in args.backfill_snapshots:
        if '=' not in item:
            continue
        label, val = item.split('=', 1)
        snapshots[label.strip()] = float(val.strip())
    if snapshots:
        backfill_history_snapshots(target_day, snapshots)
        print(f'   Backfill snapshotów: {snapshots}')

    if args.dry_run:
        from src.data.foxess_pv_total import (
            get_actual_pv_total_from_report,
            get_actual_pv_total_from_timeseries,
            resolve_actual_pv_total,
        )
        from src.models.forecast_validation import (
            build_hourly_peak_validation,
            get_actual_pv_ml,
        )

        actual_ml = get_actual_pv_ml(target_day)
        actual_total, source = resolve_actual_pv_total(
            target_day,
            pv_power_daily_kwh=actual_ml if actual_ml > 0 else None,
        )
        report = get_actual_pv_total_from_report(target_day)
        ts = get_actual_pv_total_from_timeseries(target_day)
        print(f'   actual_pv_total:        {actual_total if actual_total is not None else "brak"} kWh  [{source}]')
        print(f'   ├─ raport API:          {report if report is not None else "brak"} kWh')
        print(f'   ├─ timeseries (hybrid): {ts if ts is not None else "brak"} kWh')
        print(f'   └─ pvPower (model):     {actual_ml:.2f} kWh')
        hourly_df, peak_df = build_hourly_peak_validation(target_day)
        if not hourly_df.empty:
            print('\n   Podgląd tabeli godzinowej (bez zapisu):')
            print(hourly_df.to_string(index=False))
        print('   (dry-run — bez zapisu CSV)')
        return

    row = record_evening_closeout(target_day, actual_kwh_override=args.actual_kwh)

    print(f'\n   Dzień:                  {row["target_day"]}')
    if row['actual_pv_total'] is not None:
        src = row.get('actual_pv_source', '?')
        print(f'   actual_pv_total:        {row["actual_pv_total"]:.2f} kWh  [źródło: {src}]')
        if row.get('actual_pv_report') is not None:
            print(f'   ├─ raport API:          {row["actual_pv_report"]:.2f} kWh')
        if row.get('actual_pv_timeseries') is not None:
            print(f'   ├─ timeseries hybrid:   {row["actual_pv_timeseries"]:.2f} kWh')
    else:
        print('   actual_pv_total:        brak (raport + timeseries)')
    if row['actual_pv_ml'] is not None:
        print(f'   actual_pv_ml (model):   {row["actual_pv_ml"]:.2f} kWh')
    if row['predicted_daily'] is not None:
        print(f'   Prognoza daily:         {row["predicted_daily"]:.2f} kWh  '
              f'(błąd vs app {row["error_vs_daily_kwh"]:+.2f} kWh)')
    if row['predicted_midday'] is not None:
        print(f'   Prognoza midday:        {row["predicted_midday"]:.2f} kWh  '
              f'(błąd vs app {row["error_vs_midday_kwh"]:+.2f} kWh)')
    if row.get('predicted_daily_cs4') is not None:
        err_c = row.get('error_vs_daily_cs4_kwh')
        err_s = f'{err_c:+.2f}' if err_c is not None else '?'
        print(f'   Prognoza daily CS4:     {row["predicted_daily_cs4"]:.2f} kWh  '
              f'(błąd vs app {err_s} kWh)')
    if row.get('predicted_midday_cs4') is not None:
        err_c = row.get('error_vs_midday_cs4_kwh')
        err_s = f'{err_c:+.2f}' if err_c is not None else '?'
        print(f'   Prognoza midday CS4:    {row["predicted_midday_cs4"]:.2f} kWh  '
              f'(błąd vs app {err_s} kWh)')
    if row.get('predicted_daily_icon') is not None:
        err_i = row.get('error_vs_daily_icon_kwh')
        err_s = f'{err_i:+.2f}' if err_i is not None else '?'
        print(f'   Prognoza daily ICON:    {row["predicted_daily_icon"]:.2f} kWh  '
              f'(błąd vs app {err_s} kWh)  [shadow]')
    if row.get('predicted_midday_icon') is not None:
        err_i = row.get('error_vs_midday_icon_kwh')
        err_s = f'{err_i:+.2f}' if err_i is not None else '?'
        print(f'   Prognoza midday ICON:   {row["predicted_midday_icon"]:.2f} kWh  '
              f'(błąd vs app {err_s} kWh)  [shadow]')
    if row['predicted_manual'] is not None:
        print(f'   Prognoza manual:    {row["predicted_manual"]:.2f} kWh')
    if row['best_snapshot_label']:
        print(f'   Najbliższy snapshot: {row["best_snapshot_label"]} '
              f'({row["best_snapshot_kwh"]:.2f} kWh, błąd {row["best_snapshot_error_kwh"]:+.2f} kWh)')

    from src.models.forecast_validation import (
        HOURLY_VALIDATION_FILE,
        PEAK_VALIDATION_FILE,
        build_hourly_peak_validation,
    )

    hourly_df, peak_df = build_hourly_peak_validation(target_day)
    if not hourly_df.empty:
        print('\n[3] Top godziny prognozy vs FoxESS:')
        for run_label in hourly_df['run_label'].unique():
            sub = hourly_df[hourly_df['run_label'] == run_label]
            print(f'\n   --- {run_label} ---')
            print(f'   {"#":>2}  {"godz":>4}  {"prognoza":>8}  {"FoxESS Δ":>9}  {"FoxESS Δ":>11}  {"błąd":>8}')
            for _, r in sub.iterrows():
                ml = f'{r["actual_pv_ml_kwh"]:.2f}' if pd.notna(r['actual_pv_ml_kwh']) else '—'
                rep = f'{r["actual_report_kwh"]:.2f}' if pd.notna(r['actual_report_kwh']) else '—'
                err = f'{r["error_vs_ml_kwh"]:+.2f}' if pd.notna(r['error_vs_ml_kwh']) else '—'
                peak_ml = ' ★' if r.get('is_actual_peak_ml') else ''
                peak_rep = ' ★' if r.get('is_actual_peak_report') else ''
                print(
                    f'   {int(r["rank"]):>2}  {int(r["predicted_hour"]):02d}:00  '
                    f'{r["predicted_kwh"]:>8.2f}  {ml:>9}  {rep:>11}  {err:>8}{peak_ml}{peak_rep}'
                )

    def _fmt_peak(hour, kwh) -> str:
        if pd.isna(hour) or pd.isna(kwh):
            return '—'
        return f'{int(hour):02d}:00 ({kwh:.2f})'

    if not peak_df.empty:
        print('\n[4] Szczyt prognozy vs szczyt FoxESS:')
        for _, p in peak_df.iterrows():
            print(
                f'   {p["run_label"]:>6}: prognoza szczyt {int(p["predicted_peak_hour"]):02d}:00 '
                f'({p["predicted_peak_kwh"]:.2f} kWh/h)  |  '
                f'FoxESS Δ {_fmt_peak(p["actual_peak_hour_ml"], p["actual_peak_kwh_ml"])}'
            )

    from src.models.forecast_error_profile import build_error_profile, profile_summary
    build_error_profile()
    print(f'\n[5] Profil błędu operacyjnego: {profile_summary()}')

    print(f'\n✓ data/processed/forecasts/forecast_validation.csv')
    if row.get('hourly_validation_rows', 0) > 0:
        print(f'✓ {HOURLY_VALIDATION_FILE}')
        print(f'✓ {PEAK_VALIDATION_FILE}')
    print('=' * 70)
    if not sync_ok and not args.skip_sync and not args.dry_run:
        print('GOTOWE (sync FoxESS nie powiódł się — sprawdź logs/cron.log)')
        sys.exit(1)
    if dynamic_marker is not None:
        # Zapisz DOPIERO po udanym sync+zapisie — przy błędzie (sys.exit(1) wyżej) NIE
        # zapisujemy markera, żeby kolejne wywołanie (za ~10 min) spróbowało ponownie.
        with open(dynamic_marker, 'w') as f:
            f.write(datetime.now().isoformat())
    print('GOTOWE')
    print('=' * 70)


if __name__ == '__main__':
    main()
