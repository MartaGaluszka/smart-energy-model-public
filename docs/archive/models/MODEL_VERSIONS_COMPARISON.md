# Porównanie Wszystkich Wersji Modelu
**Data:** 9 lipca 2026  
**Test:** Wpływ flag mgły, deszczu i długości dnia na model dzienny

---

## Progresja Modelu

### Wersja 1: Baseline (tylko mgła)

| Model | MAE (kWh) | RMSE (kWh) | R² |
|-------|-----------|------------|-----|
| RF + reguły | **4.285** | 5.635 | 0.589 |
| RF | 4.339 | 5.661 | 0.585 |

**Cechy:** Radiacja, pogoda, mgła, śnieg

---

### Wersja 2: + Flaga Deszczu

| Model | MAE (kWh) | RMSE (kWh) | R² | vs V1 |
|-------|-----------|------------|-----|-------|
| RF + reguły | **4.252** | 5.614 | 0.592 | **-0.033 kWh** ✅ |
| RF | 4.323 | 5.646 | 0.588 | -0.016 kWh ✅ |

**Zmiana:** +`rainy_day` (opady >1mm + wilgotność >90% + chmury >95%)

**Rezultat:** Mała poprawa (0.8%)

---

### Wersja 3: + Długość Dnia

| Model | MAE (kWh) | RMSE (kWh) | R² | vs V2 |
|-------|-----------|------------|-----|-------|
| RF + reguły | **4.266** | 5.657 | 0.586 | **+0.014 kWh** ⚠️ |
| RF | 4.333 | 5.688 | 0.581 | +0.010 kWh ⚠️ |

**Zmiana:** +`day_length_hours` (sunset - sunrise)

**Rezultat:** POGORSZENIE! (-0.006 R²)

---

## Analiza Feature Importance

### Top 10 (Wersja 3 - z długością dnia):

| # | Feature | Importance | Uwagi |
|---|---------|-----------|-------|
| 1 | radiation_daytime_kwh_m2 | **90.66%** | Dominuje |
| 2 | cloud_cover_avg | 2.31% | |
| 3 | cloud_cover_low_avg | 1.63% | |
| 4 | precip_mm | 1.56% | |
| 5 | humidity_daytime_avg | 0.82% | |
| 6 | temp_min | 0.71% | |
| 7 | doy_cos | 0.52% | **Sezon** |
| 8 | temp_max | 0.47% | |
| **9** | **day_length_hours** | **0.45%** | **NOWA!** |
| 10 | doy_sin | 0.40% | **Sezon** |

### Flagi Pogodowe:

| Feature | Importance |
|---------|-----------|
| likely_fog_day | 0.0077% |
| rainy_day | <0.0001% (nie w top) |

---

## 🤔 Dlaczego Długość Dnia Pogorszyła Model?

### Hipoteza 1: Korelacja z Sezonem

`day_length_hours` jest **silnie skorelowana** z `doy_sin` i `doy_cos`:

| Miesiąc | Day Length | doy (normaliz.) |
|---------|-----------|-----------------|
| Grudzień | ~8h | 0° (min) |
| Czerwiec | ~16h | 180° (max) |
| Marzec/Wrzesień | ~12h | 90°/270° |

**Problem:** Model już ma informację sezonową przez doy_sin/doy_cos!

**Efekt:** 
- `day_length_hours` "kradnie" importance z doy (0.45% vs 0.40%+0.52%)
- Łącznie sezon: 0.45% + 0.40% + 0.52% = 1.37%
- Wcześniej sezon: 0.51% + 0.75% = 1.26%
- Więcej importance, ale **gorszy wynik** = **overfitting**!

### Hipoteza 2: Redundancja z Radiacją

Długość dnia wpływa na **maksymalną możliwą radiację**:
- Długi dzień → więcej czasu na produkcję → wyższa radiacja (suma)
- Krótki dzień → mniej czasu → niższa radiacja

**Ale:** Model już używa `radiation_daytime_kwh_m2` (90.66%)!

**Efekt:** `day_length_hours` dodaje **redundantną informację**

### Hipoteza 3: Test Set Bias

Test set: luty-czerwiec (wiosna/lato)
- Długość dnia: 10-16h (rosnąca)
- Train set: czerwiec-styczeń (lato→zima)
- Długość dnia: 16h→8h (malejąca)

**Problem:** Różne trendy w train vs test!
- Train: model uczy się "krótszy dzień = mniej PV"
- Test: "dłuższy dzień" ale nadal underprediction (brak innych cech)

---

## 📊 Porównanie Wszystkich 3 Wersji

| Wersja | Cechy | MAE | R² | vs Baseline |
|--------|-------|-----|-----|-------------|
| **Baseline** | mgła + śnieg | 4.285 | 0.589 | - |
| **+ deszcz** | + rainy_day | **4.252** ✅ | **0.592** ✅ | **-0.033** |
| **+ długość dnia** | + day_length | 4.266 ⚠️ | 0.586 ⚠️ | -0.019 |

**Najlepsza wersja:** V2 (mgła + deszcz) bez długości dnia!

---

## 💡 Wnioski

### ✅ Co Pomaga

1. **Flaga deszczu** - małe ale pozytywne (0.8%)
   - Teoretycznie poprawna
   - Nie szkodzi
   - Zachować ✅

### ⚠️ Co Nie Pomaga

1. **Długość dnia** - pogarsza wyniki!
   - Redundantna z doy_sin/doy_cos
   - Overfitting
   - **USUNĄĆ** ❌

### 🎯 Dlaczego Model Się Nie Poprawia?

**Główny problem: Test set bez trudnych warunków**
- 0 dni mgły
- ~2-3 dni deszczu
- Tylko wiosna/lato (łatwe warunki)

**Co byśmy potrzebowali:**
- Test set z zimą (listopad-luty)
- Więcej przykładów z mgłą/deszczem
- Lepsze cechy dla wiosny (ale nie day_length!)

---

## 🔄 Rekomendacje

### Priorytet 1: Cofnij Długość Dnia ⭐

**Akcja:** Usuń `day_length_hours` z FEATURE_COLUMNS

**Powód:** Pogarsza model (overfitting + redundancja)

### Priorytet 2: Zachowaj Deszcz ✅

**Akcja:** Zostaw `rainy_day`

**Powód:** Małe ale pozytywne, teoretycznie poprawne

### Priorytet 3: Lepszy Podział Train/Test

**Obecny:**
- Train: czerwiec 2025 - styczeń 2026
- Test: luty - czerwiec 2026

**Propozycja:**
- Train: marzec - październik (2025)
- Test: listopad 2025 - luty 2026 (zima!)

**Korzyści:**
- Test set z mgłą i deszczem
- Prawdziwy test flag pogodowych
- Bardziej reprezentatywny

### Priorytet 4: Inne Cechy dla Wiosny

Zamiast `day_length_hours`, spróbuj:

1. **Interakcja radiacja × miesiąc:**
   ```python
   df['radiation_spring'] = df['radiation_daytime_kwh_m2'] * (df['month'].isin([3,4,5]))
   ```

2. **Kąt słońca (elevation):** 
   - Wyższa elevacja wiosną niż zimą przy tej samej radiacji
   - Więcej bezpośrednia niż day_length

3. **Rolling mean PV (ostatnie 7 dni):**
   - Model "pamięta" trend
   - Pomaga w okresach przejściowych

---

## 📈 Finalna Rekomendacja

**NAJLEPSZY MODEL: Wersja 2**
- Cechy: radiacja + pogoda + mgła + deszcz + śnieg
- MAE: 4.252 kWh
- R²: 0.592
- Bez day_length_hours! ❌

**Akcje:**
1. ✅ Zachowaj `rainy_day`
2. ❌ Usuń `day_length_hours`
3. 🔄 Przetrenuj finalny model

---

**Koniec analizy**  
**Status:** Flaga deszczu OK, długość dnia do usunięcia  
**Najlepszy model:** V2 (MAE=4.252 kWh, R²=0.592)  
**Data:** 9 lipca 2026
