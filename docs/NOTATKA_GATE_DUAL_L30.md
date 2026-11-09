# Gate dual report — shuffle + L30 (soft, X 2026)

**Od:** 2026-09-27 (kod) · **pierwszy pełny weekly z dual:** **2026-10-04 ~04:30** (już podpięte w `train_dual_weekly.sh`)  
**Status:** wdrożone w train · soft gate L30 = **informacyjny** (bez REJECT)

---

## Komendy (na przyszłość)

Z katalogu repo (`smart-energy-model`):

```bash
# 1) Pełny weekly (jak launchd niedziela 04:30) — train + dual w logu + podsumowanie
./mlops/train_dual_weekly.sh

# 2) Tylko tabela dual z ostatniej historii (bez treningu)
PYTHONPATH=$PWD ./venv/bin/python scripts/train/weekly_dual_gate_report.py

# 3) Pojedynczy model z dual w logu (opcjonalnie)
PYTHONPATH=$PWD ./venv/bin/python scripts/train/train_hourly_model_tuning.py \
  --features production --model-path models/pv_hourly_model.joblib

PYTHONPATH=$PWD ./venv/bin/python scripts/train/train_hourly_model_tuning.py \
  --features cs4 --model-path models/pv_hourly_model_cs4.joblib

PYTHONPATH=$PWD ./venv/bin/python scripts/train/train_xgb_ts_shadow.py \
  --model-path models/pv_hourly_model_xgb_ts.joblib
```

**Artefakty:** `logs/train.log` (bloki `DUAL REPORT`) · `data/processed/weekly_dual_metrics.csv` · `hourly_model_tuning_summary_{production,cs4}.csv`.

**Notatka weekly:** po runie dopisz shuffle + L30 z logu/CSV (skrypt **nie** generuje `NOTATKA_WEEKLY_*.md` sam).

---

## Założenia

1. **Dual reporting** w każdym weekly train (RF16 / CS4 / XGB+TS):
   - **Shuffle Test MAE** — jak dotychczas (kontrola, gate Δ vs prev ≤ +0,02 → ACCEPT / REVIEW)
   - **L30 chrono MAE** — holdout ostatnich 30 dni do `train_end` (uczciwy błąd referencyjny)
   - **Chrono 90d** — ostatnie **90 dni** do `train_end` (stałe okno, żeby tydzień do tygodnia był porównywalny; kolumny `chrono90_*` w CSV: `test_mae`, `daily_mae`, `wape`, `bias`; **nie** gate, **nie** ucina `.joblib`). `wape` = suma |błąd| / suma produkcji (porównywalne między sezonami, w odróżnieniu od MAE); `bias` < 0 = model **zaniża** produkcję (ważne dla planu baterii). Liczenie jest w `try/except` — błąd raportu nie przerywa treningu produkcyjnego. Pierwsza liczba w CSV dopiero po weekly **15.11**; bez progów — obserwacja min. 2 tygodnie (jak cap). Dry-run 08.11: RF 16 → MAE 0,80 / WAPE 41,8% / bias −0,21; XGB+TS → 0,78 / 40,5% / −0,27 (okno 11.08→08.11).
2. **Produkcja `.joblib`:** zawsze **expanding** od `ML_TRAIN_MIN_START` → **wczoraj** (`train_end=auto`). L30 **nie** ucina danych treningowych. RF po wyborze hiperparametrów dostaje **refit na pełnym oknie** (jak XGB+TS).
3. **Soft gate L30 (październik / okres przejściowy):** MAE w okolicy **~0,75–1,0** → `INFO` / powyżej → `WATCH`. **`hard_reject=False` zawsze** — brak fałszywego alarmu / auto-rollback z samego L30.
4. **Shadow cap @05 (od 08.11, nie w apce):** cięcie gdy chmura 6–20 ≥ **88%** i ENS @05 ≤ **10 kWh**. Bias kWh z poprzednich **28** dni o chmurze ≥ 88% (min. 3, bias ≥ 0). Próg **90%** omija **01.11** (88,96%). Samo zejście progu bez sufitu ENS szkodzi dniom z wysoką chmurą NWP i Fox ~20 kWh. Na serii do 08.11: **7** cięć, **0** szkód, WAPE **16,4→15,8%**. `FORECAST_OPERATIONAL_ADJUST` zostaje **wyłączony**.

---

## Gdzie w kodzie

| Element | Plik |
|---------|------|
| Maski L30, soft/shuffle gate, historia | [`src/models/weekly_dual_metrics.py`](../src/models/weekly_dual_metrics.py) |
| RF16 / CS4 train + dual w logu | [`scripts/train/train_hourly_model_tuning.py`](../scripts/train/train_hourly_model_tuning.py) |
| XGB+TS shadow + dual | [`scripts/train/train_xgb_ts_shadow.py`](../scripts/train/train_xgb_ts_shadow.py) |
| Podsumowanie po weekly | [`scripts/train/weekly_dual_gate_report.py`](../scripts/train/weekly_dual_gate_report.py) |
| Launchd weekly | [`mlops/train_dual_weekly.sh`](../mlops/train_dual_weekly.sh) |
| Shadow cap @05 (nie apka) | [`scripts/analysis/shadow_morning_cloud_cap.py`](../scripts/analysis/shadow_morning_cloud_cap.py) → `morning_cloud_cap_shadow.csv` |
| Historia CSV | `data/processed/weekly_dual_metrics.csv` |
| Summary RF | `data/processed/hourly_model_tuning_summary_{production,cs4}.csv` (kolumny `l30_*`, `soft_gate_*`) |

---

## Jak czytać notatkę weekly

| Metryka | Rola | Alarm? |
|---------|------|--------|
| Shuffle MAE + Δ vs prev | kontrola / REVIEW jak dotychczas | REVIEW w notatce; **primary bez auto-zmiany** |
| L30 MAE | uczciwy błąd sezonu | tylko INFO/WATCH |

Przykład (oczekiwany rząd jesień): shuffle **~0,65–0,70** · L30 **~0,75–1,0** — **nie** traktuj L30 0,8 jako regresji wag.

---

## Co dalej (po X 2026)

- Po **2–4** weekly z dual: rozważyć L30 jako główny wiersz gate (nadal bez ucinania prod). **Kryteria przejścia (≥6 punktów, P90, korelacja z closeoutem, reguła wielosygnałowa) i kryteria testu live:** [`NOTATKA_GATE_L30_CLOSEOUT.md`](NOTATKA_GATE_L30_CLOSEOUT.md) (05.10).
- Sezonowy baseline (Δ vs med4 / vs rok) — osobno.

Powiązane: [`NOTATKA_WEEKLY_2026-09-27.md`](NOTATKA_WEEKLY_2026-09-27.md) · [`STATUS_ML_MLOPS.md`](STATUS_ML_MLOPS.md) · [`QUICK_START.md`](../QUICK_START.md) § retrening
