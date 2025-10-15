-- SQLite Schema for Bike Sharing Data Platform
-- Designed for Spark ETL integration
-- Timezone convention: events_hourly uses America/Chicago local time (Divvy - Chicago bike-share)

-- ============================================================================
-- 1) STATION - Station catalog (derived from trip data)
-- ============================================================================
CREATE TABLE IF NOT EXISTS station (
    id TEXT PRIMARY KEY,                -- Station identifier (from trip CSVs)
    name TEXT NOT NULL,                 -- Station name
    lat REAL,                           -- Latitude (optional)
    lon REAL,                           -- Longitude (optional)
    capacity INTEGER,                   -- Total docking capacity (nullable)
    is_active INTEGER DEFAULT 1,        -- 0 = inactive, 1 = active
    created_at_utc TEXT NOT NULL        -- ISO-8601 timestamp when first seen
);

CREATE INDEX IF NOT EXISTS idx_station_active ON station(is_active);

-- ============================================================================
-- 2) EVENTS_HOURLY - Hourly net deltas per station (Spark batch output)
-- ============================================================================
CREATE TABLE IF NOT EXISTS events_hourly (
    hour TEXT NOT NULL,                 -- Local Chicago time, format: 'YYYY-MM-DD HH:00:00'
    station_id TEXT NOT NULL,           -- FK to station.id
    delta_total INTEGER NOT NULL,       -- Net change: +1 per arrival, -1 per departure
    delta_ebike INTEGER DEFAULT 0,      -- Net change for ebikes only
    delta_other INTEGER DEFAULT 0,      -- Net change for classic/other bikes
    PRIMARY KEY (hour, station_id),
    FOREIGN KEY (station_id) REFERENCES station(id) ON DELETE CASCADE
);

-- Speed up cumulative sums and station filtering
CREATE INDEX IF NOT EXISTS idx_events_station_hour ON events_hourly(station_id, hour);
CREATE INDEX IF NOT EXISTS idx_events_hour ON events_hourly(hour);
