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
        .appName(f"silver_transform_results_{BATCH_ID}")
        .config("spark.ui.enabled", "false")
        .config("spark.ui.showConsoleProgress", "false")
        .getOrCreate()
)

# ------------------------------------------------------------
# 4. Define Bronze + Silver paths
# ------------------------------------------------------------
bronze_path = Path(f"{DATA}/bronze/results/results.parquet")
silver_dir = Path(f"{DATA}/silver/results")
silver_dir.mkdir(parents=True, exist_ok=True)

silver_output = silver_dir / "results.parquet"

print(f"[INFO] Bronze path: {bronze_path}")
print(f"[INFO] Silver path: {silver_output}")

# ------------------------------------------------------------
# 5. Read Bronze (ONLY this batch)
# ------------------------------------------------------------
results_df = (
    spark.read.parquet(str(bronze_path))
    .filter(F.col("batch_id") == BATCH_ID)
)

print("[INFO] ✔ Bronze results read")

# ------------------------------------------------------------
# 6. Unnest Ergast JSON Wrapper Structure
# ------------------------------------------------------------
races_exploded = results_df.withColumn("race", F.explode(F.col("MRData.RaceTable.Races")))
results_exploded = races_exploded.withColumn("result", F.explode(F.col("race.Results")))

flattened_df = results_exploded.select(
    F.col("race.season").cast("int").alias("season"),
    F.col("race.round").cast("int").alias("round"),
    F.col("result.Constructor.constructorId").alias("constructor_id"),
    F.col("result.Driver.driverId").alias("driver_id"),
    F.col("race.raceName").alias("race_name"),
    F.col("race.date").alias("race_date"),
    F.col("result.grid").cast("int").alias("grid"),
    F.col("result.laps").cast("int").alias("laps"),
    F.col("result.number").cast("int").alias("number"),
    F.col("result.points").cast("float").alias("points"),
    F.col("result.position").cast("int").alias("position"),
    F.col("result.positionText").alias("positionText"),
    F.col("result.status").alias("status"),
    F.col("ingest_timestamp"),
    F.col("source_file"),
    F.col("batch_id")
)

# ------------------------------------------------------------
# 7. Standardize + rename columns
# ------------------------------------------------------------
results_renamed_df = (
    flattened_df
        .withColumnRenamed("positionText", "final_position_text")
        .withColumnRenamed("position", "final_position")
        .withColumnRenamed("grid", "grid_position")
        .withColumnRenamed("laps", "completed_laps")
        .withColumnRenamed("number", "car_number")
)

# ------------------------------------------------------------
# 8. Business key validation
# ------------------------------------------------------------
results_valid_df = results_renamed_df.filter(
    "season IS NOT NULL AND round IS NOT NULL AND constructor_id IS NOT NULL AND driver_id IS NOT NULL"
)

# ------------------------------------------------------------
# 9. Remove duplicates
# ------------------------------------------------------------
results_distinct_df = results_valid_df.dropDuplicates(
    ["season", "round", "constructor_id", "driver_id"]
)

# ------------------------------------------------------------
# 10. Title Case transformations
# ------------------------------------------------------------
results_final_df = (
    results_distinct_df
        .withColumn("race_name", F.initcap("race_name"))
)

# ------------------------------------------------------------
# 11. Write to Silver (batch‑aware)
# ------------------------------------------------------------
write_to_silver(
    results_final_df,
    str(silver_output),
    BATCH_ID
)

print(f"[INFO] ✔ Results Silver written: {silver_output}")

# ------------------------------------------------------------
# 12. Validate
# ------------------------------------------------------------
spark.read.parquet(str(silver_output)).show(5, truncate=False)