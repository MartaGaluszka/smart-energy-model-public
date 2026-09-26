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
    savings_pln_period: float  # oszczędność rachunku brutto (jak symulator)
    deposit_pln_period: float = 0.0  # naliczenie depozytu RCEm (eksport → Tauron)
    opex_pln_period: float = 0.0  # przegląd rozłożony na dni okresu
    cash_gain_pln_period: float = 0.0  # rachunek + depozyt − przegląd
    recovered_pln: float = 0.0  # ile kosztów początkowych już spłacone w okresie
    remaining_pln: float = 0.0  # ile jeszcze do zwrotu (zł)
    remaining_years: float | None = None  # ile lat zostało przy tempie z okresu
    savings_pln_year_annualized: float  # tempo z okresu → zł/rok (informacyjnie)
    roi_percent: float | None = None
    payback_years: float | None = None  # pełny okres zwrotu od daty startu
    payback_reached_in_period: bool = False
    cumulative_savings_series: list[RoiCalculatePoint]
