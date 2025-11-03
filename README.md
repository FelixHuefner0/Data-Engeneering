# Bike Sharing Data Platform

**Team:** Felix, Tun, Sebi, Oli  
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
    └──────┬───────┘
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

**Station Dimension** (from trip data)
- One record per station with location, capacity, metadata

**Events Fact Table** (from Trip Histories)
- Hourly grain: one row per (hour, station_id)
- Tracks net change in bikes (+1 arrival, -1 departure)
- Split by bike type for detailed analysis

```
station (1) ──< events_hourly (*)
```

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

**4. Initialize the database:**
```bash
python database/init_db.py
```

**5. Download sample data:**
```bash
# Create data directory
mkdir -p data/202507-divvy-tripdata

# Download from https://divvybikes.com/system-data
# Place CSV file in data/202507-divvy-tripdata/
```

**6. Run Streamlit dashboard:**
```bash
streamlit run src/streamlit_test.py
```

**7 Run in a container:**

**7.1 Option 1 - Build with compose :**

```bash
docker-compose up --build
```

**7.1 Option 2 - Build and run manually :**

```bash
# Build the image
docker build -t dataengproj -f Dockerfile .

# Run the container
docker run -it -p 8501:8501 --memory=4g dataengproj
```

### Configuration Parameters

**Database Configuration** (`config/database.py`):
- `DB_PATH`: SQLite database location (default: `data/app.db`)
- `INITIAL_BALANCE`: Starting bikes per station (default: 20)
- `TIMEZONE`: Timezone for hourly events (default: `America/Chicago`)
- `BALANCE_LOW_THRESHOLD`: Warning threshold for low inventory (default: 5)
- `BALANCE_HIGH_THRESHOLD`: Warning threshold for high inventory (default: 30)

**Spark Integration** (see `SPARK_INTEGRATION.md`):
- Batch processing configuration
- Chicago timezone handling
- Delta aggregation rules

## Project Structure

```
Data-Engeneering/
├── config/                     # Configuration files
│   ├── __init__.py
│   └── database.py            # DB settings, constants
├── database/                   # Database layer (Tun's work)
│   ├── __init__.py
│   ├── connection.py          # Connection management
│   ├── repositories.py        # Data access layer
│   ├── schema.sql             # Table definitions
│   └── init_db.py             # Initialization script
├── src/                        # Application code
│   ├── streamlit_test.py      # Streamlit dashboard (Felix)
│   ├── jupiter.ipynb          # Exploratory analysis
│   └── main.py                # Entry point placeholder
├── tests/                      # Unit tests
│   ├── __init__.py
│   └── test_database.py       # Database layer tests
├── data/                       # Data files (gitignored)
│   ├── app.db                 # SQLite database
│   └── 202507-divvy-tripdata/ # Trip CSVs
├── SPARK_INTEGRATION.md        # Guide for Spark developer
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

## Team Responsibilities

### Tun (SQLite Layer) ✅ COMPLETE
- Database schema design
- Repository pattern implementation
- Connection management
- Integration contracts

### Sebi (Spark ETL) ✅ COMPLETE
- Read trip history CSVs
- Aggregate to hourly deltas (Chicago timezone)
- Write to `events_hourly` table
- Maintain station catalog
- **Implemented in `src/batch_build_stations.py`**
- **See `SPARK_INTEGRATION.md` for detailed guide**

### Felix (Streamlit Dashboard) ✅ COMPLETE
- Interactive balance visualization
- Time simulation controls
- Manual adjustment interface
- Warning system for critical levels
- **Integrated with SQLite database**

### Oli (Docker & Orchestration)
- Docker Compose setup
- Shared volume for `/data/app.db`
- Health checks
- Service coordination

## Current Status

✅ **Complete**:
- SQLite schema with 2 core tables
- Repository pattern for data access
- Database initialization
- Spark ETL batch pipeline (`src/batch_build_stations.py`)
- Streamlit dashboard integrated with SQLite
- Full data pipeline: CSV → Spark → SQLite → Streamlit

🚧 **In Progress**:
- Docker containerization (Oli)

📋 **Planned**:
- Per-bike-type analysis UI
- Historical trend visualization
- Kubernetes deployment

## Development Workflow

**For Database Changes** (Tun):
1. Update `database/schema.sql`
2. Add migration script to `database/migrations/`
3. Update repositories as needed
4. Run tests: `pytest tests/test_database.py -v`

**For Spark Integration** (Sebi):
1. Follow `SPARK_INTEGRATION.md`
2. Use repository classes for all writes
3. Test with small dataset first
4. Coordinate timezone handling with Tun

**For Frontend** (Felix):
1. Import from `database.repositories`
2. Use `EventsHourlyRepository.get_all_balances_at_hour()` for current UI
3. Add new queries as methods to repositories

## Testing

Run unit tests:
```bash
# All tests
pytest -v

# Database tests only
pytest tests/test_database.py -v

# With coverage
pytest --cov=database --cov-report=html
```

## Data Contracts

**Timezone Convention**: All hourly timestamps in `events_hourly.hour` are **America/Chicago local time** (Central Time), format: `YYYY-MM-DD HH:00:00`

**Rideable Types**: 
- `electric_bike` → `delta_ebike`
- `classic_bike` / `docked_bike` → `delta_other`

**Upsert Behavior**:
- `station`: Key on `id` (updates name/location)
- `events_hourly`: Key on `(hour, station_id)` (supports reprocessing)

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

This project demonstrates a modern data engineering pipeline that transforms raw bike-sharing data into actionable operational insights. By separating concerns (Spark for compute, SQLite for serving, Streamlit for presentation) and establishing clear data contracts, the team can work independently while maintaining system integrity. The foundation is scalable - the same architecture will support the transition to Postgres, Kafka, and Kubernetes as volume grows. Most importantly, it solves a real business problem: helping operations teams keep bikes available where and when customers need them.

## License

Educational project for Data Engineering course.

## Contributors

- **Felix Huefner** - Frontend & Visualization
- **Tun Keltesz** - Database & Storage
- **Sebi** - Spark ETL
- **Oli** - DevOps & Orchestration