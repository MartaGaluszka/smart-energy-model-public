# Status ML / MLOps — aktualny snapshot

**Stan na:** 2026-08-16  
**Źródła liczb:** `models/pv_hourly_model.joblib` (**weekly 16.08**) · `data/processed/forecasts/forecast_validation.csv` (closeouty do **14.08**) · [`NOTATKA_WEEKLY_2026-08-16.md`](NOTATKA_WEEKLY_2026-08-16.md)

Ten plik to **jedyna** krótka tabela „aktualne wyniki”. Metoda i historia → linki poniżej (nie duplikuj tu ablacji / gate’ów).

---

## Produkcja (primary)

| | |
|--|--|
| Model | Random Forest · **16 cech** |
| Target | Δ`PVEnergyTotal` (PVE = skala app FoxESS) |
| Pogoda | Open-Meteo **ICON** · GPS dach |
| Artefakt | `models/pv_hourly_model.joblib` |
| Shadow | CS4 (19) + XGB+TS — **nie** primary |

### Offline (80/20 po dniach, expanding)

| Metryka | Wartość |
|---------|---------|
| Okno | 2025-06-01 → **2026-08-15** |
| Test MAE | **0.643** kWh/h |
| Gap train–test | **0.063** |
| Daily MAE | **3.56** kWh/d |
| Daily R² | **0.838** |
| Werdykt | nie przeuczony |

### Live (closeout vs app)

| Okres | n | MAPE raw 5:00 | MAPE raw 12:00 |
|-------|--:|-------------:|---------------:|
| Era dual **27.07–14.08** | 19 | **9,4%** | **9,3%** |
| Całość **14.07–14.08** | 32 | 15,8% | 14,2% |

*(Całość wciąga burzowy tydzień przed dual — do narracji używaj ery dual jako „jak działa teraz”.)*

Wykresy: [`images/ml/july_validation_plot.png`](images/ml/july_validation_plot.png), [`images/ml/production_validation_plot.png`](images/ml/production_validation_plot.png).

---

## MLOps (skrót)

| Kiedy | Job |
|-------|-----|
| 05:00 | daily sync + prognoza (+ shadow) |
| 12:00 | midday |
| 16:00 | peak |
| wieczór | evening closeout → walidacja |
| niedziela **04:30** | `train_dual_weekly.sh` (16 + CS4 + XGB) |

Szczegóły komend: [`mlops/README.md`](../mlops/README.md).

Korekta operacyjna ADJUST: **OFF** (ocena modelu na **raw**).

---

## Gdzie czytać dalej

| Temat | Dokument |
|-------|----------|
| Data quality / EDA | [`01_EDA_analiza.md`](01_EDA_analiza.md) |
| Model, ablacja, Ridge/RF/XGB | [`02_ML_predykcja_PV.md`](02_ML_predykcja_PV.md) |
| Decyzje (PVE, ICON, 16 cech) | [`03_ZALOZENIA_I_DECYZJE.md`](03_ZALOZENIA_I_DECYZJE.md) |
| Historia gate’ów | [`CHANGELOG_ML.md`](CHANGELOG_ML.md) |
| Prezentacja | [`notebooks/03_prezentacja_dyplomowa.ipynb`](../notebooks/03_prezentacja_dyplomowa.ipynb) |
| Pogoda 15–17.08 | [`NOTATKA_POGODA_2026-08-15.md`](NOTATKA_POGODA_2026-08-15.md) |
| Weekly 16.08 | [`NOTATKA_WEEKLY_2026-08-16.md`](NOTATKA_WEEKLY_2026-08-16.md) |

---

*Odświeżaj po każdym weekly train / po serii nowych closeoutów.*
