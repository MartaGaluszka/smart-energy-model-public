# Notatka weekly — retrening 18.10.2026

**Data / godzina:** 2026-10-18 ~04:31–04:32 (`train_dual_weekly.sh` / launchd `pl.smart-energy-model.train`, niedziela)  
**Typ:** cotygodniowe odświeżenie wag — **bez zmiany logiki / primary**  
**Okno treningu:** 2025-06-01 → **2026-10-17** (expanding) · **495** dni / **5360** h (**+7** dni vs 11.10)  
**Log:** `logs/cron.log` (blok od `=== Weekly train … 04:30:01 ===`, jeśli lokalnie)  
**Artefakty:** `data/processed/weekly_dual_metrics.csv` (wiersze `production` / `cs4` / `xgb_ts`, `recorded_at=2026-10-18`) · mtime `.joblib` **~04:31–04:32**  
**Pogoda primary (live):** ensemble ICON+UKMO — weekly tego nie rusza  
**Dual report:** [`NOTATKA_GATE_DUAL_L30.md`](NOTATKA_GATE_DUAL_L30.md) · closeout live: [`NOTATKA_GATE_L30_CLOSEOUT.md`](NOTATKA_GATE_L30_CLOSEOUT.md)

---

## Werdykt (1 zdanie)

> Weekly **OK dla primary** · RF16 vs 11.10: Δ Test MAE **−0,004** → **ACCEPT** · CS4 **ACCEPT** (Δ **−0,005**) · **XGB+TS ACCEPT** (Δ **−0,026** — zamknięcie REVIEW z 11.10) · L30 **INFO** u wszystkich · primary **RF 16 + ENS** bez zmian · **watch live:** tydzień **12–17.10** mieszany — **overshoot** na ciemnych (**12–14**) i **undershoot** na jasnych (**16–17**).

---

## Metryki offline (po train)

| Model | Rola | Test MAE (shuffle) | Gap | Daily MAE | L30 MAE | L30 daily | Gate |
|-------|------|-------------------:|----:|----------:|--------:|----------:|------|
| **RF 16** | **primary** | **0,670** | 0,070 | **3,48** | 0,857 | 4,54 | ACCEPT (Δ **−0,004**) · L30 INFO |
| CS4 | shadow | **0,668** | 0,074 | 3,43 | 0,830 | 4,14 | ACCEPT (Δ **−0,005**) · L30 INFO |
| XGB+TS | shadow | **0,646** | — | 3,43 | 0,851 | 4,55 | **ACCEPT** (Δ **−0,026**) · L30 INFO |

- Werdykt tuningu: **nieprzeuczone** (production + CS4).
- Hiperparametry **RF16:** `max_depth=6`, `min_samples_leaf=20`, `min_samples_split=20`, `max_features=1.0` (**bez zmian** vs 11.10) · CV MAE **0,653**.
- **CS4:** `min_samples_split=30` (11.10: **20**) · CV MAE **0,648**.
- **XGB+TS:** bez nowego `hourly_model_tuning_summary_xgb` w `data/processed/` — metryki z `weekly_dual_metrics.csv` (Test **0,646**, daily **3,43**).
- L30 holdout: **2026-09-18 → 2026-10-17** (30 dni). L30 gap (test−train) RF16 **~0,256** · CS4 **~0,226**.
- **Obserwacja:** shuffle Test MAE **lekkio w dół** u wszystkich vs 11.10; L30 daily **wzrosło** (RF **4,05→4,54**, CS4 **3,72→4,14**) — przesunięcie okna (weszły **16–17.10** jasne, wypadł wcześniejszy wrzesień), nie regresja shuffle.

Artefakty: `models/pv_hourly_model.joblib` · `…_cs4.joblib` · `…_xgb_ts.joblib`.

---

## Gate vs poprzednie weekly

| | 04.10 | 11.10 | **18.10** |
|--|------:|------:|----------:|
| RF16 Test MAE | 0,671 | 0,674 | **0,670** |
| Δ vs poprzedni | −0,006 | +0,003 | **−0,004 (ACCEPT)** |
| CS4 Test MAE | 0,673 | 0,673 | **0,668** |
| XGB Test MAE | 0,646 | 0,672 | **0,646** |
| XGB Δ vs poprzedni | ACCEPT | **+0,027 (REVIEW)** | **−0,026 (ACCEPT)** |

Primary zostaje. **XGB REVIEW z 11.10 zamknięte** — Δ ujemne, Test MAE wróciło do poziomu **04.10**. Nadal **shadow**, bez promocji.

---

## L30 — porównanie weekly (soft INFO)

| Weekly | Holdout L30 | RF16 L30 / daily | CS4 L30 / daily | XGB L30 / daily |
|--------|-------------|-----------------:|----------------:|----------------:|
| 04.10 | 04.09–03.10 | 0,808 / 3,71 | 0,795 / 3,46 | 0,842 / 3,85 |
| 11.10 | 11.09–10.10 | 0,872 / 4,05 | 0,836 / 3,72 | 0,851 / 4,26 |
| **18.10** | **18.09–17.10** | **0,857 / 4,54** | **0,830 / 4,14** | **0,851 / 4,55** |

Δ L30 (18.10 − 11.10), godz. / daily:

| Model | Δ L30 MAE | Δ L30 daily |
|-------|----------:|------------:|
| RF16 | **−0,015** | **+0,49** |
| CS4 | **−0,006** | **+0,42** |
| XGB+TS | **≈0** | **+0,29** |

**Ranking L30 godz. 18.10:** CS4 **0,830** < XGB **0,851** < RF16 **0,857**.  
**Ranking L30 daily:** CS4 **4,14** < RF **4,54** ≈ XGB **4,55**.

Soft gate: **INFO** (wszystkie) — bez WATCH na L30.

---

## Tydzień live 12–17.10 (prognoza @05 vs Fox, przed tym trainem)

Okno między weekly **11.10** a **18.10** — wciąż **stare wagi** do **17.10** włącznie.

| Dzień | Fox | ENS @05 | Błąd | Uwaga |
|-------|----:|--------:|-----:|-------|
| 12.10 | 13,6 | 20,2 | **+49%** | overshoot · RF pick · [`NOTATKA_2026-10-12.md`](NOTATKA_2026-10-12.md) |
| 13.10 | 10,2 | 18,9 | **+85%** | ciemny · CS4 reżim |
| 14.10 | 6,6 | 15,5 | **+135%** | deszcz / pochmurno |
| 15.10 | 12,0 | 13,8 | +15% | mix |
| 16.10 | 27,5 | 22,0 | **−20%** | jasny undershoot |
| 17.10 | 28,5 | 21,9 | **−23%** | jasny undershoot |

Agregat @05: WAPE **~39%** · bias **~+40%** (ciężar **12–14**) · dni **Fox ≥ 20** bias **~−22%** (n=2) · dni **Fox < 15** bias **~+71%** (n=4).

**Czytanie:** ten tydzień **nie jest jednym wzorcem** — RF/ENS **zawyża** na słabych dniach, **zaniża** na jasnych (jak wcześniej). To argument za **dalszym watch** closeout / CS4 na pochmurnych, **nie** za rollback weekly (shuffle ACCEPT).

---

## Walidacja live (closeout @05 vs Fox)

Tydzień **12–18.10** (stare wagi do **17.10**; **18.10** @05 już na wagach z retreningu **04:32**):

| Dzień | Fox | ENS @05 | Błąd | Uwaga |
|-------|----:|--------:|-----:|-------|
| 12.10 | 13,6 | 20,2 | +49% | overshoot |
| 13.10 | 10,2 | 18,9 | +85% | overshoot |
| 14.10 | 6,6 | 15,5 | +135% | najgorszy % w tygodniu |
| 15.10 | 12,0 | 13,8 | +15% | mix |
| 16.10 | 27,5 | 22,0 | −20% | jasny undershoot |
| 17.10 | 28,5 | 21,9 | −23% | jasny undershoot |
| 18.10 | *(closeout ~18:22)* | 18,45 | *(partial)* | wieczorny snapshot — **domknąć @22** |

Agregat **12–17.10** (pełne dni): WAPE **~39%** · bias **~+40%** (ciężar **12–14**). Tydzień kalendarzowy **12–18.10** w bramie closeout: **ALARM** (WAPE **35,9%**, najgorszy dzień **135%** **14.10**) — [`NOTATKA_GATE_L30_CLOSEOUT.md`](NOTATKA_GATE_L30_CLOSEOUT.md) · szczegóły w [`july_validation_summary.md`](images/ml/july_validation_summary.md) § tydzień po tygodniu.

**Wykresy odświeżone 18.10** (n=**97**, **14.07–18.10**):

| Plik | Co widać |
|------|----------|
| [`july_validation_plot.png`](images/ml/july_validation_plot.png) | kWh dnia + **\|APE\| %** (lipiec → dziś) |
| [`production_validation_plot.png`](images/ml/production_validation_plot.png) | panel **5:00** + **5:00/12:00**; linia **18.10** = weekly **ACCEPT×3** |
| [`july_validation_summary.md`](images/ml/july_validation_summary.md) | MAPE × pogoda, hybryda, WAPE tygodniowe, opis PNG |

Skrypt: `scripts/plots/plot_july_validation.py` · `scripts/plots/plot_production_validation.py` · źródło: `data/processed/forecasts/forecast_validation.csv`.

---

## Pierwszy dzień na nowych wagach

| | |
|--|--|
| **Train** | **18.10 ~04:32** |
| **@05 18.10** | ENS **18,45** · CS4 **15,90** · ICON **15,64** (`forecast_history`, run **05:00**) |
| **Fox 18.10** | closeout **otwarty** (MB rano **21%** cloud — dzień mógł być jaśniejszy niż stary Accu **55%**) |

Prognozy @05 na **19–20.10** (nowe wagi): ENS **7,14 / 11,76** — spójne z ciemnym Accu **19–20** ([`NOTATKA_2026-10-18.md`](NOTATKA_2026-10-18.md)).

---

## Co dalej

1. Primary **bez zmian** (RF16 + ENS) · CS4/XGB shadow.
2. Kolejny weekly: **2026-10-25 ~04:30** — RF Δ vs **0,670**; XGB utrzymać ACCEPT.
3. Live **12–18.10**: wykresy **zrobione 18.10** — po **closeout @22 18.10** ponownie `plot_july_validation.py` (wiersz **18.10** dziś to snapshot **~18:22**, nie pełny dzień).
4. Operacyjnie: Accu **19–20 CS4** · **18.10** Fox vs ENS **18,45** po closeout.

---

## Oś weekly (skrót)

| Data | RF16 Test MAE | CS4 | XGB+TS | Gate |
|------|--------------:|----:|-------:|------|
| 2026-10-04 | 0,671 | 0,673 | 0,646 | ACCEPT · L30 INFO |
| 2026-10-11 | 0,674 | 0,673 | 0,672 | RF/CS4 ACCEPT · **XGB REVIEW** |
| **2026-10-18** | **0,670** | **0,668** | **0,646** | **ACCEPT ×3** · L30 INFO |

Pełna historia: [`NOTATKA_RETRENINGI_I_WDROZENIA.md`](NOTATKA_RETRENINGI_I_WDROZENIA.md) · status: [`STATUS_ML_MLOPS.md`](STATUS_ML_MLOPS.md) · poprzedni: [`NOTATKA_WEEKLY_2026-10-11.md`](NOTATKA_WEEKLY_2026-10-11.md) · dzień: [`NOTATKA_2026-10-18.md`](NOTATKA_2026-10-18.md).
