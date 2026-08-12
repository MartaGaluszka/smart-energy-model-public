# Raport: Smart Energy Model — prognoza PV
**Data:** 2026-08-11 11:34

## Konfiguracja
- Random state: 42
- Split: 80/20 po dniach
- Okno treningowe: 2025-06-01 → 2026-08-08
- Cechy: 16 · target: delta PVEnergyTotal (kWh/h)
- Model weekly: 2026-08-09

## Wyniki modeli (holdout godzinowy)

| Model | Test MAE [kWh/h] | Test R² | Gap [kWh/h] | Werdykt |
|-------|----------------:|--------:|------------:|---------|
| Ridge | 0.831 | 0.526 | -0.003 | ✅ Nie przeuczony |
| RF (prod.) | 0.602 | 0.675 | 0.096 | ✅ Nie przeuczony |
| XGBoost | 0.614 | 0.654 | 0.470 | ❌ Przeuczony |

## Model produkcyjny (Random Forest 16)
- Test MAE: **0.624** kWh/h (holdout 80/20, weekly 2026-08-09)
- Test R²: **0.701**
- Gap train–test: **0.057** kWh/h (✅ Model NIE jest przeuczony)
- Daily MAE: **3.96** kWh/d

## Najlepszy algorytm (offline Test MAE): **RF (prod.)**
- Test MAE: 0.602 kWh/h · Test R²: 0.675
- Uwaga: w produkcji RF 16 (kompromis MAE + gap + interpretowalność).

## Ablacja cech (skrót)

- 1_Baza: 1 cech, Test MAE = 1.072 kWh/h
- 2_Pogoda: 6 cech, Test MAE = 0.622 kWh/h
- 3_Kalendarz: 9 cech, Test MAE = 0.605 kWh/h
- 3_Pogoda_Slonce: 13 cech, Test MAE = 0.580 kWh/h
- 3_Pogoda_Slonce_Reguly: 16 cech, Test MAE = 0.581 kWh/h
- 4_Reguly: 19 cech, Test MAE = 0.578 kWh/h

## Walidacja operacyjna (closeout vs FoxESS, do 10.08.2026)

| Okres | n | MAPE raw 5:00 | MAPE raw 12:00 | MAPE CS4 |
|---|---:|---:|---:|---:|
| Era dual 27.07–10.08 | 15 | 9.4% | 9.2% | 10.5% (n=15) |
| Całość 14.07–10.08 | 28 | 16.7% | 14.8% | 10.5% (n=15) |

## Ostatnie dni live (closeout)

| dzień | actual_kWh | raw_5:00 | raw_12:00 | err_raw_kWh | APE_raw_% | CS4_5:00 | APE_CS4_% |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-08-01 | 33.1 | 26.6 | 31.07 | -6.5 | 19.64 | 26.08 | 21.21 |
| 2026-08-02 | 16.4 | 14.16 | 14.35 | -2.24 | 13.66 | 12.08 | 26.34 |
| 2026-08-03 | 33.5 | 33.28 | 32.26 | -0.22 | 0.66 | 32.47 | 3.07 |
| 2026-08-04 | 34.6 | 33.9 | 33.53 | -0.7 | 2.02 | 33.02 | 4.57 |
| 2026-08-05 | 34.9 | 34.47 | 34.49 | -0.43 | 1.23 | 33.72 | 3.38 |
| 2026-08-06 | 33.2 | 34.12 | 33.48 | 0.92 | 2.77 | 33.31 | 0.33 |
| 2026-08-07 | 13.6 | 15.35 | 11.24 | 1.75 | 12.87 | 13.81 | 1.54 |
| 2026-08-08 | 25.4 | 30.89 | 29.32 | 5.49 | 21.61 | 30.47 | 19.96 |
| 2026-08-09 | 37.7 | 33.84 | 33.86 | -3.86 | 10.24 | 33.47 | 11.22 |
| 2026-08-10 | 28.9 | 30.57 | 26.06 | 1.67 | 5.78 | 29.63 | 2.53 |

## Feature importance (Top 5)

- radiation_wm2: 0.309
- hours_until_sunset: 0.177
- sun_position: 0.173
- cloud_cover_pct: 0.090
- temp_c: 0.081

## Wnioski
- Prognoza godzinowa PV w skali FoxESS (target PVE).
- Random Forest 16 cech: najlepszy kompromis offline MAE i niski gap.
- Live closeout do 10.08.2026: era dual MAPE raw ~9–10% (n≈15).

## Green IT
- RF 200 drzew × 16 cech vs cięższy XGBoost — mniejsze ryzyko przeuczenia.
- Harmonogram launchd (sync/prognoza/closeout) zamiast ciągłego retreningu w chmurze.

---
*Wygenerowano z notebooka `05_raport_wynikow.ipynb`*
