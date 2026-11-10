# Dane demo (izolowane od produkcji)

Generator tworzy **`data/demo.db`**. Nie zapisuje do `energy_model.db` (twarda blokada w skrypcie).

```bash
PYTHONPATH=$PWD ./venv/bin/python scripts/demo/make_demo_db.py
```

Uruchomienie API **tylko** na demo (bez zmiany produkcyjnego `.env`):

```bash
DATABASE_PATH=data/demo.db FOXESS_SYNC_DISABLED=1 \
  ./venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Konto demo (takie same jak w aplikacji): `mobile.demo@example.com` / `demo12345678`.

`data/demo.db` jest w `.gitignore` — w repo jest skrypt, nie plik bazy. Każda osoba generuje lokalnie (seed=42 → te same dane).
