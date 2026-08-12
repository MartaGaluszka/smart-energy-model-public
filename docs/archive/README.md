# docs/archive/ — notatki robocze i historia

Archiwum decyzji, diagnostyk i eksperymentów przeniesionych z rootu projektu.  
**Dokumenty kanoniczne** (do prezentacji i na co dzień) są wyżej w `docs/`:

| Kanon | Plik |
|-------|------|
| EDA / Data Quality | [`../01_EDA_analiza.md`](../01_EDA_analiza.md) |
| Model ML | [`../02_ML_predykcja_PV.md`](../02_ML_predykcja_PV.md) |
| Założenia i decyzje | [`../03_ZALOZENIA_I_DECYZJE.md`](../03_ZALOZENIA_I_DECYZJE.md) |

Root projektu zostawia tylko: `README.md`, `QUICK_START.md`, `PROJECT_STATUS.md`, `MODELS_README.md`.

---

## Mapa kategorii

### [`data-quality/`](data-quality/) — jakość danych, luki, naprawy

| Plik | Temat |
|------|--------|
| [CLEAN_DATA_VALIDATION_SUMMARY.md](data-quality/CLEAN_DATA_VALIDATION_SUMMARY.md) | Podsumowanie walidacji „czystych” danych |
| [DATA_QUALITY_APRIL_MAY_2025.md](data-quality/DATA_QUALITY_APRIL_MAY_2025.md) | Jakość danych kwiecień–maj 2025 |
| [JAN_FEB_DATA_FIX.md](data-quality/JAN_FEB_DATA_FIX.md) | Naprawa luk sty/lut 2026 |

### [`weather-features/`](weather-features/) — śnieg, mgła, deszcz, godziny słoneczne

| Plik | Temat |
|------|--------|
| [DYNAMIC_FOG_CALIBRATION.md](weather-features/DYNAMIC_FOG_CALIBRATION.md) | Kalibracja flagi mgły |
| [DYNAMIC_SNOW_CALIBRATION.md](weather-features/DYNAMIC_SNOW_CALIBRATION.md) | Kalibracja śniegu |
| [DYNAMIC_HOURS_UPDATE.md](weather-features/DYNAMIC_HOURS_UPDATE.md) | Dynamiczne godziny wschód–zachód |
| [FOG_MODEL_FIX.md](weather-features/FOG_MODEL_FIX.md) | Fix modelu mgły |
| [INTEGRATION_FOG_SNOW.md](weather-features/INTEGRATION_FOG_SNOW.md) | Integracja mgły + śniegu |
| [SNOW_CALIBRATION_ANALYSIS.md](weather-features/SNOW_CALIBRATION_ANALYSIS.md) | Analiza kalibracji śniegu |
| [SNOW_FIX_FINAL.md](weather-features/SNOW_FIX_FINAL.md) | Finalny fix śniegu |
| [SNOW_FIX_SUMMARY.md](weather-features/SNOW_FIX_SUMMARY.md) | Skrót fixów śniegu |
| [SNOW_MELT_INTEGRATION.md](weather-features/SNOW_MELT_INTEGRATION.md) | Model topnienia śniegu |
| [RAIN_FLAG_TEST_RESULTS.md](weather-features/RAIN_FLAG_TEST_RESULTS.md) | Testy flagi deszczu |
| [YEARLY_FOG_SNOW_ANALYSIS.md](weather-features/YEARLY_FOG_SNOW_ANALYSIS.md) | Analiza roczna mgła/śnieg |

### [`models/`](models/) — split, naming, porównania wersji

| Plik | Temat |
|------|--------|
| [FINAL_SPLIT_STRATEGY_RESULTS.md](models/FINAL_SPLIT_STRATEGY_RESULTS.md) | Wyniki strategii podziału |
| [SPLIT_STRATEGIES_RESULTS.md](models/SPLIT_STRATEGIES_RESULTS.md) | Porównanie strategii split |
| [TRAIN_TEST_SPLIT_ISSUE.md](models/TRAIN_TEST_SPLIT_ISSUE.md) | Problem train/test split |
| [MODEL_NAMING_CONVENTION.md](models/MODEL_NAMING_CONVENTION.md) | Konwencja nazw modeli |
| [MODEL_TEST_SUMMARY.md](models/MODEL_TEST_SUMMARY.md) | Podsumowanie testów modeli |
| [MODEL_VERSIONS_COMPARISON.md](models/MODEL_VERSIONS_COMPARISON.md) | Porównanie wersji modeli |

### [`battery/`](battery/) — filtr baterii FoxESS

| Plik | Temat |
|------|--------|
| [BATTERY_FILTER_APPLIED.md](battery/BATTERY_FILTER_APPLIED.md) | Zastosowanie filtra baterii |
| [PV_BATTERY_FILTER.md](battery/PV_BATTERY_FILTER.md) | Filtr PV vs bateria |
| [POTWIERDZENIE_FILTRA_BATERII.md](battery/POTWIERDZENIE_FILTRA_BATERII.md) | Potwierdzenie filtra |
| [UPDATE_2026-07-09_filtr-baterii.md](battery/UPDATE_2026-07-09_filtr-baterii.md) | Raport analizy 2026-07-09 |

---

*Przeniesione z rootu projektu (reorganizacja dokumentacji, lipiec 2026). Treści nie scalano.*
