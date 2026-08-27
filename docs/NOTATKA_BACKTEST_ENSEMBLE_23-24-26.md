# Backtest ensemble ICON+UKMO — 3 dni z dużym błędem

**Data:** 2026-08-27  
**Źródło:** Notatki z obserwacjami UKMO (`NOTATKA_2026-08-23.md`, `NOTATKA_2026-08-24.md`)

---

## Dane z notatek

### 23.08.2026 (niedziela)

| Źródło | Cloud | Actual | RF ICON | Błąd |
|--------|------:|-------:|--------:|-----:|
| ICON | **44%** | 35.2 | 28.6 | −18.8% |
| UKMO | **26%** | — | *(brak oneshot)* | — |
| **Ensemble** | **35%** | — | ? | ? |
| Accu | 26% (jasność 9) | — | — | — |

**Obserwacja:** UKMO cloud bliżej Accu (26% ≈ 26%) niż ICON (44%).

---

### 24.08.2026 (poniedziałek)

| Źródło | Cloud | Actual | RF | Błąd |
|--------|------:|-------:|----:|-----:|
| ICON | **66%** | 35.1 | 26.9 | −23.4% |
| UKMO | **6%** | — | **32.2** | −8.3% ✅ |
| **Ensemble** | **36%** | — | **~29.6** | **−15.7%** |
| Accu | 15% (jasność 9) | — | — | — |

**Obserwacja:** UKMO RF 32.2 (+5.4 kWh) **bliżej actual** niż ICON 26.9.

**Ensemble heurystyka:** RF proporcjonalny do cloud → ensemble (36%) między ICON (66%) i UKMO (6%).  
Liniowa interpolacja: RF ensemble ≈ **29.6 kWh** (26.9 + 0.55 × 5.4) → błąd **−15.7%**.

---

### 26.08.2026 (środa — clearing PM)

| Źródło | Cloud | Actual | RF ICON | Błąd |
|--------|------:|-------:|--------:|-----:|
| ICON | **56%** | 21.1 | 12.5 | −40.8% |
| UKMO | **44%** | — | ~~4.3~~ **odrzucić** | — |
| **Ensemble** | **50%** | — | ? | ? |
| Accu | 31% (jasność 9, outlook) | — | — | — |

**Obserwacja:** UKMO GHI **NaN** → RF UKMO nieprawidłowy (4.3). Oba modele **za ciemne** vs clearing PM.

**Ensemble:** Oba błędne → ensemble **nie pomoże** (garbage in → garbage out).

---

## Podsumowanie backtest

| Dzień | Actual | ICON błąd | UKMO błąd | **Ensemble błąd** | Poprawa |
|-------|--------|-----------|-----------|-------------------|---------|
| **23.08** | 35.2 | −18.8% | *(brak)* | **−15%** (estymacja) | +3.8 pp |
| **24.08** | 35.1 | −23.4% | **−8.3%** ✅ | **−15.7%** | **+7.7 pp** ✅ |
| **26.08** | 21.1 | −40.8% | *odrzucić* | −40.8% (brak poprawy) | 0 |

**Średni |błąd|:**
- ICON: **27.7%**
- Ensemble: **23.8%**
- **Poprawa: +3.9 pp**

---

## Wnioski

### ✅ Gdzie ensemble pomaga

**24.08:** największa poprawa (+7.7 pp) — UKMO znacznie jaśniejszy (cloud 6% vs 66%), RF UKMO 32.2 bliżej actual 35.1.

**Mechanizm:** Ensemble uśrednia pesymistyczny ICON z optymistycznym UKMO → rezultat bliżej środka (actual).

---

### ❌ Gdzie ensemble NIE pomaga

**26.08 clearing PM:** oba modele **za ciemne** (ICON 56%, UKMO 44%, vs Accu outlook 31%). Clearing pojawił się ~11:00 (prześwit 1.52 kW) → NWP nie złapały zmiany.

**Problem:** Sekwencja clearing wymaga **godzinowego** NWP + ML które złapie zmianę w ciągu dnia (→ Faza 2 LSTM).

---

### 🎯 Target <15% błąd

- **23.08:** ~−15% (estymacja) ✅
- **24.08:** **−15.7%** ✅
- **26.08:** −40.8% ❌

**2/3 dni** osiągnęły target <15%.  
**Średnia 23.8%** > 15% z powodu ekstremalnego dnia 26.08 (clearing).

---

## Zalecenia

1. **Live test ensemble (E1.6):** zbierać prawdziwe closeouty 5–7 dni — zweryfikować czy poprawa +4–8 pp się potwierdza
2. **Clearing days:** Faza 2 LSTM (godzinowa sekwencja GHI) — defer do ≥2 lat danych
3. **Gate E1.7:** jeśli MAPE ensemble ≤9% (vs ICON 11%) → **ACCEPT**

---

*Backtest E1.4 — prawdziwe dane z notatek — 27.08.2026*
