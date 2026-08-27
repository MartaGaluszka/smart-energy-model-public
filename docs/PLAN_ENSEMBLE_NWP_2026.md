# Plan wdrożenia — Ensemble NWP (ICON+UKMO)

**Data start:** 2026-08-27  
**Stan:** po obronie · model RF16 + ICON · MAPE dual **11,0%** (n=29)  
**Cel:** produkcja prywatna — zmniejszyć duże błędy (>20%) na jasne dni clearingowe  
**Zakres:** Faza 1 (ensemble) — **start teraz** · Faza 2 (LSTM) — backlog (≥1 miesiąc lub 2 lata danych)

Powiązane: [`PLAN_T1_T2_LIPIEC_2026.md`](PLAN_T1_T2_LIPIEC_2026.md) · [`STATUS_ML_MLOPS.md`](STATUS_ML_MLOPS.md) · [`PLAN_BATERIA_JESIEN_ZIMA_2026.md`](PLAN_BATERIA_JESIEN_ZIMA_2026.md)

---

## Problem do rozwiązania

### Symptom: duże błędy na jasne dni (23–26.08)

| Dzień | Accu | ICON cloud | Actual | RF | Δ | Przyczyna |
|-------|------|-----------|--------|-----|---|-----------|
| **23.08** | jasność **9** / 26% | ~**44%** | **35,2** | 28,6 | **−19%** | ICON za chmurny |
| **24.08** | jasność **9** / 15% | ~**58–67%** | **35,1** | 26,6 | **−24%** | ICON za chmurny |
| **26.08** | jasność **9** / 31% | ~**97%** (rano) | **21,1** | 12,5 | **−41%** | ICON trzymał dzień szary; clearing PM |

**Wspólna przyczyna:** ICON systematycznie **zaniża jasne dni** → GHI za niskie → RF dostaje złe dane → undershoot.

**Diagnoza:** problem w **źródle NWP** (ICON), nie w ML. UKMO był bliżej (23–24: cloud ~6–7% vs ICON 44–67%).

---

## Faza 1: Ensemble ICON+UKMO — **START TERAZ**

**Cel:** naprawa źródła błędu — uśrednienie ICON+UKMO zmniejszy bias ICON.

**Przykład efektu:**
```python
# 23.08 — dzień z błędem −19%
icon_cloud = 44%  # za pesymistyczny
ukmo_cloud = 7%   # był jaśniejszy
ensemble = (44 + 7) / 2 = 25.5%  # vs Accu 26% ✅ bliżej!
# → RF z ensemble GHI da lepszą prognozę
```

**Czas total:** ~7–10 dni (1–2 dni kod + 5–7 dni live closeouty)

**Gate:** MAPE dual ≤9% → ACCEPT; >9% → rozważyć Fazę 2 (za ≥1 miesiąc)

---

## Taski Faza 1 — szczegółowo (kolejność wykonania)

### **Task 1: Weryfikacja dostępu UKMO API**

**ID:** E1.1  
**Czas:** 15–30 min  
**Opis:** Sprawdzić czy Open-Meteo free tier ma UKMO `ukmo_seamless` i zwraca sensowne dane.

**Kroki:**
1. Przeczytaj docs Open-Meteo: https://open-meteo.com/en/docs
2. Test request na dzisiaj (27.08):
   ```bash
   curl "https://api.open-meteo.com/v1/forecast?latitude=50.06&longitude=19.94&hourly=cloud_cover,temperature_2m,shortwave_radiation&models=ukmo_seamless"
   ```
3. Sprawdź czy zwraca JSON z danymi (nie 403/404)
4. Porównaj UKMO vs ICON cloud dla dziś — czy są różnice?

**Output:** ✅ UKMO działa / ❌ UKMO niedostępne (wtedy plan B: tylko ECMWF płatny)

---

### **Task 2: Kod — funkcja get_ukmo_forecast()**

**ID:** E1.2  
**Czas:** 1–2 h  
**Opis:** Dodać pobieranie UKMO obok ICON w `weather/openmeteo_client.py`.

**Kroki:**
1. Otwórz `src/weather/openmeteo_client.py`
2. Znajdź funkcję `get_icon_forecast()` (lub podobną)
3. Skopiuj i dostosuj jako `get_ukmo_forecast()`:
   - Model: `ukmo_seamless` zamiast `icon_seamless`
   - Te same parametry: `cloud_cover`, `shortwave_radiation`, `temperature_2m`, itd.
4. Test ręczny:
   ```python
   from src.weather.openmeteo_client import get_ukmo_forecast
   ukmo = get_ukmo_forecast(lat=50.06, lon=19.94, date='2026-08-27')
   print(ukmo['cloud_cover'])  # sprawdź czy nie NaN
   ```

**Output:** Funkcja `get_ukmo_forecast()` zwraca DataFrame z pogodą UKMO

---

### **Task 3: Kod — uśrednianie ensemble przed predict()**

**ID:** E1.3  
**Czas:** 2–3 h  
**Opis:** Zmienić pipeline predykcji żeby brał średnią ICON+UKMO zamiast tylko ICON.

**Kroki:**
1. Otwórz `scripts/forecast_pv.py` (lub gdzie jest główna predykcja)
2. Znajdź linię:
   ```python
   weather = get_icon_forecast(lat, lon, date)
   ```
3. Zmień na:
   ```python
   icon = get_icon_forecast(lat, lon, date)
   ukmo = get_ukmo_forecast(lat, lon, date)
   
   # Ensemble: średnia ICON+UKMO
   weather = icon.copy()
   for col in ['cloud_cover_pct', 'radiation_wm2', 'temp_c']:
       if col in ukmo.columns:
           weather[col] = (icon[col] + ukmo[col]) / 2
   ```
4. Test smoke: czy `predict()` nie crashuje?
5. Dodaj flag `.env`: `WEATHER_ENSEMBLE_UKMO=1` (domyślnie OFF, żeby nie zepsuć current)

**Output:** Predykcja używa ensemble ICON+UKMO (za flagą)

---

### **Task 4: Backtest — czy ensemble poprawia 23–24–26.08?**

**ID:** E1.4  
**Czas:** 1–2 h  
**Opis:** Oneshot na 3 złe dni — sprawdzić czy ensemble daje błąd <15% zamiast >20%.

**Kroki:**
1. Skrypt oneshot (lub ręcznie):
   ```bash
   WEATHER_ENSEMBLE_UKMO=1 python scripts/analysis/oneshot_ensemble_test.py \
       --dates 2026-08-23,2026-08-24,2026-08-26
   ```
2. Porównaj:
   - Baseline ICON: actual vs RF (23: 35.2 vs 28.6, 24: 35.1 vs 26.6, 26: 21.1 vs 12.5)
   - Ensemble ICON+UKMO: actual vs RF (target: błąd <15%)
3. Tabela wyników:
   | Dzień | Actual | RF ICON | Błąd ICON | RF Ensemble | Błąd Ensemble | Poprawa |
   |-------|--------|---------|-----------|-------------|---------------|---------|
   | 23.08 | 35.2 | 28.6 | −19% | ? | ? | ? |

**Output:** ✅ Poprawa ≥30% błędu (np. −19% → −12%) / ❌ Brak poprawy (wtedy REVIEW strategii)

---

### **Task 5: Retrain RF na ensemble weather**

**ID:** E1.5  
**Czas:** 30 min train + overnight  
**Opis:** Przetrenować RF na ensemble ICON+UKMO (zamiast tylko ICON).

**Kroki:**
1. Włącz flag w treningu:
   ```bash
   WEATHER_ENSEMBLE_UKMO=1 python scripts/train/train_dual_weekly.sh
   ```
2. Sprawdź Test MAE vs poprzedni:
   - Poprzedni (ICON): 0.658
   - Ensemble: ? (target: ≤0.65 albo bez regresji)
3. Zapisz nowy `.joblib`:
   ```bash
   cp models/pv_hourly_model.joblib models/pv_hourly_model_ensemble.joblib
   ```
4. **Nie podmieniaj produkcji** — to shadow test

**Output:** `pv_hourly_model_ensemble.joblib` (shadow) + Test MAE

---

### **Task 6: Live closeouty 5–7 dni**

**ID:** E1.6  
**Czas:** 5–7 dni (pasywne czekanie)  
**Opis:** Zbierać closeouty z ensemble shadow vs ICON primary vs app.

**Kroki:**
1. Dodaj do launchd shadow forecast:
   ```bash
   # 05:00 i 12:00: dwie prognozy
   # 1) primary ICON (jak teraz)
   # 2) shadow ensemble (nowy)
   ```
2. Tabela w `forecast_validation.csv`:
   | Dzień | App | RF ICON | RF Ensemble | MAPE ICON | MAPE Ensemble |
   |-------|-----|---------|-------------|-----------|---------------|
   | 28.08 | ? | ? | ? | ? | ? |
3. Zbierz ≥5 dni różnych typów (jasne, mix, pochmurne)

**Output:** Tabela 5–7 closeoutów ICON vs Ensemble

---

### **Task 7: Gate — decyzja ACCEPT/REJECT**

**ID:** E1.7  
**Czas:** 1 h analiza  
**Opis:** Porównać MAPE dual ICON vs Ensemble — czy ≤9%?

**Kroki:**
1. Policz MAPE dla obu:
   ```python
   mape_icon = mean(|app - rf_icon| / app) * 100
   mape_ensemble = mean(|app - rf_ensemble| / app) * 100
   ```
2. Sprawdź na złe dni (>20% błąd):
   - ICON: 3/29 dni (23,24,26.08)
   - Ensemble: ? (target: <2)

**Gate:**
- **ACCEPT:** MAPE ensemble ≤9% **i** błędy >20% spadły
- **REVIEW:** MAPE 9–10% — mała poprawa, rozważyć Fazę 2 za miesiąc
- **REJECT:** MAPE >10% — ensemble nie pomaga, problem gdzie indziej

**Output:** Decyzja ACCEPT/REVIEW/REJECT

---

### **Task 8: Wdrożenie do produkcji (jeśli ACCEPT)**

**ID:** E1.8  
**Czas:** 30 min  
**Opis:** Podmienić primary ICON → Ensemble.

**Kroki:**
1. W `.env`: `WEATHER_ENSEMBLE_UKMO=1`
2. W launchd: primary używa `pv_hourly_model_ensemble.joblib`
3. Commit:
   ```bash
   git commit -m "feat(ml): ensemble ICON+UKMO jako primary (gate ACCEPT, MAPE 11→X%)"
   ```
4. Restart launchd / czekać na najbliższy 05:00

**Output:** Produkcja używa ensemble

---

## Faza 2: LSTM — **BACKLOG** (≥1 miesiąc lub 2 lata danych)

### **Kiedy wrócić do Fazy 2?**

**Warunki startu:**
1. **Ensemble REVIEW/REJECT** (MAPE >9%) — wtedy priorytet, za ≥1 miesiąc
2. **Dane:** ≥2 lata (obecnie ~15 miesięcy) — LSTM potrzebuje więcej próbek
3. **Czas:** research ~1–2 tygodnie gdy oba warunki spełnione

**Cel:** złapanie **sekwencji clearing** (RF widzi tylko daily agregat).

**Przykład 26.08:**
- Rano: GHI niskie (chmury)
- 11:00: spike 1,52 kW (prześwit)
- PM: clearing → 21,1 kWh

LSTM z `GHI[6–12h]` sekwencją mógłby przewidzieć „GHI rośnie 3h z rzędu = clearing".

**Wymaga:**
- Godzinowy forecast (nie daily) — Open-Meteo ma `hourly`
- GPU (opcjonalnie, przyspieszy)
- ≥2 lata danych (obecnie 15 miesięcy)

**Gate:** MAPE dual <8%

**Status:** park do IX 2026+ lub decision po E1.7

---

## Co NIE robić (z sugestii Gemini)

| Pomysł | Status | Dlaczego |
|--------|--------|----------|
| **Lagi NWP** (hour_ago, day_ago) | ✅ Masz XGB+TS shadow (8 cech TS) | Już zaimplementowane; nie primary |
| **Osobne modele zima/lato** | ❌ Zły pomysł | ML przewiduje PV (fizyka); strategia baterii to operacyjne |
| **Kara za undershoot zimą** | ⚠️ Trudne w RF | Wymaga XGBoost custom loss; lepiej ensemble NWP |
| **Bezpiecznik baterii** | ✅ Masz w battery_advisor | Zwiększ próg 18→20 kWh na jesień (operacyjne, nie ML) |

---

## Harmonogram — start Faza 1 (teraz)

| Task | ID | Czas | Zależności | Status |
|------|-----|------|------------|--------|
| Weryfikacja UKMO API | E1.1 | 15–30 min | — | `[ ]` **START** |
| Kod `get_ukmo_forecast()` | E1.2 | 1–2 h | E1.1 PASS | `[ ]` |
| Ensemble averaging | E1.3 | 2–3 h | E1.2 | `[ ]` |
| Backtest 3 dni | E1.4 | 1–2 h | E1.3 | `[ ]` |
| Retrain ensemble | E1.5 | 30 min + overnight | E1.4 OK | `[ ]` |
| Live closeouty | E1.6 | 5–7 dni pasywne | E1.5 | `[ ]` |
| Gate decyzja | E1.7 | 1 h | E1.6 | `[ ]` |
| Wdrożenie (jeśli ACCEPT) | E1.8 | 30 min | E1.7 ACCEPT | `[ ]` |

**Czas total:** ~7–10 dni (1–2 dni aktywnej roboty + 5–7 dni czekania na closeouty)

**Next step:** Task E1.1 — sprawdź UKMO API (15 min)

---

## Co już masz (nie wymyślać od zera)

### ML
- **XGB+TS shadow** — 8 cech TS (lagi NWP + rolling) w `src/features/nwp_time_series.py`
- **CS4 shadow** — warstwy chmur + clearness
- **Weekly retrain** — `train_dual_weekly.sh` niedziela 04:30
- **Closeouty live** — `forecast_validation.csv` z MAPE

### Bateria (operacyjne, nie ML)
- **Battery advisor** — `evaluate_charge_tonight_cloudy()` (22:00 FC gdy SoC<50% i PV jutro <18)
- **G12w okna** — tanie 22–6, 13–15
- **Plan baterii jesień/zima** — [`PLAN_BATERIA_JESIEN_ZIMA_2026.md`](PLAN_BATERIA_JESIEN_ZIMA_2026.md)

---

## Operacyjne (nie ML, ale ważne)

| ID | Co | Gdzie | Kiedy |
|----|-----|-------|-------|
| **OP.1** | Zwiększ `BATTERY_CLOUDY_DAY_PV_KWH` 18→20 na jesień | `.env` / battery_advisor | IX 2026 |
| **OP.2** | Error analysis po miesiącach (MAPE VII vs VIII vs IX) | diagnostyka | po E1.7 |
| **OP.3** | Alert SoC@16:00 <50% → sugestia FC 13–15 | mobile / notifications | jesień (BAT.3) |

---

## Metryki sukcesu

| Metryka | Baseline (27.07–24.08) | Target po Faza 1 | Target po Faza 2 |
|---------|------------------------|------------------|------------------|
| MAPE dual raw 5:00 | **11,0%** (n=29) | **≤9%** | **<8%** |
| Dni z błędem >20% | **3/29** (23,24,26.08) | **<2/miesiąc** | **<1/miesiąc** |
| Undershoot jasne dni | −19 do −41% | **−10 do −15%** | **−5 to −10%** |

---

## Decyzja: co dalej?

**Po E1.7 (ensemble live closeouty):**

| Wynik MAPE dual | Decyzja |
|-----------------|---------|
| **≤8%** | ACCEPT ensemble; park LSTM; focus operacyjny (bateria jesień) |
| **8–9%** | ACCEPT ensemble; opcjonalnie L2 research w tle |
| **>9%** | Faza 2 LSTM — problem wymaga sekwencji, nie tylko averaging |

---

## Quick start — pierwsze kroki

**Dzisiaj (27.08):**
1. Task E1.1 (15 min) — test UKMO API
2. Task E1.2 (1–2 h) — kod `get_ukmo_forecast()`

**Jutro (28.08):**
3. Task E1.3 (2–3 h) — ensemble averaging
4. Task E1.4 (1–2 h) — backtest 3 dni

**Pojutrze (29.08):**
5. Task E1.5 (30 min) — retrain ensemble
6. Task E1.6 start — czekać 5–7 dni na closeouty

**~3–5.09:**
7. Task E1.7 (1 h) — gate decyzja
8. Task E1.8 (30 min) — wdrożenie (jeśli ACCEPT)

---

*Plan wdrożenia ensemble NWP — 27.08.2026 — Faza 1 start, Faza 2 backlog (≥1 miesiąc).*
