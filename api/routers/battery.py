"""Bateria — advise-only (TA.8, §9.6). CELOWO brak POST /battery/control (§9.6, §14)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from api.deps import get_current_user, get_db
from api.models import AppUser, BatteryStrategySettings
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
    battery_planner.apply_settings_update(row, body.model_dump())
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
) -> ShadowSavingsResponse:
    return ShadowSavingsResponse(**battery_planner.get_shadow_savings(from_, to))


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
    payload = battery_planner.get_home_suggestion(settings_row)
    return BatterySuggestionResponse(**payload)


@router.post('/ac-runtime', response_model=AcRuntimeResponse, summary='Formuła czasu bezpiecznej pracy klimatyzacji (§10.4)')
def ac_runtime(
    body: AcRuntimeRequest,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AcRuntimeResponse:
    settings_row = _get_or_create_settings(db, current_user.id)
    return AcRuntimeResponse(**battery_planner.calculate_ac_runtime(body.ac_power_kw, settings_row))

# Celowo NIE ISTNIEJE: POST /api/v1/battery/control — patrz §9.6 / §14 PROJEKT_APLIKACJA_MOBILNA.md
# ("Celowo nie istnieje w MVP"). Nie dodawaj tego endpointu bez osobnej decyzji produktowej (T6.*).
