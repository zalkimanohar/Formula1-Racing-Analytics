# dashboard/sections/rq4_sprint_race.py

import streamlit as st
import plotly.express as px
import pandas as pd

def render_rq4(df):
    st.markdown("## 🟨 RQ4 — SPRINT–RACE PERFORMANCE RELATIONSHIP")

    # ---------------------------------------------------------
    # Filter only seasons with sprint races (2021+)
    # ---------------------------------------------------------
    df_sprint = df[df["season"] >= 2021]

    if df_sprint.empty:
        st.info("⚠️ Sprint races exist only from 2021 onward. Adjust your Season filter.")
        return

    # ---------------------------------------------------------
    # Identify sprint sessions
    # ---------------------------------------------------------
    sprint_df = df_sprint[df_sprint["session_type"] == "SPRINT"]
    race_df = df_sprint[df_sprint["session_type"] == "RACE"]

    if sprint_df.empty:
        st.warning("No Sprint sessions found for the selected filters.")
        return

    # ---------------------------------------------------------
    # Merge sprint → race results for same driver & round
    # ---------------------------------------------------------
    merged = sprint_df.merge(
        race_df,
        on=["season", "round", "driver_id"],
        suffixes=("_sprint", "_race")
    )

    if merged.empty:
        st.warning("No matching Sprint–Race pairs found for current filters.")
        return

    # ---------------------------------------------------------
    # RQ4.1 — Sprint Position vs Race Position
    # ---------------------------------------------------------
    st.markdown("### 📌 RQ4.1 — Sprint Position vs Race Position")

    fig1 = px.scatter(
        merged,
        x="final_position_sprint",
        y="final_position_race",
        color="driver_name_sprint",
        trendline="ols",
        labels={
            "final_position_sprint": "Sprint Final Position",
            "final_position_race": "Race Final Position"
        },
        title="Sprint vs Race Final Position (Lower is Better)",
        hover_data=["season", "round", "driver_name_sprint"]
    )

    fig1.update_layout(
        template="plotly_dark",
        height=500,
        legend_title="Driver",
        xaxis=dict(autorange="reversed"),
        yaxis=dict(autorange="reversed")
    )

    st.plotly_chart(fig1, use_container_width=True)

    # ---------------------------------------------------------
    # RQ4.2 — Sprint Points vs Season Points
    # ---------------------------------------------------------
    st.markdown("### 📌 RQ4.2 — Sprint Points vs Season Points")

    # Compute season total points
    season_points = (
        df_sprint.groupby(["season", "driver_id"], as_index=False)["points"]
        .sum()
        .rename(columns={"points": "season_points"})
    )

    merged2 = merged.merge(season_points, on=["season", "driver_id"])

    if merged2.empty:
        st.warning("No Sprint/Season points data available for current filters.")
        return

    fig2 = px.scatter(
        merged2,
        x="points_sprint",
        y="season_points",
        color="driver_name_sprint",
        trendline="ols",
        labels={
            "points_sprint": "Sprint Points",
            "season_points": "Total Season Points"
        },
        title="Sprint Points vs Total Season Points",
        hover_data=["season", "round", "driver_name_sprint"]
    )

    fig2.update_layout(
        template="plotly_dark",
        height=500,
        legend_title="Driver"
    )

    st.plotly_chart(fig2, use_container_width=True)

    # ---------------------------------------------------------
    # RQ4.3 — Insight Box
    # ---------------------------------------------------------
    st.markdown("### 🧠 Key Insights")

    st.success(
        """
        - Drivers who perform well in Sprint sessions tend to carry momentum into the main race.  
        - Strong Sprint performers often accumulate higher season points.  
        - Sprint races act as a predictor of race-day competitiveness.  
        """
    )
