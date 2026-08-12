# FoxEss - Które dane eksportować?

## 🎯 Parametry NIEZBĘDNE do projektu (minimalne)

To są parametry, bez których projekt nie zadziała. Musisz je mieć w CSV:

### 1. **Timestamp** (wymagane)
- `Date` + `Time` lub `timestamp`
- Znacznik czasu dla każdego pomiaru

### 2. **Produkcja PV** (wymagane)
✅ **`GenerationPower (kW)`** lub **`Moc PV (kW)`**
- Całkowita moc wyprodukowana przez fotowoltaikę

### 3. **Bateria** (wymagane)
✅ **`SoC (%)`** - Stan naładowania baterii
✅ **`BatChargePower (kW)`** - Moc ładowania baterii
✅ **`BatDischargePower (kW)`** - Moc rozładowania baterii

Lub alternatywnie:
✅ **`invBatPower (kW)`** - Moc baterii (jeśli jest jako jedna kolumna)

### 4. **Zużycie energii** (wymagane)
✅ **`LoadsPower (kW)`** - Całkowite zużycie energii w domu

### 5. **Wymiana z siecią** (wymagane)
✅ **`GridConsumptionPower (kW)`** - Pobór z sieci
✅ **`FeedinPower (kW)`** - Oddawanie do sieci

---

## ⭐ Parametry PRZYDATNE (opcjonalne, ale warte dodania)

### Temperatury (dla analizy wydajności)
- `batTemperature (℃)` - Temperatura baterii
- `AmbientTemperature (℃)` - Temperatura otoczenia
- `InvTemperation (℃)` - Temperatura falownika

### Napięcia (dla diagnostyki)
- `BatVolt (V)` - Napięcie baterii
- `Napięcie PV1 (V)` - Napięcie stringów PV

### Szczegóły PV (jeśli masz więcej stringów)
- `Moc PV1 (kW)`, `Moc PV2 (kW)`, etc. - Osobne moce dla każdego stringa

---

## 📊 Jak wyeksportować dane z FoxEss?

### Wariant 1: Portal Web - wybierz wszystkie kluczowe parametry

1. Zaloguj się na https://www.foxesscloud.com/
2. Przejdź do **"Raporty"** (Reports)
3. Wybierz **"Raport dzienny"** lub **"Raport godzinowy"**
4. **Ustaw zakres dat:** minimum 2-3 miesiące historii
5. **Zaznacz parametry:**
   - ✅ `GenerationPower (kW)` lub `Moc PV (kW)`
   - ✅ `SoC (%)`
   - ✅ `BatChargePower (kW)`
   - ✅ `BatDischargePower (kW)`
   - ✅ `LoadsPower (kW)`
   - ✅ `GridConsumptionPower (kW)`
   - ✅ `FeedinPower (kW)`
   - ⭐ `batTemperature (℃)` (opcjonalnie)
   - ⭐ `AmbientTemperature (℃)` (opcjonalnie)

6. Kliknij **"Eksport CSV"**
7. Zapisz jako `data/raw/foxess_2026.csv`

### Wariant 2: Eksportuj wszystko (bezpieczniejsze)

Jeśli nie jesteś pewien które parametry wybrać - **zaznacz wszystko** i wyeksportuj!

Nasz skrypt importu automatycznie:
- Znajdzie i użyje potrzebne kolumny
- Zignoruje resztę
- Nie będzie problemów z brakiem danych

---

## 🔍 Jak wygląda struktura CSV?

Przykładowa struktura pliku po eksporcie:

```csv
Date,Time,GenerationPower (kW),SoC (%),LoadsPower (kW),GridConsumptionPower (kW),FeedinPower (kW),BatChargePower (kW),BatDischargePower (kW)
2026-01-01,00:00,0.0,65.0,2.5,1.2,0.0,0.0,1.3
2026-01-01,00:05,0.0,64.8,2.3,1.0,0.0,0.0,1.3
2026-01-01,00:10,0.0,64.6,2.8,1.5,0.0,0.0,1.3
...
2026-01-01,12:00,4.5,75.0,3.2,0.0,0.0,1.3,0.0
2026-01-01,12:05,5.2,76.5,3.0,0.0,1.5,0.7,0.0
```

**Ważne:**
- Jedna linia = jeden pomiar (zwykle co 5 minut)
- Data + czas w osobnych kolumnach lub razem
- Kolumny mogą być po polsku lub angielsku - skrypt obsługuje oba

---

## 🚀 Co zrobić po pobraniu CSV?

1. **Zapisz plik** w folderze `data/raw/`
   ```
   data/raw/foxess_2026_q1.csv
   ```

2. **Edytuj skrypt** `src/data/import_csv.py`:
   ```python
   # W funkcji main() dodaj:
   importer.import_foxess_csv(
       'data/raw/foxess_2026_q1.csv',
       device_sn='ABC123'  # Twój numer seryjny falownika
   )
   ```

3. **Uruchom import:**
   ```bash
   source venv/bin/activate
   python src/data/import_csv.py
   ```

4. **Sprawdź import:**
   ```bash
   python src/data/import_csv.py
   # Zobaczysz: "✅ Zaimportowano X rekordów do foxess_data"
   ```

---

## 💡 Wskazówki

### Jeśli masz problemy z eksportem:

1. **Spróbuj różnych raportów:**
   - Raport dzienny (szczegółowe dane co 5 min)
   - Raport miesięczny (dane zagregowane dziennie)
   - Raport godzinowy

2. **Exportuj w mniejszych częściach:**
   - Zamiast 6 miesięcy naraz, zrób 2x po 3 miesiące
   - Każdy plik zapisz osobno, zaimportujemy wszystkie

3. **Sprawdź format daty:**
   - FoxEss może używać różnych formatów (YYYY-MM-DD lub DD/MM/YYYY)
   - Skrypt próbuje automatycznie rozpoznać format

### Ile danych potrzebujesz?

- **Minimum:** 1 miesiąc (wystarczy do prototypu)
- **Dobrze:** 3 miesiące (widać trendy)
- **Idealnie:** 6-12 miesięcy (pokrywa wszystkie pory roku)

### Co jeśli brakuje jakiegoś parametru?

**Nie ma problemu!** Skrypt importu:
- ✅ Obsługuje brakujące kolumny
- ✅ Wypełnia wartościami NULL gdzie potrzeba
- ✅ Kontynuuje import mimo braków

Najważniejsze żeby miały:
- Timestamp (data + czas)
- Przynajmniej produkcja PV
- Przynajmniej zużycie (Loads)

Resztę możesz uzupełnić później.

---

## 📋 Checklist przed eksportem

- [ ] Zalogowany na https://www.foxesscloud.com/
- [ ] Zakładka "Raporty"
- [ ] Wybrany zakres dat (min. 2-3 miesiące)
- [ ] Zaznaczone kluczowe parametry:
  - [ ] GenerationPower / Moc PV
  - [ ] SoC
  - [ ] BatChargePower / BatDischargePower
  - [ ] LoadsPower
  - [ ] GridConsumptionPower
  - [ ] FeedinPower
- [ ] Format: CSV
- [ ] Plik zapisany w `data/raw/`

**Gotowe do importu!** 🎉
