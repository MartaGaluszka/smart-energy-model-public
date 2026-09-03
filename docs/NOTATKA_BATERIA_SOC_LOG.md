# Log SoC / ładowanie baterii — analiza operacyjna

**Pojemność (`.env`):** `BATTERY_CAPACITY_KWH` ≈ **10,36** kWh → **1% ≈ 0,10 kWh**  
**Taryfa:** G12w · tanio pn–pt **22:00–6:00** (i 13–15)  
**Dom:** od **29.08.2025** · świadoma optymalizacja baterii od **I 2026** (G12w / FC / reguła 22:00)  
**Powiązane:** [`NOTATKA_REGULA_BATERIA_POCHMURNO_22.md`](NOTATKA_REGULA_BATERIA_POCHMURNO_22.md) · advisor `battery_advisor.py`

**Gdzie pisać:** ten plik = **żywy log**. Każda doba = sekcja **NOC** (ForceCharge/AGD) + sekcja **DZIEŃ** (SoC vs PV / drogie godziny / closeout).  
Pogoda → `NOTATKA_YYYY-MM-DD.md`; reguła push → notatka reguły.

---

## Jak czytać wpis

| Blok | Co logować |
|------|------------|
| **NOC** | ForceCharge (start/koniec), AGD, min SoC przed PV |
| **DZIEŃ** | SoC @~8 / 11 / 14 / 17 / 22 + PV narastająco / closeout |
| Werdykt | czy starczyło na drogie godziny · luz pod PV · lekcja |

Źródło SoC: app FoxESS + `foxess_data` (gdy sync).

---

## Log

### 2026-09-02 — DZIEŃ (closeout)

SoC **100%** od ~10:00 · PV EOD **31,0** · eksport po pełnej baterii. Accu mix RF. FC nocy **pomiń**.

### 2026-09-03 — DZIEŃ (w toku ~14:27)

| Moment | SoC | PV / uwagi |
|--------|----:|------------|
| **~11:51** | **100%** | okno: niebieskie niebo · Solar **4,12 kW** |
| **~13:40** | **100%** | PV **20,2** · Solar **4,55 kW** · dołek 13 **nie** |
| **~13:52** | **100%** | PV **21,2** · eksport 13,0 · mix 12–14 |
| **~14:27** | **100%** | PV **22,8** · Solar **1,36 kW** · cloud **80–90%** szare |

**Werdykt na teraz:** pełna od ~10. PM zasłona — eksport spada z PV. FC 22:00 **pomiń**. Push **piątek 22:00** przed **5.09** deszcz AM.

---

**Kontekst:** 25 słaby (PV **4,4** · zużycie **7,6** · sieć **1,2**); 26 też słabe PV (daily RF ~**12,5**). Reguła pochmurno → ładuj 22:00.

| Moment | SoC | Δ / uwagi |
|--------|----:|-----------|
| ~21:50–22:00 (przed FC) | **24%** | DB zgodne |
| ForceCharge **22:00–22:30** | **24% → 75%** | **+51 pp** ≈ **~5,3 kWh** / 30 min (~**10–11 kW**) |
| ~00:07 | **75%** | DB: `load` ~**1,9 kW** — start AGD (zmywarka/chleb) |
| ~01:00–05:00 | **67%** | plateau po pierwszym zrzucie |
| **~07:00–08:00** min przed PV | **61%** | DB min godz. 7–8 = **61%** (user OK) |
| AGD łącznie (75→61) | | **≈ −14 pp** (~**1,4–1,5 kWh**) — eko + chleb |

**Werdykt noc:** ForceCharge 30 min OK; AGD nie zjadło bufora; rano **61%** przed dachiem.

---

### 2026-08-26 — DZIEŃ (śledzenie SoC + PV)

**Prognoza daily 05:** RF/CS4/XGB ≈ **12,5 / 11,4 / 11,6** · D+1 **27** ~**33** (jasny).

| Moment | SoC | PV / uwagi |
|--------|----:|------------|
| ~08:00 | **61–64%** | po deszczu przed 7:30; wolny start PV |
| **~10:55** | **74%** | **+13 pp** od min (~**1,3 kWh** w baterii z dachu); DB max godz. 10 = **75%** |
| **~11:02** | — | **prześwit** · chwilowo **1,52 kW** |
| **~11:58** (DB) | **90%** | clearing: PV ~2–3 kW; SoC 74%→90% |
| **12:38→** (app) | **~pełna** | **eksport do Tauron** — nadwyżka PV; bateria nie ładuje dalej |
| **~13:55–14:00** (app) | — | PV dnia **12,4 kWh**; chwilowo **1,99 kW**; eksport **4,1 kWh** (od 12:38 → 14:00) |
| **~18:25** (app) | — | PV dnia **21,1 kWh** (vs daily RF **12,5**); nadal **~30 W** na dachu → EOD może +odrobinę |
| ~22:00 przed ewentualnym FC | — | decyzja: 27 jasny → **nie** pełnić |
| closeout 26 | — | PV **21,1** · zużycie / sieć / SoC EOD *(uzupełnij)* |

**Werdykt dzień (~18:25):**

> MB clearing PM **potwierdzony**. Actual **21,1** vs RF **12,5** (**+8,6**) — wczoraj **4,4**.  
> SoC pełna od **12:38** → eksport (do 14:00 już **4,1**). Nocny FC 24→75% **za agresywny** ex post.  
> Wieczór **27–28**: **nie** ForceCharge.

---

## Szablon (noc + dzień)

```markdown
### YYYY-MM-DD → DD+1 — NOC
| Moment | SoC | Δ / uwagi |
|--------|----:|-----------|
| przed ForceCharge | | |
| ForceCharge HH:MM–HH:MM | → | |
| AGD … | → | ≈ −X pp |
| min przed PV | | |

### YYYY-MM-DD — DZIEŃ
| Moment | SoC | PV / uwagi |
|--------|----:|------------|
| ~08:00 | | |
| ~11:00 | | |
| ~14:00 | | |
| ~17:00 | | |
| ~22:00 | | decyzja FC? |
| closeout | | PV / zużycie / sieć / SoC EOD |

**Werdykt noc / dzień:** …
```
