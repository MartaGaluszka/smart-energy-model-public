from __future__ import annotations

import re
from datetime import date, datetime

from pydantic import BaseModel, field_validator

_HHMM = re.compile(r'^([01]\d|2[0-3]):[0-5]\d$')
MAX_DURATION_MIN = 24 * 60


def _clean_hhmm(value: object) -> str | None:
    """HH:MM albo None (puste = wyczyść). Inne formaty → ValueError (422)."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if not _HHMM.match(text):
        raise ValueError('Godzina w formacie HH:MM.')
    return text


def _clean_duration(value: object) -> int | None:
    if value is None:
        return None
    minutes = int(value)
    if minutes <= 0 or minutes > MAX_DURATION_MIN:
        raise ValueError('Czas programu: od 1 min do 24 h.')
    return minutes


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


class _EventTimes(BaseModel):
    """Początek i czas programu AGD. Wszystko opcjonalne — plan bez godziny = jeszcze nie zrobione."""

    start_time: str | None = None
    duration_min: int | None = None
    planned_time: str | None = None

    @field_validator('start_time', 'planned_time', mode='before')
    @classmethod
    def check_time(cls, value: object) -> str | None:
        return _clean_hhmm(value)

    @field_validator('duration_min', mode='before')
    @classmethod
    def check_duration(cls, value: object) -> int | None:
        return _clean_duration(value)


class HouseholdEventCreate(_EventTimes):
    event_date: str
    event_type: str
    impact: str = 'neutral'
    note: str | None = None

    @field_validator('event_date', mode='before')
    @classmethod
    def coerce_event_date(cls, value: object) -> str:
        return _as_iso_date(value)


class HouseholdEventUpdate(_EventTimes):
    """PATCH: zmieniają się tylko pola wysłane w body (null = wyczyść)."""


class HouseholdEventResponse(BaseModel):
    id: int
    event_date: str
    event_type: str
    impact: str
    note: str | None = None
    start_time: str | None = None
    duration_min: int | None = None
    planned_time: str | None = None

    @field_validator('event_date', mode='before')
    @classmethod
    def coerce_event_date(cls, value: object) -> str:
        return _as_iso_date(value)
