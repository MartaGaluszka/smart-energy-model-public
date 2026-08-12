# Pobieranie wszystkich danych z FoxEss API

## Co zostanie pobrane?

| Źródło API | Zawartość | Gdzie trafia |
|------------|-----------|--------------|
| `get_vars()` + `get_history()` | **Wszystkie zmienne** co ~5 min (moc, napięcie, prąd, SOC, temperatury…) | `foxess_timeseries` + CSV `foxess_all_variables_*.csv` |
| Agregacja | Kluczowe kolumny (PV, bateria, sieć, zużycie) | `foxess_data` + CSV `foxess_core_*.csv` |
| `get_device()` | Metadane falownika H3 | `foxess_device_meta` |
| `get_report(day)` | Raporty godzinowe (30 dni) | `foxess_report_daily` |

## Uruchomienie

**Pełna procedura (połączenie, paczki miesięczne, sprawdzenie luki):** [FOXESS_KROK_PO_KROKU.md](FOXESS_KROK_PO_KROKU.md)

```bash
source venv/bin/activate   # albo: ./venv/bin/python …
./venv/bin/python src/test_connection.py
./venv/bin/python src/data/foxess_fetch_all.py --from 2025-11-01 --to 2025-11-30 --delay 2
```

Lub przez importer (domyślnie włączone przy `DATA_SOURCE=api`):

```bash
./venv/bin/python src/data/import_csv.py
```

## Konfiguracja `.env`

```bash
FOXESS_API_KEY=twój_klucz
DATA_SOURCE=api
FOXESS_FETCH_ALL=1

# Od kiedy importować (zalecane):
FOXESS_START_DATE=2025-05-01    # od maja 2025
# FOXESS_START_DATE=2025-04-01  # albo od kwietnia 2025
```

Opcjonalnie zamiast daty startu: `FOXESS_HISTORY_DAYS=365` (wstecz od dziś).

## Czas pobrazania

- **~1 s** między zapytaniami (limit API)
- **Maj 2025 → dziś** (~13 mies.) ≈ 7–12 minut
- **Kwiecień 2025 → dziś** (~14 mies.) ≈ 8–13 minut

## Sprawdzenie w bazie

```bash
sqlite3 data/energy_model.db
```

```sql
-- Ile zmiennych?
SELECT variable, COUNT(*) FROM foxess_timeseries GROUP BY variable;

-- Zakres dat
SELECT MIN(timestamp), MAX(timestamp) FROM foxess_timeseries;

-- Próbka
SELECT * FROM foxess_timeseries LIMIT 10;
```

## Uwagi

- Przy ponownym uruchomieniu mogą powstać **duplikaty** (INSERT append). Przed pełnym re-importem możesz usunąć starą bazę: `rm data/energy_model.db`
- API ma **limit wywołań dziennie** — przy bardzo długim zakresie rozłóż pobieranie na partie
