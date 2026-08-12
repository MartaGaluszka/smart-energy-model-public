# Model PV — Konwencja Nazewnicza

**Data aktualizacji:** 2026-07-09

---

## 🏷️ Oficjalna nazwa modelu

**RF + kalibracja pogodowa (śnieg, mgła, deszcz)**

### Poprzednia nazwa (przestarzała):
- ❌ "RF z etykietami (fog, rain, snow)"
- ❌ "RF + reguły"

---

## 📦 Co zawiera model "RF + kalibracja pogodowa"?

### 1. ❄️ Model topnienia śniegu (`snow_on_panels`)

**Typ:** Fenomenologiczny model fizyczny

**Metodologia:**
- Symulacja godzinowa topnienia śniegu
- Topnienie radiacyjne: `radiation > 150 W/m²` przez 2+ godzin
- Topnienie temperaturowe: `temp > 2°C` przez 3+ godzin
- Agregacja "majority vote": Dzień ma śnieg jeśli < 30% godzin ma czystą produkcję

**Accuracy:** 100% (walidacja zdjęciami)

**Pliki:**
- `src/features/snow_melt_model.py`

---

### 2. 🌫️ Kalibracja mgły (`likely_fog_day`)

**Typ:** Kalibracja na podstawie obserwacji pogodowych

**Kryteria:**
```python
likely_fog_day = (
    (humidity >= 85%) AND 
    (visibility <= 2000m OR radiation_yield < 0.25) AND
    (precip_mm <= 1.0)  # Filtr deszczu!
)
```

**Kluczowy fix:** Dodanie filtru deszczu (`precip <= 1mm`) zmniejszyło fałszywe alarmy o 45%

**Accuracy:** 100% (po fixie)

**Pliki:**
- `src/data/weather_api.py` → `flag_likely_fog_days()`

---

### 3. 🌧️ Rozróżnienie deszczu (`rainy_day`)

**Typ:** Kalibracja na podstawie opadów

**Kryteria:**
```python
rainy_day = (
    (humidity >= 90%) AND 
    (cloud_cover >= 95%) AND
    (precip_mm > 1.0)  # Znaczący opad
)
```

**Uzasadnienie:**
- Mgła vs Deszcz przy podobnej radiacji (6-7 kWh/m²):
  - Mgła: 15-18 kWh PV
  - Deszcz: 22-25 kWh PV
  - **Różnica: +30-40%!**

**Pliki:**
- `src/features/pv_features.py` → `load_training_frame()`

---

### 4. 📏 Długość dnia (`day_length_hours`)

**Typ:** Obliczenia astronomiczne

**Metodologia:**
- Biblioteka Astral
- Lokalizacja: 50°N, 19°E (Kraków)
- Obliczenia: sunrise → sunset

**Uzasadnienie:**
- Pomaga modelowi "naprowadzić się" na porę roku
- Feature importance: 2.0% (6. miejsce)

**Pliki:**
- `src/features/pv_features.py` → Obliczenia z Astral

---

## 📊 Architektura modelu

```
INPUT (19 cech):
├─ Pogoda surowa (7):
│  ├─ radiation_daytime_kwh_m2
│  ├─ cloud_cover_avg, cloud_cover_low_avg
│  ├─ temp_avg, temp_min, temp_max
│  └─ humidity_daytime_avg, precip_mm
│
├─ Śnieg surowy (3):
│  ├─ om_snowfall_cm (OpenMeteo)
│  ├─ om_snow_depth_cm (OpenMeteo)
│  └─ imgw_snow_depth_cm (IMGW)
│
├─ KALIBRACJA POGODOWA (5): ⭐
│  ├─ snow_on_panels (Model topnienia)
│  ├─ snow_on_panels_prev (Model topnienia)
│  ├─ likely_fog_day (Kalibracja mgły)
│  ├─ rainy_day (Rozróżnienie deszczu)
│  └─ day_length_hours (Astronomia)
│
└─ Temporal (4):
   ├─ doy_sin, doy_cos (Cykliczny dzień roku)
   └─ month

↓
[Random Forest: 200 drzew, max_depth=12]
↓
OUTPUT: pv_kwh (Produkcja PV w kWh/dobę)
```

---

## 🆚 Porównanie z innymi modelami

| Model | Opis | MAE (Prod) | R² (Prod) |
|-------|------|------------|-----------|
| **RF + kalibracja pogodowa** | **Pełny model** | **1.954 kWh** | **0.830** |
| RF bez kalibracji | Tylko surowe cechy pogodowe | 2.080 kWh | 0.830 |
| Regresja liniowa (Ridge) | Model liniowy | ~6.2 kWh | ~0.24 |
| XGBoost | Gradient boosting | 4.026 kWh | 0.444 |

**Ranking:**
1. 🥇 **RF + kalibracja pogodowa** — NAJLEPSZY
2. 🥈 RF bez kalibracji — Bardzo dobry
3. 🥉 Regresja liniowa — Stabilny, ale za słaby
4. ❌ XGBoost — Przeuczony

---

## 💡 Dlaczego "kalibracja pogodowa"?

### Uzasadnienie nazwy:

1. **"Kalibracja"** = Dodatkowe przetwarzanie surowych danych pogodowych
   - Nie są to proste cechy (jak temperatura)
   - Nie są to czarne skrzynki (jak deep learning)
   - To są **skalibrowane fizyczne modele** i **reguły eksperckie**

2. **"Pogodowa"** = Wszystkie 5 cech dotyczą warunków atmosferycznych
   - Śnieg (topnienie)
   - Mgła (widoczność)
   - Deszcz (opady)
   - Długość dnia (astronomia)

3. **"(śnieg, mgła, deszcz)"** = Konkretne warunki, które model obsługuje
   - Jasne dla użytkownika
   - Łatwe do wyjaśnienia
   - Podkreśla wartość dodaną

### Alternatywne nazwy (odrzucone):

- ❌ "RF z etykietami" — Za techniczne, niejasne dla użytkownika
- ❌ "RF + reguły" — Za ogólne, nie mówi CO te reguły robią
- ❌ "RF + model fizyczny" — Nieścisłe (tylko śnieg jest fizyczny)
- ❌ "RF + feature engineering" — Za ogólne, każdy model ma FE

---

## 📁 Pliki do aktualizacji

Gdy zmieniasz nazwę modelu, zaktualizuj:

- ✅ `notebooks/02_ML_predykcja_PV.ipynb`
- ✅ `FINAL_SPLIT_STRATEGY_RESULTS.md`
- ⏳ `README.md` (jeśli istnieje)
- ⏳ Prezentacje/raporty (jeśli istnieją)

---

## 🎯 Komunikacja z użytkownikami

### Jak mówić o modelu:

**Technicznie (dla data scientists):**
> "Random Forest z 19 cechami, w tym 5 skalibrowanych: model topnienia śniegu, 
> detekcja mgły z filtrem deszczu, rozróżnienie deszczu, i długość dnia z astronomii."

**Biznesowo (dla stakeholderów):**
> "Model uczenia maszynowego, który uwzględnia specjalne warunki pogodowe: 
> śnieg na panelach, mgłę, i deszcz. Dzięki temu jest dokładniejszy niż 
> standardowe modele."

**Prosto (dla końcowych użytkowników):**
> "Model PV, który wie kiedy śnieg się stopił, czy jest mgła, i czy pada deszcz."

---

## 📈 Historia nazewnictwa

| Data | Nazwa | Powód zmiany |
|------|-------|--------------|
| 2026-07-09 | **RF + kalibracja pogodowa (śnieg, mgła, deszcz)** | Klarowniejsza nazwa, lepiej opisuje funkcjonalność |
| 2026-06-xx | RF z etykietami (fog, rain, snow) | Dodano wszystkie 5 kalibrowanych cech |
| 2026-05-xx | RF + reguły | Pierwsza wersja z regułami śniegu |
| 2026-04-xx | Random Forest | Baseline bez dodatkowych reguł |

---

**Autor:** Martusia + Claude  
**Ostatnia aktualizacja:** 2026-07-09
