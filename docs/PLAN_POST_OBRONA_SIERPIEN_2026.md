# Plan doskonalenia modelu — po obronie (sierpień+ 2026)

**Data:** 2026-08-27  
**Stan:** po obronie · model RF16 + ICON · MAPE dual **11,0%** (n=29)  
**Cel:** produkcja prywatna — zmniejszyć duże błędy (>20%) na jasne dni clearingowe  

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

## Strategia — dwie fazy

### **Faza 1: Ensemble ICON+UKMO** (priorytet 1, szybkie)

**Cel:** naprawa źródła błędu — uśrednienie ICON+UKMO zmniejszy bias ICON.

**Przykład:**
```python
# 23.08
icon_cloud = 44%  # za pesymistyczny
ukmo_cloud = 7%   # był jaśniejszy
ensemble = (44 + 7) / 2 = 25.5%  # vs Accu 26% ✅ bliżej!
```

**Implementacja:**
1. Dodać `get_ukmo_forecast()` obok ICON (Open-Meteo ma UKMO free)
2. Uśrednić GHI/cloud/rad przed `predict()`
3. Retrain RF na ensemble weather (weekly jak teraz)
4. Backtest na 23–24–26.08: czy błąd <15% zamiast >20%?

**Czas:** 1–2 dni

**Gate:** MAPE dual spadnie z 11% → ~8–9% (target)

---

### **Faza 2: LSTM z sekwencją godzinową** (priorytet 2, jeśli Faza 1 nie wystarcza)

**Cel:** złapanie **sekwencji clearing** (RF widzi tylko daily agregat).

**Przykład 26.08:**
- Rano: GHI niskie (chmury)
- 11:00: spike 1,52 kW (prześwit)
- PM: clearing → 21,1 kWh

LSTM z `GHI[6–12h]` sekwencją mógłby przewidzieć „GHI rośnie 3h z rzędu = clearing".

**Wymaga:**
- Godzinowy forecast (nie daily) — sprawdzić czy Open-Meteo ma `hourly`
- GPU (opcjonalnie, przyspieszy)
- Research time (~1–2 tygodnie): tuning, porównanie z RF, ablacja

**Czas:** 1–2 tygodnie

**Gate:** MAPE dual spadnie poniżej 8% (jeśli ensemble dał ~8–9%, LSTM ma dać <8%)

---

## Co NIE robić (z sugestii Gemini)

| Pomysł | Status | Dlaczego |
|--------|--------|----------|
| **Lagi NWP** (hour_ago, day_ago) | ✅ Masz XGB+TS shadow (8 cech TS) | Już zaimplementowane; nie primary |
| **Osobne modele zima/lato** | ❌ Zły pomysł | ML przewiduje PV (fizyka); strategia baterii to operacyjne |
| **Kara za undershoot zimą** | ⚠️ Trudne w RF | Wymaga XGBoost custom loss; lepiej ensemble NWP |
| **Bezpiecznik baterii** | ✅ Masz w battery_advisor | Zwiększ próg 18→20 kWh na jesień (operacyjne, nie ML) |

---

## Harmonogram wdrożenia

### Faza 1: Ensemble ICON+UKMO (priorytet teraz)

| Krok | Co | Gdzie | Status |
|------|-----|-------|--------|
| **E1.1** | Sprawdzić dostęp Open-Meteo UKMO (free tier) | API check | `[ ]` |
| **E1.2** | Dodać `get_ukmo_forecast()` w `weather/openmeteo_client.py` | kod | `[ ]` |
| **E1.3** | Uśrednić ICON+UKMO przed predict: `ensemble_ghi = (icon + ukmo) / 2` | `pv_hourly_predictor.py` | `[ ]` |
| **E1.4** | Retrain RF na ensemble weather (weekly jak teraz) | `train_dual_weekly.sh` | `[ ]` |
| **E1.5** | Backtest 23–24–26.08: czy błąd <15%? | oneshot / manual | `[ ]` |
| **E1.6** | Live closeouty 5–7 dni z ensemble | zbieranie | `[ ]` |
| **E1.7** | Gate: MAPE dual ≤9% → ACCEPT; >9% → Faza 2 | decyzja | `[ ]` |

**Czas:** 1–2 dni roboty + 5–7 dni closeoutów = ~tydzień total

---

### Faza 2: LSTM (tylko jeśli E1.7 REJECT)

| Krok | Co | Gdzie | Status |
|------|-----|-------|--------|
| **L2.1** | Sprawdzić Open-Meteo `hourly` ICON/UKMO (sekwencja 0–23h) | API check | `[ ]` park |
| **L2.2** | Cechy LSTM: `GHI[t-24:t]`, `cloud[t-24:t]` → `PV[t+1]` | research | `[ ]` park |
| **L2.3** | Train LSTM vs RF (ten sam split 80/20) | `train_lstm_ts.py` | `[ ]` park |
| **L2.4** | Porównanie Test MAE: LSTM vs RF vs ensemble | gate | `[ ]` park |
| **L2.5** | Jeśli LSTM > RF: live closeouty 5–7 dni | zbieranie | `[ ]` park |
| **L2.6** | Gate: MAPE dual <8% → ACCEPT | decyzja | `[ ]` park |

**Czas:** 1–2 tygodnie research + 5–7 dni closeoutów

**Priorytet:** park do Faza 1 wyników

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

## TODO (checklist startowy)

| ID | Status | Zadanie |
|----|--------|---------|
| **E1.1** | `[ ]` | Dostęp Open-Meteo UKMO (free tier check) |
| **E1.2** | `[ ]` | Kod: `get_ukmo_forecast()` + ensemble averaging |
| **E1.3** | `[ ]` | Retrain RF na ensemble |
| **E1.4** | `[ ]` | Backtest 23–24–26.08 (czy <15% błąd?) |
| **E1.5** | `[ ]` | Live closeouty 5–7 dni |
| **E1.6** | `[ ]` | Gate E1.7: MAPE ≤9% → ACCEPT/REJECT |
| **L2.x** | `[ ]` | Faza 2 park do E1.7 |

---

*Plan post-obrona — 27.08.2026 — doskonalenie dla produkcji prywatnej.*
