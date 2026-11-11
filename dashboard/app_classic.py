import streamlit as st
from theme import set_theme
from utils import load_table
import pandas as pd
# Section imports
from sections.executive_summary import render_executive_summary
from sections.rq1_driver_constructor import render_rq1
from sections.rq2_race_outcomes import render_rq2
from sections.rq3_circuit_geography import render_rq3
from sections.rq4_sprint_race import render_rq4
from sections.rq5_cross_dataset import render_rq5

from sections import rq6_graphic_llm_rag

# ---------------------------------------------------------
# 1. PAGE CONFIG + THEME
# ---------------------------------------------------------
st.set_page_config(
    page_title="F1 Analytics Dashboard",
    page_icon="🏎️",
    layout="wide"
)

set_theme()

# ---------------------------------------------------------
# 2. LOAD ALL REQUIRED DATASETS (Gold + Silver)
# ---------------------------------------------------------
@st.cache_data
def load_all_data():
    return {
        "drivers": load_table("drivers"),
        "constructors": load_table("constructors"),
        "races": load_table("races"),
        "results": load_table("results"),
        "circuits": load_table("circuits"),
        "sprints": load_table("sprints"),
    }

data = load_all_data()

# ---------------------------------------------------------
# 3. GLOBAL FILTERS (STORED IN SESSION STATE)
# ---------------------------------------------------------
st.sidebar.title("🔍 Filters")

drivers = data["drivers"]
constructors = data["constructors"]
races = data["races"]
results = data["results"]

# Ensure GOLD schema is correct
if "season" not in races.columns:
    st.error("❌ Races table missing 'season' column — check Gold layer.")
    st.stop()

# Remove 2026/2027 outliers from options if needed
season_list = sorted([s for s in races["season"].dropna().unique() if s != 2027])

# Default seasons
default_seasons = [s for s in [2024, 2025, 2026] if s in season_list]

st.session_state["selected_seasons"] = st.sidebar.multiselect(
    "Season",
    season_list,
    default=default_seasons
)

# Sliders
st.session_state["grid_range"] = st.sidebar.slider("Grid Position", 1, 20, (1, 20))
st.session_state["pos_range"] = st.sidebar.slider("Final Position", 1, 20, (1, 20))
st.session_state["points_range"] = st.sidebar.slider("Points", 0, 30, (0, 30))

# ---------------------------------------------------------
# 4. APPLY GLOBAL FILTERS
# ---------------------------------------------------------
filtered_results = results.copy()

if st.session_state["selected_seasons"] and "season" in filtered_results.columns:
    filtered_results = filtered_results[filtered_results["season"].isin(st.session_state["selected_seasons"])]

g_min, g_max = st.session_state["grid_range"]
p_min, p_max = st.session_state["pos_range"]
pts_min, pts_max = st.session_state["points_range"]

grid_col = "grid_position" if "grid_position" in filtered_results.columns else "grid"
final_col = "final_position" if "final_position" in filtered_results.columns else "position"

if grid_col in filtered_results.columns:
    filtered_results = filtered_results[filtered_results[grid_col].between(g_min, g_max)]
if final_col in filtered_results.columns:
    filtered_results = filtered_results[filtered_results[final_col].between(p_min, p_max)]
if "points" in filtered_results.columns:
    filtered_results = filtered_results[filtered_results["points"].between(pts_min, pts_max)]

# ---------------------------------------------------------
# 5. SIDEBAR NAVIGATION
# ---------------------------------------------------------
page = st.sidebar.radio(
    "Navigate",
    [
        "Executive Summary",
        "RQ1 — Driver & Constructor Insights",
        "RQ2 — Race Outcome Analytics",
        "RQ3 — Circuit Geography",
        "RQ4 — Sprint Race Analysis",
        "RQ5 — Cross‑Dataset Insights",
        "RQ6: Graphic-LLM-RAG & ML Engine"
    ]
)

# ---------------------------------------------------------
# 6. ROUTE TO SELECTED PAGE WITH FILTERED DATA
# ---------------------------------------------------------
filtered_data = {
    **data,
    "results": filtered_results
}

if page == "Executive Summary":
    render_executive_summary(filtered_data)

elif page == "RQ1 — Driver & Constructor Insights":
    render_rq1(filtered_data["results"])

elif page == "RQ2 — Race Outcome Analytics":
    render_rq2(filtered_data)

elif page == "RQ3 — Circuit Geography":
    try:
        res_df = filtered_data["results"].copy()
        races_df = data["races"].copy()

        # Direct, robust join with dim_races on season and round (per schema design)
        if not races_df.empty and "season" in res_df.columns and "round" in res_df.columns:
            races_subset = races_df.drop_duplicates(subset=["season", "round"])
            
            # Drop conflicting columns if they exist in results before merging
            cols_to_drop = [c for c in ["circuit_name", "locality", "country", "race_name", "race_date"] if c in res_df.columns]
            if cols_to_drop:
                res_df = res_df.drop(columns=cols_to_drop)

            res_df = res_df.merge(
                races_subset,
                on=["season", "round"],
                how="left"
            )

        # Standardize column aliases expected by RQ3 section
        if "country" in res_df.columns:
            res_df["circuit_country"] = res_df["country"].fillna("International")
        else:
            res_df["circuit_country"] = "International"

        if "circuit_name" not in res_df.columns:
            if "race_name" in res_df.columns:
                res_df["circuit_name"] = res_df["race_name"]
            else:
                res_df["circuit_name"] = "Grand Prix Circuit"
        else:
            res_df["circuit_name"] = res_df["circuit_name"].fillna("Grand Prix Circuit")

        render_rq3(res_df)
    except Exception as e:
        st.error(f"Error loading RQ3 Circuit Geography data: {e}")

elif page == "RQ4 — Sprint Race Analysis":
    render_rq4(filtered_data["results"])

elif page == "RQ5 — Cross‑Dataset Insights":
    render_rq5(filtered_data)

elif page == "RQ6: Graphic-LLM-RAG & ML Engine":
    rq6_graphic_llm_rag.render()

# ---------------------------------------------------------
# 7. FOOTER
# ---------------------------------------------------------
st.markdown("---")
st.markdown("### Built by SRH F1 Student Group — F1 Analytics Platform 🚀")