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
        .appName(f"silver_transform_sprints_{BATCH_ID}")
        .config("spark.ui.enabled", "false")
        .config("spark.ui.showConsoleProgress", "false")
        .getOrCreate()
)

# ------------------------------------------------------------
# 4. Define Bronze + Silver paths
# ------------------------------------------------------------
bronze_path = Path(f"{DATA}/bronze/sprints/sprints.parquet")
silver_dir = Path(f"{DATA}/silver/sprints")
silver_dir.mkdir(parents=True, exist_ok=True)

silver_output = silver_dir / "sprints.parquet"

print(f"[INFO] Bronze path: {bronze_path}")
print(f"[INFO] Silver path: {silver_output}")

# ------------------------------------------------------------
# 5. Read Bronze (ONLY this batch)
# ------------------------------------------------------------
sprints_df = (
    spark.read.parquet(str(bronze_path))
    .filter(F.col("batch_id") == BATCH_ID)
)

print("[INFO] ✔ Bronze sprints read")

# ------------------------------------------------------------
# 6. Select & Rename columns directly from flattened Bronze data
# ------------------------------------------------------------
sprints_selected_df = sprints_df.select(
    "season",
    "round",
    F.col("constructorId").alias("constructor_id"),
    F.col("driverId").alias("driver_id"),
    F.col("raceName").alias("race_name"),
    F.col("date").alias("race_date"),
    F.col("grid").alias("grid_position"),
    F.col("laps").alias("completed_laps"),
    F.col("number").alias("car_number"),
    "points",
    F.col("position").alias("final_position"),
    F.col("positionText").alias("final_position_text"),
    "status",
    "ingest_timestamp",
    "source_file",
    "batch_id"
)

# ------------------------------------------------------------
# 7. Business key validation
# ------------------------------------------------------------
sprints_valid_df = sprints_selected_df.filter(
    "season IS NOT NULL AND round IS NOT NULL AND constructor_id IS NOT NULL AND driver_id IS NOT NULL"
)

# ------------------------------------------------------------
# 8. Remove duplicates
# ------------------------------------------------------------
sprints_distinct_df = sprints_valid_df.dropDuplicates(
    ["season", "round", "constructor_id", "driver_id"]
)

# ------------------------------------------------------------
# 9. Title Case transformations
# ------------------------------------------------------------
sprints_final_df = (
    sprints_distinct_df
        .withColumn("race_name", F.initcap("race_name"))
)

# ------------------------------------------------------------
# 10. Write to Silver (batch‑aware)
# ------------------------------------------------------------
write_to_silver(
    sprints_final_df,
    str(silver_output),
    BATCH_ID
)

print(f"[INFO] ✔ Sprints Silver written: {silver_output}")

# ------------------------------------------------------------
# 11. Validate
# ------------------------------------------------------------
spark.read.parquet(str(silver_output)).show(5, truncate=False)