# Aktualizacja produkcyjna — 2026-07-26

**Zakres:** dual 16 + CS4 (16+3=19) · oneshot tydzień 19–25 · gate offline · UKMO park

**Powiązane:** [`CHANGELOG_ML.md`](CHANGELOG_ML.md) · [`UPDATE_2026-07-13_16-cech-hybryda.md`](UPDATE_2026-07-13_16-cech-hybryda.md) · [`UPDATE_2026-07-16_korekta-operacyjna.md`](UPDATE_2026-07-16_korekta-operacyjna.md) · notebook [`03_prezentacja_dyplomowa.ipynb`](../notebooks/03_prezentacja_dyplomowa.ipynb) · CSV [`oneshot_cs4_week_20260719_25.csv`](../data/processed/oneshot_cs4_week_20260719_25.csv)

---

## Jak czytać nazwy (żeby nie mieszać)

| Nazwa | Co to jest | Liczba cech |
|-------|------------|-------------|
| **Model wdrożeniowy / primary** | RF na produkcji → `pv_hourly_model.joblib` | **16** |
| **CS4** | **ten sam stack danych** + **3 dodatkowe cechy** (nie osobny świat) | **16 + 3 = 19** |
| Zapis **CS4 (19)** | tylko skrót: „model z 19 cechami = 16 bazowych + low + mid + clearness” | 19 |

**CS4 nie jest „liczone zamiast 16” ani „dla innych 19 cech z powietrza”.**  
To **rozszerzenie** modelu 16-cechowego:

```text
CS4 = HOURLY_FEATURE_COLUMNS_PRODUCTION (16)
    + cloud_cover_low_pct
    + cloud_cover_mid_pct
    + clearness
```

Ogólne `cloud_cover_pct` **już jest w 16** — CS4 dodaje warstwy low/mid + clearness, nie „trzeci ogólny obraz chmur”.

W tygodniu **19–25.07** na live produkcji działał **tylko 16**. Liczby CS4 w tabeli = **oneshot replay** (oba modele wytrenowane ≤18.07, ta sama pogoda/target).

---

## 1. Fundament wdrożeniowy (wspólny dla 16 i dla CS4)

Zanim porównujemy 16 vs 19, oba modele stoją na tym samym „podłodze” (lipiec 2026):

| # | Zmiana | Kiedy | Po co |
|---|--------|-------|--------|
| **1** | **GPS dach** (nie Observatorium ~10 km) | 17.07 | ta sama komórka siatki co instalacja |
| **2** | API pogody → Open-Meteo **ICON** (`icon_seamless`) | 17.07 | mniej wygładzania chmur niż `best_match` |
| **3** | Target → **ΔPVEnergyTotal** (jak w app FoxESS) | 18.07 | koniec rozjazdu ∫pvPower vs app |

To **nie jest CS4**. To korekty **źródeł / targetu**. Model primary nadal ma **16 cech**; CS4 tylko dorzuca 3 cechy **na tym samym** GPS+ICON+PVE.

Szczegóły gate’ów: [`CHANGELOG_ML.md`](CHANGELOG_ML.md) § GPS · ICON · PVE.  
Raporty wdrożeniowe: [`UPDATE_2026-07-17_gps-icon.md`](UPDATE_2026-07-17_gps-icon.md) · [`UPDATE_2026-07-18_target-pve.md`](UPDATE_2026-07-18_target-pve.md) · [`UPDATE_2026-07-18_skala-app.md`](UPDATE_2026-07-18_skala-app.md).

---

## 2. Gate offline — 16 vs CS4 (19) · 26.07

Ten sam split 80/20, expanding → 2026-07-25, target PVE, pogoda ICON @ GPS dach.

| Metryka | Model **16** (primary) | **CS4 = 16+3** | Δ |
|---------|------------------------|----------------|---|
| Test MAE [kWh/h] | 0.623 | **0.621** | **−0.002** |
| Gap | 0.081 | 0.082 | +0.002 |
| Daily MAE [kWh/d] | 4.03 | **3.94** | **−0.087** |

**Werdykt:** ACCEPT jako kandydat dual — **nie** podmieniamy primary.

| Artefakt | Rola |
|----------|------|
| `pv_hourly_model.joblib` | **Primary — 16** |
| `pv_hourly_model_cs4.joblib` | **Dual — CS4 (19)** |
| `pv_hourly_model_before_cs4.joblib` | Backup 16 |

---

## 3. Tydzień 19–25.07 — porównanie **16 vs CS4 (19)** vs app

**Cel tabeli:** czy dorzucenie low+mid+clearness pomaga względem modelu wdrożeniowego 16.  
**Metoda:** oneshot shadow, trening obu ≤ **2026-07-18**, raw, bez adjust.  
**Live 5:00:** faktyczna produkcja wtedy (tylko **16**).

| Dzień | App | Pred **16** | Pred **CS4 (19)** | \|err\| 16 | \|err\| CS4 | CS4 bliżej? | Live 5:00 (16) |
|-------|-----|-------------|-------------------|------------|-------------|-------------|----------------|
| 19.07 | 27,3 | 26,4 | 26,0 | 0,9 | 1,3 | nie | 26,9 |
| 20.07 | 37,4 | 31,2 | 31,5 | 6,2 | 5,9 | **tak** | 33,8 |
| 21.07 | 18,8 | 25,4 | 23,7 | 6,6 | 4,9 | **tak** | 27,6 |
| 22.07 | 33,5 | 28,4 | 27,8 | 5,1 | 5,7 | nie | 29,1 |
| 23.07 | 19,3 | 23,5 | 23,1 | 4,2 | 3,8 | **tak** | 21,0 |
| 24.07 | 7,7 | 18,6 | 16,4 | 11,0 | 8,7 | **tak** | 21,5 |
| 25.07 | 31,4 | 28,9 | 30,0 | 2,5 | 1,4 | **tak** | 31,1 |

### Agregat

| Model | cech | MAE vs app | bliżej app |
|-------|------|------------|------------|
| Wdrożeniowy **16** | 16 | 5,23 | — |
| **CS4** | 19 = 16+3 | **4,54** | **5/7** |
| Live daily 5:00 | 16 | 4,71 | — |

Geom / CS4+Geom → park (nie biją samego CS4).

---

## 4. Live dual od 26.07 (osobna warstwa od tabeli tygodnia)

Od 26.07 wieczór: te same joby launchd liczą **oba** modele; oficjalna liczba = **16**.  
Closeout porównuje 16 i CS4 vs app. Pełnego tygodnia **live** dual jeszcze nie ma.

Przykład smoke `manual_cs4` 26.07 17:15: 26.07 ≈33,2 · 27.07 ≈19,6 · 28.07 ≈28,3 (obok ostatnich daily 16).

---

## 5. Decyzja (jednym zdaniem)

**Fundament (GPS · ICON · PVE) + primary 16** = produkcja.  
**CS4 (19)** = ten sam fundament + 3 cechy, dual do porównania — nie mylić z „innym modelem 19 cech bez 16”.

UKMO / geometria / Ineichen = park lub obserwacja ręczna.

```bash
./mlops/forecast_cs4_shadow.sh daily
```

---

*Uzupełniono 2026-07-26 — rozdział fundament vs CS4, klarowne 16 vs 16+3.  
Konwencja nazw: `UPDATE_YYYY-MM-DD_temat.md`.*
