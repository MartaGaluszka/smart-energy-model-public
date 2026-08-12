"""Adapter FastAPI -> src/financial/prosumer_deposit.py (RCEm, §11 / TA.10)."""

from __future__ import annotations

from datetime import date

from api.config import get_settings
from api.errors import ApiError


def get_deposit_summary(period_month: str | None = None) -> dict:
    from src.financial.prosumer_deposit import calculate_prosumer_deposit_rcem

    settings = get_settings()
    month = period_month or date.today().strftime('%Y-%m')

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
