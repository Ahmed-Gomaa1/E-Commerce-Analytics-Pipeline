# E-Commerce Analytics Pipeline with AWS Glue, Athena, and S3

## 📌 Project Overview

This project implements a full serverless analytics pipeline for e-commerce user behavior tracking.&#x20;
The solution ingests raw event and product data into Amazon S3, processes it using AWS Glue (PySpark), and enables interactive querying via Amazon Athena.

It supports both historical batch processing and real-time extensibility.&#x20;
The output can feed dashboards, ML pipelines, or reports.

---

## 🗂️ Data Sources

**Stored in S3 bucket:** `s3://ecommerce-data/`

### Raw Folder Structure

```
raw/
├── events/               # Clickstream data: views, add-to-cart, transactions
├── item_properties/      # Item property logs with time series values
└── category_tree/        # Hierarchical category mappings
```

### Processed Folder Structure

```
processed/
├── enriched_events/      # Events joined with item and category data (partitioned)
├── item_properties/      # Cleaned, deduplicated item properties (latest only)
└── category_hierarchy/   # Recursive tree of category_id paths
```


### Data Model (ER Diagram)

                     +-----------------------+
                     |   item_properties     |
                     +-----------------------+
                     | item_id               |
                     | timestamp             |
                     | property              |
                     | value                 |
                     +-----------------------+
                              ↑
                              |
                     +-----------------------+
                     |     Events            |
                     +-----------------------+
                     | timestamp             |
                     | visitor_id            |
                     | item_id               |
                     | event_type            |
                     | transaction_id        |
                     +-----------------------+
                              ↓
                     +-----------------------+
                     |   Category_tree       |
                     +-----------------------+
                     | category_id           |
                     | parentid              |
                     +-----------------------+


---

## 🧪 ETL Job (AWS Glue Script)

The ETL job is built using PySpark via AWS Glue. It:

1. Loads events and item properties from the Glue Data Catalog.
2. Cleans & transforms timestamps and property values.
3. Deduplicates and pivots important properties like `price`, `available`, and `categoryid`.
4. Joins events with item metadata.
5. Builds recursive category hierarchies.
6. Writes Parquet files into partitioned output folders.

### Key Script Paths

```python
partitionKeys = ["event_type", "event_date"]  # Used for Athena partition discovery
```

Output format: `Parquet` with `Snappy` compression.

---

## 🧭 Architecture Diagram

### 🔧 Services Used

* **Amazon S3** – Stores raw and processed data
* **AWS Glue** – ETL processing using PySpark
* **Amazon Athena** – Serverless SQL over processed data

## 🔍 Athena Tables

Make sure your Glue job has written to partitioned folders, then run:

### 1. `processed_events`

```sql
CREATE EXTERNAL TABLE IF NOT EXISTS processed_events (
  event_time TIMESTAMP,
  visitor_id BIGINT,
  item_id BIGINT,
  transaction_id BIGINT
)
PARTITIONED BY (
  event_type STRING,
  event_date STRING
)
STORED AS PARQUET
LOCATION 's3://my-ecommerce-data-2024/processed/enriched_events/';

MSCK REPAIR TABLE processed_events;
```

### 2. `processed_item_properties`

```sql
CREATE EXTERNAL TABLE processed_item_properties (
  property_time TIMESTAMP,
  item_id BIGINT,
  property_name STRING,
  property_value STRING,
  numeric_value FLOAT
)
STORED AS PARQUET
LOCATION 's3://my-ecommerce-data-2024/processed/item_properties/';
```

### 3. `processed_category_tree`

```sql
CREATE EXTERNAL TABLE processed_category_tree (
  category_id BIGINT,
  parent_category_id BIGINT,
  category_path ARRAY<BIGINT>
)
STORED AS PARQUET
LOCATION 's3://my-ecommerce-data-2024/processed/category_hierarchy/';
```

---

## 📊 Sample Queries

### 🔸 Events by Type

```sql
SELECT event_type, COUNT(*) FROM processed_events GROUP BY event_type;
```

### 🔸 Latest Item Properties

```sql
SELECT item_id, MAX(property_time) AS last_seen
FROM processed_item_properties
GROUP BY item_id;
```

### 🔸 Deepest Category Nodes

```sql
SELECT category_id, CARDINALITY(category_path) AS depth
FROM processed_category_tree
ORDER BY depth DESC
LIMIT 5;
```

## ✅ Project Highlights

* ✅ Scalable, serverless batch ETL architecture
* ✅ Automated partitioning for analytics
* ✅ Athena SQL support for analysts & BI tools
* ✅ Real-time extensible with Lambda or Kinesis

---

## 📁 Folder Layout

```
S3
├── raw/
│   ├── events/
│   ├── item_properties/
│   └── category_tree/
├── processed/
│   ├── enriched_events/
│   ├── item_properties/
│   └── category_hierarchy/
└── scripts/
    └── etl_script.py
```

---

## 🏁 Final Thoughts

This architecture supports:

* Unified analytics and ML
* Scalable pipelines
* Extendability into Redshift, QuickSight, or SageMaker

> Built as part of a data engineering challenge – designed for real-world e-commerce scale analytics.
