# System Architecture - Bike Sharing Data Platform

## Component Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DATA SOURCE                                  │
├─────────────────────────────────────────────────────────────────────┤
│  Monthly Trip CSVs                                                   │
│  • ride_id                                                           │
│  • rideable_type                                                     │
│  • started_at / ended_at                                             │
│  • start/end station_id                                              │
│  • ~800K trips/month                                                 │
└────────┬─────────────────────────────────────────────────────────────┘
         │
         │
         ▼
┌─────────────────────┐
│   SPARK ETL         │
├─────────────────────┤
│ • Read CSVs         │
│ • Convert to NYC TZ │
│ • Floor to hour     │
│ • Aggregate deltas  │
│ • Split by type     │
└────────┬────────────┘
         │
         │
         ▼
┌────────────────────────────────────────────────────────────────────┐
│                      SQLITE DATABASE                               │
├────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐   ┌───────────────────┐                          │
│  │  station     │   │  events_hourly    │                          │
│  │              │   │                   │                          │
│  │ • id (PK)    │   │ • hour (PK)       │                          │
│  │ • name       │   │ • station_id (PK) │                          │
│  │ • lat/lon    │   │ • delta_total     │                          │
│  │ • capacity   │   │ • delta_ebike     │                          │
│  │ • is_active  │   │ • delta_other     │                          │
│  └──────┬───────┘   └─────────┬─────────┘                          │
│         │                     │                                    │
│         └─────────────────────┘                                    │
│                                                                    │
│  Database Layer (database/repositories.py):                        │
│  • StationRepository           - CRUD for stations                 │
│  • EventsHourlyRepository      - CRUD + balance queries            │
└────────┬───────────────────────────────────────────────────────────┘
         │
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    STREAMLIT DASHBOARD                              │
├─────────────────────────────────────────────────────────────────────┤
│  ┌────────────────────┐  ┌──────────────────┐                      │
│  │ Time Simulation    │  │ Balance Monitor  │                      │
│  │                    │  │                  │                      │
│  │ • Current hour     │  │ • Top 10 low     │                      │
│  │ • +1 hour          │  │ • Top 10 high    │                      │
│  │ • +6 hours         │  │ • Warnings       │                      │
│  │ • Reset            │  │ • Color coding   │                      │
│  └────────────────────┘  └──────────────────┘                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Manual Rebalancing                                           │  │
│  │ • Click to select stations                                   │  │
│  │ • Adjust bike counts (+/-)                                   │  │
│  │ • Apply adjustments (persistent)                             │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Flow Details

### Batch ETL (Historical Data)

```
Trip CSV → Spark Read → Transform → Aggregate → Write to SQLite → Streamlit Visualization
```

**Transform steps:**
1. Parse timestamps: `started_at`, `ended_at`
2. Convert to Chicago timezone (`America/Chicago` - Central Time)
3. Floor to hour: `2025-07-15 14:37:22` → `2025-07-15 14:00:00`
4. Create delta events:
   - Start: `(start_hour, start_station_id, -1)`
   - End: `(end_hour, end_station_id, +1)`
5. Split by `rideable_type`:
   - `electric_bike` → `delta_ebike`
   - Others → `delta_other`
6. Aggregate: `GROUP BY (hour, station_id)`

**Output schema:**
```python
{
    'hour': '2025-07-15 14:00:00',
    'station_id': 'CHI00123',
    'delta_total': -5,      # 5 more departures than arrivals
    'delta_ebike': -2,      # 2 from ebikes
    'delta_other': -3       # 3 from classic bikes
}
```

### Dashboard Queries

**Balance calculation:**
```sql
SELECT 
    s.id as station_id,
    s.name as station_name,
    COALESCE(SUM(e.delta_total), 0) as total_delta
FROM station s
LEFT JOIN events_hourly e 
    ON s.id = e.station_id 
    AND e.hour <= '2025-07-15 14:00:00'
WHERE s.is_active = 1
GROUP BY s.id, s.name

-- Balance = INITIAL_BALANCE (20) + total_delta + manual_adjustments
```

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Data Source** | Divvy Trip CSVs | Raw bike-sharing trip data |
| **ETL** | Apache Spark (PySpark) | Distributed batch processing |
| **Storage** | SQLite 3 | Fast, embedded database |
| **Data Access** | Python (repositories.py) | Type-safe CRUD operations |
| **Visualization** | Streamlit | Interactive web dashboard |
| **Deployment** | Docker Compose | Containerized services |

## Database Schema Details

### `station` (Dimension Table)
- **Purpose**: Station catalog and metadata
- **Source**: Derived from trip CSVs (station_id, station_name from trips)
- **Grain**: One row per station
- **Updates**: Upsert on station ID (name/location may change)

### `events_hourly` (Fact Table)
- **Purpose**: Hourly bike movement aggregates
- **Source**: Spark ETL from trip histories
- **Grain**: One row per (hour, station_id)
- **Updates**: Upsert allows reprocessing (idempotent)
- **Key insight**: Net change, not absolute counts

## Separation of Concerns

### Tun (Database Layer) ✅
- **Owns**: `database/`, `config/database.py`
- **Provides**: Clean API for data access
- **Guarantees**: Schema stability, type safety
- **Contract**: Repository methods, timezone conventions

### Sebi (Spark ETL) 🚧
- **Owns**: Spark pipeline code (future: `etl/`)
- **Consumes**: Trip CSVs
- **Produces**: Writes to `events_hourly`, `station` via repositories
- **Contract**: NYC timezone, hourly grain, delta semantics

### Felix (Frontend) 🚧
- **Owns**: `src/streamlit_test.py`
- **Consumes**: Reads via repositories
- **Produces**: User interactions, manual adjustments
- **Contract**: Uses provided query methods

### Oli (DevOps) 🚧
- **Owns**: `docker-compose.yml`, Dockerfile
- **Provides**: Shared volume for `app.db`
- **Ensures**: Service orchestration, health checks

## Key Design Decisions

### Why SQLite?
- ✅ Zero-configuration, embedded
- ✅ ACID transactions
- ✅ Fast for read-heavy workloads
- ✅ Sufficient for current scale (~700 stations, hourly grain)
- ⚠️ Single writer (acceptable for batch-only workflow)
- 🔄 Can migrate to Postgres later with minimal code changes

### Why Repository Pattern?
- ✅ Decouples business logic from SQL
- ✅ Type-safe interfaces
- ✅ Easier testing (can mock repositories)
- ✅ Centralizes query logic
- ✅ Reduces SQL injection risks

### Why Hourly Grain?
- ✅ Balances detail vs. data volume
- ✅ Matches operational decision-making (rebalancing hourly)
- ✅ Aggregatable to daily/weekly for trends
- ✅ Keeps SQLite database small

### Why Delta (not Snapshot)?
- ✅ Smaller storage (events, not full state every hour)
- ✅ Supports arbitrary time ranges (sum deltas)
- ✅ Rebalancing-friendly (adjustments are additive)
- ✅ Naturally handles missing hours (no implicit zeros)

## Workflow

1. **Data Preparation**: Download monthly CSV files from Divvy
2. **ETL Processing**: Spark reads CSVs, transforms, aggregates to hourly deltas
3. **Database Load**: Spark writes to SQLite via repositories
4. **Visualization**: Streamlit reads from SQLite and displays interactive dashboard
5. **Analysis**: Users simulate time progression, identify imbalances, record adjustments

---

**Document Version**: 1.0  
**Last Updated**: October 14, 2025  
**Maintained by**: Tun (Database Layer)
