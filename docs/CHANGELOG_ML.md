# Changelog ML — porównania zmian

Protokół: każda zmiana porównywana z baseline; **REJECT** gdy Test MAE >0,02 kWh/h lub operacyjny MAE +15%.

Generowanie: `python scripts/compare_model_change.py ... --append-changelog`

Reguły decyzji:

| Decyzja | Warunek |
|---------|---------|
| **ACCEPT** | Test MAE ≤ baseline + 0,02; brak regresji operacyjnej |
| **REVIEW** | Test MAE remis (+0,00…0,02); wymaga oceny operacyjnej (≥7 dni) |
| **REJECT** | Test MAE > baseline + 0,02 lub operacyjny MAE wyraźnie gorszy |

Metryki offline: ten sam split 80/20 po dniach (`random_state=42`).  
Metryki operacyjne: `forecast_validation.csv` (rolling N dni).

---

## Target godzinowy = PVEnergyTotal (jak w app) — 2026-07-18

**Raport wdrożeniowy:** [`UPDATE_2026-07-18_target-pve.md`](UPDATE_2026-07-18_target-pve.md) · wycofana skala: [`UPDATE_2026-07-18_skala-app.md`](UPDATE_2026-07-18_skala-app.md)

**Przyczyna:** trening na ∫`pvPower` (~wyżej) vs closeout/app na `PVEnergyTotal` (~niżej) → systematyczne „zawyżenie” operacyjne (~10–15%).  
**Wymaganie:** ta sama zmienna do treningu i porównań — bez skalowania `pvPower`.

| Element | Wartość |
|---------|---------|
| `PV_HOURLY_TARGET` | **`pve`** (domyślne; alias `app`) |
| Metoda | godzinowe **dodatnie delty** licznika `PVEnergyTotal` z `foxess_timeseries` |
| Closeout | ta sama suma godzin = dzienne `PVEnergyTotal` z aplikacji |
| Hiperparametry | `max_depth=6`, `min_samples_leaf=20`, `min_samples_split=20` |
| Rollback | `PV_HOURLY_TARGET=pvpower` + `pv_hourly_model_before_app_scale.joblib` |

Sanity 18.07: Σ ΔPVE godzin = **22.20** = report/app (∫pvPower było 25.11).

Gate (oba modele na targetcie PVE; baseline = stary model z ∫pvPower):

| Metryka | Baseline (stary) | Kandydat (PVE) | Δ |
|---------|------------------|----------------|---|
| Test MAE [kWh/h] | 0.568 | 0.582 | +0.014 |
| Gap | 0.009 | 0.040 | +0.031 |
| Daily MAE [kWh/d] | 3.45 | 3.57 | +0.124 |

**Decyzja: ACCEPT (operacyjnie)** — Test MAE w tolerancji REVIEW (+0.014 ≤ 0.02); wdrażamy, bo trening i closeout używają tej samej zmiennej co app. Obserwacja ≥7 dni.

Artefakt: `pv_hourly_model.joblib` · backup: `pv_hourly_model_before_pve_direct.joblib`

*(Wcześniejsza próba „skalowania” profilu pvPower do dziennego PVE została wycofana.)*

---

## ICON seamless + refetch + retrening — 2026-07-17

**Raport wdrożeniowy (dzień):** [`UPDATE_2026-07-17_gps-icon.md`](UPDATE_2026-07-17_gps-icon.md)

**Przyczyna:** `best_match` Open-Meteo wygładzał chmury (np. 09.07: cloud 53% / rad 6.2 vs ICON 86% / 4.3 przy PV app 17 kWh).

| Element | Wartość |
|---------|---------|
| `OPENMETEO_MODEL` | **icon_seamless** |
| Pipeline | `fetch_weather.py` → `train_hourly_model_tuning.py` |
| Kod | `OpenMeteoClient` respektuje `OPENMETEO_MODEL` (archive + forecast) |

Sanity 5–20h (po refetch): **09.07** cloud 86%, rad 4.29 · **12.07** cloud 96%, rad 1.42.

| Metryka | Baseline (GPS/`best_match` model na pogodzie ICON) | Kandydat (retrening ICON) | Δ |
|---------|-----------------------------------------------------|---------------------------|---|
| Test MAE [kWh/h] | 0.682 | **0.666** | **−0.016** |
| Gap | 0.026 | 0.086 | +0.060 |
| Test R² | 0.708 | **0.710** | +0.001 |
| Daily MAE [kWh/d] | 5.00 | **4.61** | **−0.40** |
| Hiperparametry | — | `max_depth=6`, `min_samples_leaf=20`, `min_samples_split=20` | |

**Decyzja: ACCEPT** (Test MAE poprawione o 0.016 ≤ tolerancja; daily MAE też w dół).

Artefakt: `models/pv_hourly_model.joblib`  
Backup: `pv_hourly_model_before_icon.joblib`

### Porównanie operacyjne (closeout vs ICON)

**Status (2026-07-17 wieczór):** brak jeszcze wierszy `forecast_validation.csv` **po** wdrożeniu ICON.  
Model ICON zapisany ~19:52; ostatni closeout = **2026-07-16** (sprzed ICON). Snapshoty 5:00/12:00/16:00 z 17.07 też jeszcze na starym `.joblib`.

| Warstwa | Co porównujemy | Dane |
|---------|----------------|------|
| **A. Live closeout (pre-ICON)** | prognoza dnia vs FoxESS app | `forecast_validation.csv` (14–16.07) |
| **B. Replay archiwum (po ICON)** | RF before_icon vs RF ICON na pogodzie ICON *archiwum* | `forecasts/icon_operational_replay_20260714_16.csv` |
| **C. Live closeout (po ICON)** | te same metryki co A, od pierwszego wieczoru z nowym modelem | *do uzupełnienia* (≥7 dni) |

**A — baseline live (pre-ICON):**

| Dzień | Fakty (app) | Daily 5:00 | Midday | \|błąd\| daily |
|-------|------------:|-----------:|-------:|---------------:|
| 14.07 | 31,0 | 20,8 | 25,1 | 10,2 |
| 15.07 | 10,9 | 17,4 | 8,3 | 6,5 |
| 16.07 | 29,5 | 26,9 | 18,0 | 2,6 |
| **MAE** | | | | **~6,4 kWh** |

**B — replay offline (archiwum ICON, suma godzin RF; nie jest to prognoza poranna):**

| Dzień | Fakty ML | Replay before_icon | Replay ICON | \|błąd\| ICON vs ML |
|-------|---------:|-------------------:|------------:|--------------------:|
| 14.07 | 34,6 | 28,8 | 29,8 | 4,8 |
| 15.07 | 12,3 | 15,9 | 18,2 | 5,9 |
| 16.07 | 33,0 | 30,6 | 32,5 | 0,5 |
| **MAE vs ML** | | ~4,0 | **~3,7** | |

Uwaga: replay B używa **znanej** pogody archiwum → optymistyczny względem live A. Na 15.07 (pochmurno) ICON nie wygrywa automatycznie — stąd potrzeba warstwy **C**.

**C — plan:** po ≥7 closeoutach na GPS+ICON uzupełnić tabelę rolling MAE (daily / midday / best snapshot) i ewentualny gate operacyjny (+15% = REJECT).

---

## GPS dach + refetch Open-Meteo + retrening — 2026-07-17

**Raport wdrożeniowy (dzień):** [`UPDATE_2026-07-17_gps-icon.md`](UPDATE_2026-07-17_gps-icon.md)

**Przyczyna:** współrzędne pogody były ustawione na Kraków-Observatorium (`50.0647, 19.9450`) zamiast dachu — przesunięcie ~10 km (chmury/radiacja z innej komórki siatki).

| Parametr instalacji | Wartość |
|---------------------|---------|
| `WEATHER_LAT` / `LON` | ~50.0 / 19.9 (dokładne GPS dachu tylko w lokalnym `.env`) |
| `PANEL_TILT_DEG` / `AZIMUTH` | 35° / 180° (S) |
| `PV_SYSTEM_KWP` | 5.39 (11 paneli) |
| `BATTERY_CAPACITY_KWH` | 10.36 |

**Pipeline:** `fetch_weather.py` (nadpisanie archiwum) → `train_hourly_model_tuning.py` (GridSearch min-gap) → wykresy akademickie + `production_validation.png`.

| Metryka | Przed (GPS Observatorium, model 2026-07-16) | Po (GPS dach, retrening) | Δ |
|---------|---------------------------------------------|--------------------------|---|
| Okno | expanding → 2026-07-15 | **2025-06-01 → 2026-07-16** | |
| Test MAE [kWh/h] | 0.661 | **0.652** | **−0.009** |
| Gap | 0.103 | **0.047** | **−0.056** |
| Test R² | 0.625 | **0.725** | **+0.100** |
| Daily MAE [kWh/d] | 3.52 | 4.44 | +0.92 *(inne okno / split)* |
| `min_samples_split` | 20 | **40** | |

Porównanie `.joblib` na **tej samej** nowej pogodzie (stary model vs nowy): Test MAE 0.639 → 0.652 (Δ=+0.013, remis ≤0.02) → protokół **REVIEW**; wdrożenie GPS i tak **ACCEPT** jako korekta źródła danych.

Artefakt: `models/pv_hourly_model.joblib`  
Backup: `pv_hourly_model_before_gps.joblib`

---

## Baseline rad×yield — kalibracja z train — 2026-07-17

| Element | Było | Jest |
|---------|------|------|
| Yield dzienny | stała `0.17` | mediana/OLS `PV/radiacja` z **train** (OOF w GroupKFold) |
| Coef godzinowy | stała `0.0024` | j.w. na `radiation_wm2` |
| Poprawa RF vs baseline (dzienny CV) | ~74% (artefakt skali) | **~24%** |
| Poprawa RF vs baseline (godzinowy CV) | ~35% | **~50%** |

**Decyzja: ACCEPT (dokumentacja / metodologia)** — bez zmiany modelu produkcyjnego; uczciwszy punkt odniesienia.

Skrypty: `final_cv_production_split.py`, `final_cv_production_split_hourly.py`, `compare_split_strategies.py`.  
Docs: `02_ML_predykcja_PV.md` §1.3, `03_ZALOZENIA_I_DECYZJE.md`, notebook `02_ML_predykcja_PV.ipynb`.

---

## Rolling 12m — 2026-07-16

| Metryka | Baseline (expanding/stary) | Kandydat (rolling 12m) | Δ |
|---------|---------------------------|------------------------|---|
| Okno | 2025-06-01 → 2026-05-31 | 2025-07-16 → 2026-07-15 | wyrzuca czerwiec 2025 |
| Test MAE [kWh/h] | 0,661 | 0,729 | +0,068 |
| Gap | 0,103 | 0,139 | +0,036 |
| Daily MAE [kWh/d] | 3,52 | 5,07 | +1,55 |

**Decyzja: REJECT**

Uzasadnienie:
- Test MAE +0,068 (> 0,02)
- Utrata cennego lata 2025 (czerwiec wyrzucony z okna)

---

## Expanding window — 2026-07-16

| Metryka | Baseline (prod. maj 2026) | Kandydat (expanding) | Δ |
|---------|---------------------------|----------------------|---|
| Okno | 2025-06-01 → 2026-05-31 | 2025-06-01 → 2026-07-15 | +406 dni |
| Test MAE [kWh/h] | 0,661 | 0,668 | +0,007 |
| Gap | 0,103 | 0,045 | −0,058 |
| Test R² | 0,625 | 0,699 | +0,074 |
| Daily MAE [kWh/d] | 3,52 | 4,39 | +0,87 |

**Decyzja: ACCEPT**

Uzasadnienie:
- Test MAE remis (+0,007 ≤ 0,02)
- Gap spadł o połowę — mniejsze przeuczenie
- Przywrócono czerwiec 2025; rolling 12m odrzucony

---

## 16 vs 19 cech — 2026-07-14

| Metryka | 19 cech (EXTENDED) | 16 cech (PRODUCTION) | Δ |
|---------|-------------------|----------------------|---|
| Test MAE [kWh/h] | 0,667 | 0,661 | −0,006 |
| Gap | 0,124 | 0,103 | −0,021 |
| Daily MAE [kWh/d] | 3,71 | 3,52 | −0,19 |

**Decyzja: ACCEPT** — 16 cech produkcyjnych (bez `month`/`doy_*`).

---

## Geometria paneli (tilt/azymut) — przygotowane, jeszcze NIE wdrożone

**Status:** kod gotowy, **wyłączony** (`PANEL_GEOMETRY_FEATURES=0`).

| Parametr | Wartość |
|----------|---------|
| `PANEL_TILT_DEG` | **35°** (~70% nachylenia dachu) |
| `PANEL_AZIMUTH_DEG` | **180** (południe) |
| Moduł | `src/features/panel_geometry.py` |
| Preview | `python scripts/preview_panel_geometry.py --day YYYY-MM-DD` |
| Cechy | `sun_elevation_deg`, `sun_azimuth_deg`, `incidence_cos`, `poa_approx_wm2` |

**Plan:** ~7 dni obserwacji (poranek vs prognoza) → włączyć flagę → trening z `HOURLY_FEATURE_COLUMNS_WITH_PANEL` → `compare_model_change.py` → ACCEPT/REJECT.

**Nie zmienia** modelu produkcyjnego ani prognoz operacyjnych do czasu eksperymentu.

---
## CS4 low+mid+clearness — gate + decyzja produkcji — 2026-07-26

**Przyczyna:** oneshot tydzień 19–25.07 + oficjalny gate 16 vs 19.

**Raport (tabele):** [`UPDATE_2026-07-26_cs4-dual.md`](UPDATE_2026-07-26_cs4-dual.md) · CSV: `data/processed/oneshot_cs4_geom_week_20260719_25.csv`

| Metryka | Baseline **16** | Kandydat **CS4 (19)** | Δ |
|---------|-----------------|------------------------|---|
| Test MAE [kWh/h] | 0.623 | **0.621** | **−0.002** |
| Gap | 0.081 | 0.082 | +0.002 |
| Daily MAE [kWh/d] | 4.03 | **3.94** | **−0.087** |

**Gate: ACCEPT** (Test MAE lekko w dół).

**Decyzja wdrożeniowa: OBA na produkcji (dual launchd).**  
- Ranking AGD / `pv_forecast.csv` = **16 cech**  
- CS4 w tych samych jobach 5:00/12:00/16:00 → `*_cs4` + `pv_forecast_cs4.csv` (`FORECAST_CS4_ENABLED=1`)  
- Niedziela: `train_dual_weekly.sh` trenuje **oba** modele  
- Closeout porównuje też CS4; UKMO tylko w testach  

Po aktualizacji plist: `./mlops/install_launchd.sh`

| Artefakt | Status |
|----------|--------|
| `pv_hourly_model.joblib` | **16 cech — PRIMARY** |
| `pv_hourly_model_cs4.joblib` | **19 cech — CS4 na produkcji (dual)** |
| `mlops/forecast_cs4_shadow.sh` | daily/midday/peak |
| `mlops/train_dual_weekly.sh` | niedziela launchd |
| UKMO | oneshot / unit tests — nie produkcja |

Oneshot tydzień (MAE vs app): Baseline 5,23 · **CS4 4,54** · Geom 4,91 · CS4+Geom 4,67 · Live 5:00 4,71.  
CS4+Geom **nie** wdrażać.

### Przeuczenie + testy (2026-07-26)

| Model | Train MAE | Test MAE | Gap | Verdict |
|-------|-----------|----------|-----|---------|
| 16 (prod) | 0.542 | **0.623** | 0.081 (13%) | **NIE przeuczony** |
| CS4 | 0.538 | **0.621** | 0.082 (13%) | **NIE przeuczony** |

Smoke / dual unit: **OK**.  
UKMO oneshot (19–25.07 opad + RF 21–24.07): **OK** — CSV `oneshot_icon_vs_ukmo_*` / `oneshot_rf_icon_vs_ukmo_*`.  
Werdykt UKMO: timing deszczu czasem lepszy, ale **ten sam RF na UKMO zawyża** PV (np. 21.07: 32 vs app 18,8) → **nie** przełączać `OPENMETEO_MODEL` bez retrainu.

Komenda: `./scripts/analysis/run_ukmo_tests.sh --start 2026-07-19 --end 2026-07-25`

**Protokół 2 tyg.:** UKMO tylko jako **obserwacja ręczna** na gorsze dni (mm / first_wet vs ICON + Accu) — szczegóły w [`PLAN_T1_T2_LIPIEC_2026.md`](PLAN_T1_T2_LIPIEC_2026.md) § „Najbliższe ~2 tygodnie”. `pvlib` Ineichen = park (clearness już w CS4).

---
