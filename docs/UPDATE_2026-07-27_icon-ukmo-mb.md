# UPDATE — ICON vs UKMO vs Meteoblue (2026-07-27)

**Typ:** notatka operacyjna (zły dzień / konwekcja)  
**Status:** UKMO nadal **tylko obserwacja** — produkcja = `icon_seamless`  
**Źródła:** plant CSV FoxESS · AccuWeather · Meteoblue ensemble · oneshot OM ICON/UKMO

---

## Kontekst

- Sync FoxESS API **40402** (05:00 i 12:00) → luka danych; uzupełnione plant CSV.
- Obserwacja dachu ~15:45–15:55: **ciemno, pełne chmury, bez słońca**; deszcz **zaczyna ~15:55**.

### Plant CSV (∫ Solar)

| Dzień | Zakres | Solar kWh | Import | Export | SoC |
|-------|--------|-----------|--------|--------|-----|
| 26.07 | 00:02–23:58 | **34.36** | 0.99 | 14.81 | 78→48% |
| 27.07 | 00:03–**15:30** (częściowy) | **15.85** | 0.59 | 3.30 | 47→99% |

Prognoza midday RF (prod ICON): **~18.0 kWh** (CS4 ~16.1).  
Godziny 06–14: bias **+8%**, MAE **0.79 kWh/h** — suma OK, timing słaby (09 over / 14 under).

---

## Oneshot Open-Meteo (GPS dach) — 27.07

| Model | Σ mm | 6–11 | 12–15 | first_wet (≥0.2) | cloud śr. | RF raw (16) vs CSV* |
|-------|------|------|-------|------------------|-----------|---------------------|
| **ICON** (prod) | **3.4** | 0.7 | 1.1 | **6h** | **87%** | 18.1 vs 15.8 → **~86%** |
| **UKMO** | **7.0** | 0.3 | **4.4** | **7h** | **66%** | 23.1 vs 15.8 → **~54%** |

\*CSV do 15:30 — dzień niepełny; wieczorny closeout doprecyzuje.

Pliki: `data/processed/oneshot_icon_vs_ukmo_precip.csv`, `oneshot_icon_vs_ukmo_hourly_20260727.csv`, `oneshot_rf_icon_vs_ukmo_*.csv`.

---

## AccuWeather / Meteoblue (UI)

| Źródło | Cloud | Opad | Uwagi |
|--------|-------|------|-------|
| Accu dziś | **54%** | **6.0 mm** (P=95%, ~3 h), burze 19% | Ostrzeżenie burze 10–17; Brightness 6; gust 50 |
| MB ensemble | ~**100%** w szczycie PV | konsensus **~3 mm**, góra **~7.5 mm**, peak ~15:00 | Ikony deszcz/burza 15–18 |
| Dach | wizualnie ~100%, ciemno | start deszczu **~15:55** | Bez deszczu do ~15:50 |

**28.07 Accu:** cloud 12%, AccuLumen 9, 0 mm (nasz ICON midday: cloud śr. ~62%, **28.8 kWh** — rozjazd).  
**29.07 Accu:** cloud 4%, AccuLumen 10 — zgodne z naszym **~34 kWh**.

---

## Werdykt ICON vs UKMO (ten dzień)

1. **Suma PV:** ICON bliżej CSV/RF; UKMO **zawyża** (~+5 kWh raw) — jak w oneshotach 19–25.07.  
2. **Deszcz popołudniu:** UKMO (4.4 mm w 12–15) + MB peak ~15:00 bliżej dachu niż ICON `first_wet=6` (lekki poranny sygnał). Accu 6 mm ≈ UKMO 7 mm.  
3. **Cloud %:** ICON 87% / MB ciemne niebo ≈ obserwacja; Accu 54% i UKMO 66% zbyt jasne jak na „ciemny dach”.  
4. **Decyzja:** **nie** zmieniać `OPENMETEO_MODEL`. UKMO zostaje w protokole „złe dni” (mm / first_wet), nie w prod.

`weather_notes` 27.07: AccuWeather + Meteoblue + user_observation + oneshot ICON/UKMO.

---

## TODO wieczór

- [x] CSV 22:42 → re-import plant + evening closeout (`--skip-sync`)
- [x] Finalne app/CSV: **19.14 kWh** · daily **19.10** (APE ~0.2%) · midday 17.97 · szczyt 14:00 (3.83)
- [ ] Jutro 05:00: sprawdzić czy API FoxESS 40402 spadł
