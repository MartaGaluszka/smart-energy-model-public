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

WINTER_MONTHS = {10, 11, 12, 1, 2, 3}
LOG_FILE = 'data/processed/battery_advisor_log.csv'
OUTAGE_LOG_FILE = 'data/processed/battery_outage_log.csv'


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
    """Reguła: niski SoC + jutro słabe PV → sugestia ładowania od 22:00 (G12w)."""

    triggered: bool
    soc_percent: float | None
    tomorrow_pv_kwh: float | None
    soc_below: float
    weak_pv_below: float
    recommendation: str
    title: str
    body: str


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
    season: Literal['winter', 'summer']
    tariff_zone: int
    tariff_label: str
    snapshot: BatterySnapshot
    pv: PvOutlook
    resilience: ResilienceOutlook | None
    recommendation: str
    action: str
    details: list[str]


def is_winter_season(d: date | None = None) -> bool:
    d = d or date.today()
    return d.month in WINTER_MONTHS


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

    conn = sqlite3.connect(db_path)
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


def evaluate_charge_tonight_cloudy(
    *,
    soc_percent: float | None,
    tomorrow_pv_kwh: float | None,
    as_of: datetime | None = None,
    soc_below: float | None = None,
    weak_pv_below: float | None = None,
) -> ChargeTonightCloudyRule:
    """Czysta reguła produktowa (bez I/O) — advise-only.

    IF pn–pt AND SoC < próg AND jutro PV < próg AND przed 22:00
    → komunikat: zalecane ładowanie baterii od 22:00 (G12w tanio).
    """
    as_of = as_of or datetime.now()
    soc_below = _soc_charge_tonight_below() if soc_below is None else soc_below
    weak_pv_below = _cloudy_day_pv_kwh() if weak_pv_below is None else weak_pv_below

    empty = ChargeTonightCloudyRule(
        triggered=False,
        soc_percent=soc_percent,
        tomorrow_pv_kwh=tomorrow_pv_kwh,
        soc_below=soc_below,
        weak_pv_below=weak_pv_below,
        recommendation='',
        title='',
        body='',
    )
    if is_weekend(as_of.date()) or is_public_holiday(as_of.date()):
        return empty
    if as_of.hour >= 22:
        return empty
    if soc_percent is None or tomorrow_pv_kwh is None:
        return empty
    if soc_percent >= soc_below or tomorrow_pv_kwh >= weak_pv_below:
        return empty

    rec = 'ŁADUJ OD 22:00 (POCHMURNO + NISKI SOC)'
    title = 'Sugestia: naładuj baterię od 22:00'
    body = (
        f'SoC {soc_percent:.0f}% (próg {soc_below:.0f}%) i jutro słabe PV '
        f'(~{tomorrow_pv_kwh:.0f} kWh, próg {weak_pv_below:.0f}). '
        f'Zalecane ładowanie magazynu od 22:00 w taniej strefie G12w — '
        f'jutro rano dach raczej nie odbuduje baterii. Sugestia doradcza, bez automatyki.'
    )
    return ChargeTonightCloudyRule(
        triggered=True,
        soc_percent=soc_percent,
        tomorrow_pv_kwh=tomorrow_pv_kwh,
        soc_below=soc_below,
        weak_pv_below=weak_pv_below,
        recommendation=rec,
        title=title,
        body=body,
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
    return float(os.getenv('BATTERY_CAPACITY_KWH_DEFAULT', '11.0'))


def _soc_reserve_winter() -> float:
    return float(os.getenv('BATTERY_SOC_RESERVE_WINTER', '40'))


def _soc_reserve_summer() -> float:
    return float(os.getenv('BATTERY_SOC_RESERVE_SUMMER', '15'))


def resolve_calendar_season(d: date | None = None) -> Literal['winter', 'summer']:
    """Kalendarz MVP: zima X–III, lato reszta. Pas jesień = B1 (jeszcze nie)."""
    return 'winter' if is_winter_season(d) else 'summer'


def seasonal_soc_reserve(
    d: date | None = None,
    *,
    season: str | None = None,
) -> float:
    """Rezerwa min. SoC wg sezonu (BAT.5). `season=auto`/None → kalendarz."""
    resolved = season
    if resolved in (None, '', 'auto'):
        resolved = resolve_calendar_season(d)
    if resolved == 'winter':
        return _soc_reserve_winter()
    return _soc_reserve_summer()


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
    reserve = _soc_reserve_winter() if winter else float(os.getenv('BATTERY_SOC_RESERVE_SUMMER', '15'))

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
    winter = is_winter_season(as_of.date())
    season: Literal['winter', 'summer'] = 'winter' if winter else 'summer'
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
        cloudy_rule = evaluate_charge_tonight_cloudy(
            soc_percent=soc,
            tomorrow_pv_kwh=tomorrow_pv,
            as_of=as_of,
        )
        if tomorrow_pv is not None:
            details.append(f'Prognoza PV jutro (suma): {tomorrow_pv:.1f} kWh')

        if cloudy_rule.triggered:
            rec = cloudy_rule.recommendation
            action = cloudy_rule.body
            details.append(
                f'Reguła pochmurno+niski SoC: SoC < {cloudy_rule.soc_below:.0f}% '
                f'i jutro < {cloudy_rule.weak_pv_below:.0f} kWh → ładuj od 22:00'
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