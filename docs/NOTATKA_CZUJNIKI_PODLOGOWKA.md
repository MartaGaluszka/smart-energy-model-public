# Test czujników pokojowych (podłogówka) vs bateria

**Cel:** czy czujniki od **~2.12.2025** zmniejszają **ciepło / kWh**, czy tylko komfort.  
**Nie mieszać** z nawykiem baterii od **7.01.2026** (ForceCharge / G12w).

HDD = suma `(15 − Tśr)⁺` z `weather_data` (ICON). Load / import = `foxess_report_daily` (`loads`, `gridConsumption`). Szczyt load = FoxESS 5 min, pn–pt **6–13** i **15–22**. Tauron = faktura.

---

## Dwie metryki (nie sumować do jednego „oszczędziliśmy X zł”)

| Pytanie | Licz | Nie licz |
|---------|------|----------|
| **Czujniki / podłogówka** | **load domu / HDD** | rachunek zł, import (FC psuje) |
| **Świadoma bateria** | import Tauron + **strefa 1** kWh | load/HDD |

FC (sieć → bateria) zwykle **nie** wchodzi w `loads`. Dlatego X–XI 2026 vs X–XI 2025: najpierw load/HDD, potem Z1.

---

## Oś zmian

| Od | Co |
|----|-----|
| IX 2025 | normalne mieszkanie (remont do VIII) |
| **~2.12.2025** | czujniki w pokojach |
| **7.01.2026** | świadome FC / G12w |
| X–XI 2026 | pierwszy jesienny test **czujniki + bateria** vs X–XI 2025 |

X–XI 2024 **nie porównywać** (brak FoxESS / suszenie posadzek).

Werdykt czujników po X–XI 2026:

| load/HDD vs X–XI 2025 | Znaczy |
|----------------------|--------|
| **≤ −10%** | czujniki coś tną w sezonie przejściowym |
| **−10…+5%** | szum / komfort, nie złotówki |
| **≫ +5%** | inny czynnik (obecność, T, grzałka) — nie winić czujników w ciemno |

Z1 w X–XI 2026 **może spaść** przez baterię nawet przy load/HDD bez zmian.

---

## Obserwacja 18.09.2026 — wrzesień 2025 vs 2026 (przed testem X–XI)

**Kontekst:** formalny werdykt czujników = **load/HDD** w **X–XI 2026 vs X–XI 2025** (§D). Poniżej — **jakość + wczesny sygnał Fox**, żeby nie mylić „pamięci o grzaniu” z samą pogodą zewnętrzną.

Pełny miesiąc, wykresy dnia i godziny: zestawienie September 2025 vs 2026 (canvas lokalny — tylko repo prywatne).

### Obserwacja terenowa

| | **IX 2025** | **IX 2026** |
|--|-------------|-------------|
| **Czujniki w pokojach** | **nie** (od **~2.12.2025**) | **tak** (~10 mies.) |
| **Podłogówka** | wieczorem **ciepłe podłogi**, subiektywnie **za gorąco** | regulacja na **T pokoju** (komfort; efekt kWh → load/HDD jesienią) |
| **Sterowanie** | harmonogram / T zewn. **bez** feedbacku z pokoi | setpointy + możliwość **ograniczyć dojazd / przegrzewanie** |

Wrażenie „już grzaliśmy rok temu we wrześniu” **nie musi** oznaczać chłodniejszej aury — częściej **inercja podłogi + brak pokojowych czujników** (dojazd ciepła po zapotrzebowaniu).

### Pogoda (`weather_data`, okolice Krakowa)

| Okres | T śr. | T min (w oknie) | Uwaga |
|-------|------:|----------------:|-------|
| **2025-09-01 → 17** | **~17,6 °C** | **~9,1 °C** (18.09) | pierwsza połowa IX **cieplejsza** niż 2026 w tym samym kalendarzu |
| **2026-09-01 → 17** | **~16,7 °C** | **~5,5 °C** (07.09) | chłodniejsze **noce** w wybranych dniach |
| **2025-09-18 → 30** | **~13,1 °C** | **~3,5 °C** (28.09) | HDD **~41**; koniec IX — ogrzewanie **obiektywnie** uzasadnione |
| **2026-09-18 → 30** | **~12,7 °C** | **~4,9 °C** (28.09) | HDD **~32**; podobnie chłodno, mniej stopniodni niż 2025 |

Pełniejszy kontekst PV / bilans: [`NOTATKA_2026-09-18.md`](NOTATKA_2026-09-18.md) §Dashboard Fox + Accu kalendarz ~09:13.

### Fox — proxy ciepła / obciążenia (nie rozdziela CO od bojlera)

Źródło: `foxess_report_daily` (`loads`), `foxess_data` (`load_power_kw`). Fox widzi tylko **`loads`** — wnioski o podłogówce = **heurystyka** (noc + HDD), nie licznik CO.

| Metryka | **2025-09-01 → 17** | **2026-09-01 → 17** |
|---------|---------------------:|---------------------:|
| **Load Σ (loads)** | **~221 kWh** | **~196 kWh** |
| **Load / dzień** | **~13,0 kWh** | **~11,5 kWh** |
| **Śr. load 00–05** | **~0,30 kW** | **~0,17 kW** |
| **Śr. load 22–06** | **~0,30 kW** | **~0,20 kW** |
| **Śr. load 18–23** | **~0,36 kW** | **~0,36 kW** |

Godziny: `load_power_kw` w **czasie lokalnym**. W 2025 znacznik ma `+02:00`, w 2026 jest bez offsetu; oba okna czytane tak samo (cywilnie). Noc **12.09.2025** (~1,8 kW) podnosi średnią 00–05; bez niej zostaje **~0,20 kW**, nadal powyżej 2026.

**Wniosek (1–17.09):** rok temu **wyższy nocny load** mimo **cieplejszej** średniej T — spójne z **dłuższym / mniej regulowanym** ogrzewaniem (podłoga), nie z „zimniejszym wrześniem” w pierwszej połowie miesiąca. Wieczór **18–23** w tym oknie jest zbliżony.

### 18–30.09

Wrzesień kończy się **30**. Okno **18–30** to **13 dni**. To tu pojawia się prawie całe HDD miesiąca.

| Metryka | **2025-09-18 → 30** | **2026-09-18 → 30** |
|---------|---------------------:|---------------------:|
| **Load Σ (loads)** | **~158 kWh** | **~173 kWh** |
| **Load / dzień** | **~12,1 kWh** | **~13,3 kWh** |
| **HDD (baza 15 °C)** | **~41** | **~32** |
| **Load / HDD** | **~3,8** | **~5,4** |
| **Śr. load 00–05** | **~0,22 kW** | **~0,19 kW** |
| **Śr. load 22–06** | **~0,24 kW** | **~0,20 kW** |
| **Śr. load 18–23** | **~0,33 kW** | **~0,48 kW** |
| **Import (gridConsumption)** | **~41 kWh** | **~16 kWh** |
| **PV (PVEnergyTotal)** | **~236 kWh** | **~298 kWh** |

**Wniosek (18–30.09):** noce są już zbliżone. Load domu jest **wyższy w 2026** przy **niższym HDD**. Różnica siedzi w wieczorze **18–23** (AGD, bojler — [`NOTATKA_BATERIA_SOC_LOG.md`](NOTATKA_BATERIA_SOC_LOG.md)), nie w dłuższej pracy podłogi po północy. Spadek importu to bateria od **7.01.2026**, nie czujniki. **Load/HDD** tej połówki **nie** jest werdyktem: HDD września jest małe wobec X–XI, a wieczór miesza się z ogrzewaniem. Werdykt zostaje w §D.

**HDD września** na potrzeby load/HDD liczyć dopiero w **X–XI** (próg 15 °C); sam IX często **poniżej progu grzania sezonowego** w danych — obserwacja jakościowa **uzupełnia**, nie zastępuje §D.

### Hipoteza do weryfikacji X–XI 2026

1. **Komfort:** czujniki → mniej epizodów „za gorąco” przy podobnym HDD (log T pokoi opcjonalnie obok Fox).
2. **Energia:** **load/HDD** vs X–XI 2025 — dopiero **≤ −10%** = twardy efekt czujników (§ werdykt).
3. **Mieszanie:** od **7.01.2026** import / Z1 = bateria — **nie** przypisywać spadku sieci czujnikom bez load/HDD.

---

## Obserwacja 08.10.2026 — czy podłogówka już się załącza (1–8.10, 2025 vs 2026)

**Metoda:** `foxess_report_daily` (`loads`, godziny), `foxess_data` (5 min), `weather_data` (HDD baza 15 °C). Fox nie ma licznika CO, więc to **heurystyka** (jak wyżej).  
**Okno nocne = 00:00–04:59.** Godzina **05–06** zostaje poza oknem: rano bywa **pieczenie chleba** (np. **07.10**: skok od **05:11**, do ~**3,4 kW**, **1,5 kWh** w godzinie 05–06) i fałszowało wcześniejsze „00–05”.

| 1–8.10 | **2025** | **2026** |
|--------|---------:|---------:|
| T średnia / T min (średnio) | **7,9 / 4,9 °C** | **12,9 / 6,3 °C** |
| HDD | **57** | **17** |
| Load domu | **15,7 kWh/dz.** | **13,0 kWh/dz.** |
| Noc 00–04, średnia / mediana | **0,28 / 0,25 kW** | **0,21 / 0,20 kW** |
| Wieczór 18–22 | **2,2 kWh** | **1,8 kWh** |
| Import (Fox) | **5,3 kWh/dz.** | **1,15 kWh/dz.** |
| PV | **14,7 kWh/dz.** | **26,1 kWh/dz.** |

| Noc 00–04 (kW) | Średnia | Mediana |
|----------------|--------:|--------:|
| lato 2026 (VII–VIII) | 0,211 | 0,200 |
| IX 2025 | 0,263 | 0,180 |
| IX 2026 | 0,198 | 0,160 |
| 1–8.X 2025 | 0,280 | 0,250 |
| **1–8.X 2026** | **0,212** | **0,200** |
| 9–31.X 2025 | 0,377 | 0,320 |

**Wniosek:** w 2026 noc jest na poziomie **letnim** (0,21 kW), a load **13,0 ≈ lato 13,4 kWh/dz.** — **brak śladu grzania podłogi**. Rok temu noc rosła z chłodem (do **0,38 kW** w drugiej części X; **03.10.2025** T min −2 °C → **3,4 kWh** w 00–05), więc wtedy grzało. Różnica to w dużej mierze **pogoda** (HDD **17** vs **57**), nie dowód działania czujników; werdykt nadal z §D (load/HDD w X–XI).

**Pojedyncze skoki (nie podłoga):** **07.10** — poranek **05–07**, pieczenie. **30.09** — nieregularnie (00–01, 02–03, 05–06), nie umiem przypisać. **04.10** — jedyna noc z plateau **0,3–0,5 kWh/h** w godz. 00–04 (typowo 0,1–0,2); jedna noc, **do sprawdzenia w logu sterowników**.

**Przy werdykcie X–XI:** liczyć noc **00–04**, a poranek **05–07** z pieczeniem wyłączyć lub oznaczyć w `household_events`. Import, eksport i autokonsumpcja zależą głównie od PV i baterii, więc o grzaniu nie mówią nic.

**Kontekst PV (08.10):** produkcja X 2026 do 8.10 **208,9 kWh** vs cały X 2025 **392,2 kWh**; brakuje **183,3 kWh** (**8,0 kWh/dz.** przez 23 dni). 9–31.10.2025 dało **274,6 kWh** (śr. **11,9**, mediana **9,9**). Import do końca miesiąca zależy od pogody i grzania: **~36 kWh** (jak dotąd) do **~154 kWh** (jak 2025).

---

## A. Baseline — bez świadomego FC

| Okres | Czujniki | FC | n | T śr. | HDD | Load kWh | Load/d | **Load/HDD** | Import Fox | Peak load kWh | Peak/HDD |
|-------|----------|----|--:|------:|----:|---------:|-------:|-------------:|-----------:|--------------:|---------:|
| **X 2025** | nie | nie | 31 | 8,6 | 200 | 492 | 15,9 | **2,47** | 187 | 237 | 1,19 |
| **XI 2025** | nie | nie | 30 | 3,6 | 342 | 762 | 25,4 | **2,23** | 560 | 286 | 0,83 |
| **X–XI 2025** | nie | nie | 61 | 6,1 | 542 | 1254 | 20,6 | **2,31** | 747 | 523 | 0,96 |
| **2–31.12.2025** | **tak** | nie | 30 | 1,4 | 409 | 936 | 31,2 | **2,29** | 805 | 459 | 1,12 |
| **1–6.01.2026** | tak | nie | 6 | −1,3 | 98 | 220 | 36,6 | **2,25** | 180 | 96 | 0,98 |

XII vs XI (pogoda): ten sam apetyt ~2,3 kWh/HDD → czujniki **~0%**. Surowy grudzień droższy, bo zimniej.

---

## B. Od 7.01 — czujniki **i** bateria (nie interpretować jako efekt czujników)

| Okres | n | T śr. | HDD | Load kWh | **Load/HDD** | Import Fox |
|-------|--:|------:|----:|---------:|-------------:|-----------:|
| **7–31.01.2026** | 25 | −4,4 | 486 | 1088 | **2,24** | 985 |
| **II 2026** | 28 | −0,3 | 427 | 928 | **2,17** | 741 |
| **III 2026** | 28 | 6,6 | 234 | 573 | **2,45** | 172 |

Load/HDD jak przed FC. Zmienił się **import / strefa**.

---

## C. Tauron (zł i strefy) — tu widać baterię

| Miesiąc | Z1 kWh | Z2 kWh | Pobór | Brutto zł | Oddanie | Faza |
|---------|-------:|-------:|------:|----------:|--------:|------|
| **X 2025** | 87 | 99 | 186 | 217 | 77 | bez czujników, bez FC |
| **XI 2025** | 177 | 390 | 567 | 533 | 56 | j.w. |
| **X–XI 2025** | **264** | **489** | **753** | **750** | **133** | **baseline jesień** |
| **XII 2025** | 309 | 539 | 848 | 783 | 0 | czujniki, bez FC |
| **I 2026** | **178** | **997** | 1175 | 925 | 8 | czujniki **+ FC** (Z1↓ Z2↑) |
| **II 2026** | 59 | 684 | 743 | 582 | 71 | j.w. |
| **X 2026** | | | | | | *wpisać* |
| **XI 2026** | | | | | | *wpisać* |
| **X–XI 2026** | | | | | | vs wiersz X–XI 2025 |

---

## D. Test docelowy — uzupełnić po 30.11.2026

Źródło: `foxess_report_daily` + `weather_data` (HDD próg 15°C) + faktura Tauron.

| | **X–XI 2025** (jest) | **X–XI 2026** (wpisać) | Δ |
|--|---------------------:|----------------------:|--:|
| Czujniki | nie | tak | |
| Świadoma bateria | nie | **tak** (od I 2026) | |
| n dni | 61 | | |
| T śr. °C | 6,1 | | |
| HDD | 542 | | |
| Load kWh | 1254 | | |
| Load / d | 20,6 | | |
| **Load / HDD** | **2,31** | | **← czujniki** |
| Import Fox kWh | 747 | | |
| Peak load kWh | 523 | | |
| Peak / HDD | 0,96 | | |
| Tauron Z1 kWh | 264 | | **← bateria** |
| Tauron Z2 kWh | 489 | | |
| Tauron pobór | 753 | | |
| Tauron zł | 750 | | nie werdyktować samym zł |
| Oddanie kWh | 133 | | |

**Jak czytać Δ:**  
load/HDD **< −10%** → czujniki.  
Z1 w dół przy load/HDD ≈ 0 → bateria / G12w.  
Zł w dół przy load/HDD ≈ 0 i Z1 w dół → **nie przypisywać czujnikom**.

---

## Notatki do wpisania 2026

- Obecność / wyjazd (jak kajaki 5.09) — `household_events`  
- Start grzania (pierwszy tydzień z load/HDD ~2,2)  
- Czy grzałka bufora dostała blokadę 15–22 pn–pt (osobny efekt)  
- [x] **18.09.2026** — obserwacja podłogi IX 2025 vs czujniki IX 2026 + Fox/pogoda (§ Obserwacja 18.09.2026)
- [x] **08.10.2026** — 1–8.10 2025 vs 2026: podłogówka jeszcze **nie** widoczna w nocy 00–04 (§ Obserwacja 08.10.2026); poranek 05–07 = pieczenie, nie wliczać
- [ ] Sprawdzić **04.10** (plateau nocne) w logu sterowników, jeśli jest
- [ ] Zapisać w `household_events` pieczenie chleba (np. **07.10 ~05:10–07:00**), żeby odfiltrować poranek przy werdykcie
- [x] **01.10.2026** — domknięcie **18–30.09** (load, noc, HDD)

Powiązane: [`PLAN_BATERIA_JESIEN_ZIMA_2026.md`](PLAN_BATERIA_JESIEN_ZIMA_2026.md) · [`NOTATKA_BATERIA_SOC_LOG.md`](NOTATKA_BATERIA_SOC_LOG.md) · [`NOTATKA_2026-09-05.md`](NOTATKA_2026-09-05.md) · [`NOTATKA_2026-09-18.md`](NOTATKA_2026-09-18.md)
