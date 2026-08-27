"""Schematy dla Modułu 3 — Optymalizator baterii (advise-only, §9.6)."""

from __future__ import annotations

from pydantic import BaseModel


class BatterySettingsResponse(BaseModel):
    soc_min_percent: float
    soc_reserve_percent: float
    soc_target_percent: float
    efficiency_pct: float
    price_zone1: float | None = None
    price_zone2: float | None = None
    season: str
    season_resolved: str
    battery_capacity_kwh: float | None = None
    ac_power_kw: float | None = None


class BatterySettingsUpdate(BaseModel):
    soc_min_percent: float = 20.0
    soc_target_percent: float = 80.0
    efficiency_pct: float = 90.0
    price_zone1: float | None = None
    price_zone2: float | None = None
    season: str = 'auto'
    battery_capacity_kwh: float | None = None
    ac_power_kw: float | None = None


class BatteryPlanHour(BaseModel):
    hour: int
    zone: int
    zone_label: str
    force_charge_recommended: bool
    planned_soc_percent: float | None = None


class BatteryPlanResponse(BaseModel):
    date: str
    season: str
    hours: list[BatteryPlanHour]
    note: str = 'Plan doradczy — brak wysyłki komend do falownika (§9.6 advise-only).'


class NightChargeAdviceResponse(BaseModel):
    as_of: str
    context: str
    recommendation: str
    action: str
    details: list[str]
    note: str = 'Sugestia — nie wykonano automatycznie (advise-only).'


class ShadowSavingsResponse(BaseModel):
    period_from: str
    period_to: str
    shadow_savings_pln: float
    baseline_cost_pln: float
    actual_cost_pln: float
    method_note: str = (
        'MVP: przybliżenie — oszczędność autokonsumpcji (bez PV vs z PV/baterią) w okresie; '
        'pełna symulacja "plan doradczy vs rzeczywisty przebieg SoC" to Faza 4 (T4.15/T4.17).'
    )
    is_hypothetical: bool = True


class BatteryPolicyResponse(BaseModel):
    title: str
    body: str
    automation_enabled: bool = False
    reasons: list[str]


class BatterySuggestionResponse(BaseModel):
    """Karta Home: reżim / ForceCharge / rezerwa SoC — advise-only (BAT.3 + BAT.5)."""

    as_of: str
    season: str
    season_mode: str
    soc_now_percent: float | None
    soc_min_percent: float
    soc_reserve_percent: float
    soc_target_percent: float
    soc_min_evening_percent: float
    force_charge_night_recommended: bool
    force_charge_night_label: str
    force_charge_afternoon_recommended: bool
    force_charge_afternoon_label: str
    soc16_alert: bool
    soc16_hour_passed: bool
    soc16_percent: float | None = None
    soc16_title: str | None = None
    soc16_body: str | None = None
    recommendation: str
    action: str
    automation_enabled: bool = False
    note: str = 'Sugestia — nie wykonano automatycznie (advise-only).'


class AcRuntimeRequest(BaseModel):
    ac_power_kw: float


class AcRuntimeResponse(BaseModel):
    hours_safe: float
    soc_now_percent: float | None
    soc_min_morning_percent: float
    battery_capacity_kwh: float
    efficiency_pct: float
    note: str
