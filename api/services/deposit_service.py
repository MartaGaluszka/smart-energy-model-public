"""Adapter FastAPI -> src/financial/prosumer_deposit.py (RCEm, §11 / TA.10)."""

from __future__ import annotations

from datetime import date

from api.config import get_settings
from api.errors import ApiError


def get_deposit_summary(period_month: str | None = None) -> dict:
    from src.data.rcem import get_rcem
    from src.financial.prosumer_deposit import calculate_prosumer_deposit_rcem

    settings = get_settings()
    requested = period_month or date.today().strftime('%Y-%m')
    month = requested

    # Bieżący miesiąc często nie ma jeszcze oficjalnego RCEm (PSE publikuje z opóźnieniem) —
    # bez fallbacku GET /deposit/summary i zagnieżdżone kalkulatory padały 404 co miesiąc.
    if get_rcem(month, settings.DATABASE_PATH) is None and period_month is None:
        fallback = _latest_rcem_month(settings.DATABASE_PATH)
        if fallback is None:
            raise ApiError(
                404,
                'DEPOSIT_RCEM_NOT_FOUND',
                f'Brak RCEm dla {requested} (i brak wcześniejszych miesięcy w bazie). '
                'Uruchom: python scripts/fetch_rcem.py --import-seed',
            )
        month = fallback

    try:
        summary = calculate_prosumer_deposit_rcem(settings.DATABASE_PATH, month)
    except ValueError as exc:
        raise ApiError(404, 'DEPOSIT_RCEM_NOT_FOUND', str(exc)) from exc

    return {
        'period_month': summary.period_month,
        'import_kwh': summary.import_kwh,
        'export_kwh': summary.export_kwh,
        'net_export_kwh': summary.net_export_kwh,
        'rcem_pln_kwh': summary.rcem_pln_kwh,
        'net_deposit_accrual_pln': summary.net_deposit_accrual_pln,
        'gross_export_value_pln': summary.gross_export_value_pln,
        'method': summary.method,
    }


def _latest_rcem_month(db_path: str) -> str | None:
    import sqlite3

    from src.data.rcem import ensure_rcem_table

    try:
        conn = sqlite3.connect(db_path)
        ensure_rcem_table(conn)
        row = conn.execute(
            'SELECT period_month FROM rcem_prices ORDER BY period_month DESC LIMIT 1'
        ).fetchone()
        conn.close()
    except sqlite3.Error:
        return None
    return str(row[0]) if row else None
