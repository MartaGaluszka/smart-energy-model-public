# Raport: Smart Energy Model — prognoza PV
**Data:** 2026-08-18 11:07

## Konfiguracja
- Random state: 42
- Split: 80/20 po dniach
- Okno treningowe: 2025-06-01 → 2026-08-15
- Cechy: 16 · target: delta PVEnergyTotal (kWh/h)
- Model weekly: 2026-08-16

## Wyniki modeli (holdout godzinowy)

| Model | Test MAE [kWh/h] | Test R² | Gap [kWh/h] | Werdykt |
|-------|----------------:|--------:|------------:|---------|
| Ridge | 0.831 | 0.526 | -0.003 | ✅ Nie przeuczony |
| RF (prod.) | 0.602 | 0.675 | 0.096 | ✅ Nie przeuczony |
| XGBoost | 0.614 | 0.654 | 0.470 | ❌ Przeuczony |

## Model produkcyjny (Random Forest 16)
- Test MAE: **0.643** kWh/h (holdout 80/20, weekly 2026-08-16)
- Test R²: **0.681**
- Gap train–test: **0.063** kWh/h (✅ Model NIE jest przeuczony)
- Daily MAE: **3.56** kWh/d

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

## Walidacja operacyjna (closeout vs FoxESS, do 17.08.2026)

| Okres | n | MAPE raw 5:00 | MAPE raw 12:00 | MAPE CS4 |
|---|---:|---:|---:|---:|
| Era dual 27.07–17.08 | 22 | 8.7% | 9.1% | 9.6% (n=22) |
| Całość 14.07–17.08 | 35 | 14.8% | 13.6% | 9.6% (n=22) |

## Ostatnie dni live (closeout)

| dzień | actual_kWh | raw_5:00 | raw_12:00 | err_raw_kWh | APE_raw_% | CS4_5:00 | APE_CS4_% |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-08-08 | 25.4 | 30.89 | 29.32 | 5.49 | 21.61 | 30.47 | 19.96 |
| 2026-08-09 | 37.7 | 33.84 | 33.86 | -3.86 | 10.24 | 33.47 | 11.22 |
| 2026-08-10 | 28.9 | 30.57 | 26.06 | 1.67 | 5.78 | 29.63 | 2.53 |
| 2026-08-11 | 22.6 | 21.47 | 24.18 | -1.13 | 5.0 | 20.94 | 7.35 |
| 2026-08-12 | 36.3 | 32.25 | 32.6 | -4.05 | 11.16 | 31.24 | 13.94 |
| 2026-08-13 | 37.7 | 33.51 | 33.39 | -4.19 | 11.11 | 32.9 | 12.73 |
| 2026-08-14 | 37.3 | 33.5 | 33.54 | -3.8 | 10.19 | 33.29 | 10.75 |
| 2026-08-15 | 35.9 | 33.61 | 33.63 | -2.29 | 6.38 | 33.28 | 7.3 |
| 2026-08-16 | 33.7 | 32.72 | 32.26 | -0.98 | 2.91 | 33.25 | 1.34 |
| 2026-08-17 | 21.5 | 22.2 | 18.9 | 0.7 | 3.26 | 21.36 | 0.65 |

## Feature importance (Top 5)

- radiation_wm2: 0.309
- hours_until_sunset: 0.177
- sun_position: 0.173
- cloud_cover_pct: 0.090
- temp_c: 0.081

## Wnioski
- Prognoza godzinowa PV w skali FoxESS (target PVE).
- Random Forest 16 cech: najlepszy kompromis offline MAE i niski gap.
- Live closeout do 17.08.2026: era dual MAPE raw ~9–10% (n≈15).

## Green IT
- RF 200 drzew × 16 cech vs cięższy XGBoost — mniejsze ryzyko przeuczenia.
- Harmonogram launchd (sync/prognoza/closeout) zamiast ciągłego retreningu w chmurze.

---
*Wygenerowano z notebooka `05_raport_wynikow.ipynb`*
