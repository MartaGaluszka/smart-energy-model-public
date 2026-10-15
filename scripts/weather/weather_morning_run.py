#!/usr/bin/env python
"""
Poranny run pogodowy bez Cursor: Accu (DB) × MB (API/DB) × ENS/ICON/CS4/XGB.

Wymaga wcześniej wpisanego Accu w dashboardzie (weather_notes).
MB: domyślnie świeży fetch Free API.

Użycie:
  PYTHONPATH=$PWD ./venv/bin/python scripts/weather/weather_morning_run.py
  PYTHONPATH=$PWD ./venv/bin/python scripts/weather/weather_morning_run.py --skip-mb-fetch
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / '.env')

# Reguła paper-trade (jak scripts/analysis/paper_trade_accu_regime.py)
BRIGHT_SUNNY_MIN = 8.0
CLOUD_SUNNY_MAX = 30.0
PRECIP_SUNNY_MAX = 0.5
BRIGHT_CLOUDY_MAX = 4.0
CLOUD_CLOUDY_MIN = 70.0
PRECIP_CLOUDY_MIN = 2.0
THUNDER_CLOUDY_MIN = 40.0

HISTORY = ROOT / 'data' / 'processed' / 'forecasts' / 'forecast_history.csv'
STUB_DIR = ROOT / 'data' / 'processed' / 'weather_runs'


def _db_path() -> Path:
    raw = os.getenv('DATABASE_PATH', 'data/energy_model.db')
    p = Path(raw)
    return p if p.is_absolute() else ROOT / p


def classify_regime(
    brightness: float | None,
    cloud: float | None,
    precip: float | None,
    thunder: float | None,
) -> str | None:
    if brightness is None and cloud is None:
        return None
    cloudy = False
    sunny = False
    if brightness is not None and brightness <= BRIGHT_CLOUDY_MAX:
        cloudy = True
    if cloud is not None and cloud >= CLOUD_CLOUDY_MIN:
        cloudy = True
    if precip is not None and precip >= PRECIP_CLOUDY_MIN:
        cloudy = True
    if thunder is not None and thunder >= THUNDER_CLOUDY_MIN:
        cloudy = True
    if (
        brightness is not None
        and brightness >= BRIGHT_SUNNY_MIN
        and (cloud is None or cloud <= CLOUD_SUNNY_MAX)
        and (precip is None or precip <= PRECIP_SUNNY_MAX)
    ):
        sunny = True
    if cloudy and not sunny:
        return 'pochmurny'
    if sunny and not cloudy:
        return 'jasny'
    if cloudy and sunny:
        return 'pochmurny'
    return 'mix'


def pick_from_regime(regime: str | None) -> str:
    if regime == 'pochmurny':
        return 'CS4'
    if regime in ('jasny', 'mix'):
        return 'RF'
    return '—'


def load_latest_notes(source: str, days: list[str]) -> pd.DataFrame:
    db = _db_path()
    if not db.exists():
        return pd.DataFrame()
    con = sqlite3.connect(db)
    q = """
        SELECT note_day, recorded_at, brightness_index, cloud_cover_pct,
               precip_mm, precip_prob_pct, thunder_prob_pct, uv_index, note_text
        FROM weather_notes
        WHERE source = ? AND note_day IN ({})
        ORDER BY note_day, recorded_at
    """.format(','.join('?' * len(days)))
    df = pd.read_sql(q, con, params=[source, *days])
    con.close()
    if df.empty:
        return df
    df['note_day'] = pd.to_datetime(df['note_day']).dt.strftime('%Y-%m-%d')
    return df.sort_values('recorded_at').groupby('note_day', as_index=False).last()


def load_model_daily(days: list[str]) -> pd.DataFrame:
    """Najnowszy run daily* z forecast_history dla każdego dnia."""
    if not HISTORY.exists():
        return pd.DataFrame()
    hist = pd.read_csv(HISTORY)
    hist['target_day'] = pd.to_datetime(hist['target_day']).dt.strftime('%Y-%m-%d')
    hist['run_at'] = pd.to_datetime(hist['run_at'], errors='coerce')
    label_map = {
        'daily': 'ens',
        'daily_icon': 'icon',
        'daily_cs4': 'cs4',
        'daily_xgb_ts': 'xgb',
    }
    hist = hist[hist['run_label'].isin(label_map)].copy()
    hist = hist[hist['target_day'].isin(days)]
    if hist.empty:
        return pd.DataFrame()
    hist['model'] = hist['run_label'].map(label_map)
    hist = hist.sort_values('run_at').groupby(['target_day', 'model'], as_index=False).last()
    wide = hist.pivot(index='target_day', columns='model', values='predicted_kwh_raw')
    wide = wide.reset_index().rename(columns={'target_day': 'day'})
    return wide


def mb_vs_accu_flag(accu_cloud: float | None, mb_cloud: float | None) -> str:
    if accu_cloud is None or mb_cloud is None:
        return '—'
    delta = mb_cloud - accu_cloud
    if abs(delta) >= 25:
        return f'watch (Δ cloud {delta:+.0f} pp)'
    if abs(delta) >= 15:
        return f'lekki watch (Δ {delta:+.0f})'
    return 'zgoda'


def fmt(v, nd=1):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return '—'
    if isinstance(v, float):
        return f'{v:.{nd}f}'
    return str(v)


def run_mb_fetch(days: int) -> int:
    script = ROOT / 'scripts' / 'weather' / 'fetch_meteoblue.py'
    py = ROOT / 'venv' / 'bin' / 'python'
    cmd = [str(py), str(script), '--days', str(days)]
    env = os.environ.copy()
    env['PYTHONPATH'] = str(ROOT)
    print('→ fetch Meteoblue…', flush=True)
    return subprocess.call(cmd, cwd=str(ROOT), env=env)


def write_report(rows: list[dict], *, missing_accu: list[str], out_path: Path) -> Path:
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    lines = [
        f'# Poranny run pogodowy — {now}',
        '',
        'Bez Cursor: Accu z dashboardu (`weather_notes`) · MB Free API · modele z `forecast_history` (daily @05+).',
        '',
        '| Dzień | Accu Lumen/cloud/mm | Reżim → pick | MB cloud/mm | vs Accu | ENS | ICON | CS4 | XGB |',
        '|-------|---------------------|--------------|-------------|--------|----:|-----:|----:|----:|',
    ]
    for r in rows:
        accu = (
            f"{fmt(r.get('accu_lumen'),0)}/{fmt(r.get('accu_cloud'),0)}%/"
            f"{fmt(r.get('accu_mm'),1)}"
        )
        mb = f"{fmt(r.get('mb_cloud'),0)}%/{fmt(r.get('mb_mm'),1)}"
        lines.append(
            f"| **{r['day'][8:10]}.{r['day'][5:7]}** | {accu} | "
            f"{r.get('regime') or '—'}→**{r.get('pick') or '—'}** | {mb} | "
            f"{r.get('flag')} | {fmt(r.get('ens'),1)} | {fmt(r.get('icon'),1)} | "
            f"{fmt(r.get('cs4'),1)} | {fmt(r.get('xgb'),1)} |"
        )

    lines += ['', '## Checklist', '']
    if missing_accu:
        lines.append(
            f'- ⚠️ Brak Accu w DB dla: {", ".join(missing_accu)} — wpisz w dashboardzie i odpal ponownie.'
        )
    else:
        lines.append('- ✅ Accu obecne dla wszystkich dni w oknie.')
    lines += [
        '- MB: `./mlops/fetch_meteoblue.sh` (ten run już woła, chyba że `--skip-mb-fetch`).',
        '- Primary kWh bez zmian (RF16 + ENS). Paper pick = kolumna pick (obserwacja).',
        '',
        '## Jak użyć w czacie (opcjonalnie)',
        '',
        'Jeśli chcesz dopisać `NOTATKA_YYYY-MM-DD.md` / paper: wklej tylko',
        '`@data/processed/weather_runs/morning_latest.md` i napisz „dopisz notatkę dnia”.',
        '',
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text('\n'.join(lines), encoding='utf-8')
    latest = out_path.parent / 'morning_latest.md'
    latest.write_text(out_path.read_text(encoding='utf-8'), encoding='utf-8')
    return latest


def main() -> int:
    p = argparse.ArgumentParser(description='Poranny run Accu×MB×modele (bez Cursor)')
    p.add_argument('--days', type=int, default=3, help='dziś + outlook (domyślnie 3)')
    p.add_argument('--skip-mb-fetch', action='store_true', help='użyj MB już w DB')
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args()

    today = date.today()
    days = [(today + timedelta(days=i)).isoformat() for i in range(args.days)]

    if not args.skip_mb_fetch and not args.dry_run:
        rc = run_mb_fetch(args.days)
        if rc != 0:
            print(f'⚠️ MB fetch exit={rc} — kontynuuję z DB jeśli jest')

    accu = load_latest_notes('AccuWeather', days)
    mb = load_latest_notes('Meteoblue', days)
    models = load_model_daily(days)

    accu_by = {r['note_day']: r for _, r in accu.iterrows()} if not accu.empty else {}
    mb_by = {r['note_day']: r for _, r in mb.iterrows()} if not mb.empty else {}
    mod_by = {r['day']: r for _, r in models.iterrows()} if not models.empty else {}

    rows = []
    missing_accu = []
    for d in days:
        a = accu_by.get(d)
        m = mb_by.get(d)
        mo = mod_by.get(d)
        if a is None:
            missing_accu.append(d)
            bri = cloud = precip = thunder = None
        else:
            bri = None if pd.isna(a.get('brightness_index')) else float(a['brightness_index'])
            cloud = None if pd.isna(a.get('cloud_cover_pct')) else float(a['cloud_cover_pct'])
            precip = None if pd.isna(a.get('precip_mm')) else float(a['precip_mm'])
            thunder = None if pd.isna(a.get('thunder_prob_pct')) else float(a['thunder_prob_pct'])
        regime = classify_regime(bri, cloud, precip, thunder)
        mb_cloud = None if m is None or pd.isna(m.get('cloud_cover_pct')) else float(m['cloud_cover_pct'])
        mb_mm = None if m is None or pd.isna(m.get('precip_mm')) else float(m['precip_mm'])
        rows.append(
            {
                'day': d,
                'accu_lumen': bri,
                'accu_cloud': cloud,
                'accu_mm': precip,
                'regime': regime,
                'pick': pick_from_regime(regime),
                'mb_cloud': mb_cloud,
                'mb_mm': mb_mm,
                'flag': mb_vs_accu_flag(cloud, mb_cloud),
                'ens': None if mo is None or 'ens' not in mo or pd.isna(mo.get('ens')) else float(mo['ens']),
                'icon': None if mo is None or 'icon' not in mo or pd.isna(mo.get('icon')) else float(mo['icon']),
                'cs4': None if mo is None or 'cs4' not in mo or pd.isna(mo.get('cs4')) else float(mo['cs4']),
                'xgb': None if mo is None or 'xgb' not in mo or pd.isna(mo.get('xgb')) else float(mo['xgb']),
            }
        )

    print('\nPoranny run:')
    for r in rows:
        print(
            f"  {r['day']}: Accu {fmt(r['accu_lumen'],0)}/{fmt(r['accu_cloud'],0)}% "
            f"→ {r['regime']}→{r['pick']} · MB {fmt(r['mb_cloud'],0)}% · "
            f"ENS {fmt(r['ens'])} ICON {fmt(r['icon'])} · {r['flag']}"
        )
    if missing_accu:
        print(f'⚠️ Brak Accu: {", ".join(missing_accu)}')

    if args.dry_run:
        print('(dry-run)')
        return 0

    stamp = datetime.now().strftime('%Y%m%d_%H%M')
    out = STUB_DIR / f'{today.isoformat()}_morning_{stamp}.md'
    latest = write_report(rows, missing_accu=missing_accu, out_path=out)
    print(f'\n✓ Raport: {out.relative_to(ROOT)}')
    print(f'  latest: {latest.relative_to(ROOT)}')
    return 0 if not missing_accu else 2


if __name__ == '__main__':
    raise SystemExit(main())
