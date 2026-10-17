# Review modeli × pogoda (closeouty)

**Wygenerowano:** 2026-10-17 (przegląd modeli × pogoda)  
**Zakres closeoutów:** 2026-07-14 → 2026-10-16 (**95** dni)  
**Metryka:** |APE| % = |Fox − prognoza| / Fox × 100 · pogoda: średnie cloud **6–20** (ICON w DB)  
**Nie w tabeli:** UKMO solo / oneshot ½ — tylko w notatkach dnia (`oneshot_rf_icon_vs_ukmo.py`).  

**Skrypt:** [`scripts/plots/build_weekly_model_weather_review.py`](../../scripts/plots/build_weekly_model_weather_review.py) · harmonogram: [`mlops/weekly_model_review.sh`](../../mlops/weekly_model_review.sh) · launchd **sobota 10:00**

---

### Decyzja przed niedzielą (skrót)

- **Pochmurne/deszczowe** (n=45): CS4 @05 **21.4%** vs ENS **26.7%** → rozważ routing / shadow CS4 (paper Accu).
- **Słoneczne** (n=21): ENS @05 średnio **9.1%** — nie przełączaj na CS4 globalnie.
- **Peak @16:** XGB **10.5%** vs ENS @12 **19.7%** — shadow XGB warto monitorować; retrening niedzielny i tak odświeża wszystkie trzy jobliby.

#### Cała seria (od lipca)

| Typ dnia | n | ENS @05 | ENS @12 | ICON ld @05 | ICON ld @12 | CS4 ld @05 | CS4 ld @12 | CS4 peak | ICON peak | XGB @05 | XGB peak |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pochmurny / deszczowy | 45 | 26.7% | 25.5% | 23.1% | 23.8% | 21.4% | 24.1% | 13.0% | 12.6% | 22.2% | 12.2% |
| mieszany | 29 | 17.5% | 17.3% | 23.9% | 20.3% | 18.9% | 18.3% | 8.9% | 6.3% | 18.2% | 9.3% |
| słoneczny / mało chmur | 21 | 9.1% | 10.2% | 15.1% | 15.8% | 11.8% | 12.4% | 7.8% | 6.1% | 10.5% | 8.6% |

#### Ostatnie 28 dni

| Typ dnia | n | ENS @05 | ENS @12 | ICON ld @05 | ICON ld @12 | CS4 ld @05 | CS4 ld @12 | CS4 peak | ICON peak | XGB @05 | XGB peak |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| mieszany | 8 | 30.5% | 25.9% | 28.5% | 25.0% | 30.1% | 27.9% | 6.9% | 6.6% | 27.1% | 6.9% |
| pochmurny / deszczowy | 13 | 34.1% | 24.3% | 19.3% | 19.1% | 16.1% | 17.3% | 5.5% | 5.3% | 15.8% | 4.5% |
| słoneczny / mało chmur | 7 | 13.7% | 17.0% | 16.4% | 16.9% | 18.0% | 19.0% | 6.0% | 6.5% | 18.2% | 7.4% |

#### Ostatnie 7 dni

| Typ dnia | n | ENS @05 | ENS @12 | ICON ld @05 | ICON ld @12 | CS4 ld @05 | CS4 ld @12 | CS4 peak | ICON peak | XGB @05 | XGB peak |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pochmurny / deszczowy | 4 | 50.7% | 30.9% | 30.3% | 30.3% | 20.4% | 24.1% | 6.7% | 5.4% | 24.6% | 3.9% |
| mieszany | 2 | 66.8% | 39.0% | 41.6% | 30.3% | 44.8% | 33.5% | 7.0% | 6.5% | 26.1% | 4.6% |
| słoneczny / mało chmur | 1 | 20.0% | 24.8% | 31.0% | 26.0% | 30.5% | 26.9% | 5.1% | 5.2% | 33.8% | 5.2% |

#### Najniższy |APE| @05 (porównanie daily snapshotów)

| Wariant | dni (wygrał @05) |
|---:|---:|
| ENS @05 | 44 |
| XGB @05 | 26 |
| CS4 ld @05 | 18 |
| ICON ld @05 | 7 |

**Pochmurne / deszczowe:** ENS @05 **22×**, XGB @05 **12×**, CS4 ld @05 **9×**, ICON ld @05 **2×**

---

Powiązane: [`july_validation_summary.md`](july_validation_summary.md) (primary + hybryda) · paper-trade — tylko repo prywatne · wykres: [`july_validation_plot.png`](july_validation_plot.png)
