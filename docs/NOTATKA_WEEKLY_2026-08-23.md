# Notatka weekly — retrening 23.08.2026

**Data / godzina:** 2026-08-23 ~04:30 (`train_dual_weekly.sh` / launchd)  
**Typ:** cotygodniowe odświeżenie wag — **bez zmiany logiki / primary**  
**Okno treningu:** 2025-06-01 → **2026-08-22** (expanding)  
**Log:** `logs/train.log` · daily 05:00 już na nowych artefaktach

---

## Werdykt (1 zdanie)

> Weekly **OK** · gate RF16 vs 16.08: Δ Test MAE **+0.015** (≤ +0.02) → **ACCEPT** · primary zostaje **RF 16 + ICON** · CS4 / XGB+TS nadal shadow.

---

## Metryki offline (po train)

| Model | Rola | Cechy | Test MAE | Gap | Daily MAE | Werdykt |
|-------|------|------:|---------:|----:|----------:|---------|
| **RF 16** | **primary** | 16 | **0.658** | 0.069 | 3.67 | nie przeuczony |
| CS4 | shadow | 19 | 0.664 | 0.075 | 3.75 | nie przeuczony |
| XGB+TS | shadow | 24 | 0.618 | 0.064 | 3.40 | nie przeuczony |

Artefakty (mtime ~04:31–04:32):

- `models/pv_hourly_model.joblib` (+ `.metadata.json`)
- `models/pv_hourly_model_cs4.joblib`
- `models/pv_hourly_model_xgb_ts.joblib`

---

## Gate vs poprzedni weekly (16.08)

| | 16.08 | **23.08** | Δ |
|--|------:|----------:|--:|
| RF16 Test MAE | 0.643 | **0.658** | **+0.015** |
| Protokół | — | remis ≤ +0.02 | **ACCEPT** |

Bez podmiany primary / bez nowych cech / bez UKMO w prod / bez routingu RF↔CS4.

---

## Kontekst live (przed / wokół tego weekly)

Walidacja closeoutów z pełnymi predicte **w dniu weekly** (do **22.08**; wykresy wtedy **23.08**):

| Okres | n | MAPE raw 5:00 | MAPE raw 12:00 |
|-------|--:|-------------:|---------------:|
| Era dual 27.07–22.08 | 27 | **10,2%** | **9,4%** |
| Całość 14.07–22.08 | 40 | 15,1% | 13,3% |

CS4 daily ~**10,5%** (n=27), lepszy **9/27**.

**Aktualizacja 25.08** (po closeoutach **23–24.08**): wykresy + [`july_validation_summary.md`](images/ml/july_validation_summary.md) do **24.08** — era dual **27.07–24.08** n=29 · MAPE **11,0% / 10,0%**; całość n=42 · **15,4% / 13,5%**; CS4 ~**11,4%** (9/29). Jasne undershoot **23–24** podbiły MAPE. → [`STATUS_ML_MLOPS.md`](STATUS_ML_MLOPS.md).

**22.08:** formalny closeout po backfillu same-day (runy 05/12/16 z D+1 z 21.08) — actual **25,1** · daily RF **−9,6%** · midday **+4,9%** · best peak / `midday_xgb_ts` ≈25,2.

**21.08:** actual **13,4** · poranny RF **+32,9%** (mokry) · best `peak`.

**23.08 05:00** (nowe wagi): RF ~**28,5** · CS4 ~**28,0** · XGB ~**28,8** kWh.

---

## Pogoda wokół weekly (skrót)

| Dzień | Skrót | PV / obserwacja |
|-------|--------|-----------------|
| **20.08** | front ~17:09 | actual **27,4** · best `peak_cs4` |
| **21.08** | mokry + przejaśnienia PM | actual **13,4** · overshoot raw 5:00 |
| **22.08** | Accu jasność **6** / wiatr (nie 9) | actual **25,1** · oneshot ~24 |
| **23.08** | Accu outlook jasność **9** | daily ~28–29 — ryzyko zaniżenia przy bardzo jasnym dniu |

Szerszy opis: [`NOTATKA_POGODA_2026-08-15.md`](NOTATKA_POGODA_2026-08-15.md) · [`NOTATKA_2026-08-22.md`](NOTATKA_2026-08-22.md).

---

## Co dalej

1. Nic nie zmieniać w launchd / primary.  
2. Closeout **23.08** na nowych wagach (jasny dzień — sprawdzić undershoot).  
3. Kolejny weekly: **niedziela 30.08 ~04:30**.  
4. Paper-trade reguły RF/CS4 (pochmurne) — po limicie / prywatny tor; nie w tym weekly.  
5. Wykresy walidacji: **zrobione 25.08** do closeoutów **24.08** (era dual MAPE **11,0% / 10,0%**, n=29).

---

## Oś weekly (skrót)

| Data | RF16 Test MAE | CS4 | XGB+TS | Gate |
|------|--------------:|----:|-------:|------|
| 2026-08-02 | (w erze dual) | — | — | odświeżenie wag |
| **2026-08-09** | **0.624** | 0.632 | 0.608 | ACCEPT |
| **2026-08-16** | **0.643** | 0.637 | 0.626 | ACCEPT (Δ +0.019) |
| **2026-08-23** | **0.658** | 0.664 | 0.618 | **ACCEPT** (Δ +0.015) |

Pełna historia wdrożeń: [`NOTATKA_RETRENINGI_LIPIEC_2026.md`](NOTATKA_RETRENINGI_LIPIEC_2026.md) · status: [`STATUS_ML_MLOPS.md`](STATUS_ML_MLOPS.md).
