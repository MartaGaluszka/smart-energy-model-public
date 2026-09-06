# Notatka weekly — retrening 06.09.2026

**Data / godzina:** 2026-09-06 ~04:31–04:32 (`train_dual_weekly.sh` / launchd)  
**Typ:** cotygodniowe odświeżenie wag — **bez zmiany logiki / primary**  
**Okno treningu:** 2025-06-01 → **2026-09-05** (expanding) · **453** dni (362 train / 91 test)  
**Log:** `logs/train.log` · artefakty mtime ~04:31–04:32  
**Pogoda primary (live):** ensemble ICON+UKMO od daily **02.09** — weekly tego nie rusza

---

## Werdykt (1 zdanie)

> Weekly **OK** · gate RF16 vs 30.08: Δ Test MAE **+0.018** (≤ +0.02) → **ACCEPT** (na granicy) · primary zostaje **RF 16 + ENS** · CS4 / XGB+TS / ICON solo nadal shadow.

---

## Metryki offline (po train)

| Model | Rola | Cechy | Test MAE | Gap | Daily MAE | Werdykt |
|-------|------|------:|---------:|----:|----------:|---------|
| **RF 16** | **primary** | 16 | **0.686** | 0.096 | **3.58** | nie przeuczony |
| CS4 | shadow | 19 | 0.688 | 0.098 | 3.57 | nie przeuczony |
| XGB+TS | shadow | 24 | 0.665 | 0.102 | 3.48 | nie przeuczony |

Hiperparametry RF16 (wybrane min gap): `max_depth=6`, `min_samples_leaf=20`, `min_samples_split=20`, `max_features=1.0` · CV MAE **0.644** ± 0.014.

CS4: te same `max_depth=6` / `min_samples_leaf=20` / `max_features=1.0`, `min_samples_split=40` · CV MAE **0.647**.

Artefakty:

- `models/pv_hourly_model.joblib` (+ `.metadata.json`)
- `models/pv_hourly_model_cs4.joblib`
- `models/pv_hourly_model_xgb_ts.joblib`

---

## Gate vs poprzedni weekly (30.08)

| | 30.08 | **06.09** | Δ |
|--|------:|----------:|--:|
| RF16 Test MAE | 0.668 | **0.686** | **+0.018** |
| Gap | 0.072 | 0.096 | +0.024 |
| Daily MAE | 3.46 | **3.58** | +0.12 |
| Protokół | — | remis ≤ +0.02 | **ACCEPT** |

Bez podmiany primary / bez nowych cech / bez UKMO solo w prod / bez auto-routingu RF↔CS4.  
XGB+TS znów najniższy Test MAE — zostaje shadow.

**Uwaga:** +0.018 jest tuż pod progiem REJECT (+0.02). Kolejny weekly (13.09): jeśli Δ vs 30.08 przekroczy +0.02 albo vs 06.09 znów ~+0.02 — **REVIEW** (sezon / więcej dni mix).

---

## Kontekst live (tydzień przed weekly)

Closeouty 30.08–05.09 (Fox / ENS daily raw):

| Dzień | Accu pick | Fox | Δ ENS |
|-------|-----------|----:|------:|
| **30.08** | RF | **33,2** | ens −6% (RF −15%) |
| **31.08** | CS4 | **24,6** | ens **+7%** · CS4 −17% |
| **1.09** | RF | **32,4** | ens **−3%** |
| **2.09** | RF · **ENS primary od daily** | **31,0** | ENS **−11%** |
| **3.09** | RF | **27,4** | ENS **−11%** · peak −4% |
| **4.09** | CS4 | **18,9** | ENS **−6,5%** · CS4 −20% |
| **5.09** | CS4 | **20,2** | ENS **+1,3%** |

Live era ENS **02.09–05.09** (n=4): MAPE raw **7,7% / 8,4%**. Dual ICON **27.07–01.09** (n=37): **15,6% / 15,8%**. Wykresy: [`july_validation_summary.md`](images/ml/july_validation_summary.md).

Dzień 6.09 (po train): Accu mix→**RF** · midday ENS **26,3** · oneshot ½ **26,3** — [`NOTATKA_2026-09-06.md`](NOTATKA_2026-09-06.md).

---

## Co dalej

1. Nic nie zmieniać w launchd / primary (RF16 + ENS).  
2. Closeout **6.09** EOD · **7.09** Accu CS4 · **8.09** Accu RF (UKMO rad skip).  
3. Kolejny weekly: **niedziela 13.09 ~04:30** — pilnować Δ Test MAE (ten run na granicy).  
4. Wykresy walidacji już do **05.09** (linie ICON 18.07 / dual 26.07 / ENS 02.09).

---

## Oś weekly (skrót)

| Data | RF16 Test MAE | CS4 | XGB+TS | Gate |
|------|--------------:|----:|-------:|------|
| **2026-08-09** | **0.624** | 0.632 | 0.608 | ACCEPT |
| **2026-08-16** | **0.643** | 0.637 | 0.626 | ACCEPT (Δ +0.019) |
| **2026-08-23** | **0.658** | 0.664 | 0.618 | ACCEPT (Δ +0.015) |
| **2026-08-30** | **0.668** | 0.672 | 0.654 | ACCEPT (Δ +0.010) |
| **2026-09-06** | **0.686** | 0.688 | 0.665 | **ACCEPT** (Δ +0.018) |

Pełna historia: [`NOTATKA_RETRENINGI_LIPIEC_2026.md`](NOTATKA_RETRENINGI_LIPIEC_2026.md) · status: [`STATUS_ML_MLOPS.md`](STATUS_ML_MLOPS.md) · poprzedni: [`NOTATKA_WEEKLY_2026-08-30.md`](NOTATKA_WEEKLY_2026-08-30.md).
