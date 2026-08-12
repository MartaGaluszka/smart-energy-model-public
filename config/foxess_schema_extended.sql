-- Rozszerzenie bazy: wszystkie zmienne z FoxEss API (format long)

CREATE TABLE IF NOT EXISTS foxess_timeseries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    device_sn VARCHAR(50) NOT NULL,
    variable VARCHAR(80) NOT NULL,
    value REAL,
    unit VARCHAR(20),
    data_source VARCHAR(20) DEFAULT 'api',
    UNIQUE(timestamp, device_sn, variable)
);

CREATE INDEX IF NOT EXISTS idx_foxess_ts_time ON foxess_timeseries(timestamp);
CREATE INDEX IF NOT EXISTS idx_foxess_ts_var ON foxess_timeseries(variable);

CREATE TABLE IF NOT EXISTS foxess_device_meta (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_sn VARCHAR(50) NOT NULL UNIQUE,
    fetched_at DATETIME NOT NULL,
    device_type VARCHAR(50),
    status INTEGER,
    raw_json TEXT
);

CREATE TABLE IF NOT EXISTS foxess_report_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date DATE NOT NULL,
    device_sn VARCHAR(50) NOT NULL,
    variable VARCHAR(80) NOT NULL,
    hour_index INTEGER,
    value_kwh REAL,
    total_kwh REAL,
    UNIQUE(report_date, device_sn, variable, hour_index)
);

CREATE INDEX IF NOT EXISTS idx_foxess_report_date ON foxess_report_daily(report_date);
