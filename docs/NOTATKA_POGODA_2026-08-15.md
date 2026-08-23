# Notatka pogoda — 16–24.08.2026

**Lokalizacja:** okolice Krakowa (dokładne GPS tylko w lokalnym `.env`)  
**Produkcja ML:** Open-Meteo **ICON** (`icon_seamless`)  
**UKMO / Accu / MB:** tylko obserwacja ręczna — **nie** w prod

| Aktualizacja | Źródło |
|--------------|--------|
| 2026-08-16 ~09:40 | Meteoblue MultiModel + meteogram |
| 2026-08-17 ~16:30 | AccuWeather dziś-na-dziś / jutro / +2 |
| 2026-08-17 ~16:35 | MB MultiModel + meteogram + ensemble (pon.–śr.) |
| **2026-08-18 ~10:50** | AccuWeather dziś-na-dziś (18) / jutro (19) / +2 (20) |
| **2026-08-18 ~10:54** | MB meteogram + MultiModel + ensemble (wt.–czw.+) |
| **2026-08-19 ~11:20** | AccuWeather dziś-na-dziś (19) / jutro (20) / +2 (21) |
| **2026-08-19 ~11:23** | MB MultiModel + meteogram + ensemble (śr.–pt.) |
| **2026-08-20 ~16:20** | AccuWeather dziś-na-dziś (20) / jutro (21) / +2 (22) |
| **2026-08-20 ~16:24** | **MB MultiModel + meteogram + ensemble** (czw.–sob.) |
| **2026-08-17** | **Alert RCB** — burze / silny wiatr / intensywne opady **17.08**; możliwe przerwy w prądzie |
| **2026-08-20 ~16:45** | **Alert RCB** — burze / silny wiatr / intensywne opady **20–21.08**; możliwe przerwy w prądzie |
| **2026-08-20 ~17:00** | Archiwum RCB uzupełnione: **19.07**, **01.08**, **06/07.08** → alerty RCB (archiwum lokalne) |
| **2026-08-21 ~09:05** | AccuWeather dziś-na-dziś (21) / jutro (22) / +2 (23) |
| **2026-08-21 ~09:12** | **MB MultiModel + meteogram + ensemble** (pt.–nd.+) |
| **2026-08-22 ~18:04** | AccuWeather dziś-na-dziś (22) / jutro (23) / +2 (24) |
| **2026-08-22 ~18:05** | **MB MultiModel + meteogram + ensemble** (sob.–pon.) |

---

## Alerty RCB (skrót; pełne SMS → alerty RCB (archiwum lokalne))

| Data | Okno | Skrót | Kontekst lokalny |
|------|------|-------|------------------|
| **14.07** | 14.07 | Burze + wiatr + opady; **podtopienia** + blackout | DB `#9` · koszyk pochmurny |
| **15.07** | 15.07 | Burze + wiatr + intensywne opady; blackout | DB `#10` |
| **17/18.07** | 17–18.07 | Burze z **gradem** + wiatr; blackout | DB `#11` `#12` · burza w oknie PV + EPS |
| **19.07** | 19.07 | Burze z **gradem** + wiatr; blackout | DB `#20` · closeout **27,3** · APE ~1,5% |
| **01.08** | 01/02.08 | Burze + wiatr + deszcz + **grad**; blackout | DB `#126` `#127` · koszyk pochmurny |
| **06.08** | 06/07.08 | Burze + wiatr + intensywne opady; blackout | DB `#128` `#129` · 07 CS4 1,5% vs raw 12,9% |
| **17.08** | 17.08 | Burze + wiatr + intensywne opady; blackout | DB `#130` · closeout **21,5** · best CS4 |
| **20–21.08** | 20/21.08 | Burze + wiatr + intensywne opady; blackout | DB `#131` `#132` · Accu pomarańcz 17:00→03:00 · lokalnie 20.08 front ~17:09 |

Pełne SMS + id wierszy: alerty RCB (archiwum lokalne).  
Przy blackoucie: luki FoxESS / cron — przed closeoutem sprawdzić kompletność serii.

---

## AccuWeather — 22.08 ~18:04 (obecny run)

| Dzień | T max | Jasność | Cloud | Opady | P deszcz / burza | Wiatr / porywy | PV |
|-------|------:|--------:|------:|------:|------------------|----------------|-----|
| **22.08** sob. (dziś) | **23°C** (RF 23° / Shade 20°) | **6** średnie | **65%** | **0,7 mm** (~1,5 h) | **55%** / 11% | W 24 / **59** | **umiarkowana** |
| **23.08** nd. | **22°C** (RF 22° / Shade 20°) | **9** b. jasne | **26%** | **0 mm** | 2% / 0% | W 15 / 35 | **bardzo dobra** |
| **24.08** pon. | **22°C** (RF 23° / Shade 21°) | **9** b. jasne | **7%** | **0 mm** | 3% / 0% | W 11 / 30 | **bardzo dobra** |

Opis 22.08: *„Wietrznie”* · UV 5.  
Opis 23.08: *„Słonecznie z możliwym zachmurzeniem małym”* · UV 5.  
Opis 24.08: *„Słonecznie”* · UV 5.

### Alarmy Accu (22.08)

| Alarm | Okno |
|-------|------|
| Susza | tło (×3 w UI) |

### Drift vs Accu 21.08 ~09:05

| | Accu 21.08 (outlook) | **Accu 22.08 dziś-na-dziś** |
|--|----------------------|-----------------------------|
| **22.08** jasność / cloud / mm / porywy | **9** / 29% / 0 / 41 | **6 / 65% / 0,7 / 59** — **ciemniej / wietrzniej** |
| **23.08** jasność / cloud | 9 / 18% | **9 / 26%** — nadal jasno |
| **24.08** | (brak) | jasność **9**, cloud **7%**, 0 mm |

**Wniosek:** outlook 21.08 na sobotę był za jasny — MB (deszcz rano + porywy) bliżej. Nd–pon. jasne → ryzyko zaniżenia. Primary bez zmian.  
Dzień: [`NOTATKA_2026-08-22.md`](NOTATKA_2026-08-22.md).

### MB 22.08 ~18:05 — Accu vs MB · ICON vs UKMO

| Dzień | Accu | MB | Zgodność |
|-------|------|-----|----------|
| **22** | jasność 6 / 0,7 mm / porywy 59 | Deszcz rano + drobne wieczór; porywy rano ~30–60 | **Tak** mieszany |
| **23–24** | jasność 9 / 0 mm | Porozumienie — słońce | **Tak** |

| Dzień | ICON | UKMO | Różnica |
|-------|------|------|---------|
| **22** | ICON-12 deszcz ~18; ICON-7 wieczór jaśniej | Szybszy clearing; wieczór suchy | **UKMO jaśniejszy** niż ICON-12 |
| **23–24** | Słońce | Słońce | **≈** |

Primary ICON — bez podmiany.

### Closeout 21.08 / 20.08

| Dzień | Actual | Daily RF | Daily CS4 | Best |
|-------|-------:|---------:|----------:|------|
| **21.08** | **13,4** | 17,8 (−4,4) | 16,3 (−2,9) | **peak** RF |
| **20.08** | **27,4** | 31,1 (−3,7) | 29,5 (−2,1) | **peak_cs4** |

---

## AccuWeather — 21.08 ~09:05 (archiwum)

| Dzień | T max | Jasność | Cloud | Opady | P deszcz / burza | Wiatr / porywy | PV |
|-------|------:|--------:|------:|------:|------------------|----------------|-----|
| **21.08** pt. (dziś) | **24°C** (RF 26° / Shade 23°) | **3** przyćm. | **88%** | **6,4 mm** (~3,5 h) | **96%** / **58%** | ESE 9 / 28 | **słaba** |
| **22.08** sob. | **23°C** (RF 23° / Shade 21°) | **9** b. jasne | **29%** | **0 mm** | 25% / 0% | WSW 22 / **41** | **bardzo dobra** |
| **23.08** nd. | **22°C** (RF 22° / Shade 20°) | **9** b. jasne | **18%** | **0 mm** | 2% / 0% | W 15 / 32 | **bardzo dobra** |

Opis 21.08: *„Okresowy deszcz i burza z piorunami”* · UV 4.  
Opis 22.08: *„Słonecznie z możliwym zachmurzeniem małym”* · UV 5.  
Opis 23.08: *„Przeważnie słonecznie”* · UV 5.

### Alarmy Accu (21.08)

| Alarm | Okno |
|-------|------|
| Susza | tło (×3 w UI) |

### Drift vs Accu 20.08 ~16:20

| | Accu 20.08 (outlook) | **Accu 21.08 dziś-na-dziś** |
|--|----------------------|-----------------------------|
| **21.08** T / jasność / cloud / mm / burze | 25° / 2 / 91% / 5,5 / 38% | **24° / 3 / 88% / 6,4 / 58%** — mokry; burze **↑** |
| **22.08** jasność / cloud | 9 / 29% | **9 / 29%** — bez zmian |
| **23.08** | (brak) | jasność **9**, cloud **18%**, 0 mm |

**Wniosek:** dziś słaby PV (CS4 vs RF). Sobota–niedziela jasne — ryzyko zaniżenia. Primary ICON bez zmian.  
Dzień: [`NOTATKA_2026-08-21.md`](NOTATKA_2026-08-21.md).

### MB 21.08 ~09:12 — Accu vs MB · ICON vs UKMO

| Dzień | Accu | MB (~09:12) | Zgodność |
|-------|------|-------------|----------|
| **21** | 24°, jasność 3, cloud 88%, **6,4 mm**, burze 58% | Deszcz peak **~03–06** (>5 mm/h) + opady w dzień; cloud ~80–100%; RH~95% rano; burze PM (NEMS/NMM) | **Tak** mokry |
| **22** | 23°, jasność **9**, 0 mm | Deszcz **noc/rano** → słońce PM; porywy ↑ (~30, hi-res **50–60**) | **Częściowo** — Accu suche vs MB mokry ranek |
| **23** | 22°, jasność **9**, cloud 18%, 0 mm | Porozumienie — słońce | **Tak** |

ICON ≈ UKMO (21–23). Ensemble kumulacja ~10–20 mm do sob. (outlier ~40). Primary bez zmian.

### Closeout 20.08 (wstępny → formalny 27,4)

Lokalnie front ~17:09 · app **27,3** + stop · formalny **27,4** · best peak_cs4.

---

## AccuWeather — 20.08 ~16:20 (archiwum)

| Dzień | T max | Jasność | Cloud | Opady | P deszcz / burza | Wiatr / porywy | PV |
|-------|------:|--------:|------:|------:|------------------|----------------|-----|
| **20.08** czw. (dziś) | **31°C** (RF 31°) | **7** jasne | **46%** | **0 mm** | 25% / 6% | W 19 / **52** | **wysoka** (do wieczora) |
| **21.08** pt. | **25°C** (RF 27°) | **2** ciemny | **91%** | **5,5 mm** (~2,5 h) | 63% / **38%** | ESE 9 / 28 | **słaba** |
| **22.08** sob. | **23°C** (RF 23°) | **9** b. jasne | **29%** | **0 mm** | 25% / 0% | WSW 22 / 41 | **bardzo dobra** |

Opis 20.08: *„Rosnące zachmurzenie”* · UV 6.  
Opis 21.08: *„Deszcz z przerwami i burza z piorunami”* · UV 4.  
Opis 22.08: *„Słonecznie z możliwym zachmurzeniem małym”* · UV 5.

### Alarmy Accu (20.08)

| Alarm | Okno |
|-------|------|
| **Pomarańczowe** — burze | **17:00 czw. → 03:00 pt.** |
| **Żółte** — powódź | **17:00 czw. → 10:00 pt.** |
| **Żółte** — upały | **13:00–18:00 czw.** |
| Susza | tło |

### Drift vs Accu 19.08 ~11:20

| | Accu 19.08 (outlook) | **Accu 20.08 dziś-na-dziś** |
|--|----------------------|-----------------------------|
| **20.08** T / jasność / cloud | 30°C / 7 / 45% | **31°C / 7 / 46%** — zgodne; porywy ↑52; burze **od 17:00** |
| **21.08** jasność / mm / burze | 3 / 4,0 / 19% | **2 / 5,5 / 38%** — **ciemniej / mokrej** |
| **22.08** | (brak) | jasność **9**, cloud 29%, 0 mm — **powrót słońca** |

**Wniosek:** dziś peak PV do popołudnia, potem ryzyko burz (alert 17:00+). Jutro słaby. Sobota znów jasna. Primary ICON bez zmian.

### MB 20.08 ~16:24 — Accu vs MB · ICON vs UKMO

| Dzień | Accu | MB (~16:24) | Zgodność |
|-------|------|-------------|----------|
| **20** | 31°C, jasność 7, cloud 46%, 0 mm; burze alert **17:00+** | T peak ~30–32°C (teraz ~15:00); cloud ↑ do wieczora ~100%; deszcz dopiero **noc** | **Tak** — Accu alert burz pasuje do MB deszczu nocnego |
| **21** | 25°C, jasność 2, cloud 91%, **5,5 mm**, burze 38% | T ~24–26°C; deszcz peak ~**03:00** (>5 mm/h) + popołudnie; cloud 80–100%; RH rano ~95% | **Tak** „mokry”; MB/ensemble **więcej mm** (spread duży) |
| **22** | 23°C, jasność **9**, cloud 29%, 0 mm | T ~23–24°C; rain spike **noc/rano** (00–03, >5 mm/h) potem przejaśnienia; RH↓ ~45–50% w dzień | **Częściowo** — Accu „b. jasne/suche”; MB trzyma deszcz **noc→rano**, dzień jaśniejszy |

#### ICON vs UKMO (MultiModel)

| Dzień | ICON-12 / 7 | UKMO-10 | Różnica |
|-------|-------------|---------|---------|
| **20** | słońce/chmury PM → deszcz **noc / rano pt.** | jak ICON; **piorun** wczesnym piątkiem (z NMM) | **≈**; UKMO wyraźniej burza nocna |
| **21** | deszcz rano + mieszane PM | deszcz / burza rano, potem przelotne | **≈** |
| **22** | deszcz noc/rano → jaśniej | deszcz z przerwami | drobny timing; Accu optymistyczniejszy na „suche słońce” |

Wiatr: dziś W ~20 km/h, porywy Accu 52 ≈ MB ~45–50; piątek słaby; sobota porywy ↑ (spread do ~45).  
Ensemble: kumulacja deszczu do soboty ~5–45 mm (hi-res agresywny) — nie do gate’u.

Oneshot 19.08 (~25–28 na 20): przy burzach od 17:00 actual może wyjść **niżej** niż surowy peak.

### Closeout 19.08 (jasna środa — test zaniżenia)

| | Actual | Daily RF16 | Daily CS4 | Best raw |
|--|-------:|----------:|----------:|----------|
| **19.08** | **24,7** kWh | 21,0 (**+3,7**) | 19,8 (**+4,9**) | **daily** (RF) |

Modele **zaniżyły** (klasyczny jasny dzień) — hipoteza z 19.08 oneshot potwierdzona. RF bliżej niż CS4.

---

## AccuWeather — 19.08 ~11:20 (archiwum)

| Dzień | T max | Jasność | Cloud | Opady | P deszcz / burza | Wiatr / porywy | PV |
|-------|------:|--------:|------:|------:|------------------|----------------|-----|
| **19.08** śr. (dziś) | **24°C** (RF 24°) | **7** jasne | **59%** | **0,3 mm** (~0,5 h) | 58% / 12% | WSW 17 / **43** | **dobra** |
| **20.08** czw. | **30°C** (RF 30°) | **7** jasne | **45%** | **0 mm** | 25% / 6% | W 19 / **48** | **wysoka** |
| **21.08** pt. | **24°C** (RF 27°) | **3** przyćm. | **86%** | **4,0 mm** (~1,5 h) | 62% / 19% | SSW 7 / 19 | **słaba** |

Opis 19.08: *„Krótkotrwały przelotny opad lub dwa”* · UV 6 · susza = tło.  
Opis 20.08: *„Cieplej”* · UV 6 · bez deszczu.  
Opis 21.08: *„Deszcz z przerwami i burza z piorunami”* · UV 5.

### Drift vs Accu 18.08 ~10:50

| | Accu 18.08 (outlook) | **Accu 19.08 dziś-na-dziś** |
|--|----------------------|-----------------------------|
| **19.08** jasność / cloud / mm | 7 / 52% / 0,9 | **7 / 59% / 0,3** — nadal jasno, mniej mm |
| **20.08** T / jasność / cloud | 28°C / 5 / 76% | **30°C / 7 / 45%** — **wyraźnie lepszy** dzień PV |
| **21.08** | (brak) | 24°C, jasność **3**, cloud 86%, **4 mm** — powrót szarości |

**Wniosek:** środa–czwartek = dobre PV (Accu jasność 7); piątek znów słaby / burzowy. Primary ICON bez zmian. Closeout **19–20** = test, czy modele nie zaniżają jak na słonecznych 12–15.08.

### MB 19.08 ~11:23 — Accu vs MB · ICON vs UKMO (skrót)

Pełne porównanie + oneshot: [`NOTATKA_2026-08-19.md`](NOTATKA_2026-08-19.md).

| Dzień | Accu↔MB | ICON vs UKMO (ikony) | Oneshot ICON RF/CS4/XGB | UKMO−ICON (RF) |
|-------|---------|----------------------|-------------------------|---------------:|
| **19** | zgodność (lekki deszcz rano) | ≈ | ~21 / 21 / 20 | **+4,8** (UKMO za jasny) |
| **20** | zgodność (Accu +2°C vs MB 28) | ≈ słońce | ~25 / **28** / 27 | **+5,3** |
| **21** | zgodność „mokry”; MB hi-res ≫ Accu mm | ≈ deszcz cały dzień | ~11 / 12 / 10 | API UKMO niepełne |

### Closeout 18.08 (szary wtorek)

| | Actual | Daily RF16 | Daily CS4 | Best raw |
|--|-------:|----------:|----------:|----------|
| **18.08** | **17,8** kWh | 20,3 (−2,5) | 19,3 (−1,5) | **peak** (RF) |

Oba modele **zawyżyły** szary dzień; CS4 bliżej niż RF daily, ale best = peak RF. Hipoteza oneshot (~19–21) OK co do rzędu; actual trochę niżej.

---

## AccuWeather — 18.08 ~10:50 (archiwum)

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
**RCB 17.08:** burze, silny wiatr, intensywne opady; możliwe przerwy w prądzie — zgodne z Accu.

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
| **RCB 19.07** (done) | Grad + wiatr · closeout 27,3 · APE ~1,5% |
| **RCB 01.08** (done) | Grad + burze noc 01/02 · koszyk pochmurny |
| **RCB 06–07** (done) | Alerty na 06/07 · burza **07** = wygrana CS4 |
| **RCB 17** (done) | Ten sam typ alertu co 20–21 — burze/wiatr/opad · closeout OK, best CS4 |
| **RCB 20–21** | Burze / silny wiatr / intensywne opady · możliwe blackouty → luki FoxESS/cron |
| **22.08** (done) | Accu jasność **6** — actual **25,1** · peak −2,7% (backfill) |
| **23.08** dziś | Accu jasność **9** / cloud 26% / 0 mm — daily ~**28,6**; ryzyko zaniżenia |
| **24.08** | Accu jasność **9** / cloud **7%** — daily ~**31–33** |
| **25.08** | Accu jasność **8** / **2,6 mm** / burze 52% vs MB ensemble ~suchy — daily ~**33** może zawyżyć |
| **21.08** (done) | Closeout **13,4** · RF −4,4 · CS4 −2,9 · best **peak** |
| **20.08** (done) | Closeout **27,4** · best **peak_cs4** |
| **19.08** (done) | Closeout **24,7** · RF daily +3,7 · CS4 +4,9 · best **daily** |
| **18.08** (done) | Closeout **17,8** · RF −2,5 · CS4 −1,5 · best peak |
| **17.08** (done) | Closeout 21,5 · best **daily_cs4** · **RCB** jak wyżej |

Weekly: [`NOTATKA_WEEKLY_2026-08-23.md`](NOTATKA_WEEKLY_2026-08-23.md) · [`NOTATKA_2026-08-22.md`](NOTATKA_2026-08-22.md) · [`NOTATKA_2026-08-23.md`](NOTATKA_2026-08-23.md)

---

## Archiwum — MB 16.08 ~09:40 (skrót)

16 = peak słońce · 17 = deszcz od ~15 (wtedy) · 18 = ciągły deszcz — **nadpisane** świeższym MultiModelem powyżej.

---

*Źródła: AccuWeather · Meteoblue MultiModel / meteogram / ensemble · Open-Meteo ICON w pipeline.*
