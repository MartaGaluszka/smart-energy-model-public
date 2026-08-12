# Analiza kalibracji zalegania śniegu na panelach

Data analizy: 2026-07-08

## 🎯 Pytanie: Czy kalibracja śniegu pomogła czy zaszkodziła?

**Krótka odpowiedź:** ✅ **NIE ZASZKODZIŁA** (różnica <0.05 kWh), ale też **nie pokazała pełnego potencjału** w testach, bo w okresie testowym (luty-czerwiec 2026) nie było dni ze śniegiem na panelach.

---

## 📊 Wyniki porównania modeli

### Model ML (Random Forest)

| Wersja modelu | Test MAE | Test R² | Różnica |
|---------------|----------|---------|---------|
| **Z modelem topnienia śniegu** | 4.239 kWh | 0.588 | baseline |
| **BEZ modelu (tylko IMGW)** | 4.241 kWh | 0.588 | -0.002 kWh |

**Wniosek:** Model z kalibracją śniegu jest **identyczny** lub **minimalnie lepszy** (o 0.002 kWh = 0.05%).

### Wagi cech śnieżnych w modelu

| Cecha | Waga | Interpretacja |
|-------|------|---------------|
| `om_snow_depth_cm` | 0.298% | Pokrywa śnieżna (obserwacje) |
| `imgw_snow_depth_cm` | 0.085% | Pokrywa śnieżna (IMGW) |
| `om_snowfall_cm` | 0.058% | Opady śniegu |
| `snow_on_panels_prev` | 0.026% | Śnieg dzień wcześniej |
| `snow_on_panels` | **0.014%** | **Flaga z modelu topnienia** |

**Wniosek:** Flagi z modelu topnienia mają **bardzo małą wagę** (0.014%), co oznacza, że model Random Forest uważa je za **mniej ważne** niż ogólną pokrywę śnieżną czy radiację.

---

## 🔍 Analiza szczegółowa: Gdzie są dni ze śniegiem?

### Podział na okresy

| Okres | Długość | Dni ze śniegiem NA PANELACH | % |
|-------|---------|------------------------------|---|
| **TRENING** (2025-06 → 2026-01) | 139 dni | **17 dni** | 12.2% |
| **TEST** (2026-02 → 2026-06) | 113 dni | **0 dni** | 0.0% |
| **CAŁOŚĆ** | 252 dni | **17 dni** | 6.7% |

**Kluczowy wniosek:** W okresie testowym **nie było ani jednego dnia** ze śniegiem na panelach według modelu topnienia! Dlatego nie można było sprawdzić, czy kalibracja faktycznie pomaga.

### Dlaczego w TEST nie ma śniegu na panelach?

W okresie testowym (luty-czerwiec 2026) były **15 dni ze śniegiem W OGRODZIE**, ale model topnienia poprawnie rozpoznał, że śnieg **zsunął się/stopniał z paneli**:

| Dzień | Pokrywa w ogrodzie | Produkcja PV | Interpretacja |
|-------|-------------------|--------------|---------------|
| 2026-02-20 | 9 cm | **17.0 kWh** | Panele czyste! |
| 2026-02-21 | 9 cm | **13.9 kWh** | Panele czyste! |
| 2026-02-22 | 7 cm | **8.1 kWh** | Panele czyste! |
| 2026-02-01 | 4 cm | 10.8 kWh | Panele czyste! |
| 2026-02-10 | 4 cm | 9.7 kWh | Panele czyste! |

**To jest dobra wiadomość!** Model topnienia **prawidłowo** rozpoznał, że w lutym-czerwcu śnieg szybko zsuwa się z paneli (wyższa temperatura, dłuższy dzień).

---

## ❄️ Produkcja PV w dniach ze śniegiem NA PANELACH (trening)

### Statystyki (17 dni w okresie treningowym)

- **Średnia PV:** 3.21 kWh/dzień
- **Mediana PV:** 0.57 kWh/dzień (połowa dni < 0.6 kWh!)
- **Max PV:** 11.73 kWh/dzień
- **Dni z PV < 1 kWh:** 10 z 17 (59%)

**Porównanie:** Zima **BEZ** śniegu na panelach = średnia **7.08 kWh/dzień** (2× więcej!)

### Przykłady dni ze śniegiem

| Data | Pokrywa | PV | Radiacja | Uwagi |
|------|---------|----|---------|-|
| 2025-11-22 | 6 cm | **0.2 kWh** | 1.0 kWh/m² | ✓ Prawidłowo blokuje |
| 2025-11-23 | 17 cm | **0.0 kWh** | 0.6 kWh/m² | ✓ Prawidłowo blokuje |
| 2025-11-27 | 13 cm | **0.9 kWh** | 0.7 kWh/m² | ✓ Prawidłowo blokuje |
| 2026-01-09 | 11 cm | **10.5 kWh** | 1.5 kWh/m² | ⚠️ Fałszywy alarm? |
| 2026-01-10 | 10 cm | **11.7 kWh** | 0.9 kWh/m² | ⚠️ Fałszywy alarm? |
| 2026-01-11 | 11 cm | **10.0 kWh** | 0.5 kWh/m² | ⚠️ Fałszywy alarm? |

### ⚠️ Problem: Fałszywe alarmy

W styczniu 2026 model oznaczył 3 dni jako "śnieg na panelach", mimo że produkcja PV była **wysoka** (10-12 kWh). To sugeruje, że:
1. Śnieg stopniał/zsunął się w ciągu dnia
2. Model jest zbyt konserwatywny (powolne zsuwanie/topnienie)
3. Potrzeba dokładniejszych danych (zdjęcia godzinowe?)

---

## 🎯 Interpretacja: Pomogło czy zaszkodziło?

### ✅ Kalibracja NIE ZASZKODZIŁA
- MAE praktycznie identyczne (4.239 vs. 4.241 kWh)
- Model Random Forest automatycznie ignoruje nieprzydatne cechy
- Brak przeuczenia

### ⚠️ Ale też nie pokazała pełnego potencjału
**Dlaczego?**
1. **W TEST nie było dni ze śniegiem** - nie można było sprawdzić efektu
2. **W TRENING było tylko 17 dni** (12%) - za mało do nauki silnego wzorca
3. **Z tych 17 dni, 3 były "fałszywymi alarmami"** - model uczył się na szumie

### 🔄 Model działa, ale ma ograniczenia

**Działa dobrze:**
- Rozpoznaje, że w lutym-czerwcu śnieg szybko zsuwa się z paneli
- W większości dni ze śniegiem (10/17) PV < 1 kWh - poprawna identyfikacja

**Wymaga poprawy:**
- Fałszywe alarmy w styczniu (3 dni z wysoką PV mimo flag śniegu)
- Za mała waga w modelu ML (0.014%) - model wolał polegać na radiacji

---

## 💡 Rekomendacje

### 1. **ZACHOWAJ kalibrację śniegu** ✅
**Dlaczego:**
- Nie szkodzi (różnica <0.05 kWh)
- Potencjał do pomocy w przyszłej zimie (gdy będą dni ze śniegiem w TEST)
- Fenomenologicznie uzasadniona (śnieg FAKTYCZNIE wpływa na PV)

### 2. **Zbieraj więcej danych o śniegu**
- Zdjęcia paneli z zimą 2026/2027
- Godzinowe dane produkcji (kiedy panele się odkrywają?)
- Temperatura paneli (czy są ciepłe = szybsze topnienie?)

### 3. **Popraw model topnienia**
**Problemy do rozwiązania:**
- Fałszywe alarmy w styczniu (dni z wysoką PV mimo flag śniegu)
- Model może być zbyt konserwatywny w późnej zimie (styczeń)

**Możliwe poprawki:**
```python
# W src/features/snow_melt_model.py
# Zwiększ prędkość topnienia w styczniu (wyższa temperatura, dłuższy dzień)
if month == 1:
    melt_rate_cm_per_h *= 1.5  # szybsze topnienie w styczniu
```

### 4. **Testuj w następnej zimie**
- Obecny test (luty-czerwiec) nie miał dni ze śniegiem
- Prawdziwy test będzie w zimie 2026/2027
- Wtedy sprawdź, czy kalibracja faktycznie pomaga

---

## 📈 Co dalej?

### Krótki termin (lato 2026)
- ✅ Zachowaj obecną kalibrację (nie szkodzi)
- ⏸️ Nie przejmuj się małą wagą (0.014%) - to normalne dla rzadkich zjawisk

### Średni termin (jesień 2026)
- 📸 Zbieraj zdjęcia paneli ze śniegiem
- 🔍 Analizuj godzinowe dane (kiedy panele się odkrywają?)
- 🧪 Testuj różne parametry modelu topnienia

### Długi termin (zima 2026/2027)
- 🎯 **Prawdziwy test:** okres testowy ze śniegiem
- 📊 Porównaj MAE w dniach ze śniegiem: z kalibracją vs. bez
- 🔧 Dostosuj parametry na podstawie wyników

---

## 🎓 Wnioski końcowe

1. **Kalibracja zalegania śniegu NIE ZASZKODZIŁA** - model jest identyczny (różnica 0.002 kWh)

2. **Nie pokazała pełnego potencjału** - w okresie testowym nie było dni ze śniegiem na panelach

3. **Model topnienia działa poprawnie** - rozpoznaje, że w lutym-czerwcu śnieg szybko zsuwa się z paneli

4. **Wymaga poprawy** - fałszywe alarmy w styczniu (3 dni z wysoką PV mimo flag śniegu)

5. **Zachowaj kalibrację** - będzie przydatna w przyszłej zimie, gdy będą dni ze śniegiem w TEST

6. **Zbieraj więcej danych** - zdjęcia paneli, godzinowe dane produkcji, temperatura paneli

---

**Podsumowanie jednym zdaniem:** Kalibracja śniegu nie zaszkodziła, ale też nie pomogła w testach, bo nie było dni ze śniegiem. Prawdziwy test będzie w zimie 2026/2027. Warto zachować i dalej rozwijać. ✅
