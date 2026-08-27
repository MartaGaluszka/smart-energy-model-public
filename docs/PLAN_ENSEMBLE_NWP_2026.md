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
   curl "https://api.open-meteo.com/v1/forecast?latitude=49.98&longitude=19.9&hourly=cloud_cover,temperature_2m,shortwave_radiation&models=ukmo_seamless"
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
   ukmo = get_ukmo_forecast(lat=49.98, lon=19.9, date='2026-08-27')
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

## Harmonogram Faza 1 — status 27.08.2026

| Task | ID | Czas | Status | Data | Commit |
|------|-----|------|--------|------|--------|
| Weryfikacja UKMO API | E1.1 | 15 min | `[x]` DONE | 27.08 | — |
| Kod `get_ukmo_forecast()` | E1.2 | 1 h | `[x]` DONE | 27.08 | fc15009b |
| Ensemble averaging | E1.3 | 30 min | `[x]` DONE | 27.08 | 3d6daa05 |
| Backtest 3 dni | E1.4 | 1 h | `[x]` DONE | 27.08 | 5243886f |
| Retrain ensemble | E1.5 | — | `[x]` DOC | 27.08 | 290b8238 |
| Live closeouty | E1.6 | 5–7 dni | `[ ]` DEFER | IX 2026 | — |
| Gate decyzja | E1.7 | 1 h | `[ ]` DEFER | IX 2026 | — |
| Wdrożenie (jeśli ACCEPT) | E1.8 | 30 min | `[ ]` DEFER | IX 2026 | — |

**Status 27.08:** 5/8 tasków DONE · Faza 1 kod gotowy · backtest +3.9pp poprawa

**Decyzja:** E1.6–E1.8 defer do IX 2026 (≥30 dni danych) · focus operacyjny (paper-trade routing)

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

## Następne kroki — Quick test 28–31.08 ⭐

**Decyzja:** Nie czekać do IX (warunki jesień ≠ lato) — test routing **TERAZ** (koniec sierpnia).

### **Setup dzisiaj (27.08, 10 min)**

Dodaj do launchd daily (05:00 + 12:00):

```bash
# mlops/launchd_daily_forecast.sh

# 1) PRIMARY ICON (baseline)
python mlops/forecast_pv.py --sync --out data/processed/pv_forecast.csv

# 2) SHADOW CS4 (już jest)
python mlops/forecast_pv.py --model-path models/pv_hourly_model_cs4.joblib \
  --out data/processed/pv_forecast_cs4.csv

# 3) SHADOW ENSEMBLE (nowy)
WEATHER_ENSEMBLE_UKMO=1 python mlops/forecast_pv.py --sync \
  --out data/processed/pv_forecast_ensemble.csv

# 4) ROUTING DECISION (nowy)
python scripts/analysis/routing_decision.py --date tomorrow
```

**Skrypt routing:** `scripts/analysis/routing_decision.py` — decyzja jasny/pochmurny ✅

---

### **Test 28–31.08 (4 dni, pasywne zbieranie)**

| Dzień | Forecast cloud | Regime | Pick | Zbierz closeout |
|-------|----------------|--------|------|-----------------|
| **28.08** | **54.4%** | pochmurny | **CS4** | actual, ICON, ensemble, CS4 |
| **29.08** | ? | ? | ? | j.w. |
| **30.08** | ? | ? | ? | j.w. |
| **31.08** | ? | ? | ? | j.w. |

**Routing:** jasny (cloud <30%) → ensemble; pochmurny → CS4

**Dokumentacja:** [`NOTATKA_TEST_ROUTING_28-31_08.md`](NOTATKA_TEST_ROUTING_28-31_08.md)

---

### **Gate 01.09 (pon, 1h)**

Analiza 4 dni:
- MAPE routing vs MAPE ICON baseline
- Błędy >20% (routing vs baseline 3/29)
- Średni błąd routing < ICON?

**Decyzja:**
- **ACCEPT:** routing ≤ ICON + błędy spadły → wdrożenie 02.09
- **REVIEW:** routing ≈ ICON → zbierać więcej (IX)
- **REJECT:** routing > ICON → zostać przy ICON

---

### **Wdrożenie 02.09 (wt, 30 min) — jeśli ACCEPT**

1. Flag `.env`: `ROUTING_ENABLE=1`
2. Launchd: użyj routing_pick.csv do wyboru ensemble vs CS4
3. Monitor 3–7 dni closeoutów

---

## Backup plan — IX 2026 (jeśli 01.09 REVIEW)

### **Setup zbieranie ensemble (28.08 → IX)**

**Launchd:** codzienne zbieranie ensemble forecast (shadow, nie prod):

```bash
# mlops/launchd_daily_forecast.sh
# Po primary ICON:
WEATHER_ENSEMBLE_UKMO=1 python mlops/forecast_pv.py --sync \
  --out data/processed/pv_forecast_ensemble.csv \
  --run-label daily-ensemble-shadow
```

**Czas:** 5 min setup · zbiera od 28.08 → IX 2026 (≥30 dni)

---

### **Wdrożenie IX 2026 (gdy ≥30 dni danych)**

| Krok | Co | Kiedy |
|------|-----|-------|
| **IX.1** | Retrain RF na ensemble (≥30 dni) | ~28.09–01.10 |
| **IX.2** | Gate: MAPE ensemble ≤9%? | ~05.10 |
| **IX.3** | Jeśli ACCEPT: wdrożenie ensemble primary | ~06.10 |
| **IX.4** | Jeśli REVIEW: routing conditional (jasny/pochmurny) | +1 tydzień |

---

### **Routing conditional (po IX.3 lub IX.4)**

**Task R1: Jasny → ensemble, pochmurny → CS4**

```python
# mlops/forecast_pv.py
cloud_avg = weather['cloud_cover_pct'].mean()

if cloud_avg < 30:  # jasny
    model = "ensemble"  # ICON+UKMO
else:  # pochmurny
    model = "CS4"       # więcej warstw chmur
```

**Implementacja:**
1. Reguła decyzyjna (próg cloud/jasność) — 1h
2. Pipeline routing — 2h
3. Closeouty walidacja (5–7 dni) — pasywne
4. Gate: routing vs baseline — 1h

**Czas:** 3h kod + 5–7 dni closeoutów

**Warunki start:**
- Ensemble wdrożony (IX.3) **lub**
- Ensemble REVIEW (IX.4) — routing jako plan B

---

## Taski routing — szczegółowo

### **R1.1: Reguła decyzyjna**

Dodaj progi w `.env`:
```bash
ROUTING_CLEAR_CLOUD_MAX=30      # <30% = jasny
ROUTING_CLEAR_JASNOSC_MIN=7     # ≥7 Accu = jasny
ROUTING_ENABLE=0                # default OFF
```

### **R1.2: Pipeline routing**

`mlops/forecast_pv.py`:
```python
if os.getenv('ROUTING_ENABLE') == '1':
    cloud_avg = forecast['cloud_cover_pct'].mean()
    if cloud_avg < float(os.getenv('ROUTING_CLEAR_CLOUD_MAX', '30')):
        # Jasny → ensemble
        model_path = 'models/pv_hourly_model_ensemble.joblib'
        weather_ensemble = True
    else:
        # Pochmurny → CS4
        model_path = 'models/pv_hourly_model_cs4.joblib'
        weather_ensemble = False
```

### **R1.3: Closeouty walidacja**

Zbieraj:
| Dzień | Cloud | Reżim | Model | Actual | Pred | Błąd |
|-------|-------|-------|-------|--------|------|------|
| ... | 25% | jasny | ensemble | 35.2 | 30.0 | −14.8% |
| ... | 85% | pochmurny | CS4 | 11.8 | 11.4 | −3.4% |

### **R1.4: Gate routing**

Porównaj:
- **Baseline:** ensemble all days (lub ICON)
- **Routing:** conditional ensemble/CS4

**Target:** MAPE routing ≤ baseline −1pp

---

## Timeline visual (updated 27.08 ~13:50)

```
27.08 ─── 28–31.08 ── 01.09 ── 02.09 ────────── IX 2026 ─── X 2026
  │           │          │       │                  │          │
E1.1–E1.5   TEST     GATE    DEPLOY          Backup      R1 extend
  DONE    (4 dni)    (1h)    (30min)         (jeśli      (jeśli
  │           │          │       │            REVIEW)     potrzeba)
  │           │          │       │              │           │
  └─> setup  └─> close  └─> OK? └─> prod      │           │
      routing    outs        │                 │           │
                             │                 │           │
                        ACCEPT ───────────────┘           │
                             │                             │
                        REVIEW ─────> zbieraj IX ─────────┘
                                      (≥30 dni)
```

**Kluczowe daty:**
- **27.08:** Setup routing + ensemble ✅
- **28–31.08:** Test 4 dni (zbieranie)
- **01.09:** Gate decision (ACCEPT/REVIEW/REJECT)
- **02.09:** Wdrożenie jeśli ACCEPT
- **IX 2026:** Backup jeśli 01.09 REVIEW

---

*Plan aktualizacja — 27.08.2026 — E1.1–E1.5 DONE · Quick test 28–31.08 · IX backup*
