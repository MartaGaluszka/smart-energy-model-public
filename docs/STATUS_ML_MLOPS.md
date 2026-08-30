# Status ML / MLOps — aktualny snapshot

**Stan na:** 2026-08-30  
**Źródła liczb:** `models/pv_hourly_model.joblib` (**weekly 30.08**) · `forecast_validation.csv` (closeouty do **29.08**; **30.08** EOD w toku) · [`NOTATKA_WEEKLY_2026-08-30.md`](NOTATKA_WEEKLY_2026-08-30.md)

Ten plik to **jedyna** krótka tabela „aktualne wyniki”. Metoda i historia → linki poniżej (nie duplikuj tu ablacji / gate’ów).

---

## Produkcja (primary)

| | |
|--|--|
| Model | Random Forest · **16 cech** |
| Target | Δ`PVEnergyTotal` (PVE = skala app FoxESS) |
| Pogoda | Open-Meteo **ICON** · GPS dach |
| Artefakt | `models/pv_hourly_model.joblib` |
| Shadow | CS4 (19) + XGB+TS + **ICON+UKMO** (`pv_forecast_ensemble.csv`, LIVE od 28.08) — **nie** primary |

### Offline (80/20 po dniach, expanding)

| Metryka | Wartość |
|---------|---------|
| Okno | 2025-06-01 → **2026-08-29** |
| Test MAE | **0.668** kWh/h |
| Gap train–test | **0.072** |
| Daily MAE | **3.46** kWh/d |
| Daily R² | **0.847** |
| Werdykt | nie przeuczony |

Gate vs weekly **23.08** (0.658): Δ **+0.010** ≤ +0.02 → **ACCEPT**.

### Live (closeout vs app)

| Okres | n | MAPE raw 5:00 | MAPE raw 12:00 |
|-------|--:|-------------:|---------------:|
| Era dual **27.07–29.08** | 34 | **15,7%** | **15,9%** |
| Całość **14.07–29.08** | 47 | 18,3% | 17,4% |

*(Wykresy odświeżone **30.08** do **29.08**. Skok MAPE vs 24.08 głównie przez **25.08** mokry (actual 4,5 · |APE|~150%) i **26.08** clearing undershoot. **30.08** EOD w toku — PV **≥25,9** @15 · daily ~27.)*

CS4: na pochmurnych / mix często bliżej faktu (np. **29.08** pick **21,5** vs **21,1**); na jasnych RF bywa lepszy.

Ostatnie closeouty: **27.08** **35,9** · **28.08** **34,2** · **29.08** **21,1** (CS4 ✓) · **30.08** w toku.

Wykresy (do **29.08**, odświeżone **30.08**): [`images/ml/july_validation_plot.png`](images/ml/july_validation_plot.png), [`images/ml/production_validation_plot.png`](images/ml/production_validation_plot.png) · opis błędów: [`images/ml/july_validation_summary.md`](images/ml/july_validation_summary.md).

---

## MLOps (skrót)

| Kiedy | Job |
|-------|-----|
| 05:00 | daily sync + prognoza (+ shadow CS4/XGB + ensemble) |
| 12:00 | midday (+ ensemble) |
| 16:00 | peak (+ ensemble) |
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
| Pogoda 15.08–1.09 | [`NOTATKA_POGODA_2026-08-15.md`](NOTATKA_POGODA_2026-08-15.md) |
| Weekly **30.08** | [`NOTATKA_WEEKLY_2026-08-30.md`](NOTATKA_WEEKLY_2026-08-30.md) |
| Weekly **23.08** | [`NOTATKA_WEEKLY_2026-08-23.md`](NOTATKA_WEEKLY_2026-08-23.md) |
| Weekly 16.08 | [`NOTATKA_WEEKLY_2026-08-16.md`](NOTATKA_WEEKLY_2026-08-16.md) |
| Dzień 19–30.08 | [`NOTATKA_2026-08-19.md`](NOTATKA_2026-08-19.md) · [`NOTATKA_2026-08-20.md`](NOTATKA_2026-08-20.md) · [`NOTATKA_2026-08-21.md`](NOTATKA_2026-08-21.md) · [`NOTATKA_2026-08-22.md`](NOTATKA_2026-08-22.md) · [`NOTATKA_2026-08-23.md`](NOTATKA_2026-08-23.md) · [`NOTATKA_2026-08-24.md`](NOTATKA_2026-08-24.md) · [`NOTATKA_2026-08-25.md`](NOTATKA_2026-08-25.md) · [`NOTATKA_2026-08-26.md`](NOTATKA_2026-08-26.md) · [`NOTATKA_2026-08-27.md`](NOTATKA_2026-08-27.md) · [`NOTATKA_2026-08-28.md`](NOTATKA_2026-08-28.md) · [`NOTATKA_2026-08-29.md`](NOTATKA_2026-08-29.md) · [`NOTATKA_2026-08-30.md`](NOTATKA_2026-08-30.md) |
| Oneshot shadow | [`NOTATKA_ONESHOT_2026-08-17.md`](NOTATKA_ONESHOT_2026-08-17.md) |
| Paper-trade Accu→RF/CS4 | paper-trade Accu (tylko repo prywatne) |
| Routing test 28–31.08 | [`NOTATKA_TEST_ROUTING_28-31_08.md`](NOTATKA_TEST_ROUTING_28-31_08.md) · plan [`PLAN_ENSEMBLE_NWP_2026.md`](PLAN_ENSEMBLE_NWP_2026.md) E1.6 |
| Reguła apki: SoC↓ + pochmurno → ładuj 22:00 | [`NOTATKA_REGULA_BATERIA_POCHMURNO_22.md`](NOTATKA_REGULA_BATERIA_POCHMURNO_22.md) |
| Log SoC / ForceCharge / AGD | [`NOTATKA_BATERIA_SOC_LOG.md`](NOTATKA_BATERIA_SOC_LOG.md) |

---

*Odświeżaj po każdym weekly train / po serii nowych closeoutów.*
