import streamlit as st
import plotly.express as px
import pandas as pd

def render_rq2(data):
    st.title("🏁 RQ2 — Race Outcomes & Competitiveness")

    # ---------------------------------------------------------
    # EXTRACT GOLD TABLES FROM DICT
    # ---------------------------------------------------------
    results = data["results"].copy()     # fact_session_results

    # ---------------------------------------------------------
    # VALIDATION
    # ---------------------------------------------------------
    if results.empty:
        st.error("❌ Missing required Gold results table.")
        return

    df = results.copy()

    # Ensure race_name exists (fallback if needed)
    if "race_name" not in df.columns and "races" in data:
        races = data["races"].copy()
        df = df.merge(
            races[["season", "round", "race_name"]].drop_duplicates(subset=["season", "round"]),
            on=["season", "round"],
            how="left",
            suffixes=("", "_races")
        )
        if "race_name_races" in df.columns:
            df["race_name"] = df["race_name"].fillna(df["race_name_races"])
            df = df.drop(columns=["race_name_races"])

    if "race_name" not in df.columns:
        df["race_name"] = "Round " + df["round"].astype(str)

    # ---------------------------------------------------------
    # 1) GRID vs FINAL POSITION
    # ---------------------------------------------------------
    st.subheader("📉 Grid Position vs Final Position")

    fig = px.scatter(
        df,
        x="grid_position",
        y="final_position",
        color="points",
        hover_name="race_name",
        title="Grid Position vs Final Position",
        color_continuous_scale="Turbo",
        trendline="ols",
    )
    fig.update_yaxes(autorange="reversed")  # P1 at top
    st.plotly_chart(fig, use_container_width=True)

    # ---------------------------------------------------------
    # 2) TOTAL POINTS PER RACE
    # ---------------------------------------------------------
    st.subheader("🔥 Race Competitiveness — Total Points Awarded")

    race_points = (
        df.groupby(["season", "round", "race_name"], dropna=False)["points"]
        .sum()
        .reset_index()
        .sort_values(["season", "round"])
    )

    current_season = df["season"].iloc[0] if not df.empty else 2026
    fig2 = px.line(
        race_points,
        x="round",
        y="points",
        hover_name="race_name",
        title=f"Total Points Awarded — Season {current_season}",
        markers=True,
        color_discrete_sequence=["#ff1e00"],
    )
    st.plotly_chart(fig2, use_container_width=True)

    # ---------------------------------------------------------
    # 3) DNF RATE OVER TIME
    # ---------------------------------------------------------
    st.subheader("💥 DNF Rate by Season")

    df["is_dnf"] = df["status"].str.contains("DNF|Retired|Accident|Collision|Engine|Gearbox", case=False, na=False)

    dnf_rate = (
        df.groupby("season")["is_dnf"]
        .mean()
        .reset_index()
    )

    fig3 = px.area(
        dnf_rate,
        x="season",
        y="is_dnf",
        title="DNF Rate Over Seasons",
        color_discrete_sequence=["#ff6600"],
    )
    st.plotly_chart(fig3, use_container_width=True)

    # ---------------------------------------------------------
    # 4) CONSTRUCTOR RELIABILITY INDEX
    # ---------------------------------------------------------
    st.subheader("🏆 Constructor Reliability Index")

    constructor_reliability = (
        df.groupby(["constructor_id", "constructor_name"], dropna=False)
        .agg(
            races=("constructor_id", "count"),
            dnfs=("is_dnf", "sum")
        )
        .reset_index()
    )

    constructor_reliability["reliability"] = (
        1 - constructor_reliability["dnfs"] / constructor_reliability["races"]
    )

    fig4 = px.bar(
        constructor_reliability.sort_values("reliability", ascending=False),
        x="constructor_name",
        y="reliability",
        title="Constructor Reliability Index",
        color="reliability",
        color_continuous_scale="Greens",
    )
    st.plotly_chart(fig4, use_container_width=True)

    # ---------------------------------------------------------
    # 5) DRIVER DNF HEATMAP
    # ---------------------------------------------------------
    st.subheader("🧨 Driver DNF Heatmap")

    driver_dnf = (
        df.groupby(["driver_name", "status"], dropna=False)
        .size()
        .reset_index(name="count")
    )

    fig5 = px.density_heatmap(
        driver_dnf,
        x="status",
        y="driver_name",
        z="count",
        title="Driver DNF / Status Heatmap",
        color_continuous_scale="Inferno",
    )
    st.plotly_chart(fig5, use_container_width=True)

    st.success("RQ2 analysis loaded successfully.")