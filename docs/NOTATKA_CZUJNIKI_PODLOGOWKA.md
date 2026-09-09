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

Powiązane: [`PLAN_BATERIA_JESIEN_ZIMA_2026.md`](PLAN_BATERIA_JESIEN_ZIMA_2026.md) · [`NOTATKA_BATERIA_SOC_LOG.md`](NOTATKA_BATERIA_SOC_LOG.md) · [`NOTATKA_2026-09-05.md`](NOTATKA_2026-09-05.md)
