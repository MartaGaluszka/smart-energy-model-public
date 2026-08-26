# Log SoC / ładowanie baterii — analiza operacyjna

**Pojemność (`.env`):** `BATTERY_CAPACITY_KWH` ≈ **10,36** kWh → **1% ≈ 0,10 kWh**  
**Taryfa:** G12w · tanio pn–pt **22:00–6:00** (i 13–15)  
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

### 2026-08-25 → 26 — NOC (ForceCharge + chleb + zmywarka eko)

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
| **~11:02** | — | **prześwit** na ciemnym niebie · chwilowo **1,52 kW** (mix / nie ciągłe słońce) |
| ~12:00 midday | — | *(uzupełnij)* |
| ~14:00 | — | *(uzupełnij)* |
| ~17:00 / peak | — | *(uzupełnij)* |
| ~22:00 przed ewentualnym FC | — | decyzja: 27 jasny → **nie** pełnić na styk |
| closeout 26 | — | PV actual · zużycie · sieć · SoC EOD |

**Werdykt dzień (rano ~11):**

> Na słaby ranek 26 zapas **74%** @10:55; @11:02 prześwit 1,52 kW.  
> **MB:** clearing **PM** możliwe → dach może doładować SoC popołudniu.  
> Wieczór: pod **27–28** pełne słońce (MB≈Accu) zostaw **luz** — nie ForceCharge do 100%.

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
