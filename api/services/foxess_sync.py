"""Cienki adapter FastAPI -> src/data/foxess_fetch_all.py, src/data/foxess_api.py.

Mapowanie wg §12.5 PROJEKT_APLIKACJA_MOBILNA.md. Nie przepisuje logiki — woła
istniejące funkcje z `src/*`. Redaguje SN/PII w odpowiedziach (§12.1/§12.4).
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date, datetime, timedelta

from api.config import get_settings
from api.errors import ApiError

# Zabezpieczenie przed biciem w limit FoxESS Cloud (40402), gdy użytkownik odświeża
# ekran częściej niż realnie zmieniają się dane.
SYNC_COOLDOWN_MINUTES = 3
# Gdy w bazie nie ma jeszcze żadnych danych FoxESS, ile dni wstecz pobrać na start.
DEFAULT_LOOKBACK_DAYS = 5


def sync_range(start: str, end: str) -> dict:
    """Wywołuje `src.data.foxess_fetch_all.fetch_all()` (upsert = idempotentne, §12.1)."""
    from src.data.foxess_fetch_all import fetch_all

    settings = get_settings()
    try:
        stats = fetch_all(
            start_date=start,
            end_date=end,
            db_path=settings.DATABASE_PATH,
            save_csv=False,
        )
    except RuntimeError as exc:
        # Najczęściej: brak FOXESS_API_KEY, limit 40402, lub brak urządzenia.
        raise ApiError(502, 'FOXESS_SYNC_FAILED', str(exc)) from exc

    days = (datetime.fromisoformat(end).date() - datetime.fromisoformat(start).date()).days + 1
    rows = stats.get('foxess_data_rows', '?') if isinstance(stats, dict) else '?'
    return {
        'status': 'ok',
        'start': start,
        'end': end,
        'days': days,
        'message': f'Sync zakończony ({rows} wierszy foxess_data)',
    }


def sync_incremental() -> dict:
    """Bez podanego zakresu dat: backend sam dobiera brakujący odcinek (od ostatniego
    zsynchronizowanego dnia do dziś) i pomija wywołanie FoxESS, jeśli dane są już
    aktualne (cooldown), by nie bić w limit API Fox (40402)."""
    settings = get_settings()
    today = date.today().isoformat()

    if not os.path.exists(settings.DATABASE_PATH):
        start = (date.today() - timedelta(days=DEFAULT_LOOKBACK_DAYS)).isoformat()
        return sync_range(start, today)

    conn = _connect(settings.DATABASE_PATH)
    try:
        last_date_row = conn.execute('SELECT MAX(DATE(timestamp)) FROM foxess_data').fetchone()
        last_date = last_date_row[0] if last_date_row else None
        meta_row = conn.execute(
            'SELECT fetched_at FROM foxess_device_meta ORDER BY fetched_at DESC LIMIT 1'
        ).fetchone()
        last_synced_at = meta_row['fetched_at'] if meta_row else None
    finally:
        conn.close()

    if last_synced_at:
        try:
            synced_dt = datetime.fromisoformat(str(last_synced_at).replace(' ', 'T')[:19])
            age_minutes = (datetime.now() - synced_dt).total_seconds() / 60
        except ValueError:
            age_minutes = None
        if age_minutes is not None and age_minutes < SYNC_COOLDOWN_MINUTES:
            return {
                'status': 'skipped',
                'start': last_date,
                'end': today,
                'days': 0,
                'message': f'Dane aktualne — ostatni sync {int(age_minutes)} min temu.',
            }

    start = last_date or (date.today() - timedelta(days=DEFAULT_LOOKBACK_DAYS)).isoformat()
    return sync_range(start, today)


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_overview(day: str | None = None) -> dict:
    settings = get_settings()
    target_day = day or date.today().isoformat()
    result = {
        'day': target_day,
        'pv_kwh': None,
        'soc_percent': None,
        'grid_import_kwh': None,
        'grid_export_kwh': None,
        'load_kwh': None,
        'device_sn_display': 'REDACTED',
        'last_synced_at': None,
        'has_data': False,
    }

    if not os.path.exists(settings.DATABASE_PATH):
        return result

    conn = _connect(settings.DATABASE_PATH)
    try:
        # SoC to metryka chwilowa (nie ma jej w raporcie dziennym) — bierzemy najnowszą
        # próbkę z dnia, NIE średnią (średnia z całej doby miesza noc z ~0% i szczyt
        # z ~100%, więc nie odpowiada żadnej sensownej wartości ani "aktualnemu"
        # stanowi baterii pokazywanemu w dashboardzie FoxESS).
        soc_row = conn.execute(
            """
            SELECT battery_soc_percent AS soc_percent
            FROM foxess_data
            WHERE DATE(timestamp) = ? AND battery_soc_percent IS NOT NULL
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            (target_day,),
        ).fetchone()

        # `foxess_report_daily` pochodzi z raportu FoxESS Cloud (ten sam, który zasila ich
        # własny dashboard) — dokładne sumy dobowe. Wcześniej liczyliśmy kWh jako
        # SUM(moc_kw * 5min) z próbek `foxess_data`, co dawało błąd rzędu 15-30%
        # (niestały interwał próbkowania FoxESS, ~4.6 min zamiast założonych 5 min).
        report_rows = {
            r['variable']: r['total_kwh']
            for r in conn.execute(
                'SELECT variable, MAX(total_kwh) AS total_kwh FROM foxess_report_daily '
                'WHERE report_date = ? GROUP BY variable',
                (target_day,),
            ).fetchall()
        }

        if report_rows:
            result.update(
                {
                    'pv_kwh': round(report_rows['PVEnergyTotal'], 2) if 'PVEnergyTotal' in report_rows else None,
                    'grid_import_kwh': round(report_rows['gridConsumption'], 2) if 'gridConsumption' in report_rows else None,
                    'grid_export_kwh': round(report_rows['feedin'], 2) if 'feedin' in report_rows else None,
                    'load_kwh': round(report_rows['loads'], 2) if 'loads' in report_rows else None,
                    'soc_percent': round(soc_row['soc_percent'], 1) if soc_row and soc_row['soc_percent'] is not None else None,
                    'has_data': True,
                }
            )
        else:
            # Fallback: brak jeszcze raportu dziennego dla tego dnia (np. sync tylko
            # z /device/real/query) — przybliżenie z próbek mocy, lepsze niż nic.
            row = conn.execute(
                """
                SELECT
                    SUM(pv_energy_kwh) AS pv_kwh,
                    SUM(grid_import_kwh) AS grid_import_kwh,
                    SUM(grid_export_kwh) AS grid_export_kwh,
                    SUM(load_energy_kwh) AS load_kwh
                FROM foxess_data
                WHERE DATE(timestamp) = ?
                """,
                (target_day,),
            ).fetchone()

            if row and row['pv_kwh'] is not None:
                result.update(
                    {
                        'pv_kwh': round(row['pv_kwh'], 2) if row['pv_kwh'] is not None else None,
                        'grid_import_kwh': round(row['grid_import_kwh'], 2) if row['grid_import_kwh'] is not None else None,
                        'grid_export_kwh': round(row['grid_export_kwh'], 2) if row['grid_export_kwh'] is not None else None,
                        'load_kwh': round(row['load_kwh'], 2) if row['load_kwh'] is not None else None,
                        'soc_percent': round(soc_row['soc_percent'], 1) if soc_row and soc_row['soc_percent'] is not None else None,
                        'has_data': True,
                    }
                )

        meta_row = conn.execute(
            "SELECT fetched_at FROM foxess_device_meta ORDER BY fetched_at DESC LIMIT 1"
        ).fetchone()
        if meta_row:
            result['last_synced_at'] = meta_row['fetched_at']
    finally:
        conn.close()

    return result


def get_timeseries(day: str | None = None) -> dict:
    settings = get_settings()
    target_day = day or date.today().isoformat()
    points: list[dict] = []

    if os.path.exists(settings.DATABASE_PATH):
        conn = _connect(settings.DATABASE_PATH)
        try:
            rows = conn.execute(
                """
                SELECT timestamp, pv_power_kw, battery_soc_percent, load_power_kw, grid_power_kw
                FROM foxess_data
                WHERE DATE(timestamp) = ?
                ORDER BY timestamp
                """,
                (target_day,),
            ).fetchall()
            points = [
                {
                    'timestamp': row['timestamp'],
                    'pv_power_kw': row['pv_power_kw'],
                    'battery_soc_percent': row['battery_soc_percent'],
                    'load_power_kw': row['load_power_kw'],
                    'grid_power_kw': row['grid_power_kw'],
                }
                for row in rows
            ]
        finally:
            conn.close()

    return {'day': target_day, 'points': points}
