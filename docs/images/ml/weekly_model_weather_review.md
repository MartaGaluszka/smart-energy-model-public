# Review modeli × pogoda (closeouty)

**Wygenerowano:** 2026-09-18 (sobotni przegląd przed retreningiem niedzielnym)  
**Zakres closeoutów:** 2026-07-14 → 2026-09-17 (**66** dni)  
**Metryka:** |APE| % = |Fox − prognoza| / Fox × 100 · pogoda: średnie cloud **6–20** (ICON w DB)  
**Nie w tabeli:** UKMO solo / oneshot ½ — tylko w notatkach dnia (`oneshot_rf_icon_vs_ukmo.py`).  

**Skrypt:** [`scripts/plots/build_weekly_model_weather_review.py`](../../scripts/plots/build_weekly_model_weather_review.py) · harmonogram: [`mlops/weekly_model_review.sh`](../../mlops/weekly_model_review.sh) · launchd **sobota 10:00**

---

### Decyzja przed niedzielą (skrót)

- **Pochmurne/deszczowe** (n=31): ENS @05 **23.6%** ≤ CS4 **23.9%** → trzymaj **primary ENS**.
- **Słoneczne** (n=14): ENS @05 średnio **6.8%** — nie przełączaj na CS4 globalnie.
- **Peak @16:** XGB **13.1%** vs ENS @12 **18.1%** — shadow XGB warto monitorować; retrening niedzielny i tak odświeża wszystkie trzy jobliby.

#### Cała seria (od lipca)

| Typ dnia | n | ENS @05 | ENS @12 | ICON ld @05 | ICON ld @12 | CS4 ld @05 | CS4 ld @12 | CS4 peak | ICON peak | XGB @05 | XGB peak |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pochmurny / deszczowy | 31 | 23.6% | 25.7% | 28.1% | 28.6% | 23.9% | 27.2% | 17.6% | 22.8% | 25.6% | 17.1% |
| mieszany | 21 | 12.5% | 14.5% | 14.6% | 12.1% | 13.9% | 14.6% | 9.8% | 5.8% | 13.8% | 10.5% |
| słoneczny / mało chmur | 14 | 6.8% | 6.8% | 10.6% | 11.7% | 8.2% | 8.5% | 8.8% | 4.6% | 5.9% | 9.2% |

#### Ostatnie 28 dni

| Typ dnia | n | ENS @05 | ENS @12 | ICON ld @05 | ICON ld @12 | CS4 ld @05 | CS4 ld @12 | CS4 peak | ICON peak | XGB @05 | XGB peak |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pochmurny / deszczowy | 14 | 25.8% | 34.3% | 28.1% | 28.6% | 34.2% | 36.1% | 20.6% | 22.8% | 32.8% | 19.0% |
| mieszany | 11 | 13.5% | 15.0% | 14.6% | 12.1% | 14.8% | 15.2% | 10.4% | 5.8% | 14.5% | 10.7% |
| słoneczny / mało chmur | 3 | 8.9% | 10.5% | 10.6% | 11.7% | 10.0% | 10.2% | 5.5% | 4.6% | 9.8% | 5.7% |

#### Ostatnie 7 dni

| Typ dnia | n | ENS @05 | ENS @12 | ICON ld @05 | ICON ld @12 | CS4 ld @05 | CS4 ld @12 | CS4 peak | ICON peak | XGB @05 | XGB peak |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pochmurny / deszczowy | 5 | 5.1% | 41.8% | 46.2% | 44.5% | 41.1% | 42.5% | 34.7% | 41.0% | 41.3% | 27.6% |
| mieszany | 2 | 12.7% | 18.7% | 16.9% | 20.7% | 21.2% | 25.0% | 6.9% | 7.7% | 16.7% | 8.4% |

#### Najniższy |APE| @05 (porównanie daily snapshotów)

| Wariant | dni (wygrał @05) |
|---:|---:|
| ENS @05 | 34 |
| XGB @05 | 17 |
| CS4 ld @05 | 13 |
| ICON ld @05 | 2 |

**Pochmurne / deszczowe:** ENS @05 **18×**, CS4 ld @05 **6×**, XGB @05 **6×**, ICON ld @05 **1×**

---

Powiązane: [`july_validation_summary.md`](july_validation_summary.md) (primary + hybryda) · paper-trade — tylko repo prywatne · wykres: [`july_validation_plot.png`](july_validation_plot.png)
