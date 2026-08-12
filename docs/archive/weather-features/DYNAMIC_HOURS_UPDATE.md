# Aktualizacja: Dynamiczna długość produkcji słonecznej

**Data**: 2026-07-08
**Autor**: Agent + User

## 🎯 Cel aktualizacji

Zaktualizowano wszystkie pliki projektu, aby odzwierciedlały dynamiczną długość produkcji słonecznej zamiast sztywnego okna 9-16h.

## 📊 Kluczowe zmiany

### 1. Model Dzienny
- **Target**: `pv_kwh_daytime` (suma 9-16h - agregacja historyczna)
- **Uwaga**: To jest agregacja historyczna. Rzeczywista produkcja PV zależy od długości dnia:
  - Lato: 5-20h (15h produkcji)
  - Zima: 7-15h (8h produkcji)
  - Wiosna/Jesień: zmienne (9-17h)

### 2. Model Godzinowy (Nowy, Główny)
- **Target**: `pv_kwh_hour` w każdej godzinie
- **Dynamiczne godziny**: 5-20h z automatycznym dostosowaniem do wschodu/zachodu słońca
- **Cechy słoneczne**:
  - `sunrise_hour`, `sunset_hour` - godziny wschodu/zachodu słońca (Europe/Warsaw)
  - `day_length_hours` - długość dnia
  - `hours_since_sunrise`, `hours_until_sunset` - pozycja w dniu słonecznym
  - `sun_position` - znormalizowana pozycja słońca (0=wschód, 1=zachód)
  - `is_daylight` - czy jest dzień słoneczny
- **Wydajność**: MAE 0.664 kWh/h, brak przeuczenia

### 3. Model Bazowy Godzinowy (Usunięty)
- Sztywne godziny 9-16h - **PRZESTARZAŁY**
- Tracił 17-35% produkcji (brak 5-9h i 16-20h latem)
- Zastąpiony modelem rozszerzonym z dynamicznymi godzinami

## 📝 Zaktualizowane pliki

### Dokumentacja
- **MODELS_README.md** - Kompletna dokumentacja modeli z dynamicznymi godzinami
- **DYNAMIC_HOURS_UPDATE.md** - Ten plik

### Moduły główne
- **src/features/pv_features.py** - Dodano uwagi o agregacji historycznej
- **src/features/pv_features_hourly.py** - Oznaczony jako PRZESTARZAŁY
- **src/features/pv_features_hourly_extended.py** - Główny moduł godzinowy

### Skrypty treningowe
- **scripts/train_pv_models.py** - Dodano uwagi o agregacji historycznej
- **scripts/train_hourly_model.py** - Używa dynamicznych godzin

### Skrypty walidacji i kalibracji
- **scripts/calibrate_snow_melt.py** - Dodano uwagi o agregacji
- **scripts/cv_pv_groupkfold.py** - Dodano uwagi o agregacji
- **scripts/validate_weather_pv.py** - Zaktualizowane etykiety (pv_9_16_agg)
- **scripts/find_snow_pv_loss_days.py** - Dodano uwagi o agregacji
- **scripts/calibrate_weather_flags.py** - Zaktualizowane nazwy kolumn
- **scripts/validate_snow_photos.py** - Zaktualizowane nazwy kolumn

### Moduły danych
- **src/data/weather_api.py** - Dodano uwagi o agregacji historycznej

## 🔑 Kluczowe pojęcia

### Agregacja historyczna (9-16h)
- **Definicja**: Suma produkcji PV w godzinach 9-16 (stałe okno)
- **Użycie**: Target dla modelu dziennego (`pv_kwh_daytime`)
- **Ograniczenia**: Nie uwzględnia produkcji poza 9-16h (5-9h i 16-20h latem)
- **Kiedy używać**: Planowanie ogólne, oszacowania dzienne

### Dynamiczna długość dnia
- **Definicja**: Godziny produkcji dostosowane do wschodu/zachodu słońca
- **Użycie**: Model godzinowy rozszerzony
- **Zakres**: 5-20h z filtrowaniem minimalnej produkcji
- **Kiedy używać**: Harmonogramy urządzeń, optymalizacja baterii

## 🚀 Jak używać nowych modeli

### Dla planowania ogólnego (dzienny)
```bash
python scripts/train_pv_rf_only.py
```
- Używa agregacji historycznej 9-16h
- Prosty, szybki, wystarczający dla większości zastosowań

### Dla harmonogramów godzinowych (precyzyjny)
```bash
python scripts/train_hourly_model.py
```
- Używa dynamicznych godzin 5-20h
- Uwzględnia wschód/zachód słońca
- Najlepszy do optymalizacji urządzeń i baterii

## 📈 Porównanie wydajności

| Model | Godziny | MAE | Przeuczenie | Zastosowanie |
|-------|---------|-----|-------------|--------------|
| Dzienny | Agregacja 9-16h | 3.594 kWh/d | ✅ Brak | Planowanie ogólne |
| Godzinowy | Dynamiczne 5-20h | 0.664 kWh/h | ✅ Brak | Harmonogramy precyzyjne |
| ~~Bazowy~~ | ~~Sztywne 9-16h~~ | ~~0.957 kWh/h~~ | ⚠️ Lekkie | ❌ USUNIĘTY |

## 💡 Najważniejsze cechy godzinowego modelu

1. **radiation_wm2** (34%) - promieniowanie słoneczne
2. **sun_position** (25%) - pozycja słońca (0=wschód, 1=zachód)
3. **hours_until_sunset** (11%) - czas do zachodu słońca
4. **sunrise_hour**, **sunset_hour** - dynamiczne okno produkcji

## 🎓 Wnioski

1. **Model dzienny** - nadal używa agregacji 9-16h, ale teraz jest jasne, że to tylko agregacja historyczna
2. **Model godzinowy** - uwzględnia pełną długość dnia (5-20h latem, 7-15h zimą)
3. **Wszystkie pliki** - zaktualizowane z uwagami o tym, że 9-16h to agregacja historyczna, a rzeczywista produkcja zależy od długości dnia
4. **Nazewnictwo** - zmieniono z "pv_9_16" na "pv_9_16_agg" w skryptach walidacji dla jasności

## ✅ Status

- [x] Zaktualizowano dokumentację (MODELS_README.md)
- [x] Zaktualizowano moduły cech (pv_features.py, pv_features_hourly_extended.py)
- [x] Zaktualizowano skrypty treningowe (train_pv_models.py, train_hourly_model.py)
- [x] Zaktualizowano skrypty walidacji (calibrate_snow_melt.py, cv_pv_groupkfold.py, validate_weather_pv.py)
- [x] Zaktualizowano skrypty pomocnicze (find_snow_pv_loss_days.py, calibrate_weather_flags.py, validate_snow_photos.py)
- [x] Zaktualizowano moduły danych (weather_api.py)
- [x] Oznaczono model bazowy jako przestarzały (pv_features_hourly.py)

## 📅 Następne kroki

1. Uruchomić testy, aby upewnić się, że wszystkie zmiany działają
2. Sprawdzić, czy nie ma innych plików z referencjami do 9-16h
3. Rozważyć stworzenie nowych kolumn w bazie danych z dynamicznymi godzinami
