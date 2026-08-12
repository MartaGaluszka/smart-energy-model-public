# FoxESS — krok po kroku (połączenie, paczki, sprawdzenie bazy)

Jeden dokument z całą procedurą. Powiązane: [FETCH_ALL_DATA.md](FETCH_ALL_DATA.md), [API_CONFIGURATION.md](API_CONFIGURATION.md).

---

## 0. Przygotowanie (raz na sesję terminala)

```bash
cd /path/to/smart-energy-model
source venv/bin/activate
```

Na macOS poza venv **nie ma** komendy `python`. Bez activate używaj `./venv/bin/python …`.

W pliku `.env` musi być:

```bash
FOXESS_API_KEY=twój_klucz_z_portalu
# opcjonalnie, przy limicie API:
FOXESS_DEVICE_SN=YOUR_DEVICE_SN
```

---

## 1. Sprawdzenie połączenia z FoxESS

```bash
python src/test_connection.py
```

| Wynik | Znaczenie |
|-------|-----------|
| `✅ SUKCES!` + SN falownika | Możesz pobierać dane |
| `401 Unauthorized` | Zły/wygasły klucz w `.env` |
| `40402` / limit | Odczekaj (często do następnego dnia), nie uruchamiaj dużego importu |

Krótki test **czy chmura ma historię** za wybrany dzień (np. zima):

```bash
python scripts/foxess_test_missing_days.py 2025-11-01 2025-11-03
```

Oczekujesz: `OK` i tysiące punktów na dzień (nie `PUSTO`).

---

## 2. Pobieranie danych w paczkach (zalecane)

**Nie pobieraj całego roku jedną komendą** — limit API to ok. **1440 wywołań/dzień**.

Używaj gotowego skryptu:

```bash
python src/data/foxess_fetch_all.py --from YYYY-MM-DD --to YYYY-MM-DD --delay 2
```

### Brakująca zima (listopad 2025 – marzec 2026)

Uruchamiaj **po jednym miesiącu**, czekaj na `✅ Pobieranie zakończone`, potem następny:

```bash
python src/data/foxess_fetch_all.py --from 2025-11-01 --to 2025-11-30 --delay 2
python src/data/foxess_fetch_all.py --from 2025-12-01 --to 2025-12-31 --delay 2
python src/data/foxess_fetch_all.py --from 2026-01-01 --to 2026-01-31 --delay 2
python src/data/foxess_fetch_all.py --from 2026-02-01 --to 2026-02-28 --delay 2
python src/data/foxess_fetch_all.py --from 2026-03-01 --to 2026-03-28 --delay 2
```

### Luka październik 2025 (jeśli potrzebna)

```bash
python src/data/foxess_fetch_all.py --from 2025-10-27 --to 2025-10-31 --delay 2
```

### Parametry

| Parametr | Opis |
|----------|------|
| `--from` / `--to` | Zakres dat (włącznie) |
| `--delay 2` | Pauza 2 s między dniami (mniej 40402) |
| `--no-replace` | Nie usuń starego zakresu przed zapisem (domyślnie: usuwa w zakresie) |

Dane trafiają do: `data/energy_model.db` (+ opcjonalnie CSV w `data/raw/`).

---

## 3. Jak sprawdzić, czy masz pobrane wszystkie dane

### Przykład 1 — wszystkie miesiące naraz

Szybki przegląd całej bazy: które miesiące mają ile dni.

```bash
sqlite3 data/energy_model.db "
SELECT strftime('%Y-%m', timestamp) AS miesiac,
       COUNT(DISTINCT date(timestamp)) AS dni_w_bazie
FROM foxess_timeseries
GROUP BY 1 ORDER BY 1;"
```

**Jak czytać wynik:**

| `dni_w_bazie` | Znaczenie |
|---------------|-----------|
| **28–31** | Miesiąc wygląda na pełny |
| **0** lub **1–5** | Luka — trzeba dograć paczką `--from` / `--to` |
| **32** przy październiku | Zobacz [przykład 2](#przykład-2--jeden-konkretny-miesiąc-np-październik-2025) |

**Luka zimy** (przed importem) wyglądała tak: `2025-11` … `2026-02` = **0 dni**.

**Suma dni z danymi w okresie instalacji** (od pierwszego pełnego miesiąca do dziś — zmień datę końcową):

```bash
sqlite3 data/energy_model.db "
SELECT COUNT(DISTINCT date(timestamp)) AS dni
FROM foxess_timeseries
WHERE timestamp >= '2025-05-01' AND timestamp < '2026-06-05';"
```

---

### Przykład 2 — jeden konkretny miesiąc (np. październik 2025)

Po pobraniu paczki sprawdź **tylko ten miesiąc** — bez „dni z sąsiedniego miesiąca”:

```bash
sqlite3 data/energy_model.db "
SELECT COUNT(DISTINCT date(timestamp)) AS dni
FROM foxess_timeseries
WHERE strftime('%Y-%m', timestamp) = '2025-10';"
```

**Oczekiwany wynik dla pełnego października:** `31`

**Uwaga — dlaczego czasem wychodzi 32?**

Jeśli użyjesz filtra zakresowego zamiast `strftime('%Y-%m'`):

```bash
# może policzyć też 2025-09-30 (krawędź timestampów)
WHERE timestamp >= '2025-10-01' AND timestamp < '2025-11-01'
```

…wtedy `COUNT(DISTINCT date(...))` może dać **32** (= 31 dni października + 1 dzień z końcówki września).  
Do oceny „czy październik kompletny” używaj **przykładu 2** (`strftime('%Y-%m', ...) = '2025-10'`).

**Ten sam miesiąc z zakresem dat (od–do):**

```bash
sqlite3 data/energy_model.db "
SELECT COUNT(DISTINCT date(timestamp)) AS dni,
       MIN(date(timestamp)) AS od,
       MAX(date(timestamp)) AS do
FROM foxess_timeseries
WHERE strftime('%Y-%m', timestamp) = '2025-10';"
```

Zamień `'2025-10'` na `'2025-11'`, `'2025-12'`, `'2026-01'` itd. po każdej paczce importu.

---

### A) Pokrycie miesięcy — tabela `foxess_data` (notebook EDA)

Ten sam test na tabeli uproszczonej (używanej w notebooku):

```bash
sqlite3 data/energy_model.db "
SELECT strftime('%Y-%m', timestamp) AS miesiac,
       COUNT(DISTINCT date(timestamp)) AS dni
FROM foxess_data
GROUP BY 1 ORDER BY 1;"
```

### B) Zakres dat i liczba rekordów

```bash
sqlite3 data/energy_model.db "
SELECT MIN(timestamp), MAX(timestamp) FROM foxess_timeseries;
SELECT COUNT(*) AS wiersze FROM foxess_timeseries;
SELECT COUNT(DISTINCT variable) AS zmienne FROM foxess_timeseries;"
```

### C) Konkretnie zima (2025-11 → 2026-03)

```bash
sqlite3 data/energy_model.db "
SELECT strftime('%Y-%m', timestamp) AS m, COUNT(DISTINCT date(timestamp)) AS dni
FROM foxess_timeseries
WHERE timestamp >= '2025-11-01' AND timestamp < '2026-04-01'
GROUP BY 1 ORDER BY 1;"
```

Oczekiwane po pełnym imporcie: po **~28–31** dniach w każdym miesiącu (nie same zera).

### D) Notebook (wykres)

1. Otwórz `notebooks/01_EDA_analiza_danych.ipynb`
2. Kernel: **venv** projektu
3. **Run All** — sekcje **1b** (audyt) i **1c** (zima, import z sieci)

---

## 4. Gdy import się urwie (40402)

1. **Ctrl+C** w terminalu  
2. Sprawdź w portalu FoxESS: **User Profile → API Management** → remaining calls  
3. Następnego dnia powtórz **tylko miesiąc**, który się nie dokończył  
4. Nie uruchamiaj ponownie miesięcy, które już mają ~30 dni w bazie

---

## 5. Szybka ściąga

```text
source venv/bin/activate
python src/test_connection.py                    → połączenie OK?
python src/data/foxess_fetch_all.py --from … --to … --delay 2   → jeden miesiąc
sqlite3 … GROUP BY miesiac                       → ile dni w bazie?
notebook § 1b, 1c                                → wykresy
```

---

## 6. Gdzie to jest w projekcie

| Plik | Rola |
|------|------|
| `docs/FOXESS_KROK_PO_KROKU.md` | **Ten przewodnik** |
| `src/test_connection.py` | Test API |
| `src/data/foxess_fetch_all.py` | Import w paczkach |
| `scripts/foxess_test_missing_days.py` | Test 3–5 dni zimy |
| `docs/FETCH_ALL_DATA.md` | Co trafia do której tabeli |
| `notebooks/01_EDA_analiza_danych.ipynb` | Audyt + wykres zimy |
| `src/data/weather_api.py` | Klient Open-Meteo |
| `scripts/fetch_weather.py` | Import pogody → `weather_data` |
| `scripts/analysis/validate_weather_pv.py` | Walidacja pogody vs PV |

---

## 7. Pogoda (Open-Meteo) i walidacja vs PV

**Źródło:** [Open-Meteo](https://open-meteo.com/) — darmowe, bez klucza API, historia + prognoza (radiacja, zachmurzenie, opady).

### Konfiguracja `.env`

```bash
WEATHER_LAT=50.xx    # szerokość geogr. instalacji (nie wpisuj adresu do repo)
WEATHER_LON=19.xx    # długość geogr.
WEATHER_START_DATE=2025-04-21   # od danych licznika (remont IV–VIII 2025)
```

### Pobranie danych

```bash
source venv/bin/activate
python scripts/fetch_weather.py
```

Zapisuje godzinowe rekordy do tabeli `weather_data` (archiwum + prognoza 3 dni).

### Walidacja (czy pogoda pasuje do FoxESS)

```bash
python scripts/analysis/validate_weather_pv.py
```

Porównuje dziennie: suma radiacji / zachmurzenie (Open-Meteo) vs `pv_kwh_solar` (FoxESS, bez artefaktu baterii).  
Domyślny okres: od **2025-06-01** (pierwszy pełny miesiąc po naprawie falownika — to samo okno co ML/RF).

**Interpretacja:** korelacja PV ↔ radiacja **> 0,7** = dobry sygnał pod **Random Forest** i decyzje o ładowaniu baterii w nocy.

**Uwaga (okres falownika — do slajdu / pracy):**

> 21.04–29.05.2025: błędne ustawienia falownika hybrydowego (tryb pracy / priorytet baterii w aplikacji FoxESS) — produkcja PV nie odzwierciedlała pogody.  
> Od 30.05.2025: zmiana ustawień na maksymalną produkcję prądu.

Dane FoxESS z 21.04–29.05 **nie nadają się** do walidacji pogoda↔PV (limit baterii, nie pogoda). Domyślna walidacja od **2025-06-01** omija ten okres.

---

## 8. Licznik Tauron (kupione / oddane kWh)

**Start danych licznika:** `METER_DATA_START = GRID_PHYSICAL_START = 2025-04-21`.

Umowa Tauron od **28.03.2025**, ale przez kilka dni **bezpieczniki nie były załączone** — realny pobór i pierwsze wiarygodne odczyty od **21.04**. Pierwsza faktura (korekta 28.03–24.04, **333 kWh**) to **prognoza operatora** wystawiona do zapłaty; nie odzwierciedla profilu licznika (21–24.04 to tylko **~0,6 / 1,5 kWh**).

Bez PPE i numeru licznika w repo. Przydatne gdy FoxESS ma luki (np. **12–26.05.2025**).

### Zgodność licznika z fakturą (sprawdzone)

| Okres faktury | Faktura (pobór / oddanie) | Licznik CSV | Uwagi |
|---------------|---------------------------|-------------|-------|
| 25–30.04.2025 | 1 / 2 kWh | 1,58 / 2,16 kWh | ✅ ± zaokrąglenie stref T1/T2 |
| 05.2025 | 34 / 54 kWh | 33,95 / 54,54 kWh | ✅ ±0,5 kWh |
| 21–24.04.2025 | korekta prognoza **333 / 4** kWh | 0,62 / 1,54 kWh | prognoza ≠ licznik — nie porównywać 1:1 |
| 21–30.04.2025 | brak osobnej faktury | 2,24 / 3,70 kWh | okres startu PV + remont |

Od **06.2025** w bazie są tylko **faktury** (`tauron_bills`) — brak godzinowych CSV licznika (można dodać później).

**Eksport godzinowy CSV** z portalu (kolumny: `Data; Strefa; Wartość kWh; Rodzaj`).

Jeden plik (pobór + oddanie) **lub dwa osobne** (portal czasem eksportuje osobno):

```bash
# Pełny miesiąc (maj 2025)
python scripts/import_meter_csv.py data/raw/meter/2025-05_licznik.csv

# Dwa pliki — pobór + oddanie (kwiecień 21–30.04)
python scripts/import_meter_csv.py data/raw/meter/2025-04-21_30_pobor.csv data/raw/meter/2025-04-21_30_oddanie.csv
```

Import tworzy:
- `meter_hourly` — 1488 wierszy/godzinę (T1/T2, pobór/oddanie po zbilansowaniu)
- `meter_readings` — suma miesięczna (automatyczna agregacja)

| Okres | Pobór | Oddanie | Uwagi |
|-------|-------|---------|-------|
| 21–30.04.2025 | 2,2 kWh | 3,7 kWh | start danych licznika |
| 25–30.04.2025 | 1,6 kWh | 2,2 kWh | ≈ rozliczenie IV (1 / 2 kWh) |
| 05.2025 | 34 kWh | 55 kWh | ≈ rozliczenie V (34 / 54 kWh) |

**Główna analiza** (ROI, pogoda, bateria): od **01.09.2025**. Anomalie — na później.

