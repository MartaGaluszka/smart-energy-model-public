# Status ML / MLOps — aktualny snapshot

**Stan na:** 2026-09-13  
**Źródła liczb:** `models/pv_hourly_model.joblib` (**weekly 13.09**) · `forecast_validation.csv` (closeouty do **12.09**) · [`NOTATKA_WEEKLY_2026-09-13.md`](NOTATKA_WEEKLY_2026-09-13.md) · gate [`NOTATKA_TEST_ROUTING_28-31_08.md`](NOTATKA_TEST_ROUTING_28-31_08.md)

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
| Okno | 2025-06-01 → **2026-09-12** |
| Test MAE | **0.666** kWh/h |
| Gap train–test | **0.071** |
| Daily MAE | **3.38** kWh/d |
| Daily R² | **0.859** |
| Werdykt | nie przeuczony |

Gate vs weekly **06.09** (0.686): Δ **−0.020** → **ACCEPT** (lepszy).

### Live (closeout vs app)

| Okres | n | MAPE raw 5:00 | MAPE raw 12:00 |
|-------|--:|-------------:|---------------:|
| Era dual ICON **27.07–01.09** | 37 | **15,6%** | **15,8%** |
| Era ENS primary **02.09–12.09** | 11 | **9,2%** | **24,3%** |
| Całość **14.07–12.09** | 61 | 16,9% | 18,5% |

*(Wykresy odświeżone **13.09** do closeoutu **12.09**. **11.09** = **rekord |APE|** serii (**174,8%** raw 12:00; poprzednio **25.08** ~153%) — Fox **3,1** vs midday **8,52**, Accu **CS4** OK. **12.09** Fox **13,1** vs midday **13,47** (**−2,8%**). **10–12.09** bez Porannej @05.)*

CS4: na pochmurnych / mix często bliżej faktu (np. **29.08** pick **21,5** vs **21,1**); na jasnych RF bywa lepszy, ale **30.08** ens wyprzedził RF.

Ostatnie closeouty: **28.08** **34,2** · **29.08** **21,1** (CS4 ✓) · **30.08** **33,2** · **31.08** **24,6** (Accu→CS4; CS4 −17%, ens +7%) · **1.09** **32,4** (Accu→RF; ens **−3%**, ICON/CS4 −10%) · **2.09** **31,0** (Accu→RF; ENS **−11%**, ICON −12% — I≈U) · **3.09** **27,4** (Accu→RF; ENS **−11%**, ICON/CS4 −23/−24%, peak **−4%**) · **4.09** **18,9** (Accu CS4; ENS **−6,5%**, CS4 −20%) · **5.09** **20,2** (Accu CS4; ENS **+1,3%**, CS4 −8%; **kajaki / pusty dom**) · **6.09** **23,3** (Accu→RF; ENS **+21%**; oneshot ICON **+2%**) · **7.09** **26,3** (okno→RF; ENS **+5,8%**) · **8.09** **33,3** (Accu RF; ENS **−8,7%**) · **9.09** **32,2** (Accu RF; ENS **−8,2%**, peak **−4,2%**).  
**10.09** Fox **18,8** · peak ENS **18,31 (−2,6%)** (brak daily @05). **11.09** Fox **3,1** · midday **8,52 (+175%)** ([`NOTATKA_2026-09-11.md`](NOTATKA_2026-09-11.md)). **12.09** Fox **13,1** · midday **13,47 (−2,8%)** · peak **11,94** — brak daily @05; Accu CS4 reżim OK ([`NOTATKA_2026-09-12.md`](NOTATKA_2026-09-12.md)). **13.09** w toku — Accu CS4 · ENS **24,42** watch mix.
**Gate routing 01.09:** **REJECT** ICON≥30%→CS4 · **ACCEPT** **ensemble ICON+UKMO** jako primary daily ([`NOTATKA_TEST_ROUTING_28-31_08.md`](NOTATKA_TEST_ROUTING_28-31_08.md)) — wdrożone `ENSEMBLE_PRIMARY=1` + `mlops/_ensemble_primary.sh`.

Wykresy (do **12.09**, odświeżone **13.09**): [`images/ml/july_validation_plot.png`](images/ml/july_validation_plot.png) (góra kWh, dół |błąd| %), [`images/ml/production_validation_plot.png`](images/ml/production_validation_plot.png) (góra tylko 5:00, dół 5:00+12:00) · opis błędów: [`images/ml/july_validation_summary.md`](images/ml/july_validation_summary.md).

**Review sobotni (przed retreningiem):** [`images/ml/weekly_model_weather_review.md`](images/ml/weekly_model_weather_review.md) — MAPE × typ dnia × **ENS / ICON / CS4 / XGB** · `./mlops/weekly_model_review.sh` · launchd **sob 10:00** (`install_launchd.sh`).

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
| Pogoda 15.08–11.09 | [`NOTATKA_POGODA_2026-08-15.md`](NOTATKA_POGODA_2026-08-15.md) · dzień [`NOTATKA_2026-09-11.md`](NOTATKA_2026-09-11.md) |
| Weekly **13.09** | [`NOTATKA_WEEKLY_2026-09-13.md`](NOTATKA_WEEKLY_2026-09-13.md) |
| Weekly **06.09** | [`NOTATKA_WEEKLY_2026-09-06.md`](NOTATKA_WEEKLY_2026-09-06.md) |
| Weekly **30.08** | [`NOTATKA_WEEKLY_2026-08-30.md`](NOTATKA_WEEKLY_2026-08-30.md) |
| Weekly **23.08** | [`NOTATKA_WEEKLY_2026-08-23.md`](NOTATKA_WEEKLY_2026-08-23.md) |
| Weekly 16.08 | [`NOTATKA_WEEKLY_2026-08-16.md`](NOTATKA_WEEKLY_2026-08-16.md) |
| Dzień 19.08–11.09 | [`NOTATKA_2026-08-19.md`](NOTATKA_2026-08-19.md) · … · [`NOTATKA_2026-09-09.md`](NOTATKA_2026-09-09.md) · [`NOTATKA_2026-09-10.md`](NOTATKA_2026-09-10.md) · [`NOTATKA_2026-09-11.md`](NOTATKA_2026-09-11.md) |
| Oneshot shadow | [`NOTATKA_ONESHOT_2026-08-17.md`](NOTATKA_ONESHOT_2026-08-17.md) |
| Paper-trade Accu→RF/CS4 | [`NOTATKA_PAPER_TRADE_ACCU_REGIME.md`](NOTATKA_PAPER_TRADE_ACCU_REGIME.md) |
| Routing test 28–31.08 | [`NOTATKA_TEST_ROUTING_28-31_08.md`](NOTATKA_TEST_ROUTING_28-31_08.md) · plan [`PLAN_ENSEMBLE_NWP_2026.md`](PLAN_ENSEMBLE_NWP_2026.md) E1.6 |
| Reguła apki: SoC↓ + pochmurno → ładuj 22:00 | [`NOTATKA_REGULA_BATERIA_POCHMURNO_22.md`](NOTATKA_REGULA_BATERIA_POCHMURNO_22.md) |
| Log SoC / ForceCharge / AGD | [`NOTATKA_BATERIA_SOC_LOG.md`](NOTATKA_BATERIA_SOC_LOG.md) |
| Czujniki podłogówki (test X–XI) | [`NOTATKA_CZUJNIKI_PODLOGOWKA.md`](NOTATKA_CZUJNIKI_PODLOGOWKA.md) |

---

*Odświeżaj po każdym weekly train / po serii nowych closeoutów.*
