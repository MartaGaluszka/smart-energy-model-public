"""Feed sugestii baterii (§9.6 / T4.18-T4.20) — LEKKI stub + reguła pochmurno.

Pełny generator (worker/cron analizujący plan G12w + prognozę PV codziennie,
T4.20) to zakres Fazy 4. Tutaj:
- seed „cheap_window” dla pustego feedu (happy-path testów),
- reguła **charge_tonight_cloudy**: niski SoC + jutro słabe PV → sugestia ładowania od 22:00.

Wszystkie treści są doradcze — nigdy "wykonano automatycznie" (§9.6, T4.24).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from api.models import Notification

NOTIF_TYPE_CHARGE_TONIGHT_CLOUDY = 'charge_tonight_cloudy'


def ensure_seed_notification(db: Session, user_id: int) -> None:
    existing = db.query(Notification).filter(Notification.user_id == user_id).first()
    if existing is not None:
        return

    from src.optimization.g12w_tariff import tariff_summary

    notif = Notification(
        user_id=user_id,
        notif_type='cheap_window',
        title='Sugestia: tania strefa G12w',
        body=f'Sugestia doradcza — {tariff_summary()} Rozważ ładowanie magazynu w taniej strefie.',
        payload_json=None,
        created_at=datetime.utcnow(),
    )
    db.add(notif)
    db.commit()


def _payload_day(payload_json: str | None) -> str | None:
    if not payload_json:
        return None
    try:
        return json.loads(payload_json).get('day')
    except json.JSONDecodeError:
        return None


def maybe_upsert_charge_tonight_cloudy(db: Session, user_id: int) -> Notification | None:
    """Jeśli reguła się spina — jedna sugestia na kalendarzowy dzień (upsert)."""
    try:
        from src.optimization.battery_advisor import (
            evaluate_charge_tonight_cloudy,
            get_battery_snapshot,
            get_day_pv_forecast_sum,
        )
    except Exception:
        return None

    as_of = datetime.now()
    snap = get_battery_snapshot()
    tomorrow_s = (as_of.date() + timedelta(days=1)).isoformat()
    tomorrow_pv = get_day_pv_forecast_sum(tomorrow_s, as_of=as_of)
    rule = evaluate_charge_tonight_cloudy(
        soc_percent=snap.soc_percent,
        tomorrow_pv_kwh=tomorrow_pv,
        as_of=as_of,
    )
    if not rule.triggered:
        return None

    day_key = as_of.date().isoformat()
    payload = json.dumps(
        {
            'rule': NOTIF_TYPE_CHARGE_TONIGHT_CLOUDY,
            'day': day_key,
            'soc_percent': rule.soc_percent,
            'tomorrow_pv_kwh': rule.tomorrow_pv_kwh,
            'soc_below': rule.soc_below,
            'weak_pv_below': rule.weak_pv_below,
            'recommendation': rule.recommendation,
        },
        ensure_ascii=False,
    )

    existing = (
        db.query(Notification)
        .filter(
            Notification.user_id == user_id,
            Notification.notif_type == NOTIF_TYPE_CHARGE_TONIGHT_CLOUDY,
        )
        .order_by(Notification.created_at.desc())
        .all()
    )
    for row in existing:
        if _payload_day(row.payload_json) == day_key:
            row.title = rule.title
            row.body = rule.body
            row.payload_json = payload
            db.commit()
            db.refresh(row)
            return row

    notif = Notification(
        user_id=user_id,
        notif_type=NOTIF_TYPE_CHARGE_TONIGHT_CLOUDY,
        title=rule.title,
        body=rule.body,
        payload_json=payload,
        created_at=datetime.utcnow(),
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif


def list_notifications(db: Session, user_id: int) -> list[Notification]:
    ensure_seed_notification(db, user_id)
    maybe_upsert_charge_tonight_cloudy(db, user_id)
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )
