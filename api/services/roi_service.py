"""Adapter FastAPI -> FinancialAnalyzer (§8 Moduł 2 — ROI)."""

from __future__ import annotations

from datetime import date

from api.config import get_settings
from api.errors import ApiError


def calculate_roi(period_start: str, period_end: str, assumptions: dict) -> dict:
    from src.financial.roi_calculator import FinancialAnalyzer

    settings = get_settings()
    analyzer = FinancialAnalyzer(db_path=settings.DATABASE_PATH)
    try:
        roi_data = analyzer.calculate_roi(period_start, period_end, use_forecast_baseline=False)
    except Exception as exc:  # noqa: BLE001
        raise ApiError(422, 'ROI_CALCULATE_FAILED', f'Nie można policzyć ROI: {exc}') from exc
    finally:
        analyzer.close()

    # VAT 23% — wszystkie kwoty brutto (jak na fakturze)
    vat_rate = 1.23

    d0 = date.fromisoformat(period_start)
    d1 = date.fromisoformat(period_end)
    period_days = max(1, (d1 - d0).days + 1)
    savings_period = roi_data['savings_pln'] * vat_rate
    savings_annualized = savings_period * (365.0 / period_days)

    capex = assumptions.get('capex_pln', 0.0) + (assumptions.get('battery_capex_pln') or 0.0)
    opex = assumptions.get('opex_pln_year', 0.0)
    net_annual_savings = savings_annualized - opex

    roi_percent = None
    payback_years = None
    if capex > 0 and net_annual_savings > 0:
        roi_percent = round(net_annual_savings / capex * 100, 2)
        payback_years = round(capex / net_annual_savings, 2)

    series = []
    if capex > 0 and net_annual_savings != 0:
        inflation = 1 + (assumptions.get('inflation_pct', 0.0) / 100.0)
        cumulative = 0.0
        yearly = net_annual_savings
        for year in range(1, 21):
            cumulative += yearly
            series.append({'year': year, 'cumulative_savings_pln': round(cumulative, 2)})
            yearly *= inflation
            if cumulative >= capex * 1.5:
                break

    return {
        'period_start': period_start,
        'period_end': period_end,
        'savings_pln_period': round(savings_period, 2),
        'savings_pln_year_annualized': round(savings_annualized, 2),
        'roi_percent': roi_percent,
        'payback_years': payback_years,
        'cumulative_savings_series': series,
    }
