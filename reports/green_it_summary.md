# Green IT — Smart Energy Model

*Wygenerowano: 2026-08-06 20:33 z `06_aspekt_srodowiskowy.ipynb`*

## Tabela efektywności

| label | test_mae_hour | test_r2_hour | gap_hour | fit_s | artifact_mb | efficiency | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Ridge | 0.831 | 0.526 | -0.003 | 0.01 | 0.01 | 12031.294 | ✅ Nie przeuczony |
| RF (prod.) | 0.602 | 0.675 | 0.096 | 0.11 | 0.51 | 29.613 | ✅ Nie przeuczony |
| XGBoost | 0.614 | 0.654 | 0.47 | 0.26 | 0.66 | 9.494 | ❌ Przeuczony |

## Werdykt
- Produkcja: **Random Forest 16 cech** — najlepszy kompromis Test MAE, gap i koszt.
- XGBoost odrzucony mimo niskiego train MAE (duży gap).
- Docker: `python:3.11-slim`; MLOps: launchd tygodniowy retrening na hoście.

