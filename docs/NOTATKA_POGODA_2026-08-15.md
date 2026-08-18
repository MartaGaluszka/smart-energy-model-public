# Notatka pogoda — 16–20.08.2026

**Lokalizacja:** okolice Krakowa (dokładne GPS tylko w lokalnym `.env`)  
**Produkcja ML:** Open-Meteo **ICON** (`icon_seamless`)  
**UKMO / Accu / MB:** tylko obserwacja ręczna — **nie** w prod

| Aktualizacja | Źródło |
|--------------|--------|
| 2026-08-16 ~09:40 | Meteoblue MultiModel + meteogram |
| 2026-08-17 ~16:30 | AccuWeather dziś-na-dziś / jutro / +2 |
| 2026-08-17 ~16:35 | MB MultiModel + meteogram + ensemble (pon.–śr.) |
| **2026-08-18 ~10:50** | AccuWeather dziś-na-dziś (18) / jutro (19) / +2 (20) |
| **2026-08-18 ~10:54** | **MB meteogram + MultiModel + ensemble** (wt.–czw.+) |

---

## AccuWeather — 18.08 ~10:50 (obecny run)

| Dzień | T max | Jasność | Cloud | Opady | P deszcz / burza | Wiatr / porywy | PV |
|-------|------:|--------:|------:|------:|------------------|----------------|-----|
| **18.08** wt. (dziś) | **20°C** (RF 19°) | **3** przyćm. | **88%** | **2,0 mm** (~2 h) | 55% / 33% | W 19 / **43** | **słaba** |
| **19.08** śr. | **24°C** (RF 24°) | **7** jasne | **52%** | **0,9 mm** (~1 h) | 60% / 12% | WSW 17 / 41 | **umiarkowana–dobra** |
| **20.08** czw. | **28°C** (RF 28°) | **5** średnie | **76%** | **0,5 mm** (~1 h) | 55% / 13% | SSW 15 / 33 | **umiarkowana** (ciepło, ale cloud 76%) |

Opis 18.08: *„Burza z piorunami na części obszaru”* · UV 2 · alarmy suszy = tło.  
Opis 19.08: *„Przelotne opady deszczu”* · UV 4.  
Opis 20.08: *„Słaby deszcz”* · UV 4.

### Drift vs Accu 17.08 ~16:30

| | Accu 17.08 (outlook) | **Accu 18.08 dziś-na-dziś** |
|--|----------------------|-----------------------------|
| **18.08** cloud / jasność | 78% / 4 | **88% / 3** — trochę **bardziej szary** |
| **18.08** opady | 2,1 mm | **2,0 mm** — bez zmian |
| **19.08** jasność / cloud | 6 / 68% | **7 / 52%** — **jaśniejszy** powrót |
| **19.08** opady | 1,4 mm | **0,9 mm** |

**Wniosek:** wtorek = niski PV ( Accu ≈ MB „szary dzień” ); środa wygląda lepiej niż wczorajszy Accu (jasność 7). Primary ICON bez zmian.

### Closeout 17.08 (kontekst frontu)

| | Actual | Daily RF16 | Daily CS4 | Best raw |
|--|-------:|----------:|----------:|----------|
| **17.08** | **21,5** kWh | 22,2 (−0,7) | **21,4 (+0,14)** | **daily_cs4** |

CS4 daily prawie idealny; RF daily lekko zawyżył. Midday RF 18,9 był za nisko (+2,6). Oneshot CS4 25 (hybrid OFF) zawyżył — peak/daily CS4 ~21 lepiej.

---

## Meteoblue — 18.08 ~10:54

### Skrót meteogram / ensemble

| Dzień | T max ≈ | Opady / chmury | PV |
|-------|--------:|----------------|-----|
| **18.08** wt. | **20°C** | gęste low cloud 90–100%; deszcz rano (peak ~4 mm/h), lekkie przelotne w dzień | **słaba** |
| **19.08** śr. | **24°C** | deszcz rano (~2,5 mm/h) → **przejaśnienia w dzień**; RH↓ ~55% PM | **umiarkowana–dobra** |
| **20.08** czw. | **28°C** (spread 26–30+) | dzień raczej suchy/słońce; chmury rosną PM → deszcz/burze **nocą** | **dobra w dzień**, ryzyko wieczór |
| 21–22.08 | 25–26°C | burze/przelotne (piątek wieczór, sobota rano) | mieszane |

Accu vs MB (T max): **zgodność** 20 / 24 / 28°C. Accu mm na 18 (~2) ≤ MB rano (~kilka mm intensity).

### ICON vs UKMO (MultiModel, wiersze ICON-12 / ICON-7 / UKMO-10)

| Dzień | ICON (12 / 7) | UKMO-10 | Różnica dla PV |
|-------|---------------|---------|----------------|
| **18.08** | Deszcz rano → chmury / częściowe słońce | Jak ICON: deszcz rano → szaro; **nieco więcej** przejaśnień w dzień (jak w runie 17.08) | **UKMO lekko jaśniejszy** — mały plus PV |
| **19.08** | Deszcz rano → clearing | Deszcz rano → chmury (mniej „słońca” niż ICON w ikonach) | **ICON ≈ / lekko jaśniejszy** po południu |
| **20.08** | Słońce większość dnia → chmury/deszcz późny wieczór–noc | Jak ICON: słońce dzień, deszcz nocą | **Zgodność** |

**Werdykt MB 18.08**

- **18.08:** ICON ≈ UKMO na charakterze dnia (mokry ranek, szaro); UKMO nadal trochę optymistyczniejszy na przejaśnienia — blisko Accu „burze na części obszaru”.
- **19.08:** zgodność na deszcz rano + poprawa; Accu jasność 7 wspiera narrację „lepszy dzień”.
- **20.08:** zgodność — ciepły dzień PV OK, front/burze dopiero nocą (Accu cloud 76% / jasność 5 = ostrożniej niż czyste „słońce” w ikonach MultiModel).
- **Bez oneshot UKMO** — primary RF16+ICON.

Wiatr: W/NW wtorek–środa, porywy ~35–40; czwartek większy **spread** modeli (kierunek + prędkość). Ensemble tydzień: duży spread sumy mm (hi-res/GFS ~15–80 do weekendu) — nie używać do gate’u.

---

## ICON vs UKMO — MB MultiModel **17.08 ~16:35** (archiwum)

Wiersze: **ICON-12**, **ICON-7**, **UKMO-10**. Teraz (~16:35) dzień 17.08 już w toku — rano/południe za nami.

| Dzień | ICON (12 / 7) | UKMO-10 | Różnica dla PV |
|-------|---------------|---------|----------------|
| **17.08** pon. | Do ~18 słońce/chmury; od **~18** deszcz + **burze** przez noc | Jak ICON: popołudnie OK, od **~18** deszcz/burze | **Zgodność** — wspólny start burz wieczorem (nie rozjazd 12 vs 15 jak w runie 16.08) |
| **18.08** wt. | Rano deszcz → dzień głównie szary; lekka poprawa PM | Rano deszcz; w dzień **więcej przejaśnień** (słońce+chmury) niż ICON | **UKMO trochę jaśniejszy** we wtorek — lekki plus PV vs ICON |
| **19.08** śr. | Rano jaśniej; deszcz **~12–18** | Jak ICON: rano słońce, deszcz popołudniu | **Zgodność** |

**Werdykt (17.08 popołudniu)**

- **17.08:** ICON ≈ UKMO. Stary rozjazd (UKMO deszcz ~12–13 vs ICON ~15) **się zatarł** — oba modele trzymają **front wieczorny (~18+)**. Pasuje do Accu alertu burz (od 14:00, szczyt później) i MB opadów (spike ~21–00, do ~6 mm/h).
- **18.08:** drobna przewaga UKMO na jasności dnia; hi-res ensemble nadal **rozjeżdża sumę mm** (~18 vs ~28 mm kumulatywnie do końca wtorku).
- **19.08:** zgodność — popołudniowe/wieczorne przelotne.
- **Oneshot UKMO:** nadal **nie** — primary **RF16 + ICON**. Closeout 17.08 = dzień z oknem PV przed burzami + CS4 vs RF.

### Ensemble / meteogram (konsensus, ~16:35)

| | 17.08 | 18.08 | 19.08 |
|--|------:|------:|------:|
| T max ≈ | **25–28°C** | **19–20°C** | **24–25°C** |
| Opady | spike od ~18, szczyt **~21–00** | resztki rano + możliwe przelotne PM | mniejszy peak ~15–18 / wieczór |
| Cloud | rosnące PM → ~100% wieczór | gęste rano (70–100%), przejaśnienia PM | zmienne 30–70% |
| Wiatr | słaby SE→S/SW; porywy wieczorem ↑ | porywy **~40–45** noc/rano (spread modeli duży) | W/SW, porywy ~40 PM |

---

## AccuWeather — 17.08 ~16:30 (archiwum)

| Dzień | T max | Jasność | Cloud | Opady | P deszcz / burza | Wiatr / porywy | PV |
|-------|------:|--------:|------:|------:|------------------|----------------|-----|
| **17.08** | **26°C** | **5** | **54%** | **3,4 mm** | 90% / 54% | SE 11 / 22 | umiarkowana (okno przed burzami) |
| **18.08** | **20°C** | **4** | **78%** | **2,1 mm** | 55% / 33% | W 19 / **44** | słaba |
| **19.08** | **24°C** | **6** | **68%** | **1,4 mm** | 65% / 13% | WSW 19 / 37 | umiarkowana |

Alarmy Accu 17.08: **pomarańcz burze** 14:00→00:00 · **żółte powódź** 14:00→04:00.

**Accu vs MB mm:** Accu dziś-na-dziś daje tylko **kilka mm/dzień**; MB hi-res kumuluje więcej do wtorku (18–28 mm) — closeout pokaże, kto bliżej rzeczywistości.

---

## Drift runów (17.08)

| Run | Timing deszczu 17.08 | Uwaga |
|-----|----------------------|-------|
| MB **16.08** rano | ICON ~15 · UKMO ~12–13 | **główny rozjazd** |
| Accu **15.08** | cały dzień szary (94% / 14,7 mm) | zbyt pesymistyczny |
| **MB + Accu 17.08 ~16:30** | burze **wieczór (~18+)**; Accu alert od 14 | **ICON ≈ UKMO**; Accu T≈MB |

---

## Operacyjnie

| Kiedy | Co |
|-------|-----|
| **18.08** | Niski PV; CS4 vs RF na closeout (szary) · oneshot: [`NOTATKA_ONESHOT_2026-08-17.md`](NOTATKA_ONESHOT_2026-08-17.md) (run 18.08) |
| **19.08** | Accu jasność 7 + MB clearing — lepszy dzień; UKMO niepotrzebny |
| **20.08** | Ciepło / PV OK w dzień; burze wg MB dopiero nocą |
| **17.08** (done) | Closeout 21,5 · best **daily_cs4** · oneshot: [`NOTATKA_ONESHOT_2026-08-17.md`](NOTATKA_ONESHOT_2026-08-17.md) |


Weekly: [`NOTATKA_WEEKLY_2026-08-16.md`](NOTATKA_WEEKLY_2026-08-16.md) · dzień **18.08**: [`NOTATKA_2026-08-18.md`](NOTATKA_2026-08-18.md)

---

## Archiwum — MB 16.08 ~09:40 (skrót)

16 = peak słońce · 17 = deszcz od ~15 (wtedy) · 18 = ciągły deszcz — **nadpisane** świeższym MultiModelem powyżej.

---

*Źródła: AccuWeather · Meteoblue MultiModel / meteogram / ensemble · Open-Meteo ICON w pipeline.*
