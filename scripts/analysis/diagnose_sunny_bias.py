#!/usr/bin/env python3
"""
Diagnoza: skąd niedoszacowanie na dniach jasnych (Fox >= 25 kWh)?

Rozdziela błąd na:
  1) model (hindcast z POGODĄ Z ARCHIWUM, trening tylko sprzed --holdout-from),
  2) wejście NWP (prognoza radiacji/chmur vs archiwum),
  3) kształt dnia (godziny: poranek / południe / wieczór),
  4) sprawność PV na kWh/m2 (trend jesienny).

Użycie:
    PYTHONPATH=$PWD ./venv/bin/python scripts/analysis/diagnose_sunny_bias.py
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sklearn.base import clone

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
warnings.filterwarnings('ignore')
load_dotenv(ROOT / '.env')

from src.features.pv_features_hourly_extended import load_hourly_training_frame_extended  # noqa: E402
from src.models.pv_hourly_predictor import TARGET_COLUMN  # noqa: E402

SUNNY_MIN_KWH = 25.0


def pct(a: float, b: float) -> float:
    return (a - b) / b * 100.0 if b else float('nan')


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', default=str(ROOT / 'models/pv_hourly_model.joblib'))
    ap.add_argument('--start', default='2025-06-01')
    ap.add_argument('--end', default='2026-10-04')
    ap.add_argument('--holdout-from', default='2026-09-01')
    ap.add_argument('--db', default=str(ROOT / 'data/energy_model.db'))
    args = ap.parse_args()

    data = joblib.load(args.model)
    cols = data['feature_columns']
    fr = load_hourly_training_frame_extended(
        start_date=args.start, end_date=args.end,
        latitude=data.get('latitude'), longitude=data.get('longitude'),
    )
    fr['day'] = pd.to_datetime(fr['day'])
    rad_col = next((c for c in cols if 'radiation' in c and 'wm2' in c), None) or next(
        c for c in cols if 'radiation' in c
    )
    cloud_col = next((c for c in cols if c.startswith('cloud_cover')), None)
    print(f'Ramka: {len(fr)} h, {fr.day.nunique()} dni, {fr.day.min().date()}–{fr.day.max().date()}')
    print(f'Cechy: {len(cols)} · radiacja={rad_col} · chmury={cloud_col}\n')

    pipe = data['pipeline']
    fr['pred_insample'] = pipe.predict(fr[cols])

    hold = pd.Timestamp(args.holdout_from)
    tr = fr[fr.day < hold]
    te = fr[fr.day >= hold].copy()
    oos = clone(pipe)
    oos.fit(tr[cols], tr[TARGET_COLUMN])
    te['pred_oos'] = oos.predict(te[cols])
    fr = fr.merge(te[['day', 'hour', 'pred_oos']], on=['day', 'hour'], how='left')

    daily = fr.groupby('day').agg(
        act=(TARGET_COLUMN, 'sum'),
        ins=('pred_insample', 'sum'),
        oos=('pred_oos', 'sum'),
        rad=(rad_col, 'sum'),
    ).reset_index()
    daily['month'] = daily.day.dt.to_period('M')
    daily['sunny'] = daily.act >= SUNNY_MIN_KWH

    print('== 1) Bias na dniach jasnych wg miesiąca (pogoda z archiwum) ==')
    print('   in-sample = model produkcyjny (widział te dni); OOS = fit tylko < '
          f'{args.holdout_from}')
    rows = []
    for mo, g in daily[daily.sunny].groupby('month'):
        row = {'miesiąc': str(mo), 'n': len(g), 'Fox śr.': g.act.mean(),
               'bias in-sample %': pct(g.ins.sum(), g.act.sum())}
        if g.oos.notna().any():
            gg = g[g.oos.notna()]
            row['bias OOS %'] = pct(gg.oos.sum(), gg.act.sum())
        rows.append(row)
    print(pd.DataFrame(rows).round(1).to_string(index=False))

    s = daily[daily.sunny & (daily.day >= '2026-09-02')]
    print(f'\n   Dni jasne od 02.09: n={len(s)} · bias in-sample {pct(s.ins.sum(), s.act.sum()):+.1f}%'
          f' · OOS {pct(s.oos.sum(), s.act.sum()):+.1f}%')

    print('\n== 2) Kształt dnia: Fox / model wg godziny (dni jasne od 02.09, OOS) ==')
    h = fr[(fr.day.isin(s.day)) & fr.pred_oos.notna()].groupby('hour').agg(
        fox=(TARGET_COLUMN, 'mean'), pred=('pred_oos', 'mean'), ins=('pred_insample', 'mean'))
    h['bias OOS %'] = (h.pred - h.fox) / h.fox * 100
    h['bias in-sample %'] = (h.ins - h.fox) / h.fox * 100
    print(h.round(2).to_string())

    print('\n== 3) Sprawność: Fox kWh na 1 kWh/m2 radiacji dnia (dni jasne) — tygodniowo ==')
    sd = daily[daily.sunny & (daily.rad > 0)].copy()
    sd['eff'] = sd.act / (sd.rad / 1000.0)
    sd['wk'] = sd.day.dt.to_period('W-SUN')
    w = sd.groupby('wk').agg(n=('eff', 'size'), eff=('eff', 'mean'), fox=('act', 'mean'),
                             rad=('rad', 'mean'))
    print(w.tail(14).round(1).to_string())

    # --- NWP: prognoza (ensemble) vs archiwum, radiacja dnia
    con = sqlite3.connect(args.db)
    wx = pd.read_sql_query(
        """
        SELECT date(timestamp) day, data_source src,
               SUM(solar_radiation_wm2) rad, AVG(cloud_cover_percent) cloud, COUNT(*) n
        FROM weather_data
        WHERE date(timestamp) >= '2026-08-27'
          AND CAST(strftime('%H', timestamp) AS INTEGER) BETWEEN 6 AND 20
        GROUP BY 1, 2
        """,
        con,
    )
    con.close()
    wx['day'] = pd.to_datetime(wx.day)
    piv_rad = wx.pivot_table(index='day', columns='src', values='rad')
    piv_cl = wx.pivot_table(index='day', columns='src', values='cloud')
    ens = [c for c in piv_rad.columns if 'ensemble' in c]
    arc = [c for c in piv_rad.columns if 'archive' in c]
    fc = [c for c in piv_rad.columns if c == 'OpenMeteo-forecast']
    if ens and arc:
        j = pd.DataFrame({'ens_rad': piv_rad[ens[0]], 'arc_rad': piv_rad[arc[0]],
                          'ens_cl': piv_cl[ens[0]], 'arc_cl': piv_cl[arc[0]]})
        if fc:
            j['icon_rad'] = piv_rad[fc[0]]
            j['icon_cl'] = piv_cl[fc[0]]
        j = j.join(daily.set_index('day')[['act', 'sunny']], how='inner').dropna(subset=['ens_rad', 'arc_rad'])
        js = j[j.sunny & (j.index >= '2026-09-02')]
        print('\n== 4) Wejście NWP na dniach jasnych od 02.09 (ostatnia zapisana prognoza vs archiwum) ==')
        print(f'   n={len(js)} · radiacja ENS vs archiwum: {pct(js.ens_rad.sum(), js.arc_rad.sum()):+.1f}%'
              + (f' · ICON vs archiwum: {pct(js.icon_rad.sum(), js.arc_rad.sum()):+.1f}%' if 'icon_rad' in js else ''))
        print(f'   chmury śr. [%]: ENS {js.ens_cl.mean():.0f} · archiwum {js.arc_cl.mean():.0f}'
              + (f' · ICON {js.icon_cl.mean():.0f}' if 'icon_cl' in js else ''))
        print('   (uwaga: weather_data trzyma ostatnio zapisaną prognozę dla godziny, nie snapshot @05)')
    else:
        print('\n== 4) Brak kompletu źródeł pogody ens/archive w weather_data ==')


if __name__ == '__main__':
    main()
