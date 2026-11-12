"""
Mapowanie rekomendacji battery_advisor → plan sterowania FoxESS.

Domyślnie tylko plan (dry-run). Realne API wymaga BATTERY_CONTROL_ENABLED=1 + --apply.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Literal

import pandas as pd

from src.data.foxess_control import BatteryControlState, ForceChargeWindow, FoxEssControl
from src.optimization.battery_advisor import BatteryAdvice, Context, advise
from src.optimization.g12w_tariff import is_cheap_zone, is_public_holiday, is_weekend, weekday_force_charge_windows

ActionKind = Literal[
    'set_force_charge_windows',
    'set_work_mode',
    'set_min_soc',
    'noop',
]

LOG_FILE = 'data/processed/battery_control_log.csv'
EVENING_SESSION_FILE = 'data/processed/battery_evening_session.json'
ControlPhase = Literal['run', 'apply', 'stop']


@dataclass
class ControlAction:
    kind: ActionKind
    description: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class ControlPlan:
    context: Context
    as_of: datetime
    recommendation: str
    dry_run: bool
    actions: list[ControlAction]
    notes: list[str] = field(default_factory=list)

    def has_changes(self) -> bool:
        return any(a.kind != 'noop' for a in self.actions)


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, '').strip()
    return float(raw) if raw else default


def _night_window() -> ForceChargeWindow:
    start, end = weekday_force_charge_windows()[0]
    return ForceChargeWindow(
        enabled=True,
        start_hour=start.hour + start.minute / 60.0,
        end_hour=end.hour + end.minute / 60.0,
    )


def _midday_window() -> ForceChargeWindow:
    start, end = weekday_force_charge_windows()[1]
    return ForceChargeWindow(
        enabled=True,
        start_hour=start.hour + start.minute / 60.0,
        end_hour=end.hour + end.minute / 60.0,
    )


def _disabled_window() -> ForceChargeWindow:
    return ForceChargeWindow(enabled=False, start_hour=0.0, end_hour=0.0)


def g12w_force_charge_windows(*, enabled: bool = True) -> tuple[ForceChargeWindow, ForceChargeWindow]:
    """Fox (2 okna): 22–01 i 04–06 — tanio G12w; drugie okno = ładowanie / ogrzewanie od ~4:00."""
    return (
        ForceChargeWindow(enabled=enabled, start_hour=22.0, end_hour=1.0),
        ForceChargeWindow(enabled=enabled, start_hour=4.0, end_hour=6.0),
    )


def control_enabled() -> bool:
    return os.getenv('BATTERY_CONTROL_ENABLED', '0').strip().lower() in ('1', 'true', 'yes')


def evening_apply_allowed(as_of: datetime) -> bool:
    """Apply B2 tylko w taniej strefie G12w (strefa 2)."""
    return is_cheap_zone(as_of)


def should_apply(dry_run_flag: bool | None = None) -> bool:
    """True tylko gdy master switch ON i jawne apply (flaga lub env)."""
    if not control_enabled():
        return False
    if dry_run_flag is not None:
        return not dry_run_flag
    return os.getenv('BATTERY_CONTROL_APPLY', '0').strip().lower() in ('1', 'true', 'yes')


def evening_only_enforced() -> bool:
    return os.getenv('BATTERY_CONTROL_EVENING_ONLY', '1').strip().lower() in ('1', 'true', 'yes')


def morning_cloudy_apply_enabled() -> bool:
    """Apply @~5:00 przed końcem tania (6:00) gdy mało PV / pochmurny dzień."""
    return os.getenv('BATTERY_CONTROL_MORNING_CLOUDY', '0').strip().lower() in ('1', 'true', 'yes')


def morning_cloudy_pv_kwh_threshold() -> float:
    return _env_float('BATTERY_MORNING_CLOUDY_PV_KWH', 12.0)


def morning_apply_allowed(as_of: datetime) -> bool:
    """Tania strefa przed 6:00 (pn–pt) lub weekend/święto."""
    if as_of.hour >= 6:
        return False
    if is_weekend(as_of.date()) or is_public_holiday(as_of.date()):
        return True
    return is_cheap_zone(as_of)


def morning_soc_floor() -> float:
    """@~4:00 (launchd): poniżej progu → top-up w oknie 04–06 G12w."""
    return _env_float('BATTERY_MORNING_SOC_FLOOR', 80.0)


def morning_topup_target_soc() -> float:
    return _env_float('BATTERY_MORNING_TOPUP_TARGET', 90.0)


def morning_topup_min_delta_soc() -> float:
    return _env_float('BATTERY_MORNING_TOPUP_MIN_DELTA', 5.0)


def morning_sunny_reserve_soc() -> float:
    """Fallback @4:00 gdy brak T nocy i ZIMNO/AWARIA (kalibracja 12.11 ≈ 4°C → 85%)."""
    return _env_float('BATTERY_MORNING_SUNNY_RESERVE_SOC', 85.0)


def morning_heat_t_ref_c() -> float:
    """Powyżej tej Tnoc ogrzewanie nie dolicza SoC ponad headroom 70%."""
    return _env_float('BATTERY_MORNING_HEAT_T_REF_C', 10.0)


def morning_heat_pp_per_c() -> float:
    """pp SoC na 1°C poniżej T_ref. Case 12.11: Tnoc 4°C → +15 pp → 85%."""
    return _env_float('BATTERY_MORNING_HEAT_PP_PER_C', 2.5)


def morning_sunny_target_max_soc() -> float:
    return _env_float('BATTERY_MORNING_SUNNY_TARGET_MAX', 95.0)


def sunny_morning_target_soc_for_temp(
    night_temp_c: float | None,
    *,
    zimno: bool = False,
) -> float:
    """Cel SoC @4:00 przy dużym dachu — zależy od T nocy (Open-Meteo).

    T ≥ 10°C → 70%. Każdy °C poniżej +2,5 pp (12.11: 4°C → 85%). Sufit 95%.
    Brak T: ZIMNO/AWARIA → 85%, inaczej 70%.
    """
    from src.optimization.battery_advisor import sunny_night_soc

    headroom = sunny_night_soc()
    if night_temp_c is None:
        return morning_sunny_reserve_soc() if zimno else headroom
    extra = max(0.0, (morning_heat_t_ref_c() - float(night_temp_c)) * morning_heat_pp_per_c())
    return round(min(morning_sunny_target_max_soc(), max(headroom, headroom + extra)), 1)


def _morning_reserve_recommendation(advice: BatteryAdvice) -> bool:
    rec = advice.recommendation or ''
    return rec.startswith('ZIMNO') or rec.startswith('AWARIA')


def _sunny_morning_target_soc(advice: BatteryAdvice) -> float:
    """Cel poranny przy dużym dachu: Tnoc × pp/°C, nie stałe 70/85."""
    from src.optimization.battery_advisor import get_night_mean_temp_c

    night_t = get_night_mean_temp_c(advice.as_of)
    return sunny_morning_target_soc_for_temp(
        night_t,
        zimno=_morning_reserve_recommendation(advice),
    )


@dataclass
class MorningTopupPlan:
    target_soc: float
    fc_minutes: float
    stop_at: datetime


def _collapsed_day_pv_kwh() -> float:
    """Poniżej tego PV dzień jest załamany (mgła, śnieg, gęste chmury) — dobij nawet przy jasnym Accu."""
    return _env_float('BATTERY_MORNING_COLLAPSED_PV_KWH', 8.0)


def _accu_regime_for_day(target_day: str) -> str | None:
    try:
        from src.weather.forecast_routing import resolve_forecast_display

        routing = resolve_forecast_display(target_day)
    except Exception:
        return None
    return routing.regime


def _morning_pv_weak(advice: BatteryAdvice) -> bool:
    """Czy o 4:00 dobić z sieci. Tylko przed słabym dniem, nie przed słonecznym.

    Słoneczna niedziela (Accu jasny, produkcja od ~7:00) ma zostać z miejscem w
    baterii. Pochmurno, śnieg i załamany PV (jak sobotnia mgła) dalej dobijają.
    """
    from src.optimization.battery_advisor import get_day_pv_forecast_sum

    today_pv = get_day_pv_forecast_sum(advice.target_day, as_of=advice.as_of)
    if today_pv is not None and today_pv >= morning_cloudy_pv_kwh_threshold():
        return False
    if today_pv is not None and today_pv < _collapsed_day_pv_kwh():
        return True
    if _accu_regime_for_day(advice.target_day) == 'jasny':
        return False
    if today_pv is not None:
        return today_pv < morning_cloudy_pv_kwh_threshold()
    morning_pv = advice.pv.morning_forecast_kwh if advice.pv else None
    return morning_pv is not None and morning_pv < 8.0


def _topup_from_inter_window(advice: BatteryAdvice) -> MorningTopupPlan | None:
    iw = advice.inter_window
    if iw is None or not iw.triggered:
        return None
    if iw.fc_minutes is None or iw.target_soc_percent is None:
        return None
    stop_at = iw.stop_at or planned_morning_stop_at(advice.as_of)
    return MorningTopupPlan(
        target_soc=iw.target_soc_percent,
        fc_minutes=iw.fc_minutes,
        stop_at=stop_at,
    )


def _headroom_topup(advice: BatteryAdvice) -> MorningTopupPlan | None:
    """Słoneczny poranek, SoC poniżej celu: drugie ładowanie nocy, nie pełnienie pod eksport.

    Cel rośnie gdy noc jest zimna (Tnoc vs 10°C). Case 12.11: Tnoc ~4°C, 70% → SoC 10%
    zanim PV pokrył load (~5 kWh z baterii).
    """
    from src.optimization.battery_advisor import fc_apply_minutes_for_delta_soc

    soc = advice.snapshot.soc_percent if advice.snapshot else None
    if soc is None:
        return None
    # Ślepy SoC (np. 76% sprzed 3–10 h) nie wolno traktować jako bazy do dobicia headroom/rezerwy.
    if not _snapshot_fresh(advice):
        return None
    target = _sunny_morning_target_soc(advice)
    delta = target - soc
    if delta < morning_topup_min_delta_soc():
        return None
    minutes = fc_apply_minutes_for_delta_soc(delta)
    cheap_end = planned_morning_stop_at(advice.as_of)
    max_minutes = max(0.0, (cheap_end - advice.as_of).total_seconds() / 60.0)
    minutes = min(minutes, max_minutes)
    if minutes < 3.0:
        return None
    stop_at = advice.as_of + timedelta(minutes=minutes)
    if stop_at > cheap_end:
        stop_at = cheap_end
    return MorningTopupPlan(target_soc=target, fc_minutes=minutes, stop_at=stop_at)


def compute_morning_topup(advice: BatteryAdvice) -> MorningTopupPlan | None:
    """Poranny top-up @~4:00: bilans między oknami lub (legacy) słabe PV + SoC < floor."""
    if advice.context != 'morning':
        return None
    from src.optimization.inter_window_charge import inter_window_auto_enabled

    if inter_window_auto_enabled():
        plan = _topup_from_inter_window(advice)
        if plan is not None:
            return plan
    if not _morning_pv_weak(advice):
        # 22:00 mogło nie ruszyć (nieświeży SoC). O 4:00 dobij tylko do ~70%, nie do 90–95%.
        return _headroom_topup(advice)
    soc = advice.snapshot.soc_percent if advice.snapshot else None
    if soc is None or soc >= morning_soc_floor():
        return None
    target = morning_topup_target_soc()
    delta = max(0.0, target - soc)
    if delta < morning_topup_min_delta_soc():
        return None
    from src.optimization.battery_advisor import fc_apply_minutes_for_delta_soc

    minutes = fc_apply_minutes_for_delta_soc(delta)
    cheap_end = planned_morning_stop_at(advice.as_of)
    max_minutes = max(0.0, (cheap_end - advice.as_of).total_seconds() / 60.0)
    minutes = min(minutes, max_minutes)
    if minutes < 3.0:
        return None
    stop_at = advice.as_of + timedelta(minutes=minutes)
    if stop_at > cheap_end:
        stop_at = cheap_end
    return MorningTopupPlan(target_soc=target, fc_minutes=minutes, stop_at=stop_at)


def pre_cheap_apply_enabled() -> bool:
    return os.getenv('BATTERY_CONTROL_PRE_CHEAP', '0').strip().lower() in ('1', 'true', 'yes')


def compute_pre_cheap_topup(advice: BatteryAdvice) -> MorningTopupPlan | None:
    """Apply od 13:00 w oknie 13–15 — ten sam bilans co poranek."""
    if advice.context != 'pre_cheap':
        return None
    return _topup_from_inter_window(advice)


def pre_cheap_apply_trigger(advice: BatteryAdvice) -> bool:
    return compute_pre_cheap_topup(advice) is not None


def soc_snapshot_max_age_hours() -> float:
    """Świeży odczyt do decyzji „już pełna — zgaś ForceCharge”. Starszy SoC tej decyzji nie podejmuje."""
    return _env_float('BATTERY_SOC_MAX_AGE_HOURS', 0.75)


def _snapshot_fresh(advice: BatteryAdvice) -> bool:
    snap = advice.snapshot
    if snap is None or snap.soc_percent is None:
        return False
    if snap.age_hours is None:
        return True
    return snap.age_hours <= soc_snapshot_max_age_hours()


def _night_should_release_windows(advice: BatteryAdvice) -> bool:
    """Zgaś harmonogram tylko gdy świeży SoC jest już na celu dużego dachu.

    Odczyt sprzed godzin (jak 76% o 21:15 przy prawdziwych ~12%) nie może wyłączyć ładowania.
    """
    if not _snapshot_fresh(advice):
        return False
    rule = advice.charge_tonight
    if rule is None or rule.triggered or rule.skip_reason != 'full':
        return False
    from src.optimization.battery_advisor import sunny_night_soc

    soc = advice.snapshot.soc_percent if advice.snapshot else None
    if soc is None or soc < sunny_night_soc():
        return False
    pv = rule.tomorrow_pv_kwh
    return pv is not None and pv >= morning_cloudy_pv_kwh_threshold()


def morning_cloudy_apply_trigger(advice: BatteryAdvice) -> bool:
    """Apply @4:00: dobicie przed słabym dniem albo zgaszenie okien przed słonecznym."""
    if compute_morning_topup(advice) is not None:
        return True
    if advice.context != 'morning' or advice.as_of.hour >= 6 or advice.season != 'winter':
        return False
    return not _morning_pv_weak(advice)


def planned_morning_stop_at(as_of: datetime) -> datetime:
    """Koniec FC przed szczytem G12w (6:00)."""
    stop = as_of.replace(hour=6, minute=0, second=0, microsecond=0)
    if as_of >= stop:
        stop = stop + timedelta(days=1)
    return stop


def max_applies_per_day() -> int:
    raw = os.getenv('BATTERY_CONTROL_MAX_APPLIES_PER_DAY', '3').strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 3


def count_real_applies_today(*, path: str | None = None, as_of: datetime | None = None) -> int:
    """Liczba wpisów apply (dry_run=false, applied_count>0) w danym dniu kalendarzowym."""
    path = path or LOG_FILE
    if not os.path.isfile(path):
        return 0
    day = (as_of or datetime.now()).date().isoformat()
    try:
        df = pd.read_csv(path)
    except Exception:
        return 0
    if df.empty or 'logged_at' not in df.columns:
        return 0
    applied = 0
    for _, row in df.iterrows():
        logged = str(row.get('logged_at', ''))[:10]
        if logged != day:
            continue
        dry = row.get('dry_run')
        if str(dry).lower() in ('true', '1', '1.0'):
            continue
        cnt = row.get('applied_count', 0)
        try:
            if int(cnt) > 0:
                applied += 1
        except (TypeError, ValueError):
            pass
    return applied


def validate_apply_request(
    context: Context,
    advice: BatteryAdvice,
    *,
    phase: ControlPhase = 'apply',
) -> str | None:
    """None = OK; inaczej powód odmowy apply (T6.4)."""
    try:
        from src.data.foxess_api_guard import is_api_paused, pause_message

        if is_api_paused():
            return pause_message()
    except Exception:
        pass
    if phase == 'stop':
        return None
    if evening_only_enforced() and context not in ('evening', 'morning', 'pre_cheap'):
        return 'BATTERY_CONTROL_EVENING_ONLY=1 — apply tylko evening/morning/pre_cheap.'
    if context == 'morning' and not morning_cloudy_apply_enabled():
        return 'BATTERY_CONTROL_MORNING_CLOUDY=0 — poranny apply wyłączony.'
    if count_real_applies_today(as_of=advice.as_of) >= max_applies_per_day():
        return (
            f'Limit apply/dzień ({max_applies_per_day()}) — '
            'zwiększ BATTERY_CONTROL_MAX_APPLIES_PER_DAY lub poczekaj do jutra.'
        )
    if phase == 'apply' and context == 'evening':
        if not evening_apply_allowed(advice.as_of):
            return 'Strefa G12w szczytowa — apply B2 tylko w taniej strefie (22:00–6:00 / weekend).'
        rule = advice.charge_tonight
        if not rule or not rule.triggered:
            if _night_should_release_windows(advice):
                return None
            return 'Reguła B2 bez triggera — apply pominięte (POMIŃ).'
    if phase == 'apply' and context == 'morning':
        if not morning_apply_allowed(advice.as_of):
            return 'Poza oknem tanio przed 6:00 — apply morning pominięte.'
        iw_ok = bool(advice.inter_window and advice.inter_window.triggered)
        if not morning_cloudy_apply_enabled() and not iw_ok:
            return 'BATTERY_CONTROL_MORNING_CLOUDY=0 — poranny apply wyłączony.'
        if not morning_cloudy_apply_trigger(advice):
            return (
                f'Poranny apply @4:00 pominięty: bilans/PV OK lub SoC wystarczający '
                f'(floor legacy {morning_soc_floor():.0f}%).'
            )
    if phase == 'apply' and context == 'pre_cheap':
        hour = advice.as_of.hour
        if hour < 13 or hour >= 15:
            return (
                'Apply 13:00–15:00 tylko od 13:00 — o 12:00 prąd jest jeszcze drogi, '
                'zostaje sam bilans (dry-run).'
            )
        if not pre_cheap_apply_enabled():
            return 'BATTERY_CONTROL_PRE_CHEAP=0 — apply południowy wyłączony.'
        if not pre_cheap_apply_trigger(advice):
            return 'Apply 13–15 pominięty — bilans: PV pokrywa lub luka < próg cyklu.'
    return None


def planned_stop_at(advice: BatteryAdvice) -> datetime | None:
    rule = advice.charge_tonight
    if not rule or not rule.triggered:
        return None
    from src.optimization.battery_advisor import fc_apply_minutes_for_delta_soc

    soc = advice.snapshot.soc_percent if advice.snapshot else None
    target = rule.target_soc_percent
    if soc is not None and target is not None:
        minutes = fc_apply_minutes_for_delta_soc(target - soc)
    elif rule.fc_minutes:
        minutes = float(rule.fc_minutes)
    else:
        return None
    return advice.as_of + timedelta(minutes=minutes)


def _session_path() -> str:
    return os.getenv('BATTERY_EVENING_SESSION_FILE', EVENING_SESSION_FILE)


def load_evening_session() -> dict[str, Any] | None:
    path = _session_path()
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding='utf-8') as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def save_evening_session(data: dict[str, Any]) -> None:
    path = _session_path()
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def record_evening_session_after_apply(advice: BatteryAdvice, plan: ControlPlan, results: list[dict[str, Any]]) -> None:
    """Po udanym start FC zapisz stop_at dla T6.2b (evening lub morning @5)."""
    if plan.dry_run or plan.context not in ('evening', 'morning', 'pre_cheap'):
        return
    applied = sum(1 for r in results if r.get('action') != 'noop' and not r.get('dry_run'))
    if applied <= 0:
        return
    if plan.context == 'evening':
        stop = planned_stop_at(advice)
        if stop is None:
            return
        rule = advice.charge_tonight
        fc_min = rule.fc_minutes if rule else None
        target = rule.target_soc_percent if rule else None
    elif plan.context == 'pre_cheap':
        topup = compute_pre_cheap_topup(advice)
        if not topup:
            return
        stop = topup.stop_at
        fc_min = topup.fc_minutes
        target = topup.target_soc
    else:
        topup = compute_morning_topup(advice)
        if topup:
            stop = topup.stop_at
            fc_min = topup.fc_minutes
            target = topup.target_soc
        else:
            stop = planned_morning_stop_at(advice.as_of)
            mins = max(0.0, (stop - advice.as_of).total_seconds() / 60.0)
            fc_min = round(mins, 1)
            target = _env_float('BATTERY_SOC_TARGET', 80.0)
    save_evening_session(
        {
            'day': advice.as_of.date().isoformat(),
            'kind': plan.context,
            'started_at': advice.as_of.isoformat(timespec='seconds'),
            'stop_at': stop.isoformat(timespec='seconds'),
            'fc_minutes': fc_min,
            'target_soc_percent': target,
            'stop_done': False,
        }
    )


def build_evening_stop_plan(as_of: datetime) -> ControlPlan:
    return ControlPlan(
        context='evening',
        as_of=as_of,
        recommendation='STOP FC (B2 timer)',
        dry_run=True,
        actions=[
            ControlAction(
                'set_work_mode',
                'Koniec nocnego ForceCharge — tryb SelfUse (timer B2).',
                {'mode': 'SelfUse'},
            ),
        ],
        notes=['T6.2b: wyłączenie FC po zaplanowanych minutach.'],
    )


def stop_fox_max_attempts() -> int:
    """Ile ticków stopu może dotknąć Fox Cloud (każdy ≈ odczyt + ewentualny SelfUse)."""
    raw = os.getenv('BATTERY_STOP_FOX_MAX_ATTEMPTS', '4').strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 4


def stop_fox_min_interval_sec() -> int:
    raw = os.getenv('BATTERY_STOP_FOX_MIN_INTERVAL_SEC', '600').strip()
    try:
        return max(60, int(raw))
    except ValueError:
        return 600


def stop_fox_quota_status(sess: dict[str, Any], as_of: datetime) -> str | None:
    """None = wolno wołać Fox; inaczej kod bez wywołania chmury (limit ~1440/dobę)."""
    attempts = int(sess.get('fox_stop_attempts') or 0)
    if attempts >= stop_fox_max_attempts():
        return 'quota_stop'
    last = sess.get('fox_stop_last_at')
    if last:
        prev = datetime.fromisoformat(str(last))
        if (as_of - prev).total_seconds() < stop_fox_min_interval_sec():
            return 'quota_wait'
    return None


def work_mode_is_force_charge(mode: str | None) -> bool:
    raw = (mode or '').replace(' ', '').replace('_', '').replace('-', '').lower()
    return raw == 'forcecharge'


def evening_stop_if_due(*, dry_run: bool = True, as_of: datetime | None = None) -> tuple[str, ControlPlan | None, list[dict[str, Any]]]:
    """Po `stop_at`: jeśli Fox nadal w ForceCharge — przełącz na SelfUse.

    `stop_done` dopiero gdy odczyt trybu nie jest ForceCharge (kolejny tick launchd
    powtarza wyłączenie, gdy komenda nie zeszła na falownik).
    """
    as_of = as_of or datetime.now()
    sess = load_evening_session()
    if not sess or sess.get('stop_done'):
        return 'skip_no_session', None, []
    if sess.get('day') != as_of.date().isoformat():
        return 'skip_stale_day', None, []
    stop_raw = sess.get('stop_at')
    if not stop_raw:
        return 'skip_no_stop_at', None, []
    stop_at = datetime.fromisoformat(str(stop_raw))
    if as_of < stop_at:
        return 'wait', None, []

    blocked = stop_fox_quota_status(sess, as_of)
    if blocked:
        return blocked, None, []
    sess['fox_stop_attempts'] = int(sess.get('fox_stop_attempts') or 0) + 1
    sess['fox_stop_last_at'] = as_of.isoformat(timespec='seconds')
    save_evening_session(sess)

    try:
        from src.data.foxess_api_guard import is_api_paused, pause_message

        if not dry_run and is_api_paused():
            return f'denied:{pause_message()}', None, []
    except Exception:
        pass

    try:
        controller = FoxEssControl()
        state = controller.read_state()
    except (ValueError, RuntimeError) as exc:
        plan = build_evening_stop_plan(as_of)
        plan.notes.append(f'⚠️ Brak FoxESS: {exc}')
        return 'fox_error', plan, []

    schedule_on = bool(getattr(state, 'schedule_enabled', False))
    mode_on = work_mode_is_force_charge(state.work_mode)
    # SelfUse przy włączonym harmonogramie nadal ładuje, dopóki okres ma fdPwr > 0.
    if not schedule_on and not mode_on:
        sess['stop_done'] = True
        sess['stopped_at'] = as_of.isoformat(timespec='seconds')
        sess['verified_mode'] = state.work_mode
        save_evening_session(sess)
        return 'already_off', None, []

    plan = build_evening_stop_plan(as_of)
    plan.dry_run = dry_run
    results: list[dict[str, Any]] = []
    if schedule_on:
        plan.notes.append('Harmonogram ForceCharge nadal włączony — wyłączam go.')
        try:
            results.append(controller.set_work_schedule([], enable=False, dry_run=dry_run))
        except RuntimeError as exc:
            plan.notes.append(f'⚠️ set_schedule: {exc}')
            return 'still_force_charge', plan, results
    if mode_on:
        plan.notes.append(f'Fox nadal ForceCharge ({state.work_mode}) — wysyłam SelfUse.')
        results.extend(execute_plan(plan, controller, dry_run=dry_run))

    if dry_run:
        return 'would_stop', plan, results

    try:
        after = controller.read_state()
    except (ValueError, RuntimeError) as exc:
        plan.notes.append(f'⚠️ Ponowny odczyt FoxESS nieudany: {exc}')
        return 'still_force_charge', plan, results

    still_on = work_mode_is_force_charge(after.work_mode) or bool(
        getattr(after, 'schedule_enabled', False)
    )
    if still_on:
        plan.notes.append(
            'Po komendzie ładowanie nadal włączone — kolejny tick powtórzy stop.'
        )
        return 'still_force_charge', plan, results

    sess['stop_done'] = True
    sess['stopped_at'] = as_of.isoformat(timespec='seconds')
    sess['verified_mode'] = after.work_mode
    save_evening_session(sess)
    return 'stopped', plan, results


def build_plan(advice: BatteryAdvice, *, state: BatteryControlState | None = None) -> ControlPlan:
    """Z rekomendacji advisora zbuduj listę akcji na falownik."""
    rec = advice.recommendation
    actions: list[ControlAction] = []
    notes: list[str] = []
    winter = advice.season == 'winter'
    weekend = is_weekend(advice.as_of.date())
    soc = advice.snapshot.soc_percent
    target = _env_float('BATTERY_SOC_TARGET', 80.0)
    reserve = _env_float('BATTERY_SOC_RESERVE_WINTER', 40.0)

    night = _night_window()
    midday = _midday_window()
    midday_off = _disabled_window()

    if advice.context == 'morning':
        topup = compute_morning_topup(advice)
        if not winter:
            actions.append(ControlAction('noop', 'Tryb letni — bez automatycznego ForceCharge.'))
        elif topup and advice.as_of.hour < 6:
            soc_txt = f'{soc:.0f}%' if soc is not None else '?'
            iw_on = bool(advice.inter_window and advice.inter_window.triggered)
            if not _morning_pv_weak(advice) and not iw_on:
                fc1 = _disabled_window()
                fc2 = ForceChargeWindow(enabled=True, start_hour=4.0, end_hour=6.0)
                from src.optimization.battery_advisor import get_night_mean_temp_c

                night_t = get_night_mean_temp_c(advice.as_of)
                t_txt = f'Tnoc {night_t:.0f}°C, ' if night_t is not None else ''
                window_label = (
                    f'Poranny dobij do ~{topup.target_soc:.0f}% @4:00 ({t_txt}duży dach): '
                    'tylko okno 04–06.'
                )
            else:
                fc1, fc2 = g12w_force_charge_windows(enabled=True)
                window_label = 'Poranny top-up @~4:00: Fox okna 22–01 + 04–06 (G12w tanio).'
            actions.append(ControlAction(
                'set_force_charge_windows',
                window_label,
                {'period1': fc1, 'period2': fc2},
            ))
            actions.append(ControlAction(
                'set_work_mode',
                f'ForceCharge: SoC {soc_txt} → ~{topup.target_soc:.0f}% przed 6:00.',
                {'mode': 'ForceCharge', 'max_soc': topup.target_soc},
            ))
            notes.append(
                f'Poranny top-up @4:00: okno 04–06 włączone, ΔSoC → {topup.target_soc:.0f}%, '
                f'~{topup.fc_minutes:.0f} min FC, stop {topup.stop_at.strftime("%H:%M")} '
                f'(30 min ≈ +50 pp).'
            )
        elif (
            advice.as_of.hour < 6
            and not _morning_pv_weak(advice)
            and _snapshot_fresh(advice)
            and soc is not None
            and soc >= _sunny_morning_target_soc(advice)
        ):
            actions.append(ControlAction(
                'set_work_mode',
                'Słoneczny dzień — bez doładowania o 4:00, miejsce na produkcję od ~7:00.',
                {'mode': 'SelfUse'},
            ))
            actions.append(ControlAction(
                'set_force_charge_windows',
                'Wyłącz okna ForceCharge: duży dach, nie pchać baterii do 100% przed wschodem.',
                {'period1': _disabled_window(), 'period2': _disabled_window()},
            ))
            notes.append(
                'O 4:00 bez FC — dzień nie jest pochmurny. 22:00 zostaje buforem na awarię, '
                'nie pełnieniem pod eksport.'
            )
        elif advice.as_of.hour < 6 and not _morning_pv_weak(advice) and not _snapshot_fresh(advice):
            actions.append(ControlAction(
                'noop',
                'SoC nieświeży — o 4:00 bez gaszenia okien i bez pełnienia na ślepym odczycie.',
            ))
        elif rec == 'ŁADUJ Z SIECI (TANIO)':
            actions.append(ControlAction(
                'set_force_charge_windows',
                'Włącz okno nocne 22:00–6:00 (G12w tanio).',
                {'period1': night, 'period2': midday_off},
            ))
            if advice.as_of.hour < 6:
                actions.append(ControlAction(
                    'set_work_mode',
                    'Natychmiastowe ładowanie z sieci do 6:00 (ForceCharge).',
                    {'mode': 'ForceCharge', 'max_soc': morning_topup_target_soc()},
                ))
                stop = planned_morning_stop_at(advice.as_of)
                notes.append(
                    f'Poranny top-up pochmurny: stop FC o {stop.strftime("%H:%M")} (przed szczytem G12w).'
                )
        elif rec in ('SOC OK', 'POCZEKAJ NA PV'):
            actions.append(ControlAction(
                'set_work_mode',
                'Autokonsumpcja — bez wymuszonego ładowania z sieci.',
                {'mode': 'SelfUse'},
            ))
            if rec == 'POCZEKAJ NA PV':
                notes.append('Okno 22–6 pozostaje skonfigurowane na zimę, ale tryb SelfUse teraz.')
        elif rec.startswith('ZIMNO') or rec.startswith('AWARIA'):
            actions.append(ControlAction(
                'set_force_charge_windows',
                'Pełne okna tanich stref — maks. rezerwa na przerwy.',
                {'period1': night, 'period2': midday},
            ))
            actions.append(ControlAction(
                'set_min_soc',
                f'Podnieś rezerwę min. SoC do {reserve:.0f}%.',
                {'min_soc': reserve},
            ))
        else:
            actions.append(ControlAction('noop', f'Brak reguły sterowania dla: {rec}'))

    elif advice.context == 'evening':
        rule = advice.charge_tonight
        if rule and rule.triggered:
            sunny_night = (
                rule.tomorrow_pv_kwh is not None
                and rule.tomorrow_pv_kwh >= morning_cloudy_pv_kwh_threshold()
            )
            if sunny_night:
                # Tylko 22–01. Okno 04–06 zostaje na drugie ładowanie, jeśli rano dzień jest słaby.
                fc1 = ForceChargeWindow(enabled=True, start_hour=22.0, end_hour=1.0)
                fc2 = _disabled_window()
                window_label = 'B2 @22:00: tylko okno 22–01 (duży dach — 4:00 bez drugiego ładowania).'
            else:
                fc1, fc2 = g12w_force_charge_windows(enabled=True)
                window_label = 'B2 @22:00: Fox okna 22–01 + 04–06 (słaby dzień, drugie ładowanie rano).'
            soc_txt = f'{soc:.0f}%' if soc is not None else '?'
            target_txt = (
                f'{rule.target_soc_percent:.0f}%'
                if rule.target_soc_percent is not None
                else '?'
            )
            actions.append(ControlAction(
                'set_force_charge_windows',
                window_label,
                {'period1': fc1, 'period2': fc2},
            ))
            if is_cheap_zone(advice.as_of):
                actions.append(ControlAction(
                    'set_work_mode',
                    f'B2: ForceCharge {soc_txt} → ~{target_txt} (harmonogram z mocą).',
                    {
                        'mode': 'ForceCharge',
                        'max_soc': rule.target_soc_percent,
                    },
                ))
            else:
                notes.append(
                    'Przed 22:00 (strefa szczytowa) — start FC przy apply o 22:00 (launchd).'
                )
            if rule.fc_minutes is not None and rule.fc_minutes > 0:
                notes.append(
                    f'Zaplanowany stop FC po ~{rule.fc_minutes:.0f} min (timer T6.2b).'
                )
        elif _night_should_release_windows(advice):
            actions.append(ControlAction(
                'set_work_mode',
                'Jutro duży dach — 22:00 zostaje buforem, bez pełnienia do 100%.',
                {'mode': 'SelfUse'},
            ))
            actions.append(ControlAction(
                'set_force_charge_windows',
                'Zgaś harmonogram ForceCharge: słoneczne jutro nie ma iść w eksport.',
                {'period1': _disabled_window(), 'period2': _disabled_window()},
            ))
            notes.append(
                '22:00 bez FC — jutrzejsze PV pokryje dzień. Pełna bateria zostaje na pochmurno i śnieg.'
            )
        else:
            actions.append(ControlAction(
                'noop',
                'B2: POMIŃ — brak nocnego ForceCharge.',
            ))

    elif advice.context == 'pre_cheap':
        pre_topup = compute_pre_cheap_topup(advice)
        if pre_topup and pre_cheap_apply_enabled() and winter and not weekend:
            soc_txt = f'{soc:.0f}%' if soc is not None else '?'
            actions.append(ControlAction(
                'set_force_charge_windows',
                'Bilans @13:00: okno 13–15 (doładuj teraz) + noc 22–6.',
                {'period1': night, 'period2': midday},
            ))
            actions.append(ControlAction(
                'set_work_mode',
                f'ForceCharge: SoC {soc_txt} → ~{pre_topup.target_soc:.0f}% przed 15:00.',
                {'mode': 'ForceCharge', 'max_soc': pre_topup.target_soc},
            ))
            notes.append(
                f'Południowy bilans: ΔSoC → {pre_topup.target_soc:.0f}%, '
                f'~{pre_topup.fc_minutes:.0f} min FC, stop {pre_topup.stop_at.strftime("%H:%M") if pre_topup.stop_at else "?"}'
            )
        elif not winter or weekend:
            actions.append(ControlAction('noop', 'Weekend / lato — okno 13–15 nie jest krytyczne.'))
        elif rec == 'ŁADUJ 13:00–15:00 (G12w TANIO)' or rec == 'ŁADUJ 13:00–15:00 (BILANS)':
            actions.append(ControlAction(
                'set_force_charge_windows',
                'Włącz okno południowe 13:00–15:00 + nocne 22:00–6:00.',
                {'period1': night, 'period2': midday},
            ))
        elif rec == 'SOC OK — POMIŃ FORCE CHARGE':
            actions.append(ControlAction(
                'set_force_charge_windows',
                f'SoC ≥ cel ({target:.0f}%) — wyłącz okno 13–15, zostaw noc 22–6.',
                {'period1': night, 'period2': midday_off},
            ))
        elif rec.startswith('ZIMNO') or rec.startswith('AWARIA'):
            actions.append(ControlAction(
                'set_force_charge_windows',
                'Po awarii / wysokim load — włącz oba okna tanio.',
                {'period1': night, 'period2': midday},
            ))
        else:
            actions.append(ControlAction('noop', f'Brak reguły sterowania dla: {rec}'))

    elif advice.context == 'peak':
        actions.append(ControlAction(
            'set_work_mode',
            'Szczyt G12w — autokonsumpcja, rozładowuj baterię zamiast importu.',
            {'mode': 'SelfUse'},
        ))
        if winter and soc is not None and soc < _env_float('BATTERY_SOC_MIN_EVENING', 50.0):
            notes.append('Niski SoC — jutro priorytet ładowania w 22–6 / 13–15.')
        if winter and (rec.startswith('ZIMNO') or rec.startswith('AWARIA')):
            actions.append(ControlAction(
                'set_min_soc',
                f'Zimowa rezerwa min. SoC {reserve:.0f}%.',
                {'min_soc': reserve},
            ))

    if state is not None:
        notes.extend(_diff_notes(actions, state))

    return ControlPlan(
        context=advice.context,
        as_of=advice.as_of,
        recommendation=rec,
        dry_run=True,
        actions=actions,
        notes=notes,
    )


def _diff_notes(actions: list[ControlAction], state: BatteryControlState) -> list[str]:
    """Porównaj plan z aktualnym stanem falownika."""
    diffs: list[str] = []
    for action in actions:
        if action.kind == 'set_work_mode':
            mode = action.params.get('mode')
            if mode and state.work_mode and mode != state.work_mode:
                diffs.append(f'Tryb: {state.work_mode} → {mode}')
        elif action.kind == 'set_force_charge_windows':
            p1 = action.params.get('period1')
            p2 = action.params.get('period2')
            if p1 and (p1.enabled != state.force_charge_1.enabled
                       or abs(p1.start_hour - state.force_charge_1.start_hour) > 0.01
                       or abs(p1.end_hour - state.force_charge_1.end_hour) > 0.01):
                diffs.append(f'Okno 1: {state.force_charge_1.label()} → {p1.label()}')
            if p2 and (p2.enabled != state.force_charge_2.enabled
                       or abs(p2.start_hour - state.force_charge_2.start_hour) > 0.01
                       or abs(p2.end_hour - state.force_charge_2.end_hour) > 0.01):
                diffs.append(f'Okno 2: {state.force_charge_2.label()} → {p2.label()}')
        elif action.kind == 'set_min_soc':
            target = action.params.get('min_soc')
            if target is not None and state.min_soc is not None and abs(target - state.min_soc) >= 1:
                diffs.append(f'Min SoC: {state.min_soc:.0f}% → {target:.0f}%')
    if not diffs:
        diffs.append('Stan falownika zgodny z planem (brak zmian).')
    return diffs


def fox_charge_power_w() -> int:
    """Moc okresu ForceCharge w harmonogramie. Bez niej (0 W) falownik nie bierze prądu z sieci."""
    return max(0, int(_env_float('BATTERY_FC_POWER_W', 12000)))


def periods_for_clock_window(
    start_hour: float,
    end_hour: float,
    *,
    max_soc: float,
    power_w: int | None = None,
    min_soc: float = 10.0,
) -> list[dict[str, Any]]:
    """Okno zegarowe → okresy harmonogramu Fox.

    Koniec jest wyłączny (15:00 → ostatnia minuta 14:59), tak jak ``set_period`` w foxesscloud.
    Okno przechodzące przez północ (22:00–01:00, 22:00–06:00) rozpada się na dwa okresy,
    bo jeden wpis harmonogramu nie może zawinąć doby.
    """
    start = float(start_hour) % 24.0
    end = float(end_hour)
    if end == 0 and start > 0:
        end = 24.0
    elif end <= start:
        end = end + 24.0
    if end <= start:
        return []
    spans = [(start, min(end, 24.0))]
    if end > 24.0:
        spans.append((0.0, end - 24.0))
    power = fox_charge_power_w() if power_w is None else int(power_w)
    target = int(round(max_soc))
    periods: list[dict[str, Any]] = []
    for span_start, span_end in spans:
        end_minute = int(round(span_end * 60)) - 1
        start_minute = int(round(span_start * 60))
        if end_minute < start_minute:
            continue
        periods.append({
            'startHour': start_minute // 60,
            'startMinute': start_minute % 60,
            'endHour': end_minute // 60,
            'endMinute': end_minute % 60,
            'workMode': 'ForceCharge',
            'isRemainMode': False,
            'extraParam': {
                'minSocOnGrid': int(min_soc),
                'maxSoc': target,
                'fdSoc': target,
                'fdPwr': power,
            },
        })
    return periods


def _enabled_charge_windows(plan: ControlPlan) -> list[ForceChargeWindow]:
    windows: list[ForceChargeWindow] = []
    for action in plan.actions:
        if action.kind != 'set_force_charge_windows':
            continue
        for key in ('period1', 'period2'):
            window = action.params.get(key)
            if isinstance(window, ForceChargeWindow) and window.enabled:
                windows.append(window)
    return windows


def _plan_intends_grid_charge(plan: ControlPlan) -> bool:
    return any(
        action.kind == 'set_work_mode' and action.params.get('mode') == 'ForceCharge'
        for action in plan.actions
    )


def _plan_max_soc(plan: ControlPlan) -> float | None:
    for action in plan.actions:
        if action.kind == 'set_work_mode' and action.params.get('mode') == 'ForceCharge':
            raw = action.params.get('max_soc')
            if raw is not None:
                return float(raw)
    return None


def schedule_groups_for_plan(plan: ControlPlan) -> list[dict[str, Any]]:
    """Okna z planu (pochmurno / słońce / 13–15) jako okresy harmonogramu z mocą.

    Pusty wynik: plan nie każe ładować z sieci. Decyzja „czy ładować” zostaje
    w advisorze; tu jest tylko tłumaczenie okien, które plan już wybrał.
    Samo zostawione okno nocne (SoC już w celu, bez trybu ForceCharge) nie startuje ładowania.
    """
    if plan.context not in ('evening', 'morning', 'pre_cheap'):
        return []
    if not _plan_intends_grid_charge(plan):
        return []
    windows = _enabled_charge_windows(plan)
    if not windows:
        return []
    max_soc = _plan_max_soc(plan)
    if max_soc is None:
        max_soc = 100.0
    groups: list[dict[str, Any]] = []
    for window in windows:
        groups.extend(periods_for_clock_window(
            window.start_hour,
            window.end_hour,
            max_soc=max_soc,
        ))
    return groups


def schedule_should_disable(plan: ControlPlan) -> bool:
    """Plan gasi okna (słoneczny poranek / rezygnacja z FC) — wyłącz też harmonogram."""
    if plan.context not in ('evening', 'morning', 'pre_cheap'):
        return False
    saw_windows = False
    for action in plan.actions:
        if action.kind != 'set_force_charge_windows':
            continue
        saw_windows = True
        for key in ('period1', 'period2'):
            window = action.params.get(key)
            if isinstance(window, ForceChargeWindow) and window.enabled:
                return False
    return saw_windows


def execute_plan(
    plan: ControlPlan,
    controller: FoxEssControl | None = None,
    *,
    dry_run: bool = True,
) -> list[dict[str, Any]]:
    controller = controller or FoxEssControl()
    results: list[dict[str, Any]] = []
    plan.dry_run = dry_run
    fox_schedule_on = False
    if not dry_run:
        try:
            fox_schedule_on = bool(controller.read_state().schedule_enabled)
        except (ValueError, RuntimeError):
            fox_schedule_on = False

    charge_groups = schedule_groups_for_plan(plan)
    release_schedule = schedule_should_disable(plan) and not charge_groups
    if charge_groups:
        plan.notes.append(
            'Ładowanie idzie harmonogramem Fox (fdPwr + maxSoc). '
            'Tryb ForceCharge ten falownik pomija, a force=1 gasi harmonogram.'
        )
        try:
            results.append(controller.set_work_schedule(
                charge_groups,
                enable=True,
                dry_run=dry_run,
            ))
        except RuntimeError as exc:
            plan.notes.append(f'⚠️ set_schedule: {exc}')
            results.append({
                'dry_run': dry_run,
                'action': 'set_work_schedule',
                'error': str(exc),
            })
    elif release_schedule:
        plan.notes.append('Plan gasi okna ForceCharge — wyłączam harmonogram.')
        try:
            results.append(controller.set_work_schedule(
                [],
                enable=False,
                dry_run=dry_run,
            ))
        except RuntimeError as exc:
            plan.notes.append(f'⚠️ set_schedule: {exc}')
            results.append({
                'dry_run': dry_run,
                'action': 'set_work_schedule',
                'error': str(exc),
            })

    for action in plan.actions:
        if action.kind == 'noop':
            results.append({'dry_run': dry_run, 'action': 'noop', 'description': action.description})
            continue
        if action.kind == 'set_force_charge_windows':
            if charge_groups or release_schedule:
                results.append({
                    'dry_run': True,
                    'action': 'noop',
                    'skipped': True,
                    'reason': 'fox_schedule_periods' if charge_groups else 'fox_schedule_disabled',
                })
                continue
            # set_charge z force=1 wyłącza harmonogram, a to jedyna droga ładowania z sieci.
            if fox_schedule_on:
                plan.notes.append(
                    'Harmonogram FoxESS włączony — nie ruszam set_charge (zostawiłby fdPwr=0 albo zgasił okres).'
                )
                results.append({
                    'dry_run': dry_run,
                    'action': 'set_force_charge_windows',
                    'skipped': True,
                    'reason': 'fox_schedule_enabled',
                })
                continue
            try:
                results.append(controller.set_force_charge_windows(
                    period1=action.params.get('period1'),
                    period2=action.params.get('period2'),
                    dry_run=dry_run,
                    force=0,
                ))
            except RuntimeError as exc:
                plan.notes.append(f'⚠️ set_charge: {exc}')
                results.append({
                    'dry_run': dry_run,
                    'action': 'set_force_charge_windows',
                    'error': str(exc),
                })
        elif action.kind == 'set_work_mode':
            mode = action.params['mode']
            if charge_groups and mode == 'ForceCharge':
                results.append({
                    'dry_run': True,
                    'action': 'noop',
                    'skipped': True,
                    'reason': 'inverter_ignores_forcecharge_mode',
                })
                continue
            results.append(controller.set_work_mode(
                mode,
                dry_run=dry_run,
                force=0,
            ))
        elif action.kind == 'set_min_soc':
            results.append(controller.set_min_soc(
                min_soc=action.params.get('min_soc'),
                min_soc_on_grid=action.params.get('min_soc_on_grid'),
                dry_run=dry_run,
            ))
    return results


def plan_and_run(
    context: Context,
    *,
    as_of: datetime | None = None,
    dry_run: bool = True,
    read_state: bool = True,
    phase: ControlPhase = 'run',
) -> tuple[BatteryAdvice, ControlPlan, list[dict[str, Any]]]:
    advice = advise(context, as_of=as_of)
    if not dry_run:
        deny = validate_apply_request(context, advice, phase='apply' if phase == 'apply' else phase)
        if deny:
            plan = build_plan(advice)
            plan.notes.append(f'⛔ Apply zablokowane: {deny}')
            return advice, plan, []

    state = None
    controller = None
    if read_state:
        try:
            controller = FoxEssControl()
            state = controller.read_state()
        except (ValueError, RuntimeError) as exc:
            plan = build_plan(advice)
            plan.notes.append(f'⚠️ Brak odczytu stanu FoxESS: {exc}')
            return advice, plan, []

    plan = build_plan(advice, state=state)
    plan.dry_run = dry_run
    results = execute_plan(plan, controller, dry_run=dry_run)
    if not dry_run and phase == 'apply':
        record_evening_session_after_apply(advice, plan, results)
    return advice, plan, results


def format_plan(advice: BatteryAdvice, plan: ControlPlan, results: list[dict[str, Any]]) -> str:
    mode = 'DRY-RUN' if plan.dry_run else 'APPLY'
    ctx_labels = {
        'morning': 'PORANEK — sterowanie baterią',
        'pre_cheap': 'PRZED 13:00 — ForceCharge',
        'peak': 'SZCZYT — tryb SelfUse',
        'evening': 'WIECZÓR — plan B2 (22:00–6:00)',
    }
    lines = [
        '=' * 60,
        f'FOXESS CONTROL [{mode}] — {ctx_labels[plan.context]}',
        f'{advice.as_of.strftime("%Y-%m-%d %H:%M")}  |  rekomendacja: {plan.recommendation}',
        '=' * 60,
    ]
    if not plan.has_changes():
        lines.append('→ Brak akcji sterujących (noop).')
    for i, action in enumerate(plan.actions, 1):
        prefix = '○' if action.kind == 'noop' else '→'
        lines.append(f'{prefix} [{i}] {action.description}')
    if plan.notes:
        lines.append('')
        lines.append('  --- Stan / uwagi ---')
        for note in plan.notes:
            lines.append(f'  • {note}')
    if results:
        applied = sum(1 for r in results if r.get('action') != 'noop' and not r.get('dry_run'))
        lines.append('')
        lines.append(f'  Wykonano API: {applied} akcji')
    lines.append('=' * 60)
    return '\n'.join(lines)


def append_control_log(
    advice: BatteryAdvice,
    plan: ControlPlan,
    results: list[dict[str, Any]],
    path: str | None = None,
    *,
    phase: ControlPhase = 'run',
    planned_stop: datetime | None = None,
) -> None:
    path = path or LOG_FILE
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    stop_at = planned_stop or planned_stop_at(advice)
    row = {
        'logged_at': advice.as_of.isoformat(timespec='seconds'),
        'context': plan.context,
        'phase': phase,
        'dry_run': plan.dry_run,
        'recommendation': plan.recommendation,
        'soc_percent': advice.snapshot.soc_percent,
        'planned_stop_at': stop_at.isoformat(timespec='seconds') if stop_at else '',
        'actions': '; '.join(a.description for a in plan.actions if a.kind != 'noop'),
        'applied_count': sum(
            1 for r in results if r.get('action') != 'noop' and not r.get('dry_run')
        ),
    }
    df = pd.DataFrame([row])
    header = not os.path.exists(path)
    df.to_csv(path, mode='a', header=header, index=False)
