"""
Ręczny wpis faktur / rozliczeń Tauron (G12w, net-billing).

Zapis: tauron_bills (+ opcjonalnie tauron_tariff, meter_readings).
Dane służą ROI / walidacji biznesowej — nie wchodzą do modelu PV.
"""

from __future__ import annotations

import calendar
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd

from src.data.import_csv import EnergyDataImporter

DEFAULT_DB = os.getenv('DATABASE_PATH', 'data/energy_model.db')

DOC_TYPES = ('rozliczenie', 'korekta')

DEFAULT_TARIFF_FALLBACK: dict[str, float] = {
    'price_zone1_day': 0.6244,
    'price_zone2_night': 0.4163,
    'distribution_zone1': 0.3630,
    'distribution_zone2': 0.0844,
    'subscription_fee_monthly': 30.17,
    'power_fee_monthly': 24.05,
    'transition_fee_monthly': 0.0,
    'oze_fee_kwh': 0.0073,
    'cogenerative_fee_kwh': 0.0030,
}


def _resolve_db_path(db_path: str | None = None) -> str:
    path = db_path or DEFAULT_DB
    if not os.path.isabs(path):
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        cand = os.path.join(root, path)
        if os.path.exists(cand) or not os.path.exists(path):
            path = cand
    return path


def _connect(db_path: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(_resolve_db_path(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def build_bill_number(
    doc_type: str,
    period_start: str,
    period_end: str,
    invoice_number: str | None = None,
) -> str:
    if invoice_number and str(invoice_number).strip():
        return str(invoice_number).strip()
    return f'{doc_type}_{period_start}_{period_end}'


def build_pdf_path_metadata(
    *,
    doc_type: str,
    period_start: str,
    period_end: str,
    invoice_number: str | None = None,
    issue_date: str | None = None,
    payment_deadline: str | None = None,
    deposit_period: float | None = None,
    deposit_previous: float | None = None,
    amount_due: float | None = None,
    extra: str | None = None,
) -> str:
    parts = [
        f'typ={doc_type}',
        f'okres={period_start}_{period_end}',
    ]
    if invoice_number:
        parts.append(f'numer_faktury={invoice_number}')
    if issue_date:
        parts.append(f'data_wystawienia={issue_date}')
    if payment_deadline:
        parts.append(f'termin_platnosci={payment_deadline}')
    if deposit_period is not None:
        parts.append(f'depozyt_okres={deposit_period:.2f}')
    if deposit_previous is not None:
        parts.append(f'depozyt_poprzednie={deposit_previous:.2f}')
    if amount_due is not None:
        parts.append(f'do_zaplaty_po_depozycie={amount_due:.2f}')
    if extra and str(extra).strip():
        parts.append(str(extra).strip())
    return '|'.join(parts)


@dataclass
class TauronInvoiceInput:
    billing_period_start: str
    billing_period_end: str
    bill_date: str
    bill_number: str
    actual_zone1_kwh: float
    actual_zone2_kwh: float
    actual_energy_cost: float
    actual_distribution_cost: float
    actual_fixed_costs: float
    actual_total_cost: float
    energy_exported_kwh: float
    energy_exported_value: float | None = None
    export_zone1_kwh: float | None = None
    export_zone2_kwh: float | None = None
    pdf_path: str | None = None
    save_tariff: bool = False
    save_meter_reading: bool = True
    tariff_valid_from: str | None = None
    price_zone1_day: float | None = None
    price_zone2_night: float | None = None
    distribution_zone1: float | None = None
    distribution_zone2: float | None = None
    subscription_fee_monthly: float | None = None
    power_fee_monthly: float | None = None
    transition_fee_monthly: float | None = None
    oze_fee_kwh: float | None = None
    cogenerative_fee_kwh: float | None = None
    tariff_notes: str | None = None


def period_exists(
    period_start: str,
    period_end: str,
    *,
    db_path: str | None = None,
) -> bool:
    conn = _connect(db_path)
    row = conn.execute(
        '''
        SELECT 1 FROM tauron_bills
        WHERE billing_period_start = ? AND billing_period_end = ?
        LIMIT 1
        ''',
        (period_start, period_end),
    ).fetchone()
    conn.close()
    return row is not None


def suggested_next_period(*, db_path: str | None = None) -> tuple[date, date]:
    """Następny pełny miesiąc po ostatniej fakturze — do auto-wypełnienia formularza."""
    bills = list_bills(limit=1, db_path=db_path)
    if bills.empty:
        today = date.today()
        return today.replace(day=1), today
    last_end = pd.to_datetime(bills.iloc[0]['billing_period_end']).date()
    if last_end.month == 12:
        start = date(last_end.year + 1, 1, 1)
    else:
        start = date(last_end.year, last_end.month + 1, 1)
    last_day = calendar.monthrange(start.year, start.month)[1]
    return start, date(start.year, start.month, last_day)


def list_bills(*, limit: int = 24, db_path: str | None = None) -> pd.DataFrame:
    conn = _connect(db_path)
    df = pd.read_sql_query(
        '''
        SELECT
            id,
            bill_date,
            billing_period_start,
            billing_period_end,
            actual_zone1_kwh,
            actual_zone2_kwh,
            actual_total_kwh,
            actual_energy_cost,
            actual_distribution_cost,
            actual_fixed_costs,
            actual_total_cost,
            energy_exported_kwh,
            energy_exported_value,
            bill_number
        FROM tauron_bills
        ORDER BY billing_period_end DESC, id DESC
        LIMIT ?
        ''',
        conn,
        params=(limit,),
    )
    conn.close()
    return df


def get_latest_tariff(*, db_path: str | None = None) -> dict[str, Any] | None:
    """Ostatni wpis tauron_tariff (najnowsze valid_from) — do auto-wypełnienia formularza."""
    conn = _connect(db_path)
    row = conn.execute(
        '''
        SELECT
            valid_from,
            tariff_name,
            price_zone1_day,
            price_zone2_night,
            distribution_zone1,
            distribution_zone2,
            subscription_fee_monthly,
            power_fee_monthly,
            transition_fee_monthly,
            oze_fee_kwh,
            cogenerative_fee_kwh,
            notes
        FROM tauron_tariff
        ORDER BY valid_from DESC
        LIMIT 1
        '''
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def tariff_defaults(*, db_path: str | None = None) -> dict[str, Any]:
    """Stawki do formularza: ostatni miesiąc z bazy albo stałe fallback."""
    latest = get_latest_tariff(db_path=db_path)
    if not latest:
        return {'valid_from': None, **DEFAULT_TARIFF_FALLBACK}
    out = {**DEFAULT_TARIFF_FALLBACK}
    for key in DEFAULT_TARIFF_FALLBACK:
        val = latest.get(key)
        if val is not None:
            out[key] = float(val)
    out['valid_from'] = latest.get('valid_from')
    out['tariff_notes'] = latest.get('notes') or ''
    return out


def _forecast_period_bounds(forecast_period: str) -> tuple[str, str]:
    """'2025-11_2025-12' → ('2025-11-01', '2025-12-31')."""
    start_token, end_token = forecast_period.split('_')
    y1, m1 = map(int, start_token.split('-'))
    y2, m2 = map(int, end_token.split('-'))
    last_day = calendar.monthrange(y2, m2)[1]
    return f'{y1}-{m1:02d}-01', f'{y2}-{m2:02d}-{last_day:02d}'


def _parse_do_zaplaty_from_notes(notes: str | None) -> float | None:
    if not notes:
        return None
    match = re.search(r'Do zapłaty\s+([0-9]+(?:[.,][0-9]+)?)', notes, re.IGNORECASE)
    if not match:
        return None
    return float(match.group(1).replace(',', '.'))


def _parse_bill_metadata(pdf_path: str | None) -> dict[str, Any]:
    """Kluczowe kwoty depozytu / rozliczenia z pdf_path (metadane wpisu faktury)."""
    raw: dict[str, str] = {}
    if pdf_path:
        for part in pdf_path.split('|'):
            if '=' in part:
                key, val = part.split('=', 1)
                raw[key.strip()] = val.strip()

    def _pick_float(*keys: str) -> float | None:
        for key in keys:
            val = raw.get(key)
            if val is None:
                continue
            try:
                return float(str(val).replace(',', '.'))
            except ValueError:
                continue
        return None

    def _regex_float(pattern: str) -> float | None:
        if not pdf_path:
            return None
        match = re.search(pattern, pdf_path, re.IGNORECASE)
        if not match:
            return None
        try:
            return float(match.group(1).replace(',', '.'))
        except ValueError:
            return None

    dep_prev = _pick_float('depozyt_poprzednie', 'depozyt_poprzednie_policzono')
    if dep_prev is None:
        dep_prev = _regex_float(r'depozyt_poprzednie[=:\s]+([0-9]+(?:[.,][0-9]+)?)')

    dep_okres = _pick_float('depozyt_okres')
    if dep_okres is None:
        dep_okres = _regex_float(r'depozyt_okres[=:\s]+([0-9]+(?:[.,][0-9]+)?)')

    wynik = _pick_float('wynik_brutto', 'policzono_brutto', 'nalezy_brutto')
    if wynik is None:
        wynik = _regex_float(r'wynik_brutto[=:\s]+([0-9]+(?:[.,][0-9]+)?)')

    do_zap = _pick_float('do_zaplaty_po_depozycie', 'do_zaplaty_po_korekcie', 'do_zaplaty')
    if do_zap is None:
        do_zap = _regex_float(r'do_zaplaty_po_depozycie[=:\s]+([0-9]+(?:[.,][0-9]+)?)')

    dep_rozliczenie = (dep_prev + dep_okres) if dep_prev is not None and dep_okres is not None else None

    return {
        'depozyt_poprzednie': dep_prev,
        'depozyt_okres': dep_okres,
        'rozliczenie_depozytu': dep_rozliczenie,
        'wynik_brutto': wynik,
        'do_zaplaty': do_zap,
        'numer_faktury': raw.get('numer_faktury'),
        'termin_platnosci': raw.get('termin_platnosci'),
    }


def load_deposit_ledger(*, db_path: str | None = None) -> pd.DataFrame:
    """
    Historia depozytu prosumenckiego z faktur (poz. 4–6 jak w PDF Tauron).

    depozyt_poprzednie (poz. 5) to saldo przeniesione — **nie sumować** po miesiącach.
    """
    conn = _connect(db_path)
    try:
        df = pd.read_sql_query(
            '''
            SELECT
                billing_period_start,
                billing_period_end,
                bill_date,
                bill_number,
                actual_total_cost,
                energy_exported_kwh,
                pdf_path
            FROM tauron_bills
            ORDER BY billing_period_start
            ''',
            conn,
        )
    finally:
        conn.close()

    if df.empty:
        return pd.DataFrame()

    df_canon = _canonical_bills(df)
    rows: list[dict[str, Any]] = []
    for _, bill in df_canon.iterrows():
        meta = _parse_bill_metadata(bill.get('pdf_path'))
        wynik = meta.get('wynik_brutto')
        if wynik is None and pd.notna(bill.get('actual_total_cost')):
            wynik = float(bill['actual_total_cost'])

        dep_prev = meta.get('depozyt_poprzednie')
        dep_okres = meta.get('depozyt_okres')
        dep_roz = meta.get('rozliczenie_depozytu')
        do_zap = meta.get('do_zaplaty')
        if dep_roz is None and dep_prev is not None:
            dep_roz = dep_prev + (dep_okres or 0.0)

        start = str(bill['billing_period_start'])[:10]
        rows.append(
            {
                'okres': start[:7],
                'okres_od': start,
                'okres_do': str(bill['billing_period_end'])[:10],
                'bill_number': bill.get('bill_number'),
                'depozyt_okres_zl': dep_okres,
                'depozyt_poprzednie_zl': dep_prev,
                'rozliczenie_depozytu_zl': dep_roz,
                'wynik_brutto_zl': wynik,
                'do_zaplaty_zl': do_zap,
                'oddanie_kwh': float(bill['energy_exported_kwh'])
                if pd.notna(bill.get('energy_exported_kwh'))
                else None,
                'numer_faktury': meta.get('numer_faktury'),
                'termin_platnosci': meta.get('termin_platnosci'),
            }
        )

    out = pd.DataFrame(rows)
    if not out.empty:
        out['okres'] = pd.Categorical(out['okres'], categories=out['okres'].tolist(), ordered=True)
        out = out.sort_values('okres_od').reset_index(drop=True)
    return out


def _parse_bill_do_zaplaty(pdf_path: str | None) -> float | None:
    """Kwota do zapłaty z metadanych faktury (pdf_path), jak w app Tauron."""
    if not pdf_path:
        return None
    keys = (
        'do_zaplaty_po_depozycie',
        'do_zaplaty_po_korekcie',
        'do_zaplaty',
        'nalezy_brutto',
    )
    meta: dict[str, str] = {}
    for part in pdf_path.split('|'):
        if '=' in part:
            key, val = part.split('=', 1)
            meta[key.strip()] = val.strip()
    for key in keys:
        raw = meta.get(key)
        if raw is None:
            continue
        try:
            return float(str(raw).replace(',', '.'))
        except ValueError:
            continue
    return None


def _canonical_bills(df_bills: pd.DataFrame) -> pd.DataFrame:
    """Jedna faktura na okres — preferuj rozliczenie, potem najnowszy wpis (korekta)."""
    if df_bills.empty:
        return df_bills.copy()
    picked: list[pd.Series] = []
    grouped = df_bills.groupby(['billing_period_start', 'billing_period_end'], sort=False)
    for _, grp in grouped:
        roz = grp[grp['bill_number'].astype(str).str.contains('rozliczenie', case=False, na=False)]
        pick = roz.iloc[0] if not roz.empty else grp.sort_values('bill_number').iloc[-1]
        picked.append(pick)
    out = pd.DataFrame(picked).reset_index(drop=True)
    out['bill_kind'] = out['bill_number'].astype(str).apply(
        lambda b: 'rozliczenie' if 'rozliczenie' in b.lower() else ('korekta' if 'korekta' in b.lower() or b.startswith('T/') else 'inne')
    )
    return out


def _delta_pair(actual: float | None, forecast: float | None) -> tuple[float | None, float | None]:
    if actual is None or forecast is None:
        return None, None
    delta = actual - forecast
    pct = (delta / forecast * 100) if forecast else None
    return delta, pct


def load_forecast_vs_bills(*, db_path: str | None = None) -> pd.DataFrame:
    """
    Porównanie blankietów Tauron (~2 mies.) z sumą faktur w tym samym okresie.

    Koszt (jak w app Tauron): **energia netto** (`forecast_energy_cost` vs suma `actual_energy_cost`).
    Pobór kWh (pomocniczo): suma `actual_total_kwh` — u prosumenta może rozjechać się z prognozą zużycia.
    Dodatkowo: do zapłaty (z blankietu / metadanych faktur) — z depozytem, tylko orientacyjnie.
    """
    conn = _connect(db_path)
    try:
        df_fc = pd.read_sql_query(
            '''
            SELECT
                forecast_date,
                forecast_period,
                forecast_total_kwh,
                forecast_energy_cost,
                forecast_total_cost,
                source,
                notes
            FROM tauron_forecast
            ORDER BY forecast_date
            ''',
            conn,
        )
        df_bills = pd.read_sql_query(
            '''
            SELECT
                billing_period_start,
                billing_period_end,
                actual_total_kwh,
                actual_total_cost,
                actual_energy_cost,
                actual_distribution_cost,
                bill_number,
                pdf_path
            FROM tauron_bills
            ORDER BY billing_period_start
            ''',
            conn,
        )
    finally:
        conn.close()

    if df_fc.empty or df_bills.empty:
        return pd.DataFrame()

    df_bills['billing_period_start'] = pd.to_datetime(df_bills['billing_period_start'])
    df_bills['billing_period_end'] = pd.to_datetime(df_bills['billing_period_end'])
    df_canon = _canonical_bills(df_bills)

    rows: list[dict[str, Any]] = []
    for _, fc in df_fc.iterrows():
        p_start, p_end = _forecast_period_bounds(str(fc['forecast_period']))
        mask = (df_canon['billing_period_start'] >= pd.Timestamp(p_start)) & (
            df_canon['billing_period_start'] <= pd.Timestamp(p_end)
        )
        bills_in_period = df_canon.loc[mask]

        forecast_kwh = float(fc['forecast_total_kwh']) if pd.notna(fc['forecast_total_kwh']) else None
        forecast_energy = float(fc['forecast_energy_cost']) if pd.notna(fc['forecast_energy_cost']) else None
        forecast_brutto = float(fc['forecast_total_cost']) if pd.notna(fc['forecast_total_cost']) else None
        forecast_doz = _parse_do_zaplaty_from_notes(fc.get('notes'))

        if bills_in_period.empty:
            actual_kwh = actual_energy = actual_brutto = actual_doz = None
            n_months = 0
            bill_kinds = ''
        else:
            actual_kwh = float(bills_in_period['actual_total_kwh'].sum())
            actual_energy = float(bills_in_period['actual_energy_cost'].sum())
            actual_brutto = float(bills_in_period['actual_total_cost'].sum())
            doz_vals = [_parse_bill_do_zaplaty(p) for p in bills_in_period['pdf_path']]
            doz_vals = [v for v in doz_vals if v is not None]
            has_korekta = (bills_in_period['bill_kind'] == 'korekta').any()
            # Korekta = pełna kwota faktury po korekcie — nie sumować z rozliczeniem (fałszywy Δ do zapłaty).
            actual_doz = None if has_korekta else (float(sum(doz_vals)) if doz_vals else None)
            n_months = int(len(bills_in_period))
            bill_kinds = ', '.join(sorted(set(bills_in_period['bill_kind'].astype(str))))

        delta_kwh, delta_kwh_pct = _delta_pair(actual_kwh, forecast_kwh)
        delta_energy, delta_energy_pct = _delta_pair(actual_energy, forecast_energy)
        delta_brutto, delta_brutto_pct = _delta_pair(actual_brutto, forecast_brutto)
        delta_doz, delta_doz_pct = _delta_pair(actual_doz, forecast_doz)

        rows.append(
            {
                'forecast_date': fc['forecast_date'],
                'okres': str(fc['forecast_period']).replace('_', ' – '),
                'okres_od': p_start,
                'okres_do': p_end,
                'prognoza_kwh': forecast_kwh,
                'faktura_kwh': actual_kwh,
                'delta_kwh': delta_kwh,
                'delta_kwh_pct': delta_kwh_pct,
                'prognoza_energia_zl': forecast_energy,
                'faktura_energia_zl': actual_energy,
                'delta_energia_zl': delta_energy,
                'delta_energia_pct': delta_energy_pct,
                'prognoza_brutto_zl': forecast_brutto,
                'faktura_brutto_zl': actual_brutto,
                'delta_brutto_zl': delta_brutto,
                'delta_brutto_pct': delta_brutto_pct,
                'prognoza_do_zaplaty_zl': forecast_doz,
                'faktura_do_zaplaty_zl': actual_doz,
                'delta_do_zaplaty_zl': delta_doz,
                'delta_do_zaplaty_pct': delta_doz_pct,
                'miesiecy_faktur': n_months,
                'typ_faktur': bill_kinds,
                'source': fc.get('source'),
            }
        )

    return pd.DataFrame(rows)


def _upsert_meter_reading(conn: sqlite3.Connection, payload: TauronInvoiceInput) -> None:
    total_import = payload.actual_zone1_kwh + payload.actual_zone2_kwh
    conn.execute(
        '''
        INSERT OR REPLACE INTO meter_readings (
            period_start, period_end, import_kwh, export_kwh,
            import_zone1_kwh, import_zone2_kwh, export_zone1_kwh, export_zone2_kwh,
            source, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            payload.billing_period_start,
            payload.billing_period_end,
            total_import,
            payload.energy_exported_kwh,
            payload.actual_zone1_kwh,
            payload.actual_zone2_kwh,
            payload.export_zone1_kwh,
            payload.export_zone2_kwh,
            'licznik_tauron',
            f'wpis dashboard | {payload.bill_number}',
        ),
    )
    conn.commit()


def save_invoice(payload: TauronInvoiceInput, *, db_path: str | None = None) -> dict[str, Any]:
    """Zapis rachunku (+ opcjonalnie stawki i odczytu licznika). UPSERT po okresie rozliczeniowym."""
    if payload.billing_period_start > payload.billing_period_end:
        raise ValueError('Data początku okresu musi być ≤ data końca.')

    was_existing = period_exists(
        payload.billing_period_start,
        payload.billing_period_end,
        db_path=db_path,
    )
    total_import = payload.actual_zone1_kwh + payload.actual_zone2_kwh
    bill_dict = {
        'bill_date': payload.bill_date,
        'billing_period_start': payload.billing_period_start,
        'billing_period_end': payload.billing_period_end,
        'actual_zone1_kwh': payload.actual_zone1_kwh,
        'actual_zone2_kwh': payload.actual_zone2_kwh,
        'actual_total_kwh': total_import,
        'actual_energy_cost': payload.actual_energy_cost,
        'actual_distribution_cost': payload.actual_distribution_cost,
        'actual_fixed_costs': payload.actual_fixed_costs,
        'actual_total_cost': payload.actual_total_cost,
        'energy_exported_kwh': payload.energy_exported_kwh,
        'energy_exported_value': payload.energy_exported_value,
        'bill_number': payload.bill_number,
        'pdf_path': payload.pdf_path or '',
    }

    db = _resolve_db_path(db_path)
    importer = EnergyDataImporter(db_path=db)
    try:
        importer.import_tauron_bill(bill_dict)

        if payload.save_tariff and payload.tariff_valid_from:
            tariff = {
                'valid_from': payload.tariff_valid_from,
                'tariff_name': 'G12w',
                'price_zone1_day': payload.price_zone1_day,
                'price_zone2_night': payload.price_zone2_night,
                'distribution_zone1': payload.distribution_zone1,
                'distribution_zone2': payload.distribution_zone2,
                'subscription_fee_monthly': payload.subscription_fee_monthly,
                'power_fee_monthly': payload.power_fee_monthly,
                'transition_fee_monthly': payload.transition_fee_monthly,
                'oze_fee_kwh': payload.oze_fee_kwh,
                'cogenerative_fee_kwh': payload.cogenerative_fee_kwh,
                'notes': payload.tariff_notes or f'dashboard | {payload.bill_number}',
            }
            importer.import_tauron_tariff(data_dict=tariff)

        if payload.save_meter_reading:
            conn = _connect(db_path)
            _upsert_meter_reading(conn, payload)
            conn.close()
    finally:
        importer.close()

    return {
        'bill_number': payload.bill_number,
        'period': f'{payload.billing_period_start} → {payload.billing_period_end}',
        'import_kwh': total_import,
        'export_kwh': payload.energy_exported_kwh,
        'total_brutto': payload.actual_total_cost,
        'was_existing': was_existing,
    }
