# Workflow — live AGD / SoC

**Zasada:** fakty AGD **tylko w `household_events`** (`note`: start · program · nakładki). Notatka dnia **bez** tabeli prania/obiadu i **bez** kroków gotowania.

| Plik | Co wpisujesz |
|------|----------------|
| **`household_events`** | typ · start · koniec/program · nakładki (1 linia) |
| **`NOTATKA_YYYY-MM-DD.md`** | pogoda · **decyzje** · checklist · Fox **tylko po sync**, gdy kalibracja |
| **`NOTATKA_BATERIA_SOC_LOG.md`** | SoC **@8 / 11 / 14 / 17 / 22** · werdykt dnia |

**Nie pisz:** SoC co kilka min · ten sam AGD w notatce i logu · pełne opisy posiłków.

**Wyjątek (1–2 zdania w notatce dnia):** regresja Fox, nowy profil mocy (chleb vs piekarnik).

Przykład `note` w DB:

```text
#2 · 13:10 · 2h → ~15:10 · równolegle: suszarka (13:06), chleb
```

§10.1: [`PROJEKT_APLIKACJA_MOBILNA.md`](PROJEKT_APLIKACJA_MOBILNA.md)
