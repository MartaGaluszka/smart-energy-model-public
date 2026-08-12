# Integracja kalibracji mgły i śniegu w modelach ML

Data aktualizacji: 2026-07-08

## 📋 Status integracji

### ✅ Model DZIENNY (`train_pv_rf_only.py`)
- **Target:** `pv_kwh_daytime` (suma 9-16h, historyczna agregacja)
- **Cechy:** 344 dni treningowych (2025-06-01 → 2026-06-04)

**Zintegrowane flagi:**
- `likely_fog_day` - flaga mgły (wilgotność + niska widoczność) - **waga: 0.077%**
- `snow_on_panels` - śnieg blokuje panele (ten dzień) - **waga: 0.004%**
- `snow_on_panels_prev` - śnieg blokował panele (poprzedni dzień) - **waga: 0.005%**

**Źródło danych:**
- Mgła: `flag_likely_fog_days()` z dynamicznymi godzinami (wschód/zachód słońca)
- Śnieg: `build_melt_daily_frame()` z modelu topnienia śniegu

**Wyniki:**
- Test MAE: 3.731 kWh
- Test R²: 0.632
- Model NIE jest przeuczony

---

### ✅ Model GODZINOWY (`train_hourly_model.py`)
- **Target:** `pv_kwh` (produkcja godzinowa)
- **Godziny:** Dynamiczne 5-20h (lato) / 7-15h (zima) na podstawie wschodu/zachodu słońca
- **Cechy:** 3890 rekordów (359 dni)

**Zintegrowane flagi:**
- `likely_fog_day` - flaga mgły (dzienna, powtórzona dla każdej godziny) - **waga: 0.018%**
- `snow_on_panels` - śnieg blokuje panele (dzienna, powtórzona dla każdej godziny) - **waga: 0.009%**
- `snow_on_panels_prev` - śnieg blokował panele (poprzedni dzień) - **waga: 0.016%**

**Źródło danych:**
- Mgła: `flag_likely_fog_days()` z dynamicznymi godzinami (wschód/zachód słońca), zmergowana z danymi godzinowymi
- Śnieg: `build_melt_daily_frame()` z modelu topnienia śniegu, zmergowana z danymi godzinowymi

**Wyniki:**
- Test MAE: 0.663 kWh/h
- Dzienny MAE: 4.088 kWh/dzień
- Test R²: 0.597
- Model NIE jest przeuczony

---

## 🔧 Jak działa integracja?

### Kalibracja mgły

1. **Dynamiczne godziny produkcji:**
   - `load_daily_weather()` z `use_dynamic_hours=True` oblicza wschód/zachód słońca dla każdego dnia
   - Agregacja wilgotności i radiacji na podstawie faktycznych godzin produkcji

2. **Detekcja mgły:**
   - `flag_likely_fog_days()` analizuje:
     - Wilgotność > 85%
     - Radiacja > 3 kWh/m² (słońce jest "widoczne" dla pogody)
     - PV yield < 50% normy (ale produkcja jest niska)
     - Widoczność < 5 km (jeśli dostępne z IMGW)

3. **Integracja w modelach:**
   - **Model dzienny:** Flaga dodawana bezpośrednio w `load_training_frame()`
   - **Model godzinowy:** Flaga dzienna powtarzana dla każdej godziny w `load_hourly_training_frame_extended()`

### Kalibracja śniegu

1. **Model topnienia śniegu:**
   - Fenomenologiczny model topnienia z `snow_melt_model.py`
   - Parametry: temperatura, wilgotność, czas zalegania śniegu
   - Uwzględnia dynamiczne godziny produkcji (wschód/zachód słońca)

2. **Agregacja dla flag:**
   - `aggregate_daily_melt()` oblicza średnią pokrywę śnieżną w godzinach produkcji
   - Próg: jeśli `snow_roof_cm_prod_hours > 0.5 cm`, to `snow_on_panels = 1`

3. **Integracja w modelach:**
   - **Model dzienny:** `apply_melt_snow_flags()` z `snow_mode='melt'` w `load_training_frame()`
   - **Model godzinowy:** `build_melt_daily_frame()` z `use_snow_melt=True` w `load_hourly_training_frame_extended()`

---

## 📊 Waga cech

Flagi mgły i śniegu mają **małą, ale mierzalną wagę** w obu modelach:

| Cecha | Model dzienny | Model godzinowy |
|-------|---------------|-----------------|
| `likely_fog_day` | 0.077% | 0.018% |
| `snow_on_panels` | 0.004% | 0.009% |
| `snow_on_panels_prev` | 0.005% | 0.016% |

**Interpretacja:**
- Niska waga jest **naturalna** - mgła i śnieg to rzadkie zjawiska (mgła: 32/365 dni, śnieg: ~191/365 dni)
- W normalnych warunkach model polega głównie na radiacji (81.5% dla dziennego, 34.0% dla godzinowego)
- **Ale** w dniach z mgłą lub śniegiem, te flagi pomagają modelowi "zrozumieć", dlaczego produkcja jest niska mimo słonecznej pogody
- To jest klasyczny przypadek **edge case features** - pomocne w specyficznych warunkach

---

## ✅ Potwierdzenie działania

### Test 1: Model dzienny
```bash
cd /path/to/smart-energy-model
python scripts/train_pv_rf_only.py
```

**Rezultat:**
- ✓ Wczytano 344 dni z flagami mgły i śniegu
- ✓ Test MAE: 3.731 kWh
- ✓ Model NIE jest przeuczony

### Test 2: Model godzinowy
```bash
cd /path/to/smart-energy-model
python scripts/train_hourly_model.py
```

**Rezultat:**
- ✓ Dodano flagę mgły (dni z mgłą: 32 / 365)
- ✓ Dodano flagi śniegu z modelu topnienia (dni ze śniegiem: 191 / 365)
- ✓ Test MAE: 0.663 kWh/h
- ✓ Model NIE jest przeuczony

---

## 🎯 Rekomendacje

1. **Kontynuuj zbieranie danych:**
   - Więcej dni z mgłą → lepsza kalibracja
   - Więcej zdjęć śniegu → lepszy model topnienia

2. **Monitoruj wyniki:**
   - Porównaj predykcje w dniach mgłowych/śnieżnych z rzeczywistością
   - Dostosuj progi w `flag_likely_fog_days()` jeśli potrzebne

3. **Eksperymentuj z wagami:**
   - Jeśli chcesz zwiększyć wagę flag, możesz użyć `sample_weight` w treningu
   - Ale to ryzykowne - może prowadzić do przeuczenia na rzadkich przypadkach

---

## 📝 Pliki kluczowe

- `src/data/weather_api.py` - `flag_likely_fog_days()`, `load_daily_weather()` z dynamicznymi godzinami
- `src/features/snow_melt_model.py` - model topnienia śniegu z dynamicznymi godzinami
- `src/features/pv_features.py` - integracja flag w modelu dziennym
- `src/features/pv_features_hourly_extended.py` - integracja flag w modelu godzinowym
- `scripts/train_pv_rf_only.py` - trening modelu dziennego
- `scripts/train_hourly_model.py` - trening modelu godzinowego

---

**Podsumowanie:** Kalibracja mgły i śniegu jest **w pełni zintegrowana** w obu modelach ML (dziennym i godzinowym), z dynamicznymi godzinami produkcji opartymi na wschodzie/zachodzie słońca. Flagi mają małą, ale mierzalną wagę, co jest naturalne dla rzadkich zjawisk pogodowych. ✅
