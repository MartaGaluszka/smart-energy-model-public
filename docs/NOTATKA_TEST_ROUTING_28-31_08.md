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
| **28.08** | ICON cloud **49,8%** · Accu **21%** | routing **pochmurny** / Accu **jasny** | routing→**CS4** · Accu→RF | **34,2** | **30,0** | **31,8** | **30,8** | =CS4 | **−12%** | **−10%** |
| **29.08** | ICON **67%** · Accu **33%** · **okno: burza→deszcz do 08; clearing 11:50+** | pochmurny | **CS4** ✓ | **21,1** | **20,7** | **20,3** | **21,5** | **=CS4 21,5** | **−2%** | **+2%** |
| **30.08** | ICON **~53%** · Accu **23%** · okno **0 cloud** | pochmurny (ICON) / Accu+okno **jasny** | routing→**CS4** · Accu→**RF** | **33,2** | **28,2** | **31,1** | **29,7** | =CS4 | **−15%** | **−11%** |
| **31.08** | ICON **~90%** · Accu **4/61%/0,3** P80% + burza ~15:15 | pochmurny | **CS4** | **24,6** | **19,8** | **26,2** | **20,4** | =CS4 | **−20%** | **−17%** |

*(30: oneshot UKMO **32,2 (−3%)** ≫ ICON **26,1**; ens launchd ≈ kompromis. Routing CS4 lepszy niż RF, gorszy niż ens/UKMO. 31 oneshot I/U **20,8 / 25,3**.)*

**Uwaga 28.08 ~17:35:** shadow ensemble **WŁĄCZONY** (`mlops/forecast_ensemble_shadow.sh` w daily/midday/peak).  
CSV: `pv_forecast_ensemble.csv`. Primary ICON nienaruszony (osobny `data_source`).  
Dogonienie: pierwszy live run peak 28.08 (rana 28 bez ensemble = 1 dzień straty na D+0 raw).

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

## Gate 01.09 (pon, 1h) — **DECYZJA**

### Metryki (28–31.08, n=4)

| Strategia | MAPE | Błędy >15% | Co wybiera |
|-----------|-----:|:----------:|------------|
| zawsze RF (ICON) | **10,9%** | 2/4 (30, 31) | — |
| zawsze CS4 | **9,9%** | 1/4 (31) | — |
| **ICON cloud ≥30% → CS4** (hipoteza testu) | **9,9%** | 1/4 | **zawsze CS4** (28–31 ICON cloud 50–90%) — **ensemble nigdy** |
| ICON cloud ≥55% → CS4 else ENS | **8,1%** | 1/4 (31) | 28+30 ENS · 29+31 CS4 |
| Accu mokry→CS4 else ENS | **8,1%** | 1/4 (31) | 28+30 ENS · 29+31 CS4 |
| **zawsze Ensemble** | **5,9%** | **0/4** | — |
| Accu RF/CS4 (paper) | 10,3% | 2/4 | bez ens |

| Dzień | Act | RF | CS4 | ENS | ½ oneshot | ICON cloud | Accu | Best |
|-------|----:|---:|----:|----:|----------:|-----------:|------|------|
| **28** | 34,2 | 31,8 (−7%) | 30,8 (−10%) | **31,8 (−7%)** | — | **50%** | jasny | RF≈ENS |
| **29** | 21,1 | 20,7 (−2%) | **21,5 (+2%)** | 20,3 (−4%) | 18,4 | **67%** | mokry AM | **CS4** |
| **30** | 33,2 | 28,2 (−15%) | 29,7 (−11%) | **31,1 (−6%)** | 29,1 / UKMO 32,2 | **53%** | jasny/okno 0 | **ENS** |
| **31** | 24,6 | 19,8 (−20%) | 20,4 (−17%) | 26,2 (+7%) | **25,5 (−3%)** | **90%** | pochmurny+burza | **½ / ENS** |

### Werdykt gate

| Opcja | Status | Uzasadnienie |
|-------|--------|--------------|
| Hipoteza **ICON cloud ≥30% → CS4** | **REJECT** | Próg za niski: ICON jest systematycznie za chmurny na jasne dni → routing **nigdy nie bierze ensemble**. MAPE = always CS4. |
| **Zawsze Ensemble (ICON+UKMO)** jako daily primary | **ACCEPT (rekomendacja)** | MAPE **5,9%**, 0 błędów >15% na 28–31. Nawet na 31 (burza) ENS lepszy niż CS4. |
| CS4 | **zostaje shadow** | Wygrywa wąsko tylko na **29** (mokry AM). Nie jako default. |
| RF ICON solo | **baseline / backup** | Undershoot na jasnych (30: −15%). |

### Reguły do wdrożenia (propozycja operacyjna)

```text
1) DAILY PRIMARY (od 02.09, jeśli akceptujesz):
   → Ensemble ICON+UKMO   (pv_forecast_ensemble / ten sam RF16)

2) CS4 — tylko shadow + alert, NIE primary, dopóki n≥10 mokrych closeoutów
   Wyjątek ręczny / paper: Accu pochmurny (jasność≤4 LUB cloud≥70 LUB opad≥2 LUB burze≥40%)
   LUB potwierdzony mokry AM (okno/MB) → wtedy wolno wybrać CS4 w paper/UI
   Ale launchd: nadal ensemble (31 pokazał CS4 −17% vs ENS +7%).

3) NIE wdrażać progu ICON cloud ≥30% (ani 40%).
   Jeśli kiedyś wrócimy do progu ICON-only: start od ≥55–70% + Accu mokry (nie sam cloud).

4) UKMO oneshot: pilnować broken radiation na forecast D+2 (3.09) — nie ufać ślepo.
```

### Decyzja formalna (potwierdzona 01.09)

- [x] **REJECT** routing ICON≥30%→CS4  
- [x] **ACCEPT** ensemble jako primary daily  
- [x] CS4 + RF/ICON zostają w shadow / porównaniu closeout  
- [x] Paper Accu RF↔CS4 kontynuować (osobna ścieżka UI), bez zmiany że ensemble wygrywa kWh na jasnych

**Backup planu (plan E1):** próg 40–50% był lepszy niż 30%, ale **always ENS** bije oba na tej próbce.

---

## Gate 01.09 — metryki (szablon oryginalny, wypełniony)

| Metryka | Baseline ICON | Routing ICON≥30%→CS4 | Ensemble always | Target |
|---------|---------------|----------------------|-----------------|--------|
| MAPE (4 dni) | **10,9%** | **9,9%** | **5,9%** | Routing ≤ ICON → ENS spełnia |
| Błędy >20% | **1/4** (31) | **0/4** (>20%); 31 CS4 −17% | **0/4** | spadły przy ENS |
| Średni \|błąd\| | wyższy | ≈CS4 | **najniższy** | ENS |

---

## Wdrożenie 01–02.09 — ensemble primary ✅

1. Flagi w `.env`: `ENSEMBLE_PRIMARY=1` (bez `ROUTING_CLEAR_CLOUD_MAX=30`).
2. `mlops/_ensemble_primary.sh` + daily/midday/peak: ensemble → `pv_forecast.csv`; ICON → `pv_forecast_icon.csv`.
3. CS4 + ICON solo: nadal shadow CSV; routing_decision = porównanie shadow.
4. Monitor 3–7 dni (w tym 1–3.09) — MAPE; UKMO rad broken = skip dnia w oneshot.

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
