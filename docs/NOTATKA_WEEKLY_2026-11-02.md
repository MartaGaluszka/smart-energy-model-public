# Notatka weekly — retrening 02.11.2026 (niedziela ~04:30)

**Status:** szablon przed runem · uzupełnij po `train_dual_weekly.sh`  
**Zakres (31.10 ustalenie):** **CS4 go-live** (1. tydzień operacyjny w apce/baterii) + rutyna wag **RF16 / CS4 / XGB** — **bez sekcji L30** w tej notatce (L30 = osobny wątek ~**08.11**, patrz [`NOTATKA_GATE_L30_CLOSEOUT.md`](NOTATKA_GATE_L30_CLOSEOUT.md)).  
**L30 w tle:** job nadal zapisze `l30_*` do `weekly_dual_metrics.csv` — **nie** kopiuj do werdyktu weekly.

**Typ:** cotygodniowe odświeżenie `.joblib` — **primary RF16 + ENS** bez zmiany logiki launchd  
**Okno treningu:** _(po train: train_start → train_end)_  
**Go-live CS4:** [`NOTATKA_GO_LIVE_CS4_2026-11.md`](NOTATKA_GO_LIVE_CS4_2026-11.md) · decyzja [`NOTATKA_DECYZJA_CS4_XI_2026.md`](NOTATKA_DECYZJA_CS4_XI_2026.md)

---

## Werdykt (1 zdanie)

> _(uzupełnij: shuffle gate RF/CS4/XGB · primary bez zmian · 1. tydzień live CS4 display vs Fox — skrót closeout)_

---

## Metryki offline (po train) — shuffle / daily test

| Model | Rola | Test MAE (shuffle) | Daily MAE | Gate (Δ vs 25.10) |
|-------|------|-------------------:|----------:|-------------------|
| **RF 16** | **primary** | _._ | _._ | _ACCEPT/REVIEW_ |
| CS4 | shadow + **display pochmurny** | _._ | _._ | _._ |
| XGB+TS | shadow | _._ | _._ | _._ |

- Werdykt tuningu: _(nieprzeuczone / gap — z CSV)_  
- **Nie** opierać werdyktu na L30 — osobna notatka gate później.

Artefakty: `models/pv_hourly_model.joblib` · `…_cs4.joblib` · `…_xgb_ts.joblib` · CSV `recorded_at=2026-11-02`.

---

## Gate vs poprzednie weekly (25.10)

| | 25.10 | **02.11** |
|--|------:|----------:|
| RF16 Test MAE | 0,673 | _._ |
| Δ vs poprzedni | +0,003 (ACCEPT) | _._ |

Primary zostaje **RF 16 + ENS**. CS4 joblib odświeżony — **display** w apce wg Accu, nie wg L30.

---

## CS4 operacyjny — tydzień closeout (26.10 → 01.11)

_(Subset dni **Accu pochmurny/ciemny** — WAPE/bias @05 **ENS** vs **CS4 @05** vs **Fox**; opcjonalnie czy routing pokazał CS4.)_

| Okres | ENS @05 | CS4 @05 (pochmurne) | Fox | Uwagi |
|-------|---------|---------------------|-----|--------|
| _._ | _._ | _._ | _._ | _._ |

Powiązane dni: [`NOTATKA_2026-10-31.md`](NOTATKA_2026-10-31.md) · _dopisz 01.11–02.11 po closeout_

---

## L30

**Pominięte w tej notatce** — celowo (czytelność: CS4 ≠ L30). Historia L30 w CSV; pierwsza **decyzja** soft→hard: **~08.11** ([`NOTATKA_PODSUMOWANIE_CS4_L30_XI_2026.md`](NOTATKA_PODSUMOWANIE_CS4_L30_XI_2026.md) §5).

---

## Linki

- Status: [`STATUS_ML_MLOPS.md`](STATUS_ML_MLOPS.md)  
- Poprzedni weekly: [`NOTATKA_WEEKLY_2026-10-25.md`](NOTATKA_WEEKLY_2026-10-25.md)  
- Dual report (technicznie): [`NOTATKA_GATE_DUAL_L30.md`](NOTATKA_GATE_DUAL_L30.md)
