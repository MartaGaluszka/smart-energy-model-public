"""
Pobieranie WSZYSTKICH dostępnych danych z FoxEss Cloud API.

- Historia: wszystkie zmienne (get_vars), próbkowanie ~5 min
- Raporty dzienne: generation, feedin, loads, grid, bateria, PV
- Metadane urządzenia
- Zapis: SQLite (foxess_timeseries) + CSV w data/raw/

UWAGA: Import zapisuje SUROWE wartości z API.
       Target ML: pvPower z foxess_timeseries (bez filtra baterii).
       foxess_data.pv_power_kw preferuje pvPower nad generationPower.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from datetime import datetime, timedelta
from typing import List, Optional

import numpy as np
import pandas as pd
import foxesscloud.openapi as foxess
from dotenv import load_dotenv

# Ciche pobieranie (mniej logów z biblioteki)
foxess.debug_setting = 99

# Mapowanie zmiennych API → kolumny foxess_data (agregat)
CORE_TO_DB = {
    'generationPower': 'pv_power_kw',
    'pvPower': 'pv_power_kw',
    'loadsPower': 'load_power_kw',
    'feedinPower': 'grid_export_kw',
    'gridConsumptionPower': 'grid_import_kw',
    'batChargePower': 'battery_power_kw',
    'batDischargePower': 'battery_power_kw',
    'SoC': 'battery_soc_percent',
    'batTemperature': 'battery_temp_celsius',
    'BatVolt': 'battery_voltage_v',
    'meterPower': 'grid_power_kw',
}


def _api_key() -> str:
    load_dotenv()
    key = (os.getenv('FOXESS_API_KEY') or os.getenv('FOXESS_TOKEN') or '').strip().strip('"').strip("'")
    if not key:
        raise ValueError('Ustaw FOXESS_API_KEY w .env')
    return key


def _parse_date(value: str):
    return datetime.strptime(value.strip(), '%Y-%m-%d').date()


# SN zapisywany w SQLite (PII poza bazą; prawdziwy SN tylko w pamięci / .env do API)
_DB_DEVICE_SN_PLACEHOLDER = 'REDACTED'


def _device_sn_from_env() -> Optional[str]:
    load_dotenv()
    sn = (os.getenv('FOXESS_DEVICE_SN') or '').strip().strip('"').strip("'")
    if not sn or sn.upper() == _DB_DEVICE_SN_PLACEHOLDER:
        return None
    return sn


def _api_delay_sec(override: Optional[float] = None) -> float:
    if override is not None:
        return max(0.0, override)
    load_dotenv()
    return max(0.0, float(os.getenv('FOXESS_API_DELAY_SEC', '1.5')))


def _scrub_device_meta_for_db(device: dict) -> dict:
    """Kopia metadanych bez nazwy stacji / SN (zostają typ, status, wersje)."""
    d = json.loads(json.dumps(device, default=str))
    d['stationName'] = _DB_DEVICE_SN_PLACEHOLDER
    d['deviceSN'] = _DB_DEVICE_SN_PLACEHOLDER
    if d.get('moduleSN'):
        d['moduleSN'] = _DB_DEVICE_SN_PLACEHOLDER
    if d.get('stationID'):
        d['stationID'] = _DB_DEVICE_SN_PLACEHOLDER
    for bat in d.get('batteryList') or []:
        if isinstance(bat, dict) and bat.get('batterySN'):
            bat['batterySN'] = _DB_DEVICE_SN_PLACEHOLDER
    return d


def _bootstrap_device_from_db(db_path: str) -> bool:
    """Ustawia foxess.device z bazy — pomija /device/list przy limicie API.

    Nie nadpisuje prawdziwego SN wartością REDACTED z bazy — do API
    używamy FOXESS_DEVICE_SN z .env albo SN zwróconego przez get_device.
    """
    if not os.path.exists(db_path):
        return False
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        '''SELECT device_sn, raw_json FROM foxess_device_meta
           ORDER BY fetched_at DESC LIMIT 1'''
    ).fetchone()
    conn.close()
    if not row:
        return False
    db_sn, raw_json = row[0], row[1]
    if db_sn and str(db_sn).upper() != _DB_DEVICE_SN_PLACEHOLDER and not getattr(foxess, 'device_sn', None):
        foxess.device_sn = db_sn
    if raw_json:
        try:
            foxess.device = json.loads(raw_json)
            # Przywróć prawdziwy SN do obiektu w pamięci (jeśli znamy z env)
            env_sn = _device_sn_from_env()
            if env_sn:
                foxess.device_sn = env_sn
                if isinstance(foxess.device, dict):
                    foxess.device['deviceSN'] = env_sn
            return True
        except json.JSONDecodeError:
            pass
    return bool(getattr(foxess, 'device_sn', None))

def _retry_api(label: str, fn, *args, max_retries: int = 10, **kwargs):
    """Ponawia wywołanie przy braku odpowiedzi (np. errno 40402 — limit API)."""
    for attempt in range(max_retries):
        result = fn(*args, **kwargs)
        if result is not None and result is not False:
            return result
        wait = min(300, int(15 * (1.5 ** attempt)))
        print(
            f'\n⏳ {label}: limit API FoxESS (40402?) — czekam {wait}s '
            f'({attempt + 1}/{max_retries})...',
            flush=True,
        )
        time.sleep(wait)
    return None


def _normalize_timestamp_series(series: pd.Series) -> pd.Series:
    """Jednolity format DATETIME dla SQLite (bez stref / duplikatów tekstowych)."""
    ts = pd.to_datetime(
        series.astype(str).str.replace(r'\s+(CEST|CET|BST|UTC)\s*', ' ', regex=True),
        errors='coerce',
    )
    return ts.dt.strftime('%Y-%m-%d %H:%M:%S')


def _prepare_frame_for_sql(df: pd.DataFrame, unique_cols: tuple[str, ...]) -> pd.DataFrame:
    """Normalizacja + deduplikacja przed zapisem (INSERT OR REPLACE)."""
    if df.empty:
        return df
    out = df.copy()
    if 'timestamp' in out.columns:
        out['timestamp'] = _normalize_timestamp_series(out['timestamp'])
        out = out.dropna(subset=['timestamp'])
    if 'report_date' in out.columns:
        out['report_date'] = pd.to_datetime(out['report_date'], errors='coerce').dt.strftime('%Y-%m-%d')
        out = out.dropna(subset=['report_date'])
    dedupe_cols = [c for c in unique_cols if c in out.columns]
    if dedupe_cols:
        out = out.drop_duplicates(subset=dedupe_cols, keep='last')
    return out


def _configure_sqlite(conn: sqlite3.Connection) -> None:
    """WAL + busy_timeout — mniej konfliktów przy wieczornym odświeżeniu dnia."""
    conn.execute('PRAGMA busy_timeout=60000')
    conn.execute('PRAGMA journal_mode=WAL')


def _run_with_retry(
    conn: sqlite3.Connection,
    fn,
    *,
    max_retries: int = 8,
    label: str = 'sqlite',
) -> None:
    for attempt in range(max_retries):
        try:
            fn()
            return
        except sqlite3.OperationalError as exc:
            locked = 'locked' in str(exc).lower()
            if not locked or attempt == max_retries - 1:
                raise
            wait = min(30, 2 ** attempt)
            print(
                f'   ⏳ {label}: baza zablokowana — ponawiam za {wait}s '
                f'({attempt + 1}/{max_retries})...',
                flush=True,
            )
            time.sleep(wait)


def _upsert_dataframe(
    conn: sqlite3.Connection,
    table: str,
    df: pd.DataFrame,
    unique_cols: tuple[str, ...],
) -> int:
    """Bezpieczny zapis: INSERT OR REPLACE (upsert) zamiast ślepego append."""
    prepared = _prepare_frame_for_sql(df, unique_cols)
    if prepared.empty:
        return 0

    cols = [c for c in prepared.columns if c != 'id']
    placeholders = ', '.join(['?'] * len(cols))
    col_names = ', '.join(cols)
    sql = f'INSERT OR REPLACE INTO {table} ({col_names}) VALUES ({placeholders})'
    rows = prepared[cols].replace({np.nan: None}).itertuples(index=False, name=None)

    def _write() -> None:
        conn.executemany(sql, list(rows))

    _run_with_retry(conn, _write, label=f'upsert {table}')
    return len(prepared)


def _clear_date_range(conn: sqlite3.Connection, start, end) -> None:
    """Usuwa istniejące dane w zakresie przed ponownym importem.

    Uwaga: NIE filtrujemy po device_sn. W bazie jest dokładnie jedno fizyczne
    urządzenie, ale sposób jego zapisu zmieniał się w czasie (prawdziwy SN vs.
    placeholder `REDACTED` po wprowadzeniu anonimizacji PII) — filtrowanie po
    device_sn powodowało, że re-sync pod nową konwencją nie kasował starych
    wierszy zapisanych pod poprzednią, co podwajało sumy w `get_overview()`
    (zob. incydent z 2026-07-28: 231 wierszy pod prawdziwym SN + 246 pod
    REDACTED dla tego samego dnia → ~2x zawyżone kWh).
    """
    start_s, end_s = str(start), str(end)

    def _delete() -> None:
        for table, col in (
            ('foxess_timeseries', 'timestamp'),
            ('foxess_data', 'timestamp'),
            ('foxess_report_daily', 'report_date'),
        ):
            if col == 'report_date':
                conn.execute(
                    f'DELETE FROM {table} WHERE {col} BETWEEN ? AND ?',
                    (start_s, end_s),
                )
            else:
                conn.execute(
                    f'DELETE FROM {table} WHERE date({col}) BETWEEN ? AND ?',
                    (start_s, end_s),
                )
        conn.commit()

    _run_with_retry(conn, _delete, label='czyszczenie zakresu dat')


def resolve_date_range(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    days: Optional[int] = None,
) -> tuple:
    """
    Zakres dat do importu.

    Priorytet:
    1. argumenty start_date / end_date
    2. .env: FOXESS_START_DATE (+ opcjonalnie FOXESS_END_DATE)
    3. .env: FOXESS_HISTORY_DAYS (wstecz od dziś)
    """
    load_dotenv()

    if start_date:
        start = _parse_date(start_date)
    else:
        env_start = os.getenv('FOXESS_START_DATE', '').strip()
        start = _parse_date(env_start) if env_start else None

    if end_date:
        end = _parse_date(end_date)
    else:
        env_end = os.getenv('FOXESS_END_DATE', '').strip()
        end = _parse_date(env_end) if env_end else datetime.now().date()

    if start is None:
        n = days if days is not None else int(os.getenv('FOXESS_HISTORY_DAYS', '365'))
        start = end - timedelta(days=n - 1)

    if start > end:
        raise ValueError(f'Data początkowa {start} jest po końcowej {end}')

    total_days = (end - start).days + 1
    return start, end, total_days


def history_result_to_long(result: list, device_sn: str) -> pd.DataFrame:
    """Konwertuje odpowiedź get_history (summary=0) na long DataFrame."""
    rows = []
    if not result:
        return pd.DataFrame(columns=['timestamp', 'device_sn', 'variable', 'value', 'unit'])

    for block in result:
        var_name = block.get('variable') or block.get('name')
        unit = block.get('unit', '')
        for point in block.get('data') or []:
            t = point.get('time')
            val = point.get('value')
            if t is None:
                continue
            try:
                val_num = float(val) if val is not None and val != '' else None
            except (TypeError, ValueError):
                val_num = None
            rows.append({
                'timestamp': t,
                'device_sn': device_sn,
                'variable': var_name,
                'value': val_num,
                'unit': unit,
                'data_source': 'api',
            })

    if not rows:
        return pd.DataFrame(columns=[
            'timestamp', 'device_sn', 'variable', 'value', 'unit', 'data_source',
        ])
    return pd.DataFrame(rows)


def _parse_foxess_timestamps(series: pd.Series) -> pd.Series:
    """FoxESS Cloud zwraca czasy z doklejonym skrótem strefy tuż przed offsetem,
    np. '2026-07-28 00:04:00 CEST+0200' — format zależny od strefy czasowej
    kontenera (locale FoxESS-Cloud), którego `pd.to_datetime` nie potrafi
    rozpoznać wprost. Usuwamy skrót, zostawiając sam offset liczbowy."""
    return pd.to_datetime(
        series.astype(str).str.replace(r'\s+(CEST|CET|BST|UTC)\s*', ' ', regex=True),
        errors='coerce',
    )


def history_to_wide(long_df: pd.DataFrame) -> pd.DataFrame:
    """Pivot long → wide + główne kolumny pod foxess_data."""
    if long_df.empty:
        return pd.DataFrame()

    long_df = long_df.copy()
    long_df['value'] = pd.to_numeric(long_df['value'], errors='coerce')
    long_df['timestamp'] = _parse_foxess_timestamps(long_df['timestamp'])
    long_df = long_df.dropna(subset=['timestamp'])

    wide = long_df.pivot_table(
        index=['timestamp', 'device_sn'],
        columns='variable',
        values='value',
        aggfunc='first',
    ).reset_index()

    out = pd.DataFrame()
    out['timestamp'] = wide['timestamp']
    out['device_sn'] = wide['device_sn']
    out['data_source'] = 'api'

    def col_if_exists(name):
        return wide[name] if name in wide.columns else None

    if col_if_exists('pvPower') is not None:
        out['pv_power_kw'] = col_if_exists('pvPower')
    elif col_if_exists('generationPower') is not None:
        out['pv_power_kw'] = col_if_exists('generationPower')

    if col_if_exists('loadsPower') is not None:
        out['load_power_kw'] = col_if_exists('loadsPower')
    if col_if_exists('feedinPower') is not None:
        out['grid_export_kw'] = col_if_exists('feedinPower')
    if col_if_exists('gridConsumptionPower') is not None:
        out['grid_import_kw'] = col_if_exists('gridConsumptionPower')
    if col_if_exists('meterPower') is not None:
        out['grid_power_kw'] = col_if_exists('meterPower')
    if col_if_exists('SoC') is not None:
        out['battery_soc_percent'] = col_if_exists('SoC')
    if col_if_exists('batTemperature') is not None:
        out['battery_temp_celsius'] = col_if_exists('batTemperature')
    if col_if_exists('BatVolt') is not None:
        out['battery_voltage_v'] = col_if_exists('BatVolt')

    charge = col_if_exists('batChargePower')
    discharge = col_if_exists('batDischargePower')
    if charge is not None or discharge is not None:
        out['battery_power_kw'] = (charge.fillna(0) if charge is not None else 0) - (
            discharge.fillna(0) if discharge is not None else 0
        )

    interval_h = 5 / 60
    for power_col, energy_col in [
        ('pv_power_kw', 'pv_energy_kwh'),
        ('load_power_kw', 'load_energy_kwh'),
        ('grid_import_kw', 'grid_import_kwh'),
        ('grid_export_kw', 'grid_export_kwh'),
    ]:
        if power_col in out.columns:
            out[energy_col] = out[power_col].fillna(0) * interval_h

    return out


def ensure_extended_schema(conn: sqlite3.Connection) -> None:
    schema_path = 'config/foxess_schema_extended.sql'
    if os.path.exists(schema_path):
        with open(schema_path, encoding='utf-8') as f:
            conn.executescript(f.read())
        conn.commit()


def fetch_all(
    days: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db_path: str = 'data/energy_model.db',
    save_csv: bool = True,
    api_delay: Optional[float] = None,
    max_retries: int = 10,
    replace_range: bool = True,
) -> dict:
    """
    Pobiera dane historyczne + raporty w zadanym zakresie dat.

    Returns:
        statystyki importu
    """
    foxess.api_key = _api_key()
    start, end, total_days = resolve_date_range(start_date, end_date, days)
    delay = _api_delay_sec(api_delay)

    env_sn = _device_sn_from_env()
    if env_sn:
        foxess.device_sn = env_sn
    if _bootstrap_device_from_db(db_path):
        print('📦 Urządzenie z cache bazy (mniej zapytań do API)')
    # Env zawsze wygrywa nad cache (cache może mieć REDACTED)
    if env_sn:
        foxess.device_sn = env_sn

    device = _retry_api('get_device', foxess.get_device, max_retries=max_retries)
    if not device:
        raise RuntimeError(
            'Nie można załadować urządzenia (get_device). '
            'FoxESS zwraca limit zapytań (40402) — odczekaj 30–60 min i uruchom ponownie, '
            'albo pobieraj krótszymi odcinkami (np. --from 2025-11-01 --to 2025-11-30). '
            'Upewnij się, że FOXESS_API_KEY jest w .env (opcjonalnie FOXESS_DEVICE_SN).'
        )

    # Prawdziwy SN tylko do wywołań API; w SQLite trzymamy placeholder
    api_device_sn = (
        foxess.device_sn
        or device.get('deviceSN')
        or device.get('sn')
        or env_sn
    )
    if not api_device_sn:
        raise RuntimeError(
            'Brak numeru falownika z API. Ustaw FOXESS_DEVICE_SN w .env '
            'albo sprawdź, czy klucz API ma dostęp do urządzenia.'
        )
    foxess.device_sn = api_device_sn
    device_sn = _DB_DEVICE_SN_PLACEHOLDER
    print(f'📟 Urządzenie: API OK ({device.get("deviceType", "?")}) → zapis w DB jako {device_sn}')
    variables = _retry_api('get_vars', foxess.get_vars, max_retries=max_retries)
    if not variables:
        raise RuntimeError('Brak listy zmiennych (get_vars) — spróbuj ponownie za chwilę.')

    print(f'📋 Zmiennych do pobrania: {len(variables)}')
    print(f'📅 Zakres: {start} → {end} ({total_days} dni)')
    if delay > 0:
        print(f'⏱️  Opóźnienie między dniami: {delay}s (FOXESS_API_DELAY_SEC)')

    all_long = []
    failed_days = []
    load_dotenv()
    pause_every = int(os.getenv('FOXESS_PAUSE_EVERY_N_DAYS', '10'))
    pause_sec = int(os.getenv('FOXESS_PAUSE_SEC', '45'))

    for i in range(total_days):
        day = (start + timedelta(days=i)).strftime('%Y-%m-%d')
        print(f'  [{i+1}/{total_days}] {day}...', end=' ', flush=True)

        try:
            result = _retry_api(
                f'historia {day}',
                lambda d=day: foxess.get_history(
                    time_span='day',
                    d=d,
                    v=variables,
                    summary=0,
                    plot=0,
                ),
                max_retries=5,
            )
            if result:
                df_day = history_result_to_long(result, device_sn)
                if df_day.empty:
                    failed_days.append(day)
                    print('0 punktów')
                else:
                    all_long.append(df_day)
                    print(f'{len(df_day)} punktów')
            else:
                failed_days.append(day)
                print('brak danych')
        except Exception as e:
            failed_days.append(day)
            print(f'błąd: {e}')

        if delay > 0 and i < total_days - 1:
            time.sleep(delay)
        if pause_every > 0 and (i + 1) % pause_every == 0 and i < total_days - 1:
            print(f'\n⏸️  Przerwa {pause_sec}s co {pause_every} dni (limit API)...', flush=True)
            time.sleep(pause_sec)

    if not all_long:
        msg = 'Nie pobrano żadnych danych historycznych w tym zakresie.'
        if failed_days:
            msg += f' Dni bez punktów w API: {", ".join(failed_days)}.'
        msg += ' (FoxESS często nie ma historii sprzed instalacji lub z przerw w rejestracji.)'
        raise RuntimeError(msg)

    print('\n⏳ Łączę dane i zapisuję do bazy (może chwilę potrwać)...')
    long_df = pd.concat(all_long, ignore_index=True)
    long_df['timestamp'] = _parse_foxess_timestamps(long_df['timestamp'])
    long_df = long_df.dropna(subset=['timestamp'])

    wide_df = history_to_wide(long_df)

    os.makedirs('data/raw', exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')

    if save_csv:
        long_path = f'data/raw/foxess_all_variables_{ts}.csv'
        wide_path = f'data/raw/foxess_core_{ts}.csv'
        long_df.to_csv(long_path, index=False)
        wide_df.to_csv(wide_path, index=False)
        print(f'💾 CSV (wszystkie zmienne): {long_path}')
        print(f'💾 CSV (rdzeń): {wide_path}')

    # Baza danych
    os.makedirs(os.path.dirname(db_path) or '.', exist_ok=True)
    if not os.path.exists(db_path):
        base_schema = 'config/database_schema.sql'
        if os.path.exists(base_schema):
            conn = sqlite3.connect(db_path)
            with open(base_schema, encoding='utf-8') as f:
                conn.executescript(f.read())
            conn.close()

    conn = sqlite3.connect(db_path)
    _configure_sqlite(conn)
    ensure_extended_schema(conn)

    if replace_range:
        print(f'🗑️  Czyszczę istniejące dane w zakresie {start} → {end}...')
        _clear_date_range(conn, start, end)

    # Metadane urządzenia (bez nazwy / SN — klucz API zostaje w .env)
    device_for_db = _scrub_device_meta_for_db(device)
    conn.execute(
        '''INSERT OR REPLACE INTO foxess_device_meta
           (device_sn, fetched_at, device_type, status, raw_json)
           VALUES (?, ?, ?, ?, ?)''',
        (
            device_sn,
            datetime.now().isoformat(),
            device.get('deviceType'),
            device.get('status'),
            json.dumps(device_for_db, default=str),
        ),
    )
    # Wszystkie zmienne (long) — upsert (bezpieczne przy wieczornym odświeżeniu dnia)
    ts_rows = _upsert_dataframe(
        conn,
        'foxess_timeseries',
        long_df,
        ('timestamp', 'device_sn', 'variable'),
    )

    # Agregat foxess_data
    wide_rows = 0
    if not wide_df.empty:
        cols = [c for c in wide_df.columns if c in {
            'timestamp', 'pv_power_kw', 'pv_energy_kwh', 'battery_soc_percent',
            'battery_power_kw', 'battery_temp_celsius', 'battery_voltage_v',
            'load_power_kw', 'load_energy_kwh', 'grid_import_kwh',
            'grid_export_kwh', 'grid_power_kw', 'device_sn', 'data_source',
        }]
        wide_rows = _upsert_dataframe(
            conn,
            'foxess_data',
            wide_df[cols],
            ('timestamp', 'device_sn'),
        )

    # Raporty dzienne (ten sam zakres dat)
    print(f'\n📊 Raporty dzienne ({total_days} dni)...')
    report_rows = []
    for j in range(total_days):
        rd = (start + timedelta(days=j)).strftime('%Y-%m-%d')
        rep = _retry_api(
            f'raport {rd}',
            lambda d=rd: foxess.get_report(dimension='day', d=d, summary=1, plot=0),
            max_retries=5,
        )
        if not rep:
            continue
        if delay > 0:
            time.sleep(delay)
        for var_block in rep:
            var = var_block.get('variable')
            total = var_block.get('total')
            for hi, val in enumerate(var_block.get('values') or []):
                report_rows.append({
                    'report_date': rd,
                    'device_sn': device_sn,
                    'variable': var,
                    'hour_index': hi,
                    'value_kwh': val,
                    'total_kwh': total,
                })

    report_rows_written = 0
    if report_rows:
        report_rows_written = _upsert_dataframe(
            conn,
            'foxess_report_daily',
            pd.DataFrame(report_rows),
            ('report_date', 'device_sn', 'variable', 'hour_index'),
        )

    conn.commit()
    conn.close()

    stats = {
        'device_sn': device_sn,
        'variables_count': len(variables),
        'date_start': str(start),
        'date_end': str(end),
        'days_requested': total_days,
        'days_failed': len(failed_days),
        'timeseries_rows': ts_rows,
        'unique_variables': long_df['variable'].nunique() if not long_df.empty else 0,
        'foxess_data_rows': wide_rows,
        'report_rows': report_rows_written,
        'date_from': str(long_df['timestamp'].min()),
        'date_to': str(long_df['timestamp'].max()),
    }

    print('\n' + '=' * 60)
    print('✅ Pobieranie zakończone')
    for k, v in stats.items():
        print(f'   {k}: {v}')
    if failed_days:
        print(f'   dni bez danych: {failed_days[:10]}{"..." if len(failed_days) > 10 else ""}')
    print('=' * 60)

    return stats


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Pobierz wszystkie dane FoxEss z API')
    parser.add_argument(
        '--from',
        dest='start_date',
        metavar='YYYY-MM-DD',
        help='Data początkowa (np. 2025-05-01)',
    )
    parser.add_argument('--to', dest='end_date', metavar='YYYY-MM-DD', help='Data końcowa (domyślnie dziś)')
    parser.add_argument(
        '--delay',
        type=float,
        default=None,
        help='Sekundy między dniami (domyślnie FOXESS_API_DELAY_SEC=1.5)',
    )
    parser.add_argument(
        '--max-retries',
        type=int,
        default=int(os.getenv('FOXESS_MAX_RETRIES', '2')),
        help='Maks. ponowień przy limicie API (40402); domyślnie FOXESS_MAX_RETRIES=2 (fail-fast)',
    )
    parser.add_argument(
        '--no-replace',
        action='store_true',
        help='Nie usuwaj danych w zakresie przed zapisem (domyślnie: usuń przy --from/--to)',
    )
    parser.add_argument(
        '--may-2025',
        action='store_true',
        help='Skrót: od 2025-05-01',
    )
    parser.add_argument(
        '--april-2025',
        action='store_true',
        help='Skrót: od 2025-04-01',
    )
    parser.add_argument(
        '--no-csv',
        action='store_true',
        help='Nie zapisuj kopii CSV w data/raw/ (tylko baza SQLite)',
    )
    parser.add_argument(
        '--csv',
        action='store_true',
        help='Wymuś zapis CSV (domyślnie, chyba że --no-csv)',
    )
    args = parser.parse_args()

    start = args.start_date
    if args.may_2025:
        start = '2025-05-01'
    if args.april_2025:
        start = '2025-04-01'

    print('=' * 60)
    print('FoxEss — pobieranie WSZYSTKICH dostępnych danych')
    print('=' * 60)
    explicit_range = bool(
        args.start_date or args.end_date or args.may_2025 or args.april_2025
    )
    save_csv = not args.no_csv
    if args.csv:
        save_csv = True

    fetch_all(
        start_date=start,
        end_date=args.end_date,
        api_delay=args.delay,
        max_retries=args.max_retries,
        replace_range=explicit_range and not args.no_replace,
        save_csv=save_csv,
    )


if __name__ == '__main__':
    main()
