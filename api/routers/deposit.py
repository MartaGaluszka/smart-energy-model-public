"""Deposit (TA.10, P1): GET /deposit/summary — depozyt RCEm (§11)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.deps import get_current_user
from api.schemas.deposit import DepositSummaryResponse
from api.services.deposit_service import get_deposit_summary

router = APIRouter(prefix='/api/v1/deposit', tags=['deposit'], dependencies=[Depends(get_current_user)])


@router.get('/summary', response_model=DepositSummaryResponse, summary='Wolny depozyt + pending RCEm dla miesiąca')
def summary(month: str | None = Query(default=None, description='YYYY-MM, domyślnie bieżący miesiąc')) -> DepositSummaryResponse:
    return DepositSummaryResponse(**get_deposit_summary(month))
