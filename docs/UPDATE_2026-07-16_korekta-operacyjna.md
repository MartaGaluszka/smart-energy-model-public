# Aktualizacja produkcyjna — 2026-07-16

**Zakres:** korekta operacyjna prognozy PV · profil błędu · walidacja wieczorna · advisor baterii · pivot pvPower

Powiązane: [03_ZALOZENIA_I_DECYZJE.md](03_ZALOZENIA_I_DECYZJE.md) · [02_ML_predykcja_PV.md](02_ML_predykcja_PV.md) · commit `cd1caa2`

---

## 1. Podsumowanie zmian (historia projektu)

| Data / commit | Obszar | Co wdrożono |
|---------------|--------|-------------|
| **2026-07-13** | Model ML | 16 cech, RF min-gap, prognoza hybrydowa (archiwum + FoxESS) |
| **2026-07-15** | Target + walidacja | `pvPower`, resolver `PVEnergyTotal`, sync wieczorny 22:42 |
| **2026-07-16** | **Korekta operacyjna** | Warstwa intraday nad RF — **własny algorytm**, bez zewnętrznych pluginów |
| **2026-07-16** | Bateria G12w | `battery_advisor`, job 16:00, progi w `.env.example` |

### Problem operacyjny (16.07, rano)

| | Wartość |
|---|--------|
| Prognoza 5:00 (model raw) | ~26.9 kWh / dzień |
| Realizacja do ~9:00 | ~2.1 kWh (**~22%** tempa) |
| Przyczyna | Pochmurny dzień + prognoza pogody z rana nie łapie chwilowych przejaśnień |

**Wniosek:** model offline (Test MAE ~0.66 kWh/h) jest OK; słabość leży w **warstwie operacyjnej** — brak feedbacku z falownika w trakcie dnia.

---

## 2. Korekta operacyjna (nowa warstwa)

### Architektura (3 poziomy)

```
┌─────────────────────────────────────────────────────────────┐
│  Poziom 3 — Ranking AGD (konserwatywny)                     │
│  predicted_kwh_conservative = adjusted × margines (0.85)     │
└───────────────────────────────┬─────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────┐
│  Poziom 2 — Korekta operacyjna (NOWE, lipiec 2026)           │
│  • intraday: skala z FoxESS rano / ML rano (blend 65%)       │
│  • profil błędu: median actual/predicted per godzina         │
│  • chmury: cloud_cover > 70% → ×0.6                         │
└───────────────────────────────┬─────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────┐
│  Poziom 1 — Model ML (bez zmian)                             │
│  Random Forest, 16 cech, target pvPower → predicted_kwh_raw  │
└─────────────────────────────────────────────────────────────┘
```

### Pliki (własna implementacja)

| Moduł | Rola |
|-------|------|
| [`src/models/intraday_forecast_adjust.py`](../src/models/intraday_forecast_adjust.py) | Skalowanie reszty dnia, heurystyka chmur, ranking konserwatywny |
| [`src/models/forecast_error_profile.py`](../src/models/forecast_error_profile.py) | Profil błędu z `forecast_validation_hourly.csv` |
| [`scripts/analysis/build_forecast_error_profile.py`](../scripts/analysis/build_forecast_error_profile.py) | Ręczne odświeżenie profilu |
| [`mlops/evening_closeout.py`](../mlops/evening_closeout.py) | Po walidacji wieczornej → rebuild profilu (krok `[5]`) |

### Kolumny wyjściowe (`pv_forecast.csv`)

| Kolumna | Znaczenie |
|---------|-----------|
| `predicted_kwh_raw` | Surowa prognoza RF |
| `predicted_kwh` | FoxESS (minione godz.) lub raw (przyszłe) |
| `predicted_kwh_adjusted` | **Prognoza operacyjna** (po korekcie) |
| `predicted_kwh_conservative` | Do rankingu urządzeń (z marginesem) |
| `adjust_intraday_scale` | Współczynnik z porównania rano |
| `adjust_cloudy_factor` | 0.6 przy wysokim zachmurzeniu |
| `adjust_profile_factor` | Korekta per godzina z historii błędów |

### Konfiguracja (`.env.example`)

```bash
# FORECAST_OPERATIONAL_ADJUST=1
# FORECAST_INTRADAY_BLEND=0.65
# FORECAST_CLOUDY_THRESHOLD_PCT=70
# FORECAST_CLOUDY_EXTRA_SCALE=0.6
```

Wyłączenie korekty (porównanie z surowym ML):

```bash
python scripts/forecast_pv.py --no-operational-adjust
```

### Przykład (16.07, przed sync 12:00)

| Wariant | Suma dzienna |
|---------|--------------|
| Model raw | ~26.0 kWh |
| Operacyjna (chmury) | ~20.2 kWh |
| Po sync 12:00 + intraday | skala z FoxESS 5–11h (np. 2.1/9.4 → ~0.68) |

---

## 3. Pętla uczenia operacyjnego

```mermaid
flowchart LR
    AM[5:00 forecast daily] --> MID[12:00 sync + forecast midday]
    MID --> PM[16:00 peak + battery]
    PM --> EV[22:42 evening_closeout]
    EV --> VAL[forecast_validation.csv]
    VAL --> PROF[forecast_error_profile.csv]
    PROF --> NEXT[Następny dzień: korekta w forecast_pv]
```

| Krok | Plik / skrypt |
|------|----------------|
| Archiwum prognoz | `data/processed/forecasts/pv_forecast_*.csv` |
| Walidacja dzienna | `forecast_validation.csv` |
| Walidacja godzinowa | `forecast_validation_hourly.csv` |
| Profil błędu | `forecast_error_profile.csv` |

---

## 4. Uzasadnienie prawne i metodologiczne (obrona / prezentacja)

| Pytanie | Odpowiedź |
|---------|-----------|
| Czy kopiujecie kod z HA / foxess_em? | **Nie** — tylko własna implementacja na Waszych danych |
| Skąd pomysł intraday? | Standard inżynierii prognoz (feedback z pomiaru); algorytm i parametry **autorskie** |
| Zależności zewnętrzne | `foxesscloud` (MIT, pip), Open-Meteo API, scikit-learn |
| Co jest wkładem naukowym? | **Hybrydowy model ML + korekta operacyjna** na pomiarach falownika w czasie rzeczywistym |

---

## 5. Slajdy prezentacji — proponowana struktura

### Slajd A: „Ewolucja prognozy” (oś czasu)

1. **Faza 1** — RF offline, 16 cech, MAE test 0.66 kWh/h  
2. **Faza 2** (07-13) — prognoza hybrydowa: archiwum + FoxESS dla minionych godzin  
3. **Faza 3** (07-16) — **korekta operacyjna intraday** + profil błędu + ranking konserwatywny  

*(Wykres: `forecast_history.csv` — daily vs midday vs adjusted dla 14–16.07)*

### Slajd B: Diagram 3 poziomów

Użyj diagramu z §2 (Poziom 1 → 2 → 3). Podpis: *„ML nie zastępujemy — dokładamy warstwę operacyjną”*.

### Slajd C: Case study 16.07 (pochmurny dzień)

| Godzina | Model raw | FoxESS / obserwacja |
|---------|-----------|---------------------|
| 9:00 | ~3.7 kWh/h | ~1.4 kW chwilowo |
| Do 9:00 skumul. | ~9.4 kWh prognoza | **2.1 kWh** real |

Wniosek na slajdzie: *offline MAE ≠ błąd operacyjny przy zmiennej pogodzie* → uzasadnienie korekty.

### Slajd D: Walidacja wieczorna

- Tabela z `forecast_validation.csv` (14.07: 31.0 vs 25.1; 15.07: 10.9 vs 10.05)  
- Profil błędu godzinowego z `forecast_error_profile.csv`  
- Commit wieczorny: sync + walidacja + rebuild profilu

### Slajd E: Harmonogram MLOps (aktualny)

| Czas | Job |
|------|-----|
| 5:00 | sync + forecast daily + battery morning |
| 12:00 | sync + forecast midday + **intraday adjust** |
| 16:00 | peak + battery |
| 22:42 | sync + walidacja + profil błędu |

### Slajd F: Co dalej (roadmap, opcjonalnie)

- Ensemble Open-Meteo (własny fetcher)  
- Retrening co tydzień z nowymi dniami pochmurnymi  
- Moduł sterowania baterią (ForceCharge) — osobny etap  

---

## 6. Gdzie zaktualizować dokumentację

| Dokument | Co dopisać |
|----------|------------|
| [03_ZALOZENIA_I_DECYZJE.md](03_ZALOZENIA_I_DECYZJE.md) | §7.5 Korekta operacyjna, elevator pitch pkt 6 |
| [02_ML_predykcja_PV.md](02_ML_predykcja_PV.md) | §5.5 Warstwa operacyjna |
| [README.md](../README.md) | Link do tego UPDATE, status w tabeli |
| Notebook `02_ML_predykcja_PV.ipynb` | Opcjonalna komórka: porównanie raw vs adjusted |

---

## 7. Komendy weryfikacyjne

```bash
# Prognoza z korektą (domyślnie)
python scripts/forecast_pv.py --run-label manual

# Surowy ML (bez korekty)
python scripts/forecast_pv.py --no-operational-adjust

# Profil błędu
python scripts/build_forecast_error_profile.py

# Smoke test (sekcja [3])
python scripts/test_pv_pipeline_smoke.py --day 2026-07-15
```

---

*Autor aktualizacji: pipeline MLOps · data: 2026-07-16 · commit: cd1caa2*
