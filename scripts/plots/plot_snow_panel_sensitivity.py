"""
Wykres: ile dni zimą (XII–II) oznaczono jako snow_on_panels dla różnych parametrów.

Uruchomienie:
    source venv/bin/activate
    python scripts/plot_snow_panel_sensitivity.py
"""

from __future__ import annotations

import os
import sys

import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

from src.features.pv_features import apply_snow_panel_flags, load_training_frame

load_dotenv()

OUT_PNG = os.getenv('SNOW_SENSITIVITY_PNG', 'reports/figures/snow_panel_sensitivity.png')
OUT_CSV = os.getenv('SNOW_SENSITIVITY_CSV', 'data/processed/snow_panel_sensitivity.csv')


def main() -> None:
    frame = load_training_frame()
    if frame.empty:
        raise SystemExit('Brak danych w ramce treningowej.')

    winter = frame[pd.to_datetime(frame['day']).dt.month.isin([12, 1, 2])].copy()
    if winter.empty:
        raise SystemExit('Brak dni zimowych w ramce.')

    windows = [3, 5, 7]
    thaws = [1.0, 2.0, 3.0]
    rows = []
    for w in windows:
        for t in thaws:
            variant = apply_snow_panel_flags(frame, w, t)
            winter_flagged = variant.loc[
                pd.to_datetime(variant['day']).isin(pd.to_datetime(winter['day'])),
                'snow_on_panels',
            ].sum()
            rows.append({
                'window_days': w,
                'thaw_temp_c': t,
                'winter_snow_days': int(winter_flagged),
                'label': f'{w}d / {t:.0f}°C',
            })

    summary = pd.DataFrame(rows).sort_values('winter_snow_days')
    os.makedirs(os.path.dirname(OUT_PNG) or '.', exist_ok=True)
    summary.to_csv(OUT_CSV, index=False)

    fig, ax = plt.subplots(figsize=(10, 5))
    colors = ['#94a3b8' if r['label'] != '7d / 3°C' else '#dc2626' for _, r in summary.iterrows()]
    ax.bar(summary['label'], summary['winter_snow_days'], color=colors, alpha=0.85)
    ax.set_ylabel('Dni zimą (XII–II) z snow_on_panels=1')
    ax.set_xlabel('Parametry: okno [dni] / próg odwilży [°C]')
    ax.set_title('Wrażliwość reguły śniegu na panelach — sezon zimowy')
    ax.tick_params(axis='x', rotation=45)
    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=150)
    plt.close(fig)

    print('=' * 70)
    print('Wrażliwość reguły śniegu (zima XII–II)')
    print('=' * 70)
    print(summary.to_string(index=False))
    print(f'\n✅ Wykres: {OUT_PNG}')
    print(f'✅ Tabela: {OUT_CSV}')
    print('💡 Czerwony słupek = domyślne parametry projektu (7 dni / 3°C).')


if __name__ == '__main__':
    main()
