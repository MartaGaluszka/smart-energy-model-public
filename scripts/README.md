# scripts/ — trening, wykresy, analizy

Produkcja MLOps (sync, forecast, launchd) jest w **[`mlops/`](../mlops/)**.

## Podfoldery

| Folder | Rola |
|--------|------|
| **`train/`** | Trening modelu (produkcyjny: `train_hourly_model_tuning.py`) |
| **`plots/`** | Generowanie wykresów → `reports/figures/` |
| **`analysis/`** | Jednorazowe analizy, Tauron, diagnostyki, porównania |

## Złota ścieżka (skrót)

```bash
# macOS: poza venv nie ma `python` — użyj ./venv/bin/python albo source venv/bin/activate
./venv/bin/python mlops/sync_data.py
./venv/bin/python scripts/train/train_hourly_model_tuning.py
./venv/bin/python mlops/forecast_pv.py --days 2 --top 5
./mlops/install_launchd.sh --status
```

Biblioteki: `src/` · modele: `models/` · testy: `tests/`.
