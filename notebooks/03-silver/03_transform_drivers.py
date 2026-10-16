import os
import sys
from pathlib import Path
from pyspark.sql import functions as F
from pyspark.sql import SparkSession

# ------------------------------------------------------------
# 1. Resolve WORKSPACE + BATCH_ID
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
# 2. Import helpers from 00-common
# ------------------------------------------------------------
COMMON = f"{BASE}/notebooks/00-common"
sys.path.append(COMMON)

from silver_helpers import write_to_silver

# ------------------------------------------------------------
# 3. Initialize Spark
# ------------------------------------------------------------
spark = (
    SparkSession.builder
        .appName(f"silver_transform_drivers_{BATCH_ID}")
        .config("spark.ui.enabled", "false")
        .config("spark.ui.showConsoleProgress", "false")
        .getOrCreate()
)

# ------------------------------------------------------------
# 4. Define Bronze + Silver paths
# ------------------------------------------------------------
bronze_path = Path(f"{DATA}/bronze/drivers/drivers.parquet")
silver_dir = Path(f"{DATA}/silver/drivers")
silver_dir.mkdir(parents=True, exist_ok=True)

silver_output = silver_dir / "drivers.parquet"

print(f"[INFO] Bronze path: {bronze_path}")
print(f"[INFO] Silver path: {silver_output}")

# ------------------------------------------------------------
# 5. Read Bronze (ONLY this batch)
# ------------------------------------------------------------
drivers_df = (
    spark.read.parquet(str(bronze_path))
    .filter(F.col("batch_id") == BATCH_ID)
)

print("[INFO] ✔ Bronze drivers read")
drivers_df.show(5, truncate=False)

"""
# ------------------------------------------------------------
# 6. Flatten nested name struct
# ------------------------------------------------------------
drivers_flat_df = (
    drivers_df
        .withColumn("given_name", F.col("name.givenName"))
        .withColumn("family_name", F.col("name.familyName"))
        .drop("name")
)

# ------------------------------------------------------------
# 7. Select required columns
# ------------------------------------------------------------
drivers_selected_df = drivers_flat_df.select(
    "driverId",
    "given_name",
    "family_name",
    "dateOfBirth",
    "nationality",
    "url",
    "ingest_timestamp",
    "source_file",
    "batch_id"
)
"""
# ------------------------------------------------------------
# 6. Flatten nested name struct & extract fields safely
# ------------------------------------------------------------
drivers_flat_df = (
    drivers_df
        .withColumn("given_name", F.coalesce(F.col("name.givenName"), F.lit("Unknown")))
        .withColumn("family_name", F.coalesce(F.col("name.familyName"), F.lit("Unknown")))
        .withColumn("date_of_birth", F.coalesce(F.col("dateOfBirth"), F.lit(None)))
        .withColumn("nationality_raw", F.coalesce(F.col("nationality"), F.lit("Unknown")))
        .withColumn("driver_url", F.coalesce(F.col("url"), F.lit(None)))
)

# ------------------------------------------------------------
# 7. Select required columns safely
# ------------------------------------------------------------
drivers_selected_df = drivers_flat_df.select(
    F.col("driverId").alias("driver_id"),
    "given_name",
    "family_name",
    "date_of_birth",
    F.col("nationality_raw").alias("nationality"),
    "driver_url",
    "ingest_timestamp",
    "source_file",
    "batch_id"
)

# ------------------------------------------------------------
# 8. Standardize + rename columns
# ------------------------------------------------------------
drivers_renamed_df = (
    drivers_selected_df
        .withColumnRenamed("driverId", "driver_id")
        .withColumnRenamed("dateOfBirth", "date_of_birth")
)

# ------------------------------------------------------------
# 9. Business key validation
# ------------------------------------------------------------
drivers_valid_df = drivers_renamed_df.filter("driver_id IS NOT NULL")

# ------------------------------------------------------------
# 10. Remove duplicates
# ------------------------------------------------------------
drivers_distinct_df = drivers_valid_df.dropDuplicates(["driver_id"])

# ------------------------------------------------------------
# 11. Title Case transformations
# ------------------------------------------------------------
drivers_final_df = (
    drivers_distinct_df
        .withColumn("given_name", F.initcap("given_name"))
        .withColumn("family_name", F.initcap("family_name"))
        .withColumn("nationality", F.initcap("nationality"))
)

# ------------------------------------------------------------
# 12. Write to Silver (batch‑aware)
# ------------------------------------------------------------
write_to_silver(
    drivers_final_df,
    str(silver_output),
    BATCH_ID
)

print(f"[INFO] ✔ Drivers Silver written: {silver_output}")

# ------------------------------------------------------------
# 13. Validate
# ------------------------------------------------------------
spark.read.parquet(str(silver_output)).show(5, truncate=False)
