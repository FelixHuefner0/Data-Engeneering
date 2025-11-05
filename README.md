# Bike Sharing Data Platform

**Team:** Felix, Tun, Sebi, Oliver
**Course:** Data Engineering  
**Date:** October 2025

## Abstract / Executive Summary

This project builds a comprehensive bike-sharing analytics platform for Divvy (Chicago bike-share) data. The system processes historical trip data to provide operators with actionable insights for bike rebalancing. Using a modern data engineering stack (Spark for ETL, SQLite for serving, Streamlit for visualization), the platform calculates hourly bike balances per station, identifies critical inventory levels, and supports manual rebalancing decisions. The solution processes millions of trips efficiently, maintains sub-second query performance, and provides an intuitive interface for operations teams.

## Problem Statement

**Who**: Bike-sharing operations teams managing fleet distribution across hundreds of stations.

**Pain Point**: Stations frequently become empty (no bikes for customers) or full (no docks for returns), leading to poor customer experience and revenue loss. Operators need historical visibility and patterns to optimize bike redistribution.

**User Stories**:
- As an **operations manager**, I want to **see which stations will run low on bikes in the next few hours** so that **I can dispatch rebalancing crews proactively**.
- As a **rebalancing crew member**, I want to **record manual adjustments** so that **the system accurately reflects current inventory**.
- As an **operations manager**, I want to **get notified if a stations will run low/high on bikes** so that **there is enough time to rebalancing before an over/underflow**.

## System Architecture and Design

### High-Level Architecture

```
┌─────────────────────┐
│  Data Source        │
│  • Trip Histories   │
└─────────┬───────────┘
          │
          ▼
    ┌──────────────┐
    │  Spark ETL   │
    │  • Batch     │
    │  • Transform │
    └──────┬───────┘
           │
           ▼
      ┌──────────────┐
      │   SQLite DB  │
      │  • Station   │
      │  • Events    │
      └───┬──────────┘
          │
          ▼
    ┌──────────────┐
    │  Streamlit   │
    │  Dashboard   │
    └──────────────┘
```

**Flow**:
1. **Batch**: Spark reads monthly trip CSVs, aggregates to hourly deltas (Chicago timezone), writes to SQLite
2. **Serve**: Streamlit reads from SQLite for interactive visualization and rebalancing UI

### Data Sources

**Trip Histories (Batch)**
- **Source**: [Divvy Trip Data](https://divvybikes.com/system-data) - monthly CSV files
- **Format**: CSV with columns: `ride_id`, `rideable_type`, `started_at`, `ended_at`, `start_station_id`, `start_station_name`, `end_station_id`, `end_station_name`
- **Velocity**: Monthly batch (historical), ~800K trips/month
- **Volume**: ~100MB per month compressed

### Data Model

The database uses two core tables (see `database/schema.sql` for full schema):

**`station`** - Station catalog
- `id` (TEXT, PK): Station identifier from trip data
- `name` (TEXT): Station name
- `capacity` (INTEGER): Total docking capacity (optional)
- `is_active` (INTEGER): Active status flag

**`events_hourly`** - Hourly aggregated deltas
- `(hour, station_id)` (TEXT, PK): Composite key
- `delta_total` (INTEGER): Net change (+1 arrival, -1 departure)
- `delta_ebike`, `delta_other` (INTEGER): Split by bike type
- Foreign key to `station.id`

Each record in `events_hourly` references a single station in the `station` table, meaning each station can be associated with multiple hourly event records. SO we have a one-to-many relationship from `station` to `events_hourly`.


## Setup and Deployment

### Prerequisites

- **Python 3.9+** (tested with 3.11)
- **Docker & Docker Compose** (for containerized deployment)
- **Git** (for version control)
- **SQLite 3** (included with Python)

### Installation & Launch

**1. Clone the repository:**
```bash
git clone https://github.com/FelixHuefner0/Data-Engeneering.git
cd Data-Engeneering
```

**2. Create Python virtual environment:**
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

**3. Install dependencies:**
```bash
pip install -r requirements.txt
```

**4. Download sample data:**
```bash
# Download from https://divvybikes.com/system-data
# Extract CSV files to data/tripdata/
# Example:
#   data/tripdata/202301-divvy-tripdata.csv
#   data/tripdata/202302-divvy-tripdata.csv
```

**5. Run the complete pipeline:**
```bash
# Full pipeline: initialize DB + run ETL + launch dashboard
python main.py

# Or skip ETL if data already loaded
python main.py --skip-etl

# Or run ETL only without launching dashboard
python main.py --etl-only
```

**6. Run in a container:**

**Build and run manually with docker:**

```bash
# Build the image
docker build -t dataengproj -f Dockerfile .

# Run the container
docker run -it -p 8501:8501 --memory=12g dataengproj
```

### Configuration Parameters

**Database Configuration** (`config/database.py`):
- `DB_PATH`: SQLite database location (default: `data/app.db`)
- `INITIAL_BALANCE`: Starting bikes per station (default: 20)
- `TIMEZONE`: Timezone for hourly events (default: `America/Chicago`)
- `BALANCE_LOW_THRESHOLD`: Warning threshold for low inventory (default: 5)
- `BALANCE_HIGH_THRESHOLD`: Warning threshold for high inventory (default: 30)

**Spark Integration** (see `data/docs/SPARK_INTEGRATION.md`):
- Batch processing configuration
- Chicago timezone handling
- Delta aggregation rules

## Project Structure

```
Data-Engeneering/
├── main.py                     # Main entry point (orchestrates pipeline)
├── config/                     # Configuration files
│   ├── __init__.py
│   └── database.py            # DB settings, constants
├── database/                   # Database layer
│   ├── __init__.py
│   ├── connection.py          # Connection management
│   ├── repositories.py        # Data access layer
│   ├── schema.sql             # Table definitions
│   └── init_db.py             # Initialization script
├── etl/                        # ETL configuration
│   ├── __init__.py
│   ├── schemas.py             # Spark schema definitions
│   └── spark_config.py        # Spark session builder
├── src/                        # Application code
│   ├── batch_build_stations.py # Spark ETL pipeline
│   ├── streamlit_test.py      # Streamlit dashboard
│   └── jupiter.ipynb          # Exploratory analysis
├── data/                       # Data files (gitignored)
│   ├── app.db                 # SQLite database
│   ├── tripdata/              # Trip CSVs
│   └── docs/                  # Documentation
│       └── SPARK_INTEGRATION.md
├── requirements.txt            # Python dependencies
├── HowToRun.md                # Quick start guide
└── README.md                   # This file
```


## Limitations and Future Work

**Limitations**:
- SQLite has no built-in concurrency (single writer) - acceptable for current scale
- Historical data requires reprocessing for schema changes
- No authentication/authorization on dashboard
- Manual adjustments aren't versioned/audited

**Future Work**:
- **Migrate to PostgreSQL** for production-scale concurrency
- **Implement time-series forecasting** to predict future imbalances
- **Build mobile app** for rebalancing crews
- **Add ML-based rebalancing recommendations**
- **Deploy to Kubernetes** for auto-scaling
- **Implement data quality monitoring** with Great Expectations

## Conclusion

This project demonstrates a data engineering pipeline that transforms raw bike-sharing data into actionable operational insights. By separating concerns (Spark for compute, SQLite for serving, Streamlit for presentation) and establishing clear data contracts, the team can work independently while maintaining system integrity. The foundation is scalable - the same architecture would support the transition to Postgres, Kafka, and Kubernetes as volume grows. Most importantly, it actually solves a real business problem: helping operations teams keep bikes available where and when customers need them.
