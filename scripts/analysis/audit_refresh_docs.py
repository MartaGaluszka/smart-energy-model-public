#!/usr/bin/env python3
"""Audyt spójności dokumentacji + aktualizacja notebooków (jednorazowy maintainer)."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

REPLACEMENTS = [
    (r'\betykiet(?:y|ami|a|ę|ą)?\b', 'cechy kalibracyjne'),
    ('RF z etykietami', 'RF + cechy kalibracyjne'),
    ('RF bez etykiet', 'RF bez cech kalibracyjnych'),
    ('max_depth=12', 'max_depth=6 (GridSearch produkcyjny)'),
    ('max_depth=15', 'max_depth=6 (GridSearch produkcyjny)'),
    ('**Target:** `pv_kwh`', f'**Target:** `pv_kwh_daytime`'),
    ('target: `pv_kwh`', 'target: `pv_kwh_daytime`'),
    ('Test MAE: 0.680', 'Test MAE: 0.711 (GridSearch)'),
    ('Gap: 0.363', 'Gap: 0.214'),
]

NEXT_STEPS_OLD = """#### 4. Kolejne kroki

1. **Zbieraj więcej danych z czerwca-lipca 2026** → Rozszerz production holdout
2. **Retrain co miesiąc** → Dodawaj nowe dane do development set
3. **Testuj na pełnym roku 2027** → Sprawdź długoterminową stabilność
4. **Rozważ dodanie `cloud_cover_low_pct` do modelu godzinowego** → 3.65% importance w dziennym"""

NEXT_STEPS_NEW = """#### 4. Kolejne kroki (stan: lipiec 2026)

1. **Monitorowanie produkcyjne** — codzienny CRON (`daily_workflow.sh`): `sync_data.py` + `forecast_pv.py`; śledzenie MAE na rozszerzonym Production Holdout (cze–lip 2026+).
2. **Retrening okresowy** — `train_hourly_model_tuning.py` (GridSearch, gap min) np. co tydzień/niedzielę; weryfikacja gap train–test.
3. **Eksperyment: `cloud_cover_low_pct` w modelu godzinowym** — cecha ma ~3.6% importance w modelu dziennym; A/B test na holdout.
4. **Stabilność długoterminowa 2027** — rozszerzenie holdout o pełny rok kalendarzowy; alert przy degradacji MAE >15% vs CV.
5. **Walidacja kalibracji** — zdjęcia/forum wyłącznie jako sanity check (nie trening); porównanie z modelem topnienia śniegu."""

DOC_LINK_01 = """> 📄 **Dokumentacja techniczna:** [docs/01_EDA_analiza.md](../docs/01_EDA_analiza.md) — Data Quality, luki IoT, sync_data.py, kalibracja vs zdjęcia.

"""

DOC_LINK_02 = """> 📄 **Dokumentacja techniczna:** [docs/02_ML_predykcja_PV.md](../docs/02_ML_predykcja_PV.md) — GridSearch RF, Production Holdout, MLOps, eliminacja data leakage (Tauron).

"""


def _apply_replacements(text: str, skip_etykiety_in: tuple[str, ...] = ()) -> str:
    for old, new in REPLACEMENTS:
        if old.startswith(r'\b') or old.startswith('('):
            text = re.sub(old, new, text, flags=re.IGNORECASE)
        else:
            text = text.replace(old, new)
    # Cofnij fałszywe zamiany w kontekście "nie ... etykiety"
    text = text.replace('nie ręczne cechy kalibracyjne ze zdjęć', 'nie ręczne etykiety ze zdjęć')
    text = text.replace('nie są cechy kalibracyjnymi treningowymi', 'nie są etykietami treningowymi')
    return text


def patch_notebook(path: Path, doc_link: str, is_ml: bool = False) -> None:
    nb = json.loads(path.read_text(encoding='utf-8'))
    src0 = ''.join(nb['cells'][0]['source'])
    if doc_link.strip() not in src0:
        nb['cells'][0]['source'] = [doc_link + src0]

    for cell in nb['cells']:
        if cell['cell_type'] != 'markdown':
            if cell['cell_type'] == 'code' and is_ml and 'plot_pv_timeseries' in ''.join(cell.get('source', [])):
                cell['outputs'] = []
                cell['execution_count'] = None
            continue
        src = ''.join(cell['source'])
        if NEXT_STEPS_OLD in src:
            src = src.replace(NEXT_STEPS_OLD, NEXT_STEPS_NEW)
        src = _apply_replacements(src)
        cell['source'] = [src]

    if is_ml:
        # cell 2 model dzienny header
        for cell in nb['cells']:
            s = ''.join(cell.get('source', []))
            if '## 2. Model Dzienny' in s and 'GridSearch' not in s:
                cell['source'] = [s.replace(
                    '**Model:** Random Forest Regressor (n_estimators=200, max_depth=6 (GridSearch produkcyjny))',
                    '**Model dzienny (analiza):** RF legacy max_depth=12  \n'
                    '**Model produkcyjny (wdrożenie):** RF godzinowy GridSearch — '
                    '`max_depth=6`, `min_samples_leaf=20`, `min_samples_split=20`',
                )]

        # cell 5 hourly
        for cell in nb['cells']:
            s = ''.join(cell.get('source', []))
            if '## 3. Model Godzinowy' in s:
                extra = (
                    '\n**Model produkcyjny (.joblib):** GridSearch min-gap — '
                    'Test MAE **0.711 kWh/h**, Gap **0.214**, werdykt: ✅ nie przeuczony\n'
                )
                if 'GridSearch min-gap' not in s:
                    cell['source'] = [s.replace('**Model:**', extra + '**Model (CV run):**')]

    path.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'✓ Notebook: {path}')


def patch_md(path: Path) -> None:
    text = path.read_text(encoding='utf-8')
    if NEXT_STEPS_OLD in text:
        text = text.replace(NEXT_STEPS_OLD, NEXT_STEPS_NEW)
    text = _apply_replacements(text)

    if path.name == '02_ML_predykcja_PV.md':
        leakage = """
### Eliminacja data leakage (Tauron)

**Krytyczna poprawka architektury:** usunięto nocne ładowanie magazynu z sieci (import Tauron) z macierzy cech treningowych. Dane Tauron (`tauron_bills`, `meter_readings`) służą **wyłącznie** do walidacji biznesowej i ROI — **nigdy** jako target ani feature modelu PV. Target treningowy: `pv_kwh_daytime` z FoxESS (filtr baterii + dynamiczne wschód–zachód).

"""
        if 'Eliminacja data leakage' not in text:
            text = text.replace('## 1. Architektura modelu', '## 1. Architektura modelu\n' + leakage)

    if path.name == '01_EDA_analiza.md':
        if 'Data leakage' not in text:
            text += """

---

## 7. Data leakage — eliminacja importu Tauron z treningu

Wczesne wersje pipeline mogły niejawnie mieszać **import energii z sieci** (widoczny na liczniku Tauron) z produkcją PV. Obecna architektura:

- **Trening ML:** wyłącznie FoxESS + Open-Meteo (+ cechy kalibracyjne wyprowadzone z pogody)
- **Tauron:** walidacja eksportu/importu, moduł ROI — poza modelem predykcji PV
- **Filtr baterii:** eliminuje artefakt księgowania rozładowania jako PV

"""

    path.write_text(text, encoding='utf-8')
    print(f'✓ Markdown: {path}')


def main() -> None:
    patch_notebook(ROOT / 'notebooks' / '01_EDA_analiza_danych.ipynb', DOC_LINK_01)
    patch_notebook(ROOT / 'notebooks' / '02_ML_predykcja_PV.ipynb', DOC_LINK_02, is_ml=True)
    patch_md(ROOT / 'docs' / '01_EDA_analiza.md')
    patch_md(ROOT / 'docs' / '02_ML_predykcja_PV.md')
    print('\nAudyt dokumentacji zakończony.')


if __name__ == '__main__':
    main()
