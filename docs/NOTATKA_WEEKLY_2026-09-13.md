# Notatka weekly — retrening 13.09.2026

**Data / godzina:** 2026-09-13 ~04:30–04:32 (`train_dual_weekly.sh` via `morning_hold.sh`)  
**Typ:** cotygodniowe odświeżenie wag — **bez zmiany logiki / primary**  
**Okno treningu:** 2025-06-01 → **2026-09-12** (expanding) · **460** dni (368 train / 92 test)  
**Log:** `logs/train.log` · marker `logs/.weekly_train_ok` = **2026-09-13**  
**Pogoda primary (live):** ensemble ICON+UKMO — weekly tego nie rusza

---

## Werdykt (1 zdanie)

> Weekly **OK** · gate RF16 vs **06.09**: Δ Test MAE **−0,020** (lepszy) → **ACCEPT** · primary zostaje **RF 16 + ENS** · pierwsza **Poranna @05** po fixie launchd (12.09 brak daily).

---

## Metryki offline (po train)

| Model | Rola | Cechy | Test MAE | Gap | Daily MAE | Werdykt |
|-------|------|------:|---------:|----:|----------:|---------|
| **RF 16** | **primary** | 16 | **0,666** | 0,071 | **3,38** | nie przeuczony |
| CS4 | shadow | 19 | 0,659 | 0,074 | 3,26 | nie przeuczony |
| XGB+TS | shadow | 24 | 0,644 | 0,073 | 3,08 | nie przeuczony |

Hiperparametry RF16 (min gap): `max_depth=6`, `min_samples_leaf=20`, `min_samples_split=20`, `max_features=1.0` · CV MAE **0,650** ± 0,026.

CS4 (min gap): `max_depth=8`, `min_samples_leaf=20`, `min_samples_split=40`, `max_features=sqrt` · CV MAE **0,656** ± 0,030.

Artefakty (mtime ~04:31–04:32):

- `models/pv_hourly_model.joblib` (+ `.metadata.json`)
- `models/pv_hourly_model_cs4.joblib`
- `models/pv_hourly_model_xgb_ts.joblib`

---

## Gate vs poprzedni weekly (06.09)

| | 06.09 | **13.09** | Δ |
|--|------:|----------:|--:|
| RF16 Test MAE | 0,686 | **0,666** | **−0,020** |
| Gap | 0,096 | 0,071 | −0,025 |
| Daily MAE | 3,58 | **3,38** | −0,20 |
| Protokół | ACCEPT (+0,018 vs 30.08) | lepszy vs 06.09 | **ACCEPT** |

Bez podmiany primary / bez nowych cech / bez auto-routingu RF↔CS4.  
XGB+TS znów najniższy Test MAE — zostaje shadow.

---

## Poranna @05:00 (nowe wagi)

Pierwszy daily po retrainie · `run_at` **2026-09-13T05:00:30–34**:

| Run | 13.09 (nd.) | 14.09 | 15.09 |
|-----|------------:|------:|------:|
| **ENS primary** | **24,42** | 11,79 | 20,76 |
| ICON shadow | 20,79 | 9,70 | 21,28 |
| CS4 shadow | 18,73 | 9,34 | 19,56 |

**13.09 ENS 24,42** ≈ wczoraj peak **23,23** i oneshot ~**23** (MB/Accu outlook) — spójne z jaśniejszym nd.

Kontekst launchd: **12.09** brak Porannej (flock/bash) · **morning-hold + fix** od nd. — **OK**.

---

## Co dalej

1. Nic nie zmieniać w launchd / primary (RF16 + ENS).  
2. ~~Closeout **12.09**~~ — **OK** · wykresy walidacji odświeżone **13.09**.  
3. Kolejny weekly: **niedziela 20.09 ~04:30**.  
4. Outlook **13.09**: Accu **CS4** reżim vs MB/ENS ~**24** — watch mix ([`NOTATKA_2026-09-12.md`](NOTATKA_2026-09-12.md)).

---

## Oś weekly (skrót)

| Data | RF16 Test MAE | CS4 | XGB+TS | Gate |
|------|--------------:|----:|-------:|------|
| **2026-08-30** | **0,668** | 0,672 | 0,654 | ACCEPT |
| **2026-09-06** | **0,686** | 0,688 | 0,665 | ACCEPT (Δ +0,018) |
| **2026-09-13** | **0,666** | 0,659 | 0,644 | **ACCEPT** (Δ **−0,020** vs 06.09) |

Pełna historia: [`NOTATKA_RETRENINGI_LIPIEC_2026.md`](NOTATKA_RETRENINGI_LIPIEC_2026.md) · status: [`STATUS_ML_MLOPS.md`](STATUS_ML_MLOPS.md) · poprzedni: [`NOTATKA_WEEKLY_2026-09-06.md`](NOTATKA_WEEKLY_2026-09-06.md).
