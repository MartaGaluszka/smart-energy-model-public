#!/usr/bin/env python
"""Krzywe uczenia ablacji — MAE vs n_estimators dla etapów cech."""

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

CSV = 'data/processed/learning_curves.csv'
OUT = 'reports/figures/learning_curves.png'

LABELS = {
    '1_Baza': 'Baza',
    '2_Pogoda': 'Pogoda',
    '3_Kalendarz': 'Pogoda+Kalendarz',
    '3_Pogoda_Slonce': 'Pogoda+Słońce',
    '3_Pogoda_Slonce_Reguly': '★ Wdrożone (16 cech)',
    '4_Reguly': 'Legacy (19 cech)',
}

STYLE = {
    '1_Baza': dict(color='#a0aec0', lw=1.5, ls='--'),
    '2_Pogoda': dict(color='#718096', lw=1.8),
    '3_Kalendarz': dict(color='#e53e3e', lw=1.8),
    '3_Pogoda_Slonce': dict(color='#38a169', lw=1.8),
    '3_Pogoda_Slonce_Reguly': dict(color='#276749', lw=2.5),
    '4_Reguly': dict(color='#2b6cb0', lw=1.8, ls=':'),
}


def main() -> None:
    df = pd.read_csv(CSV)

    plt.figure(figsize=(10, 6))
    for etap in df['Etap'].unique():
        subset = df[df['Etap'] == etap]
        style = STYLE.get(etap, {})
        plt.plot(
            subset['Drzewa'],
            subset['Test_MAE'],
            marker='o',
            label=LABELS.get(etap, etap),
            **style,
        )

    plt.title('Krzywe uczenia: zbieżność MAE vs n_estimators', fontsize=14)
    plt.xlabel('Liczba drzew (n_estimators)', fontsize=12)
    plt.ylabel('Test MAE (kWh/h)', fontsize=12)
    plt.legend(loc='upper right', fontsize=9)
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout()
    plt.savefig(OUT, dpi=120, bbox_inches='tight')
    plt.close()
    print(f'✓ {OUT}')


if __name__ == '__main__':
    main()
