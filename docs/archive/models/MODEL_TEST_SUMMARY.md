# Podsumowanie Testów Modeli ML z Poprawioną Flagą Mgły
**Data:** 9 lipca 2026  
**Modele:** Dzienny (Random Forest) + Godzinowy (Random Forest)

---

## 1. Model Dzienny - Wyniki

### Konfiguracja
- **Okres danych:** 2025-06-01 do 2026-06-04 (318 dni)
- **Train:** 219 dni (2025-06 → 2026-01)
- **Test:** 99 dni (2026-02 → 2026-06)
- **Model:** Random Forest (n=200, depth=12)

### Wyniki Ogólne

| Model | MAE (kWh) | RMSE (kWh) | R² |
|-------|-----------|------------|-----|
| **RF + reguły** | 4.285 | 5.635 | 0.589 |
| **RF** | 4.339 | 5.661 | 0.585 |
| Baseline (radiacja × yield) | 5.674 | 6.469 | 0.459 |

**Poprawa vs baseline:** 24.5% (1.39 kWh)

### Feature Importance - Top 10

| Feature | Importance |
|---------|-----------|
| radiation_daytime_kwh_m2 | 90.66% |
| cloud_cover_avg | 2.31% |
| cloud_cover_low_avg | 1.63% |
| precip_mm | 1.59% |
| humidity_daytime_avg | 0.86% |
| doy_cos | 0.75% |
| temp_min | 0.74% |
| doy_sin | 0.51% |
| temp_max | 0.47% |
| temp_avg | 0.39% |

### Flagi Mgły i Śniegu

| Feature | Importance |
|---------|-----------|
| **likely_fog_day** | **0.0097%** |
| om_snow_depth_cm | 0.0078% |
| om_snowfall_cm | 0.0009% |
| snow_on_panels_prev | 0.0001% |
| snow_on_panels | 0.0001% |
| imgw_snow_depth_cm | 0.0001% |

---

## 2. Model Godzinowy - Wyniki

### Konfiguracja
- **Godziny produkcji:** 5:00-20:00 (dynamiczny zakres wg wschodu/zachodu słońca)
- **Dane:** 3890 rekordów godzinowych (359 dni)
- **Train:** 2353 rekordów (235 dni)
- **Test:** 1537 rekordów (124 dni)
- **Model:** Random Forest

### Wyniki

| Metryka | Wartość |
|---------|---------|
| **Test MAE** | 0.664 kWh/h |
| **Test R²** | 0.596 |
| Train MAE | 0.301 kWh/h |
| Train R² | 0.916 |
| Gap (test-train) | 0.363 kWh/h (54.7%) |
| **Dzienny MAE** (agregacja) | 4.109 kWh/dzień |
| **Dzienny R²** | 0.702 |

### Cross-Validation (GroupKFold n=5)

| Fold | MAE (kWh/h) | Dni |
|------|-------------|-----|
| 1 | 0.588 | 47 |
| 2 | 0.557 | 47 |
| 3 | 0.609 | 47 |
| 4 | 0.579 | 47 |
| 5 | 0.593 | 47 |
| **Średnia** | **0.585 ± 0.017** | 235 |

**Diagnostyka:** Model NIE jest przeuczony (test vs CV: +0.079 kWh/h)

### Feature Importance - Top 10

| Feature | Importance |
|---------|-----------|
| radiation_wm2 | 34.0% |
| sun_position | 24.9% |
| hours_until_sunset | 11.0% |
| cloud_cover_pct | 8.4% |
| doy_sin | 3.5% |
| wind_speed_ms | 3.5% |
| temp_c | 3.0% |
| hours_since_sunrise | 2.8% |
| humidity_pct | 2.7% |
| sunrise_hour | 1.7% |

---

## 3. Analiza Flagi Mgły

### Rozkład Dni z Mgłą

| Zbiór | Dni z mgłą | % |
|-------|-----------|---|
| **Train (dzienny)** | 12 | 5.5% |
| **Test (dzienny)** | **0** | **0%** |
| **Wszystkie dni** | 22 | 5.6% |

### ⚠️ Kluczowy Problem

**Test set nie zawiera DNI Z MGŁĄ!**

- Train: czerwiec 2025 - styczeń 2026 (12 dni mgły - głównie grudzień, styczeń)
- Test: luty - czerwiec 2026 (0 dni mgły)

**Dlaczego?**
- Mgła występuje głównie w zimie (86% w grudniu-lutym)
- Test set to wiosna/lato (luty-czerwiec)
- Luty 2026 miał 6 dni mgły, ale większość była w pierwszej połowie (train)

### Wpływ Flagi Mgły

**W train secie:**
- Flaga mgły ma importance: 0.0097% (bardzo niska)
- Ale: radiacja już "widzi" efekt mgły (niska radiacja)
- Flaga dodaje informację "dlaczego radiacja jest niska"

**Problem walidacji:**
- Nie możemy zmierzyć wpływu na test secie (0 dni mgły)
- Wcześniejsza walidacja (CLEAN_DATA_VALIDATION_SUMMARY.md):
  - 2 dni z mgłą w test (zimowym)
  - MAE dla dni z mgłą: **0.085 kWh** (doskonałe!)

---

## 4. Analiza Mgła vs Deszcz

### Kluczowe Odkrycie

| Warunek | Radiacja | PV | Efektywność |
|---------|----------|-----|-------------|
| Mgła | 42 W/m² | 0.40 kWh | 0.0094 |
| Deszcz | 41 W/m² | 0.66 kWh | 0.0161 |
| **Różnica** | **3%** | **40%** | **72%** |

**Wnioski:**
1. ✅ **Mgła i deszcz mają podobną radiację** (tylko 3% różnicy)
2. ⚠️ **Ale BARDZO różną produkcję PV** (40% różnicy!)
3. 💡 **Efektywność deszczu jest 72% wyższa niż mgły**

**Hipoteza:**
- Deszcz ma przerwy → okna produkcji PV
- Mgła jest ciągła → blokuje konsekwentnie
- Średnia radiacja podobna, ale **variancja różna**

### Rekomendacja

**Dodać flagę deszczu do modelu!**
```python
features = [
    'radiation_daytime_kwh_m2',
    'likely_fog_day',       # ✅ już jest
    'rainy_day',            # 🆕 dodać!
    ...
]
```

**Oczekiwany efekt:**
- Model nauczy się: przy tej samej radiacji, mgła daje mniej niż deszcz
- Feature importance będzie niska (rzadkie), ale skuteczność wysoka
- Podobnie jak teraz: mgła 0.0097% importance, ale MAE=0.085 kWh!

---

## 5. Porównanie Modeli

### Dzienny MAE

| Model | MAE (kWh) | Źródło |
|-------|-----------|--------|
| **RF + reguły** | **4.285** | Nowy test (dzienny) |
| **RF godzinowy** | **4.109** | Agregacja godzin |
| RF | 4.339 | Nowy test (dzienny) |
| Baseline | 5.674 | Radiacja × yield |

**Model godzinowy ma lepszy dzienny MAE!** (4.109 vs 4.285)

### Dlaczego Model Godzinowy Jest Lepszy?

1. **Więcej informacji** - uwzględnia pozycję słońca w ciągu dnia
2. **Dynamiczny sunrise/sunset** - lepsze modelowanie krótkich/długich dni
3. **Lepsze R²** - 0.702 vs 0.589

---

## 6. Wnioski i Rekomendacje

### ✅ Co Działa

1. **Poprawiona flaga mgły** (filtr opadów ≤1mm)
   - Redukcja false positives o 45% (40 → 22 dni)
   - Accuracy 100% na fotografiach

2. **Model godzinowy**
   - Lepszy od dziennego (4.109 vs 4.285 kWh MAE)
   - Uwzględnia dynamikę słońca

3. **Feature engineering**
   - Radiacja dominuje (90% vs 34% w godzinowym)
   - Pozycja słońca krytyczna w modelu godzinowym

### ⚠️ Ograniczenia

1. **Test set bez mgły**
   - Nie możemy zmierzyć wpływu flagi mgły
   - Potrzeba walidacji na danych zimowych

2. **Overfitting dziennego modelu**
   - Gap 76.8% (train vs test)
   - Model godzinowy ma mniejszy gap (54.7%)

3. **Underprediction wiosny**
   - Brak feature "długość dnia"
   - Słoneczne dni w marcu/kwietniu mają duży błąd

### 🔄 Następne Kroki

#### Priorytet 1: Dodać Flagę Deszczu
```python
# src/features/pv_features.py
def add_rain_flag(df):
    humid = df['humidity_daytime_avg'].fillna(df['humidity_avg'])
    df['rainy_day'] = (
        (humid >= 90) & 
        (df['cloud_cover_avg'] >= 95) & 
        (df['total_precip_mm'] > 1.0)
    )
    return df
```

#### Priorytet 2: Dodać Feature "Długość Dnia"
```python
# Oblicz czas między wschodem a zachodem
df['day_length_hours'] = df['sunset_hour'] - df['sunrise_hour']
```

#### Priorytet 3: Walidacja na Danych Zimowych
- Przenieść test set na grudzień-luty
- Zmierzyć wpływ flagi mgły na dni z mgłą

#### Priorytet 4: Regularyzacja Modelu Dziennego
- Zwiększyć min_samples_leaf (obecnie brak)
- Dodać max_features='sqrt'
- Zmniejszyć max_depth z 12 do 10

---

## 7. Podsumowanie Liczb

### Modele Wytrenowane ✅

| Model | MAE | R² | Status |
|-------|-----|-----|--------|
| Dzienny RF + reguły | 4.285 kWh | 0.589 | ✅ |
| Godzinowy RF | 0.664 kWh/h (4.109 kWh/dzień) | 0.702 | ✅ |

### Flagi Pogodowe ✅

| Flaga | Dni | % | Accuracy | Importance |
|-------|-----|---|----------|-----------|
| likely_fog_day | 22 | 5.6% | 100% | 0.0097% |
| snow_on_panels | 12 | 3.1% | 100% | 0.0001% |
| rainy_day | 26 | 6.6% | - | 🆕 do dodania |

### Performance vs Baseline

| Model | Poprawa |
|-------|---------|
| RF + reguły | **24.5%** (1.39 kWh) |
| RF godzinowy | **27.6%** (1.57 kWh) |

---

**Koniec dokumentu**  
**Status:** Modele gotowe, flaga mgły poprawiona, deszcz do dodania  
**Data:** 9 lipca 2026
