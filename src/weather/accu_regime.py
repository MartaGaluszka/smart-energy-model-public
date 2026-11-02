"""AccuWeather reżim (jasny / mix / pochmurny) — ta sama reguła co paper-trade."""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

BRIGHT_SUNNY_MIN = 8.0
CLOUD_SUNNY_MAX = 30.0
PRECIP_SUNNY_MAX = 0.5
BRIGHT_CLOUDY_MAX = 4.0
CLOUD_CLOUDY_MIN = 70.0
PRECIP_CLOUDY_MIN = 2.0
THUNDER_CLOUDY_MIN = 40.0


@dataclass(frozen=True)
class AccuSnapshot:
    target_day: str
    brightness: float | None
    cloud_pct: float | None
    precip_mm: float | None
    precip_prob_pct: float | None
    thunder_prob_pct: float | None
    note_kind: str | None
    accu_source: str = 'AccuWeather'

    def as_dict(self) -> dict[str, Any]:
        return {
            'brightness': self.brightness,
            'cloud_pct': self.cloud_pct,
            'precip_mm': self.precip_mm,
            'precip_prob_pct': self.precip_prob_pct,
            'thunder_prob_pct': self.thunder_prob_pct,
            'note_kind': self.note_kind,
        }


def classify_regime_from_accu(
    *,
    brightness: float | None,
    cloud_pct: float | None,
    precip_mm: float | None,
    thunder_prob_pct: float | None,
    allow_icon_cloud_fallback: bool = False,
    icon_cloud_pct: float | None = None,
) -> str | None:
    """Reżim z pól Accu. Bez fallbacku ICON (operacyjny pick UI/bateria)."""
    cloudy = False
    sunny = False

    if brightness is not None and brightness <= BRIGHT_CLOUDY_MAX:
        cloudy = True
    if cloud_pct is not None and cloud_pct >= CLOUD_CLOUDY_MIN:
        cloudy = True
    if precip_mm is not None and precip_mm >= PRECIP_CLOUDY_MIN:
        cloudy = True
    if thunder_prob_pct is not None and thunder_prob_pct >= THUNDER_CLOUDY_MIN:
        cloudy = True

    if (
        brightness is not None
        and brightness >= BRIGHT_SUNNY_MIN
        and (cloud_pct is None or cloud_pct <= CLOUD_SUNNY_MAX)
        and (precip_mm is None or precip_mm <= PRECIP_SUNNY_MAX)
    ):
        sunny = True

    if allow_icon_cloud_fallback and brightness is None and icon_cloud_pct is not None:
        if icon_cloud_pct >= CLOUD_CLOUDY_MIN:
            cloudy = True
        elif icon_cloud_pct <= CLOUD_SUNNY_MAX:
            sunny = True

    if cloudy and not sunny:
        return 'pochmurny'
    if sunny and not cloudy:
        return 'jasny'
    if cloudy and sunny:
        return 'pochmurny'
    if brightness is not None or cloud_pct is not None or precip_mm is not None:
        return 'mix'
    return None


def pick_model_for_regime(regime: str | None) -> str:
    if regime == 'pochmurny':
        return 'cs4'
    return 'ensemble'


def lumen_operational_label(brightness: float | None) -> str | None:
    """Opis pod PV (nie etykieta Accu „B. jasne” z kalendarza)."""
    if brightness is None:
        return None
    b = float(brightness)
    if b <= 2:
        return 'ciemny'
    if b <= 4:
        return 'pochmurny'
    if b < 8:
        return 'średni'
    return 'jasny'


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _db_path(db_path: str | None) -> Path:
    raw = db_path or os.getenv('DATABASE_PATH', 'data/energy_model.db')
    p = Path(raw)
    return p if p.is_absolute() else _project_root() / p


def _row_to_snapshot(target_day: str, row: Any) -> AccuSnapshot:
    return AccuSnapshot(
        target_day=target_day,
        brightness=_float_or_none(row['brightness_index']),
        cloud_pct=_float_or_none(row['cloud_cover_pct']),
        precip_mm=_float_or_none(row['precip_mm']),
        precip_prob_pct=_float_or_none(row['precip_prob_pct']),
        thunder_prob_pct=_float_or_none(row['thunder_prob_pct']),
        note_kind=str(row['note_kind']) if row['note_kind'] is not None else None,
    )


def _float_or_none(val: Any) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def load_accu_for_target_day(target_day: str, *, db_path: str | None = None) -> AccuSnapshot | None:
    """Karta Accu dla dnia prognozy (daily_summary tego dnia lub jutrzejszy outlook)."""
    db = _db_path(db_path)
    if not db.exists():
        return None

    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    notes = con.execute(
        """
        SELECT note_day, note_kind, brightness_index, cloud_cover_pct,
               precip_mm, precip_prob_pct, thunder_prob_pct, recorded_at
        FROM weather_notes
        WHERE source = 'AccuWeather'
        ORDER BY note_day, recorded_at
        """,
    ).fetchall()
    con.close()
    if not notes:
        return None

    target = date.fromisoformat(target_day)
    by_day: dict[str, list[sqlite3.Row]] = {}
    for n in notes:
        day = str(n['note_day'])[:10]
        by_day.setdefault(day, []).append(n)

    def _pick_same_day(day_key: str) -> AccuSnapshot | None:
        g = by_day.get(day_key)
        if not g:
            return None
        ds = [r for r in g if r['note_kind'] == 'daily_summary' and r['brightness_index'] is not None]
        if ds:
            return _row_to_snapshot(target_day, ds[-1])
        with_bri = [r for r in g if r['brightness_index'] is not None]
        if with_bri:
            return _row_to_snapshot(target_day, with_bri[-1])
        return _row_to_snapshot(target_day, g[-1])

    snap = _pick_same_day(target_day)
    if snap is not None and (
        snap.brightness is not None or snap.cloud_pct is not None or snap.precip_mm is not None
    ):
        return snap

    prev = (target - timedelta(days=1)).isoformat()
    g = by_day.get(prev)
    if not g:
        return snap
    ft = [r for r in g if r['note_kind'] == 'forecast_tomorrow']
    if ft:
        return _row_to_snapshot(target_day, ft[-1])
    return snap
