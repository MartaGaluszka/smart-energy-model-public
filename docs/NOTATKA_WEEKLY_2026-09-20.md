# Notatka weekly — retrening 20.09.2026

**Data / godzina:** 2026-09-20 ~04:30–04:32 (`train_dual_weekly.sh` / launchd `pl.smart-energy-model.train`)  
**Typ:** cotygodniowe odświeżenie wag — **bez zmiany logiki / primary**  
**Okno treningu:** 2025-06-01 → **2026-09-19** (expanding) · **467** dni (373 train / 94 test dni · 3929 h / 1039 h)  
**Log:** `logs/train.log` · marker `logs/.weekly_train_ok` = **2026-09-20**  
**Pogoda primary (live):** ensemble ICON+UKMO — weekly tego nie rusza

---

## Werdykt (1 zdanie)

> Weekly **OK** · gate RF16 vs **13.09**: Δ Test MAE **−0,014** (lepszy) → **ACCEPT** · primary zostaje **RF 16 + ENS** · gap spada (**0,054** vs 0,071).

---

## Metryki offline (po train)

| Model | Rola | Cechy | Test MAE | Gap | Daily MAE | Werdykt |
|-------|------|------:|---------:|----:|----------:|---------|
| **RF 16** | **primary** | 16 | **0,652** | 0,054 | **3,24** | nie przeuczony |
| CS4 | shadow | 19 | 0,658 | 0,062 | 3,14 | nie przeuczony |
| XGB+TS | shadow | 24 | 0,648 | 0,083 | 3,23 | nie przeuczony |

Hiperparametry RF16 (min gap): `max_depth=6`, `min_samples_leaf=20`, `min_samples_split=20`, `max_features=1.0` · CV MAE **0,651** ± 0,028.

CS4 (min gap): `max_depth=6`, `min_samples_leaf=20`, `min_samples_split=20`, `max_features=1.0` · CV MAE **0,652** ± 0,029.

Artefakty (mtime ~04:30–04:32):

- `models/pv_hourly_model.joblib` (+ `.metadata.json`)
- `models/pv_hourly_model_cs4.joblib`
- `models/pv_hourly_model_xgb_ts.joblib`

CSV: `data/processed/hourly_model_tuning_summary_production.csv` · `…_cs4.csv`

---

## Gate vs poprzedni weekly (13.09)

| | 13.09 | **20.09** | Δ |
|--|------:|----------:|--:|
| RF16 Test MAE | 0,666 | **0,652** | **−0,014** |
| Gap | 0,071 | **0,054** | −0,017 |
| Daily MAE | 3,38 | **3,24** | −0,14 |
| Protokół | ACCEPT (Δ −0,020 vs 06.09) | lepszy vs 13.09 | **ACCEPT** |

Bez podmiany primary / bez nowych cech / bez auto-routingu RF↔CS4.  
XGB+TS nadal najniższy Test MAE w tabeli — zostaje shadow (gap wyższy niż RF16).

---

## Poranna @05:00 (nowe wagi)

Pierwsze daily po tym retrainie: **2026-09-20** @05 — sumy w archiwum prognozy (`forecast_history` / `pv_forecast.csv`).  
*(Uzupełnij wiersze dni po closeoucie, gdy masz Fox vs midday/peak.)*

---

## Co dalej

1. Nic nie zmieniać w launchd / primary (RF16 + ENS).  
2. Closeouty **13.09–19.09** — dopisać do [`STATUS_ML_MLOPS.md`](STATUS_ML_MLOPS.md) po serii wieczornych runów.  
3. Kolejny weekly: **2026-09-27 ~04:30**.  
4. Watch: jesień / krótszy dzień — gap nadal OK; Δ vs 13.09 **−0,014** (zapas względem progu REVIEW **+0,02**).

---

## Oś weekly (skrót)

| Data | RF16 Test MAE | CS4 | XGB+TS | Gate |
|------|--------------:|----:|-------:|------|
| **2026-09-06** | **0,686** | 0,688 | 0,665 | ACCEPT (Δ +0,018) |
| **2026-09-13** | **0,666** | 0,659 | 0,644 | ACCEPT (Δ −0,020 vs 06.09) |
| **2026-09-20** | **0,652** | 0,658 | 0,648 | **ACCEPT** (Δ **−0,014** vs 13.09) |

Pełna historia: [`NOTATKA_RETRENINGI_I_WDROZENIA.md`](NOTATKA_RETRENINGI_I_WDROZENIA.md) · status: [`STATUS_ML_MLOPS.md`](STATUS_ML_MLOPS.md) · poprzedni: [`NOTATKA_WEEKLY_2026-09-13.md`](NOTATKA_WEEKLY_2026-09-13.md).
