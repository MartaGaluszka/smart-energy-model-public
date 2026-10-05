# Notatka weekly — retrening 27.09.2026

**Data / godzina:** 2026-09-27 ~04:30–04:32 (`train_dual_weekly.sh` / launchd `pl.smart-energy-model.train`)  
**Typ:** cotygodniowe odświeżenie wag — **bez zmiany logiki / primary**  
**Okno treningu:** 2025-06-01 → **2026-09-26** (expanding) · **474** dni (379 train / 95 test dni · 4009 h / 1032 h)  
**Log:** `logs/train.log` · marker `logs/.weekly_train_ok` = **2026-09-27**  
**Pogoda primary (live):** ensemble ICON+UKMO — weekly tego nie rusza

---

## Werdykt (1 zdanie)

> Weekly **OK technicznie** · gate RF16 vs **20.09**: Δ Test MAE **+0,025** (**> +0,02**) → **REVIEW** · primary zostaje **RF 16 + ENS** (bez rollbacku wag) · CS4/XGB shadow · watch kolejny weekly (jesień / krótszy dzień).

---

## Metryki offline (po train)

| Model | Rola | Cechy | Test MAE | Gap | Daily MAE | Werdykt |
|-------|------|------:|---------:|----:|----------:|---------|
| **RF 16** | **primary** | 16 | **0,677** | 0,079 | **3,44** | nie przeuczony |
| CS4 | shadow | 19 | 0,673 | 0,084 | 3,38 | nie przeuczony |
| XGB+TS | shadow | 24 | 0,645 | 0,075 | 3,12 | nie przeuczony |

Hiperparametry RF16 (min gap): `max_depth=6`, `min_samples_leaf=20`, `min_samples_split=20`, `max_features=1.0` · CV MAE **0,650** ± 0,035.

CS4 (min gap): `max_depth=8`, `min_samples_leaf=20`, `min_samples_split=20`, `max_features=sqrt` · CV MAE **0,654** ± 0,039  
*(względem 20.09: było depth=6 / max_features=1.0 — GridSearch wybrał inny punkt na siatce).*

Artefakty (mtime ~04:30–04:32):

- `models/pv_hourly_model.joblib` (+ `.metadata.json`)
- `models/pv_hourly_model_cs4.joblib`
- `models/pv_hourly_model_xgb_ts.joblib`

CSV: `data/processed/hourly_model_tuning_summary_production.csv` · `…_cs4.csv`

---

## Gate vs poprzedni weekly (20.09)

| | 20.09 | **27.09** | Δ |
|--|------:|----------:|--:|
| RF16 Test MAE | 0,652 | **0,677** | **+0,025** |
| Gap | 0,054 | **0,079** | +0,025 |
| Daily MAE | 3,24 | **3,44** | +0,20 |
| Protokół | ACCEPT (Δ −0,014 vs 13.09) | Δ **> +0,02** | **REVIEW** |

Bez podmiany primary / bez nowych cech / bez auto-routingu Accu→CS4 (Faza 0 = paper — [`NOTATKA_GATE_ACCU_CS4_UI.md`](NOTATKA_GATE_ACCU_CS4_UI.md)).  
XGB+TS nadal najniższy Test MAE — zostaje shadow (nie primary).  
CS4 lekko **lepszy** offline niż RF16 (0,673 vs 0,677) — **nie** promujemy; live dual nadal ENS primary + paper Accu.

**Interpretacja REVIEW:** typowy skok przy wejściu w krótszy dzień / więcej pochmurnych w oknie testowym (jak fala IX). Trzymamy nowe wagi (expanding); kolejny weekly **04.10** — jeśli Δ vs 20.09 nadal ≫ +0,02 albo vs 27.09 znów ~+0,02 → pogłębiony REVIEW (cechy / split), nie flip CS4.

---

## Poranna @05:00 (nowe wagi)

Pierwsze daily po tym retrainie: **2026-09-27** @05 — sumy w `pv_forecast*.csv` / archiwum.  
Closeout Fox vs ENS/CS4 — dopisać wieczorem.

---

## Co dalej

1. Primary **bez zmian** (RF16 + ENS).  
2. Paper Accu→CS4 kontynuować (szare dni Fox≲15) — UI routing **nie** w tej rundzie.  
3. Kolejny weekly: **2026-10-04 ~04:30** → **wykonany** — [`NOTATKA_WEEKLY_2026-10-04.md`](NOTATKA_WEEKLY_2026-10-04.md) (ACCEPT Δ −0,006). Wcześniej: **dual już podpięte** w `train_dual_weekly.sh` (launchd); w logu bloki `DUAL REPORT` + `weekly_dual_gate_report.py`. Komendy: [`NOTATKA_GATE_DUAL_L30.md`](NOTATKA_GATE_DUAL_L30.md) §Komendy · [`QUICK_START.md`](../QUICK_START.md) §retrening.
4. Watch gap RF16 (**0,079**) — nadal „nie przeuczony”, ale wyżej niż 20.09.

```bash
# za tydzień / ręcznie — to samo co launchd
./mlops/train_dual_weekly.sh
# tylko tabela dual z CSV
PYTHONPATH=$PWD ./venv/bin/python scripts/train/weekly_dual_gate_report.py
```

---

## Oś weekly (skrót)

| Data | RF16 Test MAE | CS4 | XGB+TS | Gate |
|------|--------------:|----:|-------:|------|
| **2026-09-06** | **0,686** | 0,688 | 0,665 | ACCEPT (Δ +0,018) |
| **2026-09-13** | **0,666** | 0,659 | 0,644 | ACCEPT (Δ −0,020 vs 06.09) |
| **2026-09-20** | **0,652** | 0,658 | 0,648 | ACCEPT (Δ −0,014 vs 13.09) |
| **2026-09-27** | **0,677** | 0,673 | 0,645 | **REVIEW** (Δ **+0,025** vs 20.09) |

Pełna historia: [`NOTATKA_RETRENINGI_I_WDROZENIA.md`](NOTATKA_RETRENINGI_I_WDROZENIA.md) · status: [`STATUS_ML_MLOPS.md`](STATUS_ML_MLOPS.md) · poprzedni: [`NOTATKA_WEEKLY_2026-09-20.md`](NOTATKA_WEEKLY_2026-09-20.md).
