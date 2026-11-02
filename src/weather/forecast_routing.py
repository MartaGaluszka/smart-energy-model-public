"""Operacyjny pick prognozy PV: Accu pochmurny → CS4, inaczej ensemble (RF16×NWP)."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import pandas as pd

from src.weather.accu_regime import (
    AccuSnapshot,
    classify_regime_from_accu,
    load_accu_for_target_day,
    lumen_operational_label,
    pick_model_for_regime,
)


def accu_cs4_routing_enabled() -> bool:
    for key in ('ACCU_CS4_UI', 'ACCU_CS4_ROUTING'):
        val = os.getenv(key, '').strip().lower()
        if val in ('1', 'true', 'yes'):
            return True
    return False


@dataclass(frozen=True)
class ForecastDisplayRouting:
    enabled: bool
    regime: str | None
    display_model: str
    primary_model: str
    accu: AccuSnapshot | None

    @property
    def uses_cs4(self) -> bool:
        return self.display_model == 'cs4'


def resolve_forecast_display(
    target_day: str,
    *,
    db_path: str | None = None,
) -> ForecastDisplayRouting:
    enabled = accu_cs4_routing_enabled()
    if not enabled:
        return ForecastDisplayRouting(
            enabled=False,
            regime=None,
            display_model='ensemble',
            primary_model='ensemble',
            accu=None,
        )

    accu = load_accu_for_target_day(target_day, db_path=db_path)
    regime = None
    if accu is not None:
        regime = classify_regime_from_accu(
            brightness=accu.brightness,
            cloud_pct=accu.cloud_pct,
            precip_mm=accu.precip_mm,
            thunder_prob_pct=accu.thunder_prob_pct,
            allow_icon_cloud_fallback=False,
        )
    display = pick_model_for_regime(regime)
    return ForecastDisplayRouting(
        enabled=True,
        regime=regime,
        display_model=display,
        primary_model='ensemble',
        accu=accu,
    )


def routing_payload(routing: ForecastDisplayRouting) -> dict[str, Any]:
    accu = routing.accu.as_dict() if routing.accu else None
    lumen_label = None
    if routing.accu is not None:
        lumen_label = lumen_operational_label(routing.accu.brightness)
    return {
        'routing_enabled': routing.enabled,
        'regime': routing.regime,
        'display_model': routing.display_model,
        'primary_model': routing.primary_model,
        'accu': accu,
        'lumen_label': lumen_label,
    }


_cs4_predictor = None
_cs4_predictor_path: str | None = None


def _cs4_model_path() -> str:
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    rel = os.getenv('PV_HOURLY_MODEL_CS4_PATH', 'models/pv_hourly_model_cs4.joblib')
    return rel if os.path.isabs(rel) else os.path.join(root, rel)


def loaded_cs4_predictor():
    global _cs4_predictor, _cs4_predictor_path
    path = _cs4_model_path()
    if _cs4_predictor is not None and _cs4_predictor_path == path:
        return _cs4_predictor
    from src.models.pv_hourly_predictor import PVHourlyPredictor

    predictor = PVHourlyPredictor(model_path=path)
    predictor.load(path)
    _cs4_predictor = predictor
    _cs4_predictor_path = path
    return predictor


def predict_day_frame_cs4(
    target_day: str,
    *,
    as_of: datetime | None = None,
    db_path: str | None,
    hybrid_today: bool,
    use_actual_pv: bool,
) -> pd.DataFrame:
    as_of = as_of or datetime.now()
    pred = loaded_cs4_predictor().predict_days(
        days_ahead=1,
        db_path=db_path,
        from_date=date.fromisoformat(target_day),
        hybrid_today=hybrid_today,
        use_actual_pv=use_actual_pv,
        as_of=as_of,
    )
    if pred.empty:
        return pred
    return pred[pred['day'].astype(str) == target_day].copy()


_cs4_cache: dict[tuple, tuple[float, pd.DataFrame]] = {}
_CS4_CACHE_TTL_S = 180.0


def predict_day_frame_cs4_cached(
    target_day: str,
    *,
    as_of: datetime,
    db_path: str,
    hybrid_today: bool,
    use_actual_pv: bool,
) -> pd.DataFrame:
    bucket = as_of.replace(second=0, microsecond=0).isoformat(timespec='minutes')
    key = (target_day, bucket, hybrid_today, use_actual_pv, db_path, 'cs4')
    now = time.monotonic()
    hit = _cs4_cache.get(key)
    if hit is not None and now - hit[0] < _CS4_CACHE_TTL_S:
        return hit[1].copy()
    frame = predict_day_frame_cs4(
        target_day,
        as_of=as_of,
        db_path=db_path,
        hybrid_today=hybrid_today,
        use_actual_pv=use_actual_pv,
    )
    _cs4_cache[key] = (now, frame)
    return frame.copy()


def archived_cs4_hourly(target_day: str) -> pd.DataFrame:
    from src.models.forecast_validation import load_forecast_snapshot

    fc, _ = load_forecast_snapshot('daily_cs4', target_day)
    return fc
