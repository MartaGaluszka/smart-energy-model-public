# Tutorial SQL - Nauka na projekcie Smart Energy Model

## 🎓 Wprowadzenie

Ten tutorial nauczy Cię SQL używając Twojego własnego projektu jako przykładu.
Przejdziemy od podstaw do zaawansowanych zapytań.

## 📚 Część 1: Podstawy - Co to jest baza danych?

### Czym jest baza danych?

Baza danych to uporządkowany zbiór danych. Wyobraź sobie Excel z wieloma arkuszami:
- Każdy arkusz = **TABELA** w bazie danych
- Każda kolumna = **POLE** (column/field)
- Każdy wiersz = **REKORD** (row/record)

### Twoja baza danych `energy_model.db`

W Twoim projekcie masz 8 tabel:
1. `foxess_data` - dane z instalacji fotowoltaicznej
2. `tauron_tariff` - cennik energii
3. `tauron_forecast` - prognozy operatora
4. `tauron_bills` - rzeczywiste rachunki
5. `weather_data` - dane pogodowe
6. `ml_predictions` - predykcje modelu
7. `optimization_recommendations` - rekomendacje
8. `roi_analysis` - analiza zwrotu z inwestycji

---

## 📊 Część 2: Struktura tabeli - Przykład `foxess_data`

### Otwórz plik: `config/database_schema.sql`

Znajdź definicję tabeli `foxess_data`:

```sql
CREATE TABLE IF NOT EXISTS foxess_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    
    -- Produkcja fotowoltaiki
    pv_power_kw REAL,
    pv_energy_kwh REAL,
    
    -- Stan baterii
    battery_soc_percent REAL,
    battery_power_kw REAL,
    
    -- Zużycie energii
    load_power_kw REAL,
    load_energy_kwh REAL,
    
    -- Energia z/do sieci
    grid_import_kwh REAL,
    grid_export_kwh REAL,
    
    UNIQUE(timestamp, device_sn)
);
```

### Co to znaczy?

- **`CREATE TABLE`** - tworzy nową tabelę
- **`id INTEGER PRIMARY KEY`** - unikalny numer dla każdego rekordu
- **`timestamp DATETIME NOT NULL`** - data i czas (wymagane)
- **`pv_power_kw REAL`** - moc PV jako liczba rzeczywista
- **`UNIQUE(timestamp, device_sn)`** - nie może być duplikatów

### Typy danych:
- `INTEGER` - liczba całkowita (1, 2, 3, 100)
- `REAL` - liczba rzeczywista (3.14, 45.67)
- `TEXT` - tekst ("ABC", "Tauron")
- `DATETIME` - data i czas (2026-01-01 12:30:00)
- `BOOLEAN` - prawda/fałsz (0/1)

---

## 🔍 Część 3: Podstawowe zapytania SQL

### Uruchom konsolę SQLite:

```bash
cd /path/to/smart-energy-model
sqlite3 data/energy_model.db
```

### 1. Wyświetl wszystkie tabele

```sql
.tables
```

### 2. Zobacz strukturę tabeli

```sql
.schema foxess_data
```

### 3. SELECT - Pobieranie danych

#### Pobierz wszystko (uwaga: może być dużo!)
```sql
SELECT * FROM foxess_data LIMIT 10;
```

**Co to robi?**
- `SELECT *` - wybierz wszystkie kolumny
- `FROM foxess_data` - z tabeli foxess_data
- `LIMIT 10` - tylko 10 pierwszych wierszy

#### Pobierz tylko wybrane kolumny
```sql
SELECT 
    timestamp, 
    pv_energy_kwh, 
    load_energy_kwh,
    battery_soc_percent
FROM foxess_data
LIMIT 20;
```

#### Pobierz dane z konkretnego dnia
```sql
SELECT 
    timestamp,
    pv_energy_kwh,
    load_energy_kwh
FROM foxess_data
WHERE DATE(timestamp) = '2026-01-15'
ORDER BY timestamp;
```

**Co to robi?**
- `WHERE` - filtruje wyniki (tylko ten dzień)
- `ORDER BY` - sortuje po czasie

---

## 📈 Część 4: Agregacje - Obliczenia

### Ile mam danych?

```sql
SELECT COUNT(*) as liczba_rekordow 
FROM foxess_data;
```

### Jaka była średnia produkcja PV?

```sql
SELECT 
    AVG(pv_energy_kwh) as srednia_produkcja,
    MIN(pv_energy_kwh) as minimum,
    MAX(pv_energy_kwh) as maximum,
    SUM(pv_energy_kwh) as suma_produkcji
FROM foxess_data;
```

**Funkcje agregujące:**
- `COUNT()` - zlicza rekordy
- `AVG()` - średnia
- `MIN()` - minimum
- `MAX()` - maksimum  
- `SUM()` - suma

### Produkcja PV dzień po dniu

```sql
SELECT 
    DATE(timestamp) as dzien,
    SUM(pv_energy_kwh) as produkcja_dzienna,
    SUM(load_energy_kwh) as zuzycie_dzienne,
    AVG(battery_soc_percent) as sredni_soc
FROM foxess_data
GROUP BY DATE(timestamp)
ORDER BY dzien;
```

**Co to robi?**
- `GROUP BY` - grupuje dane (tu: po dniu)
- Dla każdego dnia oblicza sumę produkcji, zużycia i średni SOC

---

## 🔗 Część 5: JOIN - Łączenie tabel

### Po co łączyć tabele?

Żeby połączyć dane z różnych źródeł. Np. dane z FoxEss + cennik Tauron.

### Oblicz koszt energii dla każdego dnia

```sql
SELECT 
    DATE(f.timestamp) as dzien,
    SUM(f.grid_import_kwh) as import_z_sieci,
    t.price_zone1_day,
    SUM(f.grid_import_kwh) * t.price_zone1_day as koszt_energii
FROM foxess_data f
JOIN tauron_tariff t ON DATE(f.timestamp) >= t.valid_from
WHERE t.tariff_name = 'G12w'
GROUP BY DATE(f.timestamp);
```

**Co to robi?**
- Łączy `foxess_data` (alias `f`) z `tauron_tariff` (alias `t`)
- Dla każdego dnia oblicza koszt: import × cena

---

## 🎯 Część 6: Praktyczne ćwiczenia

### Zadanie 1: Znajdź najlepszy dzień produkcji PV

```sql
-- Twoje zapytanie tutaj
SELECT 
    DATE(timestamp) as dzien,
    SUM(pv_energy_kwh) as produkcja
FROM foxess_data
GROUP BY DATE(timestamp)
ORDER BY produkcja DESC
LIMIT 1;
```

### Zadanie 2: Kiedy bateria była najbardziej naładowana?

```sql
-- Twoje zapytanie tutaj
SELECT 
    timestamp,
    battery_soc_percent
FROM foxess_data
ORDER BY battery_soc_percent DESC
LIMIT 10;
```

### Zadanie 3: Średnie zużycie energii w weekendy vs dni robocze

```sql
-- Wskazówka: użyj funkcji STRFTIME('%w', timestamp)
-- gdzie 0=niedziela, 1=poniedziałek, ..., 6=sobota

SELECT 
    CASE 
        WHEN CAST(STRFTIME('%w', timestamp) AS INTEGER) IN (0, 6) 
        THEN 'Weekend'
        ELSE 'Dni robocze'
    END as typ_dnia,
    AVG(load_energy_kwh) as srednie_zuzycie
FROM foxess_data
GROUP BY typ_dnia;
```

### Zadanie 4: Ile energii oddałeś do sieci vs ile pobrałeś?

```sql
SELECT 
    SUM(grid_export_kwh) as oddane_do_sieci,
    SUM(grid_import_kwh) as pobrane_z_sieci,
    SUM(grid_export_kwh) - SUM(grid_import_kwh) as bilans
FROM foxess_data;
```

---

## 🛠️ Część 7: Modyfikowanie struktury

### Dodaj nową kolumnę do tabeli

```sql
ALTER TABLE foxess_data 
ADD COLUMN battery_voltage_v REAL;
```

### Usuń tabelę (UWAGA: nieodwracalne!)

```sql
DROP TABLE IF EXISTS nazwa_tabeli;
```

### Utwórz nową tabelę testową

```sql
CREATE TABLE test_table (
    id INTEGER PRIMARY KEY,
    name TEXT,
    value REAL
);
```

### Wstaw dane do tabeli

```sql
INSERT INTO test_table (name, value) 
VALUES ('test1', 123.45);

INSERT INTO test_table (name, value) 
VALUES ('test2', 678.90);
```

### Zaktualizuj dane

```sql
UPDATE test_table 
SET value = 999.99 
WHERE name = 'test1';
```

### Usuń dane

```sql
DELETE FROM test_table 
WHERE name = 'test2';
```

---

## 📖 Część 8: Praktyczne zastosowania w Twoim projekcie

### Stwórz własne zapytania do analizy:

#### 1. Autokonsumpcja (ile własnej energii zużywasz)

```sql
SELECT 
    DATE(timestamp) as dzien,
    SUM(pv_energy_kwh) as produkcja,
    SUM(load_energy_kwh) as zuzycie,
    SUM(grid_export_kwh) as eksport,
    (SUM(pv_energy_kwh) - SUM(grid_export_kwh)) / SUM(pv_energy_kwh) * 100 
        as autokonsumpcja_procent
FROM foxess_data
GROUP BY DATE(timestamp);
```

#### 2. Profil godzinowy (kiedy zużywasz najwięcej)

```sql
SELECT 
    CAST(STRFTIME('%H', timestamp) AS INTEGER) as godzina,
    AVG(load_power_kw) as srednia_moc,
    AVG(pv_power_kw) as srednia_pv
FROM foxess_data
GROUP BY godzina
ORDER BY godzina;
```

#### 3. Efektywność baterii (ile tracisz na cyklach ładowania)

```sql
SELECT 
    DATE(timestamp) as dzien,
    SUM(CASE WHEN battery_power_kw > 0 THEN battery_power_kw ELSE 0 END) as ladowanie,
    SUM(CASE WHEN battery_power_kw < 0 THEN ABS(battery_power_kw) ELSE 0 END) as rozladowanie,
    (rozladowanie / ladowanie) * 100 as efektywnosc_procent
FROM foxess_data
GROUP BY DATE(timestamp);
```

---

## 💡 Część 9: Narzędzia do pracy z SQL

### 1. Konsola SQLite (terminal)
```bash
sqlite3 data/energy_model.db
```

Komendy pomocnicze w konsoli:
- `.tables` - lista tabel
- `.schema nazwa_tabeli` - struktura tabeli
- `.mode column` - ładny format kolumn
- `.headers on` - pokaż nagłówki
- `.quit` - wyjdź

### 2. Python (programowo)

```python
import sqlite3
import pandas as pd

# Połącz z bazą
conn = sqlite3.connect('data/energy_model.db')

# Wykonaj zapytanie
query = "SELECT * FROM foxess_data LIMIT 10"
df = pd.read_sql_query(query, conn)

print(df)

conn.close()
```

### 3. Graficzne narzędzia (opcjonalnie)
- **DB Browser for SQLite** (darmowe) - https://sqlitebrowser.org/
- **DBeaver** (darmowe) - https://dbeaver.io/

---

## 🎓 Część 10: Zadania do samodzielnego wykonania

### Poziom Podstawowy:

1. Wyświetl 5 najnowszych pomiarów z foxess_data
2. Policz ile masz pomiarów z każdego miesiąca
3. Znajdź dzień z najwyższym zużyciem energii

### Poziom Średni:

4. Oblicz średnią produkcję PV dla każdej godziny dnia
5. Znajdź dni kiedy wyeksportowałeś więcej energii niż zaimportowałeś
6. Policz ile razy bateria była naładowana poniżej 20%

### Poziom Zaawansowany:

7. Stwórz ranking dni według samowystarczalności energetycznej
8. Oblicz średni koszt kWh dla każdego miesiąca
9. Znajdź korelację między temperaturą baterii a jej wydajnością

---

## 📚 Zasoby do nauki SQL

### Darmowe kursy online:
1. **SQLite Tutorial** - https://www.sqlitetutorial.net/
2. **W3Schools SQL** - https://www.w3schools.com/sql/
3. **Mode Analytics SQL Tutorial** - https://mode.com/sql-tutorial/

### Praktyka:
- **SQL Murder Mystery** (gra) - https://mystery.knightlab.com/
- **HackerRank SQL** - https://www.hackerrank.com/domains/sql

---

## 🚀 Co dalej?

Po opanowaniu podstaw SQL:

1. **Eksperymentuj** z własnymi zapytaniami
2. **Modyfikuj** strukturę bazy (dodaj kolumny, tabele)
3. **Optymalizuj** zapytania (indeksy, wydajność)
4. **Dokumentuj** swoje zapytania w projekcie

### Stwórz własne zapytania dla obrony projektu:

```sql
-- queries/
--   ├── daily_summary.sql
--   ├── monthly_roi.sql
--   ├── efficiency_analysis.sql
--   └── cost_comparison.sql
```

---

## 💪 Pamiętaj:

1. **Nie bój się eksperymentować** - zawsze możesz odtworzyć bazę
2. **Czytaj komunikaty błędów** - SQL jest bardzo konkretny
3. **Testuj na małych próbkach** (`LIMIT 10`) zanim uruchomisz na wszystkich danych
4. **Komentuj swój kod** (`-- to jest komentarz`)
5. **Zapisuj dobre zapytania** - będziesz ich potrzebować na obronie!

---

## ✅ Checklist nauki SQL:

- [ ] Rozumiem czym jest tabela, kolumna, rekord
- [ ] Potrafię użyć SELECT, WHERE, ORDER BY
- [ ] Umiem policzyć SUM, AVG, COUNT
- [ ] Wiem jak grupować dane (GROUP BY)
- [ ] Potrafię łączyć tabele (JOIN)
- [ ] Umiem tworzyć i modyfikować tabele
- [ ] Napisałem 5 własnych zapytań dla projektu
- [ ] Przygotowałem zapytania na obronę

**Powodzenia w nauce SQL!** 🎓

---

*Ten tutorial jest częścią projektu Smart Energy Model*
*Marta, czerwiec 2026*
