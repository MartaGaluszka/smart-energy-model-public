# Notatka weekly — retrening 30.08.2026

**Data / godzina:** 2026-08-30 ~04:30 (`train_dual_weekly.sh` / launchd)  
**Typ:** cotygodniowe odświeżenie wag — **bez zmiany logiki / primary**  
**Okno treningu:** 2025-06-01 → **2026-08-29** (expanding) · 446 dni  
**Log:** `logs/train.log` · artefakty mtime ~04:30–04:32

---

## Werdykt (1 zdanie)

> Weekly **OK** · gate RF16 vs 23.08: Δ Test MAE **+0.010** (≤ +0.02) → **ACCEPT** · primary zostaje **RF 16 + ICON** · CS4 / XGB+TS + ensemble ICON+UKMO nadal shadow.

---

## Metryki offline (po train)

| Model | Rola | Cechy | Test MAE | Gap | Daily MAE | Werdykt |
|-------|------|------:|---------:|----:|----------:|---------|
| **RF 16** | **primary** | 16 | **0.668** | 0.072 | **3.46** | nie przeuczony |
| CS4 | shadow | 19 | 0.672 | 0.079 | 3.57 | nie przeuczony |
| XGB+TS | shadow | 24 | 0.654 | 0.096 | 3.25 | nie przeuczony |

Hiperparametry RF16 (wybrane min gap): `max_depth=6`, `min_samples_leaf=20`, `min_samples_split=20`, `max_features=1.0` · CV MAE **0.648**.

Artefakty:

- `models/pv_hourly_model.joblib` (+ `.metadata.json`)
- `models/pv_hourly_model_cs4.joblib`
- `models/pv_hourly_model_xgb_ts.joblib`

---

## Gate vs poprzedni weekly (23.08)

| | 23.08 | **30.08** | Δ |
|--|------:|----------:|--:|
| RF16 Test MAE | 0.658 | **0.668** | **+0.010** |
| Protokół | — | remis ≤ +0.02 | **ACCEPT** |

Bez podmiany primary / bez nowych cech / bez UKMO w prod / bez auto-routingu RF↔CS4.

---

## Kontekst live (tydzień przed weekly)

| Dzień | Skrót | Actual / pick |
|-------|--------|---------------|
| **25.08** | mokry | **4,4** · CS4 paper |
| **26.08** | clearing | **21,1** · RF undershoot |
| **27–28.08** | jasne | RF + undershoot; Accu 28 poprawa 5/58%→9/21% |
| **29.08** | burza AM → clearing | **21,1** · routing/okno **CS4 21,5 (+2%)** ✓ |
| **30.08** | jasny (Accu 9/23%, 0 cloud @15) | PV **≥25,9** @15:02 · daily RF ~**27** · SoC 100% od południa |

Shadow ensemble ICON+UKMO: **LIVE** od 28.08. Routing test 28–31: [`NOTATKA_TEST_ROUTING_28-31_08.md`](NOTATKA_TEST_ROUTING_28-31_08.md).

Oneshot 29–30 (archive RF×ICON/UKMO): UKMO≈fakt na 29; UKMO zawyża na 30 — [`NOTATKA_2026-08-30.md`](NOTATKA_2026-08-30.md).

---

## Co dalej

1. Nic nie zmieniać w launchd / primary.  
2. Closeout **30.08** EOD + **31.08** (CS4 / deszcz PM).  
3. Gate routing ens/CS4: **01.09**.  
4. Kolejny weekly: **niedziela 06.09 ~04:30**.  
5. Wykresy walidacji: nadal do **24.08** — odświeżyć po serii closeoutów 25–31.

---

## Oś weekly (skrót)

| Data | RF16 Test MAE | CS4 | XGB+TS | Gate |
|------|--------------:|----:|-------:|------|
| **2026-08-09** | **0.624** | 0.632 | 0.608 | ACCEPT |
| **2026-08-16** | **0.643** | 0.637 | 0.626 | ACCEPT (Δ +0.019) |
| **2026-08-23** | **0.658** | 0.664 | 0.618 | ACCEPT (Δ +0.015) |
| **2026-08-30** | **0.668** | 0.672 | 0.654 | **ACCEPT** (Δ +0.010) |

Pełna historia: [`NOTATKA_RETRENINGI_LIPIEC_2026.md`](NOTATKA_RETRENINGI_LIPIEC_2026.md) · status: [`STATUS_ML_MLOPS.md`](STATUS_ML_MLOPS.md) · poprzedni: [`NOTATKA_WEEKLY_2026-08-23.md`](NOTATKA_WEEKLY_2026-08-23.md).
