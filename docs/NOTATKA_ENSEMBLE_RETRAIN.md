# Ensemble retrain — proces i wymogi

**Data:** 2026-08-27  
**Status:** Dokumentacja · czeka na ≥30 dni danych ensemble

---

## Problem

Retrain RF wymaga **historycznych danych pogody** (archive) dla treningu.  
Obecnie w bazie:
- ✅ ICON archive (2025-04–2026-08)
- ❌ UKMO archive (brak — nigdy nie zbierano)
- ✅ Ensemble forecast (od 27.08.2026)

**Brak UKMO archive** → **nie można retrain na ensemble** bez zebrania danych.

---

## Rozwiązanie — 2 opcje

### **Opcja A: Czekać na ensemble forecast → archive** (zalecane)

1. **Zbieraj ensemble forecast** codziennie (już działa od 27.08):
   ```bash
   WEATHER_ENSEMBLE_UKMO=1 python scripts/analysis/fetch_weather.py
   ```
2. **Czekaj ≥30 dni** (do ~28.09.2026) — forecast staje się archiwum
3. **Retrain** gdy masz ≥30 dni ensemble weather:
   ```bash
   # Za miesiąc (IX 2026)
   python scripts/train/train_dual_weekly.sh
   ```

**Czas:** 1 miesiąc pasywnego zbierania + 30 min retrain

---

### **Opcja B: Pobierz backdated UKMO archive** (trudne)

Open-Meteo **nie ma** UKMO archive API (tylko ICON/ECMWF).  
Nie można pobrać historycznego UKMO.

**Status:** niemożliwe z free tier

---

## Proces retrain (gdy dane gotowe)

### **Krok 1: Włącz flag dla treningu**

`.env`:
```bash
WEATHER_ENSEMBLE_UKMO=1
```

### **Krok 2: Retrain shadow model**

```bash
# Weekly retrain (niedziela 04:30 launchd)
python scripts/train/train_dual_weekly.sh

# Zapisz jako shadow:
cp models/pv_hourly_model.joblib models/pv_hourly_model_ensemble.joblib
```

### **Krok 3: Sprawdź Test MAE**

Target:
- Poprzedni (ICON): **0.658**
- Ensemble: **≤0.65** (bez regresji)

### **Krok 4: Live closeouty 5–7 dni**

Zbieraj ensemble forecast shadow vs ICON primary:

| Dzień | App | RF ICON | RF Ensemble | MAPE ICON | MAPE Ensemble |
|-------|-----|---------|-------------|-----------|---------------|
| ... | | | | | |

### **Krok 5: Gate decyzja**

MAPE ensemble ≤9% → ACCEPT → podmień produkcję

---

## Timeline

| Data | Event |
|------|-------|
| **27.08.2026** | Start zbierania ensemble forecast |
| **28.09–01.10** | ≥30 dni ensemble → retrain możliwy |
| **05–12.10** | Live closeouty (5–7 dni) |
| **13.10** | Gate decyzja E1.7 |

---

## Workaround — shadow forecast bez retrain (teraz)

Możesz **nie czekać** na retrain i od razu zbierać shadow forecast:

```bash
# Codziennie 05:00 + 12:00:
# 1) Primary ICON (jak teraz)
WEATHER_ENSEMBLE_UKMO=0 python mlops/forecast_pv.py --sync

# 2) Shadow ensemble (nowy)
WEATHER_ENSEMBLE_UKMO=1 python mlops/forecast_pv.py --sync --out data/processed/pv_forecast_ensemble.csv
```

Model RF16 (trenowany na ICON) działa też z ensemble weather (cechy te same).  
**Nie jest optymalny** (nie retrain), ale pokazuje efekt ensemble na inference.

---

*E1.5 status: dokumentacja DONE · wykonanie DEFER do IX 2026 (≥30 dni danych)*
