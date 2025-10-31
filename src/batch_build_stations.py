"""
Batch ETL pipeline: CSV trip data → SQLite database
Processes Divvy trip histories into hourly station deltas.
"""

import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pyspark.sql import functions as F
from pyspark.sql import DataFrame

from etl.schemas import ride_schema
from etl.spark_config import build_spark_session, get_csv_pattern
from database.connection import DatabaseConnection
from database.repositories import StationRepository, EventsHourlyRepository
from config.database import DB_PATH, TIMEZONE


def extract_stations(df: DataFrame) -> list:
    """
    Extract unique stations from trip data.
    
    Args:
        df: Spark DataFrame with trip data
        
    Returns:
        List of dicts with station info (id, name)
    """
    # Get start stations
    start_stations = df.select(
        F.col("start_station_id").alias("station_id"),
        F.col("start_station_name").alias("station_name")
    )
    
    # Get end stations
    end_stations = df.select(
        F.col("end_station_id").alias("station_id"),
        F.col("end_station_name").alias("station_name")
    )
    
    # Union and deduplicate
    stations = (
        start_stations.union(end_stations)
        .filter(F.col("station_id").isNotNull())
        .filter(F.col("station_name").isNotNull())
        .dropDuplicates(["station_id"])
    )
    
    # Convert to list of dicts for repository
    return [
        {"id": row.station_id, "name": row.station_name}
        for row in stations.collect()
    ]


def transform_to_hourly_deltas(df: DataFrame) -> list:
    """
    Transform trip data into hourly deltas per station.
    
    Creates events: -1 for departures (start), +1 for arrivals (end)
    Aggregates by (hour, station_id)
    
    Args:
        df: Spark DataFrame with trip data
        
    Returns:
        List of dicts with hourly event data
    """
    # Floor timestamps to hour in Chicago timezone
    df_with_hours = df.withColumn(
        "start_hour",
        F.date_format(
            F.date_trunc("hour", F.col("started_at")),
            "yyyy-MM-dd HH:00:00"
        )
    ).withColumn(
        "end_hour",
        F.date_format(
            F.date_trunc("hour", F.col("ended_at")),
            "yyyy-MM-dd HH:00:00"
        )
    )
    
    # Create departure events (delta = -1)
    departures = (
        df_with_hours
        .filter(F.col("start_station_id").isNotNull())
        .select(
            F.col("start_hour").alias("hour"),
            F.col("start_station_id").alias("station_id"),
            F.lit(-1).alias("delta")
        )
    )
    
    # Create arrival events (delta = +1)
    arrivals = (
        df_with_hours
        .filter(F.col("end_station_id").isNotNull())
        .select(
            F.col("end_hour").alias("hour"),
            F.col("end_station_id").alias("station_id"),
            F.lit(1).alias("delta")
        )
    )
    
    # Union and aggregate by (hour, station_id)
    hourly_deltas = (
        departures.union(arrivals)
        .groupBy("hour", "station_id")
        .agg(F.sum("delta").alias("delta_total"))
        .orderBy("hour", "station_id")
    )
    
    # Convert to list of dicts for repository
    return [
        {
            "hour": row.hour,
            "station_id": row.station_id,
            "delta_total": int(row.delta_total)
        }
        for row in hourly_deltas.collect()
    ]


def main():
    """Main ETL pipeline execution."""
    print("=" * 60)
    print("Divvy Batch ETL: CSV → SQLite")
    print("=" * 60)
    
    # Initialize Spark
    print("\n[1/5] Initializing Spark session...")
    spark = build_spark_session()
    print(f"✓ Spark session created (timezone: {TIMEZONE})")
    
    # Read CSV data
    print("\n[2/5] Reading CSV data...")
    csv_pattern = get_csv_pattern()
    print(f"  Reading from: {csv_pattern}")
    
    df = (
        spark.read
        .option("header", True)
        .schema(ride_schema)
        .csv(csv_pattern)
    )
    
    trip_count = df.count()
    print(f"✓ Loaded {trip_count:,} trips")
    
    # Extract stations
    print("\n[3/5] Extracting station catalog...")
    stations = extract_stations(df)
    print(f"✓ Found {len(stations)} unique stations")
    
    # Transform to hourly deltas
    print("\n[4/5] Transforming to hourly deltas...")
    hourly_events = transform_to_hourly_deltas(df)
    print(f"✓ Generated {len(hourly_events):,} hourly events")
    
    # Write to SQLite
    print("\n[5/5] Writing to SQLite database...")
    print(f"  Database: {DB_PATH}")
    
    db = DatabaseConnection(DB_PATH)
    with db.get_connection() as conn:
        # Write stations
        station_repo = StationRepository(conn)
        station_count = station_repo.upsert_stations_batch(stations)
        print(f"✓ Upserted {station_count} stations")
        
        # Write hourly events
        events_repo = EventsHourlyRepository(conn)
        events_count = events_repo.upsert_hourly_events_batch(hourly_events)
        print(f"✓ Upserted {events_count} hourly events")
    
    # Cleanup
    spark.stop()
    
    print("\n" + "=" * 60)
    print("ETL Complete!")
    print("=" * 60)
    print(f"\nSummary:")
    print(f"  • Processed: {trip_count:,} trips")
    print(f"  • Stations: {station_count}")
    print(f"  • Hourly events: {events_count:,}")
    print(f"\nNext step: streamlit run src/streamlit_test.py")


if __name__ == "__main__":
    main()
