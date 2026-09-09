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

## Bojler (CWU) — sygnatura FoxESS

Potwierdzone **5.09** (po kajakach; nie gotowanie).

| | |
|--|--|
| **Moc** | **~2,2–2,6 kW** (start cyklu bywa **~1,7 kW**) |
| **Czas** | **~20–30 min** |
| **Energia** | **~0,9–1,2 kWh** / cykl · **≈ −8…−11 pp** SoC (1% ≈ 0,10 kWh) |
| **Skąd** | bateria, gdy SoC wysoki (sieć ~0) |
| **Kiedy** | po ciepłej wodzie, typowo wieczór **~19:15–22:25** |

**5.09:** **20:20–20:47** · 1,7→2,6 kW · SoC **97%→88%** (−9 pp) · ~1 kWh.  
Podobny wieczorny impuls (ten sam rząd kW): 1.09 ~22:00–22:23 · 2.09 ~21:44–22:02 · 3.09 ~22:02–22:20 · 4.09 ~19:16–19:34.

Nie mylić z płytą (też ~2 kW, ale przy obecności / posiłku) — 5.09 bez gotowania.

---

## Log

### 2026-09-05 — DZIEŃ (kajaki / pusty dom)

Wyjazd ~**8:30** · powrót ~**14:30** (bez skoku mocy). Nie gotowali, nie grzali. PC/przedłużki zostawione — load jak pusta noc.

| Moment | SoC | PV / uwagi |
|--------|----:|------------|
| ~7:40–7:49 | 70→67% | śniadanie ~2,5 kW |
| **~8:25** | **66%** | wyjazd — load **~90–110 W** |
| **11:38** | **100%** | eksport |
| 8:30–14:30 | 66→100% | load domu **0,50 kWh** (vs weekend w domu 1,7–4,8) |
| **20:20–20:47** | **97%→88%** | **bojler** **2,2–2,6 kW** · ~1 kWh · sieć ~0 |
| EOD | **87%** | PV Fox **20,2** · ENS **+1,3%** |

**Werdykt:** pusty dom zszedł ~**4 kWh** vs typowy weekend. Zapomniany sprzęt nie zjadł wyjazdu. Bojler wieczór z baterii.

### 2026-09-06 — DZIEŃ (closeout)

Accu mix→**RF** · Fox EOD **23,3** vs app **27,5** / ENS **28,1**. FC wieczór: rozważyć jeśli SoC niski przed **7.09** CS4 (Accu 2/93%).

| Moment | SoC | PV / uwagi |
|--------|----:|------------|
| closeout ~19:04 | | PV **23,3** · zużycie / sieć / SoC EOD *(uzupełnij)* |

**Werdykt:** produkcja poniżej ENS (UKMO za jasny). Jutro paper **CS4** — watch SoC przed 22:00.

### 2026-09-02 — DZIEŃ (closeout)

SoC **100%** od ~10:00 · PV EOD **31,0** · eksport po pełnej baterii. Accu mix RF. FC nocy **pomiń**.

### 2026-09-03 — DZIEŃ (closeout)

| Moment | SoC | PV / uwagi |
|--------|----:|------------|
| **~11:51** | **100%** | okno: niebieskie niebo · Solar **4,12 kW** |
| **~13:40** | **100%** | PV **20,2** · Solar **4,55 kW** · dołek 13 **nie** |
| **~13:52** | **100%** | PV **21,2** · eksport 13,0 · mix 12–14 |
| **~14:27** | **100%** | PV **22,8** · Solar **1,36 kW** · cloud **80–90%** szare |
| **EOD** | **100%** | PV **27,4** · Accu RF · ENS −11% · FC **pomiń** |

**Werdykt:** pełna od ~10; PM zasłona bez deszczu. EOD **27,4** w szacunku 25–28. Push **piątek 22:00** przed **5.09** deszcz AM.

### 2026-09-04 — DZIEŃ (śledzenie)

Accu+MB **CS4** · okno białe 80–90% + breaks · app daily **17,68**.

| Moment | SoC | PV / uwagi |
|--------|----:|------------|
| **~9:40** | **79%** | PV **2,00** · Solar **1,12 kW** · load **2,18** · rozład. **1,03 kW** · sieć **38 W** · zużycie **2,90** · Autokonsumpcja |
| ~11:00 | | |
| ~14:00 | | |
| ~17:00 | | |
| ~22:00 | | FC przed **5.09** deszcz AM? |
| closeout | | PV / zużycie / sieć / SoC EOD |

**Werdykt ~9:40:** PV < load → bateria pokrywa lukę, prawie bez sieci. Jeszcze **nie** ładuje z dachu (1,12 kW za mało). Bufor **79%** OK na drogie godziny; watch czy SoC spadnie zanim PV urośnie.

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
