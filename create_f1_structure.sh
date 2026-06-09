#!/bin/bash

# Create base directory
mkdir -p F1-Analytics/notebooks
mkdir -p F1-Analytics/scripts
mkdir -p F1-Analytics/dashboard

# -----------------------------
# 00-common
# -----------------------------
mkdir -p F1-Analytics/notebooks/00-common
touch F1-Analytics/notebooks/00-common/01_environment_config.ipynb
touch F1-Analytics/notebooks/00-common/02_bronze_helpers.ipynb
ls

# -----------------------------
# 01-setup
# -----------------------------
mkdir -p F1-Analytics/notebooks/01-setup
touch F1-Analytics/notebooks/01-setup/01_setup_project_environment.ipynb
touch F1-Analytics/notebooks/01-setup/02_setup_batch_events.ipynb

# -----------------------------
# 02-bronze
# -----------------------------
mkdir -p F1-Analytics/notebooks/02-bronze
touch F1-Analytics/notebooks/02-bronze/01_ingest_circuits.ipynb
touch F1-Analytics/notebooks/02-bronze/02_ingest_races.ipynb
touch F1-Analytics/notebooks/02-bronze/03_ingest_drivers.ipynb
touch F1-Analytics/notebooks/02-bronze/04_ingest_constructors.ipynb
touch F1-Analytics/notebooks/02-bronze/05_ingest_results.ipynb
touch F1-Analytics/notebooks/02-bronze/06_ingest_sprints.ipynb

# -----------------------------
# 03-silver
# -----------------------------
mkdir -p F1-Analytics/notebooks/03-silver
touch F1-Analytics/notebooks/03-silver/01_transform_circuits.ipynb
touch F1-Analytics/notebooks/03-silver/02_transform_races.ipynb
touch F1-Analytics/notebooks/03-silver/03_transform_drivers.ipynb
touch F1-Analytics/notebooks/03-silver/04_transform_constructors.ipynb
touch F1-Analytics/notebooks/03-silver/05_transform_results.ipynb
touch F1-Analytics/notebooks/03-silver/06_transform_sprints.ipynb

# -----------------------------
# 04-gold
# -----------------------------
mkdir -p F1-Analytics/notebooks/04-gold
touch F1-Analytics/notebooks/04-gold/01_build_dim_races.ipynb
touch F1-Analytics/notebooks/04-gold/02_build_dim_drivers.ipynb
touch F1-Analytics/notebooks/04-gold/03_build_dim_constructors.ipynb
touch F1-Analytics/notebooks/04-gold/04_build_fact_results.ipynb
touch F1-Analytics/notebooks/04-gold/05_build_fact_sprints.ipynb

# -----------------------------
# 05-analytics
# -----------------------------
mkdir -p F1-Analytics/notebooks/05-analytics
touch F1-Analytics/notebooks/05-analytics/01_driver_standings.ipynb
touch F1-Analytics/notebooks/05-analytics/02_constructor_standings.ipynb
touch F1-Analytics/notebooks/05-analytics/03_circuit_competitiveness.ipynb
touch F1-Analytics/notebooks/05-analytics/04_sprint_vs_race.ipynb
touch F1-Analytics/notebooks/05-analytics/05_strategy_efficiency.ipynb

# -----------------------------
# Scripts
# -----------------------------
touch F1-Analytics/scripts/run_pipeline.sh

# -----------------------------
# Dashboard
# -----------------------------
touch F1-Analytics/dashboard/app.py

echo "F1-Analytics project structure created successfully!"
