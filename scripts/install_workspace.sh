#!/bin/bash

# ============================================================
# F1-Race-2.0 — WORKSPACE INSTALLATION SCRIPT
# Prepares a new machine with all required dependencies.
# ============================================================

echo "=============================================="
echo "🏎️  Installing F1-Race-2.0 Workspace"
echo "=============================================="

# -----------------------------------------
# 1. Check Python
# -----------------------------------------
echo "🔍 Checking Python installation..."

if ! command -v python3 &> /dev/null
then
    echo "❌ Python3 not found. Please install Python 3.9+ and rerun."
    exit 1
fi

echo "✔ Python3 found: $(python3 --version)"

# -----------------------------------------
# 2. Create Virtual Environment (optional but recommended)
# -----------------------------------------
echo "🔧 Creating virtual environment (venv)..."

python3 -m venv f1env
source f1env/bin/activate

echo "✔ Virtual environment activated"

# -----------------------------------------
# 3. Upgrade pip
# -----------------------------------------
echo "⬆ Upgrading pip..."
pip install --upgrade pip

# -----------------------------------------
# 4. Install Required Libraries
# -----------------------------------------
echo "📦 Installing required Python libraries..."

pip install pyspark
pip install pandas
pip install papermill
pip install streamlit
pip install pyarrow
pip install notebook
pip install jupyter

echo "✔ All required libraries installed"

# -----------------------------------------
# 5. Validate Folder Structure
# -----------------------------------------
echo "📁 Validating workspace folder structure..."

BASE_DIR="$(pwd)"

REQUIRED_DIRS=(
    "$BASE_DIR/data"
    "$BASE_DIR/data/landing"
    "$BASE_DIR/data/bronze"
    "$BASE_DIR/data/silver"
    "$BASE_DIR/data/gold"
    "$BASE_DIR/data/control"
    "$BASE_DIR/notebooks"
    "$BASE_DIR/scripts"
)

for DIR in "${REQUIRED_DIRS[@]}"; do
    if [ ! -d "$DIR" ]; then
        echo "📂 Creating missing directory: $DIR"
        mkdir -p "$DIR"
    fi
done

echo "✔ Folder structure validated"

# -----------------------------------------
# 6. Final Summary
# -----------------------------------------
echo "=============================================="
echo "🎉 Workspace Setup Complete!"
echo "Activate environment using:"
echo "   source f1env/bin/activate"
echo ""
echo "Run the full pipeline using:"
echo "   bash scripts/main.sh"
echo "=============================================="
