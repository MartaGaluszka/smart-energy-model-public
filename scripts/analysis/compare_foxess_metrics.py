#!/usr/bin/env python3
"""
Porównanie metryk FoxESS: aplikacja vs API (foxess_all_* / foxess_timeseries).

Kluczowe mapowanie (ta sama chmura FoxESS, różne reprezentacje):

| Aplikacja (PL)   | Raport dzienny (get_report) | Timeseries (get_history)     | foxess_data (agregat)        |
|------------------|-----------------------------|------------------------------|------------------------------|
| Produkcja PV     | PVEnergyTotal               | PVEnergyTotal (kWh, licznik) | generationPower → pv_energy  |
| Produkcja (gen.) | generation                  | generation (kWh, licznik)    | —                            |
| Do sieci         | feedin                      | feedin                       | feedinPower → grid_export    |
| Zużycie          | loads                       | loads                        | loadsPower → load_energy     |
| Z sieci          | gridConsumption             | gridConsumption              | gridConsumptionPower         |
| Ładowanie BAT    | chargeEnergyToTal           | chargeEnergyToTal            | batChargePower               |
| Rozładowanie BAT | dischargeEnergyToTal        | dischargeEnergyToTal         | batDischargePower            |

Timeseries kWh to liczniki skumulowane (lifetime). Dzienna energia:
  delta_last = last(day) - last(day-1)   [≈ raport, ~99% dni]
  gdy brak ciągłości (min=0): używamy delta_last zamiast max-min.

ML / trening:
  ml_filtered = suma pv_energy_kwh z filtrem battery_power_kw >= -0.1
  (systematycznie niższe niż PVEnergyTotal z aplikacji)

Użycie:
  python scripts/compare_foxess_metrics.py
  python scripts/compare_foxess_metrics.py --day 2026-07-14
  python scripts/compare_foxess_metrics.py --from 2025-11-01 --to 2026-03-31
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

DEFAULT_DB = ROOT / 'data' / 'energy_model.db'
DEFAULT_OUT = ROOT / 'data' / 'processed' / 'foxess_metrics_comparison.csv'
DEFAULT_SUMMARY = ROOT / 'data' / 'processed' / 'foxess_metrics_summary.csv'

# Raport ↔ timeseries (kWh, liczniki)
ENERGY_COUNTER_VARS = [
    'PVEnergyTotal',
    'generation',
    'feedin',
    'loads',
    'gridConsumption',
    'chargeEnergyToTal',
    'dischargeEnergyToTal',
]

# Moc (kW) → całka dzienna
POWER_INTEGRAL_VARS = [
    'generationPower',
    'pvPower',
    'pv1Power',
    'pv2Power',
]

APP_LABELS = {
    'PVEnergyTotal': 'Produkcja PV (app)',
    'generation': 'generation (raport API)',
    'feedin': 'Do sieci',
    'loads': 'Zużycie',
    'gridConsumption': 'Z sieci',
    'chargeEnergyToTal': 'Ładowanie baterii',
    'dischargeEnergyToTal': 'Rozładowanie baterii',
}


def _season(month: int) -> str:
    if month in (12, 1, 2):
        return 'Zima'
    if month in (3, 4, 5):
        return 'Wiosna'
    if month in (6, 7, 8):
        return 'Lato'
    return 'Jesień'


def _production_bucket(kwh: float) -> str:
    if kwh < 4:
        return '<4 kWh'
    if kwh < 8:
        return '4-8 kWh'
    return '8+ kWh'


def load_variable_inventory(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql(
        """
        SELECT variable, unit, COUNT(*) AS samples,
               MIN(date(timestamp)) AS date_from,
               MAX(date(timestamp)) AS date_to
        FROM foxess_timeseries
        GROUP BY variable, unit
        ORDER BY samples DESC, variable
        """,
        conn,
    )


def load_report_daily(conn: sqlite3.Connection, start: str | None, end: str | None) -> pd.DataFrame:
    where = ['1=1']
    params: list[str] = []
    if start:
        where.append('report_date >= ?')
        params.append(start)
    if end:
        where.append('report_date <= ?')
        params.append(end)
    sql = f"""
        SELECT report_date AS day, variable, MAX(total_kwh) AS kwh
        FROM foxess_report_daily
        WHERE {' AND '.join(where)}
        GROUP BY report_date, variable
    """
    df = pd.read_sql(sql, conn, params=params)
    if df.empty:
        return df
    return df.pivot(index='day', columns='variable', values='kwh').reset_index()


def daily_counter_delta(conn: sqlite3.Connection, variable: str) -> pd.DataFrame:
    """Dzienna energia z licznika skumulowanego w foxess_timeseries."""
    from src.data.foxess_pv_total import build_daily_counter_table

    return build_daily_counter_table(conn, variable=variable)


def daily_power_integral(conn: sqlite3.Connection, variable: str) -> pd.DataFrame:
    df = pd.read_sql(
        """
        SELECT date(timestamp) AS day, SUM(value) * 5.0 / 60.0 AS kwh
        FROM foxess_timeseries
        WHERE variable = ?
        GROUP BY date(timestamp)
        """,
        conn,
        params=(variable,),
    )
    if df.empty:
        return pd.DataFrame(columns=['day', f'int_{variable}'])
    return df.rename(columns={'kwh': f'int_{variable}'})


def load_foxess_data_daily(conn: sqlite3.Connection, start: str | None, end: str | None) -> pd.DataFrame:
    where = ['1=1']
    params: list[str] = []
    if start:
        where.append('DATE(timestamp) >= ?')
        params.append(start)
    if end:
        where.append('DATE(timestamp) <= ?')
        params.append(end)
    sql = f"""
        SELECT DATE(timestamp) AS day,
            ROUND(SUM(COALESCE(pv_energy_kwh, 0)), 4) AS core_raw_integral,
            ROUND(SUM(CASE WHEN pv_energy_kwh > 0 THEN pv_energy_kwh ELSE 0 END), 4)
                AS core_pos_integral,
            ROUND(SUM(CASE
                WHEN pv_energy_kwh > 0 AND COALESCE(battery_power_kw, 0) >= -0.1
                THEN pv_energy_kwh ELSE 0 END), 4) AS ml_filtered,
            ROUND(SUM(COALESCE(grid_export_kwh, 0)), 4) AS core_feedin,
            ROUND(SUM(COALESCE(load_energy_kwh, 0)), 4) AS core_loads,
            ROUND(SUM(COALESCE(grid_import_kwh, 0)), 4) AS core_grid_import,
            COUNT(*) AS n_core
        FROM foxess_data
        WHERE {' AND '.join(where)}
        GROUP BY DATE(timestamp)
    """
    return pd.read_sql(sql, conn, params=params)


def build_daily_table(
    conn: sqlite3.Connection,
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    report = load_report_daily(conn, start, end)
    if report.empty:
        raise RuntimeError('Brak danych w foxess_report_daily — uruchom foxess_fetch_all.py')

    df = report.copy()
    for var in ENERGY_COUNTER_VARS:
        ts = daily_counter_delta(conn, var)
        df = df.merge(ts, on='day', how='left')
        rep_col = var
        ts_col = f'ts_{var}'
        if rep_col in df.columns and ts_col in df.columns:
            df[f'gap_{var}'] = df[rep_col] - df[ts_col]

    for pvar in POWER_INTEGRAL_VARS:
        integral = daily_power_integral(conn, pvar)
        df = df.merge(integral, on='day', how='left')

    # pv1 + pv2
    if 'int_pv1Power' in df.columns and 'int_pv2Power' in df.columns:
        df['int_pv1_pv2'] = df['int_pv1Power'].fillna(0) + df['int_pv2Power'].fillna(0)

    core = load_foxess_data_daily(conn, start, end)
    df = df.merge(core, on='day', how='left')

    # Referencja aplikacji
    if 'PVEnergyTotal' in df.columns:
        df['app_pv'] = df['PVEnergyTotal']
    elif 'ts_PVEnergyTotal' in df.columns:
        df['app_pv'] = df['ts_PVEnergyTotal']
    else:
        df['app_pv'] = np.nan

    df['gap_app_ml'] = df['app_pv'] - df['ml_filtered']
    df['gap_app_core'] = df['app_pv'] - df['core_pos_integral']
    df['gap_app_genpower'] = df['app_pv'] - df.get('int_generationPower', np.nan)
    df['gap_app_generation'] = df['app_pv'] - df.get('generation', np.nan)

    if start:
        df = df[df['day'] >= start]
    if end:
        df = df[df['day'] <= end]

    df['month'] = pd.to_datetime(df['day']).dt.month
    df['season'] = df['month'].apply(_season)
    df['prod_bucket'] = df['app_pv'].apply(lambda x: _production_bucket(x) if pd.notna(x) else 'unknown')

    return df.sort_values('day').reset_index(drop=True)


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    rows = []

    def add_group(label: str, group: pd.DataFrame) -> None:
        if group.empty:
            return
        app = group['app_pv'].mean()
        ml = group['ml_filtered'].mean()
        gen = group.get('generation', pd.Series(dtype=float)).mean()
        ts_pv = group.get('ts_PVEnergyTotal', pd.Series(dtype=float)).mean()
        gap = group['gap_app_ml'].mean()
        pct = (group['gap_app_ml'] / group['app_pv'].clip(lower=0.1)).mean() * 100
        rows.append({
            'group': label,
            'days': len(group),
            'app_pv_avg': round(app, 2),
            'ts_PVEnergyTotal_avg': round(ts_pv, 2) if pd.notna(ts_pv) else None,
            'generation_report_avg': round(gen, 2) if pd.notna(gen) else None,
            'ml_filtered_avg': round(ml, 2),
            'gap_app_minus_ml_avg': round(gap, 2),
            'gap_pct_avg': round(pct, 1),
            'match_ts_vs_report_pct': round(
                (group['gap_PVEnergyTotal'].abs() < 0.15).mean() * 100, 1
            ) if 'gap_PVEnergyTotal' in group.columns else None,
        })

    for season in ['Zima', 'Wiosna', 'Lato', 'Jesień']:
        add_group(f'season:{season}', df[df['season'] == season])

    for bucket in ['<4 kWh', '4-8 kWh', '8+ kWh']:
        add_group(f'bucket:{bucket}', df[df['prod_bucket'] == bucket])

    add_group('all', df)
    return pd.DataFrame(rows)


def print_inventory(inv: pd.DataFrame) -> None:
    print('\n📋 foxess_timeseries — wszystkie zmienne (foxess_all_*)')
    print(f'   Liczba zmiennych: {inv["variable"].nunique()}')
    print(f'   Próbki łącznie:   {inv["samples"].sum():,}')
    print('\n   Top 15 (najwięcej próbek):')
    for _, row in inv.head(15).iterrows():
        print(f'      {row["variable"]:28} {str(row["unit"]):5}  n={row["samples"]:,}')


def print_mapping() -> None:
    print('\n🗺️  Mapowanie aplikacja ↔ API')
    for var, label in APP_LABELS.items():
        print(f'   {label:28} → raport: {var:22} | timeseries: {var} (delta licznika)')


def print_day_detail(df: pd.DataFrame, day: str) -> None:
    row = df[df['day'] == day]
    if row.empty:
        print(f'\n❌ Brak danych dla {day}')
        return
    r = row.iloc[0]
    print(f'\n📅 Szczegóły: {day}')
    print('   ' + '-' * 56)
    print(f'   Produkcja PV (app / raport):     {r.get("app_pv", float("nan")):>8.2f} kWh')
    print(f'   PVEnergyTotal (timeseries):      {r.get("ts_PVEnergyTotal", float("nan")):>8.2f} kWh')
    print(f'   generation (raport API):         {r.get("generation", float("nan")):>8.2f} kWh')
    print(f'   generation (timeseries):         {r.get("ts_generation", float("nan")):>8.2f} kWh')
    print(f'   generationPower ∫ (timeseries):  {r.get("int_generationPower", float("nan")):>8.2f} kWh')
    print(f'   pvPower ∫ (timeseries):          {r.get("int_pvPower", float("nan")):>8.2f} kWh')
    print(f'   pv1+pv2 ∫ (timeseries):          {r.get("int_pv1_pv2", float("nan")):>8.2f} kWh')
    print(f'   foxess_data pos integral:        {r.get("core_pos_integral", float("nan")):>8.2f} kWh')
    print(f'   ML filtered (trening):           {r.get("ml_filtered", float("nan")):>8.2f} kWh')
    print(f'   → luka app − ML:                 {r.get("gap_app_ml", float("nan")):>8.2f} kWh')
    print('   ' + '-' * 56)
    for var in ['feedin', 'loads', 'gridConsumption']:
        rep = r.get(var, float('nan'))
        ts = r.get(f'ts_{var}', float('nan'))
        print(f'   {APP_LABELS.get(var, var):28} raport={rep:>7.2f}  ts={ts:>7.2f} kWh')


def print_summary(summary: pd.DataFrame) -> None:
    print('\n📊 Podsumowanie (średnie dzienne)')
    print(summary.to_string(index=False))


def print_recent(df: pd.DataFrame, n: int = 10) -> None:
    cols = [
        'day', 'app_pv', 'ts_PVEnergyTotal', 'generation', 'ml_filtered',
        'gap_app_ml', 'int_generationPower',
    ]
    cols = [c for c in cols if c in df.columns]
    print(f'\n📈 Ostatnie {n} dni (kluczowe kolumny):')
    print(df[cols].tail(n).to_string(index=False))


def main() -> None:
    parser = argparse.ArgumentParser(description='Porównanie metryk FoxESS: app vs API')
    parser.add_argument('--db', default=str(DEFAULT_DB), help='Ścieżka do energy_model.db')
    parser.add_argument('--from', dest='date_from', default=None, help='Data od (YYYY-MM-DD)')
    parser.add_argument('--to', dest='date_to', default=None, help='Data do (YYYY-MM-DD)')
    parser.add_argument('--day', default=None, help='Szczegóły jednego dnia')
    parser.add_argument('--output', default=str(DEFAULT_OUT), help='CSV dzienne porównanie')
    parser.add_argument('--summary-output', default=str(DEFAULT_SUMMARY), help='CSV podsumowanie')
    parser.add_argument('--no-save', action='store_true', help='Nie zapisuj CSV')
    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f'❌ Brak bazy: {args.db}')
        sys.exit(1)

    print('=' * 72)
    print('FOXESS: mapowanie foxess_all_* (timeseries) ↔ aplikacja')
    print('=' * 72)

    conn = sqlite3.connect(args.db)
    inv = load_variable_inventory(conn)
    print_inventory(inv)
    print_mapping()

    print('\n⏳ Buduję tabelę dzienną (timeseries + raport + foxess_data)...')
    df = build_daily_table(conn, args.date_from, args.date_to)
    conn.close()

    summary = summarize(df)
    print_summary(summary)
    print_recent(df)

    if args.day:
        print_day_detail(df, args.day)

    if not args.no_save:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out, index=False)
        summary.to_csv(args.summary_output, index=False)
        print(f'\n💾 Zapisano: {out}')
        print(f'💾 Zapisano: {args.summary_output}')

    print('\n💡 Wnioski:')
    print('   • PVEnergyTotal (app) ≈ delta licznika w timeseries (~99% dni)')
    print('   • generation (raport) ≠ PVEnergyTotal — to inna metryka API')
    print('   • ML (generationPower + filtr baterii) < PVEnergyTotal, szczególnie zimą')
    print('   • Do walidacji prognoz / ROI używaj PVEnergyTotal, nie ml_filtered')


if __name__ == '__main__':
    main()
