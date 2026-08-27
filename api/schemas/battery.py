"""Schematy dla Modułu 3 — Optymalizator baterii (advise-only, §9.6)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


ScheduleMode = Literal['ForceCharge', 'SelfUse', 'ForceDischarge']


class BatteryScheduleWindow(BaseModel):
    """Blok planu dnia Smart Energy (G12w + sezon) — max 8; mapowanie na falownik osobno."""

    start: str = Field(..., description='HH:MM')
    end: str = Field(..., description='HH:MM (może przejść przez północ)')
    mode: ScheduleMode = 'SelfUse'
    # Opt-in w UI: bloki startują wyłączone, użytkownik włącza świadomie
    enabled: bool = False


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
    fc_max_minutes: float = 15.0
    fc_night_start_hour: int = 22
    recommended_fc_max_minutes: float = 15.0
    schedule_windows: list[BatteryScheduleWindow] = Field(default_factory=list)
    schedule_max_windows: int = 8
    schedule_preset: str = 'g12w'


class BatterySettingsUpdate(BaseModel):
    soc_min_percent: float = 20.0
    soc_target_percent: float = 80.0
    efficiency_pct: float = 93.0
    price_zone1: float | None = None
    price_zone2: float | None = None
    season: str = 'auto'
    battery_capacity_kwh: float | None = None
    ac_power_kw: float | None = None
    fc_max_minutes: float = 15.0
    fc_night_start_hour: int = 22
    schedule_windows: list[BatteryScheduleWindow] = Field(default_factory=list)
    schedule_preset: str = 'g12w'

class BatteryPlanHour(BaseModel):
    hour: int
    zone: int
    zone_label: str
    force_charge_recommended: bool
    planned_soc_percent: float | None = None
    mode: str = 'Auto'  # 'ForceCharge', 'Auto', 'Discharge'
    note: str = ''  # Krótki opis co się dzieje (np. "Ładowanie z PV")


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
    shadow_savings_pln: float  # brutto (z VAT 23%)
    baseline_cost_pln: float  # brutto (z VAT 23%)
    actual_cost_pln: float  # brutto (z VAT 23%)
    method_note: str = (
        'Kwoty brutto (z VAT 23%). Oszczędność = koszt bez PV minus koszt z PV/baterią. '
        'MVP: przybliżenie autokonsumpcji; pełna symulacja SoC godzina po godzinie to Faza 4.'
    )
    is_hypothetical: bool = False


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
    force_charge_night_start: str | None = None
    force_charge_night_end: str | None = None
    force_charge_night_minutes: float | None = None
    force_charge_afternoon_window: str | None = None
    charge_when_summary: str = 'Dziś bez doładowania z sieci — wystarczy PV / rezerwa SE'
    fc_max_minutes: float = 15.0
    fc_night_start_hour: int = 22
    soc16_alert: bool
    soc16_hour_passed: bool
    soc16_percent: float | None = None
    soc16_title: str | None = None
    soc16_body: str | None = None
    wait_for_cheap: bool = False
    next_cheap_window: str | None = None
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
