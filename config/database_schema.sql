-- Smart Energy Model - Database Schema
-- Baza danych dla projektu optymalizacji magazynu energii

-- =============================================================================
-- TABELA 1: Dane z instalacji FoxEss (rzeczywiste pomiary)
-- =============================================================================
CREATE TABLE IF NOT EXISTS foxess_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    
    -- Produkcja fotowoltaiki
    pv_power_kw REAL,              -- Aktualna moc PV [kW]
    pv_energy_kwh REAL,            -- Energia wyprodukowana [kWh]
    pv_energy_daily_kwh REAL,      -- Suma dzienna [kWh]
    
    -- Stan baterii
    battery_soc_percent REAL,      -- Stan naładowania [%]
    battery_power_kw REAL,         -- Moc baterii (+ ładowanie, - rozładowanie) [kW]
    battery_energy_kwh REAL,       -- Energia w baterii [kWh]
    battery_temp_celsius REAL,     -- Temperatura baterii [°C]
    
    -- Zużycie energii
    load_power_kw REAL,            -- Aktualne zużycie [kW]
    load_energy_kwh REAL,          -- Energia zużyta [kWh]
    load_energy_daily_kwh REAL,    -- Suma dzienna zużycia [kWh]
    
    -- Energia z/do sieci
    grid_import_kwh REAL,          -- Energia pobrana z sieci [kWh]
    grid_export_kwh REAL,          -- Energia oddana do sieci [kWh]
    grid_power_kw REAL,            -- Moc z/do sieci [kW]
    
    -- Metadane
    device_sn VARCHAR(50),         -- Numer seryjny urządzenia
    data_source VARCHAR(20) DEFAULT 'csv',  -- Źródło danych (csv/api)
    
    UNIQUE(timestamp, device_sn)
);

CREATE INDEX idx_foxess_timestamp ON foxess_data(timestamp);
CREATE INDEX idx_foxess_date ON foxess_data(DATE(timestamp));

-- =============================================================================
-- TABELA 2: Cennik Tauron (taryfa G12w - strefa dzienna/nocna)
-- =============================================================================
CREATE TABLE IF NOT EXISTS tauron_tariff (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    valid_from DATE NOT NULL,
    valid_to DATE,
    tariff_name VARCHAR(20) DEFAULT 'G12w',
    
    -- Stawki NETTO [zł/kWh] — jak na fakturze Tauron (energia + dystrybucja osobno).
    -- Porównanie z fakturą: actual_energy_cost + actual_distribution_cost (netto)
    -- lub actual_total_cost (brutto). Moduł ROI nie dolicza VAT — stawki muszą być netto.
    price_zone1_day REAL NOT NULL,      -- Szczyt G12w: pon-pt 6-13, 15-22 (weekend/święto: brak)
    price_zone2_night REAL NOT NULL,    -- Pozaszczyt G12w: pon-pt 22-6, 13-15; weekend/święto: cała doba
    
    -- Opłaty dystrybucyjne NETTO [zł/kWh]
    distribution_zone1 REAL,
    distribution_zone2 REAL,
    
    -- Opłaty stałe NETTO [zł/mc]
    subscription_fee_monthly REAL,      -- Opłata abonamentowa [zł/mc]
    power_fee_monthly REAL,             -- Opłata mocowa [zł/mc]
    transition_fee_monthly REAL,        -- Opłata przejściowa [zł/mc]
    
    -- Opłaty OZE i inne
    oze_fee_kwh REAL,                   -- Opłata OZE [zł/kWh]
    cogenerative_fee_kwh REAL,          -- Opłata kogeneracyjna [zł/kWh]
    
    notes TEXT
);

-- UNIQUE na valid_from: chroni przed przypadkowym zdublowaniem wpisu dla tej samej daty przy
-- ręcznym imporcie (np. skrypt "placeholder" + późniejszy skrypt z prawdziwymi danymi z faktury
-- dla tego samego miesiąca) — bez tego oba wpisy współistnieją, a to, który "wygrywa" przy
-- rozliczeniu (`bill_simulator._load_global_tariff_windows`), zależy od nieokreślonej kolejności
-- SQL dla remisów. Patrz też: `EnergyDataImporter.import_tauron_tariff` (UPSERT po valid_from).
CREATE UNIQUE INDEX IF NOT EXISTS idx_tauron_tariff_valid_from ON tauron_tariff(valid_from);

-- =============================================================================
-- TABELA 3: Prognozy zużycia od Tauronu (baseline finansowy)
-- =============================================================================
CREATE TABLE IF NOT EXISTS tauron_forecast (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    forecast_date DATE NOT NULL,
    forecast_period VARCHAR(20),        -- np. '2024-01', 'Q1-2024'
    
    -- Prognozowane zużycie
    forecast_zone1_kwh REAL,           -- Prognoza strefa dzienna [kWh]
    forecast_zone2_kwh REAL,           -- Prognoza strefa nocna [kWh]
    forecast_total_kwh REAL,           -- Całkowite zużycie [kWh]
    
    -- Prognozowane koszty
    forecast_energy_cost REAL,         -- Koszt energii [zł]
    forecast_distribution_cost REAL,   -- Koszt dystrybucji [zł]
    forecast_fixed_costs REAL,         -- Opłaty stałe [zł]
    forecast_total_cost REAL,          -- Całkowity koszt [zł]
    
    -- Metadane
    source VARCHAR(50),                -- 'rachunek_tauron', 'symulacja'
    notes TEXT,
    
    UNIQUE(forecast_date, forecast_period)
);

-- =============================================================================
-- TABELA 4: Rzeczywiste rachunki od Tauronu (do porównania z prognozą)
-- =============================================================================
CREATE TABLE IF NOT EXISTS tauron_bills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_date DATE NOT NULL,
    billing_period_start DATE NOT NULL,
    billing_period_end DATE NOT NULL,
    
    -- Rzeczywiste zużycie
    actual_zone1_kwh REAL,
    actual_zone2_kwh REAL,
    actual_total_kwh REAL,
    
    -- Rzeczywiste koszty
    actual_energy_cost REAL,
    actual_distribution_cost REAL,
    actual_fixed_costs REAL,
    actual_total_cost REAL,
    
    -- Energia oddana do sieci (prosument)
    energy_exported_kwh REAL,
    energy_exported_value REAL,        -- Wartość oddanej energii [zł]
    
    bill_number VARCHAR(50) UNIQUE,
    pdf_path TEXT,                     -- Ścieżka do skanu rachunku
    
    UNIQUE(billing_period_start, billing_period_end)
);

-- =============================================================================
-- TABELA 5: Dane pogodowe (dla modelu ML - predykcja produkcji PV)
-- =============================================================================
CREATE TABLE IF NOT EXISTS weather_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    
    -- Parametry pogodowe
    temperature_celsius REAL,          -- Temperatura [°C]
    humidity_percent REAL,             -- Wilgotność [%]
    pressure_hpa REAL,                 -- Ciśnienie [hPa]
    
    -- Nasłonecznienie
    solar_radiation_wm2 REAL,          -- Promieniowanie słoneczne [W/m²]
    sunshine_duration_min REAL,        -- Czas nasłonecznienia [min]
    cloud_cover_percent REAL,          -- Zachmurzenie [%]
    cloud_cover_low_percent REAL,      -- Chmury niskie [%] — proxy mgły
    cloud_cover_mid_percent REAL,
    cloud_cover_high_percent REAL,
    visibility_m REAL,                 -- Widoczność [m]; niska = mgła (prognoza)
    
    -- Wiatr i opady
    wind_speed_ms REAL,                -- Prędkość wiatru [m/s]
    wind_direction_deg REAL,           -- Kierunek wiatru [°]
    precipitation_mm REAL,             -- Opady [mm]
    snowfall_cm REAL,                  -- Opady śniegu (godz. suma) [cm], Open-Meteo
    snow_depth_m REAL,                 -- Grubość pokrywy [m], Open-Meteo (model)
    
    -- Metadane
    location VARCHAR(100),             -- Lokalizacja stacji pomiarowej
    data_source VARCHAR(50),           -- np. 'IMGW', 'OpenWeatherMap'
    
    UNIQUE(timestamp, location)
);

CREATE INDEX idx_weather_timestamp ON weather_data(timestamp);

-- =============================================================================
-- TABELA 5a: Notatki pogodowe z zewnątrz (np. AccuWeather ręcznie)
-- =============================================================================
CREATE TABLE IF NOT EXISTS weather_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    note_day TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    source TEXT NOT NULL,
    note_kind TEXT NOT NULL DEFAULT 'daily_summary',
    cloud_cover_pct REAL,
    uv_index REAL,
    brightness_index REAL,
    wind_dir TEXT,
    wind_kmh REAL,
    wind_gust_kmh REAL,
    precip_prob_pct REAL,
    thunder_prob_pct REAL,
    precip_mm REAL,
    rain_mm REAL,
    precip_duration_h REAL,
    rain_duration_h REAL,
    note_text TEXT,
    UNIQUE(note_day, source, note_kind, recorded_at)
);

-- =============================================================================
-- TABELA 5b: IMGW dobowe (stacja klimat — pokrywa śnieżna, opady)
-- =============================================================================
CREATE TABLE IF NOT EXISTS imgw_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day DATE NOT NULL,
    station_code VARCHAR(20) NOT NULL,
    station_name VARCHAR(100),
    station_lat REAL,
    station_lon REAL,
    distance_km REAL,
    temp_mean_c REAL,
    temp_min_c REAL,
    temp_max_c REAL,
    precip_mm REAL,
    snow_depth_cm REAL,
    snow_depth_status VARCHAR(5),
    data_source VARCHAR(50) DEFAULT 'IMGW-klimat',
    UNIQUE(day, station_code)
);

CREATE INDEX idx_imgw_daily_day ON imgw_daily(day);

-- =============================================================================
-- TABELA 5b: Odczyty licznika (portal Tauron / licznik — kupione vs oddane kWh)
-- Uzupełnia luki FoxESS (np. V 2025). Bez PPE, numeru licznika, adresu.
-- =============================================================================
CREATE TABLE IF NOT EXISTS meter_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    import_kwh REAL,                   -- Energia kupiona z sieci (pobór) [kWh]
    export_kwh REAL,                   -- Energia oddana do sieci [kWh]
    import_zone1_kwh REAL,             -- Opcjonalnie: szczyt
    import_zone2_kwh REAL,             -- Opcjonalnie: pozaszczyt
    export_zone1_kwh REAL,
    export_zone2_kwh REAL,
    source VARCHAR(50) DEFAULT 'licznik_tauron',
    notes TEXT,
    UNIQUE(period_start, period_end, source)
);

CREATE INDEX idx_meter_period ON meter_readings(period_start);

-- =============================================================================
-- TABELA 5c: Godzinowe odczyty licznika (eksport CSV portalu Tauron)
-- =============================================================================
CREATE TABLE IF NOT EXISTS meter_hourly (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    zone VARCHAR(2) NOT NULL,          -- T1 (szczyt), T2 (pozaszczyt)
    flow VARCHAR(10) NOT NULL,         -- import (pobór) / export (oddanie)
    kwh REAL NOT NULL,
    source VARCHAR(50) DEFAULT 'licznik_tauron_csv',
    UNIQUE(timestamp, zone, flow, source)
);

CREATE INDEX idx_meter_hourly_ts ON meter_hourly(timestamp);

-- =============================================================================
-- TABELA 5d: Rynkowa Cena Energii (RCE) — PSE, net-billing prosument
-- =============================================================================
CREATE TABLE IF NOT EXISTS rce_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    period_label VARCHAR(20),
    business_date DATE NOT NULL,
    rce_pln_mwh REAL NOT NULL,
    rce_pln_kwh REAL NOT NULL,
    source VARCHAR(50) DEFAULT 'pse_api',
    UNIQUE(timestamp, source)
);

CREATE INDEX idx_rce_business_date ON rce_prices(business_date);
CREATE INDEX idx_rce_timestamp ON rce_prices(timestamp);

-- =============================================================================
-- TABELA 5e: RCEm — rynkowa miesięczna cena energii (PSE)
-- =============================================================================
CREATE TABLE IF NOT EXISTS rcem_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_month VARCHAR(7) NOT NULL,
    rce_pln_mwh REAL NOT NULL,
    rce_pln_kwh REAL NOT NULL,
    corrected_rce_pln_mwh REAL,
    corrected_rce_pln_kwh REAL,
    publication_date DATE,
    source VARCHAR(50) DEFAULT 'pse_seed',
    notes TEXT,
    UNIQUE(period_month, source)
);

CREATE INDEX idx_rcem_period ON rcem_prices(period_month);

-- =============================================================================
-- TABELA 6: Predykcje modelu ML
-- =============================================================================
CREATE TABLE IF NOT EXISTS ml_predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_timestamp DATETIME NOT NULL,
    forecast_for_timestamp DATETIME NOT NULL,
    
    -- Predykcje
    predicted_pv_kwh REAL,             -- Prognozowana produkcja PV [kWh]
    predicted_load_kwh REAL,           -- Prognozowane zużycie [kWh]
    
    -- Confidence intervals
    prediction_confidence REAL,        -- Pewność predykcji [0-1]
    
    -- Model info
    model_name VARCHAR(50),            -- np. 'XGBoost_v1.0'
    model_version VARCHAR(20),
    
    UNIQUE(forecast_for_timestamp, model_name, model_version)
);

-- =============================================================================
-- TABELA 7: Rekomendacje optymalizacji (algorytm sterowania baterią)
-- =============================================================================
CREATE TABLE IF NOT EXISTS optimization_recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    
    -- Rekomendacje
    recommended_action VARCHAR(20),     -- 'charge', 'discharge', 'hold'
    recommended_power_kw REAL,          -- Zalecana moc [kW]
    target_soc_percent REAL,            -- Docelowy SOC [%]
    
    -- Uzasadnienie
    reason TEXT,                        -- Dlaczego taka decyzja
    expected_savings_pln REAL,          -- Oczekiwane oszczędności [zł]
    
    -- Status wykonania
    was_executed BOOLEAN DEFAULT 0,
    actual_savings_pln REAL,
    
    UNIQUE(timestamp)
);

-- =============================================================================
-- TABELA 8: Analiza ROI (porównanie baseline vs optymalizacja)
-- =============================================================================
CREATE TABLE IF NOT EXISTS roi_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_date DATE NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    
    -- Scenariusz baseline (bez optymalizacji, wg prognozy Tauron)
    baseline_cost_pln REAL,            -- Koszt według prognozy Tauron [zł]
    
    -- Scenariusz rzeczywisty (z optymalizacją)
    actual_cost_pln REAL,              -- Rzeczywisty koszt [zł]
    
    -- Oszczędności
    savings_pln REAL,                  -- Oszczędności [zł]
    savings_percent REAL,              -- Oszczędności [%]
    
    -- Metryki
    self_consumption_rate REAL,        -- Współczynnik autokonsumpcji [%]
    energy_exported_kwh REAL,          -- Energia oddana do sieci [kWh]
    energy_imported_kwh REAL,          -- Energia pobrana z sieci [kWh]
    
    notes TEXT,
    
    UNIQUE(period_start, period_end)
);

-- =============================================================================
-- WIDOKI (Views) - Dla łatwiejszych zapytań
-- =============================================================================

-- Widok: Dzienne podsumowanie energii
CREATE VIEW IF NOT EXISTS daily_energy_summary AS
SELECT 
    DATE(timestamp) as date,
    device_sn,
    SUM(pv_energy_kwh) as total_pv_kwh,
    SUM(load_energy_kwh) as total_load_kwh,
    SUM(grid_import_kwh) as total_import_kwh,
    SUM(grid_export_kwh) as total_export_kwh,
    AVG(battery_soc_percent) as avg_battery_soc,
    MAX(battery_soc_percent) as max_battery_soc,
    MIN(battery_soc_percent) as min_battery_soc
FROM foxess_data
GROUP BY DATE(timestamp), device_sn;

-- Widok: Porównanie prognoza vs rzeczywistość
CREATE VIEW IF NOT EXISTS forecast_vs_actual AS
SELECT 
    tf.forecast_date,
    tf.forecast_total_kwh,
    tf.forecast_total_cost,
    tb.actual_total_kwh,
    tb.actual_total_cost,
    (tb.actual_total_cost - tf.forecast_total_cost) as cost_difference,
    ((tb.actual_total_cost - tf.forecast_total_cost) / tf.forecast_total_cost * 100) as cost_difference_percent
FROM tauron_forecast tf
LEFT JOIN tauron_bills tb 
    ON DATE(tf.forecast_date) = DATE(tb.bill_date);

-- =============================================================================
-- Początkowe dane - przykładowy cennik Tauron G12w (2026)
-- =============================================================================
INSERT INTO tauron_tariff (
    valid_from, 
    tariff_name, 
    price_zone1_day, 
    price_zone2_night,
    distribution_zone1,
    distribution_zone2,
    subscription_fee_monthly,
    oze_fee_kwh,
    notes
) VALUES (
    '2026-01-01',
    'G12w',
    0.85,  -- PLACEHOLDER netto — zastąp stawkami z faktury (np. 0,505 energia + dystrybucja)
    0.45,  -- PLACEHOLDER netto
    0.25,  -- PLACEHOLDER netto dystrybucja szczyt
    0.15,  -- PLACEHOLDER netto dystrybucja pozaszczyt
    25.00, -- PLACEHOLDER netto abonament
    0.02,  -- PLACEHOLDER netto OZE
    'PLACEHOLDER netto — użyj scripts/add_tauron_rozliczenie_*.py z prawdziwymi stawkami'
);
