"""Spark configuration for SQLite-based ETL pipeline."""

from pathlib import Path
from pyspark.sql import SparkSession
from config.database import DB_PATH, TIMEZONE, PROJECT_ROOT


def build_spark_session(app_name: str = "DivvyBatchETL") -> SparkSession:
    """
    Build a simple Spark session for local batch processing.
    
    Args:
        app_name: Name of the Spark application
        
    Returns:
        Configured SparkSession
    """
    spark = (
        SparkSession.builder
        .appName(app_name)
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.sql.session.timeZone", TIMEZONE)
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    return spark


def get_data_path() -> Path:
    """
    Get the path to CSV data files.
    
    Returns:
        Path to directory containing Divvy trip CSVs
    """
    # The data/tripdata directory contains all the CSV files that we process for the ETL
    return PROJECT_ROOT / "data" / "tripdata"


def get_csv_pattern() -> str:
    """
    Get the glob pattern for reading CSV files.
    
    Returns:
        String pattern for CSV file matching
    """
    data_path = get_data_path()
    return str(data_path / "*.csv")

