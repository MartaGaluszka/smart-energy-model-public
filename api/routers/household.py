"""Household (TA.9, P1): CRUD kalendarza kontekstowego (§10.1)."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.deps import get_current_user, get_db
from api.errors import ApiError
from api.models import AppUser, HouseholdCustomType, HouseholdEvent
from api.schemas.household import (
    HouseholdCustomTypeCreate,
    HouseholdCustomTypeResponse,
    HouseholdEventCreate,
    HouseholdEventResponse,
)

router = APIRouter(prefix='/api/v1/household', tags=['household'], dependencies=[Depends(get_current_user)])

CUSTOM_ICONS = frozenset(
    {
        'car-outline',
        'flash-outline',
        'construct-outline',
        'thermometer-outline',
        'home-outline',
        'water-outline',
        'laptop-outline',
        'leaf-outline',
    }
)
_CUSTOM_EVENT = re.compile(r'^c(\d+)$')


def _custom_response(row: HouseholdCustomType) -> HouseholdCustomTypeResponse:
    return HouseholdCustomTypeResponse(
        id=row.id,
        label=row.label,
        icon=row.icon,
        kwh=row.kwh,
        archived=bool(row.archived),
    )


def _require_own_custom(db: Session, user_id: int, event_type: str) -> None:
    match = _CUSTOM_EVENT.match((event_type or '').strip())
    if match is None:
        return
    row = (
        db.query(HouseholdCustomType)
        .filter(HouseholdCustomType.id == int(match.group(1)), HouseholdCustomType.user_id == user_id)
        .first()
    )
    if row is None:
        raise ApiError(400, 'CUSTOM_TYPE_NOT_FOUND', 'Nie ma takiej własnej pozycji.')


@router.get('/custom-types', response_model=list[HouseholdCustomTypeResponse], summary='Własne pozycje planu')
def list_custom_types(
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[HouseholdCustomTypeResponse]:
    rows = (
        db.query(HouseholdCustomType)
        .filter(HouseholdCustomType.user_id == current_user.id)
        .order_by(HouseholdCustomType.id)
        .all()
    )
    return [_custom_response(r) for r in rows]


@router.post('/custom-types', response_model=HouseholdCustomTypeResponse, status_code=201, summary='Nowa własna pozycja')
def create_custom_type(
    body: HouseholdCustomTypeCreate,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HouseholdCustomTypeResponse:
    label = ' '.join((body.label or '').split())
    if not label or len(label) > 12:
        raise ApiError(400, 'CUSTOM_LABEL', 'Nazwa może mieć najwyżej 12 znaków, żeby zmieściła się na kafelku.')
    if body.icon not in CUSTOM_ICONS:
        raise ApiError(400, 'CUSTOM_ICON', 'Wybierz ikonę z listy.')
    if body.kwh <= 0 or body.kwh > 100:
        raise ApiError(400, 'CUSTOM_KWH', 'Zużycie podaj w kWh, większe od zera i nie większe niż 100.')
    row = HouseholdCustomType(
        user_id=current_user.id,
        label=label,
        icon=body.icon,
        kwh=round(float(body.kwh), 2),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _custom_response(row)


@router.delete('/custom-types/{type_id}', status_code=204, response_model=None, summary='Ukrycie własnej pozycji z siatki')
def archive_custom_type(
    type_id: int,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    row = (
        db.query(HouseholdCustomType)
        .filter(HouseholdCustomType.id == type_id, HouseholdCustomType.user_id == current_user.id)
        .first()
    )
    if row is None:
        raise ApiError(404, 'CUSTOM_TYPE_NOT_FOUND', 'Nie ma takiej własnej pozycji.')
    row.archived = True
    db.commit()


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
    # Wiele cykli tego samego typu na dzień OK (2× zmywarka, 2× pranie…).
    _require_own_custom(db, current_user.id, body.event_type)
    row = HouseholdEvent(user_id=current_user.id, **body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return HouseholdEventResponse(
        id=row.id,
        event_date=row.event_date,
        event_type=row.event_type,
        impact=row.impact,
        note=row.note,
    )


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
