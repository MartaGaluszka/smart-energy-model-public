# Go-live — Accu → CS4 w prognozie i baterii (od 01.11.2026)

**Decyzja:** zostawiamy **CS4** operacyjnie przy Accu pochmurny/ciemny (Lumen **1–4** + cloud/opad); **ensemble** = audit + launchd.  
**Kod:** `src/weather/accu_regime.py`, `forecast_routing.py` · API `/forecast/hourly` · `ACCU_CS4_UI=1`

---

## Checklist wieczór 31.10 / rano 01.11

| # | Akcja | Status |
|---|--------|--------|
| 1 | `.env`: `ACCU_CS4_UI=1`, `ENSEMBLE_PRIMARY=1`, `FORECAST_CS4_ENABLED=1` | sprawdź |
| 2 | Model `models/pv_hourly_model_cs4.joblib` istnieje | `./mlops/train_dual_weekly.sh` w niedzielę |
| 3 | **Przeładuj API** z nowym kodem i `.env`: `docker compose up -d --build api` | wymagane po deploy |
| 4 | Smoke: `./mlops/smoke_accu_cs4_routing.sh` → CS4 dla `2026-11-01` | |
| 5 | Accu w DB na **01.11** (Lumen + cloud + mm) — już `#272` | każdy dzień outlooku |
| 6 | Mobile: rebuild / odśwież WebView (Prognoza — baner CS4) | |
| 7 | Launchd **05:00** bez zmian — CS4 shadow `daily_cs4` i tak leci | |
| 8 | Niedziela **02.11** weekly: notatka **CS4 + train** — **bez L30** ([`NOTATKA_WEEKLY_2026-11-02.md`](NOTATKA_WEEKLY_2026-11-02.md)) | |

**Kill switch:** `ACCU_CS4_UI=0` + restart API → sam ensemble w apce.

---

## Co użytkownik widzi (01.11 przykład)

- Accu **Lumen 2**, **89%** → reżim **pochmurny**, etykieta operacyjna **ciemny** (nie „B. jasne” z kalendarza Accu).
- Prognoza: suma **CS4**, linia **Ensemble (audit)**.
- Bateria: PV jutro/dziś z **CS4** (`get_day_pv_forecast_sum`).

---

## Paper / closeout

- Launchd primary = **ENS** w CSV (bez zmian).
- Paper-trade: nadal log Accu→pick; porównuj Fox vs **CS4 display** vs ENS w closeout.

Powiązane: [`NOTATKA_DECYZJA_CS4_XI_2026.md`](NOTATKA_DECYZJA_CS4_XI_2026.md) (uzasadnienie) · [`NOTATKA_GATE_ACCU_CS4_UI.md`](NOTATKA_GATE_ACCU_CS4_UI.md) · [`NOTATKA_2026-10-31.md`](NOTATKA_2026-10-31.md)
