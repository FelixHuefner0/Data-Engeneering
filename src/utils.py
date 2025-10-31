# NOT USED - Configured for MongoDB, replaced by batch ETL
import os
from dotenv import load_dotenv
from pyspark.sql import SparkSession

def load_conf(env_path: str = "conf/.env"):
    if os.path.exists(env_path):
        load_dotenv(env_path)

    return {
        # Mongo
        "MONGO_URI": os.getenv("MONGO_URI", "mongodb://localhost:27017"),
        "MONGO_DB":  os.getenv("MONGO_DB",  "divvy"),

        "COLL_STATIONS": os.getenv("COLL_STATIONS", "station"),
        "COLL_HOURLY":   os.getenv("COLL_HOURLY",   "station_hourly_change"),
        "COLL_BALANCE":  os.getenv("COLL_BALANCE",  "station_balance"),

        # Pfade
        "HISTORICAL_DIR": os.getenv("HISTORICAL_DIR", "data/historical"),
        "RAW_LANDING":    os.getenv("RAW_LANDING",    "data/raw_landing"),
        "CHECKPOINT_DIR": os.getenv("CHECKPOINT_DIR", "data/checkpoints/stations_stream"),

        # Spark
        "SHUFFLE_PARTS":  os.getenv("SHUFFLE_PARTS", "4"),
    }

def build_spark(app_name: str, conf: dict) -> SparkSession:
    """
    SparkSession mit Mongo-Read/Write. (Mongo Spark Connector 10.x)
    """
    spark = (
        SparkSession.builder
        .appName(app_name)
        .config("spark.sql.shuffle.partitions", conf["SHUFFLE_PARTS"])
        # Write
        .config("spark.mongodb.write.connection.uri", conf["MONGO_URI"])
        .config("spark.mongodb.write.database",       conf["MONGO_DB"])
        # Read
        .config("spark.mongodb.read.connection.uri",  conf["MONGO_URI"])
        .config("spark.mongodb.read.database",        conf["MONGO_DB"])
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    return spark
