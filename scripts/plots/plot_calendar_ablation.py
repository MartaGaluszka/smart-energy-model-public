#!/usr/bin/env python
"""Wykres raportu decyzyjnego: kalendarz vs słońce vs wdrożone 16 cech."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

CSV = 'data/processed/calendar_ablation_comparison.csv'
OUT = 'reports/figures/calendar_ablation_comparison.png'

# Dwulinijkowe etykiety — unikamy ucięcia "(16 cech)" przy rotacji
LABELS = {
    '2_Pogoda': 'Pogoda\n(6 cech)',
    '3_Kalendarz': 'Pogoda+Kalendarz\n(9 cech)',
    '3_Pogoda_Slonce': 'Pogoda+Słońce\n(13 cech)',
    '3_Pogoda_Slonce_Reguly': '★ Wdrożone\n(16 cech)',
    '4_Reguly': 'Legacy\n(19 cech)',
}


def main() -> None:
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.chdir(root)

    if not os.path.exists(CSV):
        raise FileNotFoundError(f'Brak {CSV} — uruchom: python scripts/ablation_study.py')

    df = pd.read_csv(CSV)

    colors = []
    for etap in df['Etap']:
        if etap == '3_Pogoda_Slonce_Reguly':
            colors.append('#276749')
        elif etap == '3_Kalendarz':
            colors.append('#e53e3e')
        elif etap == '4_Reguly':
            colors.append('#718096')
        else:
            colors.append('#2b6cb0')

    fig, ax = plt.subplots(figsize=(11, 5.5))
    x = range(len(df))
    bars = ax.bar(x, df['Test_MAE'], color=colors, edgecolor='white')
    ax.set_xticks(list(x))
    ax.set_xticklabels([LABELS.get(e, e) for e in df['Etap']], fontsize=10)
    ax.set_ylabel('Test MAE [kWh/h]')
    ax.set_title('Raport decyzyjny — WDROŻONE: 16 cech (bez month/doy)')
    ax.grid(True, axis='y', linestyle='--', alpha=0.6)
    ax.set_ylim(0, float(df['Test_MAE'].max()) * 1.18)

    for bar, etap, mae in zip(bars, df['Etap'], df['Test_MAE']):
        txt = f'{mae:.3f}\n← .joblib' if etap == '3_Pogoda_Slonce_Reguly' else f'{mae:.3f}'
        ax.annotate(
            txt,
            xy=(bar.get_x() + bar.get_width() / 2, mae),
            xytext=(0, 6),
            textcoords='offset points',
            ha='center',
            fontsize=9,
            fontweight='bold' if etap == '3_Pogoda_Slonce_Reguly' else 'normal',
        )

    os.makedirs('docs', exist_ok=True)
    plt.tight_layout()
    plt.savefig(OUT, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'✓ {OUT}')


if __name__ == '__main__':
    main()
