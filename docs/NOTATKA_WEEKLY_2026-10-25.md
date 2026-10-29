# Notatka weekly — retrening 25.10.2026

**Data / godzina:** 2026-10-25 ~04:31–04:32 (`train_dual_weekly.sh` / launchd, niedziela)  
**Typ:** cotygodniowe odświeżenie wag — **bez zmiany logiki / primary**  
**Okno treningu:** 2025-06-01 → **2026-10-24** (expanding) · **+7** dni vs 18.10 (do **24.10** włącznie)  
**Artefakty:** `data/processed/weekly_dual_metrics.csv` (wiersze `recorded_at=2026-10-25`) · mtime `.joblib` **~04:31–04:32**  
**Pogoda primary (live):** ensemble ICON+UKMO — weekly tego nie rusza  
**Dual report:** [`NOTATKA_GATE_DUAL_L30.md`](NOTATKA_GATE_DUAL_L30.md) · closeout live: [`NOTATKA_GATE_L30_CLOSEOUT.md`](NOTATKA_GATE_L30_CLOSEOUT.md)

---

## Werdykt (1 zdanie)

> Weekly **OK dla primary** · RF16 vs 18.10: Δ Test MAE **+0,003** → **ACCEPT** · CS4 **ACCEPT** (Δ **+0,006**) · **XGB+TS ACCEPT** (Δ **+0,013**) · L30 **INFO** u wszystkich · primary **RF 16 + ENS** bez zmian · **watch live:** **19–22.10** ekstremy (Fox **~0,9–3,8** vs ENS **~5–11**) · **23 RF** / **24 CS4** bliżej reżimu.

---

## Metryki offline (po train)

| Model | Rola | Test MAE (shuffle) | Daily MAE | L30 MAE | L30 daily | Gate |
|-------|------|-------------------:|----------:|--------:|----------:|------|
| **RF 16** | **primary** | **0,673** | **3,47** | **0,800** | **4,67** | ACCEPT (Δ **+0,003**) · L30 INFO |
| CS4 | shadow | **0,674** | **3,48** | **0,767** | **4,24** | ACCEPT (Δ **+0,006**) · L30 INFO |
| XGB+TS | shadow | **0,659** | **3,60** | **0,772** | **4,52** | ACCEPT (Δ **+0,013**) · L30 INFO |

- Werdykt tuningu: **nieprzeuczone** (production + CS4) — bez nowego alarmu gap w CSV.
- L30 holdout: **2026-09-25 → 2026-10-24** (30 dni).
- **Obserwacja:** shuffle Test MAE **lekko w górę** u wszystkich vs 18.10 (Δ **+0,003 … +0,013**), wszystko w paśmie **ACCEPT**; L30 godz. **spadło** u RF/CS4/XGB vs 18.10, L30 daily **RF +0,13** / CS4 **+0,10** — okno weszło **18–24.10** (m.in. **22.10** deszcz **~0,9 kWh**, **24.10** pochmurny **~6 kWh**).

Artefakty: `models/pv_hourly_model.joblib` · `…_cs4.joblib` · `…_xgb_ts.joblib`.

---

## Gate vs poprzednie weekly

| | 11.10 | 18.10 | **25.10** |
|--|------:|------:|----------:|
| RF16 Test MAE | 0,674 | 0,670 | **0,673** |
| Δ vs poprzedni | +0,003 | −0,004 | **+0,003 (ACCEPT)** |
| CS4 Test MAE | 0,673 | 0,668 | **0,674** |
| CS4 Δ | −0,000 | −0,005 | **+0,006 (ACCEPT)** |
| XGB Test MAE | 0,672 | 0,646 | **0,659** |
| XGB Δ | +0,027 (REVIEW) | −0,026 (ACCEPT) | **+0,013 (ACCEPT)** |

Primary zostaje. XGB nadal **shadow**, bez promocji.

---

## L30 — porównanie weekly (soft INFO)

| Weekly | Holdout L30 | RF16 L30 / daily | CS4 L30 / daily | XGB L30 / daily |
|--------|-------------|-----------------:|----------------:|----------------:|
| 11.10 | 11.09–10.10 | 0,872 / 4,05 | 0,836 / 3,72 | 0,851 / 4,26 |
| 18.10 | 18.09–17.10 | 0,857 / 4,54 | 0,830 / 4,14 | 0,851 / 4,55 |
| **25.10** | **25.09–24.10** | **0,800 / 4,67** | **0,767 / 4,24** | **0,772 / 4,52** |

Δ L30 (25.10 − 18.10), godz. / daily:

| Model | Δ L30 MAE | Δ L30 daily |
|-------|----------:|------------:|
| RF16 | **−0,057** | **+0,13** |
| CS4 | **−0,063** | **+0,10** |
| XGB+TS | **−0,079** | **−0,03** |

**Ranking L30 godz. 25.10:** CS4 **0,767** < RF **0,800** < XGB **0,772**.  
**Ranking L30 daily:** CS4 **4,24** < XGB **4,52** < RF **4,67**.

Soft gate: **INFO** (wszystkie).

---

## Tydzień live 19–24.10 (prognoza @05 vs Fox, wagi z retreningu **18.10**)

| Dzień | Fox | ENS @05 | Błąd | Uwaga |
|-------|----:|--------:|-----:|-------|
| 19.10 | 3,4 | 6,8 | **+100%** | CS4 · [`NOTATKA_2026-10-19.md`](NOTATKA_2026-10-19.md) |
| 20.10 | 3,8 | 10,6 | **+179%** | choroba / outlook CS4 · jaśniej niż Fox |
| 21.10 | 21,3 | 19,4 | **−9%** | RF ✓ |
| 22.10 | 0,9 | 5,1 | **+462%** | deszcz · CS4 ✓ reżim |
| 23.10 | 25,6 | 22,8 | **−11%** | RF ✓ |
| 24.10 | 6,0 | 8,8 | **+46%** | pochmurny · CS4 · [`NOTATKA_2026-10-24.md`](NOTATKA_2026-10-24.md) |

**Czytanie:** ten blok to **stare wagi (18.10)** — typowy mix **overshoot** na **Fox &lt; 4 kWh** (**19–20, 22**) i **undershoot** na jasnym **23.10**. Nie uzasadnia rollbacku (shuffle **ACCEPT×3**).

---

## Pierwszy dzień na nowych wagach

| | |
|--|--|
| **Train** | **25.10 ~04:31–04:32** |
| **@05 25.10** | ENS **16,30** · CS4 **16,95** · ICON **17,32** (`forecast_history`, run **05:00:31**) |
| **Outlook @05** | **26.10** ENS **14,92** · **27.10** ENS **18,31** |
| **Fox 25.10** | dzień **otwarty** (nd. · Accu **CS4** / watch MB) |

---

## Walidacja live (wykresy odświeżone **25.10**)

| Plik | Zakres | Uwaga |
|------|--------|-------|
| [`july_validation_plot.png`](images/ml/july_validation_plot.png) | **14.07–24.10** (n=**103**) | **24.10** Fox **6,2** · \|APE\| @05 **~42%** (CS4 dzień) |
| [`production_validation_plot.png`](images/ml/production_validation_plot.png) | j.w. | linia **25.10** = weekly **ACCEPT×3** |
| [`july_validation_summary.md`](images/ml/july_validation_summary.md) | tabele WAPE / pogoda / hybryda | tydz. **19–25.10** → **ALARM** (outlier **22.10**) |
| [`weekly_model_weather_review.md`](images/ml/weekly_model_weather_review.md) | MAPE × wariant × cloud | pochmurne: CS4 @05 **31,8%** vs ENS **39,5%** |

Skrypt: `build_weekly_model_weather_review.py --also-refresh-july-summary` + `plot_production_validation.py`.

---

## Co dalej

1. Primary **bez zmian** (RF16 + ENS) · CS4/XGB shadow.
2. Kolejny weekly: **2026-11-01 ~04:30** — RF Δ vs **0,673**.
3. Closeout **25.10** @22 → ponownie wykresy (wiersz **25.10** na PNG).
4. Operacyjnie: **25–26.10** paper **CS4** (Accu) · [`NOTATKA_2026-10-24.md`](NOTATKA_2026-10-24.md).

---

## Oś weekly (skrót)

| Data | RF16 Test MAE | CS4 | XGB+TS | Gate |
|------|--------------:|----:|-------:|------|
| 2026-10-11 | 0,674 | 0,673 | 0,672 | RF/CS4 ACCEPT · **XGB REVIEW** |
| 2026-10-18 | 0,670 | 0,668 | 0,646 | **ACCEPT ×3** · L30 INFO |
| **2026-10-25** | **0,673** | **0,674** | **0,659** | **ACCEPT ×3** · L30 INFO |

Pełna historia: [`NOTATKA_RETRENINGI_I_WDROZENIA.md`](NOTATKA_RETRENINGI_I_WDROZENIA.md) · status: [`STATUS_ML_MLOPS.md`](STATUS_ML_MLOPS.md) · poprzedni: [`NOTATKA_WEEKLY_2026-10-18.md`](NOTATKA_WEEKLY_2026-10-18.md) · dzień: [`NOTATKA_2026-10-25.md`](NOTATKA_2026-10-25.md).
