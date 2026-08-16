# Notatka — retreningi i wdrożenia (lipiec 2026)

Krótka oś czasu: **kiedy** był retrening `.joblib`, **co** weszło do produkcji.  
Szczegóły gate’ów: [CHANGELOG_ML.md](CHANGELOG_ML.md).

**Model produkcyjny teraz:** dual — `pv_hourly_model.joblib` (**16**) + `pv_hourly_model_cs4.joblib` (**CS4**)  
**Stan na 2026-08-16:** GPS dach · ICON · target **ΔPVEnergyTotal** · Test MAE **0.643** (16) / **0.637** (CS4) · **nieprzeuczone** · UKMO = tylko testy · weekly: [`NOTATKA_WEEKLY_2026-08-16.md`](NOTATKA_WEEKLY_2026-08-16.md)

---

## Oś czasu (skrót)

| Data | Godz. (ok.) | Co wdrożono | Retrening RF? | Test MAE* | Backup `.joblib` |
|------|-------------|-------------|---------------|-----------|------------------|
| **2026-07-13** | — | **16 cech** (bez kalendarza), prognoza hybrydowa, dual-source pogoda | tak | ~0.661 | (starsze) |
| **2026-07-14** | 23:10 | Artefakt 19 cech (legacy) obok produkcji | porównanie | 0.667 (ext.) | `pv_hourly_model_19.joblib` |
| **2026-07-16** | — | Expanding window (ACCEPT); rolling 12m **REJECT**; korekta operacyjna intraday | expanding: tak | ~0.668 | — |
| **2026-07-17** | ~16:00 | **GPS dach** (~50.0 / 19.9) + refetch OM | tak | **0.652** | `…_before_gps.joblib` |
| **2026-07-17** | ~19:52 | **ICON** `icon_seamless` + refetch + retrening | tak | **0.666** | `…_before_icon.joblib` |
| **2026-07-18** | ~16:26 | Próba „skali app” (pvPower→PVE) — **wycofana** | tak (pośredni) | — | `…_before_app_scale.joblib` |
| **2026-07-18** | ~16:32 | **Target = ΔPVEnergyTotal** (jak w app) | tak | **0.582** | `…_before_pve_direct.joblib` |
| **2026-07-26** | ~17:00 | **Dual prod:** 16 primary + CS4 w launchd; train niedziela = oba; UKMO w testach | tak (CS4 + gate vs 16) | **0.623** / **0.621** | `…_before_cs4.joblib` |
| **2026-08-09** | 04:30 | Weekly odświeżenie wag (+7 dni do 08.08); bez zmiany logiki | tak (16 + CS4 + XGB+TS) | **0.624** / **0.632** / **0.608** | (nadpisanie `.joblib`) |
| **2026-08-16** | 04:30 | Weekly odświeżenie wag (okno → 15.08); primary bez zmiany | tak (16 + CS4 + XGB+TS) | **0.643** / **0.637** / **0.626** | (nadpisanie `.joblib`) |

\*Test MAE z summary w momencie treningu — **nie porównuj 0.666 z 0.582 wprost** (inna skala targetu: ∫pvPower vs PVE).

---

## Szczegóły po datach

### 2026-07-13 — model 16 cech + hybryda

| | |
|--|--|
| **Wdrożone** | `HOURLY_FEATURE_COLUMNS_PRODUCTION` (16 cech); prognoza hybrydowa (archiwum + FoxESS + forecast); `weather_data` dual-source |
| **Retrening** | GridSearch min-gap → RF `max_depth=6` |
| **Metryki** | Test MAE ~**0.661**, gap ~0.103 (era Observatorium / `best_match`) |
| **Docs** | [UPDATE_2026-07-13_16-cech-hybryda.md](UPDATE_2026-07-13_16-cech-hybryda.md) |

### 2026-07-14…16 — MLOps live + okno treningu

| | |
|--|--|
| **Wdrożone (bez zmiany cech)** | launchd: midday ~14.07, daily 5:00 ~15.07, peak 16:00 ~16.07; evening closeout |
| **2026-07-16** | Expanding window **ACCEPT**; rolling 12m **REJECT**; warstwa **korekty operacyjnej** (intraday / cloudy / ranking) — [UPDATE_2026-07-16_korekta-operacyjna.md](UPDATE_2026-07-16_korekta-operacyjna.md) |
| **Target ML** | nadal ∫`pvPower`; closeout vs app = `PVEnergyTotal` (rozjazd skali) |

### 2026-07-17 ~16:00 — GPS dach

| | |
|--|--|
| **Wdrożone** | `WEATHER_LAT/LON` = GPS dachu (tylko w `.env`); refetch Open-Meteo; retrening |
| **Gate** | REVIEW offline (+0.013 na nowej pogodzie); **ACCEPT** jako korekta źródła |
| **Metryki (własny summary)** | Test MAE **0.652**, gap **0.047** |
| **Backup** | `pv_hourly_model_before_gps.joblib` |
| **Docs** | [UPDATE_2026-07-17_gps-icon.md](UPDATE_2026-07-17_gps-icon.md) § GPS |

### 2026-07-17 ~19:52 — ICON

| | |
|--|--|
| **Wdrożone** | `OPENMETEO_MODEL=icon_seamless`; refetch archiwum+forecast; retrening |
| **Gate** | **ACCEPT** (na pogodzie ICON: 0.682 → **0.666**) |
| **Metryki (własny summary)** | Test MAE **0.666**, Daily MAE **4.61**, gap 0.086 |
| **Backup** | `pv_hourly_model_before_icon.joblib` |
| **Uwaga operacyjna** | Snapshoty 5:00/12:00/16:00 z **17.07** jeszcze na modelu sprzed ICON; pierwszy pełny dzień ICON w live ≈ **18.07** |
| **Docs** | [UPDATE_2026-07-17_gps-icon.md](UPDATE_2026-07-17_gps-icon.md) § ICON |

### 2026-07-18 ~16:32 — target PVEnergyTotal (produkcja teraz)

| | |
|--|--|
| **Wdrożone** | `PV_HOURLY_TARGET=pve` — godzinowe **delty `PVEnergyTotal`**; trening = closeout = app |
| **Wycofane** | skalowanie profilu `pvPower` do dziennego PVE (było ~16:26) |
| **Gate** | REVIEW offline vs stary model na danych PVE (+0.014 Test MAE); **wdrożone operacyjnie** (spójność zmiennej) |
| **Metryki (własny summary)** | Test MAE **0.582**, Daily MAE **3.57**, gap **0.040** |
| **Backup** | `pv_hourly_model_before_pve_direct.joblib` (+ `…_before_app_scale.joblib` = ICON/∫pvPower) |
| **Uwaga operacyjna** | Prognozy 14–17.07 na wykresach = **stary** model; linia rzeczywistości już = app. Pierwsza prognoza 5:00 / closeout na PVE = od **19.07** (lub ręczny run 18.07 wieczór) |
| **Docs** | [UPDATE_2026-07-18_target-pve.md](UPDATE_2026-07-18_target-pve.md) · wycofana skala: [UPDATE_2026-07-18_skala-app.md](UPDATE_2026-07-18_skala-app.md) |

---

## Co jest w produkcji „na żywo” vs na wykresie

| Warstwa | 14–17.07 (closeouty) | Od modelu z 18.07 ~16:32 |
|---------|----------------------|---------------------------|
| Rzeczywistość na wykresie | `actual_pv_total` = **app / PVE** | to samo |
| Prognoza snapshotów | model GPS/ICON, target **∫pvPower** (+ adjust) | kolejne runy: target **PVE** |
| `.joblib` na dysku | nadpisany 18.07 | **PVE** |

---

## Rollback (gdyby trzeba)

```bash
# Wróć do ICON + ∫pvPower (przed PVE)
cp models/pv_hourly_model_before_app_scale.joblib models/pv_hourly_model.joblib
# w .env:
# PV_HOURLY_TARGET=pvpower
# OPENMETEO_MODEL=icon_seamless
```

```bash
# Wróć do GPS + best_match (przed ICON)
cp models/pv_hourly_model_before_icon.joblib models/pv_hourly_model.joblib
# OPENMETEO_MODEL=best_match   # lub usuń
```

---

## 2026-07-26 — dual 16+CS4 + testy UKMO

| | |
|--|--|
| **Wdrożone** | Primary **16** + **CS4** w launchd (5:00/12:00/16:00); `train_dual_weekly.sh` niedziela; closeout z kolumnami CS4 |
| **Gate 16 vs CS4** | ACCEPT — Test MAE 0.623 → **0.621**, Daily 4.03 → **3.94** |
| **Przeuczenie** | Oba: verdict **NIE przeuczony** (gap ~13% test MAE) |
| **Testy** | `test_dual_and_ukmo.py` OK · `test_pv_pipeline_smoke.py` OK · UKMO oneshot OK |
| **UKMO** | Tylko testy — RF na UKMO **zawyża** vs ICON na 21/23/24.07 (bez retrainu UKMO) |
| **Docs** | [UPDATE_2026-07-26_cs4-dual.md](UPDATE_2026-07-26_cs4-dual.md) · [CHANGELOG_ML.md](CHANGELOG_ML.md) |

---

## Plan T1–T2 (od 19.07)

Rozpiska + status: **[PLAN_T1_T2_LIPIEC_2026.md](PLAN_T1_T2_LIPIEC_2026.md)**  
Skrót: ocena na **raw** · `FORECAST_OPERATIONAL_ADJUST=0` · ≥7 closeoutów · dopiero T2 decyzja o korektcie / cloudy / geometrii.

---

## 2026-08-09 — weekly retrain (dual + shadow)

| | |
|--|--|
| **Godz.** | **04:30** niedziela (`train_dual_weekly.sh`) |
| **Okno** | 2025-06-01 → **2026-08-08** (+7 dni vs 02.08; 425 dni) |
| **Zmiany logiki** | brak — primary **16**, shadow **CS4** + **XGB+TS** |
| **RF16** | Test MAE **0.624** (02.08: 0.631) · gap **0.057** · Daily **3.96** · ✅ nie przeuczony |
| **CS4** | Test MAE **0.632** · gap **0.066** · Daily **3.93** · ✅ |
| **XGB+TS** | Test MAE **0.608** (02.08: 0.625) · Daily **3.56** · ✅ najlepszy offline |
| **Gate** | bez podmiany produkcji |
| **Live po retrainie** | pierwsza prognoza 5:00 = **09.08** (niedz. jasny, raw zaniża 10%) |

**Tydzień obserwacji 03–09.08** (na modelu 02.08, oprócz 09.08 rano): MAPE raw 5:00 **7.3%** · CS4 **6.3%**. Upał 03–06 OK (~1–3%); burza **07.08** — CS4 **1.5%** vs raw **12.9%**; **08.08** po frontcie — raw zawyża **21.6%** (MB chmury rano); **09.08** słońce **37.7 kWh**, raw zaniża. Wpis: `weather_notes` id closeout_stats + mlops/retrain.

---

## 2026-08-16 — weekly retrain

| | |
|--|--|
| **Godz.** | **04:30** niedziela |
| **Okno** | 2025-06-01 → **2026-08-15** |
| **Zmiany logiki** | brak — primary **RF16**, shadow **CS4** + **XGB+TS** |
| **RF16** | Test MAE **0.643** · gap **0.063** · Daily **3.56** · ✅ nie przeuczony |
| **CS4** | Test MAE **0.637** · gap **0.068** · Daily **3.59** · ✅ |
| **XGB+TS** | Test MAE **0.626** · gap **0.074** · Daily **3.17** · ✅ |
| **Gate vs 09.08** | Δ RF16 Test MAE **+0.019** (≤ +0.02) → **ACCEPT** · primary bez zmiany |
| **Docs** | [`NOTATKA_WEEKLY_2026-08-16.md`](NOTATKA_WEEKLY_2026-08-16.md) |

Closeout **17.08** (deszcz Accu/MB) = pierwszy dzień porównania nowych wag RF vs CS4.

---

## 2026-08-02 — Error Analysis (skala chmur + FI) → TODO

| | |
|--|--|
| **Problem** | Dni przejściowe / po froncie: duże APE (np. 24.07 ~100%); live dual 26.07–01.08 — CS4 nie bije 16 |
| **Hipotezy** | (1) mieszana skala zachmurzenia 0–1 vs 0–100 w pipeline; (2) model „wierzy” w godzinę/DOY mocniej niż w chmury |
| **Docs** | **[UPDATE_2026-08-02_error-analysis-cloud-fi.md](UPDATE_2026-08-02_error-analysis-cloud-fi.md)** — checklista **EA.1–EA.7** też w PLAN (backlog) |
| **Prod** | bez zmian do audytu; primary 16 zostaje |

---

## Powiązane

| Plik | Treść |
|------|--------|
| [NOTATKA_WEEKLY_2026-08-16.md](NOTATKA_WEEKLY_2026-08-16.md) | Weekly 16.08 — gate ACCEPT, metryki |
| [PLAN_T1_T2_LIPIEC_2026.md](PLAN_T1_T2_LIPIEC_2026.md) | Rozpiska T1–T2, checklista closeoutów · EA TODO |
| [UPDATE_2026-08-02_error-analysis-cloud-fi.md](UPDATE_2026-08-02_error-analysis-cloud-fi.md) | Error Analysis: skala chmur + feature importance |
| [CHANGELOG_ML.md](CHANGELOG_ML.md) | Gate ACCEPT/REVIEW/REJECT |
| [UPDATE_2026-07-13_16-cech-hybryda.md](UPDATE_2026-07-13_16-cech-hybryda.md) | 16 cech, hybryda |
| [UPDATE_2026-07-16_korekta-operacyjna.md](UPDATE_2026-07-16_korekta-operacyjna.md) | Korekta operacyjna |
| [UPDATE_2026-07-17_gps-icon.md](UPDATE_2026-07-17_gps-icon.md) | GPS dach + ICON |
| [UPDATE_2026-07-18_skala-app.md](UPDATE_2026-07-18_skala-app.md) | Skala app — wycofana |
| [UPDATE_2026-07-18_target-pve.md](UPDATE_2026-07-18_target-pve.md) | Target ΔPVEnergyTotal |
| [02_ML_predykcja_PV.md](02_ML_predykcja_PV.md) | Metryki produkcyjne |
| [UPDATE_2026-07-26_cs4-dual.md](UPDATE_2026-07-26_cs4-dual.md) | Dual 16+CS4, tydzień oneshot, UKMO |
| `data/processed/hourly_model_tuning_summary_production.csv` | Ostatni summary treningu 16 |
| `data/processed/hourly_model_tuning_summary_cs4.csv` | Summary CS4 |
