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
0 5 * * * ~/smart-energy-model/mlops/daily_workflow.sh >> ~/smart-energy-model/logs/cron.log 2>&1
```

**CRON — opcjonalnie południe (12:00): odświeżenie pogody + prognoza**

```cron
0 12 * * * ~/smart-energy-model/mlops/midday_forecast.sh >> ~/smart-energy-model/logs/cron.log 2>&1
```

**Retrening niedzielny (macOS — launchd, zalecane):** `pl.smart-energy-model.train` → **`mlops/train_dual_weekly.sh`** (~**04:30**): RF **16** (produkcja) + shadow **CS4** + **XGB+TS** · log **`logs/train.log`**.

Ręcznie (cały weekly, jak w launchd):

```bash
./mlops/train_dual_weekly.sh
```

**CRON — retrening (Linux / stary skrót; tylko RF 16, bez shadow):**

```cron
0 5 * * 0 cd ~/smart-energy-model && ./venv/bin/python scripts/train/train_hourly_model_tuning.py >> logs/train.log 2>&1
```

Na Macu **nie** używaj tego CRON-a zamiast launchd — pełny weekly = `train_dual_weekly.sh` (patrz §5).

Po reorganizacji ścieżek: `./mlops/install_launchd.sh` (ponowna instalacja plistów).

---

## 5. Sprawdzenie wyników

### Prognoza operacyjna (AGD, CSV)

```bash
head -20 data/processed/pv_forecast.csv
tail -80 logs/cron.log
```

### Ostatni retrening niedzielny (weekly)

```bash
cat logs/.weekly_train_ok
tail -80 logs/train.log
cat data/processed/hourly_model_tuning_summary_production.csv
cat data/processed/hourly_model_tuning_summary_cs4.csv
./venv/bin/python -c "
import json
m = json.load(open('models/pv_hourly_model.metadata.json'))
print('saved_at:', m['saved_at'])
print('train_end:', m['train_end'])
print('Test MAE:', m['metrics']['test_mae'])
print('gap:', m['metrics']['gap'])
print(m['metrics']['verdict'])
"
ls -la models/pv_hourly_model.joblib models/pv_hourly_model_cs4.joblib models/pv_hourly_model_xgb_ts.joblib
```

- **`logs/.weekly_train_ok`** — data ostatniego udanego `train_dual_weekly.sh`
- Koniec **`logs/train.log`** — szukaj `Train OK | produkcja RF 16 + shadow CS4 + shadow XGB+TS`
- Metryki primary: **`hourly_model_tuning_summary_production.csv`** (nie stary `hourly_model_tuning_summary.csv` z lipca)
- Pełny JSON: **`models/pv_hourly_model.metadata.json`** (+ `*_cs4`, `*_xgb_ts`)

Podsumowanie gate / werdykt: [`docs/STATUS_ML_MLOPS.md`](docs/STATUS_ML_MLOPS.md) · notatka tygodnia: `docs/NOTATKA_WEEKLY_YYYY-MM-DD.md`

Ręczny trening **tylko** RF 16 (§2, bez shadow): `./venv/bin/python scripts/train/train_hourly_model_tuning.py`

### Walidacja live — backfill closeoutów + wykresy (notebooki 02/03)

Gdy brakuje dni w `data/processed/forecasts/forecast_validation.csv` (launchd / sen Maca). **Actual** musi być w SQLite — najpierw sync FoxESS albo `--actual-kwh` w closeout (patrz `mlops/evening_closeout.py --help`). Brak prognozy w archiwum: `--backfill-snapshots daily=… midday=…`.

Ustaw zakres (oba dni **włącznie**):

```bash
FROM=YYYY-MM-DD   # pierwszy dzień (np. początek luki)
TO=YYYY-MM-DD     # ostatni dzień (włącznie)

for d in $(FROM="$FROM" TO="$TO" ./venv/bin/python -c "
from datetime import date, timedelta
import os
s, e = date.fromisoformat(os.environ['FROM']), date.fromisoformat(os.environ['TO'])
d = s
while d <= e:
    print(d)
    d += timedelta(days=1)
"); do
  ./venv/bin/python mlops/evening_closeout.py --day "$d" --skip-sync
done

MPLBACKEND=Agg PYTHONPATH=$PWD ./venv/bin/python scripts/plots/plot_july_validation.py
MPLBACKEND=Agg PYTHONPATH=$PWD ./venv/bin/python scripts/plots/plot_production_validation.py
cp reports/figures/july_validation_plot.png \
   reports/figures/production_validation_plot.png \
   docs/images/ml/
```

Wynik: PNG w `reports/figures/` i `docs/images/ml/` · tabela MAPE w notebookach po ponownym uruchomieniu komórek walidacji.

### Czy CRON / launchd zadziałał?

```bash
./mlops/install_launchd.sh --status
grep "$(date +%Y-%m-%d)" logs/cron.log
ls -la data/processed/pv_forecast.csv
```

Szukaj w logu: `daily workflow | … 05:` oraz opcjonalnie `Midday refresh | … 12:`.

---

## 6. Dashboard operacyjny (Streamlit)

Panel lokalny: notatki pogodowe, walidacja prognozy vs app, faktury Tauron · [`dashboard/app.py`](dashboard/app.py)

```bash

```

→ http://localhost:8501

*(Ten sam `.env` / SQLite co MLOps na hoście — Docker API nie jest wymagany do samego dashboardu.)*

---

## 7. Aplikacja mobilna — iOS Simulator

Aplikacja Ionic (`mobile/`) woła API z Dockera. **Najpierw:**

```bash
docker compose up -d db api
curl -sf http://127.0.0.1:8000/health
```

| Tryb | URL |
|------|-----|
| API | http://localhost:8000 |
| Dev w przeglądarce | http://localhost:8100 |

### Przeglądarka (szybki podgląd UI)

```bash
cd mobile
npm install
npm start
```

Symulator rachunków: **Więcej → Symulator rachunku**.

### iOS Simulator (Xcode, macOS)

```bash
cd mobile
npm install
npm run build:sim
npx cap sync ios
open -a Simulator                    # okno Simulatora (czasem schowane za innymi appkami)
npx cap run ios
```
#Na co dzień możesz trzymać ten skrót
cd ~/smart-energy-model/mobile
open -a Simulator
npx cap run ios --target-name "iPhone 17"

#Pamiętaj też o API, jeśli chcesz live dane w appce:
cd ~/smart-energy-model
docker compose up -d db api

**`npx cap run ios` czeka w terminalu na wybór urządzenia** (`Please choose a target device`). Przejdź do okna terminala → strzałki ↓ do **iPhone 17** (lub inny iPhone) → **Enter**. Dopiero wtedy Xcode buduje apkę i Simulator się uruchamia (domyślnie podświetlony jest iPad — to normalne).

Bez pytania interaktywnego (np. z Cursora):

```bash
npx cap run ios --target-name "iPhone 17"
# lista urządzeń:
npx cap run ios --list
```

Alternatywa: otwórz `mobile/ios/App/App.xcodeproj` w Xcode → wybierz **iPhone** u góry → **Run** (▶).

### iOS — skrypt z live-reload (zalecane na co dzień)

```bash
cd mobile
chmod +x run-ios-simulator.sh   # raz, jeśli potrzeba
./run-ios-simulator.sh
```

Dev server w tle (domyślnie port **8100**). Logi: `tail -f /tmp/smart-energy-mobile-serve.log`  
Stop: `kill $(cat /tmp/smart-energy-mobile-serve.pid 2>/dev/null)`

### Po zmianach w TS/HTML (iOS)

```bash
cd mobile
npm run build:sim && npx cap sync ios
```

Potem ponownie `npx cap run ios` albo Run w Xcode.

**Gdy brak danych w Simulatorze:** sprawdź `docker compose ps` i `GET /ready`; w buildzie dev iOS używa `http://127.0.0.1:8000` (`mobile/src/environments/environment.ts`). Więcej: [README.md](README.md) § aplikacja mobilna.

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

*Ostatnia aktualizacja: 2026-09-25*
