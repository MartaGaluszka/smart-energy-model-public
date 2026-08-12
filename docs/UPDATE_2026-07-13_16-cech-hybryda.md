# Aktualizacja produkcyjna — 2026-07-13

**Zakres:** model 16 cech · prognoza hybrydowa · baza pogody · CRON

Powiązane: [02_ML_predykcja_PV.md](02_ML_predykcja_PV.md) · [QUICK_START.md](../QUICK_START.md)

---

## 1. Podsumowanie zmian

| Obszar | Przed | Po |
|--------|-------|-----|
| Cechy modelu | 19 (`HOURLY_FEATURE_COLUMNS_EXTENDED`, z kalendarzem) | **16** (`HOURLY_FEATURE_COLUMNS_PRODUCTION`, bez `month`/`doy_*`) |
| Test MAE (ablacja 80/20) | 0.650 (legacy) | **0.636** (rekomendowany zestaw) |
| Test MAE (GridSearch min-gap, retrening) | 0.711 / gap 0.214 | **0.661** / gap **0.103** |
| Prognoza „dziś” | wyłącznie `OpenMeteo-forecast` | **hybryda:** archiwum + FoxESS + prognoza |
| Baza `weather_data` | jeden rekord / timestamp (prognoza nadpisywała archiwum) | **osobno** `OpenMeteo-archive` i `OpenMeteo-forecast` |

---

## 2. Model produkcyjny (16 cech)

### Decyzja (ablacja kalendarza)

Faza `3_Pogoda_Slonce_Reguly` dała najlepszy kompromis MAE / złożoność:

- **Wyrzucono:** `month`, `doy_sin`, `doy_cos` — redundantne wobec radiacji i geometrii słońca (+0.011 MAE vs sama pogoda).
- **Zostawiono:** cechy słoneczne, śnieg, mgła — wartość w warunkach brzegowych (zima, mgła).

### Stała w kodzie

```python
# src/features/pv_features_hourly_extended.py
HOURLY_FEATURE_COLUMNS_PRODUCTION = [
    'hour',
    'temp_c', 'humidity_pct', 'cloud_cover_pct', 'radiation_wm2', 'wind_speed_ms',
    'sunrise_hour', 'sunset_hour', 'day_length_hours',
    'hours_since_sunrise', 'hours_until_sunset', 'sun_position', 'is_daylight',
    'snow_on_panels', 'snow_on_panels_prev', 'likely_fog_day',
]
```

### Pliki objęte wdrożeniem

| Plik | Zmiana |
|------|--------|
| `scripts/train/train_hourly_model_tuning.py` | trening na 16 cechach |
| `src/models/pv_hourly_predictor.py` | domyślne cechy + prognoza hybrydowa |
| `models/pv_hourly_model.joblib` | artefakt po retreningu |

### Retrening

```bash
source venv/bin/activate
python scripts/train/train_hourly_model_tuning.py
```

Metryki po retreningu (2026-07-13):

| Metryka | Wartość |
|---------|---------|
| Train MAE | 0.558 kWh/h |
| Test MAE | **0.661 kWh/h** |
| Gap | **0.103** (✅ nie przeuczony) |
| CV MAE | 0.639 ± 0.032 |
| Daily MAE | 3.52 kWh/d |

Hiperparametry: `max_depth=6`, `min_samples_leaf=20`, `min_samples_split=20`, `max_features=1.0`, `n_estimators=200`.

---

## 3. Prognoza hybrydowa (dziś)

### Problem

Prognoza na **bieżący dzień** używała wyłącznie **porannej prognozy pogody** (często pesymistycznej — 100% chmur), także dla godzin już minionych. Skutkowało to zaniżoną sumą dzienną (np. ~17 kWh vs ~18,6 kWh rzeczywiste o 16:38).

### Rozwiązanie

Dla dnia bieżącego (`predict_days`, domyślnie włączone):

```
┌─────────────────────────────────────────────────────────────┐
│  DZIŚ                                                       │
├──────────────────┬──────────────────────────────────────────┤
│ Godziny minione  │ Pogoda: OpenMeteo-archive (obserwacja)   │
│                  │ PV: FoxESS z bazy (jeśli sync zdążył)    │
├──────────────────┼──────────────────────────────────────────┤
│ Godziny przyszłe │ Pogoda: OpenMeteo-forecast               │
│                  │ PV: model RF (16 cech)                   │
├──────────────────┴──────────────────────────────────────────┤
│  JUTRO / POJUTRZE → wyłącznie prognoza pogody + model       │
└─────────────────────────────────────────────────────────────┘
```

### Kolumny w `pv_forecast.csv`

| Kolumna | Opis |
|---------|------|
| `predicted_kwh` | prognoza lub rzeczywistość (dziś, minione godziny) |
| `prediction_source` | `model` \| `foxess_actual` |
| `weather_source` | `archive` \| `forecast` (w ramce cech wewnętrznie) |

Rekomendacje AGD (`rank_hours_for_appliances`) biorą **tylko przyszłe** godziny (`prediction_source == model`).

### API (Python)

```python
from src.models.pv_hourly_predictor import PVHourlyPredictor

p = PVHourlyPredictor()
p.load()
df = p.predict_days(
    days_ahead=3,
    hybrid_today=True,   # domyślnie True
    use_actual_pv=True,  # domyślnie True
)
```

### Przykład wpływu (2026-07-13)

| Wariant | Suma dzienna |
|---------|--------------|
| Tylko prognoza pogody (stary sposób) | ~17,1 kWh |
| Hybryda pogoda (archiwum + forecast) | ~20,6 kWh |
| + FoxESS w bazie (minione godziny) | rzeczywiste + reszta z modelu |

---

## 4. Baza pogody — dwa źródła

### Problem

Tabela `weather_data` miała `UNIQUE(timestamp, location)`. Zapis prognozy **nadpisywał** archiwum dla tego samego timestampu — model widział tylko prognozę, nawet dla przeszłości.

### Naprawa

1. **Migracja schematu:** `UNIQUE(timestamp, location, data_source)` — przy pierwszym zapisie przez `save_weather_to_db`.
2. **Filtr przy zapisie prognozy:** `filter_forecast_preserve_archive()` — nie zapisuje minionych godzin dzisiejszych z prognozy (zostawia archiwum).

Pliki: `src/data/weather_api.py`, `scripts/fetch_weather.py`.

### Weryfikacja w bazie

```bash
sqlite3 data/energy_model.db "
  SELECT data_source, COUNT(*)
  FROM weather_data
  WHERE DATE(timestamp) = date('now')
  GROUP BY data_source;
"
```

Oczekiwany wynik po sync: **oba** `OpenMeteo-archive` (24 h) i `OpenMeteo-forecast` (od bieżącej godziny w górę).

---

## 5. CRON i monitorowanie

### Harmonogram

| Godzina | Skrypt | Działanie |
|---------|--------|-----------|
| **05:00** | `daily_workflow.sh` | sync FoxESS + pogoda → prognoza 3 dni |
| **12:00** *(opcja)* | `midday_forecast.sh` | odświeżenie pogody + prognoza |
| **05:00 niedziela** | `train_hourly_model_tuning.py` | retrening tygodniowy |

### Instalacja CRON

```bash
crontab -e
```

```cron
0 5 * * * /path/to/smart-energy-model/mlops/daily_workflow.sh >> /path/to/smart-energy-model/logs/cron.log 2>&1
0 12 * * * /path/to/smart-energy-model/scripts/midday_forecast.sh >> /path/to/smart-energy-model/logs/cron.log 2>&1
0 5 * * 0 cd /path/to/smart-energy-model && ./venv/bin/python scripts/train/train_hourly_model_tuning.py >> /path/to/smart-energy-model/logs/train.log 2>&1
```

### Jak sprawdzić, czy job się wykonał

**1. Log (najprościej)**

```bash
grep "$(date +%Y-%m-%d)" /path/to/smart-energy-model/logs/cron.log
tail -80 /path/to/smart-energy-model/logs/cron.log
```

Szukaj:

- `Smart Home PV — daily workflow | YYYY-MM-DD 05:` → poranek OK
- `✅ Workflow zakończony pomyślnie` → poranek zakończony
- `=== Midday refresh | YYYY-MM-DD 12:` → południe OK
- `=== Midday refresh OK ===` → południe zakończone

**2. Czy CRON w ogóle jest skonfigurowany**

```bash
crontab -l
```

Brak wpisów = joby **nie uruchomią się** automatycznie.

**3. Plik prognozy**

```bash
ls -la data/processed/pv_forecast.csv
head -3 data/processed/pv_forecast.csv
```

Data modyfikacji ≈ 05:xx (i opcjonalnie 12:xx). Pierwsze wiersze = dzisiejsza data.

**4. macOS — pułapki**

- Mac **uśpiony** o 5:00 / 12:00 → CRON **nie nadrobi** po obudzeniu.
- Test ręczny: `./mlops/daily_workflow.sh >> logs/cron.log 2>&1`

---

## 6. Komendy operacyjne (ściąga)

```bash
# Pełny sync + prognoza
python mlops/sync_data.py
python mlops/forecast_pv.py --days 3

# Jednym skryptem (jak CRON 5:00)
./mlops/daily_workflow.sh

# Południowy refresh (jak CRON 12:00)
./scripts/midday_forecast.sh

# Retrening
python scripts/train/train_hourly_model_tuning.py
```

---

## 7. Wykresy i artefakty do odświeżenia (opcjonalnie)

Po wdrożeniu 16 cech warto zregenerować:

```bash
python scripts/ablation_study.py
python scripts/plots/plot_error_chart.py
python scripts/plots/plot_learning_curves.py
python scripts/plots/plot_academic_evaluation.py
python scripts/ablation_study.py --calendar-only
```

| Wykres | Status |
|--------|--------|
| `docs/data_split_viz.png` | ✅ odświeżany przy treningu |
| `docs/calendar_ablation_comparison.png` | ✅ aktualny |
| `docs/ablation_chart.png` | ⚠️ wymaga pełnej ablacji |
| `docs/academic_*.png` | ⚠️ fazy bez `3_Pogoda_Slonce_Reguly` |
| `docs/rf_convergence.png` | ⚠️ stary split / wszystkie kolumny |

`plot_pv_timeseries_comparison.py` — używać `feature_columns` z `.joblib` (nie `EXTENDED`).

---

## 8. Znane ograniczenia

- **Maj 2025** wykluczony z ML (misconfig falownika 21.04–29.05.2025); trening od **2025-06-01**.
- FoxESS na **bieżący dzień** w bazie pojawia się dopiero po sync — bez syncu hybryda używa lepszej pogody, ale nie pinuje rzeczywistej PV.
- Regularyzacja RF (`max_depth=6`) może **obniżyć** prognozę vs stary model 19-cechowy na pojedynczych pochmurnych dniach — na teście 80/20 nowy model jest lepszy.

---

*Autor aktualizacji: pipeline MLOps · data: 2026-07-13*
