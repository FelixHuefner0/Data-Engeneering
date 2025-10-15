"""Data access layer - repositories for each table."""

from typing import List, Dict, Any, Optional
from datetime import datetime
import sqlite3


class StationRepository:
    """Repository for station catalog operations."""
    
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
    
    def upsert_station(
        self,
        station_id: str,
        name: str,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        capacity: Optional[int] = None,
        is_active: int = 1
    ) -> None:
        """
        Insert or update a station record.
        
        Args:
            station_id: Station identifier
            name: Station name
            lat: Latitude (optional)
            lon: Longitude (optional)
            capacity: Docking capacity (optional)
            is_active: 1 if active, 0 if inactive
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO station (id, name, lat, lon, capacity, is_active, created_at_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                lat = excluded.lat,
                lon = excluded.lon,
                capacity = excluded.capacity,
                is_active = excluded.is_active
        """, (station_id, name, lat, lon, capacity, is_active, datetime.utcnow().isoformat()))
    
    def upsert_stations_batch(self, stations: List[Dict[str, Any]]) -> int:
        """
        Batch upsert multiple stations.
        
        Args:
            stations: List of station dicts with keys: id, name, lat, lon, capacity, is_active
            
        Returns:
            Number of stations processed
        """
        cursor = self.conn.cursor()
        now_utc = datetime.utcnow().isoformat()
        
        data = [
            (
                s['id'],
                s['name'],
                s.get('lat'),
                s.get('lon'),
                s.get('capacity'),
                s.get('is_active', 1),
                now_utc
            )
            for s in stations
        ]
        
        cursor.executemany("""
            INSERT INTO station (id, name, lat, lon, capacity, is_active, created_at_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                lat = excluded.lat,
                lon = excluded.lon,
                capacity = excluded.capacity,
                is_active = excluded.is_active
        """, data)
        
        return len(data)
    
    def get_all_stations(self, active_only: bool = True) -> List[sqlite3.Row]:
        """
        Get all stations.
        
        Args:
            active_only: If True, return only active stations
            
        Returns:
            List of station records
        """
        cursor = self.conn.cursor()
        if active_only:
            cursor.execute("SELECT * FROM station WHERE is_active = 1 ORDER BY name")
        else:
            cursor.execute("SELECT * FROM station ORDER BY name")
        return cursor.fetchall()
    
    def get_station_by_id(self, station_id: str) -> Optional[sqlite3.Row]:
        """Get a single station by ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM station WHERE id = ?", (station_id,))
        return cursor.fetchone()


class EventsHourlyRepository:
    """Repository for hourly events operations (Spark writes here)."""
    
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
    
    def upsert_hourly_event(
        self,
        hour: str,
        station_id: str,
        delta_total: int,
        delta_ebike: int = 0,
        delta_other: int = 0
    ) -> None:
        """
        Insert or update an hourly event record.
        
        Args:
            hour: Local Chicago time in format 'YYYY-MM-DD HH:00:00'
            station_id: Station identifier
            delta_total: Net change (all bikes)
            delta_ebike: Net change for ebikes
            delta_other: Net change for other bikes
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO events_hourly (hour, station_id, delta_total, delta_ebike, delta_other)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(hour, station_id) DO UPDATE SET
                delta_total = excluded.delta_total,
                delta_ebike = excluded.delta_ebike,
                delta_other = excluded.delta_other
        """, (hour, station_id, delta_total, delta_ebike, delta_other))
    
    def upsert_hourly_events_batch(self, events: List[Dict[str, Any]]) -> int:
        """
        Batch upsert multiple hourly events (Spark entry point).
        
        Args:
            events: List of event dicts with keys: hour, station_id, delta_total, delta_ebike, delta_other
            
        Returns:
            Number of events processed
        """
        cursor = self.conn.cursor()
        
        data = [
            (
                e['hour'],
                e['station_id'],
                e['delta_total'],
                e.get('delta_ebike', 0),
                e.get('delta_other', 0)
            )
            for e in events
        ]
        
        cursor.executemany("""
            INSERT INTO events_hourly (hour, station_id, delta_total, delta_ebike, delta_other)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(hour, station_id) DO UPDATE SET
                delta_total = excluded.delta_total,
                delta_ebike = excluded.delta_ebike,
                delta_other = excluded.delta_other
        """, data)
        
        return len(data)
    
    def get_events_for_station(
        self,
        station_id: str,
        start_hour: Optional[str] = None,
        end_hour: Optional[str] = None
    ) -> List[sqlite3.Row]:
        """
        Get hourly events for a specific station, optionally filtered by time range.
        
        Args:
            station_id: Station identifier
            start_hour: Optional start hour (inclusive)
            end_hour: Optional end hour (inclusive)
            
        Returns:
            List of event records ordered by hour
        """
        cursor = self.conn.cursor()
        
        if start_hour and end_hour:
            cursor.execute("""
                SELECT * FROM events_hourly 
                WHERE station_id = ? AND hour >= ? AND hour <= ?
                ORDER BY hour
            """, (station_id, start_hour, end_hour))
        elif start_hour:
            cursor.execute("""
                SELECT * FROM events_hourly 
                WHERE station_id = ? AND hour >= ?
                ORDER BY hour
            """, (station_id, start_hour))
        elif end_hour:
            cursor.execute("""
                SELECT * FROM events_hourly 
                WHERE station_id = ? AND hour <= ?
                ORDER BY hour
            """, (station_id, end_hour))
        else:
            cursor.execute("""
                SELECT * FROM events_hourly 
                WHERE station_id = ?
                ORDER BY hour
            """, (station_id,))
        
        return cursor.fetchall()
    
    def get_cumulative_balance_at_hour(
        self,
        station_id: str,
        hour: str,
        initial_balance: int = 20
    ) -> int:
        """
        Calculate cumulative balance for a station up to a specific hour.
        
        Args:
            station_id: Station identifier
            hour: Hour to calculate balance at
            initial_balance: Starting balance (default 20)
            
        Returns:
            Cumulative balance
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT COALESCE(SUM(delta_total), 0) as total_delta
            FROM events_hourly
            WHERE station_id = ? AND hour <= ?
        """, (station_id, hour))
        
        result = cursor.fetchone()
        total_delta = result['total_delta'] if result else 0
        return initial_balance + total_delta
    
    def get_all_balances_at_hour(
        self,
        hour: str,
        initial_balance: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get balances for all stations at a specific hour.
        
        Args:
            hour: Hour to calculate balances at
            initial_balance: Starting balance (default 20)
            
        Returns:
            List of dicts with station_id and balance
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT 
                s.id as station_id,
                s.name as station_name,
                COALESCE(SUM(e.delta_total), 0) as total_delta
            FROM station s
            LEFT JOIN events_hourly e ON s.id = e.station_id AND e.hour <= ?
            WHERE s.is_active = 1
            GROUP BY s.id, s.name
            ORDER BY s.name
        """, (hour,))
        
        results = cursor.fetchall()
        return [
            {
                'station_id': row['station_id'],
                'station_name': row['station_name'],
                'balance': initial_balance + row['total_delta']
            }
            for row in results
        ]
