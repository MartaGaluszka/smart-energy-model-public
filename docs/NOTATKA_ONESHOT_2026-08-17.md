# Raport oneshot — shadow RF16 / CS4 / XGB+TS

**Ostatni run:** 2026-08-19 ~11:30 → pełny raport dnia: [`NOTATKA_2026-08-19.md`](NOTATKA_2026-08-19.md)  
**Typ:** oneshot (bez zmiany produkcji / launchd)  
**Pogoda prod:** Open-Meteo **ICON** · GPS tylko w `.env`  
**Modele:** weekly 16.08 — RF16 primary · CS4 + XGB+TS shadow  

| CSV | Okno |
|-----|------|
| `oneshot_shadow_*20260817*` | 17–19.08 (run 17.08 ~16:40) |
| `oneshot_shadow_*20260818*` | 18–20.08 (run 18.08 ~10:57) |
| `oneshot_shadow_*20260819*` | **19–21.08 (run 19.08 ~11:30)** |

Pogoda Accu/MB: [`NOTATKA_POGODA_2026-08-15.md`](NOTATKA_POGODA_2026-08-15.md) · weekly: [`NOTATKA_WEEKLY_2026-08-16.md`](NOTATKA_WEEKLY_2026-08-16.md) · dzień: [`NOTATKA_2026-08-19.md`](NOTATKA_2026-08-19.md)

---

## Werdykt (aktualny)

> **19.08:** Accu ≈ MB · ICON ≈ UKMO (ikony) · oneshot ICON ~**21 / 25–28 / 10–12** (19/20/21) · **UKMO PV +5…+7** na jasnych → bez podmiany.  
> **18.08 closeout:** actual **17,8** · RF −2,5 · CS4 −1,5 · best peak.  
> **17.08 closeout:** actual **21,5** · best **daily CS4**.

---

## A. Closeout 17.08 — weryfikacja oneshotu z 17.08

| | Actual | Daily RF16 | Daily CS4 | Midday RF | Oneshot hybrid OFF CS4 |
|--|-------:|----------:|----------:|----------:|-----------------------:|
| **17.08** | **21,5** | 22,2 (−0,7) | **21,4 (+0,14)** | 18,9 (+2,6) | 25,0 (zawyżony) |

| Hipoteza przed closeoutem | Fakt |
|---------------------------|------|
| CS4 oneshot 25 zawyży | **tak** |
| Peak/daily CS4 ~21 bliżej | **tak** (daily CS4 idealny) |
| Actual ~19–22 | **21,5** ✓ |
| UKMO lekko wyżej niż ICON | nie rozstrzygane na closeout (prod=ICON) |

**Lekcja:** na dniu przejściowym oceniaj **launchd daily/midday**, nie surowy hybrid-OFF z popołudnia (CS4 25).

---

## B. Oneshot **18.08 ~10:57** — ICON hybrid OFF

| Dzień | RF16 | CS4 | XGB+TS | vs Accu/MB |
|-------|-----:|----:|-------:|------------|
| **18.08** wt. | 20,3 | **20,8** | 19,1 | Accu: jasność 3, cloud 88% → **słaby dzień**; modele ~20 = OK |
| **19.08** śr. | 21,0 | **21,0** | 19,9 | Accu jasność **7** / MB clearing → modele ~21 mogą być **konserwatywne** |
| **20.08** czw. | 20,0 | **22,9** | 17,0 | Accu 28°C / jasność 5 / cloud 76%; MB słońce→burze nocą · **CS4↑ XGB↓** spread |

### Launchd daily 05:00 (18.08) — raw

| | RF16 | CS4 | XGB+TS |
|--|-----:|----:|-------:|
| **18.08** | **20,3** | 19,3 | 19,1 |
| 19.08 | 21,0 | 19,4 | 19,9 |
| 20.08 | 20,0 | 19,3 | 17,0 |

CS4 daily **niżej** niż oneshot hybrid OFF na 18 (19,3 vs 20,8) — typowe: launchd = ten sam pipeline co prod.

---

## C. Porównanie ICON vs UKMO (Open-Meteo, 18.08 ~10:57)

| Dzień | Model | ICON | UKMO | Δ |
|-------|-------|-----:|-----:|--:|
| **18.08** | RF16 | 20,3 | **26,1** | **+5,8** |
| | CS4 | 21,6 | 24,5 | +2,9 |
| | XGB+TS | 19,1 | 24,4 | +5,3 |
| **19.08** | *wszystkie* | ~20–22 | *(3 h — niekompletne)* | **ignorować** |
| **20.08** | *wszystkie* | ~17–21 | *(brak godzin UKMO)* | **ignorować** |

### vs Accu / MB MultiModel (dziś)

| Źródło | Narracja 18.08 | Pasuje do |
|--------|----------------|-----------|
| **Accu** | jasność 3, cloud 88%, 2 mm, burze lokalne | **ICON ~20** |
| **MB** | deszcz rano, gęste chmury, UKMO trochę jaśniejszy w ikonach | ICON |
| **UKMO oneshot PV** | +3…+6 kWh vs ICON | **zbyt optymistyczny** dziś (jak case 11.08) |

**Werdykt UKMO:** na **szarym** 18.08 UKMO **nie** do podmiany — rozjazd większy niż wczoraj (+1…+2,5). MB „UKMO jaśniejszy” potwierdzony liczbowo, ale Accu/MB konsensus = dzień słaby → zostajemy przy ICON.

---

## D. Porównanie shadow na dziś (18.08)

| Sygnał | RF16 | CS4 | XGB+TS |
|--------|-----:|----:|-------:|
| Daily 5:00 raw | **20,3** | 19,3 | 19,1 |
| Oneshot ICON hybrid OFF | 20,3 | **20,8** | 19,1 |
| UKMO oneshot | 26,1 | 24,5 | 24,4 |

- Modele na ICON **zgadzają się** (~19–21) — dzień pochmurny, mały spread.
- Po **17.08** (CS4 wygrał) warto na closeout **18.08** znów pilnować CS4 vs RF (szary dzień = teren CS4).
- XGB+TS najniżej na ICON i na 20.08 (17 kWh) — obserwacja, nie gate.

---

## E. Co dalej

| Akcja | Status |
|-------|--------|
| Primary RF16 + ICON | **bez zmian** |
| Closeout **18.08** | RF vs CS4 (szary); hipoteza actual **~15–22** |
| **19.08** | Accu jasność 7 — jeśli actual ≫ 21, ICON/model konserwatywny |
| UKMO oneshot 19–20 | powtórzyć gdy API pełne godziny |
| Gate primary→CS4 | nadal **nie** (1 wygrana 17.08 ≠ seria) |

---

## F. Archiwum — oneshot 17.08 ~16:40 (skrót)

ICON hybrid OFF: 17=22,4/25,0/23,0 · 18=20,3/20,8/19,1 · 19=21,0/21,0/19,9  
UKMO wtedy: 17–18 tylko **+1…+2,5** (dziś na 18 już **+3…+6**).  
Launchd 17: daily ~22 → midday/peak ~19; FoxESS do 15:00 już ~18,7.

---

*Raport roboczy MLOps — produkcja nietknięta.*
