from pyspark.sql.types import (
    StructType, StructField, StringType, TimestampType, DoubleType
)

# Divvy Tripdata – nur Kernspalten sind relevant, Rest optional
ride_schema = StructType([
    StructField("ride_id",            StringType(),  True),
    StructField("rideable_type",      StringType(),  True),
    StructField("started_at",         TimestampType(), True),
    StructField("ended_at",           TimestampType(), True),

    StructField("start_station_name", StringType(),  True),
    StructField("start_station_id",   StringType(),  True),
    StructField("end_station_name",   StringType(),  True),
    StructField("end_station_id",     StringType(),  True),

    # optionale Felder (werden ignoriert)
    StructField("start_lat", DoubleType(), True),
    StructField("start_lng", DoubleType(), True),
    StructField("end_lat",   DoubleType(), True),
    StructField("end_lng",   DoubleType(), True),
    StructField("member_casual", StringType(), True),
])
