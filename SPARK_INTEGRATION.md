# Spark Integration Guide

This document provides guidance for the Spark developer (Sebi) on how to integrate with the SQLite database layer.

## Overview

The SQLite database is pre-configured with two main tables:
1. **`station`** - Station catalog
2. **`events_hourly`** - Hourly deltas per station (YOUR PRIMARY OUTPUT)

## Database Location

- **Development**: `data/app.db` (relative to project root)
- **Docker**: `/data/app.db` (shared volume)

## Your Responsibilities (Spark ETL)

### 1. Process Trip Histories → `events_hourly`

**Input**: Monthly CSV files with trip data

**Output**: Hourly aggregated deltas per station

**Key Requirements**:
- **Timezone**: Convert all timestamps to `America/Chicago` (Central Time) and floor to the hour
- **Format**: Hour string as `'YYYY-MM-DD HH:00:00'` (e.g., `'2025-07-15 14:00:00'`)
- **Deltas**: 
  - `delta_total`: +1 for trip end, -1 for trip start
  - `delta_ebike`: Same but only for ebikes
  - `delta_other`: Same but only for classic/other bikes

#### Code Example (Python + Spark)

```python
from database.connection import DatabaseConnection
from database.repositories import EventsHourlyRepository
from config.database import DB_PATH

# After your Spark aggregation produces a list of events
events_data = [
    {
        'hour': '2025-07-15 14:00:00',
        'station_id': 'CHI00123',
        'delta_total': -5,      # 5 more departures than arrivals
        'delta_ebike': -2,      # 2 more ebike departures
        'delta_other': -3       # 3 more classic departures
    },
    # ... more events
]

# Write to database
db = DatabaseConnection(DB_PATH)
with db.get_connection() as conn:
    repo = EventsHourlyRepository(conn)
    count = repo.upsert_hourly_events_batch(events_data)
    print(f"✓ Inserted/updated {count} hourly events")
```

### 2. Maintain Station Catalog → `station`

**Input**: Derive from trip CSV data (station_id, station_name)

**Output**: Keep station catalog up-to-date

#### Code Example

```python
from database.repositories import StationRepository

stations_data = [
    {
        'id': 'CHI00123',
        'name': 'Michigan Ave & Oak St',
        'lat': 41.9008,         # Optional
        'lon': -87.6238,        # Optional
        'capacity': 35,         # Optional
        'is_active': 1
    },
    # ... more stations
]

with db.get_connection() as conn:
    repo = StationRepository(conn)
    count = repo.upsert_stations_batch(stations_data)
    print(f"✓ Upserted {count} stations")
```

## Data Contracts

### Timezone Convention
- All hourly keys MUST be in **America/Chicago** local time (Central Time - Divvy is in Chicago)
- Format: `'YYYY-MM-DD HH:00:00'`
- Floor timestamps to the hour (e.g., 14:37:22 → 14:00:00)

### Rideable Type Mapping
Map source `rideable_type` values to deltas:
- `'electric_bike'` → contributes to `delta_ebike`
- `'classic_bike'` or `'docked_bike'` → contributes to `delta_other`
- Unknown types → contribute to `delta_total` only

### Upsert Behavior
- **`station`**: Keyed by `id` - updates name/lat/lon/capacity on conflict
- **`events_hourly`**: Keyed by `(hour, station_id)` - overwrites deltas (supports reprocessing)

## Project Structure (for reference)

```
database/
├── __init__.py
├── connection.py       # DatabaseConnection class
├── repositories.py     # StationRepository, EventsHourlyRepository
├── schema.sql          # SQLite schema definition
└── init_db.py          # Initialization script

config/
└── database.py         # DB_PATH, INITIAL_BALANCE, TIMEZONE constants

data/
└── app.db              # SQLite database file (auto-created)
```

## Running the Database Initialization

```bash
# From project root
python database/init_db.py
```

## Testing Your Integration

After writing data, you can verify:

```python
from database.connection import DatabaseConnection
from config.database import DB_PATH

db = DatabaseConnection(DB_PATH)
with db.get_connection() as conn:
    cursor = conn.cursor()
    
    # Check event counts
    cursor.execute("SELECT COUNT(*) as cnt FROM events_hourly")
    print(f"Total hourly events: {cursor.fetchone()['cnt']}")
    
    # Check a sample
    cursor.execute("""
        SELECT * FROM events_hourly 
        ORDER BY hour DESC 
        LIMIT 5
    """)
    for row in cursor.fetchall():
        print(dict(row))
```

## Questions?

Contact Tun (SQLite developer) or Felix (Streamlit developer) for clarification on data contracts.

## PySpark Example (Complete Pipeline)

```python
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, date_format, to_timestamp, when, sum as _sum, lit
from database.connection import DatabaseConnection
from database.repositories import EventsHourlyRepository, StationRepository
from config.database import DB_PATH, TIMEZONE

# Initialize Spark
spark = SparkSession.builder.appName("BikeETL").getOrCreate()

# Read trip data
df = spark.read.csv("data/202507-divvy-tripdata/*.csv", header=True, inferSchema=True)

# Convert to Chicago timezone and extract hour
df = df.withColumn("started_at_chicago", 
                   to_timestamp(col("started_at")).cast("timestamp")) \
       .withColumn("ended_at_chicago", 
                   to_timestamp(col("ended_at")).cast("timestamp")) \
       .withColumn("start_hour", 
                   date_format(col("started_at_chicago"), "yyyy-MM-dd HH:00:00")) \
       .withColumn("end_hour", 
                   date_format(col("ended_at_chicago"), "yyyy-MM-dd HH:00:00"))

# Create delta events (starts = -1, ends = +1)
starts = df.select(
    col("start_hour").alias("hour"),
    col("start_station_id").alias("station_id"),
    col("rideable_type"),
    lit(-1).alias("delta")
)

ends = df.select(
    col("end_hour").alias("hour"),
    col("end_station_id").alias("station_id"),
    col("rideable_type"),
    lit(1).alias("delta")
)

events = starts.union(ends)

# Split by bike type
events = events.withColumn("delta_ebike", 
                          when(col("rideable_type") == "electric_bike", col("delta")).otherwise(0)) \
              .withColumn("delta_other", 
                          when(col("rideable_type") != "electric_bike", col("delta")).otherwise(0))

# Aggregate by hour and station
hourly_agg = events.groupBy("hour", "station_id").agg(
    _sum("delta").alias("delta_total"),
    _sum("delta_ebike").alias("delta_ebike"),
    _sum("delta_other").alias("delta_other")
)

# Convert to Python list of dicts
hourly_data = [row.asDict() for row in hourly_agg.collect()]

# Write to SQLite
db = DatabaseConnection(DB_PATH)
with db.get_connection() as conn:
    repo = EventsHourlyRepository(conn)
    count = repo.upsert_hourly_events_batch(hourly_data)
    print(f"✓ Loaded {count} hourly events into SQLite")

# Also extract and load station catalog
stations = df.select("start_station_id", "start_station_name").distinct() \
            .union(df.select("end_station_id", "end_station_name").distinct()) \
            .distinct() \
            .filter(col("start_station_id").isNotNull())

stations_data = [
    {
        'id': row['start_station_id'],
        'name': row['start_station_name']
    }
    for row in stations.collect()
]

with db.get_connection() as conn:
    repo = StationRepository(conn)
    count = repo.upsert_stations_batch(stations_data)
    print(f"✓ Loaded {count} stations into SQLite")
```
