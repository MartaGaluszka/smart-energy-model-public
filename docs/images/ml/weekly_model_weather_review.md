# Review modeli × pogoda (closeouty)

**Wygenerowano:** 2026-10-03 (sobotni przegląd przed retreningiem niedzielnym)  
**Zakres closeoutów:** 2026-07-14 → 2026-10-02 (**81** dni)  
**Metryka:** |APE| % = |Fox − prognoza| / Fox × 100 · pogoda: średnie cloud **6–20** (ICON w DB)  
**Nie w tabeli:** UKMO solo / oneshot ½ — tylko w notatkach dnia (`oneshot_rf_icon_vs_ukmo.py`).  

**Skrypt:** [`scripts/plots/build_weekly_model_weather_review.py`](../../scripts/plots/build_weekly_model_weather_review.py) · harmonogram: [`mlops/weekly_model_review.sh`](../../mlops/weekly_model_review.sh) · launchd **sobota 10:00**

---

### Decyzja przed niedzielą (skrót)

- **Pochmurne/deszczowe** (n=39): CS4 @05 **22.6%** vs ENS **25.2%** → rozważ routing / shadow CS4 (paper Accu).
- **Słoneczne** (n=18): ENS @05 średnio **8.5%** — nie przełączaj na CS4 globalnie.
- **Peak @16:** XGB **11.4%** vs ENS @12 **19.4%** — shadow XGB warto monitorować; retrening niedzielny i tak odświeża wszystkie trzy jobliby.

#### Cała seria (od lipca)

| Typ dnia | n | ENS @05 | ENS @12 | ICON ld @05 | ICON ld @12 | CS4 ld @05 | CS4 ld @12 | CS4 peak | ICON peak | XGB @05 | XGB peak |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pochmurny / deszczowy | 39 | 25.2% | 26.3% | 23.7% | 24.6% | 22.6% | 25.2% | 14.4% | 15.2% | 23.2% | 13.8% |
| mieszany | 24 | 14.4% | 16.1% | 20.9% | 20.1% | 16.5% | 17.4% | 9.2% | 5.8% | 16.8% | 9.9% |
| słoneczny / mało chmur | 18 | 8.5% | 8.7% | 13.2% | 14.1% | 10.0% | 10.7% | 8.1% | 5.8% | 8.2% | 8.8% |

#### Ostatnie 28 dni

| Typ dnia | n | ENS @05 | ENS @12 | ICON ld @05 | ICON ld @12 | CS4 ld @05 | CS4 ld @12 | CS4 peak | ICON peak | XGB @05 | XGB peak |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pochmurny / deszczowy | 16 | 20.7% | 28.6% | 24.5% | 25.9% | 23.5% | 26.3% | 15.0% | 16.3% | 22.5% | 12.6% |
| mieszany | 6 | 21.7% | 22.2% | 22.4% | 22.5% | 25.6% | 26.0% | 6.0% | 6.3% | 25.2% | 6.9% |
| słoneczny / mało chmur | 6 | 12.6% | 14.1% | 13.2% | 14.1% | 14.0% | 15.4% | 5.4% | 5.8% | 13.8% | 7.1% |

#### Ostatnie 7 dni

| Typ dnia | n | ENS @05 | ENS @12 | ICON ld @05 | ICON ld @12 | CS4 ld @05 | CS4 ld @12 | CS4 peak | ICON peak | XGB @05 | XGB peak |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| mieszany | 2 | 32.6% | 30.4% | 33.1% | 35.3% | 34.5% | 38.1% | 5.7% | 5.9% | 39.2% | 6.4% |
| słoneczny / mało chmur | 4 | 14.6% | 15.4% | 14.5% | 15.2% | 15.6% | 17.2% | 5.8% | 6.4% | 14.8% | 7.6% |
| pochmurny / deszczowy | 1 | 24.6% | 27.2% | 30.9% | 30.4% | 37.3% | 35.2% | 2.7% | 3.9% | 44.0% | 4.8% |

#### Najniższy |APE| @05 (porównanie daily snapshotów)

| Wariant | dni (wygrał @05) |
|---:|---:|
| ENS @05 | 38 |
| XGB @05 | 22 |
| CS4 ld @05 | 15 |
| ICON ld @05 | 6 |

**Pochmurne / deszczowe:** ENS @05 **20×**, XGB @05 **10×**, CS4 ld @05 **7×**, ICON ld @05 **2×**

---

Powiązane: [`july_validation_summary.md`](july_validation_summary.md) (primary + hybryda) · paper-trade — tylko repo prywatne · wykres: [`july_validation_plot.png`](july_validation_plot.png)
