# Modele Predykcji PV — Dokumentacja Produkcyjna

**Model wdrożeniowy:** Random Forest godzinowy (GridSearch, regularyzowany)  
**Artefakt:** `models/pv_hourly_model.joblib`  
**Szczegóły ML:** [docs/02_ML_predykcja_PV.md](docs/02_ML_predykcja_PV.md)  
**Changelog:** [docs/CHANGELOG_ML.md](docs/CHANGELOG_ML.md)

---

## Model produkcyjny (GODZINOWY)

### Trening

```bash
export PV_HOURLY_TARGET=pve   # domyślne w kodzie
./venv/bin/python scripts/train/train_hourly_model_tuning.py
```

### Hiperparametry (GridSearch min-gap)

| Parametr | Wartość |
|----------|---------|
| `max_depth` | 6 |
| `min_samples_leaf` | 20 |
| `min_samples_split` | 20 |
| `max_features` | 1.0 |
| `n_estimators` | 200 |

### Metryki (artefakt produkcyjny · GPS dach + ICON + target PVE)

Okno treningu: **2025-06-01 → 2026-07-18** (expanding; bazowo pełny rok → 2026-05-31) · split **80/20 po dniach** · FoxESS (PV) + Open-Meteo ICON · źródło: `hourly_model_tuning_summary_production.csv`

| Metryka | Wartość |
|---------|---------|
| Test MAE | **0.594** kWh/h |
| Test R² | **0.694** |
| Train MAE | **0.536** kWh/h |
| **Gap** | **0.058** kWh/h |
| Dzienny MAE | **3.67** kWh/dzień |
| Daily R² | 0.843 |
| Werdykt | ✅ Nie przeuczony |

### Cechy i target

- Target: `pv_kwh_hour` = **Δ`PVEnergyTotal`** (jak w aplikacji FoxESS); `PV_HOURLY_TARGET=pve`
- 16 cech: radiacja, chmury, cechy słoneczne, mgła, śnieg (**bez** `month`/`doy_*`); CS4 (19) = kandydat — [`UPDATE_2026-07-26_cs4-dual.md`](docs/UPDATE_2026-07-26_cs4-dual.md)
- Pogoda: Open-Meteo **`icon_seamless`**, GPS dachu z lokalnego `.env` (~Kraków)
- Moduł: `src/features/pv_features_hourly_extended.py`

### Prognoza operacyjna

```bash
./venv/bin/python mlops/forecast_pv.py --days 2 --top 5
```

---

## Model dzienny (pomocniczy)

Planowanie ogólne, oszacowanie sum dobowych:

```bash
./venv/bin/python scripts/train/train_pv_rf_only.py
```

Test MAE ~3.6 kWh/dzień. Używany do analiz, **nie** do harmonogramu godzinowego AGD.

---

## Benchmarki — dlaczego odrzucono XGBoost

Wykres: `reports/figures/hourly_algorithm_comparison.png`  
Dane: `data/processed/hourly_algorithm_comparison.csv`

| Model | Test MAE [kWh/h] | Gap | Werdykt |
|-------|------------------|-----|---------|
| Ridge | 0.831 | ~0 | baseline liniowy |
| **RF (prod.)** | **0.602** | 0.096 | **✅ wdrożony** |
| XGBoost | 0.614 | 0.470 | ❌ przeuczony |

XGBoost ma niski train MAE i duży gap. Random Forest z regularyzacją utrzymuje stabilność na teście.

---

## Porównanie modeli

| Model | Target | Test MAE | Przeuczenie | Wdrożenie |
|-------|--------|----------|-------------|-----------|
| **RF godzinowy (PVE)** | ΔPVEnergyTotal | **0.594 kWh/h** | ✅ Gap 0.058 | **PRODUKCJA** |
| RF godzinowy (ICON, ∫pvPower) | ∫pvPower | 0.666 kWh/h | ✅ Gap 0.086 | Zastąpiony 2026-07-18 |
| RF dzienny | kWh/d | ~3.6 kWh/d | ✅ | Analizy |
| XGBoost godzinowy | kWh/h | 0.614 | ❌ Gap 0.47 | Odrzucony |

---

## Struktura plików

```
src/features/
  ├── pv_features.py                    # Cechy dzienne
  ├── pv_features_hourly_extended.py    # Cechy godzinowe (PRODUKCJA)
  └── panel_geometry.py                 # eksperyment (wyłączony)

src/models/
  └── pv_hourly_predictor.py            # Trening, zapis, prognoza

mlops/
  └── forecast_pv.py                      # Prognoza operacyjna

scripts/
  ├── train/train_hourly_model_tuning.py  # GridSearch + zapis .joblib
  └── analysis/compare_model_change.py    # Gate ACCEPT/REJECT
```

Szczegóły pipeline i wykresów: [docs/02_ML_predykcja_PV.md](docs/02_ML_predykcja_PV.md).
