# Review modeli × pogoda (closeouty)

**Wygenerowano:** 2026-11-07 (przegląd modeli × pogoda)  
**Zakres closeoutów:** 2026-07-14 → 2026-11-06 (**116** dni)  
**Metryka:** |APE| % = |Fox − prognoza| / Fox × 100 · pogoda: średnie cloud **6–20** (ICON w DB)  
**Nie w tabeli:** UKMO solo / oneshot ½ — tylko w notatkach dnia (`oneshot_rf_icon_vs_ukmo.py`).  

**Skrypt:** [`scripts/plots/build_weekly_model_weather_review.py`](../../scripts/plots/build_weekly_model_weather_review.py) · harmonogram: [`mlops/weekly_model_review.sh`](../../mlops/weekly_model_review.sh) · launchd **sobota 10:00**

---

### Decyzja przed niedzielą (skrót)

- **Pochmurne/deszczowe** (n=58): CS4 @05 **45.1%** vs ENS **55.5%** → rozważ routing / shadow CS4 (paper Accu).
- **Słoneczne** (n=25): ENS @05 średnio **10.4%** — nie przełączaj na CS4 globalnie.
- **Peak @16:** XGB **14.6%** vs ENS @12 **33.2%** — shadow XGB warto monitorować; retrening niedzielny i tak odświeża wszystkie trzy jobliby.

#### Cała seria (od lipca)

| Typ dnia | n | ENS @05 | ENS @12 | ICON ld @05 | ICON ld @12 | CS4 ld @05 | CS4 ld @12 | CS4 peak | ICON peak | XGB @05 | XGB peak |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pochmurny / deszczowy | 58 | 55.5% | 51.6% | 65.0% | 62.8% | 45.1% | 45.0% | 26.3% | 36.7% | 38.8% | 21.5% |
| mieszany | 33 | 16.8% | 16.7% | 23.8% | 19.9% | 18.7% | 18.1% | 8.2% | 5.5% | 18.4% | 8.4% |
| słoneczny / mało chmur | 25 | 10.4% | 12.5% | 17.0% | 17.3% | 13.2% | 13.4% | 7.2% | 5.1% | 12.1% | 7.9% |

#### Ostatnie 28 dni

| Typ dnia | n | ENS @05 | ENS @12 | ICON ld @05 | ICON ld @12 | CS4 ld @05 | CS4 ld @12 | CS4 peak | ICON peak | XGB @05 | XGB peak |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pochmurny / deszczowy | 18 | 126.9% | 117.0% | 114.0% | 113.1% | 88.1% | 86.0% | 51.0% | 65.1% | 70.6% | 37.4% |
| mieszany | 5 | 37.5% | 27.6% | 30.6% | 23.2% | 30.7% | 23.5% | 4.2% | 4.0% | 24.0% | 2.8% |
| słoneczny / mało chmur | 5 | 16.9% | 22.1% | 24.8% | 22.8% | 23.1% | 22.2% | 2.7% | 2.8% | 25.1% | 3.1% |

#### Ostatnie 7 dni

| Typ dnia | n | ENS @05 | ENS @12 | ICON ld @05 | ICON ld @12 | CS4 ld @05 | CS4 ld @12 | CS4 peak | ICON peak | XGB @05 | XGB peak |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pochmurny / deszczowy | 6 | 139.0% | 133.5% | 144.9% | 131.6% | 110.5% | 93.1% | 65.1% | 91.1% | 105.1% | 53.7% |
| słoneczny / mało chmur | 1 | 11.4% | 11.1% | 12.1% | 12.3% | 8.5% | 8.1% | 0.5% | 0.5% | 9.4% | 1.2% |

#### Najniższy |APE| @05 (porównanie daily snapshotów)

| Wariant | dni (wygrał @05) |
|---:|---:|
| ENS @05 | 48 |
| XGB @05 | 36 |
| CS4 ld @05 | 22 |
| ICON ld @05 | 7 |

**Pochmurne / deszczowe:** ENS @05 **23×**, XGB @05 **21×**, CS4 ld @05 **10×**, ICON ld @05 **2×**

---

Powiązane: [`july_validation_summary.md`](july_validation_summary.md) (primary + hybryda) · paper-trade — tylko repo prywatne · wykres: [`july_validation_plot.png`](july_validation_plot.png)
