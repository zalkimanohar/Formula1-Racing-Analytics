import streamlit as st

def render_summary():
    st.markdown("## 🟫 EXECUTIVE SUMMARY")

    st.markdown("""
This dashboard provides a unified, multi‑layered analysis of Formula 1 performance across drivers,
constructors, circuits, sprint sessions, and race execution.

Each section answers a specific research question:

- **RQ1** — Driver & Constructor Performance  
- **RQ2** — Race Execution & Outcome Drivers  
- **RQ3** — Circuit & Geographical Effects  
- **RQ4** — Sprint–Race Performance Relationship  
- **RQ5** — Advanced Cross‑Dataset Insights  

Global filters (season, circuit, driver, constructor, grid, final position, points, status)
allow consistent slicing of all visuals, enabling both high‑level executive views and
deep analytical exploration.

This structure mirrors your Databricks F1 Performance Intelligence Dashboard, but runs locally
in Python/Streamlit—ideal for viva, portfolio, and code review.
""")
