#!/usr/bin/env python
"""
Oneshot (bez produkcji): ICON w weather_data vs IMGW synop terminowy Kraków-Balice.

Czerwiec 2026 — porównanie godzinowego zachmurzenia:
  • OM/ICON w bazie: cloud_cover_percent (location=home, OpenMeteo-archive)
  • IMGW Balice: NOG oktanty 0–8 → % = NOG/8*100

Nie zmienia .joblib / .env / launchd.

Uruchomienie:
    PYTHONPATH=$PWD python scripts/analysis/oneshot_icon_imgw_clouds_june2026.py
"""

from __future__ import annotations

import csv
import io
import os
import sys
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import sqlite3

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / '.env')

IMGW_ZIP = (
    'https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/'
    'dane_meteorologiczne/terminowe/synop/2026/2026_06_s.zip'
)
IMGW_HEADER = (
    'https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/'
    'dane_meteorologiczne/terminowe/synop/s_t_nag%C5%82%C3%B3wek.csv'
)
OUT_HOURLY = ROOT / 'data/processed/oneshot_icon_vs_imgw_balice_202606_hourly.csv'
OUT_DAILY = ROOT / 'data/processed/oneshot_icon_vs_imgw_balice_202606_daily.csv'


def _http_bytes(url: str, timeout: int = 120) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.read()


def fetch_imgw_balice_nog(year: int = 2026, month: int = 6) -> pd.DataFrame:
    url = (
        'https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/'
        f'dane_meteorologiczne/terminowe/synop/{year}/{year}_{month:02d}_s.zip'
    )
    raw = _http_bytes(url)
    header = _http_bytes(IMGW_HEADER).decode('cp1250').strip()
    cols = next(csv.reader([header]))

    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        csv_name = next(n for n in zf.namelist() if n.endswith('.csv'))
        text = zf.read(csv_name).decode('cp1250')

    rows = []
    for line in text.splitlines():
        parts = next(csv.reader([line]))
        if len(parts) < len(cols):
            continue
        if 'BALICE' not in parts[1].upper():
            continue
        rec = dict(zip(cols, parts))
        try:
            nog = int(float(str(rec['NOG']).replace(',', '.')))
        except (TypeError, ValueError):
            continue
        if nog < 0 or nog > 8:
            continue
        y, m, d, h = int(rec['ROK']), int(rec['MC']), int(rec['DZ']), int(rec['GG'])
        rows.append({
            'timestamp': pd.Timestamp(year=y, month=m, day=d, hour=h),
            'day': f'{y:04d}-{m:02d}-{d:02d}',
            'hour': h,
            'imgw_station': rec['POST'],
            'imgw_nog_okta': nog,
            'imgw_cloud_pct': nog / 8.0 * 100.0,
            'imgw_clcm_okta': pd.to_numeric(rec.get('CLCM'), errors='coerce'),
        })
    return pd.DataFrame(rows)


def load_icon_june(db_path: str) -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(
        """
        SELECT timestamp, cloud_cover_percent AS icon_cloud_pct,
               cloud_cover_low_percent AS icon_low_pct,
               cloud_cover_mid_percent AS icon_mid_pct,
               cloud_cover_high_percent AS icon_high_pct,
               solar_radiation_wm2, precipitation_mm
        FROM weather_data
        WHERE location = 'home'
          AND data_source = 'OpenMeteo-archive'
          AND timestamp >= '2026-06-01' AND timestamp < '2026-07-01'
        ORDER BY timestamp
        """,
        conn,
    )
    conn.close()
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['day'] = df['timestamp'].dt.strftime('%Y-%m-%d')
    df['hour'] = df['timestamp'].dt.hour
    return df


def main() -> None:
    db = os.getenv('DATABASE_PATH', str(ROOT / 'data/energy_model.db'))
    if not Path(db).is_absolute():
        db = str(ROOT / db)

    print('=' * 72)
    print('ONESHOT: ICON (baza) vs IMGW Balice NOG — czerwiec 2026')
    print('Bez zmian produkcji (.joblib / launchd / .env)')
    print('=' * 72)

    print('\n[1] IMGW terminowe Balice...')
    imgw = fetch_imgw_balice_nog(2026, 6)
    print(f'  godzin: {len(imgw)}  stacja: {imgw["imgw_station"].iloc[0]}')

    print('\n[2] weather_data home / OpenMeteo-archive (ICON w .env)...')
    icon = load_icon_june(db)
    print(f'  godzin: {len(icon)}  śr. cloud={icon["icon_cloud_pct"].mean():.1f}%')

    m = icon.merge(
        imgw[['timestamp', 'imgw_nog_okta', 'imgw_cloud_pct', 'imgw_clcm_okta', 'imgw_station']],
        on='timestamp',
        how='inner',
    )
    print(f'\n[3] Join godzinowy: {len(m)} wspólnych godzin')
    if m.empty:
        raise SystemExit('Brak wspólnych godzin — sprawdź strefę czasu / dane')

    m['err_pp'] = m['icon_cloud_pct'] - m['imgw_cloud_pct']
    m['abs_err_pp'] = m['err_pp'].abs()

    mae = float(m['abs_err_pp'].mean())
    bias = float(m['err_pp'].mean())
    corr = float(m['icon_cloud_pct'].corr(m['imgw_cloud_pct']))
    rmse = float(np.sqrt((m['err_pp'] ** 2).mean()))

    print('\n' + '=' * 72)
    print('METRYKI (cała doba, czerwiec)')
    print('=' * 72)
    print(f'  ICON śr. cloud:   {m["icon_cloud_pct"].mean():.1f}%')
    print(f'  IMGW śr. (NOG):   {m["imgw_cloud_pct"].mean():.1f}%  ({m["imgw_nog_okta"].mean():.2f}/8)')
    print(f'  Bias ICON−IMGW:   {bias:+.1f} pp')
    print(f'  MAE |Δ|:          {mae:.1f} pp')
    print(f'  RMSE:             {rmse:.1f} pp')
    print(f'  Korelacja:        {corr:.3f}')

    # daylight 5–20
    dayl = m[(m['hour'] >= 5) & (m['hour'] <= 20)].copy()
    print('\n  (tylko 5–20h)')
    print(f'  Bias: {dayl["err_pp"].mean():+.1f} pp  MAE: {dayl["abs_err_pp"].mean():.1f} pp  '
          f'corr: {dayl["icon_cloud_pct"].corr(dayl["imgw_cloud_pct"]):.3f}')

    daily = (
        m.groupby('day', as_index=False)
        .agg(
            icon_cloud_avg=('icon_cloud_pct', 'mean'),
            imgw_cloud_avg=('imgw_cloud_pct', 'mean'),
            imgw_nog_avg=('imgw_nog_okta', 'mean'),
            bias_pp=('err_pp', 'mean'),
            mae_pp=('abs_err_pp', 'mean'),
            icon_rad_mean=('solar_radiation_wm2', 'mean'),
            precip_om=('precipitation_mm', 'sum'),
        )
    )
    daily['abs_bias_pp'] = daily['bias_pp'].abs()

    # worst / best days by daily MAE
    worst = daily.nlargest(5, 'mae_pp')
    best = daily.nsmallest(5, 'mae_pp')
    print('\nNajgorsze 5 dni (MAE godz.):')
    for _, r in worst.iterrows():
        print(
            f"  {r['day']}: ICON {r['icon_cloud_avg']:.0f}%  IMGW {r['imgw_cloud_avg']:.0f}%  "
            f"bias {r['bias_pp']:+.0f}pp  MAE {r['mae_pp']:.0f}pp"
        )
    print('\nNajlepsze 5 dni (MAE godz.):')
    for _, r in best.iterrows():
        print(
            f"  {r['day']}: ICON {r['icon_cloud_avg']:.0f}%  IMGW {r['imgw_cloud_avg']:.0f}%  "
            f"bias {r['bias_pp']:+.0f}pp  MAE {r['mae_pp']:.0f}pp"
        )

    OUT_HOURLY.parent.mkdir(parents=True, exist_ok=True)
    m.to_csv(OUT_HOURLY, index=False)
    daily.to_csv(OUT_DAILY, index=False)
    print(f'\n✓ {OUT_HOURLY.relative_to(ROOT)}')
    print(f'✓ {OUT_DAILY.relative_to(ROOT)}')

    print('\n' + '=' * 72)
    print('WERDYKT (oneshot)')
    print('=' * 72)
    if corr >= 0.5 and abs(bias) <= 15:
        print(
            f'ICON i Balice korelują (r={corr:.2f}); bias {bias:+.0f} pp — '
            'zostaw ICON w produkcji; to audyt, nie powód do zmiany modelu.'
        )
    elif bias > 15:
        print('ICON systematycznie bardziej pochmurny niż Balice — sprawdź dni PV przed kręceniem cech.')
    elif bias < -15:
        print('ICON jaśniejszy niż Balice — możliwe niedoszacowanie chmur względem stacji.')
    else:
        print('Słaba korelacja — używaj jako audyt wejść, nie feature do RF.')
    print('Balice ≠ dach GPS (~lotnisko). Nie wdrażamy nic do produkcji z tego oneshotu.')
    print(f'Źródło ZIP: {IMGW_ZIP}')


if __name__ == '__main__':
    main()
