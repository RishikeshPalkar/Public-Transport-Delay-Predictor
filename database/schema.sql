-- Create Stations Table
CREATE TABLE IF NOT EXISTS stations (
    uic_code VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    latitude DOUBLE,
    longitude DOUBLE,
    canton VARCHAR(10)
);

-- Create Weather Observations Table
CREATE TABLE IF NOT EXISTS weather_observations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    station_uic VARCHAR(20) NOT NULL,
    observation_time DATETIME NOT NULL,
    temperature_c FLOAT,
    precipitation_mm FLOAT,
    snow_depth_cm FLOAT,
    weather_code INT,
    FOREIGN KEY (station_uic) REFERENCES stations(uic_code) ON DELETE CASCADE,
    UNIQUE KEY uq_station_time (station_uic, observation_time)
);

-- Create Trips Table (SBB Ist-Daten parsed)
CREATE TABLE IF NOT EXISTS trips (
    id INT AUTO_INCREMENT PRIMARY KEY,
    betriebstag DATE NOT NULL,
    fahrt_bezeichner VARCHAR(100) NOT NULL,
    produkt_id VARCHAR(20),
    linien_text VARCHAR(50),
    station_uic VARCHAR(20) NOT NULL,
    station_name VARCHAR(100) NOT NULL,
    scheduled_arrival DATETIME,
    actual_arrival DATETIME,
    arrival_delay_min FLOAT,
    scheduled_departure DATETIME,
    actual_departure DATETIME,
    departure_delay_min FLOAT,
    faellt_aus BOOLEAN DEFAULT FALSE,
    zusatzfahrt BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (station_uic) REFERENCES stations(uic_code) ON DELETE CASCADE,
    UNIQUE KEY uq_trip_stop (betriebstag, fahrt_bezeichner, station_uic)
);

-- Indices for performance on predictions and lookups
CREATE INDEX idx_trips_betriebstag ON trips(betriebstag);
CREATE INDEX idx_trips_station_uic ON trips(station_uic);
CREATE INDEX idx_trips_linien_text ON trips(linien_text);
CREATE INDEX idx_weather_station_time ON weather_observations(station_uic, observation_time);
