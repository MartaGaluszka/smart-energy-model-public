#!/usr/bin/env python3
"""Generator deterministycznej bazy demo — NIE rusza data/energy_model.db.

Zapisuje wyłącznie do data/demo.db (lub --output wskazujący na *demo*.db).
Stały seed → te same dane u każdej osoby. Dane fikcyjne (SN, lokalizacja).

Użycie:
  PYTHONPATH=$PWD ./venv/bin/python scripts/demo/make_demo_db.py
  DATABASE_PATH=data/demo.db FOXESS_SYNC_DISABLED=1 \\
    ./venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import argparse
import math
import os
import random
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = REPO_ROOT / 'data' / 'demo.db'
FORBIDDEN_NAMES = {'energy_model.db', 'foxess.db', 'smart_energy.db'}
DEMO_SN = 'DEMO-DEVICE-001'
DEMO_EMAIL = 'mobile.demo@example.com'
DEMO_PASSWORD = 'demo12345678'
SEED = 42
DAYS = 30
LOCATION = 'demo-site'  # fikcyjna etykieta, bez GPS


def _refuse_production_path(path: Path) -> None:
    resolved = path.resolve()
    name = resolved.name.lower()
    if name in FORBIDDEN_NAMES or 'energy_model' in name:
        raise SystemExit(
            f'Odmowa: nie wolno zapisywać do bazy produkcyjnej ({resolved}). '
            'Użyj data/demo.db lub ścieżki z „demo” w nazwie pliku.'
        )
    if 'demo' not in name:
        raise SystemExit(
            f'Odmowa: output musi mieć „demo” w nazwie pliku (dostałem {resolved.name}).'
        )
    # Nie nadpisuj niczego poza katalogiem data/ w repo (bezpieczeństwo ścieżek).
    data_dir = (REPO_ROOT / 'data').resolve()
    if data_dir not in resolved.parents and resolved.parent != data_dir:
        raise SystemExit(f'Odmowa: output musi leżeć pod {data_dir} (dostałem {resolved}).')


def _connect_new(path: Path) -> sqlite3.Connection:
    if path.exists():
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def _create_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE foxess_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME NOT NULL,
            pv_power_kw REAL,
            pv_energy_kwh REAL,
            pv_energy_daily_kwh REAL,
            battery_soc_percent REAL,
            battery_power_kw REAL,
            battery_energy_kwh REAL,
            battery_temp_celsius REAL,
            load_power_kw REAL,
            load_energy_kwh REAL,
            load_energy_daily_kwh REAL,
            grid_import_kwh REAL,
            grid_export_kwh REAL,
            grid_power_kw REAL,
            device_sn VARCHAR(50),
            data_source VARCHAR(20) DEFAULT 'demo',
            UNIQUE(timestamp, device_sn)
        );
        CREATE INDEX idx_foxess_timestamp ON foxess_data(timestamp);
        CREATE INDEX idx_foxess_date ON foxess_data(DATE(timestamp));

        CREATE TABLE foxess_report_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_date DATE NOT NULL,
            device_sn VARCHAR(50) NOT NULL,
            variable VARCHAR(80) NOT NULL,
            hour_index INTEGER,
            value_kwh REAL,
            total_kwh REAL,
            UNIQUE(report_date, device_sn, variable, hour_index)
        );
        CREATE INDEX idx_foxess_report_date ON foxess_report_daily(report_date);

        CREATE TABLE foxess_device_meta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_sn VARCHAR(50) NOT NULL UNIQUE,
            fetched_at DATETIME NOT NULL,
            device_type VARCHAR(50),
            status INTEGER,
            raw_json TEXT
        );

        CREATE TABLE weather_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME NOT NULL,
            temperature_celsius REAL,
            humidity_percent REAL,
            pressure_hpa REAL,
            solar_radiation_wm2 REAL,
            sunshine_duration_min REAL,
            cloud_cover_percent REAL,
            cloud_cover_low_percent REAL,
            cloud_cover_mid_percent REAL,
            cloud_cover_high_percent REAL,
            visibility_m REAL,
            wind_speed_ms REAL,
            wind_direction_deg REAL,
            precipitation_mm REAL,
            snowfall_cm REAL,
            snow_depth_m REAL,
            location VARCHAR(100),
            data_source VARCHAR(50),
            UNIQUE(timestamp, location)
        );
        CREATE INDEX idx_weather_timestamp ON weather_data(timestamp);

        CREATE TABLE tauron_tariff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            valid_from DATE NOT NULL,
            valid_to DATE,
            tariff_name VARCHAR(20) DEFAULT 'G12w',
            price_zone1_day REAL NOT NULL,
            price_zone2_night REAL NOT NULL,
            distribution_zone1 REAL,
            distribution_zone2 REAL,
            subscription_fee_monthly REAL,
            power_fee_monthly REAL,
            transition_fee_monthly REAL,
            oze_fee_kwh REAL,
            cogenerative_fee_kwh REAL,
            notes TEXT
        );
        CREATE UNIQUE INDEX idx_tauron_tariff_valid_from ON tauron_tariff(valid_from);

        CREATE TABLE app_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email VARCHAR(255) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            created_at DATETIME NOT NULL
        );

        CREATE TABLE notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            notif_type VARCHAR(40) NOT NULL,
            title VARCHAR(200) NOT NULL,
            body TEXT NOT NULL,
            payload_json TEXT,
            created_at DATETIME NOT NULL,
            read_at DATETIME,
            FOREIGN KEY(user_id) REFERENCES app_users(id) ON DELETE CASCADE
        );

        CREATE TABLE household_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            event_date VARCHAR(10) NOT NULL,
            event_type VARCHAR(30) NOT NULL,
            impact VARCHAR(20) NOT NULL DEFAULT 'neutral',
            note TEXT,
            start_time VARCHAR(5),
            duration_min INTEGER,
            planned_time VARCHAR(5),
            created_at DATETIME NOT NULL,
            FOREIGN KEY(user_id) REFERENCES app_users(id) ON DELETE CASCADE
        );

        CREATE TABLE battery_strategy_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            soc_min_percent REAL NOT NULL DEFAULT 20.0,
            soc_target_percent REAL NOT NULL DEFAULT 80.0,
            efficiency_pct REAL NOT NULL DEFAULT 93.0,
            price_zone1 REAL,
            price_zone2 REAL,
            season VARCHAR(10) NOT NULL DEFAULT 'auto',
            battery_capacity_kwh REAL,
            ac_power_kw REAL,
            fc_max_minutes REAL NOT NULL DEFAULT 15.0,
            fc_night_start_hour INTEGER NOT NULL DEFAULT 22,
            battery_automation_enabled BOOLEAN NOT NULL DEFAULT 0,
            schedule_windows_json TEXT,
            schedule_preset VARCHAR(10) NOT NULL DEFAULT 'g12w',
            updated_at DATETIME NOT NULL,
            FOREIGN KEY(user_id) REFERENCES app_users(id) ON DELETE CASCADE
        );
        """
    )


def _day_profile(rng: random.Random, day_index: int) -> dict:
    """Syntetyczny dzień: słoneczny / mieszany / pochmurny (deterministycznie)."""
    kind = day_index % 5
    if kind in (0, 1):
        cloud = rng.uniform(10, 35)
        pv_peak = rng.uniform(4.5, 6.2)
    elif kind in (2, 3):
        cloud = rng.uniform(40, 70)
        pv_peak = rng.uniform(2.5, 4.2)
    else:
        cloud = rng.uniform(75, 95)
        pv_peak = rng.uniform(0.8, 2.0)
    return {'cloud': cloud, 'pv_peak': pv_peak}


def _pv_kw(hour: float, peak: float) -> float:
    if hour < 6 or hour > 20:
        return 0.0
    # pół-sinus między 6 a 20
    x = (hour - 6) / 14.0
    return max(0.0, peak * math.sin(math.pi * x))


def _load_kw(hour: float, rng: random.Random) -> float:
    base = 0.35
    if 7 <= hour < 9:
        base = 1.2
    elif 11 <= hour < 14:
        base = 0.7
    elif 17 <= hour < 22:
        base = 1.6
    return max(0.15, base + rng.uniform(-0.1, 0.15))


def _fill_energy_days(
    conn: sqlite3.Connection, end_day: date, rng: random.Random, days: int
) -> None:
    foxess_rows: list[tuple] = []
    report_rows: list[tuple] = []
    weather_rows: list[tuple] = []
    start_day = end_day - timedelta(days=days - 1)

    for d_i in range(days):
        day = start_day + timedelta(days=d_i)
        profile = _day_profile(rng, d_i)
        soc = 55.0 + rng.uniform(-10, 10)
        daily_pv = 0.0
        daily_load = 0.0
        daily_import = 0.0
        daily_export = 0.0

        for h in range(24):
            for minute in (0, 30):  # co 30 min — wystarczy do wykresów
                ts = datetime(day.year, day.month, day.day, h, minute, 0)
                hour_f = h + minute / 60.0
                pv = _pv_kw(hour_f, profile['pv_peak'])
                load = _load_kw(hour_f, rng)
                # bateria: ładuj w południe, rozładuj wieczorem
                if 10 <= hour_f < 15 and soc < 90:
                    bat_p = min(2.0, max(0.0, pv - load))
                    soc = min(95.0, soc + bat_p * 0.5 * 100 / 10)  # ~10 kWh pack
                elif 18 <= hour_f < 23 and soc > 20:
                    bat_p = -min(2.0, max(0.0, load - pv))
                    soc = max(15.0, soc + bat_p * 0.5 * 100 / 10)
                else:
                    bat_p = 0.0

                grid = load - pv - bat_p
                # energia w przedziale 0.5 h
                dt_h = 0.5
                pv_e = pv * dt_h
                load_e = load * dt_h
                imp_e = max(0.0, grid) * dt_h
                exp_e = max(0.0, -grid) * dt_h
                daily_pv += pv_e
                daily_load += load_e
                daily_import += imp_e
                daily_export += exp_e

                foxess_rows.append(
                    (
                        ts.strftime('%Y-%m-%d %H:%M:%S'),
                        round(pv, 3),
                        round(pv_e, 4),
                        None,
                        round(soc, 1),
                        round(bat_p, 3),
                        round(soc / 100 * 10, 3),
                        22.0,
                        round(load, 3),
                        round(load_e, 4),
                        None,
                        round(imp_e, 4),
                        round(exp_e, 4),
                        round(grid, 3),
                        DEMO_SN,
                        'demo',
                    )
                )

                # pogoda godzinowa (raz na godzinę)
                if minute == 0:
                    elev = max(0.0, math.sin(math.pi * max(0.0, min(1.0, (hour_f - 6) / 14))))
                    weather_rows.append(
                        (
                            ts.strftime('%Y-%m-%d %H:%M:%S'),
                            round(8 + 12 * elev + rng.uniform(-1, 1), 1),
                            round(55 + rng.uniform(-10, 10), 1),
                            1013.0,
                            round(900 * elev * (1 - profile['cloud'] / 150), 1),
                            round(60 * elev, 1),
                            round(profile['cloud'], 1),
                            None,
                            None,
                            None,
                            10000.0,
                            round(rng.uniform(1, 5), 1),
                            round(rng.uniform(0, 360), 0),
                            0.0 if profile['cloud'] < 80 else round(rng.uniform(0, 0.4), 2),
                            0.0,
                            0.0,
                            LOCATION,
                            'demo',
                        )
                    )

        for variable, total in (
            ('PVEnergyTotal', daily_pv),
            ('loads', daily_load),
            ('gridConsumption', daily_import),
            ('feedin', daily_export),
        ):
            report_rows.append(
                (day.isoformat(), DEMO_SN, variable, None, None, round(total, 3))
            )

    conn.executemany(
        """
        INSERT INTO foxess_data (
            timestamp, pv_power_kw, pv_energy_kwh, pv_energy_daily_kwh,
            battery_soc_percent, battery_power_kw, battery_energy_kwh, battery_temp_celsius,
            load_power_kw, load_energy_kwh, load_energy_daily_kwh,
            grid_import_kwh, grid_export_kwh, grid_power_kw, device_sn, data_source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        foxess_rows,
    )
    conn.executemany(
        """
        INSERT INTO foxess_report_daily
            (report_date, device_sn, variable, hour_index, value_kwh, total_kwh)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        report_rows,
    )
    conn.executemany(
        """
        INSERT INTO weather_data (
            timestamp, temperature_celsius, humidity_percent, pressure_hpa,
            solar_radiation_wm2, sunshine_duration_min, cloud_cover_percent,
            cloud_cover_low_percent, cloud_cover_mid_percent, cloud_cover_high_percent,
            visibility_m, wind_speed_ms, wind_direction_deg, precipitation_mm,
            snowfall_cm, snow_depth_m, location, data_source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        weather_rows,
    )

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn.execute(
        """
        INSERT INTO foxess_device_meta (device_sn, fetched_at, device_type, status, raw_json)
        VALUES (?, ?, 'demo-inverter', 1, '{"demo": true}')
        """,
        (DEMO_SN, now),
    )


def _fill_tariff_and_app(conn: sqlite3.Connection, end_day: date, days: int) -> None:
    conn.execute(
        """
        INSERT INTO tauron_tariff (
            valid_from, valid_to, tariff_name,
            price_zone1_day, price_zone2_night,
            distribution_zone1, distribution_zone2,
            subscription_fee_monthly, power_fee_monthly, transition_fee_monthly,
            oze_fee_kwh, cogenerative_fee_kwh, notes
        ) VALUES (?, NULL, 'G12w', 0.62, 0.28, 0.25, 0.12, 12.0, 15.0, 1.5, 0.003, 0.002, 'demo tariff')
        """,
        ((end_day - timedelta(days=days)).isoformat(),),
    )

    # Hash hasła jak w API (bcrypt). Fallback: stub, gdy passlib niedostępne w PATH.
    try:
        sys.path.insert(0, str(REPO_ROOT))
        from api.security import hash_password

        password_hash = hash_password(DEMO_PASSWORD)
    except Exception as exc:  # noqa: BLE001
        print(f'[warn] nie udało się użyć api.security.hash_password ({exc}); bcrypt ręcznie')
        from passlib.context import CryptContext

        password_hash = CryptContext(schemes=['bcrypt'], deprecated='auto').hash(DEMO_PASSWORD)

    created = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    cur = conn.execute(
        """
        INSERT INTO app_users (email, password_hash, is_active, created_at)
        VALUES (?, ?, 1, ?)
        """,
        (DEMO_EMAIL, password_hash, created),
    )
    user_id = cur.lastrowid

    conn.execute(
        """
        INSERT INTO battery_strategy_settings (
            user_id, soc_min_percent, soc_target_percent, efficiency_pct,
            season, battery_capacity_kwh, battery_automation_enabled,
            schedule_preset, updated_at
        ) VALUES (?, 20.0, 80.0, 93.0, 'auto', 10.0, 0, 'g12w', ?)
        """,
        (user_id, created),
    )
    conn.execute(
        """
        INSERT INTO notifications (user_id, notif_type, title, body, created_at)
        VALUES (?, 'battery_advice', 'Demo: SoC wieczorem',
                'Sugestia doradcza (dane demo). System tylko doradza.', ?)
        """,
        (user_id, created),
    )
    # kilka AGD na ostatnich dniach
    for offset, (etype, start, dur) in enumerate(
        (
            ('washer', '10:30', 120),
            ('dishwasher', '13:00', 90),
            ('dryer', '16:00', 60),
        )
    ):
        ed = (end_day - timedelta(days=offset)).isoformat()
        conn.execute(
            """
            INSERT INTO household_events (
                user_id, event_date, event_type, impact, note,
                start_time, duration_min, planned_time, created_at
            ) VALUES (?, ?, ?, 'high', 'demo', ?, ?, ?, ?)
            """,
            (user_id, ed, etype, start, dur, start, created),
        )


def main() -> int:
    parser = argparse.ArgumentParser(description='Generuje izolowaną data/demo.db')
    parser.add_argument(
        '--output',
        type=Path,
        default=DEFAULT_OUTPUT,
        help='Ścieżka wyjściowa (musi mieć „demo” w nazwie; domyślnie data/demo.db)',
    )
    parser.add_argument('--days', type=int, default=DAYS)
    parser.add_argument('--seed', type=int, default=SEED)
    args = parser.parse_args()

    out = args.output if args.output.is_absolute() else (REPO_ROOT / args.output)
    _refuse_production_path(out)

    days = args.days
    rng = random.Random(args.seed)
    # Dane kończą się DZIŚ, żeby Home (lookback) od razu zobaczył has_data.
    end_day = date.today()

    conn = _connect_new(out)
    try:
        _create_tables(conn)
        _fill_energy_days(conn, end_day, rng, days)
        _fill_tariff_and_app(conn, end_day, days)
        conn.commit()
    finally:
        conn.close()

    # Sanity: nie wolno było tknąć produkcji
    prod = REPO_ROOT / 'data' / 'energy_model.db'
    print(f'OK: zapisano {out}')
    print(f'    seed={args.seed} days={days} end={end_day.isoformat()} sn={DEMO_SN}')
    print(f'    login demo: {DEMO_EMAIL} / {DEMO_PASSWORD}')
    print(f'    produkcja nietknięta: {prod} exists={prod.exists()}')
    print()
    print('Uruchomienie API na demo (osobny proces, bez zmiany .env produkcyjnego):')
    print(
        f'  DATABASE_PATH={out.relative_to(REPO_ROOT)} FOXESS_SYNC_DISABLED=1 \\'
    )
    print('    ./venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
