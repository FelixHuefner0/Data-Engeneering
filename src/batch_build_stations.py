from pyspark.sql import functions as F
from pyspark.sql import Window
from pyspark.sql import DataFrame
from etl.schemas import ride_schema
from etl.utils import load_conf, build_spark

def transform_stations(df: DataFrame) -> DataFrame:
    s = df.select(F.col("start_station_id").alias("station_id"),
                  F.col("start_station_name").alias("station_name"))
    e = df.select(F.col("end_station_id").alias("station_id"),
                  F.col("end_station_name").alias("station_name"))
    stations = (
        s.unionByName(e)
         .filter(F.col("station_id").isNotNull() & F.col("station_name").isNotNull())
         .withColumn("station_id", F.trim("station_id").cast("string"))
         .withColumn("station_name", F.trim("station_name"))
         .dropDuplicates(["station_id","station_name"])
    )
    return stations

def transform_hourly_change(df: DataFrame) -> DataFrame:
    # Stundenkörbe
    df_hours = (df
        .withColumn("start_hour", F.date_trunc("hour", F.col("started_at")))
        .withColumn("end_hour",   F.date_trunc("hour", F.col("ended_at"))))

    dep = (df_hours
        .filter(F.col("start_station_id").isNotNull())
        .groupBy(F.col("start_station_id").alias("station_id"),
                 F.col("start_hour").alias("hour"))
        .agg(F.count("*").alias("departures")))

    arr = (df_hours
        .filter(F.col("end_station_id").isNotNull())
        .groupBy(F.col("end_station_id").alias("station_id"),
                 F.col("end_hour").alias("hour"))
        .agg(F.count("*").alias("arrivals")))

    hourly = (arr.join(dep, ["station_id","hour"], "full_outer")
                 .na.fill({"arrivals":0, "departures":0})
                 .withColumn("delta", F.col("arrivals") - F.col("departures"))
                 .select("station_id","hour","delta"))
    return hourly

def transform_balance(hourly: DataFrame) -> DataFrame:
    w = (Window.partitionBy("station_id")
               .orderBy(F.col("hour").asc())
               .rowsBetween(Window.unboundedPreceding, Window.currentRow))
    balance = (hourly
               .withColumn("balance", F.sum("delta").over(w))
               .select("station_id","hour","balance"))
    return balance

def main():
    conf = load_conf()
    spark = build_spark("DivvyStationsBatchETL", conf)

    rides = (spark.read
                  .option("header", True)
                  .option("recursiveFileLookup", True)
                  .schema(ride_schema)
                  .csv(conf["HISTORICAL_DIR"]))

    stations = transform_stations(rides)
    hourly   = transform_hourly_change(rides)
    balance  = transform_balance(hourly)

    # Schreiben
    (stations.write.format("mongodb")
        .option("collection", conf["COLL_STATIONS"])
        .mode("overwrite").save())

    (hourly.write.format("mongodb")
        .option("collection", conf["COLL_HOURLY"])
        .mode("overwrite").save())

    (balance.write.format("mongodb")
        .option("collection", conf["COLL_BALANCE"])
        .mode("overwrite").save())

    print("✅ Wrote:")
    print(f"  - station -> {stations.count()} rows")
    print(f"  - station_hourly_change -> {hourly.count()} rows")
    print(f"  - station_balance -> {balance.count()} rows")
    spark.stop()

if __name__ == "__main__":
    main()
