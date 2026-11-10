#!/usr/bin/env python3
"""CS4 z odjęciem wagi za pochmurne dni (what-if, shadow, bez zmiany prod).

Czyta ostatni launchd `data/processed/pv_forecast_cs4.csv` i dla każdego dnia liczy:
- CS4 raw (czysty model, cały dzień) oraz CS4 hybryda (Fox actual minione + model),
- CS4 × cloudy_factor (domyślnie 0,80; `FORECAST_CLOUDY_EXTRA_SCALE`) — stosowany gdy
  Accu → pochmurny LUB średni cloud modelu ≥ `FORECAST_CLOUDY_THRESHOLD_PCT` (70),
- CS4 konserwatywny (× `conservative_margin`, 0,75 przy cloud ≥70, inaczej 0,85).

Prod: `FORECAST_OPERATIONAL_ADJUST=0` i kara cloudy nigdy nie dotyczy D+1/D+2.
Ten skrypt pokazuje, jak wyglądałoby CS4 z karą na każdy dzień. Bez Fox Cloud, bez zapisu do DB.

Użycie:
    PYTHONPATH=$PWD ./venv/bin/python scripts/weather/cs4_cloudy_discount.py [--days 3]
"""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import pandas as pd

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass

from src.models.intraday_forecast_adjust import cloudy_day_factor, conservative_margin
from src.weather.accu_regime import classify_regime_from_accu, load_accu_for_target_day

ROOT = Path(__file__).resolve().parents[2]
CS4_CSV = ROOT / 'data' / 'processed' / 'pv_forecast_cs4.csv'


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, default=3)
    ap.add_argument('--csv', default=str(CS4_CSV))
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    if 'predicted_kwh_raw' not in df.columns:
        df['predicted_kwh_raw'] = df['predicted_kwh']
    today = date.today().isoformat()
    days = sorted(df['day'].astype(str).unique())
    days = [d for d in days if d >= today][: args.days]

    extra = cloudy_day_factor(100.0)  # współczynnik kary (cloud ≥ próg)
    rows = []
    for d in days:
        g = df[df['day'].astype(str) == d]
        cloud_avg = float(g['cloud_cover_pct'].mean()) if 'cloud_cover_pct' in g else None
        raw = float(g['predicted_kwh_raw'].sum())
        hybrid = float(g['predicted_kwh'].sum())

        snap = load_accu_for_target_day(d)
        regime = None
        if snap is not None:
            regime = classify_regime_from_accu(
                brightness=snap.brightness,
                cloud_pct=snap.cloud_pct,
                precip_mm=snap.precip_mm,
                thunder_prob_pct=snap.thunder_prob_pct,
            )
        by_model = cloudy_day_factor(cloud_avg) < 1.0
        by_accu = regime == 'pochmurny'
        factor = extra if (by_model or by_accu) else 1.0
        why = '+'.join(x for x, ok in (('Accu', by_accu), ('model cloud', by_model)) if ok) or '—'

        # D+0: minione godziny Fox bez zmian, kara tylko na model (przyszłe godziny)
        is_actual = g.get('prediction_source', pd.Series(['model'] * len(g))) == 'foxess_actual'
        adj = float(g.loc[is_actual, 'predicted_kwh'].sum() + g.loc[~is_actual, 'predicted_kwh_raw'].sum() * factor)
        margin = conservative_margin(100.0 if (by_model or by_accu) else cloud_avg)
        rows.append(
            dict(
                day=d,
                regime=regime or '—',
                cloud_avg=cloud_avg,
                raw=raw,
                hybrid=hybrid,
                factor=factor,
                why=why,
                cs4_disc=adj,
                cs4_cons=adj * margin,
                margin=margin,
                n_actual=int(is_actual.sum()),
            )
        )

    print('| Dzień | Accu reżim | cloud modelu | CS4 raw | CS4 hybryda | waga | powód | **CS4 − pochmurne** | CS4 konserw. |')
    print('|---|---|---:|---:|---:|---:|---|---:|---:|')
    for r in rows:
        print(
            f"| {r['day']} | {r['regime']} | {r['cloud_avg']:.1f}% | {r['raw']:.2f} | {r['hybrid']:.2f} | "
            f"×{r['factor']:.2f} | {r['why']} | **{r['cs4_disc']:.2f}** | {r['cs4_cons']:.2f} (×{r['margin']:.2f}) |"
        )
    print()
    print('Uwaga: dla D+0 godziny z Fox actual zostają bez zmian; kara tylko na przyszłe godziny modelu.')


if __name__ == '__main__':
    main()
