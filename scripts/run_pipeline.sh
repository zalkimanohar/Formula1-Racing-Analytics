#!/bin/bash

# ============================================================
# RUN PIPELINE (Bronze → Silver → Gold → Complete Batch)
# ============================================================

BASE_DIR="/Users/manoharazalki/F1-Analytics"
NB_DIR="$BASE_DIR/notebooks"
LOG_DIR="$BASE_DIR/scripts"
CONTROL_DIR="$BASE_DIR/data/control/batch_control"

mkdir -p "$LOG_DIR"

BATCH_ID=$1

if [ -z "$BATCH_ID" ]; then
  echo "❌ ERROR: No batch_id provided."
  echo "Usage: ./run_pipeline.sh <batch_id>"
  exit 1
fi

echo "=============================================="
echo "🚀 Starting Pipeline for batch_id = $BATCH_ID"
echo "=============================================="

# -----------------------------------------
# 1. Run Bronze Layer
# -----------------------------------------
echo "▶ Running Bronze Layer..."
papermill "$NB_DIR/01-bronze/01_ingest_circuits.ipynb" \
          "$LOG_DIR/bronze_circuits_$BATCH_ID.ipynb" \
          -p p_batch_id "$BATCH_ID"

papermill "$NB_DIR/01-bronze/02_ingest_races.ipynb" \
          "$LOG_DIR/bronze_races_$BATCH_ID.ipynb" \
          -p p_batch_id "$BATCH_ID"

papermill "$NB_DIR/01-bronze/03_ingest_constructors.ipynb" \
          "$LOG_DIR/bronze_constructors_$BATCH_ID.ipynb" \
          -p p_batch_id "$BATCH_ID"

papermill "$NB_DIR/01-bronze/04_ingest_drivers.ipynb" \
          "$LOG_DIR/bronze_drivers_$BATCH_ID.ipynb" \
          -p p_batch_id "$BATCH_ID"

papermill "$NB_DIR/01-bronze/05_ingest_results.ipynb" \
          "$LOG_DIR/bronze_results_$BATCH_ID.ipynb" \
          -p p_batch_id "$BATCH_ID"

papermill "$NB_DIR/01-bronze/06_ingest_sprints.ipynb" \
          "$LOG_DIR/bronze_sprints_$BATCH_ID.ipynb" \
          -p p_batch_id "$BATCH_ID"

# -----------------------------------------
# 2. Run Silver Layer
# -----------------------------------------
echo "▶ Running Silver Layer..."

papermill "$NB_DIR/02-silver/01_transform_circuits.ipynb" \
          "$LOG_DIR/silver_circuits_$BATCH_ID.ipynb" \
          -p p_batch_id "$BATCH_ID"

papermill "$NB_DIR/02-silver/02_transform_races.ipynb" \
          "$LOG_DIR/silver_races_$BATCH_ID.ipynb" \
          -p p_batch_id "$BATCH_ID"

papermill "$NB_DIR/02-silver/03_transform_constructors.ipynb" \
          "$LOG_DIR/silver_constructors_$BATCH_ID.ipynb" \
          -p p_batch_id "$BATCH_ID"

papermill "$NB_DIR/02-silver/04_transform_drivers.ipynb" \
          "$LOG_DIR/silver_drivers_$BATCH_ID.ipynb" \
          -p p_batch_id "$BATCH_ID"

papermill "$NB_DIR/02-silver/05_transform_results.ipynb" \
          "$LOG_DIR/silver_results_$BATCH_ID.ipynb" \
          -p p_batch_id "$BATCH_ID"

papermill "$NB_DIR/02-silver/06_transform_sprints.ipynb" \
          "$LOG_DIR/silver_sprints_$BATCH_ID.ipynb" \
          -p p_batch_id "$BATCH_ID"

# -----------------------------------------
# 3. Run Gold Layer
# -----------------------------------------
echo "▶ Running Gold Layer..."

papermill "$NB_DIR/03-gold/01_build_dim_races.ipynb" \
          "$LOG_DIR/gold_dim_races_$BATCH_ID.ipynb" \
          -p p_batch_id "$BATCH_ID"

papermill "$NB_DIR/03-gold/02_build_dim_constructors.ipynb" \
          "$LOG_DIR/gold_dim_constructors_$BATCH_ID.ipynb" \
          -p p_batch_id "$BATCH_ID"

papermill "$NB_DIR/03-gold/03_build_dim_drivers.ipynb" \
          "$LOG_DIR/gold_dim_drivers_$BATCH_ID.ipynb" \
          -p p_batch_id "$BATCH_ID"

papermill "$NB_DIR/03-gold/04_build_fact_session_results.ipynb" \
          "$LOG_DIR/gold_fact_results_$BATCH_ID.ipynb" \
          -p p_batch_id "$BATCH_ID"

# -----------------------------------------
# 4. Mark Batch as Completed
# -----------------------------------------
echo "▶ Completing Batch..."

papermill "$NB_DIR/06-orchestration/03.Complete Batch.ipynb" \
          "$LOG_DIR/complete_batch_$BATCH_ID.ipynb" \
          -p p_batch_id "$BATCH_ID"

echo "=============================================="
echo "🎉 Pipeline Completed for batch_id = $BATCH_ID"
echo "=============================================="
