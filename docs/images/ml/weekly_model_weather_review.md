# Review modeli × pogoda (closeouty)

**Wygenerowano:** 2026-10-11 (odświeżenie po closeoucie 11.10 i retrenie 04:30)  
**Zakres closeoutów:** 2026-07-14 → 2026-10-11 (**90** dni)  
**Metryka:** |APE| % = |Fox − prognoza| / Fox × 100 · pogoda: średnie cloud **6–20** (ICON w DB)  
**Nie w tabeli:** UKMO solo / oneshot ½ — tylko w notatkach dnia (`oneshot_rf_icon_vs_ukmo.py`).  

**Skrypt:** [`scripts/plots/build_weekly_model_weather_review.py`](../../scripts/plots/build_weekly_model_weather_review.py) · harmonogram: [`mlops/weekly_model_review.sh`](../../mlops/weekly_model_review.sh) · launchd **sobota 10:00**

---

### Skrót (po retrenie 11.10)

- **Pochmurne/deszczowe** (n=43): CS4 @05 **21.7%** vs ENS **24.3%** → rozważ routing / shadow CS4 (paper Accu).
- **Słoneczne** (n=20): ENS @05 średnio **8.5%** — nie przełączaj na CS4 globalnie.
- **Retrain 11.10:** RF/CS4 **ACCEPT**, XGB **REVIEW** (Δ shuffle +0,027) — primary bez zmian.
- **Peak @16:** XGB **10.8%** vs ENS @12 **18.9%** — shadow XGB warto monitorować; retrening niedzielny i tak odświeża wszystkie trzy jobliby.

#### Cała seria (od lipca)

| Typ dnia | n | ENS @05 | ENS @12 | ICON ld @05 | ICON ld @12 | CS4 ld @05 | CS4 ld @12 | CS4 peak | ICON peak | XGB @05 | XGB peak |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pochmurny / deszczowy | 43 | 24.3% | 25.2% | 22.7% | 23.7% | 21.7% | 24.3% | 13.2% | 13.0% | 22.8% | 12.5% |
| mieszany | 27 | 13.8% | 15.7% | 20.4% | 18.1% | 16.8% | 17.0% | 9.1% | 6.3% | 17.5% | 9.7% |
| słoneczny / mało chmur | 20 | 8.5% | 9.4% | 13.1% | 14.5% | 10.8% | 11.6% | 7.9% | 6.2% | 9.2% | 8.7% |

#### Ostatnie 28 dni

| Typ dnia | n | ENS @05 | ENS @12 | ICON ld @05 | ICON ld @12 | CS4 ld @05 | CS4 ld @12 | CS4 peak | ICON peak | XGB @05 | XGB peak |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pochmurny / deszczowy | 15 | 21.6% | 21.1% | 17.3% | 18.9% | 16.6% | 19.4% | 5.4% | 5.9% | 17.5% | 5.0% |
| mieszany | 8 | 17.0% | 20.1% | 22.4% | 22.3% | 24.2% | 25.5% | 6.9% | 6.9% | 24.7% | 7.9% |
| słoneczny / mało chmur | 6 | 12.6% | 15.7% | 13.9% | 15.4% | 15.9% | 17.7% | 6.2% | 6.7% | 15.6% | 7.8% |

#### Ostatnie 7 dni

| Typ dnia | n | ENS @05 | ENS @12 | ICON ld @05 | ICON ld @12 | CS4 ld @05 | CS4 ld @12 | CS4 peak | ICON peak | XGB @05 | XGB peak |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| mieszany | 3 | 8.8% | 9.9% | 19.1% | 10.9% | 18.9% | 12.3% | 8.0% | 7.5% | 22.1% | 9.0% |
| słoneczny / mało chmur | 1 | 5.1% | 6.4% | 4.1% | 5.9% | 5.7% | 7.2% | 7.2% | 7.3% | 7.8% | 7.7% |
| pochmurny / deszczowy | 4 | 15.5% | 14.5% | 18.6% | 19.5% | 14.8% | 17.2% | 3.6% | 3.0% | 19.9% | 2.7% |

#### Najniższy |APE| @05 (porównanie daily snapshotów)

| Wariant | dni (wygrał @05) |
|---:|---:|
| ENS @05 | 43 |
| XGB @05 | 23 |
| CS4 ld @05 | 17 |
| ICON ld @05 | 7 |

**Pochmurne / deszczowe:** ENS @05 **22×**, XGB @05 **11×**, CS4 ld @05 **8×**, ICON ld @05 **2×**

---

Powiązane: [`july_validation_summary.md`](july_validation_summary.md) (primary + hybryda) · paper-trade — tylko repo prywatne · wykres: [`july_validation_plot.png`](july_validation_plot.png)
