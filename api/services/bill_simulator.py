"""Adapter FastAPI -> src/financial/roi_calculator.py (FinancialAnalyzer) + prosumer_deposit.

Formuła kontraktu §7.3 / §12.4 PROJEKT_APLIKACJA_MOBILNA.md:
    cost_no_pv  ~ baseline (zużycie domu, jakby 100% z sieci)
    cost_with_pv ~ rzeczywisty koszt (import netto, po autokonsumpcji)
    savings = cost_no_pv - cost_with_pv
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from sqlalchemy.orm import Session

from api.config import get_settings
from api.errors import ApiError
from api.schemas.tariff import TariffRatesCreate

# T2.7: stawki w `tauron_tariff` / `user_tariff_overrides` są zawsze NETTO (tak jak na fakturze
# Tauron — zob. `config/database_schema.sql` komentarz przy `tauron_tariff`). Zweryfikowano na
# 6 miesiącach realnych faktur (2026-01..06): (energia+dystrybucja+akcyza netto) × 1,23 ≈
# actual_total_cost (brutto) z dokładnością do ~1%. VAT na energię elektryczną w Polsce = 23%
# (stawka podstawowa; nie dotyczy obecnie żadnej ulgi/zwolnienia dla gospodarstw domowych).
VAT_RATE = 0.23

# T2.11 (2026-07-29): dwie ustawowe, KRAJOWE stawki (jednakowe dla wszystkich sprzedawców,
# niezależne od konkretnej umowy/cennika) — dotąd w ogóle nie liczone, co było jedną z
# przyczyn resztkowej rozbieżności "z PV" vs faktura Tauron:
#   • akcyza na energię elektryczną: 5,00 zł/MWh netto = 0,005 zł/kWh (art. 89 ust. 3 ustawy
#     o podatku akcyzowym; stawka niezmieniona 2025→2026, potwierdzona na fakturach —
#     np. faktura 01.2026: "Akcyza 6.20 zł od 1240 kWh" = 0,005 zł/kWh dokładnie).
#   • opłata kogeneracyjna: 3,00 zł/MWh netto = 0,003 zł/kWh (Dz.U. 2025 poz. 1664, bez
#     zmian na 2026). `tauron_tariff.cogenerative_fee_kwh` ma tę wartość tylko dla części
#     historycznych wierszy (niepełne dane z importu PDF) — liczymy ją więc jako stałą
#     krajową zamiast pola per-taryfa, żeby nie zależeć od (niekompletnego) backfillu.
# Obie doliczane do zużycia KUPIONEGO od sprzedawcy (import z sieci), tak jak OZE — nie do
# energii wyprodukowanej i zużytej z własnych paneli.
EXCISE_PLN_PER_KWH = 0.005
COGENERATION_PLN_PER_KWH = 0.003


def _gross(netto: float) -> float:
    return netto * (1 + VAT_RATE)


def _prorated_months(seg_start: date, seg_end: date) -> float:
    """Ułamek "miesięcy" w [seg_start, seg_end] liczony na DOKŁADNYCH długościach
    kalendarzowych miesięcy (28–31 dni), a nie na uśrednionej wartości rocznej —
    inaczej luty (28 dni) byłby niedoszacowany o ~8%, a miesiące 31-dniowe przeszacowane
    o ~2% względem realnego rozliczenia Tauron (pełny miesiąc kalendarzowy = 1 opłata)."""
    total = 0.0
    cur = seg_start
    while cur <= seg_end:
        days_in_month = calendar.monthrange(cur.year, cur.month)[1]
        month_end = date(cur.year, cur.month, days_in_month)
        chunk_end = min(seg_end, month_end)
        chunk_days = (chunk_end - cur).days + 1
        total += chunk_days / days_in_month
        cur = chunk_end + timedelta(days=1)
    return total


def simulate_bill(
    period_start: str,
    period_end: str,
    rates_override: TariffRatesCreate | None = None,
    db: Session | None = None,
    user_id: int | None = None,
) -> dict:
    from src.financial.roi_calculator import FinancialAnalyzer

    settings = get_settings()
    analyzer = FinancialAnalyzer(db_path=settings.DATABASE_PATH)
    try:
        if rates_override is not None:
            # Tryb "co jeśli": jedna stawka (z formularza, niezapisana) dla całego okresu —
            # użyteczne do szybkiego testu bez zapisywania nic w historii.
            roi_data = _sum_segments(analyzer, [(period_start, period_end, rates_override)])
        elif db is not None and user_id is not None:
            # Tryb domyślny: automatyczny dobór stawki per pod-okres na podstawie
            # zapisanej historii `user_tariff_overrides` (+ fallback `tauron_tariff`).
            segments = _resolve_segments(db, user_id, period_start, period_end)
            roi_data = _sum_segments(analyzer, segments)
        else:
            roi_data = analyzer.calculate_roi(period_start, period_end, use_forecast_baseline=False)
    except ApiError:
        raise
    except Exception as exc:  # noqa: BLE001 — brak danych w okresie itp.
        raise ApiError(422, 'SIMULATE_BILL_FAILED', f'Nie można policzyć rachunku: {exc}') from exc
    finally:
        analyzer.close()

    total_pv = float(roi_data.get('total_pv_kwh', 0.0) or 0.0)
    total_export = float(roi_data.get('total_export_kwh', 0.0) or 0.0)
    self_consumed = max(0.0, total_pv - total_export)

    # T2.7: VAT dolicza się na SAMYM KOŃCU, do zsumowanych złotówek — nie do poszczególnych
    # stawek — bo tak liczy też Tauron (pozycje netto → suma netto → VAT 23% → brutto
    # "do zapłaty"). Zwracamy OD RAZU obie wersje (netto i brutto) zamiast przełącznika
    # `vat_mode` po stronie żądania — UI pokazuje obie kwoty naraz, więc nie trzeba przełączać
    # trybu i ponownie odpytywać API (to też była przyczyna błędu: szybkie klikanie
    # netto/brutto → ponowna symulacja → auto-scroll w trakcie animacji → przypadkowe
    # trafienie w inne pole, w tym pole daty).
    cost_no_pv_net = round(float(roi_data['baseline_cost_pln']), 2)
    cost_with_pv_net = round(float(roi_data['actual_cost_pln']), 2)
    cost_no_pv_gross = round(_gross(float(roi_data['baseline_cost_pln'])), 2)
    cost_with_pv_gross = round(_gross(float(roi_data['actual_cost_pln'])), 2)

    return {
        'cost_no_pv_net_pln': cost_no_pv_net,
        'cost_no_pv_gross_pln': cost_no_pv_gross,
        'cost_with_pv_net_pln': cost_with_pv_net,
        'cost_with_pv_gross_pln': cost_with_pv_gross,
        'savings_net_pln': round(cost_no_pv_net - cost_with_pv_net, 2),
        'savings_gross_pln': round(cost_no_pv_gross - cost_with_pv_gross, 2),
        'production_kwh': round(total_pv, 2),
        'import_kwh': round(float(roi_data.get('total_import_kwh', 0.0) or 0.0), 2),
        'export_kwh': round(total_export, 2),
        'self_consumed_kwh': round(self_consumed, 2),
        'deposit_credit_pln': None,
    }


def _iso_to_date(value: str) -> date:
    return date.fromisoformat(value[:10])


def _load_user_override_windows(db: Session, user_id: int) -> list[tuple[str, TariffRatesCreate]]:
    """Zwraca [(valid_from, stawki)] posortowane rosnąco — historia zapisanych taryf użytkownika."""
    from api.models import UserTariffOverride

    rows = (
        db.query(UserTariffOverride)
        .filter(UserTariffOverride.user_id == user_id)
        .order_by(UserTariffOverride.valid_from.asc(), UserTariffOverride.id.asc())
        .all()
    )
    windows: list[tuple[str, TariffRatesCreate]] = []
    for row in rows:
        windows.append((
            str(row.valid_from),
            TariffRatesCreate(
                valid_from=str(row.valid_from),
                tariff_name=row.tariff_name,
                price_zone1_day=row.price_zone1_day,
                price_zone2_night=row.price_zone2_night,
                distribution_zone1=row.distribution_zone1,
                distribution_zone2=row.distribution_zone2,
                subscription_fee_monthly=row.subscription_fee_monthly,
                power_fee_monthly=row.power_fee_monthly,
                oze_fee_kwh=row.oze_fee_kwh,
                vat_mode=row.vat_mode,
                notes=row.notes,
            ),
        ))
    return windows


def _load_global_tariff_windows() -> list[tuple[str, TariffRatesCreate]]:
    """Fallback dla dat nieobjętych żadnym zapisem użytkownika — globalna `tauron_tariff`."""
    import os
    import sqlite3

    settings = get_settings()
    if not os.path.exists(settings.DATABASE_PATH):
        return []

    conn = sqlite3.connect(settings.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute('SELECT * FROM tauron_tariff ORDER BY valid_from ASC').fetchall()
    finally:
        conn.close()

    windows: list[tuple[str, TariffRatesCreate]] = []
    for row in rows:
        windows.append((
            str(row['valid_from']),
            TariffRatesCreate(
                valid_from=str(row['valid_from']),
                tariff_name=row['tariff_name'],
                price_zone1_day=row['price_zone1_day'],
                price_zone2_night=row['price_zone2_night'],
                distribution_zone1=row['distribution_zone1'],
                distribution_zone2=row['distribution_zone2'],
                subscription_fee_monthly=row['subscription_fee_monthly'],
                power_fee_monthly=row['power_fee_monthly'],
                oze_fee_kwh=row['oze_fee_kwh'],
                vat_mode='net',
                notes=row['notes'],
            ),
        ))
    return windows


def _resolve_segments(
    db: Session, user_id: int, period_start: str, period_end: str
) -> list[tuple[str, str, TariffRatesCreate]]:
    """Dzieli [period_start, period_end] na pod-okresy według historii stawek użytkownika
    (nadpisuje globalne domyślne), tak by każdy dzień był rozliczony właściwą, obowiązującą
    wtedy taryfą — bez tego zmiana taryfy w połowie okresu byłaby zignorowana."""
    user_windows = _load_user_override_windows(db, user_id)
    global_windows = _load_global_tariff_windows()

    if not user_windows and not global_windows:
        raise ApiError(
            422,
            'NO_TARIFF_RATES',
            'Brak zapisanych stawek — zapisz przynajmniej jedną taryfę w Symulatorze przed obliczeniem rachunku.',
        )

    start = _iso_to_date(period_start)
    end = _iso_to_date(period_end)

    # Wszystkie daty startu taryf (user + global), które mogą wyznaczać granicę segmentu w [start, end].
    breakpoints = {start}
    for valid_from, _ in (*user_windows, *global_windows):
        d = _iso_to_date(valid_from)
        if start < d <= end:
            breakpoints.add(d)
    ordered = sorted(breakpoints)

    def _resolve(d: date) -> TariffRatesCreate:
        best: TariffRatesCreate | None = None
        for valid_from, rates in user_windows:
            if _iso_to_date(valid_from) <= d:
                best = rates
        if best is not None:
            return best
        for valid_from, rates in global_windows:
            if _iso_to_date(valid_from) <= d:
                best = rates
        if best is not None:
            return best
        # Data wcześniejsza niż wszystko, co mamy zapisane — użyj najstarszej znanej stawki
        # (user > global), żeby nie blokować obliczenia twardym błędem.
        fallback_pool = user_windows or global_windows
        return fallback_pool[0][1]

    segments: list[tuple[str, str, TariffRatesCreate]] = []
    for i, seg_start in enumerate(ordered):
        seg_end = (ordered[i + 1] - timedelta(days=1)) if i + 1 < len(ordered) else end
        if seg_end < seg_start:
            continue
        segments.append((seg_start.isoformat(), seg_end.isoformat(), _resolve(seg_start)))
    return segments


def _parse_local_timestamps(series):
    """`foxess_data.timestamp` miesza wiersze z offsetem (`...+02:00`, z syncu FoxESS) i bez
    (`...` naive, z innych ścieżek zapisu/importu) — oba reprezentują ten sam lokalny (Europe/Warsaw)
    czas zegarowy. `pd.to_datetime(..., format='mixed')` samo nie wystarcza, bo pandas odmawia
    zbudowania jednej kolumny datetime64 z mieszaniny tz-aware/tz-naive wartości
    ("Mixed timezones detected"). Ucinamy sufiks offsetu, żeby wszystko było jednolicie naive
    lokalne — poprawna klasyfikacja stref G12w (godzina dnia) zależy od czasu lokalnego, nie UTC.
    """
    import pandas as pd

    stripped = series.astype(str).str.replace(r'[+-]\d{2}:\d{2}$', '', regex=True)
    return pd.to_datetime(stripped, format='mixed')


def _energy_cost(zone1_kwh: float, zone2_kwh: float, rates: TariffRatesCreate) -> float:
    energy = zone1_kwh * (rates.price_zone1_day + (rates.distribution_zone1 or 0)) + zone2_kwh * (
        rates.price_zone2_night + (rates.distribution_zone2 or 0)
    )
    total_kwh = zone1_kwh + zone2_kwh
    per_kwh_fees = (rates.oze_fee_kwh or 0) + EXCISE_PLN_PER_KWH + COGENERATION_PLN_PER_KWH
    return energy + total_kwh * per_kwh_fees


def _daily_counter_kwh(conn, variable: str, seg_start: str, seg_end: str):
    """Dzienna energia [kWh] z licznika skumulowanego `foxess_timeseries` (lifetime counter),
    Δ dnia — ta sama metoda co `PVEnergyTotal` (zob. `src/data/foxess_pv_total.py`), tylko
    zastosowana też do `gridConsumption` (pobór z sieci) i `feedin` (oddanie do sieci).

    Pobieramy z jednodniowym zapasem PRZED `seg_start`, żeby metoda hybrydowa miała dostęp
    do `prev_last` nawet gdy pierwszy dzień segmentu akurat ma reset licznika (`min == 0`).
    """
    from datetime import timedelta

    from src.data.foxess_pv_total import build_daily_counter_table

    lookback_start = (_iso_to_date(seg_start) - timedelta(days=1)).isoformat()
    df = build_daily_counter_table(conn, variable=variable, start=lookback_start, end=seg_end)
    return df[df['day'] >= seg_start].set_index('day')[f'ts_{variable}']


def _sum_segments(analyzer, segments: list[tuple[str, str, TariffRatesCreate]]) -> dict:
    """Liczy koszt energii per segment (skaluje się z faktycznym zużyciem w danym pod-okresie).

    UWAGA (poprawka błędu z 2026-07-28): koszt "z PV" liczymy z BRUTTO importu z sieci
    (`grid_import_kwh`), zgodnie z formułą §7.3 ("z PV ≈ import z sieci × stawki") — NIE z
    "netto" (import minus eksport w danej strefie, ucięty do zera). To drugie podejście
    (odziedziczone z `roi_calculator.calculate_actual_cost`) daje w praktyce fałszywy,
    stały wynik: gdy eksport w danej strefie regularnie przewyższa import (typowe dla domu
    z PV latem), `max(0, import-eksport)` wychodzi 0 w KAŻDYM okresie, więc koszt energii
    "z PV" spada do 0 i cały wynik to sam koszt stały — niezależnie od długości/zakresu
    wybranego okresu. Eksport jest realnie rozliczany osobno (depozyt prosumencki wg RCEm,
    zob. T2.8), a nie 1:1 odejmowany od importu w tej samej strefie.

    UWAGA 2 (poprawka błędu z 2026-07-29, zgłoszenie: "sprawdź czy dane z bazą są takie same
    jak na fakturze"): próbki 5-minutowe `foxess_data.grid_import_kwh`/`grid_export_kwh`
    (integracja z mocy chwilowej) SYSTEMATYCZNIE zawyżają miesięczny wolumen o 10–25% względem
    faktury Tauron (zweryfikowano na 05/06.2026 i 12.2025/01.2026: +9..+144 kWh/mies.).
    FoxESS ma jednak WŁASNY, wiarygodny licznik energii skumulowanej (lifetime) —
    `gridConsumption` (pobór) i `feedin` (oddanie) w `foxess_timeseries` — który zgadza się
    z fakturą z dokładnością do ~3% (ten sam mechanizm co już zweryfikowany `PVEnergyTotal`,
    zob. `src/data/foxess_pv_total.py`). Dlatego dobowy WOLUMEN importu/eksportu/produkcji
    bierzemy z licznika, a próbki 5-minutowe używamy TYLKO do wyznaczenia proporcji
    strefa1/strefa2 w ramach dnia (bo licznik dobowy nie ma rozdzielczości godzinowej
    potrzebnej do klasyfikacji G12w) — zakładając, że ewentualne odchylenie pomiarowe
    próbek 5-minutowych jest w miarę równomiernie rozłożone w ciągu doby.
    Gdy licznik nie ma danych dla danego dnia (luka w synchronizacji), używamy sumy z
    próbek 5-minutowych jako fallbacku dla TEGO dnia (lepsze przybliżenie niż zero).

    Opłatę stałą/mocową (miesięczną) doliczamy proporcjonalnie do liczby dni w KAŻDYM
    segmencie (wg jego własnej stawki) — inaczej przy symulacji okresu dłuższego niż
    miesiąc opłata stała policzyłaby się tylko raz zamiast raz na każdy miesiąc rozliczeniowy.
    """
    import pandas as pd

    from src.optimization.g12w_tariff import classify_zone as g12w_zone

    conn = analyzer.connect()

    baseline_energy = 0.0
    actual_energy = 0.0
    fixed_fee = 0.0
    total_pv = 0.0
    total_import = 0.0
    total_export = 0.0

    for seg_start, seg_end, rates in segments:
        fixed_fee += ((rates.subscription_fee_monthly or 0) + (rates.power_fee_monthly or 0)) * _prorated_months(
            _iso_to_date(seg_start), _iso_to_date(seg_end)
        )

        load_df = pd.read_sql_query(
            'SELECT timestamp, load_energy_kwh FROM foxess_data WHERE DATE(timestamp) BETWEEN ? AND ?',
            conn,
            params=(seg_start, seg_end),
        )
        load_df['timestamp'] = _parse_local_timestamps(load_df['timestamp'])
        load_df['zone'] = load_df['timestamp'].apply(g12w_zone)
        baseline_energy += _energy_cost(
            load_df[load_df['zone'] == 1]['load_energy_kwh'].sum(),
            load_df[load_df['zone'] == 2]['load_energy_kwh'].sum(),
            rates,
        )

        grid_df = pd.read_sql_query(
            'SELECT timestamp, grid_import_kwh, grid_export_kwh, pv_energy_kwh FROM foxess_data '
            'WHERE DATE(timestamp) BETWEEN ? AND ?',
            conn,
            params=(seg_start, seg_end),
        )
        grid_df['timestamp'] = _parse_local_timestamps(grid_df['timestamp'])
        grid_df['day'] = grid_df['timestamp'].dt.strftime('%Y-%m-%d')
        grid_df['zone'] = grid_df['timestamp'].apply(g12w_zone)
        grid_df['import_z1'] = grid_df['grid_import_kwh'].where(grid_df['zone'] == 1, 0.0)
        grid_df['import_z2'] = grid_df['grid_import_kwh'].where(grid_df['zone'] == 2, 0.0)
        grid_df['pv_pos'] = grid_df['pv_energy_kwh'].clip(lower=0)

        raw_daily = grid_df.groupby('day').agg(
            raw_import_z1=('import_z1', 'sum'),
            raw_import_z2=('import_z2', 'sum'),
            raw_export=('grid_export_kwh', 'sum'),
            raw_pv=('pv_pos', 'sum'),
        )

        counter_import = _daily_counter_kwh(conn, 'gridConsumption', seg_start, seg_end)
        counter_export = _daily_counter_kwh(conn, 'feedin', seg_start, seg_end)
        counter_pv = _daily_counter_kwh(conn, 'PVEnergyTotal', seg_start, seg_end)

        for day, row in raw_daily.iterrows():
            raw_import_total = row['raw_import_z1'] + row['raw_import_z2']
            counter_import_val = counter_import.get(day)
            if pd.notna(counter_import_val) and raw_import_total > 0.01:
                scale = counter_import_val / raw_import_total
                z1 = row['raw_import_z1'] * scale
                z2 = row['raw_import_z2'] * scale
            elif pd.notna(counter_import_val):
                z1, z2 = counter_import_val, 0.0
            else:
                z1, z2 = row['raw_import_z1'], row['raw_import_z2']

            actual_energy += _energy_cost(z1, z2, rates)
            total_import += z1 + z2

            counter_export_val = counter_export.get(day)
            total_export += counter_export_val if pd.notna(counter_export_val) else row['raw_export']

            counter_pv_val = counter_pv.get(day)
            total_pv += counter_pv_val if pd.notna(counter_pv_val) else row['raw_pv']

    baseline_cost = round(baseline_energy + fixed_fee, 2)
    actual_cost = round(actual_energy + fixed_fee, 2)

    return {
        'baseline_cost_pln': baseline_cost,
        'actual_cost_pln': actual_cost,
        'savings_pln': round(baseline_cost - actual_cost, 2),
        'total_pv_kwh': total_pv,
        'total_import_kwh': total_import,
        'total_export_kwh': total_export,
    }
