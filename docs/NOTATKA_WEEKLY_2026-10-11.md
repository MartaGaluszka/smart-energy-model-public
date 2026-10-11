# Notatka weekly — retrening 11.10.2026

**Data / godzina:** 2026-10-11 ~04:30–04:33 (`train_dual_weekly.sh`, uruchomienie przez poranny hold)  
**Typ:** cotygodniowe odświeżenie wag — **bez zmiany logiki / primary**  
**Okno treningu:** 2025-06-01 → **2026-10-10** (expanding) · **488** dni / **5192** h  
**Log:** `logs/cron.log` (przebieg od `=== Weekly train … 04:30:01 ===`)  
**Pogoda primary (live):** ensemble ICON+UKMO — weekly tego nie rusza  
**Dual report:** shuffle + L30 — [`NOTATKA_GATE_DUAL_L30.md`](NOTATKA_GATE_DUAL_L30.md) · closeout live: [`NOTATKA_GATE_L30_CLOSEOUT.md`](NOTATKA_GATE_L30_CLOSEOUT.md)

---

## Werdykt (1 zdanie)

> Weekly **OK dla primary** · RF16 vs 04.10: Δ Test MAE **+0,003** → **ACCEPT** · CS4 **ACCEPT** (Δ **−0,000**) · **XGB+TS REVIEW** (Δ **+0,027** > +0,02) — tylko shadow, **bez auto-rollback** · L30 **INFO** u wszystkich · primary **RF 16 + ENS** bez zmian · **watch live:** tydzień 05–11.10 bias **−10%** (WATCH; poprzedni 28.09–04.10 był ALARM w bias).

---

## Metryki offline (po train)

| Model | Rola | Test MAE (shuffle) | Gap | Daily MAE | L30 MAE | L30 daily | Gate |
|-------|------|-------------------:|----:|----------:|--------:|----------:|------|
| **RF 16** | **primary** | **0,674** | 0,080 | **3,38** | 0,872 | 4,05 | ACCEPT (Δ +0,003) · L30 INFO |
| CS4 | shadow | 0,673 | 0,084 | 3,27 | 0,836 | 3,72 | ACCEPT (Δ −0,000) · L30 INFO |
| XGB+TS | shadow | 0,672 | 0,103 | 3,21 | 0,851 | 4,26 | **REVIEW** (Δ +0,027) · L30 INFO |

- Żaden model nie jest przeuczony (werdykt tuningu).
- Hiperparametry RF16: `max_depth=6`, `min_samples_leaf=20`, `min_samples_split=20`, `max_features=1.0` (**bez zmian** vs 04.10) · CV MAE **0,650**.
- CS4: `max_depth=6`, `min_samples_leaf=20`, `min_samples_split=20`, `max_features=1.0` (04.10 było `min_samples_split=40`) · CV MAE **0,647**.
- XGB+TS: 24 cech · `max_depth=3`, `n_estimators=200`, `learning_rate=0.05`, `min_child_weight=10` · Train MAE **0,570** / Test **0,672**.
- L30 holdout: **2026-09-11 → 2026-10-10** (30 dni). L30 gap (test−train): RF16 **+0,272** · CS4 **+0,231** · XGB+TS **+0,271**.
- **Obserwacja:** MAE dzienne (shuffle) **spadło** vs 04.10 (RF 3,54→3,38, CS4 3,50→3,27, XGB 3,37→3,21), a L30 daily **wzrosło** (RF 3,71→4,05, CS4 3,46→3,72, XGB 3,85→4,26). Holdout L30 zawiera **10.10 (−28% live)** — to tłumaczy skok L30, nie regresję shuffle.

Artefakty (mtime ~04:31–04:32): `models/pv_hourly_model.joblib` · `…_cs4.joblib` · `…_xgb_ts.joblib` · historia: `data/processed/weekly_dual_metrics.csv`.

---

## Gate vs poprzednie weekly

| | 27.09 | 04.10 | **11.10** |
|--|------:|------:|----------:|
| RF16 Test MAE | 0,677 | 0,671 | **0,674** |
| Δ vs poprzedni | +0,025 (REVIEW) | −0,006 (ACCEPT) | **+0,003 (ACCEPT)** |
| Gap (RF16) | 0,079 | 0,074 | **0,080** |
| XGB Test MAE | 0,645 | 0,646 | **0,672** |
| XGB Δ vs poprzedni | ACCEPT | ACCEPT | **+0,027 (REVIEW)** |

Primary zostaje. XGB REVIEW = tylko shadow; bez zmiany routingu. Kolejny weekly (18.10): jeśli XGB znów Δ ≫ +0,02 vs 11.10 albo vs 04.10 — pogłębiony przegląd shadow, nadal bez auto-rollback.

---

## L30 — porównanie weekly (soft, INFO/WATCH)

Progi soft: ~**0,75–1,0** = INFO · powyżej = WATCH · `hard_reject=False` ([`NOTATKA_GATE_DUAL_L30.md`](NOTATKA_GATE_DUAL_L30.md)). Holdout = ostatnie 30 dni do `train_end` (okno się przesuwa — **nie porównuj 1:1 jak ten sam test**).

| Weekly | Holdout L30 | RF16 L30 / daily | CS4 L30 / daily | XGB L30 / daily | Soft |
|--------|-------------|-----------------:|----------------:|----------------:|------|
| 27.09 | 28.08–26.09 | 0,803 / 3,51 | — | — | INFO (tylko RF) |
| 04.10 | 04.09–03.10 | 0,808 / 3,71 | 0,795 / 3,46 | 0,842 / 3,85 | INFO ×3 |
| **11.10** | **11.09–10.10** | **0,872 / 4,05** | **0,836 / 3,72** | **0,851 / 4,26** | **INFO ×3** |

Δ L30 (11.10 − 04.10), godz. / daily:

| Model | Δ L30 MAE | Δ L30 daily | L30 gap (test−train) 04.10 → 11.10 |
|-------|----------:|------------:|-------------------------------------|
| RF16 | **+0,064** | **+0,34** | +0,207 → **+0,272** |
| CS4 | **+0,041** | **+0,27** | +0,191 → **+0,231** |
| XGB+TS | **+0,008** | **+0,41** | +0,263 → **+0,271** |

**Ranking L30 godz. 11.10:** CS4 **0,836** < XGB **0,851** < RF16 **0,872** (na 04.10: CS4 < RF < XGB).  
**Ranking L30 daily 11.10:** CS4 **3,72** < RF **4,05** < XGB **4,26**.

**Czytanie:** wszystkie nadal w paśmie INFO (daleko od 1,0). Skok RF/CS4 L30 godzinowego i daily u wszystkich to głównie **nowe okno** (wypadł 04–10.09, weszło 04–10.10 z **10.10 −28% live**), nie regresja shuffle (shuffle daily nawet spadło). XGB: L30 godz. prawie płaskie (+0,008), a shuffle Test MAE skoczył (+0,027 REVIEW) — soft L30 **nie** potwierdza REVIEW; REVIEW zostaje tylko z hard gate shuffle. CS4 nadal najstabilniejszy na chrono L30 (najniższe MAE i najmniejszy Δ daily wśród trzech).

---

## Pierwszy dzień na nowych wagach (closeout)

| Dzień | Fox | ENS @05 | Błąd @05 | Uwaga |
|-------|----:|--------:|---------:|-------|
| 10.10 (stare wagi) | 22,0 | 15,85 | −28% | ostatni dzień okna treningu |
| **11.10 (nowe wagi)** | **15,9** | **12,04** | **−24,3%** | @05 **05:00** już po trainie 04:30 |

Jeden dzień — to nie jest dowód regresji wag. 11.10 to dzień mieszany/słaby (Accu **6 / 52% / 0,2 mm**); niedoszacowanie jest w tym samym kierunku co bias jasnych/mieszanych dni. Prognozy @05 na **12.10 / 13.10** (nowe wagi): ENS **20,61 / 20,66**.

---

## Tydzień live 05–11.10 (prognoza @05 vs Fox)

Kryteria: [`NOTATKA_GATE_L30_CLOSEOUT.md`](NOTATKA_GATE_L30_CLOSEOUT.md).

| Dzień | Fox | ENS @05 | Błąd |
|-------|----:|--------:|-----:|
| 05.10 | 28,1 | 26,66 | −5% |
| 06.10 | 27,2 | 22,64 | −17% |
| 07.10 | 24,4 | 23,41 | −4% |
| 08.10 | 18,8 | 18,72 | −0,4% |
| 09.10 | 18,1 | 19,79 | +9% |
| 10.10 | 22,0 | 15,85 | **−28%** |
| 11.10 | 15,9 | 12,04 | −24% |

WAPE **12,1%** · bias **−10,0%** · dni jasne (Fox ≥ 20) bias **−12,9%** (n=4) · najgorszy dzień **−28%** (10.10) → ocena **WATCH** (WAPE OK, |bias| 8–12%, najgorszy dzień WATCH).

Poprzedni tydzień 28.09–04.10 był **ALARM w bias** (−13,9%). Dwa tygodnie z rzędu poza OK w bias — wg bramy to sygnał do przeglądu (nie auto-rollback). Trop: niedoszacowanie dni jasnych / „jasnych mimo chmur NWP” ([`NOTATKA_BIAS_JASNE_DNI_2026-10-05.md`](NOTATKA_BIAS_JASNE_DNI_2026-10-05.md); case **10.10** w [`NOTATKA_2026-10-10.md`](NOTATKA_2026-10-10.md) / [`NOTATKA_2026-10-11.md`](NOTATKA_2026-10-11.md)).

Wykresy walidacji odświeżone **11.10** (n=90): [`images/ml/july_validation_summary.md`](images/ml/july_validation_summary.md) · [`images/ml/production_validation_plot.png`](images/ml/production_validation_plot.png).

---

## Co dalej

1. Primary **bez zmian** (RF16 + ENS) · CS4/XGB shadow.
2. Kolejny weekly: **2026-10-18 ~04:30** — RF Δ vs 0,674; XGB: czy REVIEW się utrzymuje.
3. Live: jeśli tydzień 12–18.10 znów |bias| > 8% → trzeci tydzień z rzędu poza OK → przegląd wg bramy closeout (bias jasnych dni / alignment cech).
4. XGB REVIEW: nie promuj do primary; w weekly review sobotnim pilnuj peak @16 (shadow XGB).

---

## Oś weekly (skrót)

| Data | RF16 Test MAE | CS4 | XGB+TS | Gate |
|------|--------------:|----:|-------:|------|
| 2026-09-20 | 0,652 | 0,658 | 0,648 | ACCEPT (Δ −0,014) |
| 2026-09-27 | 0,677 | 0,673 | 0,645 | **REVIEW** (Δ +0,025) |
| 2026-10-04 | 0,671 | 0,673 | 0,646 | ACCEPT (Δ −0,006) · L30 INFO |
| **2026-10-11** | **0,674** | 0,673 | **0,672** | RF/CS4 ACCEPT · **XGB REVIEW** · L30 INFO |

Pełna historia: [`NOTATKA_RETRENINGI_I_WDROZENIA.md`](NOTATKA_RETRENINGI_I_WDROZENIA.md) · status: [`STATUS_ML_MLOPS.md`](STATUS_ML_MLOPS.md) · poprzedni: [`NOTATKA_WEEKLY_2026-10-04.md`](NOTATKA_WEEKLY_2026-10-04.md) · dzień: [`NOTATKA_2026-10-11.md`](NOTATKA_2026-10-11.md).
