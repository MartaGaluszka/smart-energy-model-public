# Notatka weekly — retrening 04.10.2026

**Data / godzina:** 2026-10-04 ~04:30–04:33 (`train_dual_weekly.sh`, uruchomienie przez poranny hold)  
**Typ:** cotygodniowe odświeżenie wag — **bez zmiany logiki / primary**  
**Okno treningu:** 2025-06-01 → **2026-10-03** (expanding) · **481** dni / **5118** h  
**Log:** `logs/cron.log` (przebieg) · `logs/train.log` ma tylko wpis „weekly train już trwa — pomijam" (zdublowany trigger launchd, zastał blokadę)  
**Pogoda primary (live):** ensemble ICON+UKMO — weekly tego nie rusza  
**Pierwszy weekly z pełnym dual reportem** (shuffle + L30): [`NOTATKA_GATE_DUAL_L30.md`](NOTATKA_GATE_DUAL_L30.md)

---

## Werdykt (1 zdanie)

> Weekly **OK** · RF16 vs 27.09: Δ Test MAE **−0,006** → **ACCEPT** · **REVIEW z 27.09 zamknięty** (Δ vs 20.09 = **+0,019**, tuż pod progiem +0,02) · L30 **INFO** dla wszystkich trzech modeli · primary **RF 16 + ENS** bez zmian · **watch:** bias live (−14% w tygodniu 28.09–04.10).

---

## Metryki offline (po train)

| Model | Rola | Test MAE (shuffle) | Gap | Daily MAE | L30 MAE | L30 daily | Gate |
|-------|------|-------------------:|----:|----------:|--------:|----------:|------|
| **RF 16** | **primary** | **0,671** | 0,074 | **3,54** | 0,808 | 3,71 | ACCEPT (Δ −0,006) · L30 INFO |
| CS4 | shadow | 0,673 | 0,078 | 3,50 | 0,795 | 3,46 | ACCEPT (Δ +0,000) · L30 INFO |
| XGB+TS | shadow | 0,646 | 0,072 | 3,37 | 0,842 | 3,85 | ACCEPT (Δ +0,001) · L30 INFO |

- Żaden model nie jest przeuczony.
- Hiperparametry RF16: `max_depth=6`, `min_samples_leaf=20`, `min_samples_split=20`, `max_features=1.0` (**bez zmian** vs 27.09) · CV MAE **0,655** ± 0,020.
- CS4: `max_depth=6`, `min_samples_leaf=20`, `min_samples_split=40`, `max_features=1.0` (było 8 / 20 / 20 / sqrt) · CV MAE **0,654**.
- L30 holdout: **2026-09-04 → 2026-10-03** (30 dni). L30 gap (test−train): RF16 +0,207 · CS4 +0,191 · XGB+TS +0,263.
- **Obserwacja:** MAE dzienne (shuffle) wzrosło we wszystkich trzech (RF 3,44→3,54, CS4 3,38→3,50, XGB 3,12→3,37), a godzinowe jest stabilne. Najpewniej efekt innego okna testowego (8 nowych dni); nie weryfikowano.

Artefakty (mtime ~04:31–04:32): `models/pv_hourly_model.joblib` · `…_cs4.joblib` · `…_xgb_ts.joblib` · historia: `data/processed/weekly_dual_metrics.csv`.

---

## Gate vs poprzednie weekly

| | 20.09 | 27.09 | **04.10** |
|--|------:|------:|----------:|
| RF16 Test MAE | 0,652 | 0,677 | **0,671** |
| Δ vs poprzedni | −0,014 | +0,025 (REVIEW) | **−0,006 (ACCEPT)** |
| Δ vs 20.09 | — | +0,025 | **+0,019** |
| Gap | 0,054 | 0,079 | **0,074** |

Zapowiedź z 27.09 („pogłębiony REVIEW jeśli Δ vs 20.09 nadal ≫ +0,02 albo vs 27.09 znów ~+0,02") — **nie spełniona**. Trzymamy nowe wagi.

---

## Pierwsze dni na nowych wagach (closeout, Fox = `PVEnergyTotal`)

| Dzień | Fox | ENS @05 | Błąd @05 | Peak 16:00 | Błąd peak |
|-------|----:|--------:|---------:|-----------:|----------:|
| 03.10 (stare wagi) | 30,3 | 26,60 | −12% | 27,99 | −8% |
| **04.10 (nowe wagi)** | **29,6** | **27,99** | **−5%** | 28,04 | −5% |

Jeden dzień — to nie jest dowód poprawy. Prognoza @05 na 05.10: **26,66 kWh** (w sobotę wieczorem było 16,4 — zmiana wynika z pogody, nie z wag) · 06.10: 21,3 kWh.

---

## Tydzień live 28.09–04.10 (prognoza @05 vs Fox)

Kryteria oceny: [`NOTATKA_GATE_L30_CLOSEOUT.md`](NOTATKA_GATE_L30_CLOSEOUT.md).

| Dzień | Fox | ENS @05 | Błąd |
|-------|----:|--------:|-----:|
| 28.09 | 31,8 | 27,6 | −13% |
| 29.09 | 32,7 | 27,1 | −17% |
| 30.09 | 31,6 | 27,2 | −14% |
| 01.10 | 19,1 | 14,4 | −25% |
| 02.10 | 31,3 | 26,8 | −14% |
| 03.10 | 30,3 | 26,6 | −12% |
| 04.10 | 29,6 | 28,0 | −5% |

WAPE **13,9%** · bias **−13,9%** (słoneczne dni −12,8%) · najgorszy dzień −25% · naiwna prognoza „jak wczoraj" WAPE 15,1% → ocena **ALARM w bias** (systematyczne niedoszacowanie słońca; WAPE sam w normie, ale ledwo lepszy od naiwnej).

---

## Co dalej

1. Primary **bez zmian** (RF16 + ENS) · CS4/XGB shadow.
2. Kolejny weekly: **2026-10-11 ~04:30** — porównać Δ z 0,671, dopisać L30 (2. punkt serii dla CS4/XGB, 3. dla RF16).
3. Obserwować bias słonecznych dni (4.10: −5%) — jeśli tydzień 05–11.10 nadal ma \|bias\| > 8% (dwa tygodnie z rzędu poza OK) → przegląd wg [`NOTATKA_GATE_L30_CLOSEOUT.md`](NOTATKA_GATE_L30_CLOSEOUT.md).

---

## Oś weekly (skrót)

| Data | RF16 Test MAE | CS4 | XGB+TS | Gate |
|------|--------------:|----:|-------:|------|
| 2026-09-13 | 0,666 | 0,659 | 0,644 | ACCEPT (Δ −0,020) |
| 2026-09-20 | 0,652 | 0,658 | 0,648 | ACCEPT (Δ −0,014) |
| 2026-09-27 | 0,677 | 0,673 | 0,645 | **REVIEW** (Δ +0,025) |
| **2026-10-04** | **0,671** | 0,673 | 0,646 | ACCEPT (Δ −0,006) |

Pełna historia: [`NOTATKA_RETRENINGI_I_WDROZENIA.md`](NOTATKA_RETRENINGI_I_WDROZENIA.md) · status: [`STATUS_ML_MLOPS.md`](STATUS_ML_MLOPS.md) · poprzedni: [`NOTATKA_WEEKLY_2026-09-27.md`](NOTATKA_WEEKLY_2026-09-27.md).
