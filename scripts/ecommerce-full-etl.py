# Glue ETL Script: Updated to match challenge logic and fix errors
import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql.functions import *
from pyspark.sql.window import Window
from awsglue.dynamicframe import DynamicFrame

# Job parameters
args = getResolvedOptions(sys.argv, ['JOB_NAME'])

# Initialize contexts
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

# Config
raw_bucket = "s3://my-ecommerce-data-2024/raw/"
processed_bucket = "s3://my-ecommerce-data-2024/processed/"
database_name = "ecommerce_db"

# ========== 1. Load Events Data ==========
events_df = glueContext.create_dynamic_frame.from_catalog(
    database=database_name,
    table_name="events",
    transformation_ctx="events_df"
).toDF()

events_processed = events_df.select(
    (col("timestamp") / 1000).cast("timestamp").alias("event_time"),
    col("visitorid").cast("bigint").alias("visitor_id"),
    col("event").alias("event_type"),
    col("itemid").cast("bigint").alias("item_id"),
    when(col("transactionid") == "", None)
      .otherwise(col("transactionid").cast("bigint")).alias("transaction_id")
).filter(col("event_type").isin(["view", "addtocart", "transaction"]))

# Add event_date partition
events_with_partitions = events_processed.withColumn(
    "event_date", date_format(col("event_time"), "yyyy-MM-dd")
)

# ========== 2. Load Item Properties ==========
item_props_df = glueContext.create_dynamic_frame.from_catalog(
    database=database_name,
    table_name="item_properties",
    transformation_ctx="item_props_df"
).toDF()

# Extract numeric values and clean columns
item_props_processed = item_props_df.select(
    (col("timestamp") / 1000).cast("timestamp").alias("property_time"),
    col("itemid").cast("bigint").alias("item_id"),
    col("property").alias("property_name"),
    col("value").alias("property_value")
).withColumn(
    "numeric_value",
    when(col("property_value").startswith("n"), regexp_replace("property_value", "n", "").cast("float"))
)

# Latest snapshot using window
window_spec = Window.partitionBy("item_id", "property_name").orderBy(desc("property_time"))
latest_properties = item_props_processed.withColumn(
    "row_num", row_number().over(window_spec)
).filter(col("row_num") == 1).drop("row_num")

# Pivot useful properties
important_props = latest_properties.filter(
    col("property_name").isin(["categoryid", "available", "price"])
).groupBy("item_id").pivot("property_name").agg(first("property_value"))

# ========== 3. Load Category Tree ==========
category_df = glueContext.create_dynamic_frame.from_catalog(
    database=database_name,
    table_name="category_tree",
    transformation_ctx="category_df"
).toDF()

category_clean = category_df.select(
    col("categoryid").cast("bigint").alias("category_id"),
    when(col("parentid") == "", None).otherwise(col("parentid").cast("bigint")).alias("parent_category_id")
)

# Recursive hierarchy builder (simplified)
def build_category_path(df):
    from pyspark.sql.functions import array, concat
    df = df.withColumn("category_path", array(col("category_id")))
    max_depth = 5
    for _ in range(max_depth):
        joined = df.alias("c1").join(
            df.alias("c2"), col("c1.parent_category_id") == col("c2.category_id"), "left_outer"
        ).select(
            col("c1.category_id"),
            col("c2.parent_category_id").alias("parent_category_id"),
            when(
                col("c2.category_id").isNotNull(),
                concat(col("c1.category_path"), array(col("c2.category_id")))
            ).otherwise(col("c1.category_path")).alias("category_path")
        )
        df = joined
    return df

category_hierarchy = build_category_path(category_clean)

# ========== 4. Join and Enrich Events ==========
enriched_events = events_with_partitions.join(important_props, "item_id", "left")

# Make sure to alias categoryid before join
final_events = enriched_events.withColumn("category_id_tmp", col("categoryid").cast("bigint")).join(
    category_hierarchy,
    col("category_id_tmp") == category_hierarchy["category_id"],
    "left"
).drop("category_id_tmp")

# ========== 5. Write to S3 ==========
glueContext.write_dynamic_frame.from_options(
    frame=DynamicFrame.fromDF(final_events, glueContext, "final_events"),
    connection_type="s3",
    connection_options={
        "path": f"{processed_bucket}/enriched_events/",
        "partitionKeys": ["event_type", "event_date"]
    },
    format="parquet"
)

glueContext.write_dynamic_frame.from_options(
    frame=DynamicFrame.fromDF(latest_properties, glueContext, "latest_properties"),
    connection_type="s3",
    connection_options={"path": f"{processed_bucket}/item_properties/"},
    format="parquet"
)

glueContext.write_dynamic_frame.from_options(
    frame=DynamicFrame.fromDF(category_hierarchy, glueContext, "category_hierarchy"),
    connection_type="s3",
    connection_options={"path": f"{processed_bucket}/category_hierarchy/"},
    format="parquet"
)

job.commit()
