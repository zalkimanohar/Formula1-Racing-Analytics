import os
import sys
from pathlib import Path
from pyspark.sql.types import (
    StructType, StructField, StringType
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

BRONZE_DIR = Path(f"{DATA}/bronze/constructors")
BRONZE_DIR.mkdir(parents=True, exist_ok=True)

source_file = LANDING_BATCH_DIR / "constructors.json"
target_path = BRONZE_DIR / "constructors.parquet"

print(f"[INFO] Source file: {source_file}")
print(f"[INFO] Target path: {target_path}")

# ------------------------------------------------------------
# 4. Initialize Spark
# ------------------------------------------------------------
spark = (
    SparkSession.builder
        .appName(f"bronze_ingest_constructors_{BATCH_ID}")
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
# 6. Schema - Kept 100% Intact
# ------------------------------------------------------------
constructors_schema = StructType([
    StructField("constructorId", StringType(), True),
    StructField("name", StringType(), True),
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

constructors_exploded = raw_df.select(
    F.explode(F.col("MRData.ConstructorTable.Constructors")).alias("constructor_struct")
)

df = constructors_exploded.select(
    F.col("constructor_struct.constructorId").alias("constructorId"),
    F.col("constructor_struct.name").alias("name"),
    F.col("constructor_struct.nationality").alias("nationality"),
    F.col("constructor_struct.url").alias("url")
)

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

print(f"[INFO] ✔ Constructors Bronze written to: {target_path}")

# ------------------------------------------------------------
# 10. Validate
# ------------------------------------------------------------
print("[INFO] Showing sample from Bronze output:")
spark.read.parquet(str(target_path)).show(5)