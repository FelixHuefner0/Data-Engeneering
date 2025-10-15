"""SQLite connection management and context helpers."""

import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Generator


class DatabaseConnection:
    """Manages SQLite database connection and initialization."""
    
    def __init__(self, db_path: Path | str):
        """
        Initialize database connection manager.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
    
    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Context manager for database connections.
        
        Yields:
            sqlite3.Connection: Active database connection
            
        Example:
            >>> db = DatabaseConnection("data/app.db")
            >>> with db.get_connection() as conn:
            ...     cursor = conn.cursor()
            ...     cursor.execute("SELECT * FROM station")
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def initialize_schema(self, schema_path: Path | str | None = None) -> None:
        """
        Initialize database schema from SQL file.
        
        Args:
            schema_path: Path to schema.sql file. If None, uses default location.
        """
        if schema_path is None:
            schema_path = Path(__file__).parent / "schema.sql"
        else:
            schema_path = Path(schema_path)
        
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")
        
        with self.get_connection() as conn:
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema_sql = f.read()
            conn.executescript(schema_sql)
        
        print(f"✓ Database initialized: {self.db_path}")
    
    def vacuum(self) -> None:
        """Optimize database by rebuilding and reclaiming space."""
        with self.get_connection() as conn:
            conn.execute("VACUUM")
        print(f"✓ Database optimized: {self.db_path}")


def get_db_connection(db_path: Path | str = "data/app.db") -> DatabaseConnection:
    """
    Factory function to get database connection manager.
    
    Args:
        db_path: Path to SQLite database file
        
    Returns:
        DatabaseConnection: Initialized connection manager
    """
    return DatabaseConnection(db_path)
