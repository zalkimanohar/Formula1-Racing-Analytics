# 🏎️ F1 Race Analytics — Version 3.0
### End‑to‑End Medallion Data Engineering Pipeline + Hybrid LLM‑RAG, Neo4j Knowledge Graph & Multi‑Model AI Engine

**F1-Race-3.0** is a complete, privacy-first local data engineering and AI analytics platform built specifically for Formula 1 World Championship data (1950–2025). 

It unifies a **Databricks-style Medallion Architecture** (PySpark, Parquet, shell-script incremental batch orchestration) with an enterprise-grade **Hybrid Vector & Graph RAG system (Neo4j + Vector Store)**, an **Automated Task-Aware Multi-Model Machine Learning Engine** (6 parallel models), and a **local LLM runner via Ollama (Llama 3)**—all accessible through a unified **FastAPI** backend and **Streamlit** analytics & conversational AI dashboard.

---

## 🧱 System Architecture Overview

### 1. Data Engineering Layer (Medallion Architecture)
* **Bronze Layer:** Incremental raw ingestion (CSV/JSON), automated batch detection, and metadata tagging (`batch_id`, timestamps, SHA-256 lineage).
* **Silver Layer:** Schema standardization, data type enforcement, sentinel/outlier flagging, and conformed Parquet generation.
* **Gold Layer:** Star-schema dimensional modeling (`dim_races`, `dim_constructors`, `dim_drivers`, `ref_nationality_region`) and granular fact tables (`fact_session_results`).

### 2. AI, Knowledge Graph & Multi-Model Layer (`Graphic-LlmRag`)
* **Knowledge Graph (`graph_store/`):** Neo4j graph database modeling complex F1 entity relationships (driver-constructor lineages, teammate rivalry chains, circuit histories).
* **Hybrid RAG Engine (`rag_engine/`):** Combines semantic vector retrieval with Neo4j graph traversal and deterministic pandas/Parquet aggregations for zero-hallucination, citation-backed responses.
* **Multi-Model ML Engine (`ml_engine/`):** Automated task-aware training, auto-labeling, evaluation, and model registry supporting 6 parallel baselines for race outcome, podium probability, and pit strategy predictions.
* **Local LLM Inference:** Powered by **Ollama (`llama3`)** running locally for complete data privacy.

### 3. Unified Serving & Dashboard Layer
* **FastAPI Backend (`api/`):** Decoupled REST API exposing RAG query endpoints, graph traversals, and ML inference routes with interactive Swagger docs.
* **Streamlit Dashboard (`LLM_Stremlit/`):** Multi-view interactive analytics dashboard featuring historical telemetry/standings visualizations alongside a ChatGPT-style conversational F1 data assistant.

---

## 📂 Unified Project Directory Structure

```text
F-Race/
├── data/
│   ├── landing/                        # Incremental raw batch dropzones (<batch_id>/)
│   ├── bronze/                         # Raw ingested Parquet tables
│   ├── silver/                         # Cleaned & standardized Parquet tables
│   └── gold/                           # Dimensional & Fact Parquet models
│       ├── dim_constructors/
│       │   └── dim_constructors.parquet
│       ├── dim_drivers/
│       │   └── dim_drivers.parquet
│       ├── dim_races/
│       │   └── dim_races.parquet
│       ├── fact_session_results/
│       │   └── fact_session_results.parquet
│       └── ref_nationality_region/
│           └── ref_nationality_region.parquet
│
├── notebooks/                          # PySpark Medallion transformation notebooks
│   └── 00-common/
│       └── 01_environment_config.ipynb
│
├── scripts/                            # Medallion batch orchestration scripts
│   ├── main.sh
│   ├── run_orchestration.sh
│   ├── run_pipeline.sh
│   └── run_dashboard.sh
│
└── Graphic-LlmRag/                     # Hybrid AI, Graph & Multi-Model Engine
    ├── api/
    │   ├── __init__.py
    │   └── app.py                      # FastAPI server endpoints
    ├── LLM_Stremlit/
    │   ├── __init__.py
    │   └── app.py                      # Unified Streamlit Analytics & AI Chat UI
    ├── graph_store/
    │   ├── __init__.py
    │   └── neo4j_connector.py          # Neo4j Cypher graph ingestion & traversal
    ├── ml_engine/
    │   ├── __init__.py
    │   ├── autolabel.py                # Automated target & feature engineering
    │   ├── evaluator.py                # Cross-model benchmarking
    │   ├── registry/                   # Serialized multi-model artifacts
    │   └── trainer.py                  # Parallel 6-model training pipeline
    ├── rag_engine/
    │   ├── __init__.py
    │   ├── embedder.py                 # Local text/metadata embedding generator
    │   ├── retriever.py                # Hybrid Vector + Graph + SQL/Pandas retriever
    │   └── vector_store.py             # Local vector index management
    ├── scripts/
    │   └── run_pipeline.sh             # AI/Graph indexing & ML training trigger
    ├── requirements.txt
    └── README.md
```

---

## ⚙️ Prerequisites & Environment Setup

### 1. System Requirements
* **Python:** 3.10+
* **Java / Spark:** OpenJDK 11/17 (required for PySpark Medallion transformations)
* **Neo4j:** Local Neo4j Desktop or Docker instance running (`bolt://localhost:7687`)
* **Ollama:** Installed locally for LLM inference

### 2. Install Python Dependencies
Install dependencies for both the PySpark data pipeline and the `Graphic-LlmRag` AI engine:

```bash
# Core Data Engineering packages
pip install pyspark papermill streamlit pandas

# AI, Neo4j, FastAPI & ML Engine packages
cd Graphic-LlmRag
pip install -r requirements.txt
```

### 3. Configure Local Services (Ollama & Neo4j)
1. **Start Neo4j:** Ensure your local Neo4j database is active and update your connection credentials in `Graphic-LlmRag/graph_store/neo4j_connector.py` (or via environment variables `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`).
2. **Start Ollama & Pull Llama 3:**
   ```bash
   ollama pull llama3
   ollama serve
   ```

---

## 🔄 Step 1: Run the Incremental Data Engineering Pipeline

Each incoming data drop resides in `data/landing/<batch_id>/` (e.g., `data/landing/20250101_090000/`).

### Automated Full Pipeline Execution
Runs log cleanup, batch detection, Bronze → Silver → Gold transformations, and batch completion:

```bash
bash scripts/main.sh --workspace "/Users/manoharazalki"
```

### Manual Batch Execution
```bash
export WORKSPACE="/Users/manoharazalki/F1-Analytics"
export BATCH_ID="2025-02"

bash scripts/run_orchestration.sh
bash scripts/run_pipeline.sh
```

---

## 🧠 Step 2: Sync Neo4j Knowledge Graph, Vector Store & ML Registry

Once the Gold Parquet tables are updated, populate the Neo4j graph, refresh vector embeddings, and update the multi-model ML registry:

```bash
cd Graphic-LlmRag
bash scripts/run_pipeline.sh
```

---

## 🚀 Step 3: Launch the FastAPI Backend & Streamlit Dashboard

The AI and analytics layer operates on a decoupled **FastAPI + Streamlit** architecture.

### 1. Start the FastAPI Backend
Open a terminal tab inside `Graphic-LlmRag/` and launch Uvicorn:

```bash
cd Graphic-LlmRag
uvicorn api.app:app --reload --host 127.0.0.1 --port 8000
```
> 🌐 **Interactive Swagger API Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 2. Start the Streamlit Unified Dashboard
Open a second terminal tab inside `Graphic-LlmRag/` and launch Streamlit:

```bash
cd dashboard
streamlit run app.py
```
> 📊 **Streamlit Dashboard & AI Assistant:** [http://localhost:8501](http://localhost:8501)

---

## 📊 Key Dashboard Capabilities

* **Interactive F1 Analytics:** Explore historical driver standings, constructor dominance eras, circuit statistics, and data quality profiling metrics directly from the Gold Parquet layer.
* **Conversational Hybrid LLM-RAG:** Ask complex natural language questions (in English or Spanish) backed by deterministic Gold data figures, Neo4j teammate/constructor relationship graphs, and inline evidence citations.
* **Multi-Model Predictive Insights:** Query real-time podium probabilities and race strategy predictions generated by the 6-model automated ML engine.

---

## 🏷️ Versioning

* **v1.0:** Initial PySpark ETL & Gold dimensional schema
* **v2.0 (`F1-Race-2.0`):** End-to-end incremental batch orchestration, shell automation, and classic Streamlit dashboard
* **v3.0 (`F1-Race-3.0`):** Integration of Neo4j Knowledge Graph, Hybrid Vector/Graph RAG, 6-Model ML Engine, Ollama Llama 3 inference, and FastAPI + Streamlit unified interface

---

## 👨‍💻 Author

**Manohar Anand Zalki**  
Munich, Germany  
MSc Applied Data Science & AI  

---

## 🏁 License

* **Code & Pipeline Architecture:** MIT License — Free to use, modify, and distribute.
* **Underlying Formula 1 Datasets (Jolpica-F1 / Ergast & OpenF1):** Governed by [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) with attribution and [OpenF1](https://openf1.org/).