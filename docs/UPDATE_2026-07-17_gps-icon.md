# Aktualizacja produkcyjna — 2026-07-17

**Zakres:** GPS dach · Open-Meteo **ICON** · (metodologia) baseline rad×yield

Powiązane: [CHANGELOG_ML.md](CHANGELOG_ML.md) · [NOTATKA_RETRENINGI_LIPIEC_2026.md](NOTATKA_RETRENINGI_LIPIEC_2026.md) · [UPDATE_2026-07-16_korekta-operacyjna.md](UPDATE_2026-07-16_korekta-operacyjna.md) · [UPDATE_2026-07-18_target-pve.md](UPDATE_2026-07-18_target-pve.md)

---

## 1. Podsumowanie dnia

| Godz. (ok.) | Wdrożenie | Retrening | Test MAE* | Backup |
|-------------|-----------|-----------|-----------|--------|
| ~16:00 | **GPS dach** + refetch OM | tak | **0.652** | `pv_hourly_model_before_gps.joblib` |
| ~19:52 | **ICON** `icon_seamless` + refetch + retrening | tak | **0.666** | `pv_hourly_model_before_icon.joblib` |
| (docs) | Baseline rad×yield kalibrowany z train | nie (tylko metodologia) | — | — |

\*Target nadal **∫pvPower** (PVE dopiero 18.07).

---

## 2. GPS dach (~16:00)

**Przyczyna:** współrzędne pogody = Kraków-Observatorium (`50.0647, 19.9450`) zamiast dachu — ~**10 km** (inna komórka siatki chmur/radiacji).

| Parametr | Wartość |
|----------|---------|
| `WEATHER_LAT` / `LON` | GPS dachu (dokładne wartości tylko w lokalnym `.env`) |
| `PANEL_TILT_DEG` / `AZIMUTH` | 35° / 180° (S) |
| `PV_SYSTEM_KWP` | 5.39 (11 paneli) |
| `BATTERY_CAPACITY_KWH` | 10.36 |

**Pipeline:** `fetch_weather.py` (nadpisanie archiwum) → `train_hourly_model_tuning.py` (GridSearch min-gap).

| Metryka | Przed (Observatorium, model 16.07) | Po (GPS dach) | Δ |
|---------|-------------------------------------|---------------|---|
| Okno | expanding → 2026-07-15 | **2025-06-01 → 2026-07-16** | |
| Test MAE [kWh/h] | 0.661 | **0.652** | **−0.009** |
| Gap | 0.103 | **0.047** | **−0.056** |
| Test R² | 0.625 | **0.725** | **+0.100** |
| Daily MAE [kWh/d] | 3.52 | 4.44 | +0.92 *(inne okno)* |
| `min_samples_split` | 20 | **40** | |

Na **tej samej** nowej pogodzie (stary vs nowy `.joblib`): Test MAE 0.639 → 0.652 (Δ=+0.013) → protokół **REVIEW**; wdrożenie GPS i tak **ACCEPT** jako korekta źródła.

Artefakt: `models/pv_hourly_model.joblib`

---

## 3. ICON seamless (~19:52)

**Przyczyna:** `best_match` Open-Meteo wygładzał chmury (np. 09.07: cloud 53% / rad 6.2 vs ICON 86% / 4.3 przy PV app 17 kWh).

| Element | Wartość |
|---------|---------|
| `OPENMETEO_MODEL` | **icon_seamless** |
| Pipeline | refetch archive+forecast → retrening RF |
| Kod | `OpenMeteoClient` respektuje `OPENMETEO_MODEL` |

Sanity 5–20h: **09.07** cloud 86%, rad 4.29 · **12.07** cloud 96%, rad 1.42.

| Metryka | Baseline (GPS/`best_match` na pogodzie ICON) | Kandydat (retrening ICON) | Δ |
|---------|-----------------------------------------------|---------------------------|---|
| Test MAE [kWh/h] | 0.682 | **0.666** | **−0.016** |
| Gap | 0.026 | 0.086 | +0.060 |
| Test R² | 0.708 | **0.710** | +0.001 |
| Daily MAE [kWh/d] | 5.00 | **4.61** | **−0.40** |

**Decyzja: ACCEPT.**

### Operacyjnie (wieczór 17.07)

- Snapshoty 5:00 / 12:00 / 16:00 z **17.07** jeszcze na modelu **sprzed** ICON.
- Ostatni closeout w CSV = **16.07** (pre-ICON).
- Pierwszy pełny dzień ICON w live ≈ **18.07**.

Replay archiwum 14–16.07 (`icon_operational_replay_20260714_16.csv`): MAE vs ML ~4.0 (before_icon) → ~**3.7** (ICON) — optymistyczne (znana pogoda).

---

## 4. Baseline rad×yield (metodologia, bez zmiany prod)

| | Było | Jest |
|--|------|------|
| Yield dzienny | stała `0.17` | mediana/OLS `PV/radiacja` z **train** |
| Poprawa RF vs baseline (dzień CV) | ~74% (artefakt) | **~24%** (uczciwiej) |

**ACCEPT dokumentacyjny** — nie zmienia `.joblib`.

---

## 5. Rollback

```bash
# Przed ICON → GPS + best_match
cp models/pv_hourly_model_before_icon.joblib models/pv_hourly_model.joblib
# OPENMETEO_MODEL=best_match

# Przed GPS → Observatorium
cp models/pv_hourly_model_before_gps.joblib models/pv_hourly_model.joblib
```

---

*Wygenerowano z CHANGELOG / NOTATKA · konwencja `UPDATE_YYYY-MM-DD.md`*
