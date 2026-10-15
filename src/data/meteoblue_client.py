"""
Klient Meteoblue Free Weather API (Forecast).

Zapisuje JSON do METEOBLUE_OUT_DIR i agreguje dzienne pod weather_notes.
Lokalizacja: METEOBLUE_LAT/LON albo WEATHER_LAT/LON.
Nie loguj klucza ani dokładnego GPS.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PACKAGES = 'basic-1h_clouds-3h'
DEFAULT_OUT = 'data/raw/weather/meteoblue'
USER_AGENT = 'smart-energy-model/meteoblue-client'


def _env(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name)
    if v is None or not str(v).strip():
        return default
    return str(v).strip()


def resolve_coords() -> tuple[float, float]:
    lat_s = _env('METEOBLUE_LAT') or _env('WEATHER_LAT')
    lon_s = _env('METEOBLUE_LON') or _env('WEATHER_LON')
    if not lat_s or not lon_s:
        raise ValueError('Brak WEATHER_LAT/LON (lub METEOBLUE_LAT/LON) w .env')
    return float(lat_s), float(lon_s)


def resolve_out_dir() -> Path:
    raw = _env('METEOBLUE_OUT_DIR', DEFAULT_OUT) or DEFAULT_OUT
    p = Path(raw)
    return p if p.is_absolute() else ROOT / p


def api_key() -> str:
    key = _env('METEOBLUE_API_KEY')
    if not key:
        raise ValueError('METEOBLUE_API_KEY jest puste — uzupełnij .env')
    return key


def packages() -> str:
    return _env('METEOBLUE_PACKAGES', DEFAULT_PACKAGES) or DEFAULT_PACKAGES


def forecast_url(lat: float, lon: float, pkgs: str, key: str) -> str:
    # Free API: https://my.meteoblue.com/packages/<pkg1>_<pkg2>?lat=&lon=&apikey=
    return (
        f'https://my.meteoblue.com/packages/{pkgs}'
        f'?lat={lat}&lon={lon}&apikey={key}&format=json'
    )


def fetch_forecast(
    *,
    lat: float | None = None,
    lon: float | None = None,
    pkgs: str | None = None,
    key: str | None = None,
    timeout: float = 45.0,
) -> dict[str, Any]:
    if lat is None or lon is None:
        lat, lon = resolve_coords()
    pkgs = pkgs or packages()
    key = key or api_key()
    url = forecast_url(lat, lon, pkgs, key)
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = ''
        try:
            body = e.read().decode()[:300]
        except Exception:
            pass
        raise RuntimeError(f'Meteoblue HTTP {e.code}: {body or e.reason}') from e


def save_raw_json(payload: dict[str, Any], out_dir: Path | None = None) -> Path:
    out_dir = out_dir or resolve_out_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M')
    path = out_dir / f'meteoblue_{stamp}.json'
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    latest = out_dir / 'meteoblue_latest.json'
    latest.write_text(path.read_text(encoding='utf-8'), encoding='utf-8')
    return path


def _day_hour(ts: str) -> tuple[str, int]:
    # "2026-10-14 07:00" albo ISO
    day = ts[:10]
    hour = int(ts[11:13])
    return day, hour


def aggregate_daily(
    payload: dict[str, Any],
    *,
    daylight_hours: tuple[int, int] = (6, 20),
) -> list[dict[str, Any]]:
    """Agregaty dzienne pod weather_notes (bez dokładnego GPS w note_text)."""
    h0, h1 = daylight_hours
    data_1h = payload.get('data_1h') or {}
    data_3h = payload.get('data_3h') or {}
    data_day = payload.get('data_day') or {}

    by: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            'precip_mm': 0.0,
            'precip_probs': [],
            'temps': [],
            'uv': [],
            'wind': [],
            'clouds': [],
            'n_h': 0,
        }
    )

    times = data_1h.get('time') or []
    for i, ts in enumerate(times):
        day, hour = _day_hour(ts)
        if hour < h0 or hour > h1:
            continue
        row = by[day]
        row['n_h'] += 1
        prec = data_1h.get('precipitation') or []
        if i < len(prec) and prec[i] is not None:
            row['precip_mm'] += float(prec[i])
        for src, dst in (
            ('precipitation_probability', 'precip_probs'),
            ('temperature', 'temps'),
            ('uvindex', 'uv'),
            ('windspeed', 'wind'),
        ):
            vals = data_1h.get(src) or []
            if i < len(vals) and vals[i] is not None:
                row[dst].append(float(vals[i]))

    times3 = data_3h.get('time') or []
    clouds = data_3h.get('totalcloudcover') or []
    for i, ts in enumerate(times3):
        day, hour = _day_hour(ts)
        if hour < h0 or hour > h1:
            continue
        if i < len(clouds) and clouds[i] is not None:
            by[day]['clouds'].append(float(clouds[i]))

    # data_day jako uzupełnienie (gdy brak 1h/3h)
    day_times = data_day.get('time') or []
    for i, ts in enumerate(day_times):
        day = ts[:10]
        row = by[day]
        if not row['clouds']:
            mean_c = data_day.get('totalcloudcover_mean') or []
            if i < len(mean_c) and mean_c[i] is not None:
                row['clouds'].append(float(mean_c[i]))
        if row['precip_mm'] == 0.0:
            day_p = data_day.get('precipitation') or []
            if i < len(day_p) and day_p[i] is not None:
                row['precip_mm'] = float(day_p[i])
        if not row['temps']:
            tmax = data_day.get('temperature_max') or []
            if i < len(tmax) and tmax[i] is not None:
                row['temps'].append(float(tmax[i]))

    out: list[dict[str, Any]] = []
    for day in sorted(by):
        row = by[day]
        clouds = row['clouds']
        temps = row['temps']
        probs = row['precip_probs']
        uv = row['uv']
        wind = row['wind']
        cloud_mean = round(sum(clouds) / len(clouds), 1) if clouds else None
        tmax = round(max(temps), 1) if temps else None
        pprob = round(max(probs), 0) if probs else None
        uv_max = round(max(uv), 1) if uv else None
        wind_mean = round(sum(wind) / len(wind), 1) if wind else None
        precip = round(row['precip_mm'], 2)
        note = (
            f'MB Free API auto · cloud~{cloud_mean}% (6–20) · '
            f'opad {precip} mm · Pmax {pprob}% · Tmax~{tmax}°'
        )
        out.append(
            {
                'note_day': day,
                'cloud_cover_pct': cloud_mean,
                'precip_mm': precip,
                'precip_prob_pct': pprob,
                'uv_index': uv_max,
                'wind_kmh': wind_mean,
                'temperature_max_c': tmax,
                'note_text': note,
            }
        )
    return out


def write_stub_markdown(
    days: list[dict[str, Any]],
    *,
    raw_path: Path | None = None,
    stub_dir: Path | None = None,
) -> Path:
    stub_dir = stub_dir or (ROOT / 'data' / 'processed' / 'weather_runs')
    stub_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    path = stub_dir / f'{today}_meteoblue.md'
    lines = [
        f'# Meteoblue stub — {today}',
        '',
        'Źródło: Free Forecast API (`basic` + `clouds`). Accu wpisuj ręcznie w dashboardzie.',
        '',
        '| Dzień | Cloud 6–20 % | Opad mm | P max % | T max °C | UV |',
        '|-------|-------------:|--------:|--------:|---------:|---:|',
    ]
    for d in days:
        lines.append(
            f"| **{d['note_day'][8:10]}.{d['note_day'][5:7]}** | "
            f"{d.get('cloud_cover_pct') if d.get('cloud_cover_pct') is not None else '—'} | "
            f"{d.get('precip_mm') if d.get('precip_mm') is not None else '—'} | "
            f"{d.get('precip_prob_pct') if d.get('precip_prob_pct') is not None else '—'} | "
            f"{d.get('temperature_max_c') if d.get('temperature_max_c') is not None else '—'} | "
            f"{d.get('uv_index') if d.get('uv_index') is not None else '—'} |"
        )
    raw_ref = None
    if raw_path is not None:
        try:
            raw_ref = raw_path.resolve().relative_to(ROOT)
        except ValueError:
            raw_ref = raw_path.name
    lines += ['', f'Raw JSON: `{raw_ref}`' if raw_ref else '', '']
    path.write_text('\n'.join(lines), encoding='utf-8')
    latest = stub_dir / 'meteoblue_latest.md'
    latest.write_text(path.read_text(encoding='utf-8'), encoding='utf-8')
    return path
