import os
import sys
from pathlib import Path
from pyspark.sql.types import (
    StructType, StructField, StringType, DateType
)
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

# ------------------------------------------------------------
# 1. Resolve WORKSPACE + BATCH_ID from environment
# ------------------------------------------------------------
WORKSPACE = os.getenv("WORKSPACE")
BATCH_ID = os.getenv("BATCH_ID")

if not WORKSPACE:
    raise RuntimeError("WORKSPACE environment variable not set")

if not BATCH_ID:
    raise RuntimeError("BATCH_ID environment variable not set")

WORKSPACE = WORKSPACE.rstrip("/")
BASE = WORKSPACE
DATA = f"{BASE}/data"

print(f"[INFO] WORKSPACE = {WORKSPACE}")
print(f"[INFO] BATCH_ID  = {BATCH_ID}")

# ------------------------------------------------------------
# 2. Fix Python import path for 00-common helpers
# ------------------------------------------------------------
sys.path.append(f"{BASE}/notebooks/00-common")

from bronze_helpers import (
    add_ingestion_metadata,
    write_to_bronze
)

# ------------------------------------------------------------
# 3. Define landing + bronze paths
# ------------------------------------------------------------
LANDING_BATCH_DIR = Path(f"{DATA}/landing/{BATCH_ID}")

BRONZE_DIR = Path(f"{DATA}/bronze/drivers")
BRONZE_DIR.mkdir(parents=True, exist_ok=True)

source_file = LANDING_BATCH_DIR / "drivers.json"
target_path = BRONZE_DIR / "drivers.parquet"

print(f"[INFO] Source file: {source_file}")
print(f"[INFO] Target path: {target_path}")

# ------------------------------------------------------------
# 4. Initialize Spark
# ------------------------------------------------------------
spark = (
    SparkSession.builder
        .appName(f"bronze_ingest_drivers_{BATCH_ID}")
        .config("spark.ui.enabled", "false")
        .config("spark.ui.showConsoleProgress", "false")
        .getOrCreate()
)

# ------------------------------------------------------------
# 5. Validate landing file
# ------------------------------------------------------------
if not source_file.exists():
    raise RuntimeError(f"Landing file not found: {source_file}")

# ------------------------------------------------------------
# 6. Schema (nested) - Kept 100% Intact
# ------------------------------------------------------------
name_schema = StructType([
    StructField("givenName", StringType(), True),
    StructField("familyName", StringType(), True),
])

drivers_schema = StructType([
    StructField("driverId", StringType(), True),
    StructField("name", name_schema, True),
    StructField("dateOfBirth", DateType(), True),
    StructField("nationality", StringType(), True),
    StructField("url", StringType(), True)
])

# ------------------------------------------------------------
# 7. Read JSON & Unnest Ergast Wrapper Structure
# ------------------------------------------------------------
raw_df = (
    spark.read
        .format("json")
        .option("multiline", "true")
        .load(str(source_file))
)

# Explode the drivers array from the wrapper and cast/select against your schema
drivers_exploded = raw_df.select(
    F.explode(F.col("MRData.DriverTable.Drivers")).alias("driver_struct")
)

df = drivers_exploded.select(
    F.col("driver_struct.driverId").alias("driverId"),
    F.struct(
        F.col("driver_struct.givenName").alias("givenName"),
        F.col("driver_struct.familyName").alias("familyName")
    ).alias("name"),
    F.col("driver_struct.dateOfBirth").cast(DateType()).alias("dateOfBirth"),
    F.col("driver_struct.nationality").alias("nationality"),
    F.col("driver_struct.url").alias("url")
)

print("[INFO] ✔ Drivers file read successfully")

# ------------------------------------------------------------
# 8. Add ingestion metadata
# ------------------------------------------------------------
df_final = add_ingestion_metadata(df, str(source_file))

print("[INFO] ✔ Metadata added")

# ------------------------------------------------------------
# 9. Write to Bronze
# ------------------------------------------------------------
write_to_bronze(
    df_final,
    str(target_path),
    BATCH_ID
)

print(f"[INFO] ✔ Drivers Bronze written to: {target_path}")

# ------------------------------------------------------------
# 10. Validate
# ------------------------------------------------------------
print("[INFO] Showing sample from Bronze output:")
spark.read.parquet(str(target_path)).show(5)