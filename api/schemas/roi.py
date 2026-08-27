from __future__ import annotations

from pydantic import BaseModel


class RoiAssumptionsResponse(BaseModel):
    capex_pln: float
    battery_capex_pln: float | None = None
    opex_pln_year: float
    inflation_pct: float
    seller_baseline_pln_year: float | None = None


class RoiAssumptionsUpdate(BaseModel):
    capex_pln: float
    battery_capex_pln: float | None = None
    opex_pln_year: float = 0.0
    inflation_pct: float = 0.0
    seller_baseline_pln_year: float | None = None


class RoiCalculateRequest(BaseModel):
    period_start: str
    period_end: str


class RoiCalculatePoint(BaseModel):
    year: int
    cumulative_savings_pln: float


class RoiCalculateResponse(BaseModel):
    period_start: str
    period_end: str
    savings_pln_period: float  # brutto (z VAT 23%)
    savings_pln_year_annualized: float  # brutto (z VAT 23%)
    roi_percent: float | None = None
    payback_years: float | None = None
    cumulative_savings_series: list[RoiCalculatePoint]
