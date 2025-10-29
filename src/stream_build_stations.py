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
    return (s.unionByName(e)
              .filter(F.col("station_id").isNotNull() & F.col("station_name").isNotNull())
              .withColumn("station_id", F.trim("station_id").cast("string"))
              .withColumn("station_name", F.trim("station_name"))
              .dropDuplicates(["station_id","station_name"]))

def transform_hourly_change(df: DataFrame) -> DataFrame:
    dfh = (df
           .withColumn("start_hour", F.date_trunc("hour", F.col("started_at")))
           .withColumn("end_hour",   F.date_trunc("hour", F.col("ended_at"))))
    dep = (dfh.filter(F.col("start_station_id").isNotNull())
               .groupBy(F.col("start_station_id").alias("station_id"),
                        F.col("start_hour").alias("hour"))
               .agg(F.count("*").alias("departures")))
    arr = (dfh.filter(F.col("end_station_id").isNotNull())
               .groupBy(F.col("end_station_id").alias("station_id"),
                        F.col("end_hour").alias("hour"))
               .agg(F.count("*").alias("arrivals")))
    return (arr.join(dep, ["station_id","hour"], "full_outer")
               .na.fill({"arrivals":0,"departures":0})
               .withColumn("delta", F.col("arrivals") - F.col("departures"))
               .select("station_id","hour","delta"))

def write_batch_to_mongo(batch_df: DataFrame, batch_id: int, conf: dict, spark):
    # 1) Stations upsert (einfach append + dedup downstream)
    stations = transform_stations(batch_df)
    (stations.dropDuplicates(["station_id","station_name"])
             .write.format("mongodb")
             .option("collection", conf["COLL_STATIONS"])
             .mode("append").save())

    # 2) Hourly delta dieses Batches
    hourly = transform_hourly_change(batch_df)
    (hourly.write.format("mongodb")
           .option("collection", conf["COLL_HOURLY"])
           .mode("append").save())

    # 3) Balance: kumulativ pro Station (Batch-intern) + Offset aus letzter bekannter Balance in Mongo
    from pyspark.sql import Window
    w = (Window.partitionBy("station_id")
               .orderBy(F.col("hour").asc())
               .rowsBetween(Window.unboundedPreceding, Window.currentRow))
    batch_balance = hourly.withColumn("cum_delta", F.sum("delta").over(w))

    # Letzten bekannten Balance-Stand je Station aus Mongo holen (max hour)
    prev = (spark.read.format("mongodb")
                  .option("collection", conf["COLL_BALANCE"])
                  .load()
                  .groupBy("station_id")
                  .agg(F.max("hour").alias("prev_hour"),
                       F.max("balance").alias("prev_balance")))

    # Wenn leer (beim ersten Lauf), einen leeren Frame mit passenden Spalten erzeugen
    if prev.rdd.isEmpty():
        prev = spark.createDataFrame([], batch_balance.select("station_id").schema) \
                    .withColumn("prev_hour", F.lit(None).cast("timestamp")) \
                    .withColumn("prev_balance", F.lit(None).cast("long"))

    # Offset-Join nur nach station_id
    joined = (batch_balance
              .join(prev.select("station_id","prev_balance"), on="station_id", how="left")
              .na.fill({"prev_balance": 0})
              .withColumn("balance", F.col("cum_delta") + F.col("prev_balance"))
              .select(F.col("station_id"),
                      F.col("hour"),
                      F.col("balance").cast("long")))

    (joined.write.format("mongodb")
           .option("collection", conf["COLL_BALANCE"])
           .mode("append").save())

def main():
    conf = load_conf()
    spark = build_spark("DivvyStationsStreamingETL", conf)

    stream_df = (spark.readStream
                      .option("header", True)
                      .option("maxFilesPerTrigger", 1)  # kontrollierter Zufluss
                      .schema(ride_schema)
                      .csv(conf["RAW_LANDING"]))

    query = (stream_df.writeStream
             .foreachBatch(lambda df, bid: write_batch_to_mongo(df, bid, conf, spark))
             .option("checkpointLocation", conf["CHECKPOINT_DIR"])
             .outputMode("update")
             .start())

    query.awaitTermination()

if __name__ == "__main__":
    main()
