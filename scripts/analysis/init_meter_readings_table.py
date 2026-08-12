"""
Tworzy tabelę meter_readings w istniejącej bazie (migracja).

Uruchomienie:
    source venv/bin/activate
    python scripts/init_meter_readings_table.py
"""

import os
import sqlite3

DB_PATH = os.getenv('DATABASE_PATH', 'data/energy_model.db')

DDL = '''
CREATE TABLE IF NOT EXISTS meter_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    import_kwh REAL,
    export_kwh REAL,
    import_zone1_kwh REAL,
    import_zone2_kwh REAL,
    export_zone1_kwh REAL,
    export_zone2_kwh REAL,
    source VARCHAR(50) DEFAULT 'licznik_tauron',
    notes TEXT,
    UNIQUE(period_start, period_end, source)
);
CREATE INDEX IF NOT EXISTS idx_meter_period ON meter_readings(period_start);
'''


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(DDL)
    conn.commit()
    n = conn.execute('SELECT COUNT(*) FROM meter_readings').fetchone()[0]
    conn.close()
    print(f'✅ Tabela meter_readings gotowa ({n} rekordów)')


if __name__ == '__main__':
    main()
