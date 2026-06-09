# 🏎️ F1‑Analytics  
### End‑to‑End Formula‑1 Data Engineering & Analytics Platform  
**PySpark Pipeline | Medallion Architecture | Star Schema | Streamlit Dashboards | Incremental Loads**

This repository contains a complete Formula‑1 data engineering and analytics system built using:

- PySpark (ETL + Medallion Architecture)
- Parquet‑based data lake (Bronze/Silver/Gold)
- Star Schema modeling
- Incremental batch ingestion
- Streamlit dashboards (RQ1–RQ5 + Business Insights)
- Automated pipeline execution via shell scripts

The project transforms 75 years of FIA racing data (1950–2025) into a **business‑ready intelligence platform**.

---

# 🚀 1. Project Overview

This project answers the central business question:

> **How do driver performance, constructor engineering strength, circuit characteristics, and race conditions influence Formula‑1 outcomes?**

The system includes:

- A **full ETL pipeline** (landing → bronze → silver → gold)
- A **star schema** optimized for analytics
- Two dashboards:
  - `/dashboard` → RQ1–RQ5 academic dashboard  
  - `/dashboard-1` → Business insights dashboard  
- Automated execution via `scripts/main.sh`

---

# 🎯 2. Key Features

### ✔ End‑to‑End Data Pipeline  
- Schema‑enforced ingestion  
- Cleaning, standardization, deduplication  
- Incremental batch processing  
- Medallion architecture (Bronze/Silver/Gold)

### ✔ Analytical Star Schema  
- `dim_drivers`  
- `dim_constructors`  
- `dim_races`  
- `fact_session_results`  
- `ref_nationality_region`

### ✔ Two Streamlit Dashboards  
- **RQ1–RQ5 Analytics Dashboard**  
- **Business Insights Dashboard** (Drivers, Constructors, Tracks, Seasons, Predictions)

### ✔ Automated Execution  
- `main.sh` → orchestrates pipeline + dashboard  
- `run_pipeline.sh` → executes all notebooks via papermill  
- `run_dashboard.sh` → launches Streamlit  

---

# 📂 3. Folder Structure
- <It is in the tree.txt>

---

# 🧠 4. Research Questions (RQ1–RQ5)

### **RQ1 — Driver & Constructor Performance**
- Dominance, consistency, improvement  
- Driver–constructor synergy  

### **RQ2 — Race Outcome Drivers**
- Grid vs final position  
- DNFs & reliability  

### **RQ3 — Circuit & Geography Effects**
- Circuit competitiveness  
- Region‑wise performance patterns  

### **RQ4 — Sprint ↔ Race Relationship**
- Sprint results → Race results  
- Sprint points → Season points  

### **RQ5 — Cross‑Dataset Insights**
- Multi‑factor interactions  
- Circuit × Driver × Constructor patterns  

---

# 🏗️ 5. Architecture

### **CRISP‑DM Workflow**
- Business Understanding  
- Data Understanding  
- Data Preparation  
- Modeling  
- Evaluation  
- Deployment  

### **Medallion Architecture**
- **Bronze:** Raw structured parquet  
- **Silver:** Cleaned, standardized  
- **Gold:** Star schema for analytics  

### **Star Schema**
fact_session_results
│
├── dim_drivers
├── dim_constructors
├── dim_races
└── ref_nationality_region


---

# 🛠️ 6. Installation

### Install required libraries
pip install pandas numpy pyarrow fastparquet plotly streamlit pyspark python-dateutil pytz tqdm
pip install jupyterlab notebook ipykernel


---

# ▶️ 7. Running the System

### **Run the entire system (pipeline + dashboard)**
cd scripts
sh main.sh


### **Run only the ETL pipeline**
cd scripts
sh run_pipeline.sh


### **Run only the dashboard**
cd scripts
sh run_dashboard.sh


---

# 📊 8. Gold Layer Tables

### **fact_session_results**
- Race + Sprint results  
- Points, positions, flags  

### **dim_drivers**
- Driver attributes  
- Nationality, DOB, experience  

### **dim_constructors**
- Constructor metadata  
- Team nationality  

### **dim_races**
- Season, round, circuit metadata  

### **ref_nationality_region**
- Region mapping for drivers  

---

# 📌 9. Key Insights

- Constructor engineering strength is the strongest predictor of success  
- Sprint performance predicts race outcomes  
- Circuit competitiveness varies widely  
- Driver consistency > peak performance  
- Geography influences long‑term patterns  

---

# ⚠️ 10. Limitations

- Sprint data only from 2021 onward  
- No weather or pit‑stop data  
- Historical data quality varies (1950–1970)  

---

# 🔮 11. Future Enhancements

- Integrate weather & pit‑stop analytics  
- Add telemetry‑based performance metrics  
- Build predictive ML models  
- Deploy dashboard as a cloud service  

---

# 🙌 12. Author

**Manohar Anand Zalki**  
MSc Applied Data Science & AI — SRH Munich  
2026

# Formula1-Racing-Analytics
