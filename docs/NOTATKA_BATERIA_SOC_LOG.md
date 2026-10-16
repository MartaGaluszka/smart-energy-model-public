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

### 2026-10-15 → 16.10 — NOC (FC do 100% — zapomniane wyłączenie) + rano ~30% przed PV

Accu **16** jasny→**RF** (Lumen **9 / 11%**) · ENS @05 **~22** · dzień pod pranie / mocne PV.  
Raport: **zapomniane wyłączenie ładowania o 22:00** → poszło do **100%**; rano **~30%** zapasu zanim dach zaczął produkować.

| Moment | SoC | Uwaga |
|--------|----:|-------|
| czw. **~21:57** | **63%** | przed FC (po wieczornym load) |
| czw. **~22:01–~22:28** | **64%→100%** | **ForceCharge** · grid/bat **~11 kW** · **~27 min** · **+36–37 pp** ≈ **~3,7–3,8 kWh** z taniej nocy |
| czw. **~22:28** | **100%** | FC domknięte (brak ręcznego stopu wcześniej) |
| pt. **~06:00** | **66–67%** | po nocy ciepła |
| pt. **~07:50** | **45%** | przed mocniejszym PV |
| pt. **~08:30** | **30%** | min przed sensowną produkcją · PV **~0,9 kW** |
| pt. **~08:40–08:45** | **29%** | PV **>1,3 kW** · dół SoC · potem ładuje |
| pt. **~09:00** | **31%→↑** | dach przejmuje · **~10:00** już **~50%+** |

**Werdykt:** przy Accu **jasny/RF** i ENS **~22** FC **nie było potrzebne** — **63%@22** pewnie starczyłoby na rano (min wyszło **~29–30%**, czyli tuż przy progu komfortu, ale **bez luki sieci**). Koszt pomyłki: **~4 kWh** taniego importu w nocy; zysk: spokojny bufor **~30%** przed PV i zero śniadania z sieci. Lekcja UI jak **13→14**: **timer / ręczne wyłączenie FC o 22:xx** — ForceCharge sam nie „wie”, że jutro jest słońce. Fox **16.10** do południa: generation już **~20 kWh**, gridConsumption **~0,4** (dzień słoneczny ratuje bilans).

### 2026-10-16 — DZIEŃ (dużo AGD: 2× pranie · zmywarka · chleb · obiad · suszarka · kolacja)

Accu **jasny→RF** · raport użytkownika **~16:40** · Fox sync do **~18:17**.

| Moment | Load / SoC (Fox) | Uwaga |
|--------|------------------|-------|
| rano **~08–09** | load peak **~3,9 kW** · SoC **29%→↑** | start PV + dom; pranie #1 w toku (raport: **2× pranie po ~2,5 h**, jedno po drugim) |
| **~11–13** | load μ **~1,3** / peak **~2,9** · SoC **85%→99%** · PV **~3,9–4,6 kW** | pranie #2 / ciąg AGD · nadwyżka do sieci (grid ujemny) |
| **~13:28–13:51** | load **2,2–3,9 kW** · PV **~4,0–4,3** · SoC **99%** · grid **~0** (eksport spada) | **13:35:** zmywarka **koniec** (~2 h) · chleb (Lidl) **~20 min do końca** · **indukcja** obiad + kawa |
| **~14–16** | load niski · SoC **98–99%** · PV **~2–3,7** · eksport **~1–3 kW** | przerwa przed suszarką |
| **~16:10–17:40** | load ciągły **~0,6–0,8 kW** · suma **~1,2 kWh** · SoC **98→94** · import **~0** | **suszarka** finisz (po 2× praniu); PV spada **~1,9→0** |
| **~17:45–18:15** | load **~0,73 kWh** · peak **3,37 kW** · SoC **93→87** (−6 pp) · import **~0,02** | **kolacja** ~30 min na indukcji (bez PV) — z baterii |

**Fox dzień (report do ~18:17):** generation **~20,4** · loads **~14,8+** · feedin **~9,6** · gridConsumption **~0,4** (godz. load **13:00 = 2,1 kWh** najwyższa).

**Werdykt:** szczyt **13:35** (zmywarka + chleb + obiad) **z dachu**. Suszarka **~1,2 kWh** z baterii przy SoC **≳90%** — OK. Kolacja wieczorem **~0,75 kWh / peak 3,4 kW** (lekka indukcja) — typ `kolacja` w kalendarzu (§10.1). **Update planowania:** budżet `kolacja` = jak `sniadanie` **~1,3–1,4 kWh** (często czajnik + ciepłe / piekarnik); case 16.10 był dolnym końcem.

**Kalendarz:** typy `pranie` / `suszarka` / `chleb` / `obiad` / `kolacja` + pakiet „dzień prania” → §10.1 [`PROJEKT_APLIKACJA_MOBILNA.md`](PROJEKT_APLIKACJA_MOBILNA.md).

### 2026-10-14 → 15.10 — NOC + rano (FC 100% · śniadanie na styk · zmywarka ~9:00)

Accu **15** Lumen **7 / 52%** → paper **RF** · ENS @05 **~15,5** · Tnoc (Accu/MB) **~3°C**.  
Fox sync do logu: do **~05:00** (SoC **55%**); śniadanie / zmywarka — raport użytkownika **~09:45**.

| Moment | SoC | Uwaga |
|--------|----:|-------|
| śr. **~22:00** | **21%** | przed FC (drogi szczyt zjadł zapas po ciemnym **14.10**) |
| śr. **~22:05–~22:50** | **21%→~100%** | **ForceCharge** · moc **~9–11 kW** / grid **~9–12 kW** · ostatni sample Fox **88%@22:41** (luka do **00:02**); cel użytkownika **100%@22** |
| czw. **~00:02** | **95%** | już rozładowanie · krótki impuls load **~1,7 kW** |
| czw. **~01:45–02:00** | **88%→83%** | cykl ciepła ~**2,3–2,5 kW** |
| czw. **~02:08–02:35** | **82%→66%** | dłuższy cykl / podłoga · peak **~3,5 kW** · **−16 pp** |
| czw. **~04:36–04:45** | **60%→55%** | kolejny impuls ~**2,7 kW** |
| czw. **~05:00** | **55%** | ostatni sync Fox przed śniadaniem |
| czw. **śniadanie** | **na styk** | raport: **100%@22 starczyło prawie na styk** na poranne śniadanie (bez luki sieci jak 13→14) |
| czw. **~kilka min przed 9:00** | — | **zmywarka załączona** (trwa @~09:45) |

**Werdykt:** lekcja z **13→14** (cel **~90–100%** przy zimnie) **potwierdzona** — **100%@22** domknęło śniadanie **na styk**, bez wcześniejszego minSoc + godziny z sieci. Noc zjadła dużo ciepłem (**~02** i **~04**), nie samym posiłkiem. Zmywarka **~9:00** — przy Accu **mix/RF** i Lumen **7** warto sprawdzić, czy już idzie z PV, czy jeszcze z baterii/sieci (sync Fox po **05:00** do dogrania). Szczegóły: [`NOTATKA_2026-10-15.md`](NOTATKA_2026-10-15.md).

### 2026-10-12 → 13.10 — NOC + rano (grzejnik łazienka + śniadanie)

Accu **13** Lumen **4 / 73%** → paper **CS4** · ENS @05 **20,75** (zawyżone vs oczekiwanie Accu) · Tnoc **~5°C**.

| Moment | SoC | Uwaga |
|--------|----:|-------|
| pn. **~18:00** | **86%** | po PV **12.10** Fox **13,6** |
| pn. **~20:00** | **73%** | spadek wieczorem |
| pn. **~22:00** | **50%** | **≥30%** → bez BUFOR RANO / bez FC (myśl: starczy) |
| wt. **~02:52** | **31%→28%** | **bojler** ~**0,4 kWh** · peak **2,64 kW** (bateria) |
| wt. **~05:00** | **24%** | baza + **grzejnik łazienkowy** (suszenie ręczników, cała noc) |
| wt. **~06:10–06:25** | **22%→14%** | **bufor ciepła / podłoga** ~**0,6 kWh** · peak **2,62 kW** |
| wt. **~07:00** | **10%** | minSoc · bateria nie oddaje |
| wt. **~07:08–08:20** | **10%** | **śniadanie** z sieci: jajecznica + kawiarka indukcja + czajnik · piki **2,2 / 1,5 / 3,8 kW** · ~**1,3–1,5 kWh** / import ~**1,5** |
| wt. **~09:19** | **14%** | PV ~**3,2 kW** · ładuje |

**Werdykt:** **50%@22 nie starczyło na śniadanie**, choć reguła 30% milczała. Pogoda: chłodno (**~5°C**) → bufor rano jak 12.10. Extra: **`grzejnik_lazienka`**. Kalendarz: eventy `grzejnik_lazienka` (12.10) + `sniadanie` (13.10). Budżet FC: §10.1 PROJEKT.

### 2026-10-13 — DZIEŃ + decyzja nocy → 14.10

Fox PV **~10,2** · Accu **CS4** · ENS peak **~14** (ostrożnie). Tnoc →14 **~2°C**.

| Moment | SoC | Uwaga |
|--------|----:|-------|
| **~09:19** | **14%** | start ładowania z PV |
| **~11:00** | **56%** | |
| **~14:00** | **72%** | |
| **~15:10–15:46** | **72%→54%** | **podłogówka / bufor ciepła (dzień)** · load **~1,7 kWh** · peak **~2,3–3,0 kW** · z baterii (PV ~0,3 kW) · **−18 pp** |
| **~17:00** | **54%** | |
| **~20:00** | **38%** | |
| **~22:04** | **31%** | |
| dzień / rano | — | **grzejnik łazienkowy wyłączony** (po nocy 12→13) |
| **od 22:07** | — | **grzejnik łazienkowy załączony** na noc 13→14 (suszenie ręczników) |
| **FC od ~22:15** | plan **65% / do 22:35** | ustawione ręcznie |
| **po FC** | **80%** | **nie wyłączyło się samo** o 22:35 · poszło **31→80%** (**+49 pp** ≈ kalibracja „30 min ≈ +50 pp”) · wyłączenie ręczne / po fakcie |

**Sygnatura podłogówki (dzień):** plateau **~2,5–3,0 kW** przez **~30–35 min**, SoC spada równo, sieć ~0, PV niski — odróżnić od bojlera (krótszy, ~2,4–2,6 kW) i kuchni (szpice nierówne). Szczegóły: [`NOTATKA_CZUJNIKI_PODLOGOWKA.md`](NOTATKA_CZUJNIKI_PODLOGOWKA.md) · [`NOTATKA_2026-10-13.md`](NOTATKA_2026-10-13.md).

**Werdykt plan / FC:** cel **65% @22:35** nieskuteczny bez ręcznego stopu — Fox **ForceCharge nie uciął** o zaplanowanej godzinie; doszło do **80%**. Lekcja UI: **timer końca FC pilnować ręcznie**.

### 2026-10-13 → 14.10 — NOC closeout + rano (późne śniadanie ~09:00)

FC **80%@22:35** · grzejnik łazienkowy od **22:07** · Tnoc **~2°C**.

| Moment | SoC | Uwaga |
|--------|----:|-------|
| wt. **22:35** | **80%** | po FC (plan był 65%) |
| śr. **~01:18–01:32** | **69%→~56%** | cykl ciepła ~**3,1–3,4 kW** (bateria) |
| śr. **~03:28–03:38** | **~54%→44%** | kolejny cykl ~**3,2–3,4 kW** |
| śr. **~05:25–05:35** | **~40%→29%** | bufor/podłoga ~**0,9 kWh** · peak **3,3 kW** |
| śr. **~06:46–06:56** | **~28%→18%** | kolejny ~**0,9 kWh** · peak **3,6 kW** |
| śr. **~07:54** | **10%** | minSoc — **zanim** śniadanie |
| śr. **~07:54–08:44** | **10%** | **~1 h z sieci** · load ~**1,9 kWh** / import ~**1,4 kWh** · peak ~**2,7 kW** (dom bez baterii) |
| śr. **~09:24–10:05** | **16%→11%→13%** | **śniadanie późniejsze** (wszyscy wstali później) · load ~**1,6 kWh** · **prawie bez sieci** (PV już **0,5–4,4 kW**) |

**Werdykt ex post:** nawet **80%@22** **nie starczyło** do PV przy **Tnoc ~2°C** + grzejnik + **4 cykle ciepła** w nocy/rano. Lukę **~1 h** zrobiło **ciepło 05–08**, nie samo śniadanie — posiłek ~**09:00** już złapał dach. Lekcja kalendarza: późne `sniadanie` ≠ mniejszy budżet nocy; przy zimnie liczy się **bufor do pierwszej sensownej PV (~8–9)**. Na taką noc cel raczej **~90–100%** albo mniej grzania z baterii. Szczegóły: [`NOTATKA_2026-10-14.md`](NOTATKA_2026-10-14.md).

---

### 2026-10-11 — DZIEŃ (w toku) + decyzja nocy → 12.10

Accu 11.10 **mix→RF** · ENS @05 **12,04** · Fox minSoc w app **10%**.

| Moment | SoC | PV / uwagi |
|--------|----:|------------|
| **~05:00** | **36%** | start dnia; bez FC nocy |
| **~13:00–17:40** | **72%→47%** | **Przetwory** · load **~10,4 kWh** · peak **~5,6 kW** · porcja: 3 kg buraków · 1,5 kg cebuli · 1,5 kg papryki · `household_events` type=`przetwory` impact=`up` (kalibracja kalendarza app) |
| **~20:15** | **~38%** | po przetworach; weekend tanio |
| **~22:38** | **28%** | dalszy spadek wieczorem (nie zatrzymaliśmy się na 38%) |
| noc → pn. | plan: do **6:00** bez FC | ENS jutro **20,6** · Tnoc **~5°C** |
| **pn. 12.10 ~03:15–03:50** | **18%→14%** | **bojler** **0,42 kWh** · peak **2,43 kW** |
| **pn. ~04:56** | **11%** | blisko podłogi |
| **pn. ~05:50–06:00** | **10%** | **bufor ciepła** **0,58 kWh** · peak **2,06 kW** (już z sieci) |
| **pn. 06:30–08:00** | **10%** | **śniadanie** **1,25 kWh** · import **1,37** · peak **2,61 kW** |

**Werdykt ex post:** na **bazę nocną** starczyło; **nie** na **bojler ~03:30 + bufor ciepła po 5:00 + śniadanie pn.** przy minSoc **10%**. Po dniu **`przetwory`**: próg **SoC &lt;30% o ~22:00** (nie @20:00 — tu **38%→28%** między 20:15 a 22:38) → na **pn.** krótki **FC w taniej nocy** albo cel **≥25–30%** do 6:00. Szczegóły: [`NOTATKA_2026-10-12.md`](NOTATKA_2026-10-12.md).

---

### 2026-10-10 → 11.10 — closeout 10.10 + NOC + rano 11.10

Accu 10.10 **mix→RF** (po fakcie) · pick z 08–09 **CS4** · PV **22,0** (ENS @05 **15,85**, **−28%**).

| Moment | SoC | PV / uwagi |
|--------|----:|------------|
| **sob. 10.10 ~8:00** | **42%** | dołek przed PV |
| ~11:00 | **91%** | Fox **5,1 kWh/h** o 11:00 |
| ~12:00–16:00 | **100%** | eksport po pełnej baterii |
| ~17:00 | **79%** | weekend, tanio |
| **~22:00** | **37%** | bez ForceCharge (ENS na nd. **11,9** ≥ 8) |
| **00:00–05:00** | **36–37%** | plateau, **bez importu** |
| closeout 10.10 | **37%** EOD | PV **22,0** · load **16,0** · eksport **9,3** · import **1,4** · charge **6,5** / discharge **8,4** |
| **nd. 11.10 ~05:00** | **36%** | ENS **12,04** · Accu mix→RF |

**Werdykt:** sobota: prognoza **15,9** zaniżona o **28%**, ale decyzja bez zakupu słuszna i bateria wróciła do **100%** do 12:00. Wieczór: zrzut do **37%** (weekend tanio). Noc nd.→pn.: ENS **20,6** ≥ 12, **zostawić naładowaną do 6:00**.

---

### 2026-10-09 → 10.10 — DZIEŃ (closeout 09.10) + NOC + DZIEŃ 10.10 (w toku @~16:00)

Accu 09.10 **mix→RF** · PV **18,1** (ENS @05 **19,79**, midday **18,10**). 10.10: ENS **15,85**, fakt **~22** (stan 15:57 **21,7**).

| Moment | SoC | PV / uwagi |
|--------|----:|------------|
| **pt. 09.10 ~8:00** | **66%** | min przed PV; wcześniej **63%** o 08:22 w app |
| ~11:00 | **91%** | PV rośnie, ładowanie z dachu |
| ~12:00–15:00 | **100%** | eksport po pełnej baterii |
| ~17:00 | **95%** | drogie 15–22 |
| ~22:00 | **73%** | bez ForceCharge (ENS na sob. **15,9** ≥ 12) |
| **00:00 / 02:00–05:00** | **60% / 59%** | plateau, **bez importu** |
| **sob. 10.10 ~8:00** | **42%** | dołek przed PV (weekend, tanio cały dzień) |
| ~11:00 | **91%** | Fox **5,1 kWh/h** o 11:00 |
| ~14:00 | **100%** | do 15:57: PV **21,7**, eksport **9,2**, import **1,0**, load **9,4** |
| closeout | | *(uzupełnij wieczór 10.10)* |

**Werdykt:** piątek: dzień **18,1** i bateria pełna od **12:00**, noc bez zakupu OK (**59%** rano po drogich godzinach 15–22). Sobota: prognoza **15,9** zaniżona o **~28%**, ale decyzja bez zakupu była słuszna i bateria wróciła do **100%** do 14:00. Noc sob.→nd.: ENS **11,9** (strefa 8–12), bez zakupu. Tydzień: lekcja 20.10.2025 (nd. wieczór → pn. do 6:00) dotyczy **11→12.10**.

---

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
| **~18:25** (app) | — | PV dnia **21,1 kWh** (vs daily RF **12,5**); nadal **~30 W** na instalacji → do końca dnia możliwy niewielki przyrost |
| ~22:00 przed ewentualnym doładowaniem | — | decyzja: 27 jasny → **nie** doładowywać |
| closeout 26 | — | PV **21,1** · zużycie / sieć / SoC EOD *(uzupełnij)* |

**Werdykt dzień (~18:25):**

> MB clearing PM **potwierdzony**. Actual **21,1** vs RF **12,5** (**+8,6**) — wczoraj **4,4**.  
> SoC pełna od **12:38** → eksport (do 14:00 już **4,1**). Nocny FC 24→75% **za agresywny** ex post.  
> Wieczór **27–28**: **nie** ForceCharge.

### 2026-09-17 — DZIEŃ (w toku @~15:15)

Accu **CS4** · ENS **9,64** · MB deszcz AM + clearing PM (częściowo **~14:52**). PV **under** prognozy; Fox wykres + app.

| Moment | SoC | PV / uwagi |
|--------|----:|------------|
| rano | **~65%** | deszcz do **~7:30** · duże zachmurzenie |
| **~7:30** | **~45%** | dołek SoC (obciążenie / brak PV) |
| **~09–10** | rośnie | krótkie okno **~1,2 / 1,0 kWh/h** |
| **~12:30** | **~95%** | szczyt SoC · **bez 100%** (niski PV vs jasne dni) |
| **~14:30** (wykres) | spadek | load **~2,8 kW** (AGD/dom) |
| **~14:52** (teren) | | słońce · **~1,7 kW** chwilowo |
| **~14:56** (teren) | | **~3,64 kW** chwilowo |
| **~15:00** (wykres) | ↓ | rozładowanie baterii **~4 kW** — load > chwilowe PV mimo clearing PM |
| **~16:54** (app/UI) | | Fox **9,1 kWh** · godz. **15=2,5** · **16=1,2** |
| **~18:08** (closeout ~) | | Fox **10,2 kWh** · **17=0,9** · **18=0,1** · Δ ENS **+5,8%** |
| closeout | | zużycie / sieć / SoC EOD *(uzupełnij wieczór)* |

**Werdykt dzień (~18:08):** **MB clearing PM** uratował dobę — **10,2** vs ENS **9,64** · profil **11–14** under / **15–17** over w modelu · SoC **~95%** w południe OK.

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
