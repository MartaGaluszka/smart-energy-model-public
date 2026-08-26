# Notatka weekly — retrening 16.08.2026

**Data / godzina:** 2026-08-16 ~04:30 (`train_dual_weekly.sh` / launchd)  
**Typ:** cotygodniowe odświeżenie wag — **bez zmiany logiki / primary**  
**Okno treningu:** 2025-06-01 → **2026-08-15** (expanding)  
**Log:** `logs/train.log` · daily 05:00 już na nowych artefaktach

---

## Werdykt (1 zdanie)

> Weekly **OK** · gate RF16 vs 09.08: Δ Test MAE **+0.019** (≤ +0.02) → **ACCEPT** · primary zostaje **RF 16 + ICON** · CS4 / XGB+TS nadal shadow.

---

## Metryki offline (po train)

| Model | Rola | Cechy | Test MAE | Gap | Daily MAE | Werdykt |
|-------|------|------:|---------:|----:|----------:|---------|
| **RF 16** | **primary** | 16 | **0.643** | 0.063 | 3.56 | nie przeuczony |
| CS4 | shadow | 19 | 0.637 | 0.068 | 3.59 | nie przeuczony |
| XGB+TS | shadow | 24 | 0.626 | 0.074 | 3.17 | nie przeuczony |

Artefakty (mtime ~04:31–04:32):

- `models/pv_hourly_model.joblib` (+ `.metadata.json`)
- `models/pv_hourly_model_cs4.joblib`
- `models/pv_hourly_model_xgb_ts.joblib`

---

## Gate vs poprzedni weekly (09.08)

| | 09.08 | **16.08** | Δ |
|--|------:|----------:|--:|
| RF16 Test MAE | ~0.624 | **0.643** | **+0.019** |
| Protokół | — | remis ≤ +0.02 | **ACCEPT** |

Bez podmiany primary / bez nowych cech / bez UKMO w prod.

---

## Kontekst live (przed tym weekly)

Walidacja closeoutów (stan na **20.08**, do **19.08**):

| Okres | n | MAPE raw 5:00 | MAPE raw 12:00 |
|-------|--:|-------------:|---------------:|
| Era dual 27.07–19.08 | 24 | **9,1%** | **9,7%** |
| Całość 14.07–19.08 | 37 | 14,8% | 13,8% |

CS4: MAPE daily ~**10,0%** (n=24). Pochmurne: **16–17.08** best `daily_cs4`. Jasne: **19.08** actual **24,7** — RF daily +3,7 / CS4 +4,9 (zaniżenie). Szare: **18.08** 17,8 — modele zawyżyły.

---

## Pogoda wokół weekly (AccuWeather, ręcznie)

| Dzień | Skrót Accu | PV / obserwacja |
|-------|------------|-----------------|
| **15.08** | upał, cloud ~3%, jasność 10, 0 mm | szczyt produkcji |
| **16.08** (dziś-na-dziś) | 34°C, cloud **29%**, jasność 8, **0,5 mm** P=55%, porywy ~43 | wysoka PV; MB MultiModel: ICON≈UKMO (słońce) |
| **17.08** | 26°C, cloud **54%**, jasność **5**, **3,4 mm**, burze P=54%, alert pomarańcz od **14:00** | Accu dziś-na-dziś ≈ ICON (start ~14–15); closeout CS4 vs RF |
| **18.08** | 20°C, cloud 78%, jasność 4, **2,1 mm**, porywy 44 | słaba PV; Accu łagodniejszy niż MB „ciągły deszcz” |
| **19.08** | 24°C, cloud 68%, jasność 6, **1,4 mm** wcześnie | umiarkowana / powrót |

Szerszy opis 15–17.08: [`NOTATKA_POGODA_2026-08-15.md`](NOTATKA_POGODA_2026-08-15.md).

---

## Co dalej

1. Nic nie zmieniać w launchd / primary.  
2. Closeout **17.08** (front): RF16 vs CS4 na nowych wagach + notatka timing deszczu (ICON / UKMO / Accu).  
3. Kolejny weekly: **niedziela 23.08 ~04:30** → **zrobione** ([`NOTATKA_WEEKLY_2026-08-23.md`](NOTATKA_WEEKLY_2026-08-23.md), ACCEPT Δ +0.015).  
4. Po serii closeoutów po 16.08 — odświeżyć wykresy walidacji → **zrobione 18.08 (do 17.08)**, **20.08 (do 19.08)**, **22.08 (do 21.08)**, **23.08 (do 22.08)** i **25.08 (do 24.08)**; era dual MAPE **11,0% / 10,0%**, n=29.

---

## Oś weekly (skrót)

| Data | RF16 Test MAE | CS4 | XGB+TS | Gate |
|------|--------------:|----:|-------:|------|
| 2026-08-02 | (w erze dual) | — | — | odświeżenie wag |
| **2026-08-09** | **0.624** | 0.632 | 0.608 | ACCEPT |
| **2026-08-16** | **0.643** | 0.637 | 0.626 | **ACCEPT** (Δ +0.019) |

Pełna historia wdrożeń: [`NOTATKA_RETRENINGI_LIPIEC_2026.md`](NOTATKA_RETRENINGI_LIPIEC_2026.md) · status: [`STATUS_ML_MLOPS.md`](STATUS_ML_MLOPS.md).
