#!/bin/bash

# ============================================================
# RUN ORCHESTRATION (Identify → Create → Run Pipeline → Complete)
# ============================================================

BASE_DIR="/Users/manoharazalki/F1-Analytics"
NB_DIR="$BASE_DIR/notebooks"
LOG_DIR="$BASE_DIR/scripts"

mkdir -p "$LOG_DIR"

echo "=============================================="
echo "🔍 Starting Orchestration"
echo "=============================================="

# -----------------------------------------
# 1. Identify Next Batch
# -----------------------------------------
papermill "$NB_DIR/06-orchestration/01.Identify Next Batch.ipynb" \
          "$LOG_DIR/identify_next_batch.ipynb"

# Extract next_batch from notebook output
NEXT_BATCH=$(python3 - <<EOF
import json
import papermill as pm

nb = pm.read_notebook("$LOG_DIR/identify_next_batch.ipynb")
for cell in nb.cells:
    if cell.cell_type == "code":
        if "next_batch" in cell.outputs[0].text:
            print(cell.outputs[0].text.split(":")[1].strip())
EOF
)

if [ -z "$NEXT_BATCH" ] || [ "$NEXT_BATCH" == "None" ]; then
  echo "⚠ No new batch found. Exiting."
  exit 0
fi

echo "➡ Next batch identified: $NEXT_BATCH"

# -----------------------------------------
# 2. Create New Batch
# -----------------------------------------
papermill "$NB_DIR/06-orchestration/02.Create New Batch.ipynb" \
          "$LOG_DIR/create_batch_$NEXT_BATCH.ipynb" \
          -p p_batch_id "$NEXT_BATCH"

# -----------------------------------------
# 3. Run Full Pipeline
# -----------------------------------------
bash "$BASE_DIR/scripts/run_pipeline.sh" "$NEXT_BATCH"

echo "=============================================="
echo "🎯 Orchestration Completed"
echo "=============================================="
