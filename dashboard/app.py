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
# 2. LOAD ALL DATASETS (Gold + Silver)
# ---------------------------------------------------------
@st.cache_data
def load_all_data():
    drivers = load_table("drivers")
    constructors = load_table("constructors")
    races = load_table("races")
    results = load_table("results")
    circuits = load_table("circuits")
    sprints = load_table("sprints")
    nationality = load_table("nationality")

    # Global Dimension Enrichment on fact_session_results
    if not results.empty:
        if not drivers.empty and "driver_id" in results.columns and "driver_id" in drivers.columns:
            d_sub = drivers.drop_duplicates(subset=["driver_id"]).copy()
            if "driver_name" not in d_sub.columns and "family_name" in d_sub.columns:
                d_sub["driver_name"] = (d_sub.get("given_name", "").fillna("") + " " + d_sub["family_name"].fillna("")).str.strip()
            merge_cols = [c for c in ["driver_id", "driver_name", "nationality"] if c in d_sub.columns and (c not in results.columns or c == "driver_id")]
            results = results.merge(d_sub[merge_cols], on="driver_id", how="left")

        if not constructors.empty and "constructor_id" in results.columns and "constructor_id" in constructors.columns:
            c_sub = constructors.drop_duplicates(subset=["constructor_id"]).copy()
            if "constructor_name" in c_sub.columns and "constructor_name" not in results.columns:
                results = results.merge(c_sub[["constructor_id", "constructor_name"]], on="constructor_id", how="left")

    return {
        "drivers": drivers,
        "constructors": constructors,
        "races": races,
        "results": results,
        "circuits": circuits,
        "sprints": sprints,
        "nationality": nationality,
    }

data = load_all_data()

# ---------------------------------------------------------
# 3. GLOBAL FILTERS (STORED IN SESSION STATE)
# ---------------------------------------------------------
st.sidebar.title("🔍 Filters")

races = data["races"]
results = data["results"]
sprints = data["sprints"]

if "season" not in races.columns and not results.empty and "season" in results.columns:
    races["season"] = results["season"]

if "season" not in races.columns:
    st.error("❌ Races table missing 'season' column — check Gold layer.")
    st.stop()

season_list = sorted([s for s in races["season"].dropna().unique() if s != 2027])
default_seasons = [s for s in [2024, 2025, 2026] if s in season_list]
if not default_seasons and season_list:
    default_seasons = [season_list[-1]]

selected_seasons = st.sidebar.multiselect(
    "Season",
    season_list,
    default=default_seasons
)
st.session_state["selected_seasons"] = selected_seasons

# Dynamically determine max grid/position for selected seasons to prevent out-of-bounds slider clipping
temp_res = results[results["season"].isin(selected_seasons)] if selected_seasons and "season" in results.columns else results
max_grid_val = int(temp_res["grid_position"].max()) if not temp_res.empty and "grid_position" in temp_res.columns else (int(temp_res["grid"].max()) if not temp_res.empty and "grid" in temp_res.columns else 35)
max_pos_val = int(temp_res["final_position"].max()) if not temp_res.empty and "final_position" in temp_res.columns else (int(temp_res["position"].max()) if not temp_res.empty and "position" in temp_res.columns else 35)

max_grid_val = max(20, min(max_grid_val, 40))
max_pos_val = max(20, min(max_pos_val, 40))

st.session_state["grid_range"] = st.sidebar.slider("Grid Position", 1, max_grid_val, (1, max_grid_val))
st.session_state["pos_range"] = st.sidebar.slider("Final Position", 1, max_pos_val, (1, max_pos_val))
st.session_state["points_range"] = st.sidebar.slider("Points", 0, 35, (0, 35))

# ---------------------------------------------------------
# 4. APPLY GLOBAL SEASON & METRIC FILTERS ACROSS ALL TABLES
# ---------------------------------------------------------
filtered_results = results.copy()
filtered_races = races.copy()
filtered_sprints = sprints.copy()

if selected_seasons:
    if "season" in filtered_results.columns:
        filtered_results = filtered_results[filtered_results["season"].isin(selected_seasons)]
    if "season" in filtered_races.columns:
        filtered_races = filtered_races[filtered_races["season"].isin(selected_seasons)]
    if "season" in filtered_sprints.columns:
        filtered_sprints = filtered_sprints[filtered_sprints["season"].isin(selected_seasons)]

g_min, g_max = st.session_state["grid_range"]
p_min, p_max = st.session_state["pos_range"]
pts_min, pts_max = st.session_state["points_range"]

grid_col = "grid_position" if "grid_position" in filtered_results.columns else "grid"
final_col = "final_position" if "final_position" in filtered_results.columns else "position"

if grid_col in filtered_results.columns:
    filtered_results[grid_col] = pd.to_numeric(filtered_results[grid_col], errors="coerce")
    filtered_results = filtered_results[filtered_results[grid_col].between(g_min, g_max)]
if final_col in filtered_results.columns:
    filtered_results[final_col] = pd.to_numeric(filtered_results[final_col], errors="coerce")
    filtered_results = filtered_results[filtered_results[final_col].between(p_min, p_max)]
if "points" in filtered_results.columns:
    filtered_results["points"] = pd.to_numeric(filtered_results["points"], errors="coerce")
    filtered_results = filtered_results[filtered_results["points"].between(pts_min, pts_max)]

# Also filter sprint session results if present
if "session_type" in filtered_results.columns:
    filtered_sprint_results = filtered_results[filtered_results["session_type"].str.upper() == "SPRINT"]
else:
    filtered_sprint_results = filtered_sprints

filtered_data = {
    **data,
    "races": filtered_races,
    "results": filtered_results,
    "sprints": filtered_sprint_results
}

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
# 6. ROUTE TO SELECTED PAGE
# ---------------------------------------------------------
if page == "Executive Summary":
    render_executive_summary(filtered_data)

elif page == "RQ1 — Driver & Constructor Insights":
    render_rq1(filtered_data["results"])

elif page == "RQ2 — Race Outcome Analytics":
    render_rq2(filtered_data)

elif page == "RQ3 — Circuit Geography":
    try:
        res_df = filtered_data["results"].copy()
        races_df = filtered_data["races"].copy()

        if not races_df.empty and "season" in res_df.columns and "round" in res_df.columns:
            races_subset = races_df.drop_duplicates(subset=["season", "round"])
            cols_to_drop = [c for c in ["circuit_name", "locality", "country", "race_name", "race_date"] if c in res_df.columns]
            if cols_to_drop:
                res_df = res_df.drop(columns=cols_to_drop)

            res_df = res_df.merge(races_subset, on=["season", "round"], how="left")

        res_df["circuit_country"] = res_df["country"].fillna("International") if "country" in res_df.columns else "International"
        if "circuit_name" not in res_df.columns:
            res_df["circuit_name"] = res_df["race_name" if "race_name" in res_df.columns else "circuit_id"].fillna("Grand Prix Circuit")
        else:
            res_df["circuit_name"] = res_df["circuit_name"].fillna("Grand Prix Circuit")

        render_rq3(res_df)
    except Exception as e:
        st.error(f"Error loading RQ3 Circuit Geography data: {e}")

elif page == "RQ4 — Sprint Race Analysis":
    render_rq4(filtered_data["sprints"] if not filtered_data["sprints"].empty else filtered_data["results"])

elif page == "RQ5 — Cross‑Dataset Insights":
    render_rq5(filtered_data)

elif page == "RQ6: Graphic-LLM-RAG & ML Engine":
    rq6_graphic_llm_rag.render()

# ---------------------------------------------------------
# 7. FOOTER
# ---------------------------------------------------------
st.markdown("---")
st.markdown("### Built by SRH F1 Student Group — F1 Analytics Platform 🚀")