# mlops/ — produkcja na hoście (launchd)

Warstwa operacyjna: synchronizacja FoxESS + Open-Meteo, prognoza PV (primary **RF 16** + shadow **CS4** / **XGB+TS**), doradca baterii, closeout, automatyzacja macOS (`config/launchd/`).

**Uwaga:** HTTP API pod aplikację mobilną żyje w `api/` + Docker (`docker-compose.yml`: Postgres + FastAPI).  
`mlops/` = **codzienna produkcja na Macu** (SQLite), nie zastępuje Dockera.

Aktualne metryki modelu / live: [`docs/STATUS_ML_MLOPS.md`](../docs/STATUS_ML_MLOPS.md).

## Złota ścieżka dnia

| Kiedy | Skrypt | Co |
|-------|--------|-----|
| **05:00** | `./mlops/daily_workflow.sh` | sync + prognoza **16** (+ shadow CS4 / XGB gdy włączone) + advisor |
| **12:00** | `./mlops/midday_forecast.sh` | sync + midday (16 + shadow) |
| **16:00** | `./mlops/peak_arrival.sh` | sync + peak (16 + shadow) |
| **wieczór** | `./mlops/evening_closeout.sh` | walidacja vs app → `forecast_validation.csv` (stała 22:42 i/lub dynamicznie po zachodzie) |
| **niedziela 04:30** | `./mlops/train_dual_weekly.sh` | retrain **16 + CS4 + XGB+TS** (przed daily 05:00) |

Shadow: `FORECAST_CS4_ENABLED=1` · skrypty `forecast_cs4_shadow.sh` / `forecast_xgb_ts_shadow.sh` (wywoływane z workflow).

```bash
# Ręcznie (macOS: użyj venv — nie ma systemowego `python`)
./venv/bin/python mlops/sync_data.py
./venv/bin/python mlops/forecast_pv.py --days 2 --top 5
./mlops/install_launchd.sh --status
```

Skrypty `mlops/*.sh` biorą `./venv/bin/python` przez `mlops/_venv.sh`.

Biblioteki ML: `src/` · modele: `models/` · dane: `data/` (SQLite) · logi: `logs/`.
