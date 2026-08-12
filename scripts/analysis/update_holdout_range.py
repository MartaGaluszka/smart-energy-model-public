#!/usr/bin/env python3
"""Jednorazowa synchronizacja zakresu Production Holdout w docs + notebook."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

HOLDOUT_LABEL = "39 dni: 2026-06-01 → 2026-07-09"
HOLDOUT_HOURLY = "485 godzin: 2026-06-01 → 2026-07-09"
HOLDOUT_DESC = "ponad miesiąc walidacji na zbiorze produkcyjnym (czerwiec–lipiec 2026)"

REPLACEMENTS = [
    ("2026-06-01 → 2026-06-04", "2026-06-01 → 2026-07-09"),
    ("2026-06-01 → 2026-07-31", "2026-06-01 → 2026-07-09"),
    ("Production Holdout (4 dni: 2026-06-01 → 2026-07-09)", f"Production Holdout ({HOLDOUT_LABEL})"),
    ("Production Holdout (60 godzin: 2026-06-01 → 2026-07-09)", f"Production Holdout ({HOLDOUT_HOURLY})"),
    ("#### Production Holdout (4 dni: 2026-06-01 → 2026-07-09)", f"#### Production Holdout ({HOLDOUT_LABEL})"),
    ("Czerwiec 2026 (4 dni)", "Czerwiec–lipiec 2026 (39 dni holdout)"),
    ("4 dni) to **szczyt lata**", "39 dni holdout) obejmuje **szczyt lata**"),
    ("Development Set (314 dni: 2025-06 → 2026-05)", "Development Set (365 dni: 2025-06 → 2026-05)"),
    ("3830 godzin: 2025-06 → 2026-05", "3163 godzin: 2025-06 → 2026-05"),
    # daily production metrics
    ("- **MAE:** 1.954 kWh (lepsze niż CV o 2.39 kWh!)\n- **R²:** 0.830\n- **RMSE:** 2.821 kWh\n- **Poprawa vs baseline:** 89.0%",
     "- **MAE:** 4.354 kWh (zgodne z CV: Δ=0.14 kWh)\n- **R²:** 0.714\n- **RMSE:** 5.122 kWh\n- **Poprawa vs baseline:** 73.1%"),
    ("1. **Production Holdout lepszy niż CV** (1.95 vs 4.34 kWh)", "1. **Production Holdout zgodny z CV** (4.35 vs 4.22 kWh)"),
    ("   → Czerwiec 2026 jest łatwiejszy do predykcji (szczyt lata)", f"   → {HOLDOUT_DESC.capitalize()}"),
    # hourly production
    ("#### Production Holdout (60 godzin: 2026-06-01 → 2026-07-09) ⭐\n\n- **MAE:** 0.559 kWh",
     f"#### Production Holdout ({HOLDOUT_HOURLY}) ⭐\n\n- **MAE:** 0.740 kWh"),
    ("- **MAE:** 0.740 kWh (lepsze niż CV o 0.12 kWh!)\n- **R²:** 0.474\n- **RMSE:** 0.827 kWh\n- **Poprawa vs baseline:** 46.3%",
     "- **MAE:** 0.740 kWh (zgodne z CV: Δ=0.04 kWh)\n- **R²:** 0.586\n- **RMSE:** 1.028 kWh\n- **Poprawa vs baseline:** 28.0%"),
    ("1. **Production Holdout lepszy niż CV** (0.56 vs 0.68 kWh)", "1. **Production Holdout zgodny z CV** (0.74 vs 0.70 kWh)"),
    # comparison table
    ("| **Dzienny** | 1 dzień | 4.344 kWh | 0.736 | **1.954 kWh** | **0.830** | 75.6% (CV), 89.0% (Prod) |",
     "| **Dzienny** | 1 dzień | 4.218 kWh | 0.739 | **4.354 kWh** | **0.714** | 73.9% (CV), 73.1% (Prod) |"),
    ("| **Godzinowy** | 1 godzina | 0.680 kWh | 0.603 | **0.559 kWh** | 0.474 | 34.7% (CV), 46.3% (Prod) |",
     "| **Godzinowy** | 1 godzina | 0.698 kWh | 0.609 | **0.740 kWh** | **0.586** | 32.0% (CV), 28.0% (Prod) |"),
    ("- **Oba modele:** Production lepsze niż CV → Czerwiec 2026 \"łatwiejszy\"",
     f"- **Oba modele:** Production zgodne z CV → {HOLDOUT_DESC}"),
    ("| Dzienny | 4.344 kWh | 1.954 kWh | -2.39 kWh | -55% |",
     "| Dzienny | 4.218 kWh | 4.354 kWh | +0.14 kWh | +3% |"),
    ("| Godzinowy | 0.680 kWh | 0.559 kWh | -0.12 kWh | -18% |",
     "| Godzinowy | 0.698 kWh | 0.740 kWh | +0.04 kWh | +6% |"),
    ("#### 4. Production Holdout vs CV — Dlaczego Production jest lepszy?",
     "#### 4. Production Holdout vs CV — Zgodność na pełnym holdout"),
    ("| **Lato (cze-sie)** | ~2.0 kWh | ~0.56 kWh |",
     "| **Lato (cze-sie)** | ~4.4 kWh | ~0.74 kWh |"),
    ("   - Dzienny: MAE 1.95 kWh, R² 0.830 (production)\n   - Godzinowy: MAE 0.56 kWh, R² 0.474 (production)",
     "   - Dzienny: MAE 4.35 kWh, R² 0.714 (production holdout 39 dni)\n   - Godzinowy: MAE 0.74 kWh, R² 0.586 (production holdout 485 h)"),
    # monthly comparison section in notebook
    ("#### Production Holdout (4 dni: 2026-06-01 → 2026-07-09)\n\n| Model | MAE (kWh) | R² | Status |",
     "#### Production Holdout (39 dni: 2026-06-01 → 2026-07-09)\n\n| Model | MAE (kWh) | R² | Status |"),
    ("| **RF + kalibracja pogodowa** | 1.954 | 0.830 | ✅ Najlepszy |",
     "| **RF + kalibracja pogodowa** | 4.715 | 0.692 | ✅ Najlepszy |"),
    ("| RF bez cech kalibracyjnych | 2.080 | 0.807 | ✅ Podobny |",
     "| RF bez cech kalibracyjnych | 4.665 | 0.697 | ✅ Podobny |"),
    ("| **Regresja liniowa (Ridge)** | 4.607 | 0.680 | ✅ Stabilny |",
     "| **Regresja liniowa (Ridge)** | 4.607 | 0.680 | ✅ Stabilny |"),
    ("| XGBoost | 5.163 | 0.679 | ⚠️ Gorszy na holdout |",
     "| XGBoost | 5.163 | 0.679 | ⚠️ Gorszy na holdout |"),
]


def patch_text(text: str) -> str:
    for old, new in REPLACEMENTS:
        text = text.replace(old, new)
    return text


def patch_notebook(path: Path) -> None:
    nb = json.loads(path.read_text(encoding='utf-8'))
    for cell in nb['cells']:
        if cell['cell_type'] == 'markdown':
            cell['source'] = [patch_text(''.join(cell['source']))]
        elif cell['cell_type'] == 'code' and 'build_chart' in ''.join(cell.get('source', [])):
            cell['outputs'] = []
            cell['execution_count'] = None
    path.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'✓ {path}')


def patch_md(path: Path) -> None:
    text = patch_text(path.read_text(encoding='utf-8'))
    text = text.replace(
        "Production Holdout    2026-06-01 → …           (dane niewidziane w treningu)",
        "Production Holdout    2026-06-01 → 2026-07-09   (39 dni, dane niewidziane w treningu)",
    )
    text = re.sub(
        r"Na \*\*Production Holdout \(czerwiec 2026\)\*\*",
        f"Na **Production Holdout ({HOLDOUT_DESC})**",
        text,
    )
    if "ponad miesiąc walidacji" not in text:
        text = text.replace(
            "## 3. Production Holdout — interpretacja wykresów",
            f"## 3. Production Holdout — interpretacja wykresów\n\n"
            f"**Zakres:** `2026-06-01 → 2026-07-09` ({HOLDOUT_LABEL}) — {HOLDOUT_DESC}.\n",
        )
    path.write_text(text, encoding='utf-8')
    print(f'✓ {path}')


def main() -> None:
    patch_notebook(ROOT / 'notebooks' / '02_ML_predykcja_PV.ipynb')
    patch_md(ROOT / 'docs' / '02_ML_predykcja_PV.md')
    for p in [ROOT / 'README.md', ROOT / 'MODELS_README.md']:
        if p.exists():
            p.write_text(patch_text(p.read_text(encoding='utf-8')), encoding='utf-8')
            print(f'✓ {p}')
    print('\nHoldout range zaktualizowany.')


if __name__ == '__main__':
    main()
