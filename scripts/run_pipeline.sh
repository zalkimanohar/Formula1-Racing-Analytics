#!/bin/bash

set -e
set -o pipefail

run_notebook() {
    notebook_path="$1"

    echo "------------------------------------------------------------"
    echo "▶ Running: $notebook_path"
    echo "------------------------------------------------------------"

    if [ ! -f "$notebook_path" ]; then
        echo "❌ Notebook not found: $notebook_path"
        exit 1
    fi

    papermill "$notebook_path" "/tmp/$(basename "$notebook_path")_executed.ipynb"

    echo "✔ Completed: $notebook_path"
    echo
}


echo "============================================================"
echo "        F1 ANALYTICS PIPELINE — LOCAL EXECUTION
============================================================"

# BRONZE
run_notebook "../notebooks/02-bronze/01_ingest_circuits.ipynb"
run_notebook "../notebooks/02-bronze/02_ingest_races.ipynb"
run_notebook "../notebooks/02-bronze/03_ingest_drivers.ipynb"
run_notebook "../notebooks/02-bronze/04_ingest_constructors.ipynb"
run_notebook "../notebooks/02-bronze/05_ingest_results.ipynb"
run_notebook "../notebooks/02-bronze/06_ingest_sprints.ipynb"

# SILVER
run_notebook "../notebooks/03-silver/01_transform_circuits.ipynb"
run_notebook "../notebooks/03-silver/02_transform_races.ipynb"
run_notebook "../notebooks/03-silver/03_transform_drivers.ipynb"
run_notebook "../notebooks/03-silver/04_transform_constructors.ipynb"
run_notebook "../notebooks/03-silver/05_transform_results.ipynb"
run_notebook "../notebooks/03-silver/06_transform_sprints.ipynb"

# GOLD
run_notebook "../notebooks/04-gold/91_build_ref_nationality_region.ipynb"
run_notebook "../notebooks/04-gold/01_build_dim_races.ipynb"
run_notebook "../notebooks/04-gold/02_build_dim_drivers.ipynb"
run_notebook "../notebooks/04-gold/03_build_dim_constructors.ipynb"
run_notebook "../notebooks/04-gold/04_build_fact_results.ipynb"

echo "============================================================"
echo "        ✔ PIPELINE COMPLETED SUCCESSFULLY
============================================================"
