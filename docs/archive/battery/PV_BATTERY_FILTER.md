# Filtr danych PV - wykluczenie rozładowania baterii

Data: 2026-07-08

## 🎯 Problem

Dane `pv_energy_kwh` z FoxESS zawierają **nie tylko produkcję PV**, ale też **rozładowanie baterii**.

Przykład (11.01.2026, 6-8h):
- Radiacja: 0 W/m² (brak słońca)
- `pv_energy_kwh`: +0.158, +0.085 kWh (dodatnie!)
- `battery_power_kw`: -2.034, -1.196 kW (bateria się rozładowuje)

**Wniosek:** `pv_energy_kwh` = produkcja PV + rozładowanie baterii

---

## 📊 Analiza (dane 9-16h)

### Statystyki rozładowania baterii:

W tym dokumencie zostaną zapisane wyniki analizy po uruchomieniu skryptu.

---

## 💡 Rekomendowany filtr

### Warunek:
```sql
WHERE battery_power_kw >= -0.1
```

**Znaczenie:**
- `battery_power_kw < 0` = bateria rozładowuje się
- `battery_power_kw >= -0.1` = bateria **nie rozładowuje się** (lub minimalnie)
- Wartość -0.1 kW to próg szumu (niewielkie fluktuacje)

### Implementacja w kodzie Python:

```python
# W zapytaniu SQL:
pv = pd.read_sql_query('''
    SELECT 
        timestamp,
        date(timestamp) AS day,
        cast(strftime('%H', timestamp) AS integer) AS hour,
        SUM(CASE WHEN pv_energy_kwh > 0 AND battery_power_kw >= -0.1 
            THEN pv_energy_kwh ELSE 0 END) AS pv_kwh
    FROM foxess_data
    WHERE date(timestamp) BETWEEN ? AND ?
    GROUP BY timestamp
    ORDER BY timestamp
''', conn, params=(start_date, end_date))
```

### W funkcjach ładowania danych:

Pliki do aktualizacji:
- `src/data/weather_api.py` - funkcje `load_daily_pv()`, `load_daily_pv_daytime()`
- `src/features/snow_melt_model.py` - funkcja `load_hourly_weather_pv()`

---

## ⚠️ Wpływ na dane

### Oczekiwany wpływ:
- Usunięcie 2-5% rekordów w godzinach 9-16h
- Większy wpływ rano/wieczorem (gdy bateria często rozładowuje się)
- Minimalny wpływ w południe (gdy jest produkcja PV)

### Dni najbardziej dotknięte:
- Dni pochmurne z niską produkcją PV
- Dni zimowe z krótkim dniem
- Dni ze śniegiem (jak 11.01.2026)

### Korzyści:
✅ Czysta produkcja PV (bez baterii)
✅ Zgodność z danymi radiacji
✅ Lepsze modele ML (nie uczą się na artefaktach)

---

## 🔧 Wdrożenie

### Krok 1: Aktualizuj funkcje ładowania danych

Dodaj warunek `AND battery_power_kw >= -0.1` do wszystkich zapytań SQL pobierających `pv_energy_kwh`.

### Krok 2: Przetestuj wpływ

Porównaj wyniki modelu:
- PRZED filtrem
- PO zastosowaniu filtru

### Krok 3: Waliduj z danymi rzeczywistymi

Sprawdź czy filtrowane dane są zgodne z:
- Danymi radiacji (dni słoneczne → wysoka PV, dni pochmurne → niska PV)
- Zdjęciami paneli (dni ze śniegiem → niska PV)

---

## 📝 Przykładowy wynik (po wdrożeniu)

Dzień 11.01.2026:
- **PRZED:** 27.56 kWh (zawiera baterię)
- **PO:** ~2-3 kWh (tylko czysta PV)
- **Zgodność z radiację:** 534 Wh/m² → oczekiwane 2-3 kWh ✓

---

## ✅ Zalety rozwiązania

1. **Dokładność:** Czysta produkcja PV bez artefaktów
2. **Prostota:** Jeden prosty warunek SQL
3. **Nieinwazyjność:** Nie wymaga zmiany struktury bazy danych
4. **Odwracalność:** Łatwo można wrócić do surowych danych

---

**Status:** Gotowe do wdrożenia
**Priorytet:** Średni (modele działają OK, ale filtr poprawi jakość danych)
