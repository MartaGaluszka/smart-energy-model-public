"""Adapter FastAPI -> src/optimization/g12w_tariff.py, battery_advisor.py (§9 Moduł 3).

BEZPIECZEŃSTWO PRODUKTOWE (§9.6, §14): ten moduł jest wyłącznie DORADCZY.
Nie importuje ani nie woła `src/data/foxess_control.py` / `mlops/foxess_control.py`.
Żadna funkcja tutaj nie wysyła komend do falownika — patrz też brak routera
`POST /battery/control` (celowo, `api/routers/battery.py`).
"""

from __future__ import annotations

from datetime import date, datetime, time

from api.config import get_settings

BATTERY_POLICY_TITLE = 'System tylko doradza — automatyka wyłączona (MVP)'

BATTERY_POLICY_BODY = (
    'Mój system na razie tylko doradza i wyświetla powiadomienia na dashboardzie. '
    'Pokazuje, ile BYŚMY zaoszczędzili, gdybyśmy włączyli automatykę. Dopiero gdy po roku '
    'testów upewnię się, że algorytm się nie myli, udostępnię przycisk do fizycznego '
    'sterowania falownikiem.'
)

BATTERY_POLICY_REASONS = [
    'Ryzyko kosztowe przy błędzie algorytmu (ładowanie w droższej strefie, zbędny import).',
    'Limit i niestabilność API FoxESS; brak dojrzałego OAuth sterowania w produkcie.',
    'Konieczność zebrania sezonu zimowego i letniego pod walidację shadow vs reality.',
    'Odpowiedzialność użytkownika / bezpieczeństwo instalacji (opt-in dopiero po dowodach).',
]


def get_battery_policy() -> dict:
    return {
        'title': BATTERY_POLICY_TITLE,
        'body': BATTERY_POLICY_BODY,
        'automation_enabled': False,
        'reasons': BATTERY_POLICY_REASONS,
    }


def _zone_label(zone: int) -> str:
    from src.optimization.g12w_tariff import cheap_zone_label

    return cheap_zone_label(zone)  # type: ignore[arg-type]


def build_daily_plan(target_date: str, settings_row) -> dict:
    """Plan 24h: strefy G12w + prosta symulacja SoC (reguły, bez ML/komend do falownika).

    Symulacja jest celowo prosta (liniowy ramp w oknach taniej strefy, spadek w
    szczycie) — wystarcza do wizualizacji "kiedy warto ładować", zgodnie z DoD
    T4.1 ("bez wywołań foxess_control"). Dokładniejszy model (PV forecast +
    rzeczywiste zużycie godzinowe) to rozszerzenie v2 (§9.3 dokumentu produktowego).
    """
    from src.optimization.g12w_tariff import classify_zone, is_public_holiday, is_weekend

    d = date.fromisoformat(target_date)
    from src.optimization.battery_advisor import is_winter_season

    season = 'winter' if is_winter_season(d) else 'summer'

    soc_min = settings_row.soc_min_percent if settings_row else 20.0
    soc_target = settings_row.soc_target_percent if settings_row else 80.0

    all_day_cheap = is_weekend(d) or is_public_holiday(d)
    hours = []
    soc = soc_min
    charge_step = max(1.0, (soc_target - soc_min) / 8.0)
    discharge_step = max(1.0, (soc_target - soc_min) / 7.0)

    for hour in range(24):
        dt = datetime.combine(d, time(hour, 0))
        zone = classify_zone(dt)
        cheap = all_day_cheap or zone == 2
        force_charge = cheap and soc < soc_target

        if force_charge:
            soc = min(soc_target, soc + charge_step)
        elif zone == 1:
            soc = max(soc_min, soc - discharge_step)

        hours.append(
            {
                'hour': hour,
                'zone': zone,
                'zone_label': _zone_label(zone),
                'force_charge_recommended': bool(force_charge),
                'planned_soc_percent': round(soc, 1),
            }
        )

    return {'date': target_date, 'season': season, 'hours': hours}


def _pick_context(as_of: datetime) -> str:
    if as_of.hour < 12:
        return 'morning'
    if as_of.hour < 15:
        return 'pre_cheap'
    return 'peak'


def get_night_charge_advice() -> dict:
    from src.optimization.battery_advisor import advise

    as_of = datetime.now()
    context = _pick_context(as_of)
    advice = advise(context, as_of=as_of)  # type: ignore[arg-type]

    return {
        'as_of': as_of.isoformat(timespec='seconds'),
        'context': advice.context,
        'recommendation': advice.recommendation,
        'action': advice.action,
        'details': advice.details,
    }


def get_shadow_savings(period_from: str, period_to: str) -> dict:
    """MVP: przybliżenie shadow_savings_pln (patrz dokstring w schemas/battery.py).

    Pełna kontrfaktyczna symulacja "co gdyby wykonano plan doradczy godzina po
    godzinie" wymaga replayu SoC na historycznych danych — poza budżetem czasowym
    tej fazy (Faza 0). Odsyła do T4.15/T4.17 (Faza 4) jako follow-up.
    """
    from src.financial.roi_calculator import FinancialAnalyzer

    settings = get_settings()
    analyzer = FinancialAnalyzer(db_path=settings.DATABASE_PATH)
    try:
        roi_data = analyzer.calculate_roi(period_from, period_to, use_forecast_baseline=False)
    finally:
        analyzer.close()

    return {
        'period_from': period_from,
        'period_to': period_to,
        'shadow_savings_pln': roi_data['savings_pln'],
        'baseline_cost_pln': roi_data['baseline_cost_pln'],
        'actual_cost_pln': roi_data['actual_cost_pln'],
    }


def calculate_ac_runtime(ac_power_kw: float, settings_row) -> dict:
    """§10.4: energia_dostępna = (SoC_now - SoC_min_morning)/100 * pojemność * sprawność."""
    from src.optimization.battery_advisor import get_battery_snapshot

    snap = get_battery_snapshot()
    soc_now = snap.soc_percent

    soc_min_morning = settings_row.soc_min_percent if settings_row else 20.0
    capacity_kwh = (settings_row.battery_capacity_kwh if settings_row and settings_row.battery_capacity_kwh else None) or 10.36
    efficiency = (settings_row.efficiency_pct if settings_row else 90.0) / 100.0

    if soc_now is None:
        hours_safe = 0.0
        note = 'Brak świeżego odczytu SoC z FoxESS — zwrócono 0h (bezpieczny fallback).'
    else:
        available_kwh = max(0.0, (soc_now - soc_min_morning) / 100.0 * capacity_kwh * efficiency)
        hours_safe = round(available_kwh / ac_power_kw, 2) if ac_power_kw > 0 else 0.0
        note = f'Bezpiecznie możesz odpalić klimatyzację ~{hours_safe:.1f} h bez dokupowania w szczycie.'

    return {
        'hours_safe': hours_safe,
        'soc_now_percent': soc_now,
        'soc_min_morning_percent': soc_min_morning,
        'battery_capacity_kwh': capacity_kwh,
        'efficiency_pct': efficiency * 100,
        'note': note,
    }
