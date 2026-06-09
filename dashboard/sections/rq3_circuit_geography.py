# dashboard/sections/rq3_circuit_geography.py

import streamlit as st
import plotly.express as px

def render_rq3(df):
    st.markdown("## 🟩 RQ3 — CIRCUIT & GEOGRAPHICAL PERFORMANCE")

    # ---------------------------------------------------------
    # FIX: unify nationality_region column
    # ---------------------------------------------------------
    if "nationality_region" not in df.columns:
        if "nationality_region_x" in df.columns:
            df["nationality_region"] = df["nationality_region_x"]
        elif "nationality_region_y" in df.columns:
            df["nationality_region"] = df["nationality_region_y"]
        else:
            df["nationality_region"] = "Other"

    # RQ3.1 — Circuit Competitiveness Index
    circuit_comp = (
        df.groupby("circuit_name")["points"]
        .std()
        .reset_index()
        .rename(columns={"points": "points_std"})
        .sort_values("points_std", ascending=False)
    )
    st.plotly_chart(
        px.bar(circuit_comp.head(20), x="circuit_name", y="points_std",
               title="RQ3.1 — Circuit Competitiveness Index"),
        use_container_width=True
    )

    # RQ3.2 — Country Performance
    country_perf = (
        df.groupby("country_name", as_index=False)["points"]
        .mean()
        .sort_values("points", ascending=False)
    )
    st.plotly_chart(
        px.bar(country_perf, x="country_name", y="points",
               title="RQ3.2 — Average Points by Host Country"),
        use_container_width=True
    )

    # RQ3.3 — Driver Region vs Performance
    region_perf = (
        df.groupby("nationality_region", as_index=False)["points"]
        .mean()
        .sort_values("points", ascending=False)
    )
    st.plotly_chart(
        px.bar(region_perf, x="nationality_region", y="points",
               title="RQ3.3 — Driver Region vs Performance"),
        use_container_width=True
    )
