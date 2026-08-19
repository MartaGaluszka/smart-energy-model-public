# Status ML / MLOps — aktualny snapshot

**Stan na:** 2026-08-18  
**Źródła liczb:** `models/pv_hourly_model.joblib` (**weekly 16.08**) · `forecast_validation.csv` (closeouty do **17.08**) · [`NOTATKA_WEEKLY_2026-08-16.md`](NOTATKA_WEEKLY_2026-08-16.md) · [`NOTATKA_2026-08-18.md`](NOTATKA_2026-08-18.md)

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
| Era dual **27.07–17.08** | 22 | **8,7%** | **9,1%** |
| Całość **14.07–17.08** | 35 | 14,8% | 13,6% |

*(Całość wciąga burzowy tydzień przed dual — do narracji używaj ery dual jako „jak działa teraz”.)*

CS4 daily (era dual, n=22): MAPE **~9,6%** — lekko powyżej RF średnio, ale wygrywa dni pochmurne (np. **16.08**, **17.08** best=`daily_cs4`; 17.08 APE **0,7%**).

Ostatnie closeouty: **15.08** 35,9 · **16.08** 33,7 · **17.08** **21,5** (front; CS4 daily +0,14 kWh).

Wykresy (do **17.08**): [`images/ml/july_validation_plot.png`](images/ml/july_validation_plot.png), [`images/ml/production_validation_plot.png`](images/ml/production_validation_plot.png) · opis błędów: [`images/ml/july_validation_summary.md`](images/ml/july_validation_summary.md).

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
| Pogoda 15–20.08 | [`NOTATKA_POGODA_2026-08-15.md`](NOTATKA_POGODA_2026-08-15.md) |
| Weekly 16.08 | [`NOTATKA_WEEKLY_2026-08-16.md`](NOTATKA_WEEKLY_2026-08-16.md) |
| Dzień 18.08 | [`NOTATKA_2026-08-18.md`](NOTATKA_2026-08-18.md) |
| Oneshot shadow | [`NOTATKA_ONESHOT_2026-08-17.md`](NOTATKA_ONESHOT_2026-08-17.md) |

---

*Odświeżaj po każdym weekly train / po serii nowych closeoutów.*
