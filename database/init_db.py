"""Database initialization script."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.connection import DatabaseConnection
from config.database import DB_PATH


def initialize_database(db_path: Path | str = DB_PATH) -> None:
    """
    Initialize the SQLite database with schema.
    
    Args:
        db_path: Path to database file
    """
    print(f"Initializing database at: {db_path}")
    
    db = DatabaseConnection(db_path)
    db.initialize_schema()
    
    print("\n✅ Database initialization complete!")
    print(f"   Location: {db_path}")
    print(f"   Size: {Path(db_path).stat().st_size if Path(db_path).exists() else 0} bytes")


if __name__ == "__main__":
    initialize_database()
