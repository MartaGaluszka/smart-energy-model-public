# Project status — przekierowanie

**Aktualne liczby modelu i closeoutów** nie są już utrzymywane w tym pliku (unikamy trzech sprzecznych tabel).

| Potrzebujesz | Idź do |
|--------------|--------|
| Snapshot ML / MLOps / MAPE live | [`docs/STATUS_ML_MLOPS.md`](docs/STATUS_ML_MLOPS.md) |
| Cel repo, FoxESS, app HOW TO | [`README.md`](README.md) |
| Decyzje (PVE, ICON, 16 cech) | [`docs/03_ZALOZENIA_I_DECYZJE.md`](docs/03_ZALOZENIA_I_DECYZJE.md) |
| Metoda ML, ablacja | [`docs/02_ML_predykcja_PV.md`](docs/02_ML_predykcja_PV.md) |
| Data quality | [`docs/01_EDA_analiza.md`](docs/01_EDA_analiza.md) |
| Joby launchd | [`mlops/README.md`](mlops/README.md) |
| Historia gate’ów | [`docs/CHANGELOG_ML.md`](docs/CHANGELOG_ML.md) |
| App mobilna | [`docs/PROJEKT_APLIKACJA_MOBILNA.md`](docs/PROJEKT_APLIKACJA_MOBILNA.md) |

### Stan skrótowy (bez metryk)

- **Primary:** RF 16 · PVE · ICON · GPS dach  
- **Shadow:** CS4 + XGB+TS (launchd)  
- **MLOps host:** SQLite + `mlops/` + launchd  
- **App:** Docker Postgres + FastAPI (`api/`) + Ionic (`mobile/`)  
- **ADJUST:** OFF · ocena na raw  

### Backlog (wysoki poziom)

- [ ] Screenshoty app w `docs/images/app/` (README §6)  
- [ ] Plan baterii jesień/zima — [`docs/PLAN_BATERIA_JESIEN_ZIMA_2026.md`](docs/PLAN_BATERIA_JESIEN_ZIMA_2026.md)  
- [ ] Obrona — sierpień 2026  

*Przekierowanie od 2026-08-05 · stary długi dump statusu zastąpiony hubem.*
