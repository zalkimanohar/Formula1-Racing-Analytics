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
# 2. Import helpers
# ------------------------------------------------------------
COMMON = f"{BASE}/notebooks/00-common"
sys.path.append(COMMON)
from gold_helpers import write_to_gold

# ------------------------------------------------------------
# 3. Initialize Spark
# ------------------------------------------------------------
spark = (
    SparkSession.builder
        .appName(f"gold_fact_session_results_{BATCH_ID}")
        .config("spark.ui.enabled", "false")
        .config("spark.ui.showConsoleProgress", "false")
        .getOrCreate()
)

# ------------------------------------------------------------
# 4. Define Silver + Gold paths
# ------------------------------------------------------------
silver_results_path      = Path(f"{DATA}/silver/results/results.parquet")
silver_sprints_path      = Path(f"{DATA}/silver/sprints/sprints.parquet")
silver_races_path        = Path(f"{DATA}/silver/races/races.parquet")
silver_circuits_path     = Path(f"{DATA}/silver/circuits/circuits.parquet")
silver_drivers_path      = Path(f"{DATA}/silver/drivers/drivers.parquet")
silver_constructors_path = Path(f"{DATA}/silver/constructors/constructors.parquet")

gold_output = f"{DATA}/gold/fact_session_results/fact_session_results"
print(f"[INFO] Gold output: {gold_output}.parquet")

# ------------------------------------------------------------
# 5. Read Silver
# ------------------------------------------------------------
results_df      = spark.read.parquet(str(silver_results_path)).filter(F.col("batch_id") == BATCH_ID)
races_df        = spark.read.parquet(str(silver_races_path))
circuits_df     = spark.read.parquet(str(silver_circuits_path))
drivers_df      = spark.read.parquet(str(silver_drivers_path))
constructors_df = spark.read.parquet(str(silver_constructors_path))

if silver_sprints_path.exists():
    sprints_df = spark.read.parquet(str(silver_sprints_path)).filter(F.col("batch_id") == BATCH_ID)
else:
    sprints_df = None
    print("[WARN] No sprints.parquet found → using only race results")

print("[INFO] ✔ All available Silver tables read")

# Prepare drivers with full driver_name
drivers_prepared = drivers_df.withColumn(
    "driver_name", 
    F.concat_ws(" ", F.col("given_name"), F.col("family_name"))
)

# ------------------------------------------------------------
# 6. Prepare results (RACE sessions)
# ------------------------------------------------------------
results_clean = (
    results_df.alias("res")
        .join(
            races_df.alias("ra"),
            (F.col("res.season") == F.col("ra.year")) &
            (F.col("res.round")  == F.col("ra.round")),
            "left"
        )
        .join(
            circuits_df.alias("ci"),
            F.col("ra.circuit_id") == F.col("ci.circuit_id"),
            "left"
        )
        .join(drivers_prepared.alias("d"), "driver_id", "left")
        .join(constructors_df.alias("c"), "constructor_id", "left")
        .select(
            # Keys
            F.col("res.season").alias("season"),
            F.col("res.round").alias("round"),
            F.lit("RACE").alias("session_type"),

            # Race / circuit context for dashboard
            F.col("ra.race_name"),
            F.col("ci.circuit_id"),
            F.col("ci.circuit_name"),
            F.col("ci.locality").alias("circuit_location"),
            F.col("ci.country_name").alias("circuit_country"),

            # Metrics
            F.col("res.final_position"),
            F.col("res.grid_position"),
            F.col("res.points"),
            F.col("res.completed_laps").alias("laps"),
            F.col("res.race_date").alias("time"),

            # Status
            F.col("res.status").alias("status"),

            # Driver
            F.col("d.driver_id"),
            F.col("d.driver_name"),
            F.col("d.nationality").alias("driver_nationality"),

            # Constructor
            F.col("c.constructor_id"),
            F.col("c.constructor_name"),
            F.col("c.nationality").alias("constructor_nationality")
        )
)

# ------------------------------------------------------------
# 7. Prepare sprint results (SPRINT sessions)
# ------------------------------------------------------------
if sprints_df is not None:
    sprints_clean = (
        sprints_df.alias("sp")
            .join(
                races_df.alias("ra"),
                (F.col("sp.season") == F.col("ra.year")) &
                (F.col("sp.round")  == F.col("ra.round")),
                "left"
            )
            .join(
                circuits_df.alias("ci"),
                F.col("ra.circuit_id") == F.col("ci.circuit_id"),
                "left"
            )
            .join(drivers_prepared.alias("d"), "driver_id", "left")
            .join(constructors_df.alias("c"), "constructor_id", "left")
            .select(
                F.col("sp.season").alias("season"),
                F.col("sp.round").alias("round"),
                F.lit("SPRINT").alias("session_type"),

                F.col("ra.race_name"),
                F.col("ci.circuit_id"),
                F.col("ci.circuit_name"),
                F.col("ci.locality").alias("circuit_location"),
                F.col("ci.country_name").alias("circuit_country"),

                F.col("sp.final_position"),
                F.col("sp.grid_position"),
                F.col("sp.points"),
                F.col("sp.completed_laps").alias("laps"),
                F.col("sp.race_date").alias("time"),

                F.col("sp.status").alias("status"),

                F.col("d.driver_id"),
                F.col("d.driver_name"),
                F.col("d.nationality").alias("driver_nationality"),

                F.col("c.constructor_id"),
                F.col("c.constructor_name"),
                F.col("c.nationality").alias("constructor_nationality")
            )
    )
    fact_df = results_clean.unionByName(sprints_clean)
else:
    fact_df = results_clean

# ------------------------------------------------------------
# 8. Business key validation
# ------------------------------------------------------------
fact_valid = fact_df.filter(
    "season IS NOT NULL AND round IS NOT NULL AND driver_id IS NOT NULL"
)

# ------------------------------------------------------------
# 9. Deduplicate
# ------------------------------------------------------------
fact_final = fact_valid.dropDuplicates(
    ["season", "round", "driver_id", "session_type"]
)

# ------------------------------------------------------------
# 10. Write to Gold
# ------------------------------------------------------------
write_to_gold(
    fact_final,
    gold_output,
    ["season", "round", "driver_id", "session_type"]
)

print(f"[INFO] ✔ fact_session_results written to: {gold_output}.parquet")

# ------------------------------------------------------------
# 11. Validate
# ------------------------------------------------------------
spark.read.parquet(f"{gold_output}.parquet").show(10, truncate=False)