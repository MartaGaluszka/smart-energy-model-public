"""Adapter FastAPI -> src/optimization/g12w_tariff.py, battery_advisor.py (§9 Moduł 3).

BEZPIECZEŃSTWO PRODUKTOWE (§9.6, §14): ten moduł jest wyłącznie DORADCZY.
Nie importuje ani nie woła `src/data/foxess_control.py` / `mlops/foxess_control.py`.
Żadna funkcja tutaj nie wysyła komend do falownika — patrz też brak routera
`POST /battery/control` (celowo, `api/routers/battery.py`).
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from api.config import get_settings

# Stary fabryczny default UI (20%) — BAT.5: przy season=auto i tak bierzemy rezerwę sezonową.
_FACTORY_SOC_MIN = 20.0

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


def _fc_on_off_label(
    *,
    minutes: float | None,
    target_soc: float | None,
    soc_now: float | None,
    start_hour: int = 22,
    start_minute: int = 0,
) -> str:
    """Etykieta okna ForceCharge: włącz → wyłącz (30 min ≈ +50 pp), nie „ładuj do X% w Y min”."""
    if minutes is None or minutes <= 0:
        return 'włącz 22:00 (sprawdź czas)'
    end = (datetime.combine(date.today(), time(start_hour, start_minute)) + timedelta(minutes=round(minutes)))
    end_s = end.strftime('%H:%M')
    start_s = f'{start_hour:02d}:{start_minute:02d}'
    delta = None
    if soc_now is not None and target_soc is not None:
        delta = max(0.0, target_soc - soc_now)
    if delta is not None and target_soc is not None:
        return f'włącz {start_s}, wyłącz {end_s} (~+{delta:.0f} pp → ~{target_soc:.0f}%)'
    if target_soc is not None:
        return f'włącz {start_s}, wyłącz {end_s} (cel ~{target_soc:.0f}%)'
    return f'włącz {start_s}, wyłącz {end_s} (~{minutes:.0f} min; 30 min ≈ +50 pp)'


def get_battery_policy() -> dict:
    return {
        'title': BATTERY_POLICY_TITLE,
        'body': BATTERY_POLICY_BODY,
        'automation_enabled': False,
        'reasons': BATTERY_POLICY_REASONS,
    }


def resolve_season_name(season_mode: str | None, d: date | None = None) -> str:
    """`auto` → zima X–III / lato (B1 jesień jeszcze nie)."""
    from src.optimization.battery_advisor import is_winter_season

    mode = (season_mode or 'auto').strip().lower()
    if mode in ('winter', 'summer'):
        return mode
    return 'winter' if is_winter_season(d or date.today()) else 'summer'


def seasonal_reserve_for(season: str, d: date | None = None) -> float:
    from src.optimization.battery_advisor import seasonal_soc_reserve

    return seasonal_soc_reserve(d or date.today(), season=season)


def effective_soc_min(settings_row, d: date | None = None) -> float:
    """BAT.5: przy season=auto (lub braku wiersza) soc_min = rezerwa sezonowa, nie 20%."""
    d = d or date.today()
    mode = (getattr(settings_row, 'season', None) or 'auto') if settings_row else 'auto'
    resolved = resolve_season_name(mode, d)
    reserve = seasonal_reserve_for(resolved, d)
    if settings_row is None or mode == 'auto':
        return reserve
    stored = float(settings_row.soc_min_percent)
    if abs(stored - _FACTORY_SOC_MIN) < 0.01:
        return reserve
    return stored


def default_soc_min_for_today() -> float:
    return effective_soc_min(None, date.today())


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
    season_mode = getattr(settings_row, 'season', None) if settings_row else 'auto'
    season = resolve_season_name(season_mode, d)

    soc_min = effective_soc_min(settings_row, d)
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

    soc_min_morning = effective_soc_min(settings_row)
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


def settings_payload(settings_row, d: date | None = None) -> dict:
    """GET/PUT /settings — soc_min_percent to wartość efektywna (BAT.5)."""
    d = d or date.today()
    season_mode = settings_row.season if settings_row else 'auto'
    resolved = resolve_season_name(season_mode, d)
    return {
        'soc_min_percent': effective_soc_min(settings_row, d),
        'soc_reserve_percent': seasonal_reserve_for(resolved, d),
        'soc_target_percent': settings_row.soc_target_percent,
        'efficiency_pct': settings_row.efficiency_pct,
        'price_zone1': settings_row.price_zone1,
        'price_zone2': settings_row.price_zone2,
        'season': season_mode,
        'season_resolved': resolved,
        'battery_capacity_kwh': settings_row.battery_capacity_kwh,
        'ac_power_kw': settings_row.ac_power_kw,
    }


def fallback_home_suggestion(settings_row=None, as_of: datetime | None = None) -> dict:
    """Karta Home gdy SQLite/Fox blokuje odczyt — i tak pokaż reżim (lato/zima)."""
    as_of = as_of or datetime.now()
    d = as_of.date()
    season_mode = getattr(settings_row, 'season', None) if settings_row else 'auto'
    season = resolve_season_name(season_mode, d)
    reserve = seasonal_reserve_for(season, d)
    target = float(settings_row.soc_target_percent) if settings_row and settings_row.soc_target_percent else 80.0
    winter = season == 'winter'
    if winter:
        rec, night, aft = 'REŻIM ZIMA', 'wg T+PV (22–6)', 'włącz (13–15)'
        action = (
            f'Rezerwa SoC {reserve:.0f}% — nie ładuj w drogiej G12w. '
            f'ForceCharge 22–6 wg T jutro + PV. System tylko doradza — bez automatyki.'
        )
    else:
        rec, night, aft = 'REŻIM LATO', 'pomiń — wystarczy PV', 'rzadko potrzebne'
        action = (
            f'Trzymaj min {reserve:.0f}% na noc (rezerwa). Ładowanie z sieci tylko gdy bateria spada poniżej 20% i jutro słabe PV. '
            f'System tylko doradza — bez automatyki.'
        )
    return {
        'as_of': as_of.isoformat(timespec='seconds'),
        'season': season,
        'season_mode': season_mode or 'auto',
        'soc_now_percent': None,
        'soc_min_percent': reserve,
        'soc_reserve_percent': reserve,
        'soc_target_percent': target,
        'soc_min_evening_percent': 50.0,
        'force_charge_night_recommended': False,
        'force_charge_night_label': night,
        'force_charge_afternoon_recommended': winter,
        'force_charge_afternoon_label': aft,
        'soc16_alert': False,
        'soc16_hour_passed': as_of.hour >= 16,
        'soc16_percent': None,
        'soc16_title': None,
        'soc16_body': None,
        'wait_for_cheap': False,
        'next_cheap_window': None,
        'recommendation': rec,
        'action': action,
        'automation_enabled': False,
        'note': 'Sugestia — nie wykonano automatycznie (advise-only).',
    }


def get_home_suggestion(settings_row, as_of: datetime | None = None) -> dict:
    as_of = as_of or datetime.now()
    try:
        return _compose_home_suggestion(settings_row, as_of)
    except Exception:
        return fallback_home_suggestion(settings_row, as_of)


def _compose_home_suggestion(settings_row, as_of: datetime) -> dict:
    """Karta Home (BAT.3 + BAT.5): reżim / ForceCharge / rezerwa — bez ML, bez auto-apply."""
    from src.optimization.battery_advisor import (
        evaluate_below_reserve_wait_cheap,
        evaluate_charge_tonight_cloudy,
        evaluate_soc16_hold_reserve,
        get_archived_day_pv_kwh,
        get_battery_snapshot,
        get_day_mean_temp_c,
        get_soc_at_hour,
        seasonal_soc_reserve,
    )
    from src.optimization.g12w_tariff import is_public_holiday, is_weekend

    d = as_of.date()
    season_mode = getattr(settings_row, 'season', None) if settings_row else 'auto'
    season = resolve_season_name(season_mode, d)
    reserve = seasonal_soc_reserve(d, season=season)
    soc_min = effective_soc_min(settings_row, d)
    target = float(settings_row.soc_target_percent) if settings_row else 80.0
    snap = get_battery_snapshot(target_day=d.isoformat())
    soc_now = snap.soc_percent

    soc16_sample = get_soc_at_hour(d.isoformat(), 16)
    if as_of.hour >= 16:
        soc_for_alert = soc16_sample if soc16_sample is not None else soc_now
    else:
        soc_for_alert = soc_now
    alert = evaluate_soc16_hold_reserve(
        soc_percent=soc_for_alert,
        as_of=as_of,
        reserve_percent=reserve,
    )
    wait_cheap = evaluate_below_reserve_wait_cheap(
        soc_percent=soc_now,
        as_of=as_of,
        reserve_percent=reserve,
    )

    tomorrow_s = (d + timedelta(days=1)).isoformat()
    night_rule = evaluate_charge_tonight_cloudy(
        soc_percent=soc_now,
        tomorrow_pv_kwh=get_archived_day_pv_kwh(tomorrow_s),
        as_of=as_of,
        tomorrow_temp_c=get_day_mean_temp_c(tomorrow_s),
        capacity_kwh=(
            settings_row.battery_capacity_kwh if settings_row and settings_row.battery_capacity_kwh else None
        ),
    )

    weekend = is_weekend(d) or is_public_holiday(d)
    winter = season == 'winter'
    if weekend:
        night_rec, night_label = False, 'weekend — cała doba tanio'
        aft_rec, aft_label = False, 'niekrytyczne (weekend)'
    elif night_rule.triggered:
        mins = night_rule.fc_minutes
        tgt = night_rule.target_soc_percent
        night_rec = True
        night_label = _fc_on_off_label(
            minutes=mins,
            target_soc=tgt,
            soc_now=soc_now,
        )
        if soc_now is not None and soc_now >= target:
            aft_rec, aft_label = False, 'pomiń (SoC ≥ cel)'
        elif winter:
            aft_rec, aft_label = True, 'włącz (13–15)'
        else:
            aft_rec, aft_label = False, 'rzadko potrzebne'
    elif night_rule.skip_reason == 'wear':
        night_rec, night_label = False, 'pomiń (niewiele brakuje vs zużycie baterii)'
        aft_rec, aft_label = (False, 'rzadko potrzebne') if not winter else (
            soc_now is None or soc_now < target,
            'włącz (13–15)' if (soc_now is None or soc_now < target) else 'pomiń (SoC ≥ cel)',
        )
    elif night_rule.skip_reason in ('covered', 'full'):
        night_rec, night_label = False, 'nie (dach pokryje szczyt)' if night_rule.skip_reason == 'covered' else 'nie (SoC ≥ cel)'
        if soc_now is not None and soc_now >= target:
            aft_rec, aft_label = False, 'pomiń (SoC ≥ cel)'
        elif winter:
            aft_rec, aft_label = True, 'włącz (13–15)'
        else:
            aft_rec, aft_label = False, 'rzadko potrzebne'
    elif winter:
        night_rec, night_label = False, 'sprawdź T+PV (brak prognozy)'
        if soc_now is not None and soc_now >= target:
            aft_rec, aft_label = False, 'pomiń (SoC ≥ cel)'
        else:
            aft_rec, aft_label = True, 'włącz (13–15)'
    else:
        night_rec, night_label = False, 'pomiń — wystarczy PV'
        aft_rec, aft_label = False, 'rzadko potrzebne'

    if wait_cheap.triggered:
        rec, action = wait_cheap.recommendation, wait_cheap.body
    elif alert.triggered:
        rec, action = alert.recommendation, alert.body
    elif night_rule.triggered:
        rec, action = night_rule.recommendation, night_rule.body
    elif night_rule.skip_reason == 'wear':
        rec = 'POMIŃ FC (CYKL)'
        action = (
            'Niewiele brakuje do celu — spread G12w nie pokrywa zużycia cyklu LFP. '
            'Zostaw rezerwę, ewentualnie 13–15. System tylko doradza — bez automatyki.'
        )
    elif winter:
        rec = 'REŻIM ZIMA'
        action = (
            f'Rezerwa SoC {reserve:.0f}% to podłoga na noc po tanim oknie G12w — '
            f'nie ładuj z sieci w drogiej taryfie (6–13 i 15–22). '
            f'ForceCharge 22–6 wg T jutro + PV jutro (B2), nie zawsze do 100%. '
            f'System tylko doradza — bez automatyki.'
        )
    else:
        rec = 'REŻIM LATO'
        action = (
            f'Rezerwa SoC {reserve:.0f}% wystarcza na noc — także gdy jutro PV do 10 kWh. '
            f'Nie pełnić do 75%. Krótki FC (max 15 min / +25 pp; 30 min ≈ +50 pp) tylko gdy SoC < 20% i jutro ≤ 10 kWh. '
            f'System tylko doradza — bez automatyki.'
        )

    return {
        'as_of': as_of.isoformat(timespec='seconds'),
        'season': season,
        'season_mode': season_mode or 'auto',
        'soc_now_percent': soc_now,
        'soc_min_percent': soc_min,
        'soc_reserve_percent': reserve,
        'soc_target_percent': target,
        'soc_min_evening_percent': alert.min_evening_percent,
        'force_charge_night_recommended': night_rec,
        'force_charge_night_label': night_label,
        'force_charge_afternoon_recommended': aft_rec,
        'force_charge_afternoon_label': aft_label,
        'soc16_alert': alert.triggered,
        'soc16_hour_passed': alert.hour_passed,
        'soc16_percent': soc16_sample,
        'soc16_title': alert.title or None,
        'soc16_body': alert.body or None,
        'wait_for_cheap': wait_cheap.triggered,
        'next_cheap_window': wait_cheap.next_cheap_window,
        'recommendation': rec,
        'action': action,
        'automation_enabled': False,
        'note': 'Sugestia — nie wykonano automatycznie (advise-only).',
    }
