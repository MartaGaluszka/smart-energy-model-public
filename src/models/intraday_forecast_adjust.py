"""
Korekta operacyjna prognozy PV w trakcie dnia (intraday).

Algorytm własny:
1. Porównaj skumulowaną produkcję FoxESS (minione godziny) z surową prognozą ML.
2. Oblicz współczynnik skali (z wygładzeniem blend) dla pozostałych godzin **dziś (D+0)**.
3. **Conditional Adjust:** skalę + cloudy stosuj tylko gdy błąd rano >15% LUB cloud_avg ≥70.
4. Zastosuj profil błędu godzinowego (tylko gdy conditional OK, tylko D+0).
5. Heurystyka pochmurnego dnia (wysokie cloud_cover → dodatkowe obniżenie) — tylko D+0.
6. Ranking urządzeń na wartości konserwatywnej (adjusted × conservative margin).

Hybryda (FoxESS minione + RF przyszłe) jest niezależna — buduje `predicted_kwh` wcześniej.
D+1 / D+2: bez skali intradzien i bez kary cloudy (zostaje baza / opcjonalnie bez profilu).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd

from src.models.forecast_error_profile import hourly_correction_factor, load_error_profile


@dataclass
class IntradayAdjustReport:
    day: str
    applied: bool
    reason: str
    actual_cumulative_kwh: float
    raw_forecast_cumulative_kwh: float
    intraday_scale: float
    blended_scale: float
    cloudy_factor: float
    cloud_cover_avg_pct: float | None
    hours_compared: int
    future_hours_adjusted: int
    daily_total_raw_kwh: float
    daily_total_adjusted_kwh: float
    morning_error_ratio: float | None = None
    conditional_triggered: bool = False


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == '':
        return default
    return float(raw)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == '':
        return default
    return int(raw)


def _is_enabled() -> bool:
    # Domyślnie WYŁĄCZONE (T1: zbieramy closeouty na raw RF po retreningach PVE/ICON).
    # Włączenie: FORECAST_OPERATIONAL_ADJUST=1
    return os.getenv('FORECAST_OPERATIONAL_ADJUST', '0').strip().lower() in ('1', 'true', 'yes')


def cloudy_day_factor(cloud_cover_avg_pct: float | None) -> float:
    """Dodatkowe obniżenie prognozy przy wysokim zachmurzeniu (tylko D+0, po conditional)."""
    threshold = _env_float('FORECAST_CLOUDY_THRESHOLD_PCT', 70.0)
    extra = _env_float('FORECAST_CLOUDY_EXTRA_SCALE', 0.80)
    if cloud_cover_avg_pct is None or cloud_cover_avg_pct < threshold:
        return 1.0
    return extra


def conservative_margin(cloud_cover_avg_pct: float | None) -> float:
    """Margines na ranking urządzeń (p25-style — nie szczyt, lekko poniżej adjusted)."""
    base = _env_float('FORECAST_CONSERVATIVE_MARGIN', 0.85)
    if cloud_cover_avg_pct is not None and cloud_cover_avg_pct >= _env_float(
        'FORECAST_CLOUDY_THRESHOLD_PCT', 70.0
    ):
        return min(base, _env_float('FORECAST_CLOUDY_CONSERVATIVE_MARGIN', 0.75))
    return base


def compute_intraday_scale(
    predictions: pd.DataFrame,
    as_of: datetime,
    *,
    min_hours: int | None = None,
    min_forecast_cumulative: float | None = None,
) -> tuple[float | None, float, float, int, str]:
    """
    Współczynnik skali z minionych godzin dziś.

    Returns: (blended_scale | None, actual_cum, raw_cum, n_hours, reason)
    """
    min_hours = min_hours or _env_int('FORECAST_INTRADAY_MIN_HOURS', 2)
    min_forecast_cumulative = min_forecast_cumulative or _env_float(
        'FORECAST_INTRADAY_MIN_FORECAST_KWH', 0.5
    )
    blend = _env_float('FORECAST_INTRADAY_BLEND', 0.50)
    scale_min = _env_float('FORECAST_SCALE_MIN', 0.25)
    scale_max = _env_float('FORECAST_SCALE_MAX', 1.5)

    today = as_of.date().isoformat()
    today_df = predictions[predictions['day'].astype(str) == today].copy()
    if today_df.empty:
        return None, 0.0, 0.0, 0, 'brak wierszy na dziś'

    if 'predicted_kwh_raw' not in today_df.columns:
        today_df['predicted_kwh_raw'] = today_df['predicted_kwh']

    past = today_df[today_df['hour'] < as_of.hour]
    if past.empty:
        return None, 0.0, 0.0, 0, 'brak minionych godzin'

    actual_mask = past.get('prediction_source', pd.Series(['model'] * len(past))) == 'foxess_actual'
    actual_rows = past[actual_mask]
    if actual_rows.empty:
        return None, 0.0, 0.0, 0, 'brak odczytów FoxESS (sync?)'

    n_hours = len(actual_rows)
    if n_hours < min_hours:
        return None, 0.0, 0.0, n_hours, f'za mało godzin ({n_hours} < {min_hours})'

    actual_cum = float(actual_rows['predicted_kwh'].sum())
    raw_cum = float(actual_rows['predicted_kwh_raw'].sum())

    if raw_cum < min_forecast_cumulative:
        return None, actual_cum, raw_cum, n_hours, f'za mała prognoza bazowa ({raw_cum:.2f} kWh)'

    raw_scale = actual_cum / raw_cum
    raw_scale = float(np.clip(raw_scale, scale_min, scale_max))
    blended = 1.0 + (raw_scale - 1.0) * blend
    blended = float(np.clip(blended, scale_min, scale_max))
    return blended, actual_cum, raw_cum, n_hours, 'ok'


def conditional_adjust_should_apply(
    actual_cum: float,
    raw_cum: float,
    cloud_avg: float | None,
) -> tuple[bool, float | None, str]:
    """
    Guardrail Conditional Adjust.

    Trigger gdy:
      |actual/raw − 1| > FORECAST_ADJUST_ERROR_THRESHOLD (domyślnie 0.15)
      LUB cloud_avg ≥ FORECAST_CLOUDY_THRESHOLD_PCT (domyślnie 70)
    """
    err_thr = _env_float('FORECAST_ADJUST_ERROR_THRESHOLD', 0.15)
    cloud_thr = _env_float('FORECAST_CLOUDY_THRESHOLD_PCT', 70.0)

    morning_err: float | None = None
    if raw_cum > 0:
        morning_err = abs(actual_cum / raw_cum - 1.0)

    high_err = morning_err is not None and morning_err > err_thr
    high_cloud = cloud_avg is not None and cloud_avg >= cloud_thr

    if high_err or high_cloud:
        bits = []
        if high_err and morning_err is not None:
            bits.append(f'morning_err={morning_err:.0%}>{err_thr:.0%}')
        if high_cloud:
            bits.append(f'cloud={cloud_avg:.0f}%≥{cloud_thr:.0f}')
        return True, morning_err, 'conditional_ok: ' + ', '.join(bits)

    bits = []
    if morning_err is not None:
        bits.append(f'morning_err={morning_err:.0%}≤{err_thr:.0%}')
    else:
        bits.append('brak skali rano')
    if cloud_avg is not None:
        bits.append(f'cloud={cloud_avg:.0f}%<{cloud_thr:.0f}')
    else:
        bits.append('brak cloud')
    return False, morning_err, 'conditional_skip: ' + ', '.join(bits)


def apply_operational_adjustment(
    predictions: pd.DataFrame,
    as_of: datetime | None = None,
) -> tuple[pd.DataFrame, IntradayAdjustReport | None]:
    """
    Dodaje kolumny:
    - predicted_kwh_raw (jeśli brak)
    - predicted_kwh_adjusted
    - predicted_kwh_conservative (do rankingu urządzeń)
    - adjust_intraday_scale, adjust_cloudy_factor, adjust_profile_factor

    Nie zmienia hybrydy (`predicted_kwh` / FoxESS minione). Skala i cloudy tylko D+0
    i tylko gdy conditional_adjust_should_apply.
    """
    as_of = as_of or datetime.now()
    out = predictions.copy()

    if 'predicted_kwh_raw' not in out.columns:
        out['predicted_kwh_raw'] = out['predicted_kwh'].astype(float)

    today = as_of.date().isoformat()
    cloud_avg = None
    if 'cloud_cover_pct' in out.columns:
        today_cloud = out[out['day'].astype(str) == today]['cloud_cover_pct']
        if not today_cloud.empty:
            cloud_avg = float(today_cloud.mean())

    cloudy_f_raw = cloudy_day_factor(cloud_avg)
    profile = load_error_profile()

    if not _is_enabled():
        out['predicted_kwh_adjusted'] = out['predicted_kwh'].astype(float)
        out['predicted_kwh_conservative'] = out['predicted_kwh_adjusted'] * conservative_margin(cloud_avg)
        out['adjust_intraday_scale'] = 1.0
        out['adjust_cloudy_factor'] = cloudy_f_raw
        out['adjust_profile_factor'] = 1.0
        report = IntradayAdjustReport(
            day=today,
            applied=False,
            reason='FORECAST_OPERATIONAL_ADJUST=0',
            actual_cumulative_kwh=0.0,
            raw_forecast_cumulative_kwh=0.0,
            intraday_scale=1.0,
            blended_scale=1.0,
            cloudy_factor=cloudy_f_raw,
            cloud_cover_avg_pct=cloud_avg,
            hours_compared=0,
            future_hours_adjusted=0,
            daily_total_raw_kwh=float(out[out['day'].astype(str) == today]['predicted_kwh_raw'].sum()),
            daily_total_adjusted_kwh=float(out[out['day'].astype(str) == today]['predicted_kwh_adjusted'].sum()),
            morning_error_ratio=None,
            conditional_triggered=False,
        )
        return out, report

    blended, actual_cum, raw_cum, n_hours, scale_reason = compute_intraday_scale(out, as_of)
    triggered, morning_err, cond_reason = conditional_adjust_should_apply(
        actual_cum, raw_cum, cloud_avg
    )

    # Bez triggera: baza hybrydowa, bez skali / cloudy / profilu na D+0
    if not triggered:
        out['predicted_kwh_adjusted'] = out['predicted_kwh'].astype(float)
        out['predicted_kwh_conservative'] = (
            out['predicted_kwh_adjusted'] * conservative_margin(cloud_avg)
        )
        out['adjust_intraday_scale'] = 1.0
        out['adjust_cloudy_factor'] = 1.0
        out['adjust_profile_factor'] = 1.0
        today_mask = out['day'].astype(str) == today
        report = IntradayAdjustReport(
            day=today,
            applied=False,
            reason=cond_reason,
            actual_cumulative_kwh=actual_cum,
            raw_forecast_cumulative_kwh=raw_cum,
            intraday_scale=actual_cum / raw_cum if raw_cum > 0 else 1.0,
            blended_scale=1.0,
            cloudy_factor=1.0,
            cloud_cover_avg_pct=cloud_avg,
            hours_compared=n_hours,
            future_hours_adjusted=0,
            daily_total_raw_kwh=float(out.loc[today_mask, 'predicted_kwh_raw'].sum()),
            daily_total_adjusted_kwh=float(out.loc[today_mask, 'predicted_kwh_adjusted'].sum()),
            morning_error_ratio=morning_err,
            conditional_triggered=False,
        )
        return out, report

    intraday_scale = blended if blended is not None else 1.0
    cloudy_f = cloudy_f_raw
    applied = True
    reason = cond_reason if scale_reason == 'ok' else f'{cond_reason}; scale={scale_reason}'

    adjusted = out['predicted_kwh'].astype(float).copy()
    future_adjusted = 0

    for idx, row in out.iterrows():
        day = str(row['day'])
        hour = int(row['hour'])
        source = row.get('prediction_source', 'model')

        # Hybryda: minione FoxESS bez zmian
        if day == today and source == 'foxess_actual':
            adjusted.at[idx] = float(row['predicted_kwh'])
            continue

        raw_val = float(row.get('predicted_kwh_raw', row['predicted_kwh']))

        if day == today and hour >= as_of.hour:
            # Skala + cloudy + profil TYLKO reszta DZISIAJ (D+0)
            profile_f = hourly_correction_factor(hour, profile)
            val = raw_val * intraday_scale * cloudy_f * profile_f
            future_adjusted += 1
        elif day != today:
            # D+1 / D+2: bez skali intradzien i bez kary cloudy
            val = raw_val
        else:
            val = float(row['predicted_kwh'])

        adjusted.at[idx] = max(val, 0.0)

    out['predicted_kwh_adjusted'] = adjusted
    out['predicted_kwh_conservative'] = adjusted * conservative_margin(cloud_avg)
    out['adjust_intraday_scale'] = intraday_scale
    out['adjust_cloudy_factor'] = cloudy_f
    out['adjust_profile_factor'] = out.apply(
        lambda r: (
            hourly_correction_factor(int(r['hour']), profile)
            if str(r['day']) == today
            else 1.0
        ),
        axis=1,
    )

    today_mask = out['day'].astype(str) == today
    report = IntradayAdjustReport(
        day=today,
        applied=applied,
        reason=reason,
        actual_cumulative_kwh=actual_cum,
        raw_forecast_cumulative_kwh=raw_cum,
        intraday_scale=actual_cum / raw_cum if raw_cum > 0 else 1.0,
        blended_scale=intraday_scale,
        cloudy_factor=cloudy_f,
        cloud_cover_avg_pct=cloud_avg,
        hours_compared=n_hours,
        future_hours_adjusted=future_adjusted,
        daily_total_raw_kwh=float(out.loc[today_mask, 'predicted_kwh_raw'].sum()),
        daily_total_adjusted_kwh=float(out.loc[today_mask, 'predicted_kwh_adjusted'].sum()),
        morning_error_ratio=morning_err,
        conditional_triggered=True,
    )
    return out, report


def rank_hours_conservative(
    predictions: pd.DataFrame,
    top_n_per_day: int = 5,
    future_only: bool = True,
    value_column: str = 'predicted_kwh_conservative',
) -> list:
    """Ranking godzin na wartości konserwatywnej (po korekcie operacyjnej)."""
    from src.models.pv_hourly_predictor import ApplianceRecommendation, _appliances_for_hour

    recs = []
    df = predictions.copy()

    if value_column not in df.columns:
        value_column = 'predicted_kwh_adjusted' if 'predicted_kwh_adjusted' in df.columns else 'predicted_kwh'

    if future_only and 'prediction_source' in df.columns:
        df = df[df['prediction_source'] == 'model']

    for day, group in df.groupby('day'):
        top = group.nlargest(top_n_per_day, value_column)
        for rank, (_, row) in enumerate(top.iterrows(), 1):
            kwh = float(row[value_column])
            raw_kwh = float(row.get('predicted_kwh_adjusted', row.get('predicted_kwh', kwh)))
            recs.append(ApplianceRecommendation(
                day=str(day),
                hour=int(row['hour']),
                predicted_kwh=raw_kwh,
                predicted_kw=raw_kwh,
                appliances=_appliances_for_hour(kwh),
                rank=rank,
            ))
    return recs


def format_adjust_report(report: IntradayAdjustReport | None) -> str:
    if report is None:
        return ''
    if not report.applied:
        return f'  Korekta intraday: nie zastosowano ({report.reason})'
    return (
        f'  Korekta intraday: {report.actual_cumulative_kwh:.1f} / '
        f'{report.raw_forecast_cumulative_kwh:.1f} kWh → skala {report.blended_scale:.2f} '
        f'(chmury×{report.cloudy_factor:.2f}, {report.hours_compared}h) | '
        f'dziś ~{report.daily_total_adjusted_kwh:.1f} kWh (raw {report.daily_total_raw_kwh:.1f}) '
        f'[{report.reason}]'
    )
