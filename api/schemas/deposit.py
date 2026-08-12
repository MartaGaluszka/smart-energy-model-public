from __future__ import annotations

from pydantic import BaseModel


class DepositSummaryResponse(BaseModel):
    period_month: str
    import_kwh: float
    export_kwh: float
    net_export_kwh: float
    rcem_pln_kwh: float
    net_deposit_accrual_pln: float
    gross_export_value_pln: float
    method: str
