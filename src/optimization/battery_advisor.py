"""
Rekomendacje ładowania baterii — G12w + prognoza PV (tryb zimowy / letni).

Konteksty (zgodne z harmonogramem launchd):
  morning    — 5:00  tanio do 6:00; czy ładować z sieci czy poczekać na PV?
  pre_cheap  — 12:00 przed oknem 13:00–15:00 (tanio G12w pn–pt)
  peak       — 16:00 przed szczytem wieczornym 15:00–22:00
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal

import pandas as pd
import sqlite3

from src.optimization.g12w_tariff import classify_zone, is_public_holiday, is_weekend

Context = Literal['morning', 'pre_cheap', 'peak']

WINTER_MONTHS = {11, 12, 1, 2}  # XI–II; III–V = wiosna (§E); X = jesień (B1)
SPRING_MONTHS = {3, 4, 5}
# Jesień: 15.09–31.10 (PLAN_BATERIA §A / §D)
AUTUMN_MONTH_START = 9
AUTUMN_DAY_START = 15

LOG_FILE = 'data/processed/battery_advisor_log.csv'
OUTAGE_LOG_FILE = 'data/processed/battery_outage_log.csv'
# Pojemność magazynu (fakt instalacji) — 1% SoC ≈ 0,104 kWh.
NOMINAL_CAPACITY_KWH = 10.36
# 25–26.08: ForceCharge 22:00–22:30, 24% → 75% ≈ +50 pp / 30 min.
# 50% × 10,36 kWh = 5,18 kWh / 0,5 h ≈ 10,4 kW.
FC_MINUTES_PER_50_SOC = 30.0
FC_SOC_PER_30_MIN = 50.0
# load_exp ≈ 18 − 1.0×Tśr (dni robocze zima X.2025–III.2026); ~70% PV w drogiej G12w.
LOAD_EXP_INTERCEPT_KWH = 18.0
LOAD_EXP_SLOPE_PER_C = -1.0
PV_IN_PEAK_FRACTION = 0.70


@dataclass
class BatterySnapshot:
    timestamp: str | None
    soc_percent: float | None
    battery_power_kw: float | None
    pv_power_kw: float | None
    load_power_kw: float | None
    age_hours: float | None


@dataclass
class PvOutlook:
    sunrise_hour: float | None
    first_production_hour: int | None
    morning_forecast_kwh: float
    window_forecast_kwh: float
    remaining_forecast_kwh: float
    actual_so_far_kwh: float


@dataclass
class ChargeTonightCloudyRule:
    """Reguła B2: nocne FC 22–6 (lato krótki cap / zima T×PV) — advise-only."""

    triggered: bool
    soc_percent: float | None
    tomorrow_pv_kwh: float | None
    soc_below: float
    weak_pv_below: float
    recommendation: str
    title: str
    body: str
    target_soc_percent: float | None = None
    fc_minutes: float | None = None
    tomorrow_temp_c: float | None = None
    estimated_gap_kwh: float | None = None
    skip_reason: str = ''


@dataclass
class Soc16HoldReserveRule:
    """BAT.3: SoC@16 < min wieczór → trzymaj rezerwę / ForceCharge 13–15 albo 22–6."""

    triggered: bool
    hour_passed: bool
    soc_percent: float | None
    min_evening_percent: float
    reserve_percent: float
    in_afternoon_window: bool
    recommendation: str
    title: str
    body: str


@dataclass
class WinterAfternoonFcRule:
    """Zima: ForceCharge 13–15 gdy niski SoC i słabe PV / zimno (historia XI–II.2025/26)."""

    triggered: bool
    soc_percent: float | None
    today_pv_kwh: float | None
    today_temp_c: float | None
    soc_below: float
    weak_pv_below: float
    mild_temp_below: float
    recommendation: str
    title: str
    body: str
    skip_reason: str = ''


@dataclass
class BelowReserveWaitCheapRule:
    """Poniżej rezerwy w drogiej G12w → nie ładuj z sieci teraz; poczekaj na tanie okno."""

    triggered: bool
    in_cheap_zone: bool
    next_cheap_window: str
    soc_percent: float | None
    reserve_percent: float
    recommendation: str
    title: str
    body: str


@dataclass
class ResilienceOutlook:
    """Szacunek autonomii baterii (zima / przerwy w zasilaniu)."""
    capacity_kwh: float
    usable_kwh: float
    reserve_soc_percent: float
    avg_load_kw: float
    peak_load_kw: float
    hours_until_empty: float | None
    minutes_until_empty: float | None
    high_load_warning: bool
    outage_last_night: bool
    outage_start: str | None
    outage_end: str | None
    outage_min_soc: float | None
    notes: list[str]


@dataclass
class BatteryAdvice:
    context: Context
    as_of: datetime
    target_day: str
    season: Literal['winter', 'summer', 'autumn', 'spring']
    tariff_zone: int
    tariff_label: str
    snapshot: BatterySnapshot
    pv: PvOutlook
    resilience: ResilienceOutlook | None
    recommendation: str
    action: str
    details: list[str]


def is_winter_season(d: date | None = None) -> bool:
    """Zima kalendarzowa: XI–II (§E — marzec = wiosna)."""
    d = d or date.today()
    return d.month in WINTER_MONTHS


def is_autumn_season(d: date | None = None) -> bool:
    """Jesień B1/§D: 15.09–31.10."""
    d = d or date.today()
    if d.month == AUTUMN_MONTH_START and d.day >= AUTUMN_DAY_START:
        return True
    return d.month == 10


def is_spring_season(d: date | None = None) -> bool:
    """Wiosna §E: III–V (FC jak lato, próg PV ~8)."""
    d = d or date.today()
    return d.month in SPRING_MONTHS


def is_b2_night_season(d: date | None = None) -> bool:
    """B2 T×PV: tylko zima XI–II. Jesień ma osobną ścieżkę PV (§D)."""
    return is_winter_season(d)


def _db_path() -> str:
    return os.getenv('DATABASE_PATH', 'data/energy_model.db')


def get_battery_snapshot(
    db_path: str | None = None,
    *,
    target_day: str | None = None,
    max_age_hours: float = 6.0,
) -> BatterySnapshot:
    db_path = db_path or _db_path()
    target_day = target_day or date.today().isoformat()
    empty = BatterySnapshot(None, None, None, None, None, None)
    if not os.path.exists(db_path):
        return empty

    conn = sqlite3.connect(db_path, timeout=2.0)
    row = conn.execute(
        '''
        SELECT timestamp, battery_soc_percent, battery_power_kw, pv_power_kw, load_power_kw
        FROM foxess_data
        WHERE date(timestamp) = ?
        ORDER BY timestamp DESC
        LIMIT 1
        ''',
        (target_day,),
    ).fetchone()
    if not row:
        row = conn.execute(
            '''
            SELECT timestamp, battery_soc_percent, battery_power_kw, pv_power_kw, load_power_kw
            FROM foxess_data
            ORDER BY timestamp DESC
            LIMIT 1
            '''
        ).fetchone()
    conn.close()

    if not row or row[0] is None:
        return empty

    ts = str(row[0]).replace(' ', 'T')[:19]
    last = datetime.fromisoformat(ts)
    age = (datetime.now() - last).total_seconds() / 3600
    if age > max_age_hours:
        return BatterySnapshot(ts, row[1], row[2], row[3], row[4], round(age, 2))

    return BatterySnapshot(ts, row[1], row[2], row[3], row[4], round(age, 2))


def _sum_hours(df: pd.DataFrame, h_start: int, h_end: int) -> float:
    if df.empty:
        return 0.0
    mask = (df['hour'] >= h_start) & (df['hour'] <= h_end)
    return float(df.loc[mask, 'predicted_kwh'].sum())


def get_pv_outlook(
    target_day: str,
    as_of: datetime | None = None,
    db_path: str | None = None,
) -> PvOutlook:
    as_of = as_of or datetime.now()
    db_path = db_path or _db_path()

    from src.models.pv_hourly_predictor import PVHourlyPredictor

    predictor = PVHourlyPredictor()
    predictor.load()

    pred = predictor.predict_days(
        days_ahead=1,
        db_path=db_path,
        from_date=date.fromisoformat(target_day),
        hybrid_today=True,
        use_actual_pv=True,
        as_of=as_of,
    )
    day_df = pred[pred['day'] == target_day].copy() if not pred.empty else pred

    sunrise = float(day_df['sunrise_hour'].iloc[0]) if not day_df.empty else None
    first_h = None
    if not day_df.empty:
        prod = day_df[day_df['predicted_kwh'] > 0.08]
        if not prod.empty:
            first_h = int(prod['hour'].min())

    morning_end = 12 if as_of.hour <= 12 else min(as_of.hour, 12)
    morning = _sum_hours(day_df, 5, morning_end)
    cheap_window = _sum_hours(day_df, 13, 15)
    remaining = _sum_hours(day_df, max(as_of.hour, 5), 21)

    actual = 0.0
    if date.fromisoformat(target_day) <= as_of.date():
        from src.models.pv_hourly_predictor import load_actual_pv_hourly

        act = load_actual_pv_hourly(db_path, target_day, as_of=as_of)
        if not act.empty:
            actual = float(act['pv_kwh_hour'].sum())

    return PvOutlook(
        sunrise_hour=sunrise,
        first_production_hour=first_h,
        morning_forecast_kwh=round(morning, 2),
        window_forecast_kwh=round(cheap_window, 2),
        remaining_forecast_kwh=round(remaining, 2),
        actual_so_far_kwh=round(actual, 2),
    )


def _soc_target() -> float:
    return float(os.getenv('BATTERY_SOC_TARGET', '80'))


def _soc_min_evening() -> float:
    return float(os.getenv('BATTERY_SOC_MIN_EVENING', '50'))


def _morning_pv_enough_kwh() -> float:
    return float(os.getenv('BATTERY_MORNING_PV_ENOUGH_KWH', '3.0'))


def _soc_charge_tonight_below() -> float:
    """Poniżej tego SoC (wieczór) rozważamy ładowanie nocne przy słabym jutrze."""
    return float(os.getenv('BATTERY_SOC_CHARGE_TONIGHT_BELOW', os.getenv('BATTERY_SOC_MIN_EVENING', '50')))


def _cloudy_day_pv_kwh() -> float:
    """Suma dzienna PV poniżej tego progu = dzień „pochmurny / słaby” (jak 25–26.08 ~11–14)."""
    return float(os.getenv('BATTERY_CLOUDY_DAY_PV_KWH', '18'))


def _summer_fc_max_minutes() -> float:
    """Lato: jeśli już ładować w nocy — max minut (25–26.08: 30 min ≈ +50 pp)."""
    return float(os.getenv('BATTERY_SUMMER_FC_MAX_MINUTES', '15'))


def _summer_fc_delta_soc() -> float:
    """Lato: przyrost SoC na krótki FC (~15 min ≈ +25 pp przy ~10 kW)."""
    return float(os.getenv('BATTERY_SUMMER_FC_DELTA_SOC', '25'))


def _summer_tomorrow_max_kwh() -> float:
    """Lato: jutro do tylu kWh nadal obowiązuje podłoga 20% + cap 15 min (nie pełnić)."""
    return float(os.getenv('BATTERY_SUMMER_TOMORROW_MAX_KWH', '10'))


def _b2_pv_skip_kwh() -> float:
    """Zima B2: przy T ≥ 0°C dach ≥ tyle kWh zwykle pokrywa szczyt — nie pełnić."""
    return float(os.getenv('BATTERY_B2_PV_SKIP_KWH', '12'))


def _b2_mild_weak_pv_kwh() -> float:
    """Zima B2: T ≥ 5°C i PV poniżej tego → ładuj do ~80%."""
    return float(os.getenv('BATTERY_B2_MILD_WEAK_PV_KWH', '8'))


def _autumn_pv_charge_kwh() -> float:
    """Jesień §D: ładuj nocą gdy PV jutro poniżej tego (fakt: PV<8 → luka ~7 kWh)."""
    return float(os.getenv('BATTERY_AUTUMN_PV_CHARGE_KWH', '8'))


def _autumn_target_soc() -> float:
    return float(os.getenv('BATTERY_AUTUMN_TARGET_SOC', '85'))


def _spring_tomorrow_max_kwh() -> float:
    """Wiosna §E: FC tylko przy bardzo słabym PV (jak lato, próg 8 nie 10)."""
    return float(os.getenv('BATTERY_SPRING_TOMORROW_MAX_KWH', '8'))


def _spring_soc_charge_below() -> float:
    """Wiosna: ładuj tylko gdy SoC poniżej tego (plan: ~40%)."""
    return float(os.getenv('BATTERY_SPRING_SOC_CHARGE_BELOW', '40'))


def _fc_minutes_per_50_soc() -> float:
    return float(os.getenv('BATTERY_FC_MINUTES_PER_50_SOC', str(FC_MINUTES_PER_50_SOC)))


def _fc_soc_per_30_min() -> float:
    return float(os.getenv('BATTERY_FC_SOC_PER_30_MIN', str(FC_SOC_PER_30_MIN)))


def fc_minutes_for_delta_soc(delta_soc: float) -> float:
    """Czas ForceCharge: 30 min ≈ +50 pp SoC (fakt 25–26.08)."""
    per_30 = _fc_soc_per_30_min()
    minutes_30 = _fc_minutes_per_50_soc()
    if per_30 <= 0:
        return 0.0
    return round(max(0.0, delta_soc) * minutes_30 / per_30, 1)


def estimate_expensive_load_kwh(t_mean_c: float) -> float:
    intercept = float(os.getenv('BATTERY_LOAD_EXP_INTERCEPT_KWH', str(LOAD_EXP_INTERCEPT_KWH)))
    slope = float(os.getenv('BATTERY_LOAD_EXP_SLOPE_PER_C', str(LOAD_EXP_SLOPE_PER_C)))
    return max(8.0, intercept + slope * t_mean_c)


def estimate_peak_gap_kwh(t_mean_c: float, tomorrow_pv_kwh: float) -> float:
    frac = float(os.getenv('BATTERY_PV_IN_PEAK_FRACTION', str(PV_IN_PEAK_FRACTION)))
    return estimate_expensive_load_kwh(t_mean_c) - frac * max(0.0, tomorrow_pv_kwh)


def winter_night_target_soc(
    t_mean_c: float | None,
    tomorrow_pv_kwh: float,
) -> float | None:
    """Docelowy SoC po FC 22–6 zimą (§C). None = nie pełnić (zostaw rezerwę / dach)."""
    skip_pv = _b2_pv_skip_kwh()
    mild_weak = _b2_mild_weak_pv_kwh()
    if t_mean_c is None:
        return 90.0 if tomorrow_pv_kwh < skip_pv else None
    if t_mean_c < 0:
        return 95.0
    if t_mean_c < 5:
        return 95.0 if tomorrow_pv_kwh < skip_pv else None
    if tomorrow_pv_kwh < mild_weak:
        return 80.0
    if tomorrow_pv_kwh >= skip_pv:
        return None
    return 80.0


def autumn_night_target_soc(tomorrow_pv_kwh: float) -> float | None:
    """Jesień §D: steruje PV (nie T). PV < ~8 → cel ~85%; inaczej dach / pomiń."""
    if tomorrow_pv_kwh < _autumn_pv_charge_kwh():
        return _autumn_target_soc()
    return None


def estimate_autumn_peak_gap_kwh(tomorrow_pv_kwh: float) -> float:
    """Przybliżenie luki szczytu jesienią: load_exp ~9,5; ~70% PV w drogiej (§D)."""
    load = float(os.getenv('BATTERY_AUTUMN_LOAD_EXP_KWH', '9.5'))
    frac = float(os.getenv('BATTERY_AUTUMN_PV_IN_PEAK_FRACTION', '0.70'))
    return load - frac * max(0.0, tomorrow_pv_kwh)


def _b2_capacity_kwh(capacity_kwh: float | None) -> float:
    if capacity_kwh is not None:
        return float(capacity_kwh)
    env = os.getenv('BATTERY_CAPACITY_KWH', '').strip()
    if env:
        return float(env)
    return float(os.getenv('BATTERY_CAPACITY_KWH_DEFAULT', str(NOMINAL_CAPACITY_KWH)))


def _charge_worth_vs_wear(
    *,
    energy_kwh: float,
    delta_soc: float,
    gap_kwh: float | None,
    frost: bool,
    below_reserve: bool,
) -> bool:
    """False = drobny brak vs cykl LFP; True = ładuj (albo bezpieczeństwo / mróz)."""
    if below_reserve or frost:
        return True
    min_kwh = float(os.getenv('BATTERY_FC_MIN_WORTH_KWH', '2.0'))
    min_delta = float(os.getenv('BATTERY_FC_MIN_DELTA_SOC', '15'))
    if delta_soc < min_delta or energy_kwh < min_kwh:
        return False
    if gap_kwh is not None and gap_kwh < min_kwh:
        return False
    spread = float(os.getenv('BATTERY_TARIFF_SPREAD_PLN_PER_KWH', '0.36'))
    cycle = float(os.getenv('BATTERY_CYCLE_COST_PLN_PER_KWH', '0.30'))
    # Spread G12w ~0,36 zł/kWh, cykl LFP ~0,30 — małe doładowanie prawie nic nie zostawia.
    if spread <= cycle + 0.08 and energy_kwh < 3.0:
        return False
    return True


def _cap_fc_minutes(minutes: float, fc_max_minutes: float | None) -> float:
    if fc_max_minutes is None or fc_max_minutes <= 0:
        return round(max(0.0, minutes), 1)
    return round(min(max(0.0, minutes), float(fc_max_minutes)), 1)


def _delta_soc_for_minutes(minutes: float) -> float:
    """Przyrost SoC z czasu FC (30 min ≈ +50 pp)."""
    return round(max(0.0, minutes) * _fc_soc_per_30_min() / max(1.0, _fc_minutes_per_50_soc()), 1)


def _fc_end_clock(start_hour: int, minutes: float) -> tuple[int, int]:
    end_min = int(round(minutes))
    end_h, end_m = divmod((start_hour * 60 + end_min) % (24 * 60), 60)
    return end_h, end_m


def evaluate_charge_tonight_cloudy(
    *,
    soc_percent: float | None,
    tomorrow_pv_kwh: float | None,
    as_of: datetime | None = None,
    soc_below: float | None = None,
    weak_pv_below: float | None = None,
    tomorrow_temp_c: float | None = None,
    capacity_kwh: float | None = None,
    fc_max_minutes: float | None = None,
    night_start_hour: int = 22,
) -> ChargeTonightCloudyRule:
    """Czysta reguła produktowa (bez I/O) — advise-only.

    - Zima XI–II (§C): Tśr jutro + PV → cel SoC i minuty (30 min ≈ +50 pp).
    - Jesień 15.09–31.10 (§D): PV jutro < ~8 kWh → cel ~85%; T nie filtruje.
    - Wiosna III–V (§E) / lato: krótki FC gdy SoC niski i jutro słabe PV.
    Drobny brak (< ~2 kWh / < 15 pp) pomijamy — cykl vs spread G12w.
    ``fc_max_minutes`` / ``night_start_hour`` — preferencje UI (nie pełnić całej baterii).
    """
    as_of = as_of or datetime.now()
    start_h = int(night_start_hour) if 0 <= int(night_start_hour) <= 23 else 22
    cal = resolve_calendar_season(as_of.date())
    winter_b2 = cal == 'winter'
    autumn = cal == 'autumn'
    spring = cal == 'spring'

    if soc_below is None:
        if winter_b2:
            soc_below = _soc_reserve_winter()
        elif autumn:
            soc_below = _soc_reserve_autumn()
        elif spring:
            soc_below = _spring_soc_charge_below()
        else:
            soc_below = _soc_reserve_summer()
    if weak_pv_below is None:
        if winter_b2:
            weak_pv_below = _b2_pv_skip_kwh()
        elif autumn:
            weak_pv_below = _autumn_pv_charge_kwh()
        elif spring:
            weak_pv_below = _spring_tomorrow_max_kwh()
        else:
            weak_pv_below = _summer_tomorrow_max_kwh()

    def _empty(*, skip_reason: str = '', **extra) -> ChargeTonightCloudyRule:
        return ChargeTonightCloudyRule(
            triggered=False,
            soc_percent=soc_percent,
            tomorrow_pv_kwh=tomorrow_pv_kwh,
            soc_below=soc_below,
            weak_pv_below=weak_pv_below,
            recommendation='',
            title='',
            body='',
            tomorrow_temp_c=tomorrow_temp_c,
            skip_reason=skip_reason,
            **extra,
        )

    if is_weekend(as_of.date()) or is_public_holiday(as_of.date()):
        return _empty()
    if as_of.hour >= 22:
        return _empty()
    if soc_percent is None:
        return _empty()

    # --- Lato / wiosna: krótki FC (nie pełnić baterii) ---
    if not winter_b2 and not autumn:
        if soc_percent >= soc_below:
            return _empty()
        if tomorrow_pv_kwh is None:
            return _empty()
        if tomorrow_pv_kwh > weak_pv_below:
            return _empty()
        if fc_max_minutes is not None and fc_max_minutes > 0:
            minutes = float(fc_max_minutes)
            delta = _delta_soc_for_minutes(minutes)
        else:
            minutes = _summer_fc_max_minutes()
            delta = _summer_fc_delta_soc()
        end_h, end_m = _fc_end_clock(start_h, minutes)
        label = 'WIOSNA' if spring else 'LATO'
        return ChargeTonightCloudyRule(
            triggered=True,
            soc_percent=soc_percent,
            tomorrow_pv_kwh=tomorrow_pv_kwh,
            soc_below=soc_below,
            weak_pv_below=weak_pv_below,
            recommendation=f'{label}: KRÓTKI FC {minutes:.0f} MIN (+{delta:.0f}%)',
            title=f'Sugestia: krótko doładuj od {start_h:02d}:00 (max {minutes:.0f} min)',
            body=(
                f'SoC {soc_percent:.0f}% < próg {soc_below:.0f}% i jutro ~{tomorrow_pv_kwh:.0f} kWh '
                f'(próg PV {weak_pv_below:.0f}). {label.capitalize()}: włącz ForceCharge {start_h:02d}:00, '
                f'wyłącz o {end_h:02d}:{end_m:02d} (~{minutes:.0f} min / +{delta:.0f} pp; 30 min ≈ +50 pp) '
                f'— nie ładuj do 75–100%. Sugestia doradcza, bez automatyki.'
            ),
            target_soc_percent=min(100.0, soc_percent + delta),
            fc_minutes=minutes,
            tomorrow_temp_c=tomorrow_temp_c,
        )

    # --- Jesień §D: PV-driven ---
    if autumn:
        if tomorrow_pv_kwh is None:
            return _empty()
        target = autumn_night_target_soc(tomorrow_pv_kwh)
        gap = estimate_autumn_peak_gap_kwh(tomorrow_pv_kwh)
        reserve = soc_below
        if target is None:
            if soc_percent < reserve:
                target = reserve
            else:
                return _empty(skip_reason='covered', estimated_gap_kwh=gap)
        if soc_percent >= target:
            return _empty(skip_reason='full', target_soc_percent=target, estimated_gap_kwh=gap)
        delta_soc = target - soc_percent
        cap = _b2_capacity_kwh(capacity_kwh)
        energy_kwh = delta_soc / 100.0 * cap
        minutes = _cap_fc_minutes(fc_minutes_for_delta_soc(delta_soc), fc_max_minutes)
        if minutes + 0.05 < fc_minutes_for_delta_soc(delta_soc):
            delta_soc = _delta_soc_for_minutes(minutes)
            target = min(100.0, soc_percent + delta_soc)
            energy_kwh = delta_soc / 100.0 * cap
        below_reserve = soc_percent < reserve
        if not _charge_worth_vs_wear(
            energy_kwh=energy_kwh,
            delta_soc=delta_soc,
            gap_kwh=gap,
            frost=False,
            below_reserve=below_reserve,
        ):
            return _empty(
                skip_reason='wear',
                target_soc_percent=target,
                fc_minutes=minutes,
                estimated_gap_kwh=gap,
            )
        end_h, end_m = _fc_end_clock(start_h, minutes)
        return ChargeTonightCloudyRule(
            triggered=True,
            soc_percent=soc_percent,
            tomorrow_pv_kwh=tomorrow_pv_kwh,
            soc_below=soc_below,
            weak_pv_below=weak_pv_below,
            recommendation=f'ŁADUJ OD {start_h:02d}:00 (JESIEŃ PV)',
            title=f'Sugestia: naładuj baterię od {start_h:02d}:00',
            body=(
                f'SoC {soc_percent:.0f}% → cel {target:.0f}% (+{delta_soc:.0f} pp). '
                f'Włącz ForceCharge o {start_h:02d}:00, wyłącz o {end_h:02d}:{end_m:02d} '
                f'(~{minutes:.0f} min; 30 min ≈ +50 pp). '
                f'Jutro PV ~{tomorrow_pv_kwh:.0f} kWh < {weak_pv_below:.0f} '
                f'(luka szczytu ~{gap:.0f} kWh). Nie zostawiaj FC do rana. '
                f'Sugestia doradcza, bez automatyki.'
            ),
            target_soc_percent=target,
            fc_minutes=minutes,
            tomorrow_temp_c=tomorrow_temp_c,
            estimated_gap_kwh=round(gap, 1),
        )

    # --- Zima §C: T×PV ---
    frost = tomorrow_temp_c is not None and tomorrow_temp_c < 0
    if tomorrow_pv_kwh is None and not frost:
        return _empty()
    pv_for_target = 0.0 if tomorrow_pv_kwh is None else tomorrow_pv_kwh
    target = winter_night_target_soc(tomorrow_temp_c, pv_for_target)
    gap = (
        estimate_peak_gap_kwh(tomorrow_temp_c, pv_for_target)
        if tomorrow_temp_c is not None
        else None
    )
    reserve = soc_below
    if target is None:
        if soc_percent < reserve:
            target = reserve
        else:
            return _empty(skip_reason='covered', estimated_gap_kwh=gap)

    if soc_percent >= target:
        return _empty(
            skip_reason='full',
            target_soc_percent=target,
            estimated_gap_kwh=gap,
        )

    delta_soc = target - soc_percent
    cap = _b2_capacity_kwh(capacity_kwh)
    energy_kwh = delta_soc / 100.0 * cap
    raw_minutes = fc_minutes_for_delta_soc(delta_soc)
    minutes = _cap_fc_minutes(raw_minutes, fc_max_minutes)
    if minutes + 0.05 < raw_minutes:
        delta_soc = _delta_soc_for_minutes(minutes)
        target = min(100.0, soc_percent + delta_soc)
        energy_kwh = delta_soc / 100.0 * cap
    below_reserve = soc_percent < reserve
    if not _charge_worth_vs_wear(
        energy_kwh=energy_kwh,
        delta_soc=delta_soc,
        gap_kwh=gap,
        frost=frost,
        below_reserve=below_reserve,
    ):
        return _empty(
            skip_reason='wear',
            target_soc_percent=target,
            fc_minutes=minutes,
            estimated_gap_kwh=gap,
        )

    pv_txt = f'~{tomorrow_pv_kwh:.0f} kWh' if tomorrow_pv_kwh is not None else 'brak prognozy PV'
    t_txt = f'{tomorrow_temp_c:.0f}°C' if tomorrow_temp_c is not None else 'T nieznana'
    gap_txt = f', luka szczytu ~{gap:.0f} kWh' if gap is not None else ''
    end_h, end_m = _fc_end_clock(start_h, minutes)
    return ChargeTonightCloudyRule(
        triggered=True,
        soc_percent=soc_percent,
        tomorrow_pv_kwh=tomorrow_pv_kwh,
        soc_below=soc_below,
        weak_pv_below=weak_pv_below,
        recommendation=f'ŁADUJ OD {start_h:02d}:00 (B2 T+PV)',
        title=f'Sugestia: naładuj baterię od {start_h:02d}:00',
        body=(
            f'SoC {soc_percent:.0f}% → cel {target:.0f}% (+{delta_soc:.0f} pp). '
            f'Włącz ForceCharge o {start_h:02d}:00, wyłącz o {end_h:02d}:{end_m:02d} '
            f'(~{minutes:.0f} min; kalibracja: 30 min ≈ +50 pp, jak 25–26.08). '
            f'Jutro {t_txt}, PV {pv_txt}{gap_txt}. Nie zostawiaj FC do rana — tylko okno. '
            f'Sugestia doradcza, bez automatyki.'
        ),
        target_soc_percent=target,
        fc_minutes=minutes,
        tomorrow_temp_c=tomorrow_temp_c,
        estimated_gap_kwh=None if gap is None else round(gap, 1),
    )



def get_day_pv_forecast_sum(
    target_day: str,
    *,
    as_of: datetime | None = None,
    db_path: str | None = None,
) -> float | None:
    """Suma prognozy RF (raw) na cały dzień — pod regułę pochmurno."""
    as_of = as_of or datetime.now()
    db_path = db_path or _db_path()
    try:
        from src.models.pv_hourly_predictor import PVHourlyPredictor

        predictor = PVHourlyPredictor()
        predictor.load()
        pred = predictor.predict_days(
            days_ahead=1,
            db_path=db_path,
            from_date=date.fromisoformat(target_day),
            hybrid_today=False,
            use_actual_pv=False,
            as_of=as_of,
        )
        day_df = pred[pred['day'] == target_day] if not pred.empty else pred
        if day_df.empty:
            return None
        return round(float(day_df['predicted_kwh'].sum()), 2)
    except Exception:
        return None


def get_archived_day_pv_kwh(target_day: str) -> float | None:
    """Suma PV z forecast_history.csv (bez ładowania modelu) — karta Home."""
    path = os.path.join('data', 'processed', 'forecasts', 'forecast_history.csv')
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path)
        if 'target_day' not in df.columns:
            return None
        sub = df[df['target_day'].astype(str) == str(target_day)]
        if sub.empty:
            return None
        if 'run_at' in sub.columns:
            sub = sub.sort_values('run_at')
        row = sub.iloc[-1]
        for col in ('predicted_kwh_raw', 'predicted_kwh'):
            if col in row.index and pd.notna(row[col]):
                return round(float(row[col]), 2)
        return None
    except Exception:
        return None


def get_day_mean_temp_c(
    target_day: str,
    *,
    db_path: str | None = None,
) -> float | None:
    """Średnia temperatura doby z weather_data (fakt lub prognoza Open-Meteo)."""
    db_path = db_path or _db_path()
    if not os.path.exists(db_path):
        return None
    try:
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            '''
            SELECT AVG(temperature_celsius)
            FROM weather_data
            WHERE substr(timestamp, 1, 10) = ?
              AND temperature_celsius IS NOT NULL
            ''',
            (target_day,),
        ).fetchone()
        conn.close()
        if row and row[0] is not None:
            return round(float(row[0]), 1)
        return None
    except Exception:
        return None


def _battery_capacity_kwh(db_path: str | None = None) -> float:
    env = os.getenv('BATTERY_CAPACITY_KWH', '').strip()
    if env:
        return float(env)
    db_path = db_path or _db_path()
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            '''
            SELECT MAX(t.value)
            FROM foxess_timeseries t
            JOIN foxess_data f ON f.timestamp = t.timestamp
            WHERE t.variable = 'ResidualEnergy'
              AND f.battery_soc_percent >= 95
            '''
        ).fetchone()
        conn.close()
        if row and row[0] and float(row[0]) > 1:
            return float(row[0])
    return float(os.getenv('BATTERY_CAPACITY_KWH_DEFAULT', str(NOMINAL_CAPACITY_KWH)))


def _soc_reserve_winter() -> float:
    return float(os.getenv('BATTERY_SOC_RESERVE_WINTER', '40'))


def _soc_reserve_summer() -> float:
    return float(os.getenv('BATTERY_SOC_RESERVE_SUMMER', '20'))


def _soc_reserve_autumn() -> float:
    """Mostek lato→zima (PLAN §A: 20–25%)."""
    return float(os.getenv('BATTERY_SOC_RESERVE_AUTUMN', '22'))


def _soc_min_evening_for_season(season: str) -> float:
    if season == 'autumn':
        return float(os.getenv('BATTERY_SOC_MIN_EVENING_AUTUMN', '45'))
    if season == 'winter':
        return float(os.getenv('BATTERY_SOC_MIN_EVENING_WINTER', os.getenv('BATTERY_SOC_MIN_EVENING', '50')))
    if season == 'spring':
        return float(os.getenv('BATTERY_SOC_MIN_EVENING_SPRING', os.getenv('BATTERY_SOC_MIN_EVENING_SUMMER', '50')))
    return float(os.getenv('BATTERY_SOC_MIN_EVENING_SUMMER', os.getenv('BATTERY_SOC_MIN_EVENING', '50')))


def resolve_calendar_season(d: date | None = None) -> Literal['winter', 'summer', 'autumn', 'spring']:
    """Kalendarz: zima XI–II, wiosna III–V, jesień 15.09–31.10, lato reszta."""
    d = d or date.today()
    if is_winter_season(d):
        return 'winter'
    if is_autumn_season(d):
        return 'autumn'
    if is_spring_season(d):
        return 'spring'
    return 'summer'


def seasonal_soc_reserve(
    d: date | None = None,
    *,
    season: str | None = None,
) -> float:
    """Rezerwa min. SoC (BAT.5 / B1 / §E). `season=auto`/None → kalendarz."""
    resolved = season
    if resolved in (None, '', 'auto'):
        resolved = resolve_calendar_season(d)
    if resolved == 'winter':
        return _soc_reserve_winter()
    if resolved == 'autumn':
        return _soc_reserve_autumn()
    # lato + wiosna: 20%
    return _soc_reserve_summer()


def seasonal_min_evening_percent(
    d: date | None = None,
    *,
    season: str | None = None,
) -> float:
    """Próg SoC@16 / wieczór (B1: jesień 45%, zima 50%)."""
    resolved = season
    if resolved in (None, '', 'auto'):
        resolved = resolve_calendar_season(d)
    return _soc_min_evening_for_season(resolved)


def get_soc_at_hour(
    target_day: str,
    hour: int,
    db_path: str | None = None,
) -> float | None:
    """Pierwszy odczyt SoC w danej godzinie (BAT.3 — checkpoint 16:00)."""
    db_path = db_path or _db_path()
    if not os.path.exists(db_path):
        return None
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        '''
        SELECT battery_soc_percent
        FROM foxess_data
        WHERE date(timestamp) = ?
          AND battery_soc_percent IS NOT NULL
          AND CAST(strftime('%H', timestamp) AS INTEGER) = ?
        ORDER BY timestamp
        LIMIT 1
        ''',
        (target_day, hour),
    ).fetchone()
    conn.close()
    if not row or row[0] is None:
        return None
    return float(row[0])


def _winter_afternoon_soc_below() -> float:
    """Historia: silne FC 13–15 przy SoC@13 p50≈15%; próg produktowy = rezerwa zimy ~40%."""
    return float(os.getenv('BATTERY_WINTER_AFT_SOC_BELOW', '40'))


def _winter_afternoon_pv_below() -> float:
    """Historia: need_fc przy PV p50≈3 kWh; przy PV≥10 rzadko trzeba z sieci."""
    return float(os.getenv('BATTERY_WINTER_AFT_PV_BELOW', '10'))


def _winter_afternoon_temp_below() -> float:
    """Historia: need_fc przy T p50≈−1,7°C; T>5 + PV≥10 → prawie nigdy."""
    return float(os.getenv('BATTERY_WINTER_AFT_TEMP_BELOW', '5'))


def evaluate_winter_afternoon_fc(
    *,
    soc_percent: float | None,
    today_pv_kwh: float | None,
    today_temp_c: float | None = None,
    as_of: datetime | None = None,
) -> WinterAfternoonFcRule:
    """Czysta reguła: zimą włącz FC 13–15 gdy SoC niski i słabe PV przy chłodzie.

    Kalibracja na XI.2025–II.2026 (silne ładowanie z sieci ≥3 kWh w 13–15):
    SoC@13 < 40% ∧ T≤5°C ∧ PV<10 → prec≈0,46 / rec≈0,92 na „strong FC”.
    """
    from dataclasses import replace

    as_of = as_of or datetime.now()
    soc_below = _winter_afternoon_soc_below()
    pv_below = _winter_afternoon_pv_below()
    t_below = _winter_afternoon_temp_below()
    empty = WinterAfternoonFcRule(
        triggered=False,
        soc_percent=soc_percent,
        today_pv_kwh=today_pv_kwh,
        today_temp_c=today_temp_c,
        soc_below=soc_below,
        weak_pv_below=pv_below,
        mild_temp_below=t_below,
        recommendation='',
        title='',
        body='',
    )
    if not is_winter_season(as_of.date()):
        return replace(empty, skip_reason='not_winter')
    if is_weekend(as_of.date()) or is_public_holiday(as_of.date()):
        return replace(empty, skip_reason='weekend')
    if soc_percent is None:
        return replace(empty, skip_reason='no_soc')
    if soc_percent >= soc_below:
        return replace(empty, skip_reason='soc_ok')

    pv = today_pv_kwh
    temp = today_temp_c
    weak_pv = pv is not None and pv < pv_below
    cold = temp is not None and temp <= t_below
    if pv is None and temp is None:
        weather_ok = True
    elif pv is None:
        weather_ok = cold
    elif temp is None:
        weather_ok = weak_pv
    else:
        weather_ok = cold and weak_pv

    if not weather_ok:
        return replace(empty, skip_reason='covered')

    pv_txt = f'{pv:.0f} kWh' if pv is not None else '?'
    t_txt = f'{temp:.0f}°C' if temp is not None else '?'
    return WinterAfternoonFcRule(
        triggered=True,
        soc_percent=soc_percent,
        today_pv_kwh=today_pv_kwh,
        today_temp_c=today_temp_c,
        soc_below=soc_below,
        weak_pv_below=pv_below,
        mild_temp_below=t_below,
        recommendation='ZIMA — WŁĄCZ FORCECHARGE 13–15',
        title='Sugestia: doładuj w oknie 13–15',
        body=(
            f'SoC {soc_percent:.0f}% < {soc_below:.0f}% w zimie, dziś PV {pv_txt}, Tśr {t_txt}. '
            f'Historia XI–II: przy takim profilu zwykle trzeba było ładować z sieci 13–15. '
            f'Włącz ForceCharge 13:00, wyłącz 15:00 (G12w tanio). Sugestia doradcza, bez automatyki.'
        ),
    )


def evaluate_soc16_hold_reserve(
    *,
    soc_percent: float | None,
    as_of: datetime | None = None,
    min_evening: float | None = None,
    reserve_percent: float | None = None,
) -> Soc16HoldReserveRule:
    """Czysta reguła produktowa (bez I/O) — advise-only.

    Od 13:00: jeśli SoC < próg wieczorny → sugestia FC 13–15.
    Od 16:00: jeśli SoC@16 < próg → trzymaj rezerwę do 22:00, ładuj 22–6.
    """
    as_of = as_of or datetime.now()
    min_evening = _soc_min_evening() if min_evening is None else min_evening
    reserve_percent = (
        seasonal_soc_reserve(as_of.date()) if reserve_percent is None else reserve_percent
    )
    hour_passed = as_of.hour >= 16
    in_afternoon = 13 <= as_of.hour < 16
    empty = Soc16HoldReserveRule(
        triggered=False,
        hour_passed=hour_passed,
        soc_percent=soc_percent,
        min_evening_percent=min_evening,
        reserve_percent=reserve_percent,
        in_afternoon_window=in_afternoon,
        recommendation='',
        title='',
        body='',
    )
    if soc_percent is None or as_of.hour < 13:
        return empty
    if soc_percent >= min_evening:
        return empty

    if in_afternoon:
        rec = 'NISKI SOC — WŁĄCZ FORCECHARGE 13–15'
        title = 'Sugestia: niski SoC — okno 13–15'
        body = (
            f'SoC {soc_percent:.0f}% < {min_evening:.0f}% przed szczytem wieczornym. '
            f'Nie rozładowuj poniżej rezerwy {reserve_percent:.0f}%. '
            f'Rozważ ForceCharge 13:00–15:00 (G12w tanio). Sugestia doradcza, bez automatyki.'
        )
    else:
        rec = 'NISKI SOC@16 — TRZYMAJ REZERWĘ'
        title = 'Sugestia: niski SoC na wieczór'
        body = (
            f'SoC o 16:00 wynosi {soc_percent:.0f}% (próg {min_evening:.0f}%). '
            f'Nie rozładowuj poniżej rezerwy {reserve_percent:.0f}% do 22:00. '
            f'Zalecane ładowanie 22–6; jutro okno 13–15. Sugestia doradcza, bez automatyki.'
        )
    return Soc16HoldReserveRule(
        triggered=True,
        hour_passed=hour_passed,
        soc_percent=soc_percent,
        min_evening_percent=min_evening,
        reserve_percent=reserve_percent,
        in_afternoon_window=in_afternoon,
        recommendation=rec,
        title=title,
        body=body,
    )


def next_cheap_window_label(as_of: datetime) -> str:
    """Kolejne tanie okno G12w (albo 'teraz', jeśli już jesteśmy w tanim)."""
    d = as_of.date()
    if is_weekend(d) or is_public_holiday(d):
        return 'teraz (weekend/święto — cała doba tanio)'
    h = as_of.hour
    if h >= 22 or h < 6:
        return 'teraz (22–6)'
    if 13 <= h < 15:
        return 'teraz (13–15)'
    if 6 <= h < 13:
        return '13–15'
    return '22–6'


def _hours_until_morning_six(as_of: datetime) -> float:
    """Godziny do najbliższego 6:00 (koniec drogiego poranka / koniec taniej nocy)."""
    target = as_of.replace(hour=6, minute=0, second=0, microsecond=0)
    if as_of >= target:
        target = target + timedelta(days=1)
    return max(0.0, (target - as_of).total_seconds() / 3600.0)


def _fmt_duration_hm(hours: float) -> str:
    """np. 10.6 → '10 h 36 min' (czytelniej niż zaokrąglone 11 h)."""
    total_min = max(0, int(round(float(hours) * 60)))
    h, m = divmod(total_min, 60)
    return f'{h} h {m:02d} min'


def _evening_planning_load_kw() -> float:
    """Uśredniony pobór wieczór/noc latem (bez pompy) — do szacunku „starczy do rana”."""
    return float(os.getenv('BATTERY_EVENING_LOAD_KW', '0.55'))


def get_today_pv_observed_kwh(target_day: str, db_path: str | None = None) -> float | None:
    """Suma PV dotychczas (ΔPVE) dla dnia — jeśli są pomiary."""
    try:
        from src.models.forecast_validation import get_actual_hourly_ml

        df = get_actual_hourly_ml(target_day, db_path=db_path or _db_path())
        if df is None or df.empty:
            return None
        return round(float(df['actual_pv_ml_kwh'].sum()), 1)
    except Exception:
        return None


def format_evening_battery_plan_note(
    *,
    soc_percent: float | None,
    today_pv_kwh: float | None,
    tomorrow_pv_kwh: float | None,
    as_of: datetime | None = None,
    reserve_percent: float | None = None,
    capacity_kwh: float | None = None,
    today_pv_actual_kwh: float | None = None,
) -> str:
    """Tekst doradczy: SoC po słonecznym dniu + czy starczy do rana / jutro.

    Accu/MB deszcz vs model ~20 kWh — wzmianka o rozjeździe (bez API Accu).
    """
    as_of = as_of or datetime.now()
    reserve = (
        seasonal_soc_reserve(as_of.date()) if reserve_percent is None else float(reserve_percent)
    )
    capacity = _battery_capacity_kwh() if capacity_kwh is None else float(capacity_kwh)
    pv_today = today_pv_actual_kwh if today_pv_actual_kwh is not None else today_pv_kwh
    sunny_today = pv_today is not None and pv_today >= 18.0

    parts: list[str] = []
    if soc_percent is not None:
        if sunny_today and soc_percent >= 85:
            parts.append(
                f'Po słonecznym dniu (PV dziś ~{pv_today:.0f} kWh) SoC ~{soc_percent:.0f}% — '
                f'bateria praktycznie pełna.'
            )
        elif sunny_today and soc_percent >= 60:
            parts.append(
                f'Po słonecznym dniu (PV ~{pv_today:.0f} kWh) SoC ~{soc_percent:.0f}% — '
                f'dobry bufor na noc.'
            )
        elif soc_percent >= 85:
            parts.append(f'SoC teraz ~{soc_percent:.0f}% — bateria pełna/wysoka.')
        elif soc_percent < reserve + 10:
            parts.append(
                f'SoC teraz ~{soc_percent:.0f}% — blisko rezerwy {reserve:.0f}%; '
                f'rozważ FC 22–6.'
            )
        else:
            parts.append(f'SoC teraz ~{soc_percent:.0f}% (rezerwa {reserve:.0f}%).')

        usable = capacity * max(0.0, soc_percent - reserve) / 100.0
        load_kw = _evening_planning_load_kw()
        hours_left = usable / load_kw if load_kw > 0.05 else None
        hours_to_6 = _hours_until_morning_six(as_of)
        if hours_left is not None:
            left_s = _fmt_duration_hm(hours_left)
            to6_s = _fmt_duration_hm(hours_to_6)
            if hours_left >= hours_to_6 + 1.0:
                parts.append(
                    f'Szacunek: starczy do rana (~{left_s} użytecznych przy ~{load_kw:.1f} kW '
                    f'vs ~{to6_s} do 6:00).'
                )
            elif hours_left >= hours_to_6 - 0.5:
                parts.append(
                    f'Szacunek: do rana na styk (~{left_s} vs ~{to6_s} do 6:00).'
                )
            else:
                parts.append(
                    f'Szacunek: może nie starczyć do rana (~{left_s} vs ~{to6_s}) — '
                    f'FC 22–6 ma sens.'
                )

    if tomorrow_pv_kwh is not None:
        if tomorrow_pv_kwh >= 18:
            parts.append(
                f'Model PV jutro ~{tomorrow_pv_kwh:.0f} kWh — przy suchym dniu dach zwykle pokryje zużycie; '
                f'jeśli Accu/MB zapowiadają deszcz, licz na mniej i nie rozładowuj rezerwy wieczorem.'
            )
        elif tomorrow_pv_kwh < 12:
            parts.append(
                f'PV jutro tylko ~{tomorrow_pv_kwh:.0f} kWh — słaby dzień; FC nocny bardziej uzasadniony.'
            )
        else:
            parts.append(
                f'PV jutro ~{tomorrow_pv_kwh:.0f} kWh — dzień mieszany; trzymaj rezerwę na szczyt.'
            )

    return ' '.join(parts)


def evaluate_below_reserve_wait_cheap(
    *,
    soc_percent: float | None,
    as_of: datetime | None = None,
    reserve_percent: float | None = None,
) -> BelowReserveWaitCheapRule:
    """Czysta reguła: SoC < rezerwa i droga taryfa → nie ForceCharge teraz.

    40% zimą to podłoga na noc po tanim oknie, nie polecenie ładowania w szczycie 6–13 / 15–22.
    """
    as_of = as_of or datetime.now()
    reserve_percent = (
        seasonal_soc_reserve(as_of.date()) if reserve_percent is None else reserve_percent
    )
    cheap = classify_zone(as_of) == 2
    nxt = next_cheap_window_label(as_of)
    empty = BelowReserveWaitCheapRule(
        triggered=False,
        in_cheap_zone=cheap,
        next_cheap_window=nxt,
        soc_percent=soc_percent,
        reserve_percent=reserve_percent,
        recommendation='',
        title='',
        body='',
    )
    if soc_percent is None or soc_percent >= reserve_percent or cheap:
        return empty

    rec = 'PONIŻEJ REZERWY — POCZEKAJ NA TANIĄ TARYFĘ'
    title = 'Sugestia: nie ładuj w drogiej taryfie'
    body = (
        f'SoC {soc_percent:.0f}% jest poniżej rezerwy {reserve_percent:.0f}%, '
        f'ale teraz G12w jest drogo (pn–pt 6–13 i 15–22). '
        f'Nie ładuj z sieci w szczycie — poczekaj na tanie okno {nxt}. '
        f'Sugestia doradcza, bez automatyki.'
    )
    return BelowReserveWaitCheapRule(
        triggered=True,
        in_cheap_zone=False,
        next_cheap_window=nxt,
        soc_percent=soc_percent,
        reserve_percent=reserve_percent,
        recommendation=rec,
        title=title,
        body=body,
    )


def _high_load_kw_threshold() -> float:
    return float(os.getenv('BATTERY_HIGH_LOAD_KW', '2.0'))


def _outage_grid_kw_threshold() -> float:
    return float(os.getenv('BATTERY_OUTAGE_GRID_KW', '0.2'))


def get_winter_night_load_stats(
    db_path: str | None = None,
    *,
    lookback_days: int = 14,
) -> tuple[float, float]:
    """Średni i szczyt load_power w nocy 1–6 (zima, ostatnie dni)."""
    db_path = db_path or _db_path()
    if not os.path.exists(db_path):
        return 2.0, 4.0

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        '''
        SELECT AVG(load_power_kw), MAX(load_power_kw)
        FROM foxess_data
        WHERE date(timestamp) >= date('now', ?)
          AND CAST(strftime('%H', timestamp) AS INTEGER) BETWEEN 1 AND 5
          AND load_power_kw IS NOT NULL
          AND load_power_kw > 0.2
        ''',
        (f'-{lookback_days} days',),
    ).fetchone()
    conn.close()
    if not row or row[0] is None:
        return 2.0, 4.0
    return float(row[0]), float(row[1])


def detect_outage_last_night(
    db_path: str | None = None,
    *,
    reference: datetime | None = None,
) -> tuple[bool, str | None, str | None, float | None]:
    """
    Wykryj przerwę w zasilaniu w oknie 1:00–6:00 (ostatnia noc).

    Heurystyka: brak importu z sieci + load > 0 + rozładowanie baterii ≥ 30 min.
    """
    db_path = db_path or _db_path()
    reference = reference or datetime.now()
    if reference.hour < 6:
        night_day = (reference.date() - timedelta(days=1)).isoformat()
    else:
        night_day = reference.date().isoformat()

    if not os.path.exists(db_path):
        return False, None, None, None

    grid_thr = _outage_grid_kw_threshold()
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(
        '''
        SELECT timestamp, load_power_kw, grid_power_kw, battery_power_kw, battery_soc_percent
        FROM foxess_data
        WHERE date(timestamp) = ?
          AND CAST(strftime('%H', timestamp) AS INTEGER) BETWEEN 1 AND 5
        ORDER BY timestamp
        ''',
        conn,
        params=(night_day,),
    )
    conn.close()

    if df.empty:
        return False, None, None, None

    df['off_grid'] = (
        df['load_power_kw'].fillna(0) > 0.4
    ) & (
        df['grid_power_kw'].fillna(0).abs() < grid_thr
    ) & (
        df['battery_power_kw'].fillna(0) < -0.05
    )

    if not df['off_grid'].any():
        return False, None, None, None

    runs: list[tuple[str, str, float]] = []
    start_idx = None
    for i, on in enumerate(df['off_grid'].tolist()):
        if on and start_idx is None:
            start_idx = i
        elif not on and start_idx is not None:
            seg = df.iloc[start_idx:i]
            if len(seg) >= 6:
                min_soc = seg['battery_soc_percent'].min()
                runs.append((
                    str(seg['timestamp'].iloc[0])[:16],
                    str(seg['timestamp'].iloc[-1])[:16],
                    float(min_soc) if pd.notna(min_soc) else float('nan'),
                ))
            start_idx = None
    if start_idx is not None:
        seg = df.iloc[start_idx:]
        if len(seg) >= 6:
            min_soc = seg['battery_soc_percent'].min()
            runs.append((
                str(seg['timestamp'].iloc[0])[:16],
                str(seg['timestamp'].iloc[-1])[:16],
                float(min_soc) if pd.notna(min_soc) else float('nan'),
            ))

    if not runs:
        return False, None, None, None

    longest = max(runs, key=lambda r: r[1])
    return True, longest[0], longest[1], longest[2]


def build_resilience_outlook(
    snap: BatterySnapshot,
    *,
    as_of: datetime | None = None,
    winter: bool = True,
    db_path: str | None = None,
) -> ResilienceOutlook:
    as_of = as_of or datetime.now()
    db_path = db_path or _db_path()
    capacity = _battery_capacity_kwh(db_path)
    reserve = _soc_reserve_winter() if winter else _soc_reserve_summer()

    avg_load, peak_load = get_winter_night_load_stats(db_path)
    if snap.load_power_kw is not None and snap.load_power_kw > 0.3:
        avg_load = max(avg_load, float(snap.load_power_kw))

    # Zimą o 5:00 chwilowy load bywa niski — planujemy na szczyt nocny (pompa).
    planning_load = avg_load
    if winter:
        planning_load = max(
            avg_load,
            peak_load * 0.85,
            float(os.getenv('BATTERY_OUTAGE_PLANNING_LOAD_KW', '2.5')),
        )
        if snap.load_power_kw is not None:
            planning_load = max(planning_load, float(snap.load_power_kw))

    soc = snap.soc_percent or 0.0
    usable_soc = max(0.0, soc - reserve)
    usable_kwh = capacity * usable_soc / 100.0

    hours_empty = None
    minutes_empty = None
    if planning_load > 0.1:
        hours_empty = round(usable_kwh / planning_load, 2)
        minutes_empty = round(hours_empty * 60, 0)

    high_load = planning_load >= _high_load_kw_threshold() or peak_load >= _high_load_kw_threshold()

    outage, o_start, o_end, o_min_soc = detect_outage_last_night(db_path, reference=as_of)
    notes: list[str] = []

    if winter and hours_empty is not None:
        load_label = planning_load
        if hours_empty < 4:
            notes.append(
                f'⚠️ Przy obciążeniu ~{load_label:.1f} kW starczy ~{hours_empty:.1f} h '
                f'(rezerwa SoC {reserve:.0f}%) — ryzyko przy przerwie 1–6.'
            )
        elif hours_empty < 5:
            notes.append(
                f'Przy ~{load_label:.1f} kW autonomia ~{hours_empty:.1f} h — przy awarii do 6:00 może być na styk.'
            )

    if high_load and winter:
        notes.append(
            f'⚠️ Wysokie obciążenie nocne (plan ~{planning_load:.1f} kW, szczyt ~{peak_load:.1f} kW) — '
            'pompa ciepła obciąża baterię w przerwie.'
        )

    if outage:
        notes.append(
            f'Wykryto przerwę zasilania w nocy {o_start} → {o_end}'
            + (f' (min. SoC {o_min_soc:.0f}%)' if o_min_soc is not None and not pd.isna(o_min_soc) else '')
        )

    return ResilienceOutlook(
        capacity_kwh=round(capacity, 2),
        usable_kwh=round(usable_kwh, 2),
        reserve_soc_percent=reserve,
        avg_load_kw=round(planning_load, 2),
        peak_load_kw=round(peak_load, 2),
        hours_until_empty=hours_empty,
        minutes_until_empty=minutes_empty,
        high_load_warning=high_load and winter,
        outage_last_night=outage,
        outage_start=o_start,
        outage_end=o_end,
        outage_min_soc=o_min_soc,
        notes=notes,
    )


def _append_outage_log(
    resilience: ResilienceOutlook,
    target_day: str,
    as_of: datetime,
    path: str | None = None,
) -> None:
    if not resilience.outage_last_night:
        return
    path = path or OUTAGE_LOG_FILE
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    key = f'{target_day}_{resilience.outage_start}'
    if os.path.exists(path):
        existing = pd.read_csv(path)
        if 'event_key' in existing.columns and key in existing['event_key'].astype(str).values:
            return
    row = {
        'event_key': key,
        'logged_at': as_of.isoformat(timespec='seconds'),
        'night_date': target_day,
        'outage_start': resilience.outage_start,
        'outage_end': resilience.outage_end,
        'min_soc_percent': resilience.outage_min_soc,
        'avg_load_kw': resilience.avg_load_kw,
    }
    df = pd.DataFrame([row])
    header = not os.path.exists(path)
    df.to_csv(path, mode='a', header=header, index=False)


def _apply_resilience_to_advice(
    advice: BatteryAdvice,
    resilience: ResilienceOutlook,
) -> None:
    """Dopisz szacunek autonomii i ewentualnie nadpisz rekomendację zimą."""
    r = resilience
    if r.capacity_kwh:
        advice.details.append(
            f'Pojemność ~{r.capacity_kwh:.1f} kWh | użyteczne ~{r.usable_kwh:.1f} kWh '
            f'(SoC − rezerwa {r.reserve_soc_percent:.0f}%)'
        )
    if r.hours_until_empty is not None:
        advice.details.append(
            f'Szac. czas do rozładowania: ~{r.hours_until_empty:.1f} h '
            f'({int(r.minutes_until_empty or 0)} min) przy ~{r.avg_load_kw:.1f} kW'
        )
    for note in r.notes:
        advice.details.append(note)

    if not is_winter_season(advice.as_of.date()):
        return

    if r.outage_last_night and r.outage_min_soc is not None and r.outage_min_soc < 15:
        advice.recommendation = 'AWARIA NOCĄ — SOC KRYTYCZNY'
        advice.action = (
            f'W nocy przerwa {r.outage_start}–{r.outage_end}, SoC spadło do ~{r.outage_min_soc:.0f}%. '
            f'Zimą ładuj do 100% w 22–6, rezerwa min. {r.reserve_soc_percent:.0f}%, '
            'przy zapowiedzi przerwy obniż pompę 1–2°C.'
        )
    elif r.high_load_warning and r.hours_until_empty is not None and r.hours_until_empty < 5:
        if advice.context in ('morning', 'peak'):
            advice.recommendation = 'ZIMNO + WYSOKI LOAD — REZERWA'
            advice.action = (
                f'Obciążenie plan ~{r.avg_load_kw:.1f} kW — przy przerwie 4–5 h starczy ~{r.hours_until_empty:.1f} h. '
                f'Utrzymuj rezerwę SoC ≥ {r.reserve_soc_percent:.0f}%; pełne ładowanie 22–6; '
                'przy zapowiedzi przerwy obniż pompę 1–2°C.'
            )
        elif advice.context == 'pre_cheap' and r.outage_last_night:
            advice.action += (
                ' Po nocnej awarii — rozważ pełne ładowanie 13–15 zamiast pomijania.'
            )


def advise(context: Context, as_of: datetime | None = None) -> BatteryAdvice:
    as_of = as_of or datetime.now()
    target_day = as_of.date().isoformat()
    season = resolve_calendar_season(as_of.date())
    winter = season == 'winter'
    zone = classify_zone(as_of)
    tariff_label = 'tanio (pozaszczyt)' if zone == 2 else 'drogo (szczyt)'

    snap = get_battery_snapshot(target_day=target_day)
    pv = get_pv_outlook(target_day, as_of=as_of)
    resilience = build_resilience_outlook(snap, as_of=as_of, winter=winter) if winter else None

    soc = snap.soc_percent
    target = _soc_target()
    min_eve = _soc_min_evening()
    pv_enough = _morning_pv_enough_kwh()
    details: list[str] = []
    rec = ''
    action = ''

    if context == 'morning':
        minutes_to_6 = max(0, (6 - as_of.hour) * 60 - as_of.minute) if as_of.hour < 6 else 0
        if snap.timestamp:
            age_note = f'{snap.age_hours}h temu'
            if snap.age_hours is not None and snap.age_hours > 6:
                age_note += ' ⚠️ nieświeże'
            details.append(f'Ostatni odczyt FoxESS: {snap.timestamp} ({age_note})')
        if soc is not None:
            details.append(f'SoC: {soc:.0f}%')
        if pv.sunrise_hour is not None:
            details.append(f'Wschód słońca: ~{pv.sunrise_hour:.1f}h')
        if pv.first_production_hour is not None:
            details.append(f'Pierwsza prognozowana produkcja: ~{pv.first_production_hour:02d}:00')
        details.append(f'Prognoza PV rano (5–12h): {pv.morning_forecast_kwh:.1f} kWh')
        if pv.actual_so_far_kwh > 0:
            details.append(f'PV rzeczywiste dotąd: {pv.actual_so_far_kwh:.1f} kWh')

        if not winter:
            rec = 'TRYB LETNI'
            action = 'Patrz ranking godzin w prognozie PV (autokonsumpcja).'
        elif soc is not None and soc >= target:
            rec = 'SOC OK'
            action = 'Bateria naładowana — nie ładuj z sieci przed 6:00 (chyba że planujesz duży pobór rano).'
        elif minutes_to_6 > 0 and zone == 2:
            if pv.morning_forecast_kwh >= pv_enough and (
                pv.first_production_hour is not None and pv.first_production_hour <= 9
            ):
                rec = 'POCZEKAJ NA PV'
                action = (
                    f'Tanio jeszcze {minutes_to_6} min do 6:00, ale prognoza daje '
                    f'{pv.morning_forecast_kwh:.1f} kWh rano — rozważ bez ładowania z sieci.'
                )
            else:
                rec = 'ŁADUJ Z SIECI (TANIO)'
                action = (
                    f'Tanio do 6:00 ({minutes_to_6} min). Mało PV rano ({pv.morning_forecast_kwh:.1f} kWh) '
                    f'→ ForceCharge / ładowanie z sieci teraz.'
                )
        elif as_of.hour >= 6:
            rec = 'STREFA DROGA OD 6:00'
            action = (
                'Okno tanie przed 6:00 minęło. Następne tanio pn–pt: 13:00–15:00 '
                f'(prognoza PV w tym oknie: {pv.window_forecast_kwh:.1f} kWh).'
            )
        else:
            rec = 'BRAK DANYCH SOC'
            action = 'Sync FoxESS — sprawdź SoC w aplikacji przed decyzją o ładowaniu.'

    elif context == 'pre_cheap':
        cheap_soon = not is_weekend(as_of.date()) and as_of.hour < 13
        if snap.timestamp:
            details.append(f'Ostatni odczyt: {snap.timestamp}')
        if soc is not None:
            details.append(f'SoC: {soc:.0f}% (cel: {target:.0f}%, min. na wieczór: {min_eve:.0f}%)')
        details.append(f'PV dziś dotąd: {pv.actual_so_far_kwh:.1f} kWh')
        details.append(f'Prognoza PV 13–15: {pv.window_forecast_kwh:.1f} kWh')

        if is_weekend(as_of.date()):
            rec = 'WEEKEND — CAŁA DOBA TANIO'
            action = 'Możesz ładować w dowolnym momencie; okno 13–15 nie jest krytyczne.'
        elif not winter:
            rec = 'TRYB LETNI'
            action = 'Okno 13–15 opcjonalne — priorytet autokonsumpcja PV z prognozy midday.'
        elif soc is not None and soc >= target:
            rec = 'SOC OK — POMIŃ FORCE CHARGE'
            action = f'SoC {soc:.0f}% ≥ cel {target:.0f}% — nie musisz ładować 13:00–15:00 z sieci.'
        elif cheap_soon:
            rec = 'ŁADUJ 13:00–15:00 (G12w TANIO)'
            action = (
                f'Za {13 - as_of.hour}h tania strefa. SoC '
                f'{(f"{soc:.0f}%" if soc is not None else "?")} — włącz ForceCharge 13–15 '
                f'(PV w oknie ~{pv.window_forecast_kwh:.1f} kWh).'
            )
        else:
            rec = 'OKNO 13–15 TRWA LUB MINĘŁO'
            action = 'Sprawdź w aplikacji FoxESS czy ładowanie z sieci ruszyło.'

    else:  # peak
        if snap.timestamp:
            details.append(f'Ostatni odczyt: {snap.timestamp}')
        if soc is not None:
            details.append(f'SoC: {soc:.0f}%')
        details.append(f'Prognoza PV do końca dnia: {pv.remaining_forecast_kwh:.1f} kWh')
        details.append('Strefa droga do 22:00 (pn–pt)')

        tomorrow = (date.fromisoformat(target_day) + timedelta(days=1)).isoformat()
        tomorrow_pv = get_day_pv_forecast_sum(tomorrow, as_of=as_of)
        tomorrow_t = get_day_mean_temp_c(tomorrow)
        cloudy_rule = evaluate_charge_tonight_cloudy(
            soc_percent=soc,
            tomorrow_pv_kwh=tomorrow_pv,
            as_of=as_of,
            tomorrow_temp_c=tomorrow_t,
        )
        if tomorrow_pv is not None:
            details.append(f'Prognoza PV jutro (suma): {tomorrow_pv:.1f} kWh')
        if tomorrow_t is not None:
            details.append(f'T śr. jutro: {tomorrow_t:.1f}°C')

        if cloudy_rule.triggered:
            rec = cloudy_rule.recommendation
            action = cloudy_rule.body
            details.append(
                f'B2 T+PV: cel {cloudy_rule.target_soc_percent:.0f}% '
                f'~{cloudy_rule.fc_minutes:.0f} min (30 min ≈ +50 pp)'
            )
        elif soc is not None and soc >= min_eve:
            rec = 'BATERIA NA WIECZÓR OK'
            action = (
                f'SoC {soc:.0f}% wystarczy na start szczytu 16–22. '
                'Minimalizuj import — rozładowuj baterię w drogiej strefie.'
            )
        elif soc is not None and soc < min_eve:
            rec = 'NISKI SOC — RYZYKO IMPORTU'
            action = (
                f'SoC {soc:.0f}% < {min_eve:.0f}% — wieczorem (16–22) spodziewaj się poboru z sieci. '
                'Jutro: naładuj w 22–6 lub 13–15.'
            )
        else:
            rec = 'SPRAWDŹ SOC W APP'
            action = 'Brak świeżego SoC w bazie — sync FoxESS przed szczytem wieczornym.'

    advice = BatteryAdvice(
        context=context,
        as_of=as_of,
        target_day=target_day,
        season=season,
        tariff_zone=zone,
        tariff_label=tariff_label,
        snapshot=snap,
        pv=pv,
        resilience=resilience,
        recommendation=rec,
        action=action,
        details=details,
    )
    if resilience is not None:
        _apply_resilience_to_advice(advice, resilience)
        _append_outage_log(resilience, target_day, as_of)
    return advice


def format_advice(advice: BatteryAdvice) -> str:
    ctx_labels = {
        'morning': 'PORANEK 5:00 — bateria + PV rano',
        'pre_cheap': 'PRZED TANIO 12:00 — okno 13:00–15:00',
        'peak': 'SZCZYT 16:00 — powrót do domu',
    }
    lines = [
        '=' * 60,
        f'BATTERY ADVISOR — {ctx_labels[advice.context]}',
        f'Dzień: {advice.target_day}  |  {advice.as_of.strftime("%H:%M")}  |  sezon: {advice.season}',
        f'Taryfa G12w: {advice.tariff_label}',
        '=' * 60,
        f'→ {advice.recommendation}',
        f'  {advice.action}',
        '',
    ]
    if advice.resilience and advice.season == 'winter':
        r = advice.resilience
        lines.append('  --- Autonomia baterii (zima) ---')
        if r.hours_until_empty is not None:
            lines.append(
                f'  Szac. do rozładowania: ~{r.hours_until_empty:.1f} h '
                f'@ {r.avg_load_kw:.1f} kW (rezerwa {r.reserve_soc_percent:.0f}%)'
            )
        if r.outage_last_night:
            lines.append(f'  Ostatnia awaria nocna: {r.outage_start} → {r.outage_end}')
        lines.append('')
    for d in advice.details:
        lines.append(f'  • {d}')
    lines.append('=' * 60)
    return '\n'.join(lines)


def append_advice_log(advice: BatteryAdvice, path: str | None = None) -> None:
    path = path or LOG_FILE
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    row = {
        'logged_at': advice.as_of.isoformat(timespec='seconds'),
        'context': advice.context,
        'target_day': advice.target_day,
        'season': advice.season,
        'soc_percent': advice.snapshot.soc_percent,
        'recommendation': advice.recommendation,
        'morning_pv_kwh': advice.pv.morning_forecast_kwh,
        'window_pv_kwh': advice.pv.window_forecast_kwh,
        'actual_pv_kwh': advice.pv.actual_so_far_kwh,
        'hours_until_empty': (
            advice.resilience.hours_until_empty if advice.resilience else None
        ),
        'avg_load_kw': advice.resilience.avg_load_kw if advice.resilience else None,
        'outage_last_night': (
            advice.resilience.outage_last_night if advice.resilience else False
        ),
    }
    df = pd.DataFrame([row])
    header = not os.path.exists(path)
    df.to_csv(path, mode='a', header=header, index=False)