#!/usr/bin/env python3
"""
Wykres intraday: RF raw vs hybryda vs korekta operacyjna (+ FoxESS minione h).

Wyjście: docs/images/ml/intraday_raw_vs_adjust.png

Użycie:
    python scripts/plots/plot_intraday_raw_vs_adjust.py
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

os.environ.setdefault('MPLBACKEND', 'Agg')

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / '.env')
os.environ.setdefault('DATABASE_PATH', str(ROOT / 'data' / 'energy_model.db'))

from src.models.intraday_forecast_adjust import _is_enabled, apply_operational_adjustment, format_adjust_report
from src.models.pv_hourly_predictor import PVHourlyPredictor, load_actual_pv_hourly, TARGET_COLUMN


def plot_intraday_raw_vs_adjust(
    out_path: Path | None = None,
    as_of: datetime | None = None,
) -> Path:
    as_of = as_of or datetime.now()
    today = as_of.date().isoformat()
    db_path = str(ROOT / 'data' / 'energy_model.db')
    out_path = out_path or ROOT / 'docs' / 'images' / 'ml' / 'intraday_raw_vs_adjust.png'

    model_path = ROOT / 'models' / 'pv_hourly_model.joblib'
    predictor = PVHourlyPredictor(model_path=str(model_path))
    predictor.load()

    adj_df, _ = predictor.recommend_appliances(
        days_ahead=3, top_n_per_day=5, operational_adjust=True, as_of=as_of,
    )
    _, adjust_report = apply_operational_adjustment(adj_df.copy(), as_of=as_of)

    if today not in set(adj_df['day'].astype(str)):
        raise SystemExit(f'Brak prognozy na dziś ({today}) w adj_df')

    t = adj_df[adj_df['day'].astype(str) == today].sort_values('hour').copy()
    raw_col = 'predicted_kwh_raw' if 'predicted_kwh_raw' in t.columns else 'predicted_kwh'

    actuals = load_actual_pv_hourly(db_path, today, as_of=as_of)

    hybrid_differs = not np.allclose(
        t['predicted_kwh'].values, t[raw_col].values, rtol=0, atol=1e-6, equal_nan=True,
    )
    adjust_differs = (
        'predicted_kwh_adjusted' in t.columns
        and not np.allclose(
            t['predicted_kwh_adjusted'].values,
            t['predicted_kwh'].values,
            rtol=0,
            atol=1e-6,
            equal_nan=True,
        )
    )

    fig, ax = plt.subplots(figsize=(10, 4.5))

    # 1) RF raw — zawsze czysty model ML (cały dzień)
    ax.plot(
        t['hour'], t[raw_col],
        'o--', label='RF raw (prognoza ML)', color='C0', markersize=5, alpha=0.95, zorder=3,
    )

    # 2) Hybryda — FoxESS minione h + RF na przyszłe (≠ rzeczywistość końca dnia)
    if hybrid_differs:
        ax.plot(
            t['hour'], t['predicted_kwh'],
            's-', label='Hybryda dnia (FoxESS+RF)', color='C1', linewidth=2, zorder=2,
        )
    elif actuals.empty:
        ax.plot(
            t['hour'], t['predicted_kwh'],
            's-', label='Hybryda (= RF raw, brak FoxESS)', color='C1', linewidth=2,
            alpha=0.6, zorder=2,
        )

    # 3) Korekta operacyjna — tylko gdy włączona i zmienia prognozę
    if adjust_differs:
        ax.plot(
            t['hour'], t['predicted_kwh_adjusted'],
            'D-', label='Korekta operacyjna', color='C3', linewidth=2, zorder=4,
        )
    elif _is_enabled() and adjust_report and adjust_report.applied:
        ax.plot(
            t['hour'], t['predicted_kwh_adjusted'],
            'D-', label='Korekta operacyjna', color='C3', linewidth=2, zorder=4,
        )

    # 4) FoxESS — rzeczywista produkcja godzinowa (tylko minione godziny)
    if not actuals.empty:
        ax.plot(
            actuals['hour'], actuals[TARGET_COLUMN],
            '^', label='FoxESS rzeczywistość (minione h)', color='green',
            markersize=8, zorder=5, linewidth=0,
        )

    ax.set_xlabel('Godzina')
    ax.set_ylabel('kWh/h')
    ax.set_title(f'Dziś {today}: RF raw vs hybryda / korekta operacyjna')
    ax.legend(loc='upper right', fontsize=9)
    ax.grid(True, alpha=0.3)

    notes = []
    if not _is_enabled():
        notes.append('FORECAST_OPERATIONAL_ADJUST=0')
    if actuals.empty:
        notes.append('brak odczytów FoxESS dla minionych godzin')
    elif adjust_report:
        notes.append(format_adjust_report(adjust_report).split('\n')[0].strip())
    if notes:
        fig.text(0.01, 0.01, ' · '.join(notes), fontsize=8, color='gray')

    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return out_path


def main() -> None:
    path = plot_intraday_raw_vs_adjust()
    print(f'✓ Zapisano: {path}')


if __name__ == '__main__':
    main()
