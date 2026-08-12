"""Testy kalkulatora depozytu RCEm × oddanie (model Tauron)."""

from __future__ import annotations

import os
import sqlite3

import pandas as pd
import pytest

from src.data.rcem import get_rcem, import_seed_to_db
from src.financial.prosumer_deposit import (
    build_rcem_accrual_table,
    build_invoice_deposit_comparison,
    load_bills_for_deposit_report,
    load_deposit_rcem_report,
)

DEFAULT_DB = os.getenv('DATABASE_PATH', 'data/energy_model.db')

_TAURON_BILLS_DDL = '''
CREATE TABLE IF NOT EXISTS tauron_bills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_date DATE NOT NULL,
    billing_period_start DATE NOT NULL,
    billing_period_end DATE NOT NULL,
    actual_zone1_kwh REAL,
    actual_zone2_kwh REAL,
    actual_total_kwh REAL,
    actual_energy_cost REAL,
    actual_distribution_cost REAL,
    actual_fixed_costs REAL,
    actual_total_cost REAL,
    energy_exported_kwh REAL,
    energy_exported_value REAL,
    bill_number VARCHAR(50) UNIQUE,
    pdf_path TEXT,
    UNIQUE(billing_period_start, billing_period_end)
);
'''

_MINIMAL_BILLS = (
    ('2025-05-01', '2025-05-31', 100.0, 'TEST-2025-05', None),
    ('2025-06-01', '2025-06-30', 200.0, 'TEST-2025-06', None),
    ('2025-07-01', '2025-07-31', 150.0, 'TEST-2025-07', 'depozyt_poprzednie=15.0'),
    ('2025-08-01', '2025-08-31', 80.0, 'TEST-2025-08', 'depozyt_poprzednie=25.0'),
)


def _tauron_bills_count(db_path: str) -> int:
    if not os.path.isfile(db_path):
        return 0
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='tauron_bills'",
        ).fetchone()
        if not row or row[0] == 0:
            return 0
        return int(conn.execute('SELECT COUNT(*) FROM tauron_bills').fetchone()[0])
    except sqlite3.Error:
        return 0
    finally:
        conn.close()


def _seed_minimal_deposit_db(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.executescript(_TAURON_BILLS_DDL)
    for start, end, export_kwh, bill_number, pdf_path in _MINIMAL_BILLS:
        conn.execute(
            '''
            INSERT INTO tauron_bills (
                bill_date, billing_period_start, billing_period_end,
                actual_total_kwh, actual_total_cost,
                energy_exported_kwh, bill_number, pdf_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (start, start, end, 300.0, 100.0, export_kwh, bill_number, pdf_path),
        )
    conn.commit()
    conn.close()
    import_seed_to_db(db_path)


@pytest.fixture(scope='module')
def deposit_db_path(tmp_path_factory):
    """Lokalnie: pełna baza; CI: syntetyczna baza z fakturami i RCEm."""
    if _tauron_bills_count(DEFAULT_DB) > 0:
        return DEFAULT_DB
    db = tmp_path_factory.mktemp('deposit') / 'test_deposit.db'
    _seed_minimal_deposit_db(str(db))
    return str(db)


@pytest.fixture(scope='module')
def deposit_report(deposit_db_path):
    return load_deposit_rcem_report(deposit_db_path)


def test_suma_nalezne_equals_accrual_sum(deposit_report):
    acc = deposit_report['accrual']
    s = deposit_report['summary']
    manual = float(acc['nalezny_depozyt_zl'].sum())
    assert s['suma_nalezny_rcem_zl'] == round(manual, 2)


def test_suma_do_odebrania_identity(deposit_report):
    s = deposit_report['summary']
    assert s['suma_do_odebrania_zl'] == round(
        s['suma_nalezny_rcem_zl'] - s['suma_uzyty_faktury_zl'], 2,
    )
    assert s['saldo_model_koncowe_zl'] == s['suma_do_odebrania_zl']


def test_saldo_puli_non_negative(deposit_report):
    inv = deposit_report['invoices']
    assert (inv['saldo_model_po_zl'] >= 0).all()


def test_saldo_puli_cumulative(deposit_report):
    inv = deposit_report['invoices']
    s = deposit_report['summary']
    last = inv.iloc[-1]
    assert last['saldo_model_po_zl'] == s['saldo_model_koncowe_zl']


def test_accrual_uses_monthly_rcem_not_hourly(deposit_report, deposit_db_path):
    """Każdy wiersz = oddanie_faktury × RCEm miesiąca (tabela rcem_prices)."""
    acc = deposit_report['accrual'].dropna(subset=['nalezny_depozyt_zl'])
    for _, row in acc.iterrows():
        month = row['miesiac_eksportu']
        rcem = get_rcem(month, deposit_db_path)
        assert rcem is not None, f'Brak RCEm dla {month}'
        expected = round(float(row['oddanie_kwh']) * rcem['rce_pln_kwh'], 2)
        assert row['nalezny_depozyt_zl'] == expected
        assert rcem['source'] in {
            'pse_official', 'pse_seed', 'pse_seed_file', 'computed_from_rce',
        }


def test_pending_only_after_last_invoice(deposit_report, deposit_db_path):
    bills = load_bills_for_deposit_report(deposit_db_path)
    pending = deposit_report['pending']
    if pending.empty:
        return
    last = bills['period_month'].iloc[-1]
    assert (pending['faktura_docelowa'] > last).all()


def test_invoice_comparison_rebuild(deposit_report, deposit_db_path):
    bills = load_bills_for_deposit_report(deposit_db_path)
    acc = build_rcem_accrual_table(bills, deposit_db_path)
    inv = build_invoice_deposit_comparison(bills, acc)
    assert len(inv) == len(deposit_report['invoices'])
