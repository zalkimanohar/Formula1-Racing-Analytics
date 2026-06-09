#!/bin/bash

# ============================================================
# MAIN ORCHESTRATOR — AUTO-DETECT LATEST BATCH + CLEAN LOGS
# ============================================================

BASE_DIR="/Users/manoharazalki/F1-Analytics"
SCRIPT_DIR="$BASE_DIR/scripts"
LANDING_DIR="$BASE_DIR/data/landing"

# -----------------------------------------
# 0. Clean previous logs
# -----------------------------------------
echo "🧹 Cleaning previous logs..."

if [ -d "$SCRIPT_DIR" ]; then
    find "$SCRIPT_DIR" -maxdepth 1 -type d -name "logs_*" -exec rm -rf {} \;
    find "$SCRIPT_DIR" -maxdepth 1 -type f -name "*.log" -exec rm -f {} \;
fi

echo "✔ Previous logs removed"

# -----------------------------------------
# 1. Create timestamped log folder
# -----------------------------------------
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_DIR="$SCRIPT_DIR/logs_$TIMESTAMP"
mkdir -p "$LOG_DIR"

echo "=============================================="
echo "🚀 Starting MAIN Orchestration"
echo "Log folder: $LOG_DIR"
echo "=============================================="

# -----------------------------------------
# 2. Detect latest batch folder
# -----------------------------------------
LATEST_BATCH=$(ls -1t "$LANDING_DIR" | head -n 1)

if [ -z "$LATEST_BATCH" ]; then
  echo "❌ ERROR: No batch folders found in $LANDING_DIR"
  exit 1
fi

echo "➡ Latest batch detected: $LATEST_BATCH"

# -----------------------------------------
# 3. Run Orchestration (Identify + Create Batch)
# -----------------------------------------
echo "▶ Running Orchestration..."
bash "$SCRIPT_DIR/run_orchestration.sh" \
    > "$LOG_DIR/orchestration.log" 2>&1

if [ $? -ne 0 ]; then
    echo "❌ Orchestration failed. Check $LOG_DIR/orchestration.log"
    exit 1
fi

echo "✔ Orchestration completed"

# -----------------------------------------
# 4. Run Pipeline with detected batch_id
# -----------------------------------------
echo "▶ Running Pipeline for batch_id = $LATEST_BATCH..."
bash "$SCRIPT_DIR/run_pipeline.sh" "$LATEST_BATCH" \
    > "$LOG_DIR/pipeline.log" 2>&1

if [ $? -ne 0 ]; then
    echo "❌ Pipeline failed. Check $LOG_DIR/pipeline.log"
    exit 1
fi

echo "✔ Pipeline completed"

# -----------------------------------------
# 5. Run Dashboard
# -----------------------------------------
echo "▶ Starting Dashboard..."
bash "$SCRIPT_DIR/run_dashboard.sh" \
    > "$LOG_DIR/dashboard.log" 2>&1 &

DASH_PID=$!

echo "✔ Dashboard started (PID: $DASH_PID)"
echo "Log: $LOG_DIR/dashboard.log"

# -----------------------------------------
# 6. Summary
# -----------------------------------------
echo "=============================================="
echo "🎉 MAIN Orchestration Completed Successfully"
echo "Logs saved in: $LOG_DIR"
echo "=============================================="
