import streamlit as st
from theme import set_theme
from utils import load_table

# Section imports
from sections.executive_summary import render_executive_summary
from sections.rq1_driver_constructor import render_rq1
from sections.rq2_race_outcomes import render_rq2
from sections.rq3_circuit_geography import render_rq3
from sections.rq4_sprint_race import render_rq4
from sections.rq5_cross_dataset import render_rq5

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

# [Rest of your app.py remains the same...]

# ---------------------------------------------------------
# 3. GLOBAL FILTERS (ONLY SEASON + SLIDERS)
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

# Remove 2026 from options
season_list = sorted([s for s in races["season"].dropna().unique() if s != 2027])

# Default seasons
default_seasons = [s for s in [2024, 2025, 2026] if s in season_list]

seasons = st.sidebar.multiselect(
    "Season",
    season_list,
    default=default_seasons
)

# Sliders
grid_min, grid_max = st.sidebar.slider("Grid Position", 1, 20, (1, 20))
final_min, final_max = st.sidebar.slider("Final Position", 1, 20, (1, 20))
points_min, points_max = st.sidebar.slider("Points", 0, 30, (0, 30))

# ---------------------------------------------------------
# 4. APPLY FILTERS (REMOVED CIRCUIT/DRIVER/CONSTRUCTOR/STATUS)
# ---------------------------------------------------------
filtered_results = results.copy()

# Season filter
if len(seasons) > 0:
    filtered_results = filtered_results[
        filtered_results["season"].isin(seasons)
    ]

# Numeric filters
filtered_results = filtered_results[
    (filtered_results["grid_position"].between(grid_min, grid_max)) &
    (filtered_results["final_position"].between(final_min, final_max)) &
    (filtered_results["points"].between(points_min, points_max))
]

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
        "RQ5 — Cross‑Dataset Insights"
    ]
)

# ---------------------------------------------------------
# 6. ROUTE TO SELECTED PAGE
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
    render_rq3(filtered_data)

elif page == "RQ4 — Sprint Race Analysis":
    render_rq4(filtered_data["results"])

elif page == "RQ5 — Cross‑Dataset Insights":
    render_rq5(filtered_data)

# ---------------------------------------------------------
# 7. FOOTER
# ---------------------------------------------------------
st.markdown("---")
st.markdown("### Built by SRH F1 Student Group — F1 Analytics Platform 🚀")
