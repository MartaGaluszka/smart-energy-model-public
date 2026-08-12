"""Household (TA.9, P1): CRUD kalendarza kontekstowego (§10.1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.deps import get_current_user, get_db
from api.errors import ApiError
from api.models import AppUser, HouseholdEvent
from api.schemas.household import HouseholdEventCreate, HouseholdEventResponse

router = APIRouter(prefix='/api/v1/household', tags=['household'], dependencies=[Depends(get_current_user)])


@router.get('/events', response_model=list[HouseholdEventResponse], summary='Lista wydarzeń (opcjonalny zakres dat)')
def list_events(
    date_from: str | None = Query(default=None, alias='from'),
    date_to: str | None = Query(default=None, alias='to'),
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[HouseholdEventResponse]:
    query = db.query(HouseholdEvent).filter(HouseholdEvent.user_id == current_user.id)
    if date_from:
        query = query.filter(HouseholdEvent.event_date >= date_from)
    if date_to:
        query = query.filter(HouseholdEvent.event_date <= date_to)
    rows = query.order_by(HouseholdEvent.event_date).all()
    return [
        HouseholdEventResponse(id=r.id, event_date=r.event_date, event_type=r.event_type, impact=r.impact, note=r.note)
        for r in rows
    ]


@router.post('/events', response_model=HouseholdEventResponse, status_code=201, summary='Dodanie wydarzenia')
def create_event(
    body: HouseholdEventCreate,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HouseholdEventResponse:
    row = HouseholdEvent(user_id=current_user.id, **body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return HouseholdEventResponse(id=row.id, event_date=row.event_date, event_type=row.event_type, impact=row.impact, note=row.note)


@router.delete('/events/{event_id}', status_code=204, response_model=None, summary='Usunięcie wydarzenia')
def delete_event(event_id: int, current_user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    row = (
        db.query(HouseholdEvent)
        .filter(HouseholdEvent.id == event_id, HouseholdEvent.user_id == current_user.id)
        .first()
    )
    if row is None:
        raise ApiError(404, 'EVENT_NOT_FOUND', 'Wydarzenie nie istnieje')
    db.delete(row)
    db.commit()
