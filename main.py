#!/usr/bin/env python3
"""
Divvy Bike Share Data Platform - Main Entry Point

This script orchestrates the entire data pipeline:
1. Initialize database (if needed)
2. Run ETL pipeline (optional)
3. Launch Streamlit dashboard (optional)

Usage:
    python main.py                    # Full pipeline + launch dashboard
    python main.py --skip-etl         # Skip ETL, just launch dashboard
    python main.py --etl-only         # Run ETL only, don't launch dashboard
    python main.py --init-only        # Just initialize database
"""

import sys
import argparse
import subprocess
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from database.connection import DatabaseConnection
from config.database import DB_PATH


def print_header(text: str):
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70 + "\n")


def print_step(step: int, total: int, text: str):
    """Print a step indicator."""
    print(f"[{step}/{total}] {text}")


def check_database_exists() -> bool:
    """Check if database file exists and has tables."""
    if not Path(DB_PATH).exists():
        return False
    
    # Check if tables exist
    try:
        db = DatabaseConnection(DB_PATH)
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            return 'station' in tables and 'events_hourly' in tables
    except Exception:
        return False


def check_database_populated() -> tuple[int, int]:
    """
    Check if database has data.
    
    Returns:
        Tuple of (station_count, events_count)
    """
    if not check_database_exists():
        return (0, 0)
    
    try:
        db = DatabaseConnection(DB_PATH)
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM station")
            station_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM events_hourly")
            events_count = cursor.fetchone()[0]
            
            return (station_count, events_count)
    except Exception:
        return (0, 0)


def count_csv_files() -> int:
    """Count CSV files in data directory."""
    data_dir = PROJECT_ROOT / "data" / "tripdata"
    if not data_dir.exists():
        return 0
    return len(list(data_dir.glob("*.csv")))


def initialize_database(force: bool = False) -> bool:
    """
    Initialize the database.
    
    Args:
        force: If True, recreate database even if it exists
        
    Returns:
        True if successful
    """
    if check_database_exists() and not force:
        print("✓ Database already initialized")
        return True
    
    print("Initializing database...")
    try:
        db = DatabaseConnection(DB_PATH)
        db.initialize_schema()
        print("✓ Database initialized successfully")
        return True
    except Exception as e:
        print(f"✗ Database initialization failed: {e}")
        return False


def run_etl_pipeline() -> bool:
    """
    Run the Spark ETL pipeline.
    
    Returns:
        True if successful
    """
    print("Running ETL pipeline...")
    print("(This may take several minutes depending on data size)\n")
    
    try:
        # Import here to avoid loading Spark unless needed
        from src.batch_build_stations import main as etl_main
        etl_main()
        return True
    except Exception as e:
        print(f"\n✗ ETL pipeline failed: {e}")
        return False


def launch_streamlit() -> bool:
    """
    Launch the Streamlit dashboard.
    
    Returns:
        True if launched successfully
    """
    print("Launching Streamlit dashboard...")
    print("(Browser should open automatically)\n")
    
    try:
        streamlit_script = PROJECT_ROOT / "src" / "streamlit_test.py"
        subprocess.run(
            ["streamlit", "run", str(streamlit_script)],
            check=True
        )
        return True
    except KeyboardInterrupt:
        print("\n✓ Streamlit stopped by user")
        return True
    except Exception as e:
        print(f"\n✗ Failed to launch Streamlit: {e}")
        return False


def main():
    """Main orchestration function."""
    parser = argparse.ArgumentParser(
        description="Divvy Bike Share Data Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                 # Full pipeline: init + ETL + dashboard
  python main.py --skip-etl      # Skip ETL, launch dashboard only
  python main.py --etl-only      # Run ETL only, don't launch dashboard
  python main.py --init-only     # Just initialize database
  python main.py --force-init    # Recreate database, then run pipeline
        """
    )
    
    parser.add_argument(
        "--skip-etl",
        action="store_true",
        help="Skip ETL pipeline, just launch dashboard"
    )
    
    parser.add_argument(
        "--etl-only",
        action="store_true",
        help="Run ETL only, don't launch dashboard"
    )
    
    parser.add_argument(
        "--init-only",
        action="store_true",
        help="Only initialize database, skip ETL and dashboard"
    )
    
    parser.add_argument(
        "--force-init",
        action="store_true",
        help="Force database reinitialization (WARNING: deletes existing data)"
    )
    
    args = parser.parse_args()
    
    # Print welcome header
    print_header("Divvy Bike Share Data Platform")
    
    # Show current status
    print("Current Status:")
    print(f"  Database: {DB_PATH}")
    db_exists = check_database_exists()
    print(f"  Database initialized: {'Yes ✓' if db_exists else 'No ✗'}")
    
    if db_exists:
        station_count, events_count = check_database_populated()
        print(f"  Stations in DB: {station_count:,}")
        print(f"  Hourly events in DB: {events_count:,}")
    
    csv_count = count_csv_files()
    print(f"  CSV files available: {csv_count}")
    
    if csv_count == 0:
        print("\n⚠️  WARNING: No CSV files found in data/tripdata/")
        print("    Download data from: https://divvybikes.com/system-data")
        print("    Extract CSV files to: data/tripdata/")
        if not args.init_only:
            print("\n✗ Cannot run ETL without data. Exiting.")
            return 1
    
    # Determine what to do
    total_steps = 0
    if not args.skip_etl and not args.init_only:
        total_steps = 3  # init + etl + dashboard
    elif args.etl_only:
        total_steps = 2  # init + etl
    elif args.skip_etl:
        total_steps = 2  # init + dashboard
    else:
        total_steps = 1  # init only
    
    current_step = 0
    
    # Step 1: Initialize database
    current_step += 1
    print_header(f"Step {current_step}/{total_steps}: Database Initialization")
    
    if args.force_init:
        if db_exists:
            print("⚠️  Force init requested - existing database will be deleted")
            response = input("Are you sure? This will delete all data! (yes/no): ")
            if response.lower() != 'yes':
                print("✗ Aborted by user")
                return 1
            Path(DB_PATH).unlink()
            print("✓ Old database deleted")
    
    if not initialize_database(force=args.force_init):
        return 1
    
    if args.init_only:
        print_header("Complete!")
        print("Database initialized. Run with --etl-only to process data.")
        return 0
    
    # Step 2: ETL Pipeline (if not skipped)
    if not args.skip_etl:
        current_step += 1
        print_header(f"Step {current_step}/{total_steps}: ETL Pipeline")
        
        if csv_count == 0:
            print("✗ No CSV files found. Skipping ETL.")
            return 1
        
        # Check if database already has data
        station_count, events_count = check_database_populated()
        if station_count > 0 and events_count > 0:
            print(f"⚠️  Database already contains data:")
            print(f"    Stations: {station_count:,}")
            print(f"    Events: {events_count:,}")
            print("\n📝 Note: Running ETL will UPSERT (update/insert) data.")
            print("    - Existing stations will be updated")
            print("    - Existing events will be replaced")
            print("    - This is safe and idempotent\n")
            
            response = input("Continue with ETL? (yes/no): ")
            if response.lower() != 'yes':
                print("✗ ETL skipped by user")
                if args.etl_only:
                    return 0
            else:
                if not run_etl_pipeline():
                    return 1
        else:
            if not run_etl_pipeline():
                return 1
    
    if args.etl_only:
        print_header("Complete!")
        print("ETL pipeline finished. Run without --etl-only to launch dashboard.")
        return 0
    
    # Step 3: Launch Dashboard
    current_step += 1
    print_header(f"Step {current_step}/{total_steps}: Streamlit Dashboard")
    
    # Final check before launching
    station_count, events_count = check_database_populated()
    if station_count == 0 or events_count == 0:
        print("✗ Database is empty. Run ETL first:")
        print("  python main.py --etl-only")
        return 1
    
    print(f"Ready to launch with:")
    print(f"  • {station_count:,} stations")
    print(f"  • {events_count:,} hourly events\n")
    
    if not launch_streamlit():
        return 1
    
    print_header("Complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())

