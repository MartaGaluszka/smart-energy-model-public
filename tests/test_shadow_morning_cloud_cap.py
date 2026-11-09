"""Shadow cap porannej sumy @05 — reguła chmura ≥ 88% i ENS ≤ 10 kWh (bez apki, bez prawdziwej bazy)."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pandas as pd

from scripts.analysis import shadow_morning_cloud_cap as cap


def _make_db(path, cloud_by_day: dict[str, float]) -> None:
    con = sqlite3.connect(str(path))
    con.execute('CREATE TABLE weather_data (timestamp DATETIME, cloud_cover_percent REAL)')
    for day, cloud in cloud_by_day.items():
        for hour in (6, 12, 20):
            con.execute(
                'INSERT INTO weather_data VALUES (?, ?)',
                (f'{day} {hour:02d}:00:00', cloud),
            )
    con.commit()
    con.close()


def _make_validation(path, rows: list[tuple[str, float, float]]) -> None:
    pd.DataFrame(
        [
            {'target_day': day, 'actual_pv_total': fox, 'predicted_daily_raw': ens}
            for day, fox, ens in rows
        ]
    ).to_csv(path, index=False)


def _history(n: int, start: date, *, ens: float, fox: float) -> list[tuple[str, float, float]]:
    return [((start + timedelta(days=i)).isoformat(), fox, ens) for i in range(n)]


def test_cap_applies_on_dark_low_ens_day_with_bias(tmp_path):
    """Trzy pochmurne dni z zawyżonym ENS dają bias; kolejny pochmurny dzień z niskim ENS dostaje cap."""
    hist = _history(3, date(2026, 11, 1), ens=8.0, fox=3.0)  # bias +5
    target = ('2026-11-04', 3.5, 7.0)
    days = [d for d, _, _ in hist] + [target[0]]
    _make_db(tmp_path / 'db.sqlite', {d: 95.0 for d in days})
    _make_validation(tmp_path / 'val.csv', hist + [target])

    out = cap.build_shadow(tmp_path / 'val.csv', tmp_path / 'db.sqlite')
    row = out[out['target_day'] == '2026-11-04'].iloc[0]
    assert bool(row['cap_applied']) is True
    assert row['bias_kwh'] == 5.0
    assert row['cap_kwh'] == 2.0
    assert row['abs_err_cap'] < row['abs_err_ens']


def test_cap_skipped_when_ens_above_ceiling(tmp_path):
    """Pochmurny dzień, ale ENS > 10 kWh: nie tniemy (fałszywa wysoka chmura NWP)."""
    hist = _history(3, date(2026, 11, 1), ens=8.0, fox=3.0)
    target = ('2026-11-04', 14.0, 14.5)
    days = [d for d, _, _ in hist] + [target[0]]
    _make_db(tmp_path / 'db.sqlite', {d: 95.0 for d in days})
    _make_validation(tmp_path / 'val.csv', hist + [target])

    row = cap.build_shadow(tmp_path / 'val.csv', tmp_path / 'db.sqlite').iloc[-1]
    assert bool(row['cap_applied']) is False
    assert row['cap_kwh'] == row['ens_kwh']


def test_cap_skipped_when_cloud_below_threshold(tmp_path):
    """Chmura < 88%: cap się nie włącza, nawet przy niskim ENS."""
    hist = _history(3, date(2026, 11, 1), ens=8.0, fox=3.0)
    target = ('2026-11-04', 5.0, 6.0)
    cloud = {d: 95.0 for d, _, _ in hist}
    cloud[target[0]] = 60.0
    _make_db(tmp_path / 'db.sqlite', cloud)
    _make_validation(tmp_path / 'val.csv', hist + [target])

    row = cap.build_shadow(tmp_path / 'val.csv', tmp_path / 'db.sqlite').iloc[-1]
    assert bool(row['cap_applied']) is False
    assert row['cap_kwh'] == 6.0


def test_cap_needs_min_bias_days(tmp_path):
    """Poniżej 3 pochmurnych dni w oknie 28 dni nie ma biasu, więc nie ma cięcia."""
    hist = _history(2, date(2026, 11, 1), ens=8.0, fox=3.0)
    target = ('2026-11-03', 3.5, 7.0)
    days = [d for d, _, _ in hist] + [target[0]]
    _make_db(tmp_path / 'db.sqlite', {d: 95.0 for d in days})
    _make_validation(tmp_path / 'val.csv', hist + [target])

    row = cap.build_shadow(tmp_path / 'val.csv', tmp_path / 'db.sqlite').iloc[-1]
    assert pd.isna(row['bias_kwh'])
    assert bool(row['cap_applied']) is False


def test_negative_bias_is_clamped_and_never_raises_forecast(tmp_path):
    """ENS poniżej Foxa w historii: bias obcięty do 0, cap nie podnosi prognozy."""
    hist = _history(3, date(2026, 11, 1), ens=3.0, fox=6.0)  # bias -3 → 0
    target = ('2026-11-04', 5.0, 4.0)
    days = [d for d, _, _ in hist] + [target[0]]
    _make_db(tmp_path / 'db.sqlite', {d: 95.0 for d in days})
    _make_validation(tmp_path / 'val.csv', hist + [target])

    row = cap.build_shadow(tmp_path / 'val.csv', tmp_path / 'db.sqlite').iloc[-1]
    assert bool(row['cap_applied']) is False
    assert row['cap_kwh'] <= row['ens_kwh']


def test_cap_never_negative(tmp_path):
    """Bias większy niż ENS: cap ścięty do zera, nie ujemny."""
    hist = _history(3, date(2026, 11, 1), ens=9.5, fox=1.0)  # bias +8.5
    target = ('2026-11-04', 0.5, 4.0)
    days = [d for d, _, _ in hist] + [target[0]]
    _make_db(tmp_path / 'db.sqlite', {d: 95.0 for d in days})
    _make_validation(tmp_path / 'val.csv', hist + [target])

    row = cap.build_shadow(tmp_path / 'val.csv', tmp_path / 'db.sqlite').iloc[-1]
    assert bool(row['cap_applied']) is True
    assert row['cap_kwh'] == 0.0


def test_missing_db_does_not_crash_and_leaves_forecast_untouched(tmp_path):
    """Brak bazy pogody: cloud = NaN, shadow zwraca surowy ENS (apka nietknięta)."""
    _make_validation(tmp_path / 'val.csv', _history(5, date(2026, 11, 1), ens=8.0, fox=3.0))
    out = cap.build_shadow(tmp_path / 'val.csv', tmp_path / 'brak.sqlite')
    assert len(out) == 5
    assert not out['cap_applied'].any()
    assert (out['cap_kwh'] == out['ens_kwh']).all()
