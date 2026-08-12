# Konfiguracja projektu

## 🔑 Konfiguracja API FoxEss

### 1. Uzyskaj klucz API

Postępuj zgodnie z instrukcją w `docs/API_ACCESS_REQUEST.md`:
- Zaloguj się do portalu V1: https://www.foxesscloud.com/user/center
- Przejdź do "API Management"
- Wygeneruj klucz API
- Skopiuj klucz (będzie długi!)

### 2. Skonfiguruj plik .env

Skopiuj `.env.example` do `.env`:
```bash
cp .env.example .env
```

Edytuj `.env` — **wystarczy sam klucz** (wg [Open API](https://www.foxesscloud.com/public/i18n/en/OpenApiDocument.html)):

```bash
FOXESS_API_KEY=twój_klucz_z_API_Management
DATA_SOURCE=api
```

Biblioteka `foxesscloud` sama dodaje nagłówki `timestamp`, `signature` i `lang` wymagane przez API.

### 3. Opcjonalnie: numer seryjny (tylko przy wielu falownikach)

`FOXESS_DEVICE_SN` **nie jest wymagany** przy jednej instalacji — API zwróci urządzenie powiązane z kontem.

Ustaw `FOXESS_DEVICE_SN` tylko gdy masz kilka urządzeń i chcesz wskazać konkretny parametr `sn` (historia / dane na żywo).

---

## 🚀 Użycie

### Test połączenia z API:

```bash
source venv/bin/activate
python src/data/foxess_api.py
```

Powinieneś zobaczyć:
```
✅ API działa poprawnie!
⚡ Nazwa instalacji: Twoja instalacja
🔢 Numer seryjny: ABC123...
```

### Import danych z API:

```bash
python src/data/import_csv.py
```

Skrypt automatycznie:
- Wykryje konfigurację w `.env`
- Połączy się z API
- Pobierze dane z ostatnich 30 dni
- Zaimportuje do bazy danych

---

## 🔄 Wybór źródła danych

Projekt może działać w dwóch trybach:

### Tryb 1: API (automatyczny)
```bash
DATA_SOURCE=api
FOXESS_API_KEY=twój_klucz
```

**Wymagania:** tylko api-key z portalu V1 (API Management).

**Zalety:** automatyczny import, bez ręcznego CSV.

### Tryb 2: CSV (ręczny)
```bash
# W pliku .env:
DATA_SOURCE=csv
```

**Zalety:**
- ✅ Działa bez API
- ✅ Pełna kontrola nad danymi

**Proces:**
1. Eksportuj CSV z FoxEss Cloud
2. Zapisz w `data/raw/`
3. Uruchom import:
```python
importer = EnergyDataImporter(use_api=False)
importer.import_foxess_csv('data/raw/foxess_2026.csv', device_sn='ABC123')
```

---

## 📊 Przykłady użycia API

### W skrypcie Python:

```python
from src.data.foxess_api import FoxEssAPI

# Inicjalizacja (automatycznie czyta .env)
api = FoxEssAPI()

# Test połączenia
api.test_connection()

# Pobierz dane z ostatnich 7 dni
df = api.get_raw_data(
    start_date='2026-05-25',
    end_date='2026-06-01'
)

print(df.head())

# Zapisz do CSV
df.to_csv('data/raw/foxess_api_data.csv', index=False)
```

### W Jupyter Notebook:

```python
from src.data.foxess_api import FoxEssAPI
import pandas as pd

api = FoxEssAPI()

# Pobierz dane
df = api.get_raw_data(start_date='2026-01-01', end_date='2026-03-31')

# Analiza
print(f"Rekordów: {len(df)}")
print(f"Zakres dat: {df['timestamp'].min()} - {df['timestamp'].max()}")

# Wizualizacja
import matplotlib.pyplot as plt
df.plot(x='timestamp', y='pv_energy_kwh', figsize=(12, 6))
plt.show()
```

---

## 🔧 Konfiguracja zaawansowana

### Wiele urządzeń (opcjonalnie):

```bash
FOXESS_DEVICE_SN=ABC123456
```

```python
api = FoxEssAPI(device_sn='ABC123456')
```

### Harmonogram automatyczny (cron):

```bash
# Dodaj do crontab (codziennie o 23:00):
0 23 * * * cd /path/to/smart-energy-model && /path/to/venv/bin/python src/data/import_csv.py >> logs/import.log 2>&1
```

---

## ❓ Troubleshooting

### Błąd: "Brak klucza API"
```bash
❌ ValueError: Brak klucza API! Ustaw FOXESS_API_KEY w pliku .env
```

**Rozwiązanie:**
1. Sprawdź czy plik `.env` istnieje
2. Sprawdź czy jest zmienna `FOXESS_API_KEY=...`
3. Usuń spacje wokół `=`

### Błąd: "Invalid API key"
```bash
❌ Błąd połączenia: 401 Unauthorized
```

**Rozwiązanie:**
1. Sprawdź czy klucz jest poprawny (skopiowany cały)
2. Sprawdź czy klucz nie wygasł
3. Zregeneruj klucz w portalu V1

### Brak urządzeń na koncie
```bash
⚠️ Klucz OK, ale brak urządzeń
```

**Rozwiązanie:** sprawdź, czy falownik jest przypisany do tego samego konta co klucz API. `FOXESS_DEVICE_SN` ustaw tylko przy wielu instalacjach.

### API działa, ale brak danych
```bash
⚠️ Brak danych dla podanego zakresu
```

**Rozwiązanie:**
1. Sprawdź zakres dat (może być za stary lub przyszły)
2. Sprawdź czy instalacja działała w tym okresie
3. Spróbuj krótszego zakresu (7 dni)

---

## 📝 Checklist konfiguracji

- [ ] Uzyskałem klucz API z portalu V1
- [ ] Skopiowałem `.env.example` do `.env`
- [ ] Uzupełniłem `FOXESS_API_KEY` w `.env`
- [ ] (Opcjonalnie) `FOXESS_DEVICE_SN` — tylko przy wielu falownikach
- [ ] Ustawiłem `DATA_SOURCE=api` w `.env`
- [ ] Uruchomiłem test: `python src/data/foxess_api.py`
- [ ] Test pokazuje ✅ - połączenie działa!
- [ ] Zaimportowałem dane: `python src/data/import_csv.py`
- [ ] Dane są w bazie - mogę rozpocząć analizę!

---

**Gotowe!** Możesz teraz korzystać z API do automatycznego pobierania danych! 🎉
