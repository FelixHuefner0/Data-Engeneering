"""Database configuration settings."""

from pathlib import Path

# Project root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Database file location (shared volume for Docker)
DB_PATH = PROJECT_ROOT / "data" / "app.db"

# Default initial balance for stations (bikes per station at start)
INITIAL_BALANCE = 20

# Chicago timezone for hourly events (Divvy bike-share system)
TIMEZONE = "America/Chicago"

# Balance thresholds for warnings
BALANCE_LOW_THRESHOLD = 5
BALANCE_HIGH_THRESHOLD = 30
