from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, field_validator


def _as_iso_date(value: object) -> str:
    """Postgres ma kolumnę DATE → SQLAlchemy oddaje ``datetime.date``; API trzyma ISO string."""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


class FloorHeatDayResponse(BaseModel):
    day: str
    kwh: float
    cycles: int
    night_kwh: float = 0


class HouseholdCustomTypeCreate(BaseModel):
    label: str
    icon: str
    kwh: float


class HouseholdCustomTypeResponse(BaseModel):
    id: int
    label: str
    icon: str
    kwh: float
    archived: bool = False


class HouseholdEventCreate(BaseModel):
    event_date: str
    event_type: str
    impact: str = 'neutral'
    note: str | None = None

    @field_validator('event_date', mode='before')
    @classmethod
    def coerce_event_date(cls, value: object) -> str:
        return _as_iso_date(value)


class HouseholdEventResponse(BaseModel):
    id: int
    event_date: str
    event_type: str
    impact: str
    note: str | None = None

    @field_validator('event_date', mode='before')
    @classmethod
    def coerce_event_date(cls, value: object) -> str:
        return _as_iso_date(value)
