"""T4.17 — audit log sugestii doradczych (advice_events).

Jeden wiersz na (user, dzień, typ) — pod późniejszą walidację shadow vs reality.
Nie steruje falownikiem; tylko zapis, że rada została wygenerowana.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from api.models import AdviceEvent


def record_advice_event(
    db: Session,
    user_id: int,
    *,
    event_date: str,
    advice_type: str,
    payload_json: str | None = None,
    was_actionable: bool = True,
) -> AdviceEvent:
    """Upsert: max jeden event na użytkownika / dzień / typ sugestii."""
    existing = (
        db.query(AdviceEvent)
        .filter(
            AdviceEvent.user_id == user_id,
            AdviceEvent.event_date == event_date,
            AdviceEvent.advice_type == advice_type,
        )
        .first()
    )
    if existing is not None:
        if payload_json is not None:
            existing.payload_json = payload_json
        existing.was_actionable = was_actionable
        db.commit()
        db.refresh(existing)
        return existing

    row = AdviceEvent(
        user_id=user_id,
        event_date=event_date,
        advice_type=advice_type,
        payload_json=payload_json,
        was_actionable=was_actionable,
        created_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_advice_events(
    db: Session,
    user_id: int,
    *,
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int = 100,
) -> list[AdviceEvent]:
    q = db.query(AdviceEvent).filter(AdviceEvent.user_id == user_id)
    if from_date:
        q = q.filter(AdviceEvent.event_date >= from_date)
    if to_date:
        q = q.filter(AdviceEvent.event_date <= to_date)
    return q.order_by(AdviceEvent.event_date.desc(), AdviceEvent.id.desc()).limit(limit).all()
