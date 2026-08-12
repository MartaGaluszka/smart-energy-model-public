#!/usr/bin/env python3
"""Odświeża artefakty raportu z notebooka 05 (wykresy walidacji + model_comparison.md)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    os.chdir(ROOT)
    env = {**os.environ, 'MPLBACKEND': 'Agg', 'PYTHONPATH': str(ROOT)}
    for script in (
        'scripts/plots/plot_july_validation.py',
        'scripts/plots/plot_production_validation.py',
    ):
        print(f'→ {script}')
        subprocess.run([sys.executable, script], check=True, env=env)

    gh = ROOT / 'docs' / 'images' / 'ml'
    fig = ROOT / 'reports' / 'figures'
    for name in ('july_validation_plot.png', 'production_validation_plot.png', 'july_validation_summary.md'):
        src = fig / name
        if src.exists():
            (gh / name).write_bytes(src.read_bytes())
            print(f'  copied {name} → docs/images/ml/')

    print('✓ Walidacja odświeżona — uruchom komórki 4–11 w notebooks/05_raport_wynikow.ipynb')


if __name__ == '__main__':
    main()
