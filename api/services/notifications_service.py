"""Feed sugestii baterii (§9.6 / T4.18-T4.20) — LEKKI stub + reguła pochmurno.

Pełny generator (worker/cron analizujący plan G12w + prognozę PV codziennie,
T4.20) to zakres Fazy 4. Tutaj:
- seed „cheap_window” dla pustego feedu (happy-path testów),
- reguła **charge_tonight_cloudy** (B2): T jutro + PV jutro → FC od 22:00 (albo pomiń vs cykl),
- T4.17: każdy upsert sugestii → `advice_events` (1×/dzień/typ, audit pod rok testów).

Wszystkie treści są doradcze — nigdy "wykonano automatycznie" (§9.6, T4.24).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from api.models import Notification
from api.services.advice_events import record_advice_event

NOTIF_TYPE_CHEAP_WINDOW = 'cheap_window'
NOTIF_TYPE_CHARGE_TONIGHT_CLOUDY = 'charge_tonight_cloudy'
NOTIF_TYPE_SOC16_RESERVE = 'soc_reserve'


def ensure_seed_notification(db: Session, user_id: int) -> None:
    existing = db.query(Notification).filter(Notification.user_id == user_id).first()
    if existing is not None:
        return

    from src.optimization.g12w_tariff import tariff_summary

    day_key = datetime.utcnow().date().isoformat()
    notif = Notification(
        user_id=user_id,
        notif_type=NOTIF_TYPE_CHEAP_WINDOW,
        title='Sugestia: tania strefa G12w',
        body=f'Sugestia doradcza — {tariff_summary()} Rozważ ładowanie magazynu w taniej strefie.',
        payload_json=json.dumps({'day': day_key, 'rule': NOTIF_TYPE_CHEAP_WINDOW}, ensure_ascii=False),
        created_at=datetime.utcnow(),
    )
    db.add(notif)
    db.commit()
    record_advice_event(
        db,
        user_id,
        event_date=day_key,
        advice_type=NOTIF_TYPE_CHEAP_WINDOW,
        payload_json=notif.payload_json,
        was_actionable=True,
    )


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
            get_day_mean_temp_c,
            get_day_pv_forecast_sum,
        )
    except Exception:
        return None

    as_of = datetime.now()
    snap = get_battery_snapshot()
    tomorrow_s = (as_of.date() + timedelta(days=1)).isoformat()
    tomorrow_pv = get_day_pv_forecast_sum(tomorrow_s, as_of=as_of)
    tomorrow_t = get_day_mean_temp_c(tomorrow_s)
    rule = evaluate_charge_tonight_cloudy(
        soc_percent=snap.soc_percent,
        tomorrow_pv_kwh=tomorrow_pv,
        as_of=as_of,
        tomorrow_temp_c=tomorrow_t,
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
            'tomorrow_temp_c': rule.tomorrow_temp_c,
            'soc_below': rule.soc_below,
            'weak_pv_below': rule.weak_pv_below,
            'target_soc_percent': rule.target_soc_percent,
            'fc_minutes': rule.fc_minutes,
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
            record_advice_event(
                db,
                user_id,
                event_date=day_key,
                advice_type=NOTIF_TYPE_CHARGE_TONIGHT_CLOUDY,
                payload_json=payload,
                was_actionable=True,
            )
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
    record_advice_event(
        db,
        user_id,
        event_date=day_key,
        advice_type=NOTIF_TYPE_CHARGE_TONIGHT_CLOUDY,
        payload_json=payload,
        was_actionable=True,
    )
    return notif


def maybe_upsert_soc16_reserve(db: Session, user_id: int) -> Notification | None:
    """BAT.3: SoC@16 < próg wieczorny → jedna sugestia na dzień (upsert)."""
    try:
        from src.optimization.battery_advisor import (
            evaluate_soc16_hold_reserve,
            get_battery_snapshot,
            get_soc_at_hour,
            seasonal_soc_reserve,
        )
    except Exception:
        return None

    as_of = datetime.now()
    snap = get_battery_snapshot()
    soc16 = get_soc_at_hour(as_of.date().isoformat(), 16)
    if as_of.hour >= 16:
        soc = soc16 if soc16 is not None else snap.soc_percent
    else:
        soc = snap.soc_percent
    reserve = seasonal_soc_reserve(as_of.date())
    rule = evaluate_soc16_hold_reserve(
        soc_percent=soc,
        as_of=as_of,
        reserve_percent=reserve,
    )
    if not rule.triggered:
        return None

    day_key = as_of.date().isoformat()
    payload = json.dumps(
        {
            'rule': NOTIF_TYPE_SOC16_RESERVE,
            'day': day_key,
            'soc_percent': rule.soc_percent,
            'soc16_percent': soc16,
            'min_evening_percent': rule.min_evening_percent,
            'reserve_percent': rule.reserve_percent,
            'recommendation': rule.recommendation,
        },
        ensure_ascii=False,
    )

    existing = (
        db.query(Notification)
        .filter(
            Notification.user_id == user_id,
            Notification.notif_type == NOTIF_TYPE_SOC16_RESERVE,
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
            record_advice_event(
                db,
                user_id,
                event_date=day_key,
                advice_type=NOTIF_TYPE_SOC16_RESERVE,
                payload_json=payload,
                was_actionable=True,
            )
            return row

    notif = Notification(
        user_id=user_id,
        notif_type=NOTIF_TYPE_SOC16_RESERVE,
        title=rule.title,
        body=rule.body,
        payload_json=payload,
        created_at=datetime.utcnow(),
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    record_advice_event(
        db,
        user_id,
        event_date=day_key,
        advice_type=NOTIF_TYPE_SOC16_RESERVE,
        payload_json=payload,
        was_actionable=True,
    )
    return notif


def list_notifications(db: Session, user_id: int) -> list[Notification]:
    ensure_seed_notification(db, user_id)
    maybe_upsert_charge_tonight_cloudy(db, user_id)
    maybe_upsert_soc16_reserve(db, user_id)
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )
