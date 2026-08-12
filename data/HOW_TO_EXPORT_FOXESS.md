# Jak wyeksportować dane z FoxEss Cloud do CSV?

## Metoda 1: Portal Web (zalecana)

1. **Zaloguj się** na https://www.foxesscloud.com/
2. Przejdź do zakładki **"Raporty"** (Reports)
3. **Wybierz typ raportu:**
   - "Raport dzienny" (Daily Report) - dane godzinowe
   - "Raport miesięczny" (Monthly Report) - dane dzienne
   - "Raport roczny" (Yearly Report) - dane miesięczne

4. **Ustaw zakres dat:**
   - Data początkowa: np. 2026-01-01
   - Data końcowa: np. 2026-06-01
   - Im więcej danych historycznych, tym lepiej (min. 2-3 miesiące)

5. **Wybierz parametry do eksportu** (jeśli dostępne):
   - ✅ Produkcja PV (Solar Production)
   - ✅ Zużycie (Load/Consumption)
   - ✅ Stan baterii (Battery SOC)
   - ✅ Moc baterii (Battery Power)
   - ✅ Import/Export z sieci (Grid Import/Export)

6. **Kliknij "Eksport" → "CSV"**

7. **Zapisz plik** w folderze `data/raw/` jako np.:
   - `foxess_daily_2026_q1.csv` (dla danych dziennych Q1 2026)
   - `foxess_hourly_2026_01.csv` (dla danych godzinowych styczeń)

## Metoda 2: Aplikacja mobilna FoxEss

Niektóre wersje aplikacji mobilnej również mają opcję eksportu:

1. Otwórz aplikację **FoxEss** na telefonie
2. Przejdź do **"Dane"** lub **"Statistics"**
3. Wybierz zakres dat
4. Kliknij ikonę **"Udostępnij"** lub **"Export"**
5. Wybierz **"Eksport CSV"** lub **"Wyślij email"**

## Metoda 3: API (jeśli uzyskasz dostęp)

Jeśli uda Ci się uzyskać dostęp do API (klucz z portalu V1):

```python
import foxesscloud.openapi as foxess

foxess.api_key = "twoj_klucz_api"
device = foxess.get_device()

# Pobierz dane historyczne
raw = f.get_raw(start='2026-01-01', end='2026-06-01')
raw.to_csv('data/raw/foxess_api_data.csv')
```

## Ważne uwagi:

### Co powinien zawierać CSV?

Idealnie, CSV powinien mieć kolumny typu:
- `timestamp` lub `date` + `time` - znacznik czasu
- `pv_power` lub `solar_power` - moc fotowoltaiki [kW]
- `pv_energy` - energia z PV [kWh]
- `battery_soc` lub `soc` - stan baterii [%]
- `battery_power` - moc baterii [kW]
- `load_power` lub `consumption` - zużycie [kW]
- `grid_import` - import z sieci [kWh]
- `grid_export` - export do sieci [kWh]

**Nie martw się** jeśli Twój CSV ma inne nazwy kolumn - skrypt `import_csv.py` 
ma automatyczne mapowanie najpopularniejszych nazw!

### Jeśli nie możesz wyeksportować CSV:

1. **Spróbuj starszej wersji portalu** (V1): https://www.foxesscloud.com/user/center
2. **Skontaktuj się z supportem FoxEss** - poproś o możliwość eksportu danych
3. **Użyj screenshotów** - jako ostateczność możesz przepisać dane ręcznie 
   (nie idealne, ale dla demonstracji projektu może wystarczyć próbka)

### Ile danych potrzebujesz?

- **Minimum**: 1 miesiąc danych (wystarczy do prototypu)
- **Dobrze**: 3 miesiące (pozwala zobaczyć trendy)
- **Idealnie**: 6-12 miesięcy (pokrywa różne pory roku)

### Prywatność

Dane z FoxEss mogą zawierać informacje o Twoim wzorcu zużycia energii.
**Pamiętaj:**
- Pliki CSV są ignorowane przez git (.gitignore)
- NIE commituj danych osobowych do publicznego repozytorium
- Dla prezentacji projektu możesz zanonimizować dane

## Po pobraniu CSV:

1. Zapisz plik w `data/raw/`
2. Uruchom: `python src/data/import_csv.py`
3. Skrypt automatycznie zaimportuje dane do bazy SQLite

Gotowe! 🎉
