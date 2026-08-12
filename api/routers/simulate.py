"""Simulate (TA.6): POST /simulate/bill — Moduł 1 Symulator Rachunków (§7)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.deps import get_current_user, get_db
from api.models import AppUser
from api.schemas.simulate import SimulateBillRequest, SimulateBillResponse
from api.services import bill_simulator

router = APIRouter(prefix='/api/v1/simulate', tags=['simulate'], dependencies=[Depends(get_current_user)])


@router.post('/bill', response_model=SimulateBillResponse, summary='cost_no_pv vs cost_with_pv vs savings (§7.3)')
def simulate_bill(
    body: SimulateBillRequest,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SimulateBillResponse:
    return SimulateBillResponse(
        **bill_simulator.simulate_bill(
            body.period_start,
            body.period_end,
            body.rates_override,
            db=db,
            user_id=current_user.id,
        )
    )
