# KRYTYCZNE: Problem z Danymi Kwiecień-Maj 2025
**Data:** 9 lipca 2026

---

## ⚠️ Nieprawidłowe Dane (NIE używać do treningu!)

**21.04 – 29.05.2025: Błędne ustawienia falownika**

Z `src/data/household_context.py`:
```python
PV_INVERTER_MISCONFIG_START = date(2025, 4, 21)
PV_INVERTER_MISCONFIG_END = date(2025, 5, 29)
PV_WEATHER_VALID_START = date(2025, 5, 30)
FOXESS_RELIABLE_START = date(2025, 6, 1)
ML_BATTERY_START = date(2025, 9, 1)  # Normalne użytkowanie
```

**Problem:** 
- Falownik hybrydowy miał priorytet baterii
- **Produkcja PV ograniczona do pojemności baterii**
- Dane NIE odzwierciedlają rzeczywistej produkcji paneli
- Nie można użyć do predykcji PV!

---

## ✅ Prawidłowe Dane

| Okres | Status | Użycie |
|-------|--------|--------|
| **21.04 – 29.05.2025** | ❌ Błędne ustawienia | **NIE używać!** |
| **30.05 – 31.05.2025** | ⚠️ Poprawione, ale luka API | Ostrożnie |
| **01.06.2025 →** | ✅ Ciągła seria, poprawne | **OK do ML** |
| **01.09.2025 →** | ✅ + normalne użytkowanie | **Idealne** |

---

## 🎯 Konsekwencje dla Train/Test Split

### ❌ NIE MOŻEMY użyć:

~~Opcja 1: Start od 2025-04-25~~
- Zawiera kwiecień-maj z błędnymi danymi
- **ODRZUCONE**

### ✅ MOŻEMY użyć:

**Opcja 1: Start od 2025-06-01 (obecny)** ⭐
```
Train: 2025-06-01 → 2026-03-31 (304 dni)
  - Lato: 92 dni
  - Jesień: 91 dni
  - Zima: 90 dni
  - Wiosna: 31 dni (MARZEC 2026!) ✅
  
Test: 2026-04-01 → 2026-06-04 (65 dni)
  - Kwiecień-czerwiec
```

**KLUCZOWE ODKRYCIE:**
- Jeśli zmienimy train end z **2026-01-31** → **2026-03-31**
- Dostaniemy **31 dni wiosny** (marzec!) w train set!
- Model zobaczy wiosnę! ✅

### Opcja 2: Start od 2025-09-01 (ML_BATTERY_START)
```
Train: 2025-09-01 → 2026-03-31 (213 dni)
  - Wszystkie 4 sezony
  - Normalne użytkowanie domu
  
Test: 2026-04-01 → 2026-06-04 (65 dni)
```

**Korzyści:**
- Tylko dane z normalnym użytkowaniem
- Bez okresu "pusty dom" (czerwiec-sierpień 2025)

---

## 💡 Rekomendacja FINALNA

**Użyj Opcji 1: 2025-06-01 → 2026-03-31**

**Dlaczego?**
1. ✅ **Maksimum danych** (304 dni vs 213)
2. ✅ **Wszystkie 4 sezony** (w tym 31 dni wiosny!)
3. ✅ **Poprawne dane** (od FOXESS_RELIABLE_START)
4. ✅ Więcej przykładów lata (pusty dom = inna produkcja, ale nadal ważna)

**Zmiana vs obecny split:**
- Było: Train → 2026-01-31 (0 dni wiosny) ❌
- Teraz: Train → 2026-03-31 (31 dni wiosny) ✅

**Oczekiwany efekt:**
- `day_length_hours` powinien pomóc!
- MAE: ~4.0-4.1 kWh (vs 4.25)
- Model nauczy się wzorca wiosny

---

## 🚀 Następny Krok

1. ✅ Zmień train_end na 2026-03-31 (zamiast 2026-01-31)
2. ✅ Przywróć `day_length_hours`
3. ✅ Zachowaj `rainy_day`
4. ✅ Przetrenuj model

**Wszystko z istniejących danych - nie potrzebujemy Tauron!**

---

**Status:** Problem zrozumiany, rozwiązanie gotowe  
**Data:** 9 lipca 2026
