#!/usr/bin/env python
"""Wykres ablacji MAE — etapy cech (legacy 19 vs produkcja 16)."""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

CSV = 'data/processed/ablation_results.csv'
OUT = 'reports/figures/ablation_chart.png'

LABELS = {
    '1_Baza': 'Baza',
    '2_Pogoda': 'Pogoda',
    '3_Kalendarz': 'Pogoda+Kalendarz',
    '3_Pogoda_Slonce': 'Pogoda+Słońce',
    '3_Pogoda_Slonce_Reguly': '★ Wdrożone (16 cech)',
    '4_Reguly': 'Legacy (19 cech)',
}


def main() -> None:
    df = pd.read_csv(CSV)
    df['Etykieta'] = df['Etap'].map(LABELS).fillna(df['Etap'])

    colors = []
    for etap in df['Etap']:
        if etap == '3_Pogoda_Slonce_Reguly':
            colors.append('#276749')
        elif etap == '4_Reguly':
            colors.append('#718096')
        elif etap == '3_Kalendarz':
            colors.append('#e53e3e')
        else:
            colors.append('#2b6cb0')

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(df['Etykieta'], df['Test_MAE'], marker='o', linestyle='-', color='#2b6cb0',
            linewidth=2, markersize=8, zorder=1)
    ax.scatter(df['Etykieta'], df['Test_MAE'], c=colors, s=90, zorder=2, edgecolors='white')

    for _, row in df.iterrows():
        ax.annotate(
            f'{row["Test_MAE"]:.3f}',
            xy=(row['Etykieta'], row['Test_MAE']),
            xytext=(0, 8),
            textcoords='offset points',
            ha='center',
            fontsize=8,
        )

    ax.set_title('Wpływ inżynierii cech na błąd modelu (MAE)', fontsize=14)
    ax.set_xlabel('Etap rozwoju modelu', fontsize=12)
    ax.set_ylabel('Test MAE (kWh/h)', fontsize=12)
    ax.grid(True, linestyle='--', alpha=0.7)
    plt.xticks(rotation=15, ha='right')
    plt.tight_layout()
    plt.savefig(OUT, dpi=120, bbox_inches='tight')
    plt.close()
    print(f'✓ {OUT}')


if __name__ == '__main__':
    main()
