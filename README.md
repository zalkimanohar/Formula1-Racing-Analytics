
%md

# 🏎️ F1 Race Analytics — Version 2.0  
### End‑to‑End Incremental Data Engineering Pipeline (Local Workspace Edition)

F1‑Race‑2.0 is a complete end‑to‑end data engineering and analytics system built using PySpark, Parquet, notebook‑driven transformations, and shell‑script orchestration.  
It mirrors a Databricks‑style Medallion Architecture but runs entirely on a local laptop workspace.

---

## 🧱 Architecture Overview

### Medallion Layers  
- **Bronze** → Raw ingestion  
- **Silver** → Cleaned, standardized, conformed  
- **Gold** → Dimensional models + Fact tables  

### Orchestration  
- Batch detection  
- Batch creation  
- Pipeline execution  
- Batch completion  
- Dashboard refresh  

### Dashboard  
- Streamlit analytics dashboard  
- Driver, constructor, and race insights  

---

## 📁 Project Structure

<img width="507" height="477" alt="Screenshot 2026-06-09 at 4 35 00 PM" src="https://github.com/user-attachments/assets/58e1b300-2187-49da-b084-1028eecc6e36" />

---

## 🔄 Incremental Batch Processing

Each batch is a folder inside:

data/landing/<batch_id>/

Example:

data/landing/20250101_090000/


The system automatically:

1. Detects the latest batch folder  
2. Creates a new batch entry  
3. Runs Bronze → Silver → Gold  
4. Marks the batch as completed  
5. Refreshes the dashboard  

---

## 🧠 Orchestration Scripts

### main.sh  
Runs the entire system:

- Cleans old logs  
- Detects latest batch  
- Runs orchestration  
- Runs pipeline  
- Starts dashboard  
- Saves logs  

Run:

bash scripts/main.sh


---

### run_orchestration.sh  
Handles:

- Identify Next Batch  
- Create New Batch  

---

### run_pipeline.sh  
Executes:

- Bronze ingestion  
- Silver transformation  
- Gold modeling  
- Batch completion  

Manual run:

bash scripts/run_pipeline.sh <batch_id>


---

### run_dashboard.sh  
Starts the Streamlit dashboard.

---

## 🧪 Pipeline Execution Flow

### Bronze Layer
- Reads raw CSV/JSON files  
- Adds batch metadata  
- Writes raw Parquet  

### Silver Layer
- Cleans data  
- Standardizes schema  
- Fixes types  
- Writes conformed Parquet  

### Gold Layer
Builds:

- dim_races  
- dim_constructors  
- dim_drivers  
- fact_session_results  

---

## 📊 Dashboard

A Streamlit dashboard visualizes:

- Race results  
- Constructor performance  
- Driver statistics  
- Season trends  

Run manually:

bash scripts/run_dashboard.sh


---

## 🛠️ Environment Setup

### Install dependencies

pip install pyspark papermill streamlit pandas


### Configure environment paths  
Inside:

notebooks/00-common/01_environment_config.ipynb


---

## 🚀 Running the Entire System

### Recommended (fully automated)

bash scripts/main.sh


### Manual batch run

bash scripts/run_pipeline.sh 20250101_090000


---

## 🏷️ Versioning

This release is tagged:

v2.0 — F1-Race-2.0


Includes:

- Full local orchestration  
- Auto‑detect batch  
- Auto‑clean logs  
- Updated Gold notebooks  
- Updated environment config  
- Production‑grade shell scripts  

---

## 🧭 Roadmap

- Add Airflow/Dagster orchestration  
- Add unit tests (pytest)  
- Add CI/CD (GitHub Actions)  
- Add data quality checks (Great Expectations)  
- Add historical dashboards  
- Add metadata lineage  

---

## 👨‍💻 Author

**Manohar Anand Zalki**  
Munich, Germany  
MSc Applied Data Science & AI  

---

## 🏁 License

MIT License  
Free to use, modify, and distribute.
