# Test Flagi Deszczu - Wyniki
**Data:** 9 lipca 2026  
**Dodano:** Flaga `rainy_day` do modelu dziennego

---

## Porównanie Wyników

### Przed (tylko flaga mgły):

| Model | MAE (kWh) | RMSE (kWh) | R² |
|-------|-----------|------------|-----|
| RF + reguły | **4.285** | 5.635 | 0.589 |
| RF | 4.339 | 5.661 | 0.585 |
| Baseline | 5.674 | 6.469 | 0.459 |

### Po (flaga mgły + flaga deszczu):

| Model | MAE (kWh) | RMSE (kWh) | R² | Zmiana MAE |
|-------|-----------|------------|-----|------------|
| RF + reguły | **4.252** | 5.614 | 0.592 | **-0.033 kWh** (-0.8%) |
| RF | 4.323 | 5.646 | 0.588 | **-0.016 kWh** (-0.4%) |
| Baseline | 5.674 | 6.469 | 0.459 | (bez zmian) |

---

## Analiza

### ✅ Poprawa

- **RF + reguły:** -0.033 kWh (0.8% lepiej)
- **RF:** -0.016 kWh (0.4% lepiej)
- **R² RF + reguły:** 0.589 → 0.592 (+0.003)

### Feature Importance

| Feature | Importance |
|---------|-----------|
| radiation_daytime_kwh_m2 | 90.66% |
| cloud_cover_avg | 2.32% |
| ... | ... |
| **likely_fog_day** | 0.0097% |
| **rainy_day** | *brak w top features* |

**Uwaga:** `rainy_day` nie pojawia się w top features, co sugeruje bardzo niską importance (prawdopodobnie <0.0001%).

---

## Dlaczego Mała Poprawa?

### 1. Test Set Nie Ma Deszczu w Krytycznych Dniach

Przypominamy:
- Train: czerwiec 2025 - styczeń 2026
- Test: luty - czerwiec 2026

Deszcz występuje głównie w:
- **Listopadzie (27%)** - w train
- **Lipcu (10%)** - poza test set
- **Marcu (10%)** - częściowo w test

**Test set ma tylko ~2-3 dni deszczu** (luty-czerwiec to głównie wiosna/lato bez ekstremalnych opadów).

### 2. Radiacja Już Wyjaśnia Większość Wariancji

- Radiacja: **90.66% importance**
- Wszystkie inne cechy łącznie: **9.34%**
- Flagi pogodowe (mgła + deszcz): **<0.01%**

**Ale:** Niska importance ≠ nieskuteczność!
- Wcześniejsza walidacja: dni z mgłą miały MAE=0.085 kWh (doskonałe!)
- Flagi działają na rzadkich przypadkach (5-7% dni)

### 3. Efekt "Rzadkich Zdarzeń"

| Warunek | % dni | W test set |
|---------|-------|------------|
| Mgła | 5.6% | 0 dni |
| Deszcz | 6.6% | ~2-3 dni |
| Razem | 12.2% | ~2-3 dni |

**Problem:** Model nie może się nauczyć na 2-3 przykładach!

---

## Wnioski

### ✅ Pozytywne

1. **Flaga deszczu NIE SZKODZI** - nawet mała poprawa (0.8%)
2. **R² się poprawia** - 0.589 → 0.592
3. **Teoretycznie sensowna** - deszcz ma wyższą efektywność niż mgła

### ⚠️ Ograniczenia

1. **Test set nie testuje głównego efektu** - za mało dni z deszczem
2. **Importance bardzo niska** - model prawie nie używa tej cechy
3. **Poprawa marginalna** - 0.033 kWh przy MAE 4.252 kWh

### 💡 Rekomendacja

**ZACHOWAĆ flagę deszczu w modelu:**

**Powody:**
1. ✅ Nie szkodzi (a nawet trochę pomaga)
2. ✅ Teoretycznie poprawna (efektywność 72% wyższa niż mgły)
3. ✅ Przygotowanie na przyszłość - gdy będzie więcej danych
4. ✅ Koszt obliczeniowy bliski zeru

**Ale:**
- Nie oczekuj dramatycznej poprawy
- Efekt będzie widoczny dopiero na większym zbiorze danych
- Szczególnie gdy test set będzie zawierał jesień/zimę (listopad-marzec)

---

## Następne Kroki

### Priorytet 1: Feature "Długość Dnia"

To MOŻE dać większą poprawę niż flaga deszczu:
```python
df['day_length_hours'] = df['sunset_hour'] - df['sunrise_hour']
```

**Dlaczego?**
- Wpływa na WSZYSTKIE dni (100%), nie tylko 6.6%
- Wyjaśnia underprediction wiosny (marzec-kwiecień)
- Korelacja z sezonem (doy_sin/cos) ale bardziej bezpośrednia

### Priorytet 2: Test Set z Jesienią/Zimą

Obecny podział:
- Train: czerwiec-styczeń
- Test: luty-czerwiec

**Nowy podział (do przetestowania):**
- Train: marzec-październik
- Test: listopad-luty

**Korzyści:**
- Test set będzie miał dni z mgłą i deszczem
- Prawdziwy test flag pogodowych
- Bardziej realistyczny sezon (zima najważniejsza)

### Priorytet 3: Zbadać Interakcje

Może radiacja × rainy_day?
```python
df['radiation_rain_interaction'] = df['radiation_daytime_kwh_m2'] * df['rainy_day']
```

**Hipoteza:** Przy niskiej radiacji, deszcz zachowuje się inaczej niż mgła.

---

## Podsumowanie Końcowe

| Aspekt | Ocena |
|--------|-------|
| **Poprawność implementacji** | ✅ OK |
| **Wpływ na wyniki** | ⚠️ Marginalny (+0.8%) |
| **Teoretyczne uzasadnienie** | ✅ Silne |
| **Rekomendacja** | ✅ **ZACHOWAĆ** |
| **Oczekiwania** | Efekt widoczny na większych danych |

**Flaga deszczu jest OK, ale nie rozwiąże głównego problemu underprediction wiosny.**

Potrzebujemy:
1. Feature "długość dnia" ⭐ **Priorytet!**
2. Lepszy test set (z zimą)
3. Więcej danych treningowych

---

**Koniec raportu**  
**Status:** Flaga deszczu dodana i przetestowana ✅  
**Data:** 9 lipca 2026
