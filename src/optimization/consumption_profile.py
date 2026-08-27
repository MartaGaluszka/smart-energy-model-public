"""
Profil godzinowy zużycia energii na podstawie danych historycznych.

Używane w battery_planner.py do realistycznej symulacji SoC.

UWAGI TECHNICZNE:
- Rok przestępny: 29 lutego → fallback na 28 lutego przy year-1
- Zmiana czasu (DST): 
  * Wiosna (ostatnia niedziela marca): 2:00→3:00 (23h dzień)
  * Jesień (ostatnia niedziela października): 3:00→2:00 (25h dzień)
- Minimalna ilość danych: 168 rekordów (7 dni × 24h)
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd


def get_hourly_consumption_profile(
    db_path: str | Path,
    target_date: date,
    lookback_days: int = 30,
    prefer_year_ago: bool = True,
    min_records: int = 168,  # Minimum 7 dni × 24h
) -> list[float]:
    """Oblicz średni profil zużycia per godzina (0-23) na podstawie historii.

    STRATEGIA SEZONOWA (prefer_year_ago=True, default):
    1. Najpierw szuka danych z tego samego miesiąca rok wcześniej (±7 dni)
    2. Fallback: ostatnie N dni (jeśli brak danych rok wstecz)

    EDGE CASES:
    - Rok przestępny (29.02 → 28.02)
    - DST: ostatnia niedz. marca (23h) i października (25h)

    Przykład:
    - target_date = 2026-08-27 → szuka 2025-08-20 do 2025-09-03
    - Jeśli brak: fallback na 2026-07-28 do 2026-08-26

    Args:
        db_path: Ścieżka do bazy SQLite
        target_date: Data, dla której tworzymy profil
        lookback_days: Ile dni do fallbacku (ostatnie N dni)
        prefer_year_ago: Priorytetuj ten sam miesiąc rok wcześniej (default: True)
        min_records: Minimalna liczba rekordów do walidacji (default: 168 = 7 dni)

    Returns:
        Lista 24 wartości [kWh] — średnie zużycie per godzina (0-23)
    """
    conn = sqlite3.connect(db_path)

    # Strategia 1: Ten sam miesiąc rok wcześniej (±7 dni tolerancja)
    if prefer_year_ago:
        try:
            # Obsługa roku przestępnego (29.02 → 28.02)
            try:
                year_ago = target_date.replace(year=target_date.year - 1)
            except ValueError:
                # 29 lutego w roku przestępnym → 28 lutego rok wcześniej
                year_ago = target_date.replace(year=target_date.year - 1, day=28)
            
            start_date = year_ago - timedelta(days=7)
            end_date = year_ago + timedelta(days=7)
            
            profile = _query_consumption_profile(conn, start_date, end_date, min_records)
            if profile and sum(profile) > 0.1:  # Jeśli mamy sensowne dane
                conn.close()
                return profile
        except Exception:
            pass  # Fallback do strategii 2

    # Strategia 2 (fallback): Ostatnie N dni
    end_date = target_date - timedelta(days=1)
    start_date = end_date - timedelta(days=lookback_days)

    profile = _query_consumption_profile(conn, start_date, end_date, min_records)
    conn.close()
    return profile


def _query_consumption_profile(
    conn: sqlite3.Connection,
    start_date: date,
    end_date: date,
    min_records: int = 168,
) -> list[float]:
    """Pomocnicza funkcja: wyciąga profil zużycia z bazy dla podanego okresu.
    
    Uwzględnia DST (zmiana czasu):
    - Wiosna (marzec): 23h dzień (2:00-2:59 nie istnieje)
    - Jesień (październik): 25h dzień (2:00-2:59 dwa razy)
    """
    # Query: oblicz zużycie godzinowe z foxess_timeseries
    query = """
    SELECT 
        CAST(strftime('%H', time) AS INTEGER) as hour,
        date,
        SUM(COALESCE(feedin_kwh, 0) + COALESCE(grid_consumption_kwh, 0)) as consumption_kwh
    FROM foxess_timeseries
    WHERE date BETWEEN ? AND ?
    GROUP BY date, hour
    ORDER BY date, hour
    """

    try:
        df = pd.read_sql_query(query, conn, params=(start_date.isoformat(), end_date.isoformat()))
    except Exception:
        # Fallback: jeśli foxess_timeseries nie istnieje, użyj foxess_data
        query_fallback = """
        SELECT 
            CAST(strftime('%H', timestamp) AS INTEGER) as hour,
            DATE(timestamp) as date,
            AVG(COALESCE(load_power_kw, 0)) as avg_load_kw
        FROM foxess_data
        WHERE DATE(timestamp) BETWEEN ? AND ?
        GROUP BY date, hour
        ORDER BY date, hour
        """
        df = pd.read_sql_query(query_fallback, conn, params=(start_date.isoformat(), end_date.isoformat()))
        df['consumption_kwh'] = df['avg_load_kw']  # Aproximacja

    # Walidacja: minimum rekordów (7 dni × 24h = 168)
    if df.empty or len(df) < min_records:
        # Brak wystarczających danych — zwróć realistyczny profil dobowy (nie płaski!)
        return _realistic_fallback_profile()

    # DST handling: agreguj per godzina (0-23), ignorując anomalie DST
    # Dni z 23h lub 25h są uśrednione tak samo jak normalne 24h dni
    hourly_avg = df.groupby('hour')['consumption_kwh'].mean()

    # Uzupełnij brakujące godziny fallbackiem
    profile = []
    for h in range(24):
        if h in hourly_avg.index:
            profile.append(float(hourly_avg[h]))
        else:
            # Godzina bez danych → użyj fallback per godzina
            profile.append(_realistic_fallback_profile()[h])

    # Normalizacja: upewnij się, że żadna wartość nie jest ujemna
    profile = [max(0.0, val) for val in profile]

    return profile


def _realistic_fallback_profile() -> list[float]:
    """Realistyczny profil zużycia dobowego (gdy brak danych historycznych).
    
    Bazuje na typowych wzorcach gospodarstwa domowego:
    - Noc (0-6): ~0.25 kWh/h (lodówka, standby, ładowarki)
    - Rano (7-9): ~0.7 kWh/h (ekspres, czajnik, AGD poranne)
    - Dzień (10-15): ~0.5 kWh/h (lekkie AGD, biuro domowe)
    - Popołudnie (16-18): ~0.8 kWh/h (gotowanie zaczyna się)
    - Wieczór (19-22): ~1.0 kWh/h (gotowanie, TV, oświetlenie, AGD)
    - Późny wieczór (23): ~0.5 kWh/h (wiatr w dół)
    
    Średnie dzienne: ~14.5 kWh (typowe gospodarstwo 2-3 osoby bez ogrzewania elektrycznego)
    """
    return [
        # Noc (0-6): standby, lodówka
        0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.30,
        # Poranek (7-9): ekspres, czajnik, AGD
        0.70, 0.80, 0.70,
        # Przedpołudnie (10-12): lekkie AGD
        0.50, 0.55, 0.60,
        # Popołudnie (13-18): wzrost aktywności
        0.65, 0.70, 0.75, 0.80, 0.85, 0.90,
        # Wieczór (19-22): szczyt (gotowanie, TV, oświetlenie)
        1.00, 1.10, 1.00, 0.90,
        # Późny wieczór (23): wiatr w dół
        0.50,
    ]


def estimate_load_from_balance(
    pv_kwh: float,
    feedin_kwh: float,
    grid_consumption_kwh: float,
    battery_charge_kwh: float = 0.0,
    battery_discharge_kwh: float = 0.0,
) -> float:
    """Oszacuj zużycie domowe z bilansu energii.

    Bilans: PV + battery_discharge + grid_import = load + battery_charge + grid_export

    Args:
        pv_kwh: Produkcja PV
        feedin_kwh: Energia oddana do sieci (export)
        grid_consumption_kwh: Energia pobrana z sieci (import)
        battery_charge_kwh: Energia zmagazynowana w baterii
        battery_discharge_kwh: Energia rozładowana z baterii

    Returns:
        Estimated load [kWh]
    """
    load = pv_kwh + battery_discharge_kwh + grid_consumption_kwh - battery_charge_kwh - feedin_kwh
    return max(0.0, load)


if __name__ == '__main__':
    # Test
    import os
    db_path = os.path.join(os.path.dirname(__file__), '../../data/processed/smart_energy.db')
    today = date.today()
    
    print(f"=== Test profilu zużycia dla {today} ===\n")
    
    # Test 1: Preferuj rok wstecz
    profile_year_ago = get_hourly_consumption_profile(db_path, today, prefer_year_ago=True)
    print(f"Strategia 1 (rok wstecz): {today.replace(year=today.year-1)} (±7 dni)")
    print(f"  Średnie dzienne: {sum(profile_year_ago):.2f} kWh")
    print(f"  Szczyt (godz. 18-20): {sum(profile_year_ago[18:21]):.2f} kWh")
    
    print()
    
    # Test 2: Ostatnie 30 dni
    profile_recent = get_hourly_consumption_profile(db_path, today, prefer_year_ago=False, lookback_days=30)
    print(f"Strategia 2 (ostatnie 30 dni): {today - timedelta(days=30)} do {today - timedelta(days=1)}")
    print(f"  Średnie dzienne: {sum(profile_recent):.2f} kWh")
    print(f"  Szczyt (godz. 18-20): {sum(profile_recent[18:21]):.2f} kWh")
