# Decyzja — operacyjny **CS4**, **ensemble (ENS)** w roli shadow (od 01.11.2026)

**Data:** 2026-10-31  
**Go-live:** `ACCU_CS4_UI=1` · checklist [`NOTATKA_GO_LIVE_CS4_2026-11.md`](NOTATKA_GO_LIVE_CS4_2026-11.md)  
**Gate UI (Faza A+B):** [`NOTATKA_GATE_ACCU_CS4_UI.md`](NOTATKA_GATE_ACCU_CS4_UI.md)  
**Paper Accu→RF/CS4:** tylko repo prywatne (`NOTATKA_PAPER_TRADE_ACCU_REGIME.md`)

---

## Werdykt (jedno zdanie)

Od **01.11.2026** w **apce i baterii** przy Accu **pochmurny/ciemny** używamy **CS4**; **ensemble ICON+UKMO (RF16)** zostaje **shadow** — audyt, closeout i zapis launchd — bez globalnej podmiany primary w MLOps.

---

## Dlaczego przechodzimy na CS4 (operacyjnie)

### 1. Sezon i fakt z listopada 2025 (baza)

| Obserwacja (XI 2025, Open-Meteo + Fox) | Wniosek |
|----------------------------------------|---------|
| Średnie zachmurzenie **~84%** | Zima u nas ≈ długo **pochmurno** |
| **25/30** dni chmury **≥70%** | Dominanta typu dnia z review ML |
| **15/30** dni Fox **&lt;5 kWh** | Niski PV — ENS często **zawyża** |
| Tylko **6/30** dni **≥15 kWh** | Jaśniejsze dni są **wyjątkiem**, nie regułą |

### 2. Jakość modeli na pochmornych (closeouty lipiec–październik)

Z [`weekly_model_weather_review.md`](images/ml/weekly_model_weather_review.md) (n=52 pochmurne/deszczowe):

| Snapshot | ENS (RF×NWP) | **CS4** |
|----------|-------------:|--------:|
| Daily **@05** | 44,9% \|APE\| | **35,2%** |
| Ostatnie **28 dni** (ciemny odcinek) | ~**100%** | ~**63%** |

**ENS wychodzi najsłabiej** na pochmurnych — to główny powód zmiany warstwy **operacyjnej**, nie retreningu jobliba primary.

### 3. Paper-trade i Accu (jesień 2026)

- Reguła od **27.07** dual CS4: **Accu pochmurny → CS4**, mix/jasny → RF/ENS.
- **Nie** routing po samym ICON cloud (gate **01.09 REJECT** ≥30% → CS4).
- **Lumen 1–2** = **ciemny** operacyjnie (ignorujemy etykietę kalendarza Accu „B. jasne”).
- Progi: Lumen **≤4**, cloud **≥70%**, opad **≥2 mm**, burze **≥40%** → **pochmurny → CS4**.

### 4. Bateria i zima

- Reguły **ForceCharge / charge tonight / PV jutro** liczą na **`get_day_pv_forecast_sum`** — zawyżony ENS → zbyt optymistyczna bateria.
- **CS4** na pochmurnych zwykle **niżej** → bezpieczniejsze rezerwy SoC (zgodne z [`PLAN_BATERIA_JESIEN_ZIMA_2026.md`](PLAN_BATERIA_JESIEN_ZIMA_2026.md), osobny tor od routingu kWh).

### 5. Co **nie** robimy

- **Nie** wyłączamy `ENSEMBLE_PRIMARY=1` w launchd.
- **Nie** CS4 **globalnie** na całą zimę — **mix/jasny** i **brak Accu** → nadal **ensemble** w apce.
- **Nie** XGB w operacji (tylko shadow MLOps / ewentualny mix później).

---

## Ensemble = **shadow** — co to znaczy w praktyce

| Warstwa | Ensemble (ICON+UKMO) | CS4 |
|---------|----------------------|-----|
| **Launchd 05/12/16** | Nadal **pierwszy zapis** → `pv_forecast.csv`, `forecast_history` (primary MLOps) | **Dual shadow** → `pv_forecast_cs4.csv`, `daily_cs4` |
| **Aplikacja Prognoza** | **Audit** — `primary_total_kwh`, linia „Ensemble (audit)” | **Display** przy pochmurnym Accu — suma, wykres, baner |
| **Bateria / Home PV** | Gdy **mix/jasny** lub brak Accu | Gdy **pochmurny** (`ACCU_CS4_UI=1`) |
| **Closeout / weekly** | Porównanie **ENS vs CS4 vs Fox** | Pick operacyjny vs fakt |
| **Retrening niedziela** | RF16 + ENS pogoda | CS4 joblib (`train_dual_weekly.sh`) |

**Nazewnictwo:** historycznie ENS był „primary” w gate **01.09**; od XI 2026 **primary operacyjny dla użytkownika** na szary dzień = **CS4**, a **ensemble = shadow operacyjny + shadow techniczny w pipeline**.

---

## Wdrożenie techniczne (skrót)

- `.env`: `ACCU_CS4_UI=1`, `FORECAST_CS4_ENABLED=1`, `ENSEMBLE_PRIMARY=1`
- Kod: `src/weather/accu_regime.py`, `src/weather/forecast_routing.py`, API `/forecast/hourly`, `battery_advisor`
- Smoke: `./mlops/smoke_accu_cs4_routing.sh`
- **Kill switch:** `ACCU_CS4_UI=0` + restart API

---

## KPI listopada (sukces / rollback)

| Sygnał | Działanie |
|--------|-----------|
| Pochmurne dni: \|APE\| **display CS4** ≤ ENS w closeout | kontynuuj |
| False positive Accu (CS4 gorszy o ≥10 pp przy Fox ≥15 kWh) | notatka + ewent. „watch mix” |
| Brak wpisów Accu &gt;2 dni z rzędu | przypomnienie — wtedy apka = ensemble |

Paper-trade i [`NOTATKA_POGODA.md`](NOTATKA_POGODA.md) — log dzienny; po **≥10** pochmurnych closeoutów XI → mini-gate zima (patrz gate §4c).

---

## Powiązane

- Dzień startu: [`NOTATKA_2026-10-31.md`](NOTATKA_2026-10-31.md)  
- **CS4 + L30 (podsumowanie XI):** [`NOTATKA_PODSUMOWANIE_CS4_L30_XI_2026.md`](NOTATKA_PODSUMOWANIE_CS4_L30_XI_2026.md)  
- STATUS ML: [`STATUS_ML_MLOPS.md`](STATUS_ML_MLOPS.md)  
- L30 hard gate: [`NOTATKA_GATE_L30_CLOSEOUT.md`](NOTATKA_GATE_L30_CLOSEOUT.md)  
- Automatyka baterii XI: [`NOTATKA_DECYZJA_AUTOMATYKA_BATERII_XI_2026.md`](NOTATKA_DECYZJA_AUTOMATYKA_BATERII_XI_2026.md)
