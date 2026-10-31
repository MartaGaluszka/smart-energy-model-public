"""Bateria — ustawienia, plan doradczy i sterowanie nocne B2 (T6.1 / T6.2c)."""

from __future__ import annotations

from datetime import datetime, timedelta
import os

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from api.deps import get_current_user, get_db
from api.models import AppUser, BatteryControlAudit, BatteryStrategySettings
from api.schemas.battery import (
    AcRuntimeRequest,
    AcRuntimeResponse,
    BatteryPlanResponse,
    BatteryPolicyResponse,
    BatterySettingsResponse,
    BatterySettingsUpdate,
    BatterySuggestionResponse,
    NightChargeAdviceResponse,
    ShadowSavingsResponse,
)
from api.services import battery_planner

router = APIRouter(prefix='/api/v1/battery', tags=['battery'], dependencies=[Depends(get_current_user)])


def _get_or_create_settings(db: Session, user_id: int) -> BatteryStrategySettings:
    row = db.query(BatteryStrategySettings).filter(BatteryStrategySettings.user_id == user_id).first()
    if row is None:
        row = BatteryStrategySettings(
            user_id=user_id,
            soc_min_percent=battery_planner.default_soc_min_for_today(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


@router.get('/settings', response_model=BatterySettingsResponse, summary='SoC min, sprawność, sezon, ceny z1/z2')
def get_settings_(current_user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)) -> BatterySettingsResponse:
    row = _get_or_create_settings(db, current_user.id)
    return BatterySettingsResponse(**battery_planner.settings_payload(row))


@router.put('/settings', response_model=BatterySettingsResponse, summary='Zapis ustawień strategii baterii')
def update_settings(
    body: BatterySettingsUpdate,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BatterySettingsResponse:
    row = _get_or_create_settings(db, current_user.id)
    # exclude_unset: zapis AC / jednego pola nie nadpisuje season defaultami modelu
    battery_planner.apply_settings_update(row, body.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(row)
    return BatterySettingsResponse(**battery_planner.settings_payload(row))


@router.get('/plan', response_model=BatteryPlanResponse, summary='Okna G12w + plan SoC 24h (reguły, bez komend do falownika)')
def get_plan(
    request: Request,
    date: str = Query(..., description='YYYY-MM-DD'),
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BatteryPlanResponse:
    settings_row = _get_or_create_settings(db, current_user.id)
    return BatteryPlanResponse(**battery_planner.build_daily_plan(date, settings_row, request=request))


@router.get('/night-charge-advice', response_model=NightChargeAdviceResponse, summary='Sugestia ładowania nocnego + uzasadnienie PL')
def night_charge_advice() -> NightChargeAdviceResponse:
    return NightChargeAdviceResponse(**battery_planner.get_night_charge_advice())


@router.get('/shadow-savings', response_model=ShadowSavingsResponse, summary='Kontrfaktyczne oszczędności (advise-only, §9.3)')
def shadow_savings(
    from_: str = Query(..., alias='from', description='YYYY-MM-DD'),
    to: str = Query(..., description='YYYY-MM-DD'),
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ShadowSavingsResponse:
    return ShadowSavingsResponse(**battery_planner.get_shadow_savings(from_, to, db=db, user_id=current_user.id))


@router.get('/policy', response_model=BatteryPolicyResponse, summary='Treść polityki advise-only (§9.6) — automation_enabled=false')
def policy() -> BatteryPolicyResponse:
    return BatteryPolicyResponse(**battery_planner.get_battery_policy())


@router.get(
    '/suggestion',
    response_model=BatterySuggestionResponse,
    summary='Sugestia Home: reżim / ForceCharge / rezerwa SoC (advise-only, BAT.3+BAT.5)',
)
def suggestion(
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BatterySuggestionResponse:
    settings_row = _get_or_create_settings(db, current_user.id)
    payload = battery_planner.get_home_suggestion(
        settings_row, db=db, user_id=current_user.id
    )
    return BatterySuggestionResponse(**payload)


@router.get(
    '/ac-runtime',
    response_model=AcRuntimeResponse,
    summary='Godzina wyłączenia AC vs rezerwa do rana (T4.5; karta gdy kalendarz = klimatyzacja)',
)
def get_ac_runtime(
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AcRuntimeResponse:
    settings_row = _get_or_create_settings(db, current_user.id)
    ac_power = battery_planner.resolve_ac_power_kw(settings_row)
    ac_day = battery_planner.today_is_ac_day(db, current_user.id)
    return AcRuntimeResponse(
        **battery_planner.calculate_ac_runtime(ac_power, settings_row, ac_day=ac_day)
    )


@router.post('/ac-runtime', response_model=AcRuntimeResponse, summary='Formuła czasu klimatyzacji (§10.4 / T4.5).')
def ac_runtime(
    body: AcRuntimeRequest,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AcRuntimeResponse:
    settings_row = _get_or_create_settings(db, current_user.id)
    ac_power = battery_planner.resolve_ac_power_kw(settings_row, body.ac_power_kw)
    ac_day = battery_planner.today_is_ac_day(db, current_user.id)
    return AcRuntimeResponse(
        **battery_planner.calculate_ac_runtime(ac_power, settings_row, ac_day=ac_day)
    )


def _control_limit() -> int:
    raw = os.getenv('BATTERY_CONTROL_API_MAX_PER_HOUR', '6').strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 6


def _control_rate_limited(db: Session, user_id: int) -> bool:
    since = datetime.utcnow() - timedelta(hours=1)
    n = (
        db.query(BatteryControlAudit)
        .filter(
            BatteryControlAudit.user_id == user_id,
            BatteryControlAudit.created_at >= since,
        )
        .count()
    )
    return n >= _control_limit()


def _record_control(db: Session, user_id: int, action: str, allowed: bool, detail: str) -> None:
    db.add(
        BatteryControlAudit(
            user_id=user_id,
            action=action,
            allowed=allowed,
            detail=detail[:2000],
        )
    )
    db.commit()


def _evening_preview():
    from src.optimization.battery_advisor import advise
    from src.optimization.battery_control import build_plan

    advice = advise('evening')
    plan = build_plan(advice)
    return advice, plan


def _control_payload(plan, *, action: str, allowed: bool, detail: str) -> dict:
    notes = list(getattr(plan, 'notes', None) or [])
    return {
        'action': action,
        'allowed': allowed,
        'dry_run': action != 'apply' or not allowed,
        'detail': detail,
        'recommendation': getattr(plan, 'recommendation', '') or '',
        'notes': [str(n) for n in notes],
    }


def _battery_control_response_model():
    from api.schemas.battery import BatteryControlResponse
    return BatteryControlResponse


@router.post('/control/dry-run', response_model=_battery_control_response_model(), summary='Plan wieczorny B2 bez wysyłki do Fox')
def control_dry_run(
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BatteryControlResponse:
    from api.schemas.battery import BatteryControlResponse as ControlResponse

    if _control_rate_limited(db, current_user.id):
        raise HTTPException(status_code=429, detail=f'Limit {_control_limit()} żądań sterowania na godzinę.')
    try:
        _advice, plan = _evening_preview()
    except Exception as exc:
        detail = f'Podgląd niedostępny: {exc}'
        _record_control(db, current_user.id, 'dry_run', False, detail)
        return ControlResponse(action='dry_run', allowed=False, dry_run=True, detail=detail)
    detail = 'Dry-run: bez odczytu i bez zapisu Fox.'
    _record_control(db, current_user.id, 'dry_run', True, detail)
    return ControlResponse(**_control_payload(plan, action='dry_run', allowed=True, detail=detail))


@router.post('/control/apply', response_model=_battery_control_response_model(), summary='Wyślij plan wieczorny B2 do Fox')
def control_apply(
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BatteryControlResponse:
    from api.schemas.battery import BatteryControlResponse as ControlResponse
    from src.optimization.battery_control import control_enabled, plan_and_run

    if _control_rate_limited(db, current_user.id):
        raise HTTPException(status_code=429, detail=f'Limit {_control_limit()} żądań sterowania na godzinę.')
    row = _get_or_create_settings(db, current_user.id)
    if not bool(getattr(row, 'battery_automation_enabled', False)):
        detail = 'Automatyka nocna jest wyłączona w ustawieniach.'
        _record_control(db, current_user.id, 'apply', False, detail)
        return ControlResponse(action='apply', allowed=False, dry_run=True, detail=detail)
    if not control_enabled():
        detail = 'BATTERY_CONTROL_ENABLED=0 — host nie wysyła komend do Fox.'
        _record_control(db, current_user.id, 'apply', False, detail)
        return ControlResponse(action='apply', allowed=False, dry_run=True, detail=detail)
    try:
        _advice, plan, results = plan_and_run(
            'evening', dry_run=False, read_state=False, phase='apply'
        )
    except Exception as exc:
        detail = f'Apply nie doszło do Fox: {exc}'
        _record_control(db, current_user.id, 'apply', False, detail)
        return ControlResponse(action='apply', allowed=False, dry_run=True, detail=detail)
    blocked = next((n for n in (plan.notes or []) if str(n).startswith('⛔')), None)
    if blocked:
        detail = str(blocked)
        _record_control(db, current_user.id, 'apply', False, detail)
        return ControlResponse(**_control_payload(plan, action='apply', allowed=False, detail=detail))
    applied = [r for r in results if r.get('action') != 'noop' and not r.get('dry_run')]
    if not applied:
        detail = 'Brak akcji do wysłania (POMIŃ lub noop).'
        _record_control(db, current_user.id, 'apply', False, detail)
        return ControlResponse(**_control_payload(plan, action='apply', allowed=False, detail=detail))
    detail = f'Wysłano {len(applied)} akcji do Fox.'
    _record_control(db, current_user.id, 'apply', True, detail)
    return ControlResponse(**_control_payload(plan, action='apply', allowed=True, detail=detail))

# POST /control/dry-run nie woła Fox. POST /control/apply wymaga flagi użytkownika i BATTERY_CONTROL_ENABLED=1.
# Limit: BATTERY_CONTROL_API_MAX_PER_HOUR (domyślnie 6).
