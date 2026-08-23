# Status ML / MLOps — aktualny snapshot

**Stan na:** 2026-08-23  
**Źródła liczb:** `models/pv_hourly_model.joblib` (**weekly 23.08**) · `forecast_validation.csv` (closeouty predicte do **21.08**; actual **22.08** = 25,1) · [`NOTATKA_WEEKLY_2026-08-23.md`](NOTATKA_WEEKLY_2026-08-23.md)

Ten plik to **jedyna** krótka tabela „aktualne wyniki”. Metoda i historia → linki poniżej (nie duplikuj tu ablacji / gate’ów).

---

## Produkcja (primary)

| | |
|--|--|
| Model | Random Forest · **16 cech** |
| Target | Δ`PVEnergyTotal` (PVE = skala app FoxESS) |
| Pogoda | Open-Meteo **ICON** · GPS dach |
| Artefakt | `models/pv_hourly_model.joblib` |
| Shadow | CS4 (19) + XGB+TS — **nie** primary |

### Offline (80/20 po dniach, expanding)

| Metryka | Wartość |
|---------|---------|
| Okno | 2025-06-01 → **2026-08-22** |
| Test MAE | **0.658** kWh/h |
| Gap train–test | **0.069** |
| Daily MAE | **3.67** kWh/d |
| Daily R² | **0.829** |
| Werdykt | nie przeuczony |

Gate vs weekly **16.08** (0.643): Δ **+0.015** ≤ +0.02 → **ACCEPT**.

### Live (closeout vs app)

| Okres | n | MAPE raw 5:00 | MAPE raw 12:00 |
|-------|--:|-------------:|---------------:|
| Era dual **27.07–21.08** | 26 | **10,2%** | **9,6%** |
| Całość **14.07–21.08** | 39 | 15,2% | 13,5% |

*(Całość wciąga burzowy tydzień przed dual — do narracji używaj ery dual. **21.08** oversboot raw 5:00 +32,9% podbił MAPE.)*

CS4 daily (era dual, n=26): MAPE **~10,4%** — lekko powyżej RF; lepszy **9/26** (m.in. **16–18**, **20–21.08**); na jasnych bywa gorzej (**19.08**).

Ostatnie closeouty: **20.08** **27,4** (best `peak_cs4`) · **21.08** **13,4** (RF +32,9% @5:00; best `peak`) · **22.08** **25,1** (actual only — brak oficjalnych predicte 05/12/16; oneshot ~24,3 ≈ fakt).

Wykresy (do **21.08**): [`images/ml/july_validation_plot.png`](images/ml/july_validation_plot.png), [`images/ml/production_validation_plot.png`](images/ml/production_validation_plot.png) · opis: [`images/ml/july_validation_summary.md`](images/ml/july_validation_summary.md).

---

## MLOps (skrót)

| Kiedy | Job |
|-------|-----|
| 05:00 | daily sync + prognoza (+ shadow) |
| 12:00 | midday |
| 16:00 | peak |
| wieczór | evening closeout → walidacja |
| niedziela **04:30** | `train_dual_weekly.sh` (16 + CS4 + XGB) |

Szczegóły komend: [`mlops/README.md`](../mlops/README.md).

Korekta operacyjna ADJUST: **OFF** (ocena modelu na **raw**).

---

## Gdzie czytać dalej

| Temat | Dokument |
|-------|----------|
| Data quality / EDA | [`01_EDA_analiza.md`](01_EDA_analiza.md) |
| Model, ablacja, Ridge/RF/XGB | [`02_ML_predykcja_PV.md`](02_ML_predykcja_PV.md) |
| Decyzje (PVE, ICON, 16 cech) | [`03_ZALOZENIA_I_DECYZJE.md`](03_ZALOZENIA_I_DECYZJE.md) |
| Historia gate’ów | [`CHANGELOG_ML.md`](CHANGELOG_ML.md) |
| Prezentacja | [`notebooks/03_prezentacja_dyplomowa.ipynb`](../notebooks/03_prezentacja_dyplomowa.ipynb) |
| Pogoda 15–22.08 | [`NOTATKA_POGODA_2026-08-15.md`](NOTATKA_POGODA_2026-08-15.md) |
| Weekly **23.08** | [`NOTATKA_WEEKLY_2026-08-23.md`](NOTATKA_WEEKLY_2026-08-23.md) |
| Weekly 16.08 | [`NOTATKA_WEEKLY_2026-08-16.md`](NOTATKA_WEEKLY_2026-08-16.md) |
| Dzień 19–22.08 | [`NOTATKA_2026-08-19.md`](NOTATKA_2026-08-19.md) · [`NOTATKA_2026-08-20.md`](NOTATKA_2026-08-20.md) · (21–22.08: szczegóły w weekly / prywatnym ops) |
| Oneshot shadow | [`NOTATKA_ONESHOT_2026-08-17.md`](NOTATKA_ONESHOT_2026-08-17.md) |

---

*Odświeżaj po każdym weekly train / po serii nowych closeoutów.*
