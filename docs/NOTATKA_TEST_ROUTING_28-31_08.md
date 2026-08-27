# Test routing ensemble + CS4 — 28–31.08.2026

**Setup:** 27.08.2026  
**Test:** 28–31.08 (4 dni)  
**Gate:** 01.09.2026

---

## Strategia

**Routing conditional:**
- **Jasny** (cloud <30%) → **Ensemble** (ICON+UKMO avg)
- **Pochmurny** (cloud ≥30%) → **CS4** (warstwy chmur + clearness)

**Baseline:** RF16 ICON (current prod)

**Cel:** MAPE routing ≤ MAPE ICON **i** błędy >20% spadły

---

## Shadow forecast daily (05:00 + 12:00)

| Model | Plik | Opis |
|-------|------|------|
| **Baseline ICON** | `pv_forecast.csv` | RF16 + ICON (prod) |
| **Shadow CS4** | `pv_forecast_cs4.csv` | RF CS4 (19 cech) |
| **Shadow Ensemble** | `pv_forecast_ensemble.csv` | RF16 + ICON+UKMO |
| **Routing pick** | `routing_pick.csv` | Decyzja: ensemble vs CS4 |

---

## Zbieranie closeoutów (28–31.08)

| Dzień | Cloud fcst | Regime | Pick | App | ICON | Ensemble | CS4 | **Routing** | Błąd ICON | Błąd Routing |
|-------|------------|--------|------|-----|------|----------|-----|-------------|-----------|--------------|
| **28.08** | **54.4%** | pochmurny | **CS4** | ? | ~30 | ? | ? | **= CS4** | ? | ? |
| **29.08** | ? | ? | ? | ? | ~CS4 | ? | ? | ? | ? | ? |
| **30.08** | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? |
| **31.08** | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? |

**Routing value:** = ensemble jeśli jasny, = CS4 jeśli pochmurny

---

## Closeout template (wieczór każdego dnia)

```bash
# Closeout dnia
python scripts/analysis/evening_closeout_dynamic.sh --day 2026-08-28

# Porównaj prognozy
sqlite3 data/energy_model.db "
SELECT 
  date(timestamp) as day,
  SUM(CASE WHEN pv_energy_kwh > 0 THEN pv_energy_kwh ELSE 0 END) as actual_kwh
FROM foxess_data
WHERE date(timestamp) = '2026-08-28'
"

# Odczytaj shadow forecasts (z plików CSV, kolumna D+0)
cat data/processed/pv_forecast.csv | grep 2026-08-28 | awk -F, '{sum+=$3} END {print "ICON:", sum}'
cat data/processed/pv_forecast_ensemble.csv | grep 2026-08-28 | awk -F, '{sum+=$3} END {print "Ensemble:", sum}'
cat data/processed/pv_forecast_cs4.csv | grep 2026-08-28 | awk -F, '{sum+=$3} END {print "CS4:", sum}'
cat data/processed/routing_pick.csv | grep 2026-08-28
```

---

## Gate 01.09 (pon, 1h)

### **Metryki**

| Metryka | Baseline ICON | Routing (ensemble/CS4) | Target |
|---------|---------------|------------------------|--------|
| MAPE (4 dni) | ? | ? | Routing ≤ ICON |
| Błędy >20% | ? | ? | 0/4 (vs 3/29 baseline) |
| Średni błąd | ? | ? | Routing < ICON |

### **Decyzja**

- **ACCEPT:** Routing ≤ ICON + błędy >20% spadły → wdrożenie 02.09
- **REVIEW:** Routing ≈ ICON → zbierać więcej danych (IX)
- **REJECT:** Routing > ICON → zostać przy ICON

---

## Wdrożenie 02.09 (wt, 30 min) — jeśli ACCEPT

1. Dodaj flag w `.env`:
   ```bash
   ROUTING_ENABLE=1
   ROUTING_CLEAR_CLOUD_MAX=30
   ```

2. Podmień launchd na routing:
   ```bash
   # mlops/launchd_daily_forecast.sh
   if [ "$ROUTING_ENABLE" = "1" ]; then
       python scripts/analysis/routing_decision.py --date tomorrow
       # ... użyj routing_pick.csv do wyboru modelu
   fi
   ```

3. Monitor closeoutów (3–7 dni) — czy poprawa się utrzymuje

---

## Prognozy na 28–31.08 (z notatek)

### **28.08 (czwartek)**
- Accu: jasność 9, cloud 18%, upał ~29°
- **ICON cloud:** ~54% (pesymistyczny vs Accu)
- **Routing:** pochmurny → **CS4**
- **Oczekiwanie:** actual ~30–32 kWh (upał)

### **29.08 (piątek)**
- Accu: jasność 3, cloud 66%, deszcz 1.8 mm rano, burze 17%
- **Routing:** pochmurny → **CS4**
- **Oczekiwanie:** actual ~10–15 kWh (deszcz rano)

### **30–31.08 (sb–ndz)**
- Zależne od Accu run 28.08 midday/29.08 rano

---

## Przewidywania routing

**Hipoteza:**
- **28.08 upał:** ICON za pesymistyczny (54% vs Accu 18%) → CS4 lub ensemble powinny być wyżej
- **29.08 deszcz:** CS4 lepszy na pochmurne → routing pick CS4 dobry
- **Jeśli 30–31 jasne:** ensemble powinien pomóc (jak 23–24.08)

**Ryzyko:**
- 28.08 ICON cloud 54% → routing pick CS4, ale może być za jasno (Accu 18%)
- Próg cloud=30% może być za niski (Accu 18% to jeszcze jasny, ICON 54% to routing→CS4)

**Backup:** Jeśli 28.08 routing CS4 zaniży, rozważ próg 40–50% zamiast 30%.

---

*Test routing 28–31.08 — ensemble + CS4 conditional — gate 01.09*
