"""Plan ładowania między oknami G12w — pobór vs prognoza PV (priorytet magazynu z paneli).

Używany przez ``battery_advisor`` (szczegóły), ``battery_control`` (apply @4:00 / @12:00)
oraz sugestie T4.20. Logika: ile energii brakuje do następnej drogiej strefy po odjęciu
prognozowanego PV trafiającego do baterii; ładuj z sieci tylko w taniej strefie i tylko
gdy luka przekracza próg opłacalności cyklu.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from src.optimization.g12w_tariff import is_cheap_zone, is_public_holiday, is_weekend

Context = Literal['morning', 'pre_cheap', 'peak', 'evening']

# Pon–pt drogie odcinki (h): 6–12 i 15–21 → 14 h / dobę roboczą
EXPENSIVE_HOURS_WEEKDAY = 14.0


@dataclass
class InterWindowChargePlan:
    triggered: bool
    context: Context
    horizon_label: str
    load_kwh: float
    pv_to_battery_kwh: float
    usable_kwh: float
    deficit_kwh: float
    target_soc_percent: float | None
    grid_charge_kwh: float | None
    fc_minutes: float | None
    stop_at: datetime | None
    skip_reason: str = ''


def inter_window_auto_enabled() -> bool:
    return os.getenv('BATTERY_INTER_WINDOW_AUTO', '1').strip().lower() in ('1', 'true', 'yes')


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, str(default)).strip()
    try:
        return float(raw)
    except ValueError:
        return default


def pv_capture_fraction() -> float:
    """Ułamek prognozy PV w drogiej strefie trafiający do magazynu (reszta = bezpośrednio load)."""
    return min(1.0, max(0.0, _env_float('BATTERY_PV_CAPTURE_FRACTION', 0.85)))


def min_grid_charge_kwh() -> float:
    return _env_float('BATTERY_FC_MIN_WORTH_KWH', 2.0)


def soc_margin_pp() -> float:
    return _env_float('BATTERY_INTER_WINDOW_SOC_MARGIN_PP', 5.0)


def horizon_until_13() -> bool:
    return os.getenv('BATTERY_INTER_WINDOW_HORIZON', 'until_13').strip().lower() in (
        'until_13',
        '13',
        'morning',
    )


def _capacity_kwh(capacity_kwh: float | None) -> float:
    if capacity_kwh is not None and capacity_kwh > 0:
        return float(capacity_kwh)
    return _env_float('BATTERY_CAPACITY_KWH', 10.36)


def _horizon_hours(context: Context, as_of: datetime) -> tuple[int, int, str]:
    """Zwraca (h_start, h_end_exclusive, opis) dla bilansu w drogiej strefie."""
    if context == 'morning':
        return 6, 13, 'droga 6:00–13:00 (do tanio 13–15)'
    if context == 'pre_cheap':
        return 15, 22, 'droga 15:00–22:00 (szczyt wieczorny)'
    if context == 'evening':
        return 6, 13, 'jutro droga 6:00–13:00'
    return max(as_of.hour, 6), 22, 'reszta dnia droga'


def _forecast_pv_kwh(
    target_day: str,
    h_start: int,
    h_end: int,
    *,
    as_of: datetime,
) -> float:
    from src.optimization.battery_advisor import _predict_one_day, _sum_hours
    from src.weather.forecast_routing import predict_day_frame_cs4_cached, resolve_forecast_display

    db_path = os.getenv('ENERGY_DB_PATH', 'data/energy_model.db')
    routing = resolve_forecast_display(target_day, db_path=db_path)
    if routing.uses_cs4:
        day_df = predict_day_frame_cs4_cached(
            target_day,
            as_of=as_of,
            db_path=db_path,
            hybrid_today=True,
            use_actual_pv=True,
        )
    else:
        pred = _predict_one_day(
            target_day,
            as_of,
            db_path,
            hybrid_today=True,
            use_actual_pv=True,
        )
        day_df = pred[pred['day'] == target_day].copy() if not pred.empty else pred
    if day_df.empty:
        return 0.0
    h_lo = max(h_start, as_of.hour if target_day == as_of.date().isoformat() else h_start)
    if h_lo >= h_end:
        return 0.0
    # _sum_hours inclusive end; używamy h_end-1
    return max(0.0, _sum_hours(day_df, h_lo, max(h_lo, h_end - 1)))


def _segment_load_kwh(
    *,
    h_start: int,
    h_end: int,
    temp_c: float | None,
    day_pv_kwh: float | None,
    morning_buffers_kwh: float,
) -> float:
    from src.optimization.battery_advisor import (
        PV_IN_PEAK_FRACTION,
        estimate_expensive_load_kwh,
    )

    hours = max(0, h_end - h_start)
    if hours <= 0:
        return 0.0
    load_day = estimate_expensive_load_kwh(temp_c if temp_c is not None else 5.0)
    if day_pv_kwh is not None:
        load_day = max(0.0, load_day - PV_IN_PEAK_FRACTION * max(0.0, day_pv_kwh))
    prorated = load_day * (hours / EXPENSIVE_HOURS_WEEKDAY)
    if h_start < 13:
        prorated = max(prorated, morning_buffers_kwh)
    return round(prorated, 2)


def _morning_buffers_kwh() -> float:
    from src.optimization.battery_advisor import (
        _morning_buffer_boiler_kwh,
        _morning_buffer_breakfast_kwh,
        _morning_buffer_heat_kwh,
    )

    return (
        _morning_buffer_breakfast_kwh()
        + _morning_buffer_boiler_kwh()
        + _morning_buffer_heat_kwh()
    )


def compute_inter_window_charge_plan(
    *,
    context: Context,
    as_of: datetime,
    soc_percent: float | None,
    reserve_percent: float,
    season: str,
    temp_c: float | None = None,
    day_pv_kwh: float | None = None,
    capacity_kwh: float | None = None,
) -> InterWindowChargePlan:
    """Bilans: pobór w następnej drogiej strefie − PV do magazynu − energia w baterii."""
    def _skip(reason: str) -> InterWindowChargePlan:
        return InterWindowChargePlan(
            triggered=False,
            context=context,
            horizon_label='',
            load_kwh=0.0,
            pv_to_battery_kwh=0.0,
            usable_kwh=0.0,
            deficit_kwh=0.0,
            target_soc_percent=None,
            grid_charge_kwh=None,
            fc_minutes=None,
            stop_at=None,
            skip_reason=reason,
        )

    if not inter_window_auto_enabled():
        return _skip('disabled')

    if season not in ('winter', 'autumn', 'spring'):
        return _skip('season_summer')

    if is_weekend(as_of.date()) or is_public_holiday(as_of.date()):
        return _skip('weekend')

    if soc_percent is None:
        return _skip('no_soc')

    if context == 'morning' and not is_cheap_zone(as_of):
        return _skip('not_cheap_window')
    if context == 'pre_cheap' and as_of.hour >= 15:
        return _skip('past_midday_window')

    target_day = as_of.date().isoformat()
    if context == 'evening':
        target_day = (as_of.date() + timedelta(days=1)).isoformat()

    h_start, h_end, label = _horizon_hours(context, as_of)
    if horizon_until_13() and context == 'evening':
        h_end = min(h_end, 13)

    pv_raw = _forecast_pv_kwh(target_day, h_start, h_end, as_of=as_of)
    pv_batt = round(pv_raw * pv_capture_fraction(), 2)
    load_kwh = _segment_load_kwh(
        h_start=h_start,
        h_end=h_end,
        temp_c=temp_c,
        day_pv_kwh=day_pv_kwh,
        morning_buffers_kwh=_morning_buffers_kwh() if h_start < 13 else 0.0,
    )

    cap = _capacity_kwh(capacity_kwh)
    usable = max(0.0, (float(soc_percent) - float(reserve_percent)) / 100.0 * cap)
    need_stored = max(0.0, load_kwh - pv_batt)
    deficit = max(0.0, need_stored - usable)

    target_soc = min(
        100.0,
        float(reserve_percent) + (need_stored / cap) * 100.0 + soc_margin_pp(),
    )
    grid_kwh = max(0.0, (target_soc - float(soc_percent)) / 100.0 * cap)

    if deficit < min_grid_charge_kwh() or grid_kwh < min_grid_charge_kwh() * 0.5:
        return InterWindowChargePlan(
            triggered=False,
            context=context,
            horizon_label=label,
            load_kwh=load_kwh,
            pv_to_battery_kwh=pv_batt,
            usable_kwh=round(usable, 2),
            deficit_kwh=round(deficit, 2),
            target_soc_percent=round(target_soc, 1),
            grid_charge_kwh=round(grid_kwh, 2),
            fc_minutes=None,
            stop_at=None,
            skip_reason='pv_covers_or_wear',
        )

    from src.optimization.battery_advisor import fc_minutes_for_delta_soc

    delta = max(0.0, target_soc - float(soc_percent))
    minutes = fc_minutes_for_delta_soc(delta)
    stop_at: datetime | None = None
    if context == 'morning':
        stop = as_of.replace(hour=6, minute=0, second=0, microsecond=0)
        if as_of >= stop:
            stop = stop + timedelta(days=1)
        max_min = max(0.0, (stop - as_of).total_seconds() / 60.0)
        minutes = min(minutes, max_min)
        stop_at = as_of + timedelta(minutes=minutes)
        if stop_at > stop:
            stop_at = stop
    elif context == 'pre_cheap':
        stop = as_of.replace(hour=15, minute=0, second=0, microsecond=0)
        max_min = max(0.0, (stop - as_of).total_seconds() / 60.0)
        minutes = min(minutes, max_min)
        stop_at = as_of + timedelta(minutes=minutes)
        if stop_at > stop:
            stop_at = stop

    if minutes < 3.0:
        return InterWindowChargePlan(
            triggered=False,
            context=context,
            horizon_label=label,
            load_kwh=load_kwh,
            pv_to_battery_kwh=pv_batt,
            usable_kwh=round(usable, 2),
            deficit_kwh=round(deficit, 2),
            target_soc_percent=round(target_soc, 1),
            grid_charge_kwh=round(grid_kwh, 2),
            fc_minutes=minutes,
            stop_at=stop_at,
            skip_reason='no_time_in_cheap_window',
        )

    return InterWindowChargePlan(
        triggered=True,
        context=context,
        horizon_label=label,
        load_kwh=load_kwh,
        pv_to_battery_kwh=pv_batt,
        usable_kwh=round(usable, 2),
        deficit_kwh=round(deficit, 2),
        target_soc_percent=round(target_soc, 1),
        grid_charge_kwh=round(grid_kwh, 2),
        fc_minutes=round(minutes, 1),
        stop_at=stop_at,
        skip_reason='',
    )
