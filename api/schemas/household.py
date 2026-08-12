from __future__ import annotations

from pydantic import BaseModel


class HouseholdEventCreate(BaseModel):
    event_date: str
    event_type: str
    impact: str = 'neutral'
    note: str | None = None


class HouseholdEventResponse(BaseModel):
    id: int
    event_date: str
    event_type: str
    impact: str
    note: str | None = None
