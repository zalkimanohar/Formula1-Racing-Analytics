#!/bin/bash
set -e

# ------------------------------------------------------------
# 0. Resolve WORKSPACE
# ------------------------------------------------------------
if [ -z "$1" ] && [ -z "$WORKSPACE" ]; then
    echo "❌ ERROR: WORKSPACE not provided."
    echo "Usage: bash run_orchestration.sh /path/to/F1-Analytics"
    exit 1
fi

if [ -n "$1" ]; then
    export WORKSPACE="$1"
fi

WORKSPACE="${WORKSPACE%/}"
BASE="$WORKSPACE"

# Use python3 where it works (macOS/Linux), otherwise python (Windows).
if python3 -c "import sys" >/dev/null 2>&1; then PY=python3; else PY=python; fi

# ------------------------------------------------------------
# 1. Setup logs folder + log file
# ------------------------------------------------------------
SCRIPTS="$BASE/scripts"
LOG_DIR="$SCRIPTS/logs"
mkdir -p "$LOG_DIR"

TS=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$LOG_DIR/orchestration_$TS.log"

# Everything printed from now on goes to both console + log
exec > >(tee -a "$LOG_FILE") 2>&1

echo "===================================="
echo "🚀 Starting Orchestration Pipeline"
echo "===================================="
echo "✔ WORKSPACE = $WORKSPACE"
echo "✔ LOG FILE  = $LOG_FILE"
echo ""

# ------------------------------------------------------------
# 2. Define orchestration script paths
# ------------------------------------------------------------
ORCH="$BASE/notebooks/06-orchestration"

CREATE_TABLES="$ORCH/00_create_control_tables.py"
IDENTIFY="$ORCH/01_identify_next_batch.py"
CREATE="$ORCH/02_create_new_batch.py"
COMPLETE="$ORCH/03_complete_batch.py"

# ------------------------------------------------------------
# 3. Ensure control table exists
# ------------------------------------------------------------
echo "🔍 Step 1 — Checking control table..."
"$PY" "$CREATE_TABLES" --workspace "$WORKSPACE"
echo ""

# ------------------------------------------------------------
# 4. Identify next batch
# ------------------------------------------------------------
echo "🔍 Step 2 — Identifying next batch..."
IDENTIFY_OUTPUT=$("$PY" "$IDENTIFY" --workspace "$WORKSPACE")
echo "$IDENTIFY_OUTPUT"
echo ""

P_BATCH_ID=$(echo "$IDENTIFY_OUTPUT" | grep "p_batch_id" | awk '{print $2}')
HAS_BATCH=$(echo "$IDENTIFY_OUTPUT" | grep "has_batch" | awk '{print $2}')

if [ "$HAS_BATCH" != "true" ]; then
    echo "⏹ No READY batch found. Stopping orchestration."
    exit 0
fi

echo "✔ Batch detected: $P_BATCH_ID"
export BATCH_ID="$P_BATCH_ID"
echo ""

# ------------------------------------------------------------
# 5. Create new batch entry
# ------------------------------------------------------------
echo "📝 Step 3 — Creating new batch entry..."
"$PY" "$CREATE" --workspace "$WORKSPACE" --batch_id "$BATCH_ID"
echo ""

# ------------------------------------------------------------
# 6. Run pipeline for this batch
# ------------------------------------------------------------
echo "🚦 Step 4 — Running pipeline for batch: $BATCH_ID"
bash "$BASE/scripts/run_pipeline.sh" "$WORKSPACE" "$BATCH_ID" >> "$LOG_FILE" 2>&1
echo ""

# ------------------------------------------------------------
# 7. Mark batch as complete
# ------------------------------------------------------------
echo "🏁 Step 5 — Completing batch..."
"$PY" "$COMPLETE" --workspace "$WORKSPACE" --batch_id "$BATCH_ID"
echo ""

echo "===================================="
echo "🎉 Orchestration Completed Successfully"
echo "Batch: $BATCH_ID"
echo "Log saved at: $LOG_FILE"
echo "===================================="
