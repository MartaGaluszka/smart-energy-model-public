# Reguła apki — niski SoC + pochmurny jutro → ładuj od 22:00

**Status:** wdrożone w kodzie (advise-only) · **2026-08-25**  
**Typ powiadomienia:** `charge_tonight_cloudy`  
**Gdzie:** `src/optimization/battery_advisor.py` · `api/services/notifications_service.py` · peak 16:00

---

## Reguła (produkt)

```text
JEŚLI  dzień roboczy (pn–pt, nie święto)
  ORAZ  godzina < 22:00
  ORAZ  SoC < BATTERY_SOC_CHARGE_TONIGHT_BELOW   (domyślnie 50%)
  ORAZ  prognoza PV jutro (suma dnia) < BATTERY_CLOUDY_DAY_PV_KWH  (domyślnie 18 kWh)
TO
  komunikat: „Zalecane ładowanie baterii od 22:00” (G12w tanio)
  ton: sugestia doradcza — BEZ automatyki / ForceCharge
```

**Case 25–26.08:** SoC wieczór ~24–43%, jutro ~11–14 kWh → reguła **TAK**.  
**Log pomiarów SoC:** [`NOTATKA_BATERIA_SOC_LOG.md`](NOTATKA_BATERIA_SOC_LOG.md) (ForceCharge 22:00–22:30: 24→75%; AGD −15%; rano 61%→74% @10:55).

---

## Progi (`.env`)

| Zmienna | Domyślnie | Sens |
|---------|----------:|------|
| `BATTERY_SOC_CHARGE_TONIGHT_BELOW` | **50** (fallback = `BATTERY_SOC_MIN_EVENING`) | „słaba bateria” wieczorem |
| `BATTERY_CLOUDY_DAY_PV_KWH` | **18** | dzień jak dziś/jutro (~11–14) vs jasny (~30+) |

---

## Gdzie widać

1. **`GET /api/v1/battery/night-charge-advice`** (kontekst peak / po 15) — recommendation `ŁADUJ OD 22:00 (POCHMURNO + NISKI SOC)`.
2. **`GET /api/v1/notifications`** — upsert jednej sugestii na dzień (`charge_tonight_cloudy`).
3. Job **`peak_arrival` 16:00** → `battery_advisor_report.py --context peak` (log CSV).

Push FCM (T4.22) — później; na razie feed in-app.

---

## Czego NIE robi

- Nie wysyła komend do FoxESS (§9.6).
- Nie spina w weekend / święto (cała doba i tak tania G12w).
- Po 22:00 nie powtarza „ładuj od 22” (okno już trwa).
