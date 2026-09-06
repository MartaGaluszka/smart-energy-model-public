# Status ML / MLOps — aktualny snapshot

**Stan na:** 2026-09-06  
**Źródła liczb:** `models/pv_hourly_model.joblib` (**weekly 06.09**) · `forecast_validation.csv` (closeouty do **5.09**) · [`NOTATKA_WEEKLY_2026-09-06.md`](NOTATKA_WEEKLY_2026-09-06.md) · gate [`NOTATKA_TEST_ROUTING_28-31_08.md`](NOTATKA_TEST_ROUTING_28-31_08.md)

Ten plik to **jedyna** krótka tabela „aktualne wyniki”. Metoda i historia → linki poniżej (nie duplikuj tu ablacji / gate’ów).

---

## Produkcja (primary)

| | |
|--|--|
| Model | Random Forest · **16 cech** |
| Target | Δ`PVEnergyTotal` (PVE = skala app FoxESS) |
| Pogoda | Open-Meteo **ensemble ICON+UKMO** (`ENSEMBLE_PRIMARY=1`, gate **01.09**, daily od **02.09**) · GPS dach |
| Artefakt | `models/pv_hourly_model.joblib` |
| Shadow | **ICON solo** (`pv_forecast_icon.csv` + closeout `daily_icon`) · CS4 · XGB+TS · kopia ens CSV |

### Offline (80/20 po dniach, expanding)

| Metryka | Wartość |
|---------|---------|
| Okno | 2025-06-01 → **2026-09-05** |
| Test MAE | **0.686** kWh/h |
| Gap train–test | **0.096** |
| Daily MAE | **3.58** kWh/d |
| Daily R² | **0.850** |
| Werdykt | nie przeuczony |

Gate vs weekly **30.08** (0.668): Δ **+0.018** ≤ +0.02 → **ACCEPT** (na granicy).

### Live (closeout vs app)

| Okres | n | MAPE raw 5:00 | MAPE raw 12:00 |
|-------|--:|-------------:|---------------:|
| Era dual ICON **27.07–01.09** | 37 | **15,6%** | **15,8%** |
| Era ENS primary **02.09–05.09** | 4 | **7,7%** | **8,4%** |
| Całość **14.07–05.09** | 54 | 17,3% | 16,5% |

*(Wykresy odświeżone **06.09** do **05.09** — linia/tło **ENS primary od 02.09**.)*

CS4: na pochmurnych / mix często bliżej faktu (np. **29.08** pick **21,5** vs **21,1**); na jasnych RF bywa lepszy, ale **30.08** ens wyprzedził RF.

Ostatnie closeouty: **28.08** **34,2** · **29.08** **21,1** (CS4 ✓) · **30.08** **33,2** · **31.08** **24,6** (Accu→CS4; CS4 −17%, ens +7%) · **1.09** **32,4** (Accu→RF; ens **−3%**, ICON/CS4 −10%) · **2.09** **31,0** (Accu→RF; ENS **−11%**, ICON −12% — I≈U) · **3.09** **27,4** (Accu→RF; ENS **−11%**, ICON/CS4 −23/−24%, peak **−4%**) · **4.09** **18,9** (Accu CS4; ENS **−6,5%**, CS4 −20%) · **5.09** **20,2** (Accu CS4; ENS **+1,3%**, CS4 −8%).  
**6.09** Accu mix→**RF** (7/47%/0) · launchd ENS **28,1** / midday **26,3** · oneshot ½ **26,3** (ICON 23,8 / UKMO 28,9). **7.09** Accu **CS4** (2/93%/0) · ENS **24,3** · I≈U ~25. **8.09** Accu mix→**RF** (8/45%/0) · ENS **30,3** · ICON oneshot **30,8** · UKMO rad skip ([`NOTATKA_2026-09-06.md`](NOTATKA_2026-09-06.md)).  
**Gate routing 01.09:** **REJECT** ICON≥30%→CS4 · **ACCEPT** **ensemble ICON+UKMO** jako primary daily ([`NOTATKA_TEST_ROUTING_28-31_08.md`](NOTATKA_TEST_ROUTING_28-31_08.md)) — wdrożone `ENSEMBLE_PRIMARY=1` + `mlops/_ensemble_primary.sh`.

Wykresy (do **05.09**, odświeżone **06.09**): [`images/ml/july_validation_plot.png`](images/ml/july_validation_plot.png), [`images/ml/production_validation_plot.png`](images/ml/production_validation_plot.png) · opis błędów: [`images/ml/july_validation_summary.md`](images/ml/july_validation_summary.md).

---

## MLOps (skrót)

| Kiedy | Job |
|-------|-----|
| 05:00 | daily sync + prognoza (**ensemble primary** + shadow ICON/CS4/XGB) |
| 12:00 | midday (j.w.) |
| 16:00 | peak (j.w.) |
| wieczór | evening closeout → walidacja |
| niedziela **04:30** | `train_dual_weekly.sh` (16 + CS4 + XGB) |

Szczegóły komend: [`mlops/README.md`](../mlops/README.md). Flaga: `ENSEMBLE_PRIMARY=1` (`.env`).

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
| Pogoda 15.08–6.09 | [`NOTATKA_POGODA_2026-08-15.md`](NOTATKA_POGODA_2026-08-15.md) · dzień [`NOTATKA_2026-09-06.md`](NOTATKA_2026-09-06.md) |
| Weekly **06.09** | [`NOTATKA_WEEKLY_2026-09-06.md`](NOTATKA_WEEKLY_2026-09-06.md) |
| Weekly **30.08** | [`NOTATKA_WEEKLY_2026-08-30.md`](NOTATKA_WEEKLY_2026-08-30.md) |
| Weekly **23.08** | [`NOTATKA_WEEKLY_2026-08-23.md`](NOTATKA_WEEKLY_2026-08-23.md) |
| Weekly 16.08 | [`NOTATKA_WEEKLY_2026-08-16.md`](NOTATKA_WEEKLY_2026-08-16.md) |
| Dzień 19.08–6.09 | [`NOTATKA_2026-08-19.md`](NOTATKA_2026-08-19.md) · … · [`NOTATKA_2026-09-04.md`](NOTATKA_2026-09-04.md) · [`NOTATKA_2026-09-06.md`](NOTATKA_2026-09-06.md) |
| Oneshot shadow | [`NOTATKA_ONESHOT_2026-08-17.md`](NOTATKA_ONESHOT_2026-08-17.md) |
| Paper-trade Accu→RF/CS4 | paper-trade Accu (tylko repo prywatne) |
| Routing test 28–31.08 | [`NOTATKA_TEST_ROUTING_28-31_08.md`](NOTATKA_TEST_ROUTING_28-31_08.md) · plan [`PLAN_ENSEMBLE_NWP_2026.md`](PLAN_ENSEMBLE_NWP_2026.md) E1.6 |
| Reguła apki: SoC↓ + pochmurno → ładuj 22:00 | [`NOTATKA_REGULA_BATERIA_POCHMURNO_22.md`](NOTATKA_REGULA_BATERIA_POCHMURNO_22.md) |
| Log SoC / ForceCharge / AGD | [`NOTATKA_BATERIA_SOC_LOG.md`](NOTATKA_BATERIA_SOC_LOG.md) |

---

*Odświeżaj po każdym weekly train / po serii nowych closeoutów.*
