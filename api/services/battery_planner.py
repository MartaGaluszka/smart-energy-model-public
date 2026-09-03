"""Adapter FastAPI -> src/optimization/g12w_tariff.py, battery_advisor.py (§9 Moduł 3).

BEZPIECZEŃSTWO PRODUKTOWE (§9.6, §14): ten moduł jest wyłącznie DORADCZY.
Nie importuje ani nie woła `src/data/foxess_control.py` / `mlops/foxess_control.py`.
Żadna funkcja tutaj nie wysyła komend do falownika — patrz też brak routera
`POST /battery/control` (celowo, `api/routers/battery.py`).
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, time, timedelta

from api.config import get_settings
from api.deps import get_db

# Stary fabryczny default UI (20%) — BAT.5: przy season=auto i tak bierzemy rezerwę sezonową.
_FACTORY_SOC_MIN = 20.0

# Limit bloków planu dnia SE — typowy limit segmentów u wielu falowników; nasz plan
# budujemy spod G12w/Tauron + reguł sezonowych, nie jako klon UI producenta.
SCHEDULE_MAX_WINDOWS = 8
SCHEDULE_MODES = frozenset({'ForceCharge', 'SelfUse', 'ForceDischarge'})

# T4.5: kalendarz włącza kartę AC; typy z §10.1 + klimatyzacja/upał.
AC_EVENT_TYPES = frozenset({'klimatyzacja', 'upal', 'upał', 'ac'})
DEFAULT_AC_POWER_KW = 1.2
# Od tej godziny PV zwykle nie pokrywa AC+dom — liczymy noc z baterii (bez GPS).
AC_BATTERY_NIGHT_START_HOUR = 18
AC_MORNING_HOUR = 6

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


def _hhmm(hour: int, minute: int = 0) -> str:
    return f'{int(hour) % 24:02d}:{int(minute) % 60:02d}'


def _parse_hhmm(value: str) -> tuple[int, int] | None:
    try:
        parts = str(value).strip().split(':')
        h, m = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
        if 0 <= h <= 23 and 0 <= m <= 59:
            return h, m
    except (TypeError, ValueError, IndexError):
        return None
    return None


def normalize_schedule_windows(raw) -> list[dict]:
    """Walidacja listy bloków planu dnia SE — max SCHEDULE_MAX_WINDOWS."""
    if not raw:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    out: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        start = item.get('start')
        end = item.get('end')
        if _parse_hhmm(str(start or '')) is None or _parse_hhmm(str(end or '')) is None:
            continue
        mode = str(item.get('mode') or 'SelfUse')
        if mode not in SCHEDULE_MODES:
            mode = 'SelfUse'
        out.append(
            {
                'start': str(start),
                'end': str(end),
                'mode': mode,
                # Domyślnie wyłączony — użytkownik włącza świadomie w UI
                'enabled': bool(item.get('enabled', False)),
            }
        )
        if len(out) >= SCHEDULE_MAX_WINDOWS:
            break
    return out


def schedule_template_for_tariff(
    tariff: str = 'g12w',
    *,
    night_start_hour: int = 22,
    night_minutes: float = 15.0,
) -> list[dict]:
    """Opcjonalny szablon startowy planu dnia SE — użytkownik i tak może dodać/usunąć bloki.

    - **G11** (płaska): zwykle 1 krótkie doładowanie.
    - **G12w** (2 strefy weekendowa): noc + szczyty + 13–15 (kilka bloków).
    - **G13** (więcej stref): gęstszy podział doby (więcej okien startowych).
    """
    start_h = int(night_start_hour) if 0 <= int(night_start_hour) <= 23 else 22
    minutes = max(5, int(round(night_minutes)))
    end_dt = datetime.combine(date.today(), time(start_h, 0)) + timedelta(minutes=minutes)
    night_end = end_dt.strftime('%H:%M')
    night_start = _hhmm(start_h, 0)
    key = (tariff or 'g12w').strip().lower().replace(' ', '')

    if key in ('g11', 'flat', 'single'):
        return normalize_schedule_windows(
            [{'start': night_start, 'end': night_end, 'mode': 'ForceCharge', 'enabled': False}]
        )

    if key in ('g13',):
        # Poranek → dzień, na końcu 2 okna taniej nocy G12w/G13: 22–01 i 04–06.
        return normalize_schedule_windows(
            [
                {'start': '06:00', 'end': '09:00', 'mode': 'SelfUse', 'enabled': False},
                {'start': '09:00', 'end': '13:00', 'mode': 'SelfUse', 'enabled': False},
                {'start': '13:00', 'end': '15:00', 'mode': 'ForceCharge', 'enabled': False},
                {'start': '15:00', 'end': '17:00', 'mode': 'SelfUse', 'enabled': False},
                {'start': '17:00', 'end': '22:00', 'mode': 'SelfUse', 'enabled': False},
                {'start': '22:00', 'end': '01:00', 'mode': 'ForceCharge', 'enabled': False},
                {'start': '04:00', 'end': '06:00', 'mode': 'ForceCharge', 'enabled': False},
            ]
        )

    # G12w — od rana; 2 ostatnie: 22:00–01:00 i 04:00–06:00 (tanie strefy).
    return normalize_schedule_windows(
        [
            {'start': '06:00', 'end': '13:00', 'mode': 'SelfUse', 'enabled': False},
            {'start': '13:00', 'end': '15:00', 'mode': 'ForceCharge', 'enabled': False},
            {'start': '15:00', 'end': '22:00', 'mode': 'SelfUse', 'enabled': False},
            {'start': '22:00', 'end': '01:00', 'mode': 'ForceCharge', 'enabled': False},
            {'start': '04:00', 'end': '06:00', 'mode': 'ForceCharge', 'enabled': False},
        ]
    )


def g12w_schedule_template(
    *,
    night_start_hour: int = 22,
    night_minutes: float = 15.0,
    afternoon_charge: bool = True,
    afternoon_end_hour: int = 14,
    multi_day: bool | None = None,
    season: str | None = None,
) -> list[dict]:
    """Kompatybilność wsteczna — preferuj ``schedule_template_for_tariff``."""
    if multi_day is False or (multi_day is None and season and season != 'winter'):
        return schedule_template_for_tariff(
            'g11', night_start_hour=night_start_hour, night_minutes=night_minutes
        )
    return schedule_template_for_tariff(
        'g12w', night_start_hour=night_start_hour, night_minutes=night_minutes
    )


def schedule_windows_from_settings(settings_row) -> list[dict]:
    raw = getattr(settings_row, 'schedule_windows_json', None) if settings_row else None
    if raw is not None and str(raw).strip() != '':
        return normalize_schedule_windows(raw)
    # Pusty stan → szablon wg wybranej taryfy (domyślnie G12w); zawsze edytowalny potem.
    preset = getattr(settings_row, 'schedule_preset', None) if settings_row else None
    preset = (preset or 'g12w').strip().lower()
    season_mode = getattr(settings_row, 'season', None) if settings_row else 'auto'
    resolved = resolve_season_name(season_mode, date.today())
    return schedule_template_for_tariff(
        preset,
        night_start_hour=_settings_night_start(settings_row),
        night_minutes=effective_fc_max(settings_row, resolved),
    )


def apply_settings_update(row, body_dump: dict) -> None:
    """Mapuje PUT body → ORM. Tylko pola obecne w dumpie (partial OK, np. sam ac_power_kw)."""
    body = dict(body_dump)
    if 'schedule_windows' in body:
        windows = normalize_schedule_windows(body.pop('schedule_windows'))
        row.schedule_windows_json = json.dumps(windows, ensure_ascii=False)
    preset = body.pop('schedule_preset', None)
    for field, value in body.items():
        if hasattr(row, field):
            setattr(row, field, value)
    if preset is not None and hasattr(row, 'schedule_preset'):
        p = str(preset).strip().lower()
        row.schedule_preset = p if p in ('g11', 'g12w', 'g13', 'custom') else 'custom'


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
        return f'włącz {start_hour:02d}:00 (sprawdź czas)'
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


def recommended_fc_max_minutes_for(season: str) -> float:
    """Zalecany max czas FC wg sezonu — lato/wiosna krótko (nie pełnić)."""
    if season == 'winter':
        return 90.0
    if season == 'autumn':
        return 45.0
    return 15.0  # summer / spring


def _settings_fc_max(settings_row) -> float:
    if settings_row is None:
        return 15.0
    val = getattr(settings_row, 'fc_max_minutes', None)
    if val is None:
        return 15.0
    return float(val)


_FACTORY_FC_MAX = 15.0


def effective_fc_max(settings_row, season: str) -> float:
    """Przy Auto + fabryczne 15 min bierz zalecenie sezonu (zima 90 / jesień 45)."""
    rec = recommended_fc_max_minutes_for(season)
    if settings_row is None:
        return rec
    stored = _settings_fc_max(settings_row)
    mode = (getattr(settings_row, 'season', None) or 'auto').strip().lower()
    if mode == 'auto' and abs(stored - _FACTORY_FC_MAX) < 0.01:
        return rec
    return stored


def _settings_night_start(settings_row) -> int:
    if settings_row is None:
        return 22
    val = getattr(settings_row, 'fc_night_start_hour', None)
    if val is None:
        return 22
    h = int(val)
    return h if 0 <= h <= 23 else 22


def _charge_window_bits(
    *,
    night_rec: bool,
    night_rule,
    aft_rec: bool,
    start_hour: int,
) -> dict:
    """Strukturalne pola planu SE (G12w + sezon) na Home / ekran Bateria."""
    night_start = night_end = None
    night_minutes = None
    aft_window = '13:00–15:00' if aft_rec else None
    if night_rec and night_rule is not None and night_rule.fc_minutes:
        minutes = float(night_rule.fc_minutes)
        night_minutes = minutes
        night_start = f'{start_hour:02d}:00'
        end = datetime.combine(date.today(), time(start_hour, 0)) + timedelta(minutes=round(minutes))
        night_end = end.strftime('%H:%M')
        delta = round(minutes * 50.0 / 30.0)
        summary = (
            f'Sugestia SE: doładuj {night_start}–{night_end} '
            f'(~{minutes:.0f} min ≈ +{delta:.0f}% SoC; 30 min ≈ +50%)'
        )
        if aft_rec:
            summary += '; popołudnie też 13:00–15:00 (tania G12w)'
    elif aft_rec:
        summary = 'Sugestia SE: doładuj 13:00–15:00 (tania G12w)'
    else:
        summary = 'Dziś bez doładowania z sieci — wystarczy PV / rezerwa SE'
    return {
        'force_charge_night_start': night_start,
        'force_charge_night_end': night_end,
        'force_charge_night_minutes': night_minutes,
        'force_charge_afternoon_window': aft_window,
        'charge_when_summary': summary,
    }


def get_battery_policy() -> dict:
    return {
        'title': BATTERY_POLICY_TITLE,
        'body': BATTERY_POLICY_BODY,
        'automation_enabled': False,
        'reasons': BATTERY_POLICY_REASONS,
    }


def resolve_season_name(season_mode: str | None, d: date | None = None) -> str:
    """`auto` → zima XI–II / wiosna III–V / jesień 15.09–31.10 / lato."""
    from src.optimization.battery_advisor import resolve_calendar_season

    mode = (season_mode or 'auto').strip().lower()
    if mode in ('winter', 'summer', 'autumn', 'spring'):
        return mode
    return resolve_calendar_season(d or date.today())


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


def _hourly_pv_for_plan(target_date: str, request=None) -> list[float]:
    """24h PV do symulacji planu — ten sam sygnał co wykres Home (archiwum → predictor).

    Bez tego request bez `app.state.pv_predictor` daje same zera → lato mylnie włącza
    ForceCharge we wszystkich oknach G12w (wykres: płaski 80% + skok o 22:00).
    """
    import logging

    pv = [0.0] * 24

    try:
        from api.services.forecast_ml import _archived_hourly_predictions

        arch = _archived_hourly_predictions(target_date)
        if not arch.empty:
            for _, row in arch.iterrows():
                h = int(row['hour'])
                if 0 <= h < 24:
                    pv[h] = float(row['predicted_kwh'])
    except Exception as exc:
        logging.warning('Plan 24h: archiwum PV niedostępne: %s', exc)

    if sum(pv) >= 1.0:
        return pv

    predictor = None
    if request is not None:
        predictor = getattr(getattr(request, 'app', None), 'state', None)
        predictor = getattr(predictor, 'pv_predictor', None) if predictor is not None else None

    if predictor is None:
        return pv

    try:
        from api.services.forecast_ml import get_hourly_forecast

        forecast_data = get_hourly_forecast(predictor, target_date)
        for hour_data in forecast_data.get('hours', []):
            h = int(hour_data['hour'])
            if 0 <= h < 24:
                pv[h] = float(hour_data['predicted_kwh'])
    except Exception as exc:
        logging.warning('Plan 24h: żywa prognoza PV niedostępna: %s', exc)

    return pv


def _force_charge_hours_for_season(
    *,
    season: str,
    d: date,
    pv_forecast: list[float],
    all_day_cheap: bool,
) -> list[int]:
    """Godziny FC w symulacji planu — zgodne z reżimem doradczym, nie „wszystkie tanie”."""
    from src.optimization.g12w_tariff import classify_zone

    total_pv = sum(pv_forecast)
    hours: list[int] = []

    if season in ('winter', 'autumn'):
        # Zima/jesień: tanie okna (noc + 13–15 pn–pt)
        for h in range(24):
            zone = classify_zone(datetime.combine(d, time(h, 0)))
            if all_day_cheap or zone == 2:
                hours.append(h)
        return hours

    # Lato/wiosna: FC tylko gdy dzień słaby; wyłącznie noc G12w (nie popołudnie 13–15)
    if total_pv < 15.0:
        for h in range(24):
            if not (h >= 22 or h < 6):
                continue
            zone = classify_zone(datetime.combine(d, time(h, 0)))
            if all_day_cheap or zone == 2:
                hours.append(h)
    return hours


def build_daily_plan(target_date: str, settings_row, use_realistic_sim: bool = True, request=None) -> dict:
    """Plan 24h: strefy G12w + symulacja SoC (reguły, bez ML/komend do falownika).

    Symulacja może być prosta (liniowy ramp, L342-373 poniżej) lub realistyczna
    (z historycznym profilem zużycia + PV forecast). Realistyczna symulacja jest
    domyślnie włączona (use_realistic_sim=True).

    Args:
        target_date: Data w formacie YYYY-MM-DD
        settings_row: Wiersz z tabeli battery_settings (soc_min, soc_target, season)
        use_realistic_sim: Jeśli True, użyj consumption_profile + PV forecast (default)
        request: FastAPI Request object (optional, for accessing app.state.pv_predictor)

    Returns:
        Dict z kluczami: date, season, hours (lista dict: hour, zone, soc, mode, note)
    """
    from src.optimization.g12w_tariff import classify_zone, is_public_holiday, is_weekend

    d = date.fromisoformat(target_date)
    season_mode = getattr(settings_row, 'season', None) if settings_row else 'auto'
    season = resolve_season_name(season_mode, d)

    soc_min = effective_soc_min(settings_row, d)
    soc_target = settings_row.soc_target_percent if settings_row else 80.0

    all_day_cheap = is_weekend(d) or is_public_holiday(d)

    # ═══════════════════════════════════════════════════════════════════
    # REALISTIC SIMULATION (use_realistic_sim=True)
    # ═══════════════════════════════════════════════════════════════════
    if use_realistic_sim:
        from src.optimization.battery_simulation import simulate_realistic_soc, BatterySimulationParams, annotate_soc_with_notes
        from src.optimization.consumption_profile import get_hourly_consumption_profile
        
        settings = get_settings()
        
        # 1. Pobierz profil zużycia historycznego
        load_profile = get_hourly_consumption_profile(
            db_path=settings.DATABASE_PATH,
            target_date=d,
            lookback_days=30,
        )
        
        # 2. Prognoza PV (archiwum daily / predictor) — musi być zsynchronizowana z wykresem Home
        pv_forecast = _hourly_pv_for_plan(target_date, request)
        
        # 3. ForceCharge: zima/jesień = tanie okna; lato = tylko słabe PV i tylko noc
        force_charge_hours = _force_charge_hours_for_season(
            season=season,
            d=d,
            pv_forecast=pv_forecast,
            all_day_cheap=all_day_cheap,
        )
        should_force_charge = bool(force_charge_hours)
        
        # 4. Wyznacz starting SoC — steady-state dla tego typu dnia
        # Wykres pokazuje "typowy dzień o tym reżimie pogodowym", nie "jutro po dzisiejszym dniu"
        # Używamy DZISIEJSZEJ prognozy do oszacowania starting SoC (steady-state założenie)
        
        total_pv_forecast = sum(pv_forecast)
        
        # Estymacja starting SoC na podstawie dzisiejszej prognozy (steady-state)
        if total_pv_forecast > 25.0:
            # Słoneczny dzień → steady-state: start z zapasem (typowo kończy ~60%, więc i zaczyna)
            soc_start = 60.0
        elif total_pv_forecast > 15.0:
            # Przyzwoity dzień → średni start
            soc_start = 45.0
        elif total_pv_forecast > 5.0:
            # Pochmurny dzień → niski start
            soc_start = max(soc_min + 5.0, 30.0)
        else:
            # Bardzo pochmurno/zima → start z FC nocnego
            soc_start = soc_min if season in ('summer', 'spring') else min(soc_target, 70.0)
        
        # Override dla zimy/jesieni z FC: zakładamy że FC nocny naładował
        if season in ('winter', 'autumn') and should_force_charge:
            soc_start = min(soc_target, 70.0)
        
        params = BatterySimulationParams()
        soc_trajectory = simulate_realistic_soc(
            pv_forecast_kwh=pv_forecast,
            load_profile_kwh=load_profile,
            soc_start_percent=soc_start,
            soc_min_percent=soc_min,
            soc_target_percent=soc_target,
            force_charge_hours=force_charge_hours,
            params=params,
        )
        
        # 5. Zbuduj wynik
        zones = []
        for h in range(24):
            dt = datetime.combine(d, time(h, 0))
            zones.append(classify_zone(dt))
        
        notes = annotate_soc_with_notes(
            soc_trajectory=soc_trajectory,
            pv_forecast_kwh=pv_forecast,
            load_profile_kwh=load_profile,
            soc_min_percent=soc_min,
            zones=zones,
        )
        
        hours = []
        for h in range(24):
            hours.append({
                'hour': h,
                'zone': zones[h],
                'zone_label': _zone_label(zones[h]),
                'force_charge_recommended': h in force_charge_hours,
                'planned_soc_percent': round(soc_trajectory[h], 1),
                'mode': 'ForceCharge' if h in force_charge_hours else 'Auto',
                'note': notes[h],
            })
        
        return {'date': target_date, 'season': season, 'hours': hours, 'note': 'Symulacja z historycznym profilem zużycia + PV forecast'}
    
    # ═══════════════════════════════════════════════════════════════════
    # SIMPLE SIMULATION (fallback, use_realistic_sim=False)
    # ═══════════════════════════════════════════════════════════════════
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
                'mode': 'ForceCharge' if force_charge else 'Auto',
                'note': 'Uproszczona symulacja (liniowy ramp)',
            }
        )

    return {'date': target_date, 'season': season, 'hours': hours, 'note': 'Uproszczona symulacja — liniowy ramp (stara metoda)'}


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

    # VAT 23% na energię elektryczną (zgodnie z symulator/bill)
    vat_rate = 1.23
    savings_netto = roi_data['savings_pln']
    baseline_netto = roi_data['baseline_cost_pln']
    actual_netto = roi_data['actual_cost_pln']

    return {
        'period_from': period_from,
        'period_to': period_to,
        'shadow_savings_pln': round(savings_netto * vat_rate, 2),
        'baseline_cost_pln': round(baseline_netto * vat_rate, 2),
        'actual_cost_pln': round(actual_netto * vat_rate, 2),
    }


def is_ac_event_type(event_type: str | None) -> bool:
    return (event_type or '').strip().lower() in AC_EVENT_TYPES


def resolve_ac_power_kw(settings_row, override: float | None = None) -> float:
    if override is not None and override > 0:
        return float(override)
    if settings_row and settings_row.ac_power_kw and settings_row.ac_power_kw > 0:
        return float(settings_row.ac_power_kw)
    return float(os.getenv('BATTERY_AC_POWER_KW', str(DEFAULT_AC_POWER_KW)))


def today_is_ac_day(db, user_id: int, day: date | None = None) -> bool:
    """True gdy w kalendarzu jest dziś klimatyzacja/upał — tylko wtedy karta na Home."""
    from api.models import HouseholdEvent

    try:
        target = (day or date.today()).isoformat()
        rows = (
            db.query(HouseholdEvent.event_type)
            .filter(HouseholdEvent.user_id == user_id, HouseholdEvent.event_date == target)
            .all()
        )
        return any(is_ac_event_type(r.event_type) for r in rows)
    except Exception:
        return False


def _ac_night_window(as_of: datetime) -> tuple[datetime, datetime, float]:
    """Start rozliczania baterii (18:00 lub teraz, jeśli później) → najbliższe 6:00."""
    night_hour = int(os.getenv('BATTERY_AC_NIGHT_START_HOUR', str(AC_BATTERY_NIGHT_START_HOUR)))
    cover_start = as_of.replace(hour=night_hour, minute=0, second=0, microsecond=0)
    if as_of >= cover_start:
        cover_start = as_of.replace(second=0, microsecond=0)
    morning = cover_start.replace(hour=AC_MORNING_HOUR, minute=0, second=0, microsecond=0)
    if cover_start >= morning:
        morning = morning + timedelta(days=1)
    hours_night = max(0.0, (morning - cover_start).total_seconds() / 3600.0)
    return cover_start, morning, hours_night


def calculate_ac_runtime(
    ac_power_kw: float,
    settings_row,
    *,
    as_of: datetime | None = None,
    ac_day: bool = False,
    snapshot=None,
    night_load_kw: float | None = None,
) -> dict:
    """T4.5: godzina wyłączenia AC, żeby SoC starczyło do 6:00 przy nocnym domu.

    Do 18:00 zakładamy, że PV jeszcze pokrywa bazę; od 18:00 (albo od „teraz”,
    jeśli później) bateria płaci za AC + load nocny. Kalendarz (`ac_day`) tylko
    steruje `show_card` — nie zmienia wzoru.
    """
    from src.optimization.battery_advisor import _evening_planning_load_kw, get_battery_snapshot

    as_of = as_of or datetime.now()
    snap = snapshot if snapshot is not None else get_battery_snapshot()
    soc_now = snap.soc_percent

    soc_min_morning = effective_soc_min(settings_row, as_of.date())
    capacity_kwh = (
        settings_row.battery_capacity_kwh if settings_row and settings_row.battery_capacity_kwh else None
    ) or 10.36
    efficiency = (settings_row.efficiency_pct if settings_row else 93.0) / 100.0
    power = max(0.01, float(ac_power_kw) if ac_power_kw and ac_power_kw > 0 else DEFAULT_AC_POWER_KW)
    load_kw = float(night_load_kw) if night_load_kw is not None else _evening_planning_load_kw()

    cover_start, morning, hours_night = _ac_night_window(as_of)
    night_house_kwh = round(load_kw * hours_night, 2)
    suggested_off_at: str | None = None
    hours_safe = 0.0
    available_kwh = 0.0

    if soc_now is None:
        note = 'Brak świeżego odczytu SoC z FoxESS — nie liczę godziny wyłączenia.'
    else:
        available_kwh = max(0.0, (soc_now - soc_min_morning) / 100.0 * capacity_kwh * efficiency)
        ac_budget = available_kwh - night_house_kwh
        if ac_budget <= 0:
            hours_safe = 0.0
            suggested_off_at = cover_start.strftime('%H:%M')
            note = (
                f'Wyłącz klimatyzację najpóźniej o {suggested_off_at} — '
                f'nocny dom (~{night_house_kwh:.1f} kWh do 6:00) zje rezerwę SoC. '
                'Sugestia — nie wyłączamy AC za Ciebie.'
            )
        else:
            hours_ac = ac_budget / power
            off_at = cover_start + timedelta(hours=hours_ac)
            if off_at >= morning:
                hours_safe = round(hours_night, 2)
                suggested_off_at = morning.strftime('%H:%M')
                note = (
                    f'Możesz trzymać klimatyzację do rana ({suggested_off_at}) — '
                    f'rezerwa {soc_min_morning:.0f}% powinna starczyć. Pomieszczenia zostają schłodzone.'
                )
            else:
                hours_safe = round(hours_ac, 2)
                suggested_off_at = off_at.strftime('%H:%M')
                note = (
                    f'Wyłącz klimatyzację ok. {suggested_off_at} — starczy do 6:00 '
                    f'bez importu w szczycie (noc ~{load_kw:.2f} kW). Pomieszczenia zostają schłodzone.'
                )

    return {
        'hours_safe': hours_safe,
        'suggested_off_at': suggested_off_at,
        'night_load_kw': round(load_kw, 2),
        'night_house_kwh': night_house_kwh,
        'hours_until_morning': round(hours_night, 2),
        'battery_covers_from': cover_start.strftime('%H:%M'),
        'ac_power_kw': round(power, 2),
        'show_card': bool(ac_day),
        'ac_day': bool(ac_day),
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
        'fc_max_minutes': effective_fc_max(settings_row, resolved),
        'fc_night_start_hour': _settings_night_start(settings_row),
        'recommended_fc_max_minutes': recommended_fc_max_minutes_for(resolved),
        'schedule_windows': schedule_windows_from_settings(settings_row),
        'schedule_max_windows': SCHEDULE_MAX_WINDOWS,
        'schedule_preset': getattr(settings_row, 'schedule_preset', None) or 'g12w',
    }


def fallback_home_suggestion(settings_row=None, as_of: datetime | None = None) -> dict:
    """Karta Home gdy SQLite/Fox blokuje odczyt — i tak pokaż reżim (lato/jesień/zima)."""
    as_of = as_of or datetime.now()
    d = as_of.date()
    season_mode = getattr(settings_row, 'season', None) if settings_row else 'auto'
    season = resolve_season_name(season_mode, d)
    reserve = seasonal_reserve_for(season, d)
    target = float(settings_row.soc_target_percent) if settings_row and settings_row.soc_target_percent else 80.0
    if season == 'winter':
        rec, night, aft = 'REŻIM ZIMA', 'wg T+PV (22–6)', 'włącz (13–15)'
        action = (
            f'Rezerwa SoC {reserve:.0f}% — nie ładuj w drogiej G12w. '
            f'ForceCharge 22–6 wg T jutro + PV. System tylko doradza — bez automatyki.'
        )
    elif season == 'autumn':
        rec, night, aft = 'REŻIM JESIEŃ', 'gdy PV jutro < ~8 kWh', 'gdy SoC poniżej celu'
        action = (
            f'Rezerwa SoC {reserve:.0f}% (mostek do zimy). '
            f'Ładuj nocą tylko gdy jutro PV < ~8 kWh — włącz 22:00 i wyłącz po czasie (30 min ≈ +50 pp). '
            f'System tylko doradza — bez automatyki.'
        )
    elif season == 'spring':
        rec, night, aft = 'REŻIM WIOSNA', 'rzadko (dach zwykle wystarczy)', 'rzadko potrzebne'
        action = (
            f'Rezerwa SoC {reserve:.0f}% jak lato. '
            f'Krótki FC tylko gdy SoC < 40% i jutro PV < ~8 kWh. System tylko doradza — bez automatyki.'
        )
    else:
        rec, night, aft = 'REŻIM LATO', 'pomiń — wystarczy PV', 'rzadko potrzebne'
        action = (
            f'Trzymaj min {reserve:.0f}% na noc (rezerwa). Ładowanie z sieci tylko gdy bateria spada poniżej 20% i jutro słabe PV. '
            f'System tylko doradza — bez automatyki.'
        )
    from src.optimization.battery_advisor import seasonal_min_evening_percent

    start_h = _settings_night_start(settings_row)
    fc_max = effective_fc_max(settings_row, season)
    aft_rec = season in ('winter', 'autumn')
    bits = _charge_window_bits(night_rec=False, night_rule=None, aft_rec=aft_rec, start_hour=start_h)

    return {
        'as_of': as_of.isoformat(timespec='seconds'),
        'season': season,
        'season_mode': season_mode or 'auto',
        'soc_now_percent': None,
        'soc_min_percent': reserve,
        'soc_reserve_percent': reserve,
        'soc_target_percent': target,
        'soc_min_evening_percent': seasonal_min_evening_percent(d, season=season),
        'force_charge_night_recommended': False,
        'force_charge_night_label': night,
        'force_charge_afternoon_recommended': aft_rec,
        'force_charge_afternoon_label': aft,
        **bits,
        'fc_max_minutes': fc_max,
        'fc_night_start_hour': start_h,
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
    """Karta Home (BAT.3 + BAT.5 + B1 jesień): reżim / ForceCharge / rezerwa — bez ML."""
    from src.optimization.battery_advisor import (
        evaluate_below_reserve_wait_cheap,
        evaluate_charge_tonight_cloudy,
        evaluate_soc16_hold_reserve,
        evaluate_winter_afternoon_fc,
        get_archived_day_pv_kwh,
        get_battery_snapshot,
        get_day_mean_temp_c,
        get_soc_at_hour,
        seasonal_min_evening_percent,
        seasonal_soc_reserve,
    )
    from src.optimization.g12w_tariff import is_public_holiday, is_weekend

    d = as_of.date()
    season_mode = getattr(settings_row, 'season', None) if settings_row else 'auto'
    season = resolve_season_name(season_mode, d)
    reserve = seasonal_soc_reserve(d, season=season)
    soc_min = effective_soc_min(settings_row, d)
    target = float(settings_row.soc_target_percent) if settings_row else 80.0
    min_evening = seasonal_min_evening_percent(d, season=season)
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
        min_evening=min_evening,
    )
    wait_cheap = evaluate_below_reserve_wait_cheap(
        soc_percent=soc_now,
        as_of=as_of,
        reserve_percent=reserve,
    )

    tomorrow_s = (d + timedelta(days=1)).isoformat()
    start_h = _settings_night_start(settings_row)
    fc_max = effective_fc_max(settings_row, season)
    night_rule = evaluate_charge_tonight_cloudy(
        soc_percent=soc_now,
        tomorrow_pv_kwh=get_archived_day_pv_kwh(tomorrow_s),
        as_of=as_of,
        tomorrow_temp_c=get_day_mean_temp_c(tomorrow_s),
        capacity_kwh=(
            settings_row.battery_capacity_kwh if settings_row and settings_row.battery_capacity_kwh else None
        ),
        fc_max_minutes=fc_max,
        night_start_hour=start_h,
    )

    weekend = is_weekend(d) or is_public_holiday(d)
    winter = season == 'winter'
    autumn = season == 'autumn'
    spring = season == 'spring'

    today_s = d.isoformat()
    aft_rule = evaluate_winter_afternoon_fc(
        soc_percent=soc_now,
        today_pv_kwh=get_archived_day_pv_kwh(today_s),
        today_temp_c=get_day_mean_temp_c(today_s),
        as_of=as_of,
    )

    def _aft_for_peak_season() -> tuple[bool, str]:
        """Zima: reguła historyczna SoC×T×PV; jesień: prosty próg SoC vs cel."""
        if winter:
            if aft_rule.triggered:
                return True, 'włącz 13–15 (niski SoC + słabe PV/zimno)'
            if aft_rule.skip_reason == 'soc_ok':
                return False, 'pomiń (SoC ≥ 40%)'
            if aft_rule.skip_reason == 'covered':
                return False, 'pomiń (dziś PV/T wystarczą)'
            if aft_rule.skip_reason == 'weekend':
                return False, 'niekrytyczne (weekend)'
            return False, 'sprawdź SoC@13 + PV'
        if soc_now is not None and soc_now >= target:
            return False, 'pomiń (SoC ≥ cel)'
        return True, 'włącz (13–15)'

    if weekend:
        night_rec, night_label = False, 'weekend — cała doba tanio'
        aft_rec, aft_label = False, 'niekrytyczne (weekend)'
    elif night_rule.triggered:
        night_rec = True
        night_label = _fc_on_off_label(
            minutes=night_rule.fc_minutes,
            target_soc=night_rule.target_soc_percent,
            soc_now=soc_now,
            start_hour=start_h,
        )
        aft_rec, aft_label = _aft_for_peak_season() if (winter or autumn) else (False, 'rzadko potrzebne')
    elif night_rule.skip_reason == 'wear':
        night_rec, night_label = False, 'pomiń (niewiele brakuje vs zużycie baterii)'
        aft_rec, aft_label = _aft_for_peak_season() if (winter or autumn) else (False, 'rzadko potrzebne')
    elif night_rule.skip_reason in ('covered', 'full'):
        night_rec, night_label = (
            False,
            'nie (dach pokryje szczyt)' if night_rule.skip_reason == 'covered' else 'nie (SoC ≥ cel)',
        )
        aft_rec, aft_label = _aft_for_peak_season() if (winter or autumn) else (False, 'rzadko potrzebne')
    elif winter:
        night_rec, night_label = False, 'sprawdź T+PV (brak prognozy)'
        aft_rec, aft_label = _aft_for_peak_season()
    elif autumn:
        night_rec, night_label = False, 'gdy PV jutro < ~8 kWh'
        aft_rec, aft_label = _aft_for_peak_season()
    elif spring:
        night_rec, night_label = False, 'rzadko (dach zwykle wystarczy)'
        aft_rec, aft_label = False, 'rzadko potrzebne'
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
            f'ForceCharge 22–6 wg T jutro + PV jutro (B2). '
            f'Okno 13–15: gdy SoC < 40% i dziś PV < ~10 kWh przy T≤5°C (historia XI–II). '
            f'System tylko doradza — bez automatyki.'
        )
    elif autumn:
        rec = 'REŻIM JESIEŃ'
        action = (
            f'Rezerwa SoC {reserve:.0f}% (mostek lato→zima). '
            f'Ładuj nocą gdy jutro PV < ~8 kWh — włącz 22:00, wyłącz po czasie (30 min ≈ +50 pp). '
            f'Cel ~85%. System tylko doradza — bez automatyki.'
        )
    elif spring:
        rec = 'REŻIM WIOSNA'
        action = (
            f'Rezerwa SoC {reserve:.0f}%. Krótki FC tylko gdy SoC < 40% i jutro PV < ~8 kWh. '
            f'System tylko doradza — bez automatyki.'
        )
    else:
        rec = 'REŻIM LATO'
        action = (
            f'Trzymaj min {reserve:.0f}% na noc (rezerwa). '
            f'Ładowanie z sieci tylko gdy bateria spada poniżej 20% i jutro słabe PV. '
            f'System tylko doradza — decyzja należy do Ciebie.'
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
        **_charge_window_bits(
            night_rec=night_rec,
            night_rule=night_rule if night_rec else None,
            aft_rec=aft_rec,
            start_hour=start_h,
        ),
        'fc_max_minutes': fc_max,
        'fc_night_start_hour': start_h,
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
