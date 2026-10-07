# Status ML / MLOps — aktualny snapshot

**Stan na:** 2026-10-04 (offline weekly) · live closeouty do **04.10** (n=83) · wykresy walidacji odświeżone **05.10**  
**Źródła liczb:** `models/pv_hourly_model.joblib` (**weekly 04.10**) · `forecast_validation.csv` (closeouty do **04.10**) · [`NOTATKA_WEEKLY_2026-10-04.md`](NOTATKA_WEEKLY_2026-10-04.md) · gate [`NOTATKA_TEST_ROUTING_28-31_08.md`](NOTATKA_TEST_ROUTING_28-31_08.md)

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
| Okno | 2025-06-01 → **2026-10-03** |
| Test MAE | **0.671** kWh/h |
| Gap train–test | **0.074** |
| Daily MAE | **3.54** kWh/d |
| Daily R² | **0.842** |
| Werdykt | nie przeuczony |

Gate vs weekly **27.09** (0.677): Δ **−0.006** → **ACCEPT** (REVIEW z 27.09 zamknięty: Δ vs 20.09 = +0.019). L30 chrono **0.808** (INFO). Primary bez zmian (RF16 + ENS). Dual report: shuffle + **L30 soft** ([`NOTATKA_GATE_DUAL_L30.md`](NOTATKA_GATE_DUAL_L30.md)); kryteria testu live i przejścia L30: [`NOTATKA_GATE_L30_CLOSEOUT.md`](NOTATKA_GATE_L30_CLOSEOUT.md). Szczegóły: [`NOTATKA_WEEKLY_2026-10-04.md`](NOTATKA_WEEKLY_2026-10-04.md).

### Live (closeout vs app)

| Okres | n | MAPE raw 5:00 | MAPE raw 12:00 |
|-------|--:|-------------:|---------------:|
| Era dual ICON **27.07–01.09** | 37 | **15,6%** | **15,8%** |
| Era ENS primary **02.09–04.10** | 33 | **17,4%** | **22,4%** |
| Całość **14.07–04.10** | 83 | 17,8% | 19,3% |

*(Wykresy odświeżone **05.10** do closeoutu **04.10**. Rekord |APE| serii nadal **11.09** (**174,8%** raw 12:00 — Fox **3,1** vs midday **8,52**). Era ENS ma więcej dni pochmurnych (55% vs 35% w erze dual); na tych samych typach dni raw 5:00 jest gorszy na słonecznych/mieszanych (+6,0 / +5,6 pp) i lepszy na pochmurnych (−6,6 pp) — mała próba, obserwacja. Tydzień po tygodniu (WAPE/bias, progi OK/WATCH/ALARM): [`images/ml/july_validation_summary.md`](images/ml/july_validation_summary.md) · kryteria: [`NOTATKA_GATE_L30_CLOSEOUT.md`](NOTATKA_GATE_L30_CLOSEOUT.md). Ostatni tydzień 28.09–04.10: WAPE 13,9% · bias −13,9% → ALARM w bias.)*

CS4: na pochmurnych / mix często bliżej faktu (np. **29.08** pick **21,5** vs **21,1**); na jasnych RF bywa lepszy, ale **30.08** ens wyprzedził RF.

Ostatnie closeouty: **28.08** **34,2** · **29.08** **21,1** (CS4 ✓) · **30.08** **33,2** · **31.08** **24,6** (Accu→CS4; CS4 −17%, ens +7%) · **1.09** **32,4** (Accu→RF; ens **−3%**, ICON/CS4 −10%) · **2.09** **31,0** (Accu→RF; ENS **−11%**, ICON −12% — I≈U) · **3.09** **27,4** (Accu→RF; ENS **−11%**, ICON/CS4 −23/−24%, peak **−4%**) · **4.09** **18,9** (Accu CS4; ENS **−6,5%**, CS4 −20%) · **5.09** **20,2** (Accu CS4; ENS **+1,3%**, CS4 −8%; **kajaki / pusty dom**) · **6.09** **23,3** (Accu→RF; ENS **+21%**; oneshot ICON **+2%**) · **7.09** **26,3** (okno→RF; ENS **+5,8%**) · **8.09** **33,3** (Accu RF; ENS **−8,7%**) · **9.09** **32,2** (Accu RF; ENS **−8,2%**, peak **−4,2%**).  
**10.09** Fox **18,8** · peak ENS **18,31 (−2,6%)** (brak daily @05). **11.09** Fox **3,1** · midday **8,52 (+175%)** ([`NOTATKA_2026-09-11.md`](NOTATKA_2026-09-11.md)). **12.09** Fox **13,1** · midday **13,47 (−2,8%)** · peak **11,94** — brak daily @05; Accu CS4 reżim OK ([`NOTATKA_2026-09-12.md`](NOTATKA_2026-09-12.md)). Dalsze closeouty **13.09–04.10** → tabela tydzień po tygodniu w `images/ml/july_validation_summary.md`; ostatnie: **27.09** **29,0** · **28.09** **31,8** (−13%) · **29.09** **32,7** (−17%) · **30.09** **31,6** (−14%) · **1.10** **19,1** (−25%) · **2.10** **31,3** (−14%) · **3.10** **30,3** (−12%) · **4.10** **29,6** (**−5%**, pierwszy dzień na nowych wagach).
**Gate routing 01.09:** **REJECT** ICON≥30%→CS4 · **ACCEPT** **ensemble ICON+UKMO** jako primary daily ([`NOTATKA_TEST_ROUTING_28-31_08.md`](NOTATKA_TEST_ROUTING_28-31_08.md)) — wdrożone `ENSEMBLE_PRIMARY=1` + `mlops/_ensemble_primary.sh`.

Wykresy (do **04.10**, odświeżone **05.10**; na production pomarańczowe linie = niedzielne retreningi, w tym 27.09 REVIEW i 04.10 + L30): [`images/ml/july_validation_plot.png`](images/ml/july_validation_plot.png) (góra kWh, dół |błąd| %), [`images/ml/production_validation_plot.png`](images/ml/production_validation_plot.png) (góra tylko 5:00, dół 5:00+12:00) · opis błędów: [`images/ml/july_validation_summary.md`](images/ml/july_validation_summary.md).

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
| Notatki pogodowe od 16.08 | [`NOTATKA_POGODA.md`](NOTATKA_POGODA.md) · dzień [`NOTATKA_2026-10-07.md`](NOTATKA_2026-10-07.md) (Accu **07** jasny→RF · **08–09** pochmurny→CS4; closeout **04** Fox **29,6** · **05** **28,1** · **06** **27,2**) · poprzednio [`NOTATKA_2026-10-03.md`](NOTATKA_2026-10-03.md) · [`NOTATKA_2026-10-01.md`](NOTATKA_2026-10-01.md) |
| Oś retreningów / wdrożeń | [`NOTATKA_RETRENINGI_I_WDROZENIA.md`](NOTATKA_RETRENINGI_I_WDROZENIA.md) |
| Weekly **20.09** | [`NOTATKA_WEEKLY_2026-09-20.md`](NOTATKA_WEEKLY_2026-09-20.md) |
| Weekly **04.10** | [`NOTATKA_WEEKLY_2026-10-04.md`](NOTATKA_WEEKLY_2026-10-04.md) |
| Weekly **27.09** | [`NOTATKA_WEEKLY_2026-09-27.md`](NOTATKA_WEEKLY_2026-09-27.md) |
| Gate dual L30 (soft X 2026) | [`NOTATKA_GATE_DUAL_L30.md`](NOTATKA_GATE_DUAL_L30.md) |
| Kryteria closeout tygodniowego + przejście L30 | [`NOTATKA_GATE_L30_CLOSEOUT.md`](NOTATKA_GATE_L30_CLOSEOUT.md) |
| Diagnoza niedoszacowania dni jasnych (05.10) | [`NOTATKA_BIAS_JASNE_DNI_2026-10-05.md`](NOTATKA_BIAS_JASNE_DNI_2026-10-05.md) |
| Weekly **13.09** | [`NOTATKA_WEEKLY_2026-09-13.md`](NOTATKA_WEEKLY_2026-09-13.md) |
| Weekly **06.09** | [`NOTATKA_WEEKLY_2026-09-06.md`](NOTATKA_WEEKLY_2026-09-06.md) |
| Weekly **30.08** | [`NOTATKA_WEEKLY_2026-08-30.md`](NOTATKA_WEEKLY_2026-08-30.md) |
| Weekly **23.08** | [`NOTATKA_WEEKLY_2026-08-23.md`](NOTATKA_WEEKLY_2026-08-23.md) |
| Weekly 16.08 | [`NOTATKA_WEEKLY_2026-08-16.md`](NOTATKA_WEEKLY_2026-08-16.md) |
| Dzień 19.08–11.09 | [`NOTATKA_2026-08-19.md`](NOTATKA_2026-08-19.md) · … · [`NOTATKA_2026-09-09.md`](NOTATKA_2026-09-09.md) · [`NOTATKA_2026-09-10.md`](NOTATKA_2026-09-10.md) · [`NOTATKA_2026-09-11.md`](NOTATKA_2026-09-11.md) |
| Oneshot shadow | [`NOTATKA_ONESHOT_2026-08-17.md`](NOTATKA_ONESHOT_2026-08-17.md) |
| Paper-trade Accu→RF/CS4 | log paper-trade — tylko repo prywatne |
| Routing test 28–31.08 | [`NOTATKA_TEST_ROUTING_28-31_08.md`](NOTATKA_TEST_ROUTING_28-31_08.md) · plan [`PLAN_ENSEMBLE_NWP_2026.md`](PLAN_ENSEMBLE_NWP_2026.md) E1.6 |
| Reguła apki: SoC↓ + pochmurno → ładuj 22:00 | [`NOTATKA_REGULA_BATERIA_POCHMURNO_22.md`](NOTATKA_REGULA_BATERIA_POCHMURNO_22.md) |
| Log SoC / ForceCharge / AGD | [`NOTATKA_BATERIA_SOC_LOG.md`](NOTATKA_BATERIA_SOC_LOG.md) |
| Czujniki podłogówki (test X–XI) | [`NOTATKA_CZUJNIKI_PODLOGOWKA.md`](NOTATKA_CZUJNIKI_PODLOGOWKA.md) |

---

*Odświeżaj po każdym weekly train / po serii nowych closeoutów.*
