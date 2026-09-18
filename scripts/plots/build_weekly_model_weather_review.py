#!/usr/bin/env python3
"""
Tabela MAPE: typ dnia (cloud) × wariant prognozy — pod decyzję przed niedzielnym retreningiem.

Źródła:
  - data/processed/forecasts/forecast_validation.csv (ENS/ICON/CS4 @05/@12/peak)
  - forecast_history.csv (XGB+TS daily / peak, gdy brak w validation)
  - weather_data (średnie cloud 6–20, jak plot_july_validation.py)

Wyjście: docs/images/ml/weekly_model_weather_review.md

Użycie:
    PYTHONPATH=. python scripts/plots/build_weekly_model_weather_review.py
    PYTHONPATH=. python scripts/plots/build_weekly_model_weather_review.py --also-refresh-july-summary
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.plots.plot_july_validation import (  # noqa: E402
    DEFAULT_DB,
    DEFAULT_VALIDATION,
    _load_daily_weather,
    _weather_bucket,
    build_july_error_summary,
    load_july_validation,
)

DEFAULT_OUT = ROOT / 'docs/images/ml/weekly_model_weather_review.md'
HISTORY = ROOT / 'data/processed/forecasts/forecast_history.csv'
JULY_START = '2026-07-01'

# (etykieta, kolumna w forecast_validation.csv)
VARIANTS: list[tuple[str, str]] = [
    ('ENS @05', 'predicted_daily_raw'),
    ('ENS @12', 'predicted_midday_raw'),
    ('ICON ld @05', 'predicted_daily_icon'),
    ('ICON ld @12', 'predicted_midday_icon'),
    ('CS4 ld @05', 'predicted_daily_cs4'),
    ('CS4 ld @12', 'predicted_midday_cs4'),
    ('CS4 peak', 'predicted_peak_cs4'),
    ('ICON peak', 'predicted_peak_icon'),
]

XGB_LABELS = [
    ('XGB @05', 'daily_xgb_ts'),
    ('XGB peak', 'peak_xgb_ts'),
]


def _ape(actual: float, pred: float) -> float | None:
    if pred is None or (isinstance(pred, float) and np.isnan(pred)):
        return None
    if actual is None or actual < 0.5:
        return None
    return abs(actual - pred) / actual * 100.0


def _attach_xgb_from_history(m: pd.DataFrame) -> pd.DataFrame:
    if not HISTORY.exists():
        return m
    hist = pd.read_csv(HISTORY)
    hist['target_day'] = hist['target_day'].astype(str)
    hist['run_at'] = pd.to_datetime(hist['run_at'], errors='coerce')

    for label, run_label in XGB_LABELS:
        col = f'_pred_{run_label}'
        vals = []
        for day in m['target_day'].dt.strftime('%Y-%m-%d'):
            h = hist[(hist['target_day'] == day) & (hist['run_label'] == run_label)].copy()
            if h.empty:
                vals.append(np.nan)
                continue
            # Poranna prognoza: run tego samego dnia (≤12:00) lub ostatni przed closeout
            same = h[h['run_at'].dt.strftime('%Y-%m-%d') == day]
            if not same.empty:
                pick = same.sort_values('run_at').iloc[-1]
            else:
                pick = h.sort_values('run_at').iloc[-1]
            vals.append(float(pick['predicted_kwh']))
        m[col] = vals
        m[f'ape_{label}'] = [
            _ape(a, p) for a, p in zip(m['actual_pv_total'], m[col])
        ]
    return m


def _prepare_frame(validation_path: Path, db_path: Path) -> pd.DataFrame:
    df = load_july_validation(validation_path)
    if df.empty:
        return df

    weather = _load_daily_weather(db_path, JULY_START)
    m = df.copy()
    m['day'] = pd.to_datetime(m['target_day']).dt.normalize()
    if not weather.empty:
        m = m.merge(weather, on='day', how='left')
    else:
        m['cloud'] = np.nan

    m['weather_type'] = m['cloud'].map(_weather_bucket)
    actual = m['actual_pv_total']

    for label, col in VARIANTS:
        if col not in m.columns:
            m[f'ape_{label}'] = np.nan
            continue
        m[f'ape_{label}'] = [
            _ape(a, p) for a, p in zip(actual, pd.to_numeric(m[col], errors='coerce'))
        ]

    m = _attach_xgb_from_history(m)
    return m


def _allowed_ape_columns(m: pd.DataFrame) -> list[str]:
    wanted = [f'ape_{label}' for label, _ in VARIANTS] + [f'ape_{label}' for label, _ in XGB_LABELS]
    return [c for c in wanted if c in m.columns]


def _best_daily_at05(m: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in _allowed_ape_columns(m) if '@05' in c]
    out = m.copy()
    labels, vals = [], []
    for _, row in out.iterrows():
        candidates = []
        for c in cols:
            v = row.get(c)
            if v is not None and not (isinstance(v, float) and np.isnan(v)):
                candidates.append((c.replace('ape_', ''), float(v)))
        if candidates:
            name, val = min(candidates, key=lambda x: x[1])
            labels.append(name)
            vals.append(val)
        else:
            labels.append('')
            vals.append(np.nan)
    out['best_daily@05'] = labels
    out['best_ape@05'] = vals
    return out


def _mape_table(m: pd.DataFrame, ape_cols: list[str], title: str) -> list[str]:
    lines = [f'#### {title}', '']
    header = '| Typ dnia | n | ' + ' | '.join(c.replace('ape_', '') for c in ape_cols) + ' |'
    sep = '|---|' + '|'.join(['---:'] * (len(ape_cols) + 1)) + '|'
    lines.extend([header, sep])

    for wtype, g in m.groupby('weather_type', sort=False):
        if wtype == 'brak pogody' or g.empty:
            continue
        cells = [str(len(g))]
        for c in ape_cols:
            v = g[c].mean()
            cells.append(f'{v:.1f}%' if pd.notna(v) else '—')
        lines.append(f'| {wtype} | ' + ' | '.join(cells) + ' |')
    lines.append('')
    return lines


def _win_counts(m: pd.DataFrame) -> list[str]:
    lines = ['#### Najniższy |APE| @05 (porównanie daily snapshotów)', '']
    m = _best_daily_at05(m)
    sub = m[m['best_daily@05'].astype(str).str.len() > 0]
    if sub.empty:
        lines.append('_Brak closeoutów._')
        lines.append('')
        return lines
    vc = sub['best_daily@05'].value_counts()
    lines.append('| Wariant | dni (wygrał @05) |')
    lines.append('|---:|---:|')
    for name, cnt in vc.items():
        lines.append(f'| {name} | {cnt} |')
    lines.append('')
    cloudy = sub[sub['weather_type'] == 'pochmurny / deszczowy']
    if not cloudy.empty:
        cvc = cloudy['best_daily@05'].value_counts()
        lines.append(
            '**Pochmurne / deszczowe:** '
            + ', '.join(f'{name} **{int(cnt)}×**' for name, cnt in cvc.items())
        )
        lines.append('')
    return lines


def build_markdown(m: pd.DataFrame, *, generated: date) -> str:
    if m.empty:
        return (
            f'# Review modeli × pogoda\n\n'
            f'_Wygenerowano: **{generated.isoformat()}** — brak closeoutów w validation._\n'
        )

    ape_cols = _allowed_ape_columns(m)
    last_day = m['target_day'].max()
    n_days = len(m)
    nd = generated
    last_28 = m[m['target_day'] >= pd.Timestamp(nd - timedelta(days=28))]
    last_7 = m[m['target_day'] >= pd.Timestamp(nd - timedelta(days=7))]

    lines = [
        '# Review modeli × pogoda (closeouty)',
        '',
        f'**Wygenerowano:** {generated.isoformat()} (sobotni przegląd przed retreningiem niedzielnym)  ',
        f'**Zakres closeoutów:** {m["target_day"].min().date()} → {last_day.date()} (**{n_days}** dni)  ',
        '**Metryka:** |APE| % = |Fox − prognoza| / Fox × 100 · pogoda: średnie cloud **6–20** (ICON w DB)  ',
        '**Nie w tabeli:** UKMO solo / oneshot ½ — tylko w notatkach dnia (`oneshot_rf_icon_vs_ukmo.py`).  ',
        '',
        '**Skrypt:** [`scripts/plots/build_weekly_model_weather_review.py`](../../scripts/plots/build_weekly_model_weather_review.py) · '
        'harmonogram: [`mlops/weekly_model_review.sh`](../../mlops/weekly_model_review.sh) · launchd **sobota 10:00**',
        '',
        '---',
        '',
        '### Decyzja przed niedzielą (skrót)',
        '',
    ]

    cloudy = m[m['weather_type'] == 'pochmurny / deszczowy']
    sunny = m[m['weather_type'] == 'słoneczny / mało chmur']

    def _mean_col(frame: pd.DataFrame, col: str) -> float | None:
        if col not in frame.columns or frame.empty:
            return None
        v = frame[col].mean()
        return float(v) if pd.notna(v) else None

    ens_c = _mean_col(cloudy, 'ape_ENS @05')
    cs4_c = _mean_col(cloudy, 'ape_CS4 ld @05')
    ens_s = _mean_col(sunny, 'ape_ENS @05')
    if ens_c is not None and cs4_c is not None:
        if cs4_c < ens_c - 1.0:
            lines.append(
                f'- **Pochmurne/deszczowe** (n={len(cloudy)}): CS4 @05 **{cs4_c:.1f}%** vs ENS **{ens_c:.1f}%** '
                '→ rozważ routing / shadow CS4 (paper Accu).'
            )
        else:
            lines.append(
                f'- **Pochmurne/deszczowe** (n={len(cloudy)}): ENS @05 **{ens_c:.1f}%** ≤ CS4 **{cs4_c:.1f}%** '
                '→ trzymaj **primary ENS**.'
            )
    if ens_s is not None:
        lines.append(f'- **Słoneczne** (n={len(sunny)}): ENS @05 średnio **{ens_s:.1f}%** — nie przełączaj na CS4 globalnie.')
    xgb_p = _mean_col(m, 'ape_XGB peak')
    ens_p = _mean_col(m, 'ape_ENS @12')
    if xgb_p is not None and ens_p is not None and xgb_p < ens_p - 1.0:
        lines.append(
            f'- **Peak @16:** XGB **{xgb_p:.1f}%** vs ENS @12 **{ens_p:.1f}%** — shadow XGB warto monitorować; '
            'retrening niedzielny i tak odświeża wszystkie trzy jobliby.'
        )
    lines.append('')

    lines.extend(_mape_table(m, ape_cols, 'Cała seria (od lipca)'))
    if len(last_28) >= 5:
        lines.extend(_mape_table(last_28, ape_cols, 'Ostatnie 28 dni'))
    if len(last_7) >= 3:
        lines.extend(_mape_table(last_7, ape_cols, 'Ostatnie 7 dni'))
    lines.extend(_win_counts(m))

    lines.extend([
        '---',
        '',
        'Powiązane: [`july_validation_summary.md`](july_validation_summary.md) (primary + hybryda) · '
        'paper-trade — tylko repo prywatne · '
        'wykres: [`july_validation_plot.png`](july_validation_plot.png)',
        '',
    ])
    return '\n'.join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description='MAPE × pogoda × wariant (review sobotni)')
    parser.add_argument('--input', default=str(DEFAULT_VALIDATION))
    parser.add_argument('--db', default=str(DEFAULT_DB))
    parser.add_argument('--output', default=str(DEFAULT_OUT))
    parser.add_argument(
        '--also-refresh-july-summary',
        action='store_true',
        help='Odśwież też july_validation_plot + july_validation_summary.md',
    )
    args = parser.parse_args()

    m = _prepare_frame(Path(args.input), Path(args.db))
    md = build_markdown(m, generated=date.today())
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding='utf-8')
    print(f'✓ {out.relative_to(ROOT)}')
    print(md.split('\n')[0:8])

    if args.also_refresh_july_summary:
        from scripts.plots.plot_july_validation import build_july_plot

        df = load_july_validation(Path(args.input))
        fig = ROOT / 'reports/figures/july_validation_plot.png'
        summary = ROOT / 'docs/images/ml/july_validation_summary.md'
        build_july_plot(df, fig)
        summary.write_text(build_july_error_summary(df, db_path=Path(args.db)), encoding='utf-8')
        print(f'✓ odświeżono {fig.name} + {summary.name}')


if __name__ == '__main__':
    main()
