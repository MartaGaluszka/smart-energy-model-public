"""Feed sugestii baterii (§9.6 / T4.18–T4.20) — advise-only.

T4.20: generator (cron + GET) upsertuje na dzień:
- cheap_window — okno G12w + plan dziś/jutro (kontekst morning / pre_cheap / peak),
- charge_tonight_cloudy — B2 (T+PV → FC 22–6),
- soc_reserve — BAT.3 (SoC@16).

Cron: mlops/generate_battery_suggestions.py (daily/midday/peak).
GET /notifications woła ten sam generator dla bieżącego użytkownika.

Wszystkie treści są doradcze — nigdy „wykonano automatycznie” (§9.6, T4.24).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Literal

from sqlalchemy.orm import Session

from api.models import AppUser, Notification
from api.services.advice_events import record_advice_event

NOTIF_TYPE_CHEAP_WINDOW = 'cheap_window'
NOTIF_TYPE_CHARGE_TONIGHT_CLOUDY = 'charge_tonight_cloudy'
NOTIF_TYPE_SOC16_RESERVE = 'soc_reserve'

SuggestionContext = Literal['morning', 'pre_cheap', 'peak']


def suggestion_context_for_hour(hour: int | None = None) -> SuggestionContext:
    h = datetime.now().hour if hour is None else hour
    if h < 11:
        return 'morning'
    if h < 15:
        return 'pre_cheap'
    return 'peak'


def _payload_day(payload_json: str | None) -> str | None:
    if not payload_json:
        return None
    try:
        return json.loads(payload_json).get('day')
    except json.JSONDecodeError:
        return None


def _upsert_day_notification(
    db: Session,
    user_id: int,
    *,
    notif_type: str,
    day_key: str,
    title: str,
    body: str,
    payload: str,
) -> Notification:
    existing = (
        db.query(Notification)
        .filter(
            Notification.user_id == user_id,
            Notification.notif_type == notif_type,
        )
        .order_by(Notification.created_at.desc())
        .all()
    )
    for row in existing:
        if _payload_day(row.payload_json) == day_key:
            row.title = title
            row.body = body
            row.payload_json = payload
            db.commit()
            db.refresh(row)
            record_advice_event(
                db,
                user_id,
                event_date=day_key,
                advice_type=notif_type,
                payload_json=payload,
                was_actionable=True,
            )
            return row

    notif = Notification(
        user_id=user_id,
        notif_type=notif_type,
        title=title,
        body=body,
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
        advice_type=notif_type,
        payload_json=payload,
        was_actionable=True,
    )
    return notif


def maybe_upsert_cheap_window(
    db: Session,
    user_id: int,
    context: SuggestionContext = 'morning',
) -> Notification | None:
    """Sugestia G12w: najbliższe okno + skrót planu dziś/jutro (zawsze 1×/dzień)."""
    try:
        from src.optimization.battery_advisor import (
            evaluate_below_reserve_wait_cheap,
            format_evening_battery_plan_note,
            get_battery_snapshot,
            get_day_pv_forecast_sum,
            get_today_pv_observed_kwh,
            next_cheap_window_label,
            seasonal_soc_reserve,
        )
        from src.optimization.g12w_tariff import is_cheap_zone, tariff_summary
    except Exception:
        return None

    as_of = datetime.now()
    day_key = as_of.date().isoformat()
    tomorrow_s = (as_of.date() + timedelta(days=1)).isoformat()
    snap = get_battery_snapshot()
    reserve = seasonal_soc_reserve(as_of.date())
    wait = evaluate_below_reserve_wait_cheap(
        soc_percent=snap.soc_percent,
        as_of=as_of,
        reserve_percent=reserve,
    )
    tomorrow_pv = get_day_pv_forecast_sum(tomorrow_s, as_of=as_of) or 0.0
    today_pv = get_day_pv_forecast_sum(day_key, as_of=as_of) or 0.0
    # Prognoza modelu do startu okna 13–15 (godziny < 13), nie fakt dotychczas.
    today_pv_until_13 = get_day_pv_forecast_sum(day_key, as_of=as_of, until_hour=13)
    if today_pv_until_13 is None:
        today_pv_until_13 = today_pv
    today_actual = get_today_pv_observed_kwh(day_key)
    nxt = next_cheap_window_label(as_of)
    in_cheap = is_cheap_zone(as_of)
    evening_note = format_evening_battery_plan_note(
        soc_percent=snap.soc_percent,
        today_pv_kwh=today_pv,
        tomorrow_pv_kwh=tomorrow_pv,
        as_of=as_of,
        reserve_percent=reserve,
        today_pv_actual_kwh=today_actual,
    )

    if wait.triggered:
        title = wait.title
        body = f'{wait.body} {evening_note}'.strip()
    elif context == 'morning':
        title = 'Sugestia: tania strefa G12w (rano)'
        body = (
            f'Sugestia doradcza — {tariff_summary()} '
            f'Najbliższe tanie okno: {nxt}. '
            f'Prognoza PV dziś ~{today_pv:.0f} kWh, jutro ~{tomorrow_pv:.0f} kWh. '
            f'Rozważ ładowanie magazynu w taniej strefie — bez automatyki.'
        )
    elif context == 'pre_cheap':
        title = 'Sugestia: zbliża się okno 13:00–15:00'
        body = (
            f'Sugestia doradcza — za chwilę tania G12w 13–15 (pn–pt). '
            f'Najbliższe okno: {nxt}. '
            f'Prognoza PV dziś do 13:00 ~{today_pv_until_13:.0f} kWh '
            f'(cały dzień ~{today_pv:.0f} kWh). '
            f'Jeśli SoC niski, rozważ doładowanie w tanim oknie — decyzja należy do Ciebie.'
        )
    else:
        title = 'Sugestia: szczyt wieczorny — plan na noc'
        body = (
            f'Sugestia doradcza — droga G12w do 22:00. '
            f'Trzymaj rezerwę; tanie ładowanie nocne od 22:00 ({nxt}). '
            f'Prognoza PV dziś ~{today_pv:.0f} kWh; jutro ~{tomorrow_pv:.0f} kWh. '
            f'{evening_note} '
            f'System tylko doradza.'
        ).strip()

    payload = json.dumps(
        {
            'rule': NOTIF_TYPE_CHEAP_WINDOW,
            'day': day_key,
            'context': context,
            'next_cheap_window': nxt,
            'in_cheap_zone': in_cheap,
            'soc_percent': snap.soc_percent,
            'reserve_percent': reserve,
            'today_pv_kwh': today_pv,
            'today_pv_until_13_kwh': today_pv_until_13,
            'today_pv_actual_kwh': today_actual,
            'tomorrow_pv_kwh': tomorrow_pv,
            'wait_for_cheap': wait.triggered,
            'evening_note': evening_note,
        },
        ensure_ascii=False,
    )
    return _upsert_day_notification(
        db,
        user_id,
        notif_type=NOTIF_TYPE_CHEAP_WINDOW,
        day_key=day_key,
        title=title,
        body=body,
        payload=payload,
    )


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
    return _upsert_day_notification(
        db,
        user_id,
        notif_type=NOTIF_TYPE_CHARGE_TONIGHT_CLOUDY,
        day_key=day_key,
        title=rule.title,
        body=rule.body,
        payload=payload,
    )


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
    return _upsert_day_notification(
        db,
        user_id,
        notif_type=NOTIF_TYPE_SOC16_RESERVE,
        day_key=day_key,
        title=rule.title,
        body=rule.body,
        payload=payload,
    )


def generate_suggestions_for_user(
    db: Session,
    user_id: int,
    context: SuggestionContext | None = None,
) -> dict:
    """T4.20: jeden przebieg generatora dla użytkownika (cron lub GET)."""
    ctx = context or suggestion_context_for_hour()
    return {
        'context': ctx,
        'cheap_window': maybe_upsert_cheap_window(db, user_id, ctx),
        'charge_tonight_cloudy': maybe_upsert_charge_tonight_cloudy(db, user_id),
        'soc_reserve': maybe_upsert_soc16_reserve(db, user_id),
    }


def generate_suggestions_for_all_users(
    db: Session,
    context: SuggestionContext | None = None,
) -> dict:
    """Cron: upsert sugestii dla wszystkich aktywnych użytkowników appki."""
    ctx = context or suggestion_context_for_hour()
    users = db.query(AppUser).filter(AppUser.is_active.is_(True)).all()
    summary = {
        'context': ctx,
        'users': len(users),
        'cheap_window': 0,
        'charge_tonight_cloudy': 0,
        'soc_reserve': 0,
    }
    for user in users:
        result = generate_suggestions_for_user(db, user.id, ctx)
        for key in ('cheap_window', 'charge_tonight_cloudy', 'soc_reserve'):
            if result.get(key) is not None:
                summary[key] += 1
    return summary


def list_notifications(db: Session, user_id: int) -> list[Notification]:
    generate_suggestions_for_user(db, user_id)
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )
