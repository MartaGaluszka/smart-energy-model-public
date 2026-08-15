# Notatka pogoda — 15–17.08.2026

**Data notatki:** 2026-08-15 ~11:00  
**Lokalizacja:** okolice Krakowa (dokładne GPS tylko w lokalnym `.env`)  
**Produkcja ML:** Open-Meteo **ICON** (`icon_seamless`)  
**AccuWeather / Meteoblue / UKMO:** obserwacja ręczna — **nie** wpływają na RF primary

---

## Skrót

| Dzień | AccuWeather | Meteoblue / ensemble | UKMO vs ICON | PV (oczekiwane) |
|-------|-------------|----------------------|--------------|-----------------|
| **15.08** sobota | 33°C, słońce, cloud **3%**, jasność **10**, 0 mm, alert upały | ~32–33°C, 0 mm, zgodność modeli wysoka | **UKMO ≈ ICON** (słońce) | **bardzo wysoka** |
| **16.08** niedziela | 34°C, cloud **23%**, jasność **8**, 0 mm, porywy ~35 | ~33–35°C, 0 mm; wiatr po południu | **UKMO ≈ ICON** | wysoka |
| **17.08** poniedziałek | 20°C, cloud **94%**, jasność **2**, **14,7 mm**, P=87%, burze 35% | front: deszcz od południa (~15 mm konsensus, spread 5–30+), chmury ~100% | **UKMO ≈ ICON** (deszcz ~13:00+); GFS bywa wcześniej; ARPEGE/NEMS → burze | **słaba** |

---

## UKMO (nie prod)

- Weekend: zgodny z ICON — nie ma sensu oneshot podmiany pogody.
- Poniedziałek: timing deszczu jak ICON (popołudnie), nie outlier jak bywało na półsłonecznych dniach.
- Primary zostaje **RF16 + ICON**; CS4/XGB+TS = shadow (CS4 często bliżej w dni pochmurne).

---

## Operacyjnie

- **15–16.08:** peak produkcji; weekly retrain niedziela 04:30 = odświeżenie wag (bez zmiany primary).
- **17.08:** dzień obserwacji Accu/MB/UKMO vs ICON + closeout shadow CS4 vs RF.
- Walidacja live (wykresy): closeouty do **14.08** w `july_validation_plot` / `production_validation_plot` (notebooki 02 / 03 / 05).

---

*Źródła UI: AccuWeather (dziś-na-dziś) · Meteoblue MultiModel / meteogram · Open-Meteo ICON w pipeline.*
