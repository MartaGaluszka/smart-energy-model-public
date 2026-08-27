# Reguła apki — nocne FC 22–6 (B2 T×PV + lato cap)

**Status:** wdrożone (advise-only) · **B2 2026-08-27** (Tśr + PV + 30 min ≈ 50% + próg cyklu)  
**Typ powiadomienia:** `charge_tonight_cloudy`  
**Gdzie:** `src/optimization/battery_advisor.py` · `api/services/notifications_service.py` · peak 16:00 · karta Home

---

## Reguła (produkt)

**Zima / jesień od 15.09 (B2):**

```text
JEŚLI  dzień roboczy (pn–pt, nie święto)
  ORAZ  godzina < 22:00
TO  cel SoC z tabeli Tśr jutro × PV jutro (PLAN_BATERIA §C)
     minuty = ΔSoC × 30/50   (30 min ≈ +50 pp, fakt 25–26.08)
     JEŚLI ΔSoC < 15 pp LUB energia < 2 kWh  (i SoC ≥ rezerwa, nie mróz)
       → POMIŃ (cykl LFP vs spread G12w ~0,36 zł/kWh)
     INACZEJ ładuj od 22:00 do celu (nie z drogiego szczytu)
```

| Tśr jutro | PV jutro | Cel SoC |
|-----------|----------|--------:|
| < 0°C | dowolne | 95% |
| 0–5°C | < 12 kWh | 95% |
| 0–5°C | ≥ 12 kWh | nie pełnić (rezerwa) |
| ≥ 5°C | < 8 kWh | 80% |
| ≥ 5°C | ≥ 12 kWh | nie pełnić / jak lato |

Bez T: PV < 12 kWh → 90%, inaczej pomiń.

**Lato (do ~14.09) — po 25–26.08:**

```text
JEŚLI  dzień roboczy
  ORAZ  godzina < 22:00
  ORAZ  SoC < BATTERY_SOC_RESERVE_SUMMER   (20%)
  ORAZ  prognoza PV jutro ≤ BATTERY_SUMMER_TOMORROW_MAX_KWH  (10 kWh)
TO
  krótki FC: max 15 min / +25 pp SoC — NIE do 75%
  jutro do 10 kWh NIE spina pełnego ładowania; jutro > 10 kWh → poczekaj na dach
```

**Case 25–26.08:** SoC 24% + jutro RF ~12 kWh → stara reguła TAK, **ex post niepotrzebne** (26.08 ~21 kWh, pełna od 12:38). Nowa reguła lata przy 24% → **NIE**. 30 min FC = +50 pp SoC (kalibracja mocy).  
**Log:** [`NOTATKA_BATERIA_SOC_LOG.md`](NOTATKA_BATERIA_SOC_LOG.md) (FC 22:00–22:30: 24→75%; za agresywny).

---

## Progi (`.env`)

| Zmienna | Domyślnie | Sens |
|---------|----------:|------|
| `BATTERY_SOC_RESERVE_SUMMER` | **20** | nocna podłoga lata |
| `BATTERY_SUMMER_FC_MAX_MINUTES` | **15** | cap czasu FC |
| `BATTERY_SUMMER_FC_DELTA_SOC` | **25** | cap przyrostu SoC (~15 min) |
| `BATTERY_SUMMER_TOMORROW_MAX_KWH` | **10** | jutro do 10 kWh = nadal lato |
| `BATTERY_B2_PV_SKIP_KWH` | **12** | dach pokrywa szczyt (jesień/łagodna zima) |
| `BATTERY_B2_MILD_WEAK_PV_KWH` | **8** | T ≥ 5°C, słaby dach → cel 80% |
| `BATTERY_FC_MINUTES_PER_50_SOC` | **30** | 30 min ≈ +50 pp |
| `BATTERY_FC_MIN_WORTH_KWH` | **2** | poniżej — nie warto vs cykl |
| `BATTERY_FC_MIN_DELTA_SOC` | **15** | poniżej — za krótki impuls |
| `BATTERY_TARIFF_SPREAD_PLN_PER_KWH` | **0,36** | G12w droga−tania (szacunek) |
| `BATTERY_CYCLE_COST_PLN_PER_KWH` | **0,30** | zużycie LFP na 1 kWh throughput |

---

## Gdzie widać

1. **`GET /api/v1/battery/night-charge-advice`** (kontekst peak / po 15) — recommendation `ŁADUJ OD 22:00 (B2 T+PV)`.
2. **`GET /api/v1/notifications`** — upsert jednej sugestii na dzień (`charge_tonight_cloudy`).
3. **`GET /api/v1/battery/suggestion`** — etykieta ForceCharge 22–6 (minuty / pomiń cykl).
4. Job **`peak_arrival` 16:00** → `battery_advisor_report.py --context peak` (log CSV).

Push FCM (T4.22) — później; na razie feed in-app.

---

## Czego NIE robi

- Nie wysyła komend do FoxESS (§9.6).
- Nie spina w weekend / święto (cała doba i tak tania G12w).
- Po 22:00 nie powtarza „ładuj od 22” (okno już trwa).
- Nie pełnią baterii, gdy brakuje < ~2 kWh / < 15 pp SoC (żywotność > spread).
