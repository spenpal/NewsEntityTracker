import os
from collections import Counter
from pathlib import Path

import spacy
from dotenv import load_dotenv
from pyspark.sql import SparkSession
from pyspark.sql.functions import explode, struct, sum, to_json, udf

# Load .env file
current_directory = Path.cwd()
env_path = current_directory.joinpath("src", ".env")
load_dotenv(env_path)

kafka_bootstrap_servers = os.getenv("KAFKA_BROKER_URL")
topic1 = os.getenv("TOPIC1")
topic2 = os.getenv("TOPIC2")
checkpoint_location = os.getenv("CHECKPOINT_LOCATION")


def main(spark, nlp):
    # Create a streaming DataFrame that reads from Kafka
    raw_data_df = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", kafka_bootstrap_servers)
        .option("subscribe", topic1)
        # .option("failOnDataLoss", "false") # use this option if you want to ignore data loss
        # .option("startingOffsets", "earliest") # use this option if you want to read from the beginning of the topic
        .load()
        .selectExpr("CAST(value AS STRING)")
        .select("value")
    )

    # Define a user-defined function (UDF) for named entity recognition
    @udf("map<string, int>")
    def count_named_entities(text):
        doc = nlp(text)
        entities_count = Counter([ent.text.lower() for ent in doc.ents])
        return dict(entities_count)

    # Apply the UDF to get counts of named entities for each event
    processed_data_df = raw_data_df.withColumn(
        "named_entities", count_named_entities(raw_data_df["value"])
    )

    # Split the named entities map into separate rows
    ne_counts_df = processed_data_df.select(
        explode(processed_data_df.named_entities).alias("named_entity", "count")
    )

    # Sum of all counts of named entities
    ne_counts_df = ne_counts_df.groupBy("named_entity").agg(sum("count").alias("count"))

    # Convert columns to string type and create a value column for JSON serialization
    ne_counts_df = ne_counts_df.selectExpr(
        "CAST(named_entity AS STRING)",
        "CAST(count AS STRING)",
    ).withColumn(
        "value",
        to_json(struct("*")).cast("string"),
    )

    # Write the results to Kafka at specified trigger intervals
    query = (
        ne_counts_df.select("value")
        .writeStream.trigger(processingTime="10 seconds")
        .outputMode("complete")
        .format("kafka")
        .option("topic", topic2)
        .option("kafka.bootstrap.servers", kafka_bootstrap_servers)
        .option("checkpointLocation", checkpoint_location)
        .start()
        .awaitTermination()
    )

    # USE THIS FOR DEBUGGING
    # query = (
    #     combined_ne_counts_df.select("value")
    #     .writeStream.outputMode("complete")
    #     .format("console")
    #     .option("truncate", "false")
    #     .start()
    # )


if __name__ == "__main__":
    # Create a Spark session
    spark = (
        SparkSession.builder.appName("NamedEntityRecognition")
        .master("local[*]")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")

    # Initialize spaCy
    nlp = spacy.load("en_core_web_sm")

    try:
        main(spark, nlp)
    except KeyboardInterrupt:
        print("Stopping the application...")
        spark.stop()
