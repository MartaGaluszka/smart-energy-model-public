# Review modeli × pogoda (closeouty)

**Wygenerowano:** 2026-10-31 (przegląd modeli × pogoda)  
**Zakres closeoutów:** 2026-07-14 → 2026-10-30 (**109** dni)  
**Metryka:** |APE| % = |Fox − prognoza| / Fox × 100 · pogoda: średnie cloud **6–20** (ICON w DB)  
**Nie w tabeli:** UKMO solo / oneshot ½ — tylko w notatkach dnia (`oneshot_rf_icon_vs_ukmo.py`).  

**Skrypt:** [`scripts/plots/build_weekly_model_weather_review.py`](../../scripts/plots/build_weekly_model_weather_review.py) · harmonogram: [`mlops/weekly_model_review.sh`](../../mlops/weekly_model_review.sh) · launchd **sobota 10:00**

---

### Decyzja przed niedzielą (skrót)

- **Pochmurne/deszczowe** (n=52): CS4 @05 **35.2%** vs ENS **44.9%** → rozważ routing / shadow CS4 (paper Accu).
- **Słoneczne** (n=24): ENS @05 średnio **10.4%** — nie przełączaj na CS4 globalnie.
- **Peak @16:** XGB **12.2%** vs ENS @12 **27.7%** — shadow XGB warto monitorować; retrening niedzielny i tak odświeża wszystkie trzy jobliby.

#### Cała seria (od lipca)

| Typ dnia | n | ENS @05 | ENS @12 | ICON ld @05 | ICON ld @12 | CS4 ld @05 | CS4 ld @12 | CS4 peak | ICON peak | XGB @05 | XGB peak |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pochmurny / deszczowy | 52 | 44.9% | 41.7% | 47.9% | 49.0% | 35.2% | 38.2% | 20.7% | 25.9% | 29.1% | 16.8% |
| mieszany | 33 | 16.8% | 16.7% | 23.8% | 19.9% | 18.7% | 18.1% | 8.2% | 5.5% | 18.4% | 8.4% |
| słoneczny / mało chmur | 24 | 10.4% | 12.5% | 17.4% | 17.7% | 13.4% | 13.7% | 7.5% | 5.5% | 12.2% | 8.2% |

#### Ostatnie 28 dni

| Typ dnia | n | ENS @05 | ENS @12 | ICON ld @05 | ICON ld @12 | CS4 ld @05 | CS4 ld @12 | CS4 peak | ICON peak | XGB @05 | XGB peak |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| słoneczny / mało chmur | 6 | 14.7% | 21.9% | 22.5% | 22.1% | 23.5% | 23.6% | 4.8% | 5.0% | 25.0% | 5.5% |
| mieszany | 8 | 26.7% | 22.5% | 26.3% | 19.7% | 26.3% | 20.3% | 5.6% | 5.3% | 23.3% | 5.1% |
| pochmurny / deszczowy | 14 | 100.5% | 89.4% | 80.1% | 85.6% | 63.1% | 69.2% | 36.1% | 41.9% | 42.0% | 23.8% |

#### Ostatnie 7 dni

| Typ dnia | n | ENS @05 | ENS @12 | ICON ld @05 | ICON ld @12 | CS4 ld @05 | CS4 ld @12 | CS4 peak | ICON peak | XGB @05 | XGB peak |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pochmurny / deszczowy | 5 | 124.2% | 116.9% | 99.2% | 110.3% | 75.2% | 89.8% | 21.1% | 26.4% | 56.4% | 25.2% |
| słoneczny / mało chmur | 1 | — | — | — | — | — | — | — | — | — | — |
| mieszany | 1 | 16.0% | 10.8% | 11.4% | 9.2% | 10.2% | 7.5% | 0.8% | 0.8% | 2.9% | 1.1% |

#### Najniższy |APE| @05 (porównanie daily snapshotów)

| Wariant | dni (wygrał @05) |
|---:|---:|
| ENS @05 | 47 |
| XGB @05 | 33 |
| CS4 ld @05 | 19 |
| ICON ld @05 | 7 |

**Pochmurne / deszczowe:** ENS @05 **22×**, XGB @05 **18×**, CS4 ld @05 **8×**, ICON ld @05 **2×**

---

Powiązane: [`july_validation_summary.md`](july_validation_summary.md) (primary + hybryda) · paper-trade — tylko repo prywatne · wykres: [`july_validation_plot.png`](july_validation_plot.png)
