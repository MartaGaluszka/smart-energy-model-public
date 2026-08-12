"""
Kalkulator depozytu prosumenckiego.

- RCE godzinowa: max(0, export_h − import_h) × RCE_h  (z rce_prices)
- RCEm miesięczna: kWh × RCEm miesiąca  (model Tauron / PSE, konsultant)
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from typing import Literal, Optional, Tuple

import pandas as pd

from src.data.rce_api import load_grid_exchange_hourly, load_rce_hourly
from src.data.rcem import get_rcem


@dataclass
class DepositSummary:
    period_start: str
    period_end: str
    data_source: str
    total_import_kwh: float
    total_export_kwh: float
    gross_export_value_pln: float
    net_deposit_accrual_pln: float
    avg_rce_when_exporting: float
    hours_with_export: int
    hours_with_net_export: int
    rce_hours_matched: int
    invoice_deposit_previous: Optional[float] = None
    invoice_deposit_period: Optional[float] = None
    method: str = 'rce_hourly'

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class DepositSummaryRCEm:
    period_month: str
    period_start: str
    period_end: str
    data_source: str
    import_kwh: float
    export_kwh: float
    net_export_kwh: float
    rcem_pln_mwh: float
    rcem_pln_kwh: float
    rcem_source: str
    gross_export_value_pln: float
    net_deposit_accrual_pln: float
    implied_kwh_for_deposit: float
    invoice_deposit_previous: Optional[float] = None
    invoice_deposit_period: Optional[float] = None
    deposit_delay_months: int = 2
    export_month_for_delay: Optional[str] = None
    method: str = 'rcem_monthly'

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def load_monthly_exchange(
    db_path: str,
    period_month: str,
    source: str = 'auto',
) -> dict:
    """
    Miesięczny import/export [kWh].

    Priorytet: tauron_bills (faktura) → agregacja foxess/meter.
    """
    start = f'{period_month}-01'
    end = (pd.Timestamp(start) + pd.offsets.MonthEnd(0)).strftime('%Y-%m-%d')

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        '''
        SELECT actual_total_kwh, actual_zone1_kwh, actual_zone2_kwh,
               energy_exported_kwh, billing_period_start, billing_period_end
        FROM tauron_bills
        WHERE billing_period_start = ?
        ''',
        (start,),
    ).fetchone()
    conn.close()

    if row and row[0] is not None:
        imp = float(row[0])
        exp = float(row[3] or 0)
        return {
            'import_kwh': imp,
            'export_kwh': exp,
            'data_source': 'tauron_bills',
            'period_start': row[4] or start,
            'period_end': row[5] or end,
        }

    hourly = load_grid_exchange_hourly(db_path, start, end, source=source)
    if hourly.empty:
        raise ValueError(f'Brak danych import/export dla {period_month}')

    return {
        'import_kwh': round(hourly['import_kwh'].sum(), 2),
        'export_kwh': round(hourly['export_kwh'].sum(), 2),
        'data_source': str(hourly['data_source'].iloc[0]),
        'period_start': start,
        'period_end': end,
    }


def calculate_prosumer_deposit(
    db_path: str,
    start_date: str,
    end_date: str,
    exchange_source: str = 'auto',
    invoice_deposit_previous: Optional[float] = None,
    invoice_deposit_period: Optional[float] = None,
) -> Tuple[DepositSummary, pd.DataFrame]:
    """Depozyt z RCE godzinowej (kwadransy PSE → średnia godzinowa)."""
    rce = load_rce_hourly(db_path, start_date, end_date)
    exchange = load_grid_exchange_hourly(db_path, start_date, end_date, source=exchange_source)

    if exchange.empty:
        raise ValueError(f'Brak danych import/export ({exchange_source}) dla {start_date}–{end_date}')
    if rce.empty:
        raise ValueError(
            f'Brak RCE w bazie dla {start_date}–{end_date}. '
            f'Uruchom: python scripts/fetch_rce.py --start {start_date} --end {end_date}'
        )

    hourly = exchange.merge(rce, left_on='hour', right_on='hour', how='left')
    hourly['net_export_kwh'] = (hourly['export_kwh'] - hourly['import_kwh']).clip(lower=0)
    hourly['gross_export_value'] = hourly['export_kwh'] * hourly['rce_pln_kwh']
    hourly['deposit_value'] = hourly['net_export_kwh'] * hourly['rce_pln_kwh']

    matched = hourly['rce_pln_kwh'].notna().sum()
    export_mask = hourly['export_kwh'] > 0
    avg_rce = (
        hourly.loc[export_mask, 'gross_export_value'].sum()
        / hourly.loc[export_mask, 'export_kwh'].sum()
        if export_mask.any()
        else 0.0
    )

    summary = DepositSummary(
        period_start=start_date,
        period_end=end_date,
        data_source=str(hourly['data_source'].iloc[0]),
        total_import_kwh=round(hourly['import_kwh'].sum(), 2),
        total_export_kwh=round(hourly['export_kwh'].sum(), 2),
        gross_export_value_pln=round(hourly['gross_export_value'].sum(), 2),
        net_deposit_accrual_pln=round(hourly['deposit_value'].sum(), 2),
        avg_rce_when_exporting=round(avg_rce, 4),
        hours_with_export=int(export_mask.sum()),
        hours_with_net_export=int((hourly['net_export_kwh'] > 0).sum()),
        rce_hours_matched=int(matched),
        invoice_deposit_previous=invoice_deposit_previous,
        invoice_deposit_period=invoice_deposit_period,
    )
    return summary, hourly


def calculate_prosumer_deposit_rcem(
    db_path: str,
    period_month: str,
    exchange_source: str = 'auto',
    netting: Literal['gross', 'net'] = 'gross',
    invoice_deposit_previous: Optional[float] = None,
    invoice_deposit_period: Optional[float] = None,
    deposit_delay_months: int = 2,
) -> DepositSummaryRCEm:
    """
    Depozyt wg RCEm (miesięczna cena PSE) — model opisywany przez Tauron.

    netting:
        'gross' — export_kwh × RCEm (typowe na fakturze kwietniowej: 288 × 0,133)
        'net'   — max(0, export − import) × RCEm
    """
    rcem = get_rcem(period_month, db_path)
    if rcem is None:
        raise ValueError(
            f'Brak RCEm dla {period_month}. '
            f'Uruchom: python scripts/fetch_rcem.py --import-seed'
        )

    ex = load_monthly_exchange(db_path, period_month, source=exchange_source)
    imp = ex['import_kwh']
    exp = ex['export_kwh']
    net_exp = max(0.0, exp - imp)
    kwh = exp if netting == 'gross' else net_exp
    rce_kwh = rcem['rce_pln_kwh']
    value = kwh * rce_kwh
    gross = exp * rce_kwh
    implied = invoice_deposit_previous / rce_kwh if invoice_deposit_previous and rce_kwh else 0.0

    export_for_delay = (
        pd.Timestamp(f'{period_month}-01') - pd.DateOffset(months=deposit_delay_months)
    ).strftime('%Y-%m')

    return DepositSummaryRCEm(
        period_month=period_month,
        period_start=ex['period_start'],
        period_end=ex['period_end'],
        data_source=ex['data_source'],
        import_kwh=imp,
        export_kwh=exp,
        net_export_kwh=round(net_exp, 2),
        rcem_pln_mwh=rcem['rce_pln_mwh'],
        rcem_pln_kwh=rce_kwh,
        rcem_source=rcem['source'],
        gross_export_value_pln=round(gross, 2),
        net_deposit_accrual_pln=round(value, 2),
        implied_kwh_for_deposit=round(implied, 1),
        invoice_deposit_previous=invoice_deposit_previous,
        invoice_deposit_period=invoice_deposit_period,
        deposit_delay_months=deposit_delay_months,
        export_month_for_delay=export_for_delay,
    )


def calculate_cumulative_deposit(
    db_path: str,
    start_date: str,
    end_date: str,
    exchange_source: str = 'auto',
) -> float:
    """Suma depozytu RCE godzinowej za wiele miesięcy."""
    total = 0.0
    cur = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    while cur <= end:
        month_start = cur.replace(day=1)
        month_end = (month_start + pd.offsets.MonthEnd(0)).normalize()
        if month_end > end:
            month_end = end
        try:
            summary, _ = calculate_prosumer_deposit(
                db_path,
                month_start.strftime('%Y-%m-%d'),
                month_end.strftime('%Y-%m-%d'),
                exchange_source=exchange_source,
            )
            total += summary.net_deposit_accrual_pln
        except ValueError:
            pass
        cur = month_start + pd.offsets.MonthBegin(1)
    return round(total, 2)


def calculate_cumulative_deposit_rcem(
    db_path: str,
    start_month: str,
    end_month: str,
    exchange_source: str = 'auto',
    netting: Literal['gross', 'net'] = 'gross',
) -> pd.DataFrame:
    """Tabela miesięczna: RCEm × eksport dla każdego miesiąca."""
    rows = []
    cur = pd.Timestamp(f'{start_month}-01')
    end = pd.Timestamp(f'{end_month}-01')
    while cur <= end:
        month = cur.strftime('%Y-%m')
        try:
            s = calculate_prosumer_deposit_rcem(
                db_path, month, exchange_source=exchange_source, netting=netting,
            )
            rows.append(s.to_dict())
        except ValueError:
            pass
        cur += pd.DateOffset(months=1)
    return pd.DataFrame(rows)


DEPOSIT_DELAY_MONTHS = 2

# Korekty RCE — uzupełnienie depozyt_uzyty gdy brak w pdf_path
KOREKTY_DEPOZYT: dict[str, dict[str, float | str]] = {
    '2025-05': {'uzyty': 2.14, 'uwagi': 'korekta RCE maj 2025'},
    '2025-10': {'uzyty': 115.55, 'uwagi': 'korekta RCE październik 2025'},
    '2025-11': {'uzyty': 352.20, 'uwagi': 'korekta RCE listopad 2025'},
}


def _parse_deposit_meta(meta: Optional[str]) -> tuple[Optional[float], Optional[float]]:
    if not meta:
        return None, None
    prev = re.search(r'depozyt_poprzednie(?:_policzono)?=([\d.]+)', meta)
    okres = re.search(r'depozyt_okres=([\d.]+)', meta)
    return (
        float(prev.group(1)) if prev else None,
        float(okres.group(1)) if okres else None,
    )


def load_bills_for_deposit_report(db_path: str) -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(
        '''
        SELECT billing_period_start, billing_period_end, actual_total_kwh,
               energy_exported_kwh, actual_total_cost, pdf_path, bill_number
        FROM tauron_bills
        ORDER BY billing_period_start
        ''',
        conn,
    )
    conn.close()
    df['period_month'] = df['billing_period_start'].str[:7]
    dep = df['pdf_path'].apply(_parse_deposit_meta)
    df['depozyt_uzyty_zl'] = dep.apply(lambda x: x[0])
    df['depozyt_okres_zl'] = dep.apply(lambda x: x[1])
    for month, korekta in KOREKTY_DEPOZYT.items():
        mask = df['period_month'] == month
        if mask.any() and pd.isna(df.loc[mask, 'depozyt_uzyty_zl'].iloc[0]):
            df.loc[mask, 'depozyt_uzyty_zl'] = float(korekta['uzyty'])
    return df


def build_rcem_accrual_table(
    bills: pd.DataFrame,
    db_path: str,
    delay_months: int = DEPOSIT_DELAY_MONTHS,
    start_month: str = '2025-04',
) -> pd.DataFrame:
    """Miesiąc eksportu → należny depozyt (oddanie × RCEm) → faktura docelowa (M+delay)."""
    from src.data.household_context import GRID_PHYSICAL_START

    grid_start = GRID_PHYSICAL_START.strftime('%Y-%m')
    start = max(start_month, grid_start)
    rows: list[dict] = []
    for _, bill in bills.iterrows():
        month = bill['period_month']
        if month < start:
            continue
        export_kwh = float(bill['energy_exported_kwh'] or 0)
        if export_kwh <= 0 and month < '2025-05':
            continue

        rcem = get_rcem(month, db_path)
        if rcem is None:
            rows.append({
                'miesiac_eksportu': month,
                'oddanie_kwh': export_kwh,
                'rcem_zl_mwh': None,
                'rcem_zl_kwh': None,
                'nalezny_depozyt_zl': None,
                'faktura_docelowa': None,
                'uwagi': 'brak RCEm',
            })
            continue

        accrual = round(export_kwh * rcem['rce_pln_kwh'], 2)
        invoice_month = (
            pd.Timestamp(f'{month}-01') + pd.DateOffset(months=delay_months)
        ).strftime('%Y-%m')
        rows.append({
            'miesiac_eksportu': month,
            'oddanie_kwh': export_kwh,
            'rcem_zl_mwh': round(rcem['rce_pln_mwh'], 2),
            'rcem_zl_kwh': round(rcem['rce_pln_kwh'], 5),
            'nalezny_depozyt_zl': accrual,
            'faktura_docelowa': invoice_month,
            'rcem_zrodlo': rcem.get('source'),
        })
    return pd.DataFrame(rows)


def build_invoice_deposit_comparison(
    bills: pd.DataFrame,
    accrual: pd.DataFrame,
    start_month: str = '2025-05',
) -> pd.DataFrame:
    """Faktura → depozyt użyty (poz. 5) vs należny RCEm z eksportów kierowanych na ten miesiąc."""
    acc_by_invoice = (
        accrual.groupby('faktura_docelowa')['nalezny_depozyt_zl'].sum().to_dict()
        if not accrual.empty
        else {}
    )
    acc_valid = accrual.dropna(subset=['nalezny_depozyt_zl']) if not accrual.empty else accrual
    rows: list[dict] = []
    for _, bill in bills.iterrows():
        month = bill['period_month']
        if month < start_month:
            continue
        used = bill['depozyt_uzyty_zl']
        expected = acc_by_invoice.get(month)
        export_rows = accrual[accrual['faktura_docelowa'] == month]
        export_months = ', '.join(export_rows['miesiac_eksportu'].astype(str).tolist())
        nalezne = float(expected) if expected is not None else 0.0
        used_val = float(used) if pd.notna(used) else 0.0

        inv_through = bills[
            (bills['period_month'] >= start_month) & (bills['period_month'] <= month)
        ]
        cum_used = float(inv_through['depozyt_uzyty_zl'].dropna().sum())
        cum_nalezne = (
            float(acc_valid[acc_valid['miesiac_eksportu'] <= month]['nalezny_depozyt_zl'].sum())
            if not acc_valid.empty
            else 0.0
        )
        cum_used_przed = cum_used - (used_val if pd.notna(used) else 0.0)
        saldo_przed = round(max(0.0, cum_nalezne - cum_used_przed), 2)
        saldo_puli = round(max(0.0, cum_nalezne - cum_used), 2)

        rows.append({
            'faktura_za_miesiac': month,
            'depozyt_uzyty_faktura_zl': used,
            'nalezne_rcem_2mc_zl': expected,
            'roznica_uzyty_minus_nalezne': (
                round(used_val - nalezne, 2) if pd.notna(used) and expected is not None else None
            ),
            'saldo_model_przed_zl': saldo_przed,
            'saldo_model_po_zl': saldo_puli,
            'eksport_rozliczany_z_miesiecy': export_months or '—',
            'oddanie_w_miesiacu_faktury_kwh': bill['energy_exported_kwh'],
        })
    return pd.DataFrame(rows)


def load_deposit_rcem_report(
    db_path: str,
    delay_months: int = DEPOSIT_DELAY_MONTHS,
) -> dict[str, pd.DataFrame | dict[str, float | None]]:
    """
    Raport depozytu: RCEm × oddanie (model Tauron/PSE) vs depozyt użyty na fakturach.

    Opóźnienie domyślne 2 mc — eksport z M trafia na fakturę za M+2.
    """
    bills = load_bills_for_deposit_report(db_path)
    accrual = build_rcem_accrual_table(bills, db_path, delay_months=delay_months)
    invoices = build_invoice_deposit_comparison(bills, accrual)

    total_nalezne = float(accrual['nalezny_depozyt_zl'].sum()) if not accrual.empty else 0.0
    total_uzyte = float(invoices['depozyt_uzyty_faktura_zl'].dropna().sum()) if not invoices.empty else 0.0
    saldo_koncowe = float(invoices['saldo_model_po_zl'].iloc[-1]) if not invoices.empty else 0.0

    pending = build_pending_deposit_table(bills, accrual)
    depozyt_w_drodze = (
        float(pending['nalezny_depozyt_zl'].sum()) if not pending.empty else 0.0
    )
    suma_do_odebrania = round(total_nalezne - total_uzyte, 2)

    summary = {
        'delay_months': delay_months,
        'suma_nalezny_rcem_zl': round(total_nalezne, 2),
        'suma_uzyty_faktury_zl': round(total_uzyte, 2),
        'roznica_nalezne_minus_uzyte_zl': suma_do_odebrania,
        'saldo_model_koncowe_zl': saldo_koncowe,
        'depozyt_w_drodze_zl': round(depozyt_w_drodze, 2),
        'suma_do_odebrania_zl': suma_do_odebrania,
        'ostatnia_faktura_miesiac': (
            bills['period_month'].iloc[-1] if not bills.empty else None
        ),
    }
    return {
        'accrual': accrual,
        'invoices': invoices,
        'pending': pending,
        'summary': summary,
    }


def build_pending_deposit_table(
    bills: pd.DataFrame,
    accrual: pd.DataFrame,
) -> pd.DataFrame:
    """Eksporty naliczone RCEm, których faktura docelowa jeszcze nie wpadła do bazy."""
    if accrual.empty or bills.empty:
        return pd.DataFrame()

    last_month = bills['period_month'].iloc[-1]
    pending = accrual[
        accrual['faktura_docelowa'].notna()
        & (accrual['faktura_docelowa'] > last_month)
        & accrual['nalezny_depozyt_zl'].notna()
    ].copy()
    if pending.empty:
        return pending

    pending = pending.rename(columns={
        'miesiac_eksportu': 'eksport_z_miesiaca',
        'nalezny_depozyt_zl': 'nalezny_depozyt_zl',
    })
    pending['status'] = 'w drodze — czeka na fakturę'
    return pending[
        [
            'eksport_z_miesiaca',
            'oddanie_kwh',
            'rcem_zl_mwh',
            'nalezny_depozyt_zl',
            'faktura_docelowa',
            'status',
        ]
    ].reset_index(drop=True)


def build_rcem_vs_rce_hourly_comparison(
    db_path: str,
    start_month: str = '2025-04',
    exchange_source: str = 'auto',
) -> pd.DataFrame:
    """
    Porównanie wartości eksportu: stawka miesięczna RCEm vs RCE godzinowa (PSE).

    RCEm (Tauron): oddanie_faktura × RCEm miesiąca.
    RCE godz. brutto: Σ(eksport_h × RCE_h) — ta sama baza kWh co godzinowa wymiana.
    RCE godz. netto: Σ max(0, eksport_h − import_h) × RCE_h — model net-billing godzinowy.
    """
    from src.data.household_context import GRID_PHYSICAL_START

    grid_start = GRID_PHYSICAL_START.strftime('%Y-%m')
    start = max(start_month, grid_start)
    bills = load_bills_for_deposit_report(db_path)
    rows: list[dict] = []

    for _, bill in bills.iterrows():
        month = bill['period_month']
        if month < start:
            continue
        export_bill = float(bill['energy_exported_kwh'] or 0)
        if export_bill <= 0 and month < '2025-05':
            continue

        period_start = f'{month}-01'
        period_end = (pd.Timestamp(period_start) + pd.offsets.MonthEnd(0)).strftime('%Y-%m-%d')

        rcem_val: Optional[float] = None
        rcem_mwh: Optional[float] = None
        rcem_source: Optional[str] = None
        try:
            rcem_sum = calculate_prosumer_deposit_rcem(
                db_path, month, exchange_source=exchange_source, netting='gross',
            )
            rcem_val = rcem_sum.net_deposit_accrual_pln
            rcem_mwh = rcem_sum.rcem_pln_mwh
            rcem_source = rcem_sum.rcem_source
        except ValueError:
            pass

        hourly_brutto: Optional[float] = None
        hourly_netto: Optional[float] = None
        export_hourly: Optional[float] = None
        import_hourly: Optional[float] = None
        avg_rce_export: Optional[float] = None
        exchange_src: Optional[str] = None
        hourly_note: Optional[str] = None

        try:
            h_sum, _ = calculate_prosumer_deposit(
                db_path, period_start, period_end, exchange_source=exchange_source,
            )
            hourly_brutto = h_sum.gross_export_value_pln
            hourly_netto = h_sum.net_deposit_accrual_pln
            export_hourly = h_sum.total_export_kwh
            import_hourly = h_sum.total_import_kwh
            avg_rce_export = h_sum.avg_rce_when_exporting
            exchange_src = h_sum.data_source
            if h_sum.rce_hours_matched == 0:
                hourly_note = 'brak RCE godzinowej w bazie'
        except ValueError as exc:
            hourly_note = str(exc).split('.')[0]

        row: dict = {
            'miesiac': month,
            'oddanie_faktura_kwh': export_bill,
            'oddanie_godzinowe_kwh': export_hourly,
            'import_godzinowy_kwh': import_hourly,
            'rcem_zl_mwh': rcem_mwh,
            'rcem_zrodlo': rcem_source,
            'depozyt_rcem_zl': rcem_val,
            'depozyt_rce_godz_brutto_zl': hourly_brutto,
            'depozyt_rce_godz_netto_zl': hourly_netto,
            'sr_rce_przy_eksporcie_zl_kwh': avg_rce_export,
            'zrodlo_wymiany_godz': exchange_src,
            'uwagi': hourly_note,
        }
        if rcem_val is not None and hourly_brutto is not None:
            row['roznica_godz_brutto_minus_rcem_zl'] = round(hourly_brutto - rcem_val, 2)
        else:
            row['roznica_godz_brutto_minus_rcem_zl'] = None
        if rcem_val is not None and hourly_netto is not None:
            row['roznica_godz_netto_minus_rcem_zl'] = round(hourly_netto - rcem_val, 2)
        else:
            row['roznica_godz_netto_minus_rcem_zl'] = None
        rows.append(row)

    return pd.DataFrame(rows)


def load_rcem_vs_hourly_comparison(
    db_path: str,
    start_month: str = '2025-04',
    exchange_source: str = 'auto',
) -> dict[str, pd.DataFrame | dict[str, float | int]]:
    """Raport porównawczy RCEm vs RCE godzinowa + sumy po miesiącach z danymi."""
    df = build_rcem_vs_rce_hourly_comparison(db_path, start_month, exchange_source)
    has_hourly = df['depozyt_rce_godz_brutto_zl'].notna()
    has_rcem = df['depozyt_rcem_zl'].notna()
    both = has_rcem & has_hourly

    summary: dict[str, float | int] = {
        'miesiecy_rcem': int(has_rcem.sum()),
        'miesiecy_godzinowa': int(has_hourly.sum()),
        'miesiecy_wspolne': int(both.sum()),
        'suma_rcem_zl': round(float(df.loc[has_rcem, 'depozyt_rcem_zl'].sum()), 2),
        'suma_rce_godz_brutto_zl': round(
            float(df.loc[has_hourly, 'depozyt_rce_godz_brutto_zl'].sum()), 2,
        ),
        'suma_rce_godz_netto_zl': round(
            float(df.loc[has_hourly, 'depozyt_rce_godz_netto_zl'].sum()), 2,
        ),
    }
    if both.any():
        rcem_wsp = float(df.loc[both, 'depozyt_rcem_zl'].sum())
        godz_brutto_wsp = float(df.loc[both, 'depozyt_rce_godz_brutto_zl'].sum())
        godz_netto_wsp = float(df.loc[both, 'depozyt_rce_godz_netto_zl'].sum())
        roznica_brutto = round(godz_brutto_wsp - rcem_wsp, 2)
        summary['suma_rcem_wspolne_mc_zl'] = round(rcem_wsp, 2)
        summary['suma_rce_godz_brutto_wspolne_zl'] = round(godz_brutto_wsp, 2)
        summary['suma_rce_godz_netto_wspolne_zl'] = round(godz_netto_wsp, 2)
        summary['roznica_brutto_minus_rcem_zl'] = roznica_brutto
        summary['roznica_netto_minus_rcem_zl'] = round(godz_netto_wsp - rcem_wsp, 2)
        months_wsp = df.loc[both, 'miesiac'].astype(str).tolist()
        summary['okres_wspolny_od'] = min(months_wsp)
        summary['okres_wspolny_do'] = max(months_wsp)
        if roznica_brutto < 0:
            summary['godzinowka_mniej_niz_rcem_zl'] = round(-roznica_brutto, 2)
        elif roznica_brutto > 0:
            summary['godzinowka_wiecej_niz_rcem_zl'] = roznica_brutto
    return {'comparison': df, 'summary': summary}
