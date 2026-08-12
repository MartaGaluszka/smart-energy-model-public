# Przykładowe zapytania SQL - Smart Energy Model

Ten folder zawiera gotowe zapytania SQL do analizy danych energetycznych.

## 📊 Dostępne zapytania:

### 1. `daily_summary.sql` - Dzienny bilans energetyczny
Pokazuje dla każdego dnia:
- Produkcję PV
- Zużycie energii
- Wymianę z siecią (import/export)
- Autokonsumpcję
- Samowystarczalność

**Użycie:**
```bash
sqlite3 data/energy_model.db < queries/daily_summary.sql
```

### 2. `hourly_profile.sql` - Profil godzinowy
Średnia moc dla każdej godziny dnia:
- Produkcja PV
- Zużycie
- Praca baterii
- Strefy taryfowe G12w

**Przydatne do:** Analizy kiedy ładować baterię (strefa nocna tańsza)

### 3. `cost_comparison.sql` - Porównanie kosztów (NAJWAŻNIEJSZE!)
**To zapytanie jest kluczowe dla Twojego projektu!**

Pokazuje:
- Koszt gdyby nie było PV (baseline)
- Rzeczywisty koszt (z PV + bateria)
- Oszczędności w złotówkach i procentach
- Autokonsumpcję

**Użycie na obronie:** To zapytanie udowadnia wartość biznesową projektu!

### 4. `monthly_summary.sql` - Miesięczne podsumowanie
Agregacja danych miesięcznych do prezentacji:
- Całkowita produkcja/zużycie
- Średnie dzienne
- Wskaźniki efektywności

## 🚀 Jak używać zapytań?

### Metoda 1: Terminal (SQLite)
```bash
cd /path/to/smart-energy-model
sqlite3 data/energy_model.db < queries/daily_summary.sql
```

### Metoda 2: Konsola SQLite (interaktywnie)
```bash
sqlite3 data/energy_model.db
sqlite> .read queries/daily_summary.sql
```

### Metoda 3: Python
```python
import sqlite3
import pandas as pd

conn = sqlite3.connect('data/energy_model.db')

# Wczytaj zapytanie z pliku
with open('queries/daily_summary.sql', 'r') as f:
    query = f.read()

# Wykonaj i wyświetl
df = pd.read_sql_query(query, conn)
print(df)

conn.close()
```

### Metoda 4: Jupyter Notebook
```python
# W notebooku:
import sqlite3
import pandas as pd

conn = sqlite3.connect('../data/energy_model.db')

%%sql
-- Twoje zapytanie tutaj
SELECT * FROM daily_summary LIMIT 10;
```

## 💡 Tworzenie własnych zapytań

### Szablon nowego zapytania:

```sql
-- queries/moje_zapytanie.sql
-- Opis: co to zapytanie robi

SELECT 
    kolumna1,
    kolumna2,
    agregacja(kolumna3) as alias
FROM tabela
WHERE warunek
GROUP BY kolumna1
ORDER BY kolumna2;
```

### Wskazówki:

1. **Komentuj swój kod** (`-- komentarz`)
2. **Używaj aliasów** dla czytelności (`as srednia_produkcja`)
3. **Formatuj kod** - wcięcia dla czytelności
4. **Testuj na małych próbkach** (`LIMIT 10`)
5. **Zapisuj działające zapytania** - przydadzą się na obronie!

## 🎓 Nauka SQL

Kompletny tutorial SQL znajdziesz w: `docs/SQL_TUTORIAL.md`

## 📈 Zapytania dla obrony projektu

Na obronę przygotuj:

1. ✅ **Dzienny bilans** (`daily_summary.sql`)
2. ✅ **Porównanie kosztów** (`cost_comparison.sql`) - NAJWAŻNIEJSZE!
3. ✅ **Profil godzinowy** (`hourly_profile.sql`)
4. ✅ **Podsumowanie miesięczne** (`monthly_summary.sql`)

Dodatkowe (opcjonalnie):
- Analiza efektywności baterii
- Prognoza vs rzeczywistość
- Najlepsze/najgorsze dni produkcji

## 🔧 Modyfikowanie zapytań

Możesz modyfikować zapytania według potrzeb:

```sql
-- Zmień zakres dat:
WHERE DATE(timestamp) BETWEEN '2026-01-01' AND '2026-03-31'

-- Zmień grupowanie (dzień → tydzień):
GROUP BY STRFTIME('%Y-%W', timestamp)

-- Zmień sortowanie:
ORDER BY produkcja_pv DESC  -- od największej do najmniejszej
```

## 📝 Zapisywanie wyników

### Do pliku CSV:
```bash
sqlite3 -header -csv data/energy_model.db < queries/daily_summary.sql > output.csv
```

### Do tabeli w bazie:
```sql
CREATE TABLE daily_stats AS
SELECT * FROM (
    -- Twoje zapytanie tutaj
);
```

---

*Projekt: Smart Energy Model*
*Folder: queries/*
