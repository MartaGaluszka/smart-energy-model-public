"""ROI (TA.7): GET/PUT /roi/assumptions, POST /roi/calculate — Moduł 2 (§8)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.deps import get_current_user, get_db
from api.models import AppUser, RoiAssumptions
from api.schemas.roi import RoiAssumptionsResponse, RoiAssumptionsUpdate, RoiCalculateRequest, RoiCalculateResponse
from api.services import roi_service

router = APIRouter(prefix='/api/v1/roi', tags=['roi'], dependencies=[Depends(get_current_user)])


def _get_or_create(db: Session, user_id: int) -> RoiAssumptions:
    row = db.query(RoiAssumptions).filter(RoiAssumptions.user_id == user_id).first()
    if row is None:
        row = RoiAssumptions(user_id=user_id)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


@router.get('/assumptions', response_model=RoiAssumptionsResponse, summary='CAPEX/OPEX/inflacja użytkownika')
def get_assumptions(current_user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)) -> RoiAssumptionsResponse:
    row = _get_or_create(db, current_user.id)
    return RoiAssumptionsResponse(
        capex_pln=row.capex_pln,
        battery_capex_pln=row.battery_capex_pln,
        opex_pln_year=row.opex_pln_year,
        inflation_pct=row.inflation_pct,
        seller_baseline_pln_year=row.seller_baseline_pln_year,
    )


@router.put('/assumptions', response_model=RoiAssumptionsResponse, summary='Zapis założeń ROI')
def update_assumptions(
    body: RoiAssumptionsUpdate,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RoiAssumptionsResponse:
    row = _get_or_create(db, current_user.id)
    for field, value in body.model_dump().items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return RoiAssumptionsResponse(
        capex_pln=row.capex_pln,
        battery_capex_pln=row.battery_capex_pln,
        opex_pln_year=row.opex_pln_year,
        inflation_pct=row.inflation_pct,
        seller_baseline_pln_year=row.seller_baseline_pln_year,
    )


@router.post('/calculate', response_model=RoiCalculateResponse, summary='Payback, ROI %, seria skumulowanych oszczędności')
def calculate(
    body: RoiCalculateRequest,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RoiCalculateResponse:
    row = _get_or_create(db, current_user.id)
    assumptions = {
        'capex_pln': row.capex_pln,
        'battery_capex_pln': row.battery_capex_pln,
        'opex_pln_year': row.opex_pln_year,
        'inflation_pct': row.inflation_pct,
    }
    return RoiCalculateResponse(**roi_service.calculate_roi(body.period_start, body.period_end, assumptions))
