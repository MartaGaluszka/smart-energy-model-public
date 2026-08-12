# Quick Start — Smart Energy Model (Production)

System predykcji PV z automatycznym harmonogramem urządzeń AGD.

**Aktualizacja 2026-07-23:** model PVE · Test MAE **0.594** · struktura `mlops/` + `docs/archive/` · [README](README.md) · [UPDATE_2026-07-13](docs/UPDATE_2026-07-13_16-cech-hybryda.md)

Mapa skryptów: [scripts/README.md](scripts/README.md) · MLOps: [mlops/README.md](mlops/README.md)

---

## Wymagania

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Na macOS **poza venv nie ma komendy `python`**. Po `source venv/bin/activate` działa `python`, albo zawsze:

```bash
./venv/bin/python mlops/sync_data.py
```

W `.env` ustaw minimum:

```bash
FOXESS_API_KEY=...
WEATHER_LAT=...
WEATHER_LON=...
WEATHER_LOCATION=home
DATABASE_PATH=data/energy_model.db
# PV_HOURLY_MODEL_PATH=models/pv_hourly_model.joblib
```

---

## 1. Synchronizacja danych (Live)

```bash
./venv/bin/python mlops/sync_data.py              # FoxESS + Open-Meteo (archiwum + prognoza)
./venv/bin/python mlops/sync_data.py --dry-run    # audyt luk bez pobierania
./venv/bin/python mlops/sync_data.py --weather    # tylko pogoda
./venv/bin/python mlops/sync_data.py --foxess     # tylko FoxESS
```

Uzupełnia luki w `foxess_data` i odświeża pogodę Open-Meteo (archiwum do dziś + prognoza 3 dni).

---

## 2. Trening modelu (16 cech, GridSearch)

```bash
./venv/bin/python scripts/train/train_hourly_model_tuning.py
```

**Wynik:**

- `models/pv_hourly_model.joblib` — model produkcyjny (`HOURLY_FEATURE_COLUMNS_PRODUCTION`)
- `data/processed/hourly_model_tuning_summary.csv` — metryki
- `data/processed/hourly_model_grid_search.csv` — pełna siatka

Parametry: `max_depth=6`, `min_samples_leaf=20`, Test MAE **0.594 kWh/h**, gap **0.058** (target PVE, artefakt `models/pv_hourly_model.joblib`).

---

## 3. Prognoza + harmonogram AGD

```bash
./venv/bin/python mlops/forecast_pv.py --days 3 --sync --top 5
```

Domyślnie: **dziś + jutro + pojutrze** (3 dni).

**Hybryda na dziś:** minione godziny → pogoda z archiwum + PV z FoxESS (gdy w bazie); reszta dnia → prognoza + model.

Generuje `data/processed/pv_forecast.csv` z kolumnami m.in.:
- `prediction_source` — `model` / `foxess_actual`
- `predicted_kwh` — prognoza pvPower (skala zbliżona do PVEnergyTotal, bez filtra baterii)

**Wykresy walidacji operacyjnej:**

```bash
./venv/bin/python scripts/plots/plot_production_validation.py   # reports/figures/production_validation_plot.png
./venv/bin/python scripts/plots/plot_july_validation.py         # reports/figures/july_validation_plot.png
```

Ranking godzin na:
- Pralka (≥1.5 kW)
- Suszarka (≥2.0 kW)
- Zmywarka (≥1.2 kW)
- Gotowanie (≥1.5 kW)

Opcje: `--sync` (pobierz dane przed prognozą), `--retrain` (wytrenuj od nowa).

---

## 4. Workflow dzienny (launchd — zalecane; CRON = Linux)

```bash
chmod +x mlops/daily_workflow.sh mlops/midday_forecast.sh mlops/peak_arrival.sh mlops/evening_closeout.sh
./mlops/daily_workflow.sh
./mlops/install_launchd.sh --status   # macOS — zalecane
```

**CRON — poranek (5:00): sync + prognoza 3 dni** (alternatywa Linux)
```bash
crontab -e
```

```cron
0 5 * * * /path/to/smart-energy-model/mlops/daily_workflow.sh >> /path/to/smart-energy-model/logs/cron.log 2>&1
```

**CRON — opcjonalnie południe (12:00): odświeżenie pogody + prognoza**

```cron
0 12 * * * /path/to/smart-energy-model/mlops/midday_forecast.sh >> /path/to/smart-energy-model/logs/cron.log 2>&1
```

**Retrening (niedziela 5:00):**

```cron
0 5 * * 0 cd /path/to/smart-energy-model && ./venv/bin/python scripts/train/train_hourly_model_tuning.py >> logs/train.log 2>&1
```

Po reorganizacji ścieżek: `./mlops/install_launchd.sh` (ponowna instalacja plistów).

---

## 5. Sprawdzenie wyników

```bash
cat data/processed/hourly_model_tuning_summary.csv
head -20 data/processed/pv_forecast.csv
tail -80 logs/cron.log
```

### Czy CRON / launchd zadziałał?

```bash
./mlops/install_launchd.sh --status
grep "$(date +%Y-%m-%d)" logs/cron.log
ls -la data/processed/pv_forecast.csv
```

Szukaj w logu: `daily workflow | … 05:` oraz opcjonalnie `Midday refresh | … 12:`.

---

## Dokumentacja szczegółowa

| Plik | Temat |
|------|-------|
| [docs/UPDATE_2026-07-13_16-cech-hybryda.md](docs/UPDATE_2026-07-13_16-cech-hybryda.md) | **Aktualizacja:** 16 cech, hybryda, CRON |
| [docs/02_ML_predykcja_PV.md](docs/02_ML_predykcja_PV.md) | Model, ablacja, MLOps |
| [docs/01_EDA_analiza.md](docs/01_EDA_analiza.md) | Jakość danych, luki IoT |
| [MODELS_README.md](MODELS_README.md) | Porównanie modeli |
| [PROJECT_STATUS.md](PROJECT_STATUS.md) | Kontekst projektu |
| [docs/archive/README.md](docs/archive/README.md) | Archiwum notatek (data quality, pogoda, modele, bateria) |

---

*Ostatnia aktualizacja: 2026-07-23*
