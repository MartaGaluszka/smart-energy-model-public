# EDA — Analiza Eksploracyjna Danych PV

**Notebook:** [`notebooks/01_EDA_analiza_danych.ipynb`](../notebooks/01_EDA_analiza_danych.ipynb)  
**Status:** Production-ready (lipiec 2026)  
**Autor:** Marta Gałuszka

---

## 1. Cel analizy

Notebook EDA stanowi warstwę **Data Quality Assurance** dla systemu Smart Home PV. Odpowiada na pytania:

- Czy dane FoxESS pokrywają pełny kalendarz instalacji?
- Czy obserwowane „zera” produkcji to fizyczna rzeczywistość (śnieg, mgła), czy luki telemetryczne?
- Czy agregacja PV jest spójna z Tauron (sanity check, nie źródło treningu)?

---

## 2. Jakość danych (Data Quality)

### 2.1 Luki telemetryczne IoT — styczeń/luty 2026

Na wykresach szeregów czasowych PV (notebook ML + EDA) zidentyfikowano **nienaturalnie proste segmenty** łączące odległe punkty na przełomie **stycznia i lutego 2026**. Objawy:

- Wykres `plot` łączy kolejne dostępne obserwacje linią — przy **rzadkich punktach** powstaje pozorna „rampa” lub plateau.
- Część dni była **filtrowana przy wczytywaniu** (zbyt agresywny `_is_artifact_day` zimą), mimo że rekordy **istniały w bazie** (`foxess_data`: 59/59 dni sty+lut 2026).

**Diagnostyka (kod w projekcie):**

| Skrypt / moduł | Rola |
|----------------|------|
| `scripts/diagnose_jan_feb_line.py` | Wykrywa efekt „prostej linii” na wykresie |
| `scripts/verify_data_completeness.py` | Liczba dni per miesiąc po filtrach |
| `scripts/validate_battery_filter_vs_tauron.py` | FoxESS vs Tauron vs filtr baterii |
| `UPDATE_2026-07-09_filtr-baterii.md` | Pełny raport incydentu → [`archive/battery/`](archive/battery/UPDATE_2026-07-09_filtr-baterii.md) |

**Naprawa filtrów (stan produkcyjny):**

- `_is_artifact_day` — tylko okres misconfig falownika (21.04–29.05.2025), nie cała zima.
- Filtr baterii `battery_power_kw >= -0.1` — przy **odczycie**, nie przy imporcie.
- Dynamiczne godziny wschód–zachód zamiast sztywnego 9–16h.

### 2.3 „Zdrowe zera” vs braki transmisji

Nie każde PV ≈ 0 kWh oznacza błąd telemetrii. System rozróżnia:

| Typ | Opis | Walidacja |
|-----|------|-----------|
| **Zdrowe zero** | Śnieg/mgła blokują panele; radiacja niska lub yield anomalny | **Kalibracja:** model topnienia śniegu (`snow_melt_model.py`), heurystyka mgły — **nie** ręczne etykiety ze zdjęć |
| **Artefakt baterii** | Rozładowanie baterii księgowane jako PV | Filtr `battery_power >= -0.1 kW` |
| **Luka IoT** | Brak próbek w `foxess_data` mimo oczekiwanego dnia | `sync_data.py` + SQL |

**Zdjęcia z kamery** służą wyłącznie do **walidacji** kalibracji (ground truth). W treningu modelu używane są wyłącznie cechy wyprowadzone z danych pogodowych i FoxESS.

### 2.3 Rozwiązanie systemowe — potok `sync_data.py`

Ostateczna architektura ingestii:

```
FoxESS API ──► foxess_data (surowe)
Open-Meteo  ──► weather_data (historia + prognoza)
                      │
                      ▼
              sync_data.py (wykrywa luki, uzupełnia zakres)
                      │
                      ▼
         load_* / pv_features_* (filtry przy odczycie)
```

```bash
python scripts/sync_data.py          # pełna synchronizacja
python scripts/sync_data.py --dry-run  # audyt luk bez pobierania
```

---

## 3. Źródła danych w EDA

| Źródło | Tabela | Użycie w EDA |
|--------|--------|--------------|
| FoxESS Cloud | `foxess_data` | Produkcja PV, bateria, sieć |
| Open-Meteo | `weather_data` | Radiacja, temperatura, wilgotność |
| Tauron | `tauron_bills`, `meter_readings` | **Walidacja** importu/eksportu — nie target ML |
| IMGW | `weather_data` (stacja) | Głębokość śniegu |

---

## 4. Kluczowe wykresy EDA

1. **Pokrycie miesięczne** — liczba dni z danymi FoxESS vs oczekiwana liczba dni w miesiącu.
2. **Profil dobowy** — import/export vs strefy G12w.
3. **PV vs radiacja** — yield kWh/kWh/m²; odchylenia → kandydaci na mgłę/śnieg.
4. **Sezonowość** — wiosna/jesień jako okresy krytyczne dla baterii (patrz `PROJECT_STATUS.md`).

### 4.1 Korelacja PV ↔ pogoda (Open-Meteo, dzienne sumy)

Okres **2025-06-01 → dziś** (`pv_kwh_solar` vs agregaty dzienne z ICON):

| Para | Pearson r | Interpretacja |
|------|----------:|---------------|
| PV ↔ suma radiacji | **0,87** | silny sygnał — **> 0,7** uzasadnia RF z cechami pogodowymi |
| PV ↔ (−zachmurzenie) | **0,68** | umiarkowany; chmury tłumaczą część wariancji obok radiacji |

Skrypt: `python scripts/analysis/validate_weather_pv.py` · notebook: `01_EDA_analiza_danych.ipynb` §2b.  
Stan: **437 dni wspólnych** (2025-06-01 → 2026-08-11).

---

## 5. Kontekst czasowy (skrót)

| Okres | Uwagi dla EDA/ML |
|-------|------------------|
| 21.04–29.05.2025 | Misconfig falownika — wykluczyć z treningu |
| od 30.05.2025 | PV zależne od pogody |
| od 2025-06-01 | Korelacja pogoda↔PV i okno ML/RF (436+ dni wspólnych) |
| od 01.09.2025 | Normalne użytkowanie, ROI |
| sty–lut 2026 | Incydent filtrów + weryfikacja Tauron — **naprawione** |

---

## 6. Powiązane dokumenty

- [`02_ML_predykcja_PV.md`](02_ML_predykcja_PV.md) — model, tuning, holdout
- [`03_ZALOZENIA_I_DECYZJE.md`](03_ZALOZENIA_I_DECYZJE.md) — założenia do prezentacji
- [`../README.md`](../README.md) — architektura wdrożeniowa
- [`archive/battery/UPDATE_2026-07-09_filtr-baterii.md`](archive/battery/UPDATE_2026-07-09_filtr-baterii.md) — raport filtra baterii
- [`archive/data-quality/`](archive/data-quality/) — naprawy luk (sty/lut, kwiecień–maj)
- [`archive/weather-features/`](archive/weather-features/) — śnieg, mgła, godziny dynamiczne
- [`archive/README.md`](archive/README.md) — mapa całego archiwum notatek
- [`FOXESS_KROK_PO_KROKU.md`](FOXESS_KROK_PO_KROKU.md) — pobieranie danych API

---

*Ostatnia aktualizacja: 2026-08-11*


---

## 7. Data leakage — eliminacja importu Tauron z treningu

Wczesne wersje pipeline mogły niejawnie mieszać **import energii z sieci** (widoczny na liczniku Tauron) z produkcją PV. Obecna architektura:

- **Trening ML:** wyłącznie FoxESS + Open-Meteo (+ cechy kalibracyjne wyprowadzone z pogody)
- **Tauron:** walidacja eksportu/importu, moduł ROI — poza modelem predykcji PV
- **Filtr baterii:** eliminuje artefakt księgowania rozładowania jako PV

