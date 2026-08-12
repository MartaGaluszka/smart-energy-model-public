#!/usr/bin/env python3
"""
Import FoxESS Cloud plant-chart CSV (power samples ~5 min) into the local DB.

Fills gaps when API sync fails (40402). Writes:
  - foxess_data          (samples)
  - foxess_report_daily  (hourly aggregates: generation / feedin / … / PVEnergyTotal)
  - foxess_timeseries    (pvPower + synthetic cumulative PVEnergyTotal for ML/closeout)
  - foxess_device_meta   (fetched_at refresh)

Usage:
  python scripts/import_foxess_plant_csv.py data/raw/foxess_plant/*.csv
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DB_DEFAULT = ROOT / 'data' / 'energy_model.db'
DEVICE_SN = 'REDACTED'
PVE_VARIABLE = 'PVEnergyTotal'


def _abs_num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors='coerce').fillna(0.0).abs()


def read_plant_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    # trailing empty column from FoxESS export
    df = df.loc[:, ~df.columns.astype(str).str.fullmatch(r'')]
    df.columns = [c.strip() for c in df.columns]

    required = {
        'time',
        'Solar(kW)',
        'Total Load(kW)',
        'Grid Import(kW)',
        'Grid Export(kW)',
        'Battery Charge(kW)',
        'Battery Discharge(kW)',
        'SoC(%)',
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f'{path.name}: brak kolumn {sorted(missing)}')

    work = df.copy()
    # "2026-07-26 00:02:34 CEST" → drop timezone label, treat as local wall time
    ts = (
        work['time']
        .astype(str)
        .str.replace(r'\s+(CEST|CET|UTC|GMT)[+-]?\d*$', '', regex=True)
        .str.strip()
    )
    work['timestamp'] = pd.to_datetime(ts, errors='coerce')
    work = work.dropna(subset=['timestamp']).sort_values('timestamp').reset_index(drop=True)

    solar = _abs_num(work['Solar(kW)'])
    load = _abs_num(work['Total Load(kW)'])
    g_imp = _abs_num(work['Grid Import(kW)'])
    g_exp = _abs_num(work['Grid Export(kW)'])
    bat_c = _abs_num(work['Battery Charge(kW)'])
    bat_d = _abs_num(work['Battery Discharge(kW)'])
    soc = pd.to_numeric(work['SoC(%)'], errors='coerce')

    # interval length from consecutive samples (fallback 5 min)
    dt_h = work['timestamp'].diff().dt.total_seconds().div(3600.0)
    dt_h = dt_h.fillna(5.0 / 60.0).clip(lower=1.0 / 60.0, upper=30.0 / 60.0)

    out = pd.DataFrame({
        'timestamp': work['timestamp'],
        'pv_power_kw': solar,
        'load_power_kw': load,
        'grid_power_kw': g_imp - g_exp,
        'battery_power_kw': bat_c - bat_d,
        'battery_soc_percent': soc,
        'pv_energy_kwh': solar * dt_h,
        'load_energy_kwh': load * dt_h,
        'grid_import_kwh': g_imp * dt_h,
        'grid_export_kwh': g_exp * dt_h,
        'battery_charge_kwh': bat_c * dt_h,
        'battery_discharge_kwh': bat_d * dt_h,
        'dt_h': dt_h,
        'device_sn': DEVICE_SN,
        'data_source': 'plant_csv',
        'source_file': path.name,
    })
    return out


def _days(df: pd.DataFrame) -> list[str]:
    return sorted(df['timestamp'].dt.strftime('%Y-%m-%d').unique().tolist())


def replace_foxess_data(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    days = _days(df)
    for day in days:
        conn.execute('DELETE FROM foxess_data WHERE date(timestamp) = ? AND data_source = ?', (day, 'plant_csv'))
        # also drop empty api gap days if any partial junk
        conn.execute(
            "DELETE FROM foxess_data WHERE date(timestamp) = ? AND data_source = 'api'",
            (day,),
        )
    cols = [
        'timestamp', 'pv_power_kw', 'pv_energy_kwh',
        'battery_soc_percent', 'battery_power_kw',
        'load_power_kw', 'load_energy_kwh',
        'grid_import_kwh', 'grid_export_kwh', 'grid_power_kw',
        'device_sn', 'data_source',
    ]
    insert = df[cols].copy()
    insert['timestamp'] = insert['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
    insert.to_sql('foxess_data', conn, if_exists='append', index=False, method='multi')
    return len(insert)


def replace_report_daily(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    """Hourly energy from plant samples → foxess_report_daily."""
    work = df.copy()
    work['report_date'] = work['timestamp'].dt.strftime('%Y-%m-%d')
    work['hour_index'] = work['timestamp'].dt.hour.astype(int)

    mapping = {
        'generation': 'pv_energy_kwh',
        'PVEnergyTotal': 'pv_energy_kwh',  # best proxy from plant chart (∫ Solar)
        'feedin': 'grid_export_kwh',
        'gridConsumption': 'grid_import_kwh',
        'loads': 'load_energy_kwh',
        'chargeEnergyToTal': 'battery_charge_kwh',
        'dischargeEnergyToTal': 'battery_discharge_kwh',
    }

    rows = 0
    for day in _days(df):
        day_df = work[work['report_date'] == day]
        for variable, col in mapping.items():
            conn.execute(
                'DELETE FROM foxess_report_daily WHERE report_date = ? AND variable = ? AND device_sn = ?',
                (day, variable, DEVICE_SN),
            )
            hourly = (
                day_df.groupby('hour_index', as_index=False)[col]
                .sum()
                .rename(columns={col: 'value_kwh'})
            )
            # ensure 0..23 present
            full = pd.DataFrame({'hour_index': list(range(24))}).merge(hourly, on='hour_index', how='left')
            full['value_kwh'] = full['value_kwh'].fillna(0.0)
            total = float(full['value_kwh'].sum())
            for _, r in full.iterrows():
                conn.execute(
                    '''
                    INSERT INTO foxess_report_daily
                      (report_date, device_sn, variable, hour_index, value_kwh, total_kwh)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ''',
                    (day, DEVICE_SN, variable, int(r['hour_index']), float(r['value_kwh']), total),
                )
                rows += 1
    return rows


def replace_timeseries(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    """pvPower samples + synthetic cumulative PVEnergyTotal continuing from last known counter."""
    days = _days(df)
    for day in days:
        conn.execute(
            "DELETE FROM foxess_timeseries WHERE date(timestamp) = ? AND variable IN ('pvPower', 'PVEnergyTotal', 'loadsPower', 'feedinPower', 'gridConsumptionPower', 'SoC')",
            (day,),
        )

    # last PVE before first imported sample
    first_ts = df['timestamp'].min().strftime('%Y-%m-%d %H:%M:%S')
    row = conn.execute(
        '''
        SELECT value FROM foxess_timeseries
        WHERE variable = ? AND timestamp < ?
        ORDER BY timestamp DESC LIMIT 1
        ''',
        (PVE_VARIABLE, first_ts),
    ).fetchone()
    pve_base = float(row[0]) if row and row[0] is not None else 0.0

    # cumulative solar energy within imported window
    cum = df['pv_energy_kwh'].cumsum()
    pve_series = pve_base + cum

    n = 0
    for i, r in df.iterrows():
        ts = r['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
        samples = [
            ('pvPower', float(r['pv_power_kw'])),
            ('loadsPower', float(r['load_power_kw'])),
            ('feedinPower', float(r['grid_export_kwh'] / r['dt_h']) if r['dt_h'] else 0.0),
            ('gridConsumptionPower', float(r['grid_import_kwh'] / r['dt_h']) if r['dt_h'] else 0.0),
            ('SoC', float(r['battery_soc_percent']) if pd.notna(r['battery_soc_percent']) else None),
            (PVE_VARIABLE, float(pve_series.loc[i])),
        ]
        for variable, value in samples:
            if value is None:
                continue
            unit = (
                '%' if variable == 'SoC'
                else 'kWh' if variable == PVE_VARIABLE
                else 'kW'
            )
            conn.execute(
                '''
                INSERT INTO foxess_timeseries
                  (timestamp, device_sn, variable, value, unit, data_source)
                VALUES (?, ?, ?, ?, ?, 'plant_csv')
                ''',
                (ts, DEVICE_SN, variable, value, unit),
            )
            n += 1
    return n


def touch_device_meta(conn: sqlite3.Connection, last_ts: pd.Timestamp) -> None:
    now = datetime.now().isoformat()
    conn.execute(
        '''
        UPDATE foxess_device_meta
        SET fetched_at = ?, device_sn = COALESCE(device_sn, ?)
        WHERE id = (SELECT id FROM foxess_device_meta ORDER BY id DESC LIMIT 1)
        ''',
        (now, DEVICE_SN),
    )
    # if empty table, skip
    if conn.total_changes == 0:
        pass


def summarize(df: pd.DataFrame) -> None:
    for day, g in df.groupby(df['timestamp'].dt.strftime('%Y-%m-%d')):
        print(
            f"  {day}: samples={len(g):4d}  "
            f"Solar≈{g['pv_energy_kwh'].sum():6.2f} kWh  "
            f"Import≈{g['grid_import_kwh'].sum():5.2f}  "
            f"Export≈{g['grid_export_kwh'].sum():5.2f}  "
            f"Load≈{g['load_energy_kwh'].sum():5.2f}  "
            f"SoC {g['battery_soc_percent'].iloc[0]:.0f}%→{g['battery_soc_percent'].iloc[-1]:.0f}%  "
            f"({g['timestamp'].iloc[0].strftime('%H:%M')}–{g['timestamp'].iloc[-1].strftime('%H:%M')})"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description='Import FoxESS plant-chart CSV into energy_model.db')
    parser.add_argument('csv', nargs='+', type=Path, help='Plant CSV path(s)')
    parser.add_argument('--db', type=Path, default=Path(os.getenv('DATABASE_PATH', DB_DEFAULT)))
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    frames = [read_plant_csv(p) for p in args.csv]
    df = (
        pd.concat(frames, ignore_index=True)
        .sort_values('timestamp')
        .drop_duplicates(subset=['timestamp'])
        .reset_index(drop=True)
    )
    print(f'Wczytano {len(df)} próbek z {len(args.csv)} plików:')
    summarize(df)

    if args.dry_run:
        print('Dry-run — bez zapisu do DB.')
        return 0

    conn = sqlite3.connect(args.db)
    try:
        n_data = replace_foxess_data(conn, df)
        n_report = replace_report_daily(conn, df)
        n_ts = replace_timeseries(conn, df)
        touch_device_meta(conn, df['timestamp'].max())
        conn.commit()
    finally:
        conn.close()

    print(
        f'\n✅ Zapisano do {args.db}:\n'
        f'   foxess_data:         {n_data} wierszy\n'
        f'   foxess_report_daily: {n_report} wierszy\n'
        f'   foxess_timeseries:   {n_ts} wierszy\n'
        f'   Źródło: plant_csv (∫ Solar ≈ proxy PVEnergyTotal)'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
