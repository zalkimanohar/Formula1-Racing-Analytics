import streamlit as st
import plotly.express as px

def render_rq1(df):
    st.markdown("## 🟥 RQ1 — DRIVER & CONSTRUCTOR PERFORMANCE")

    # RQ1.1 — Driver Season Performance (Line)
    driver_season = (
        df.groupby(["season", "driver_name"], as_index=False)["points"]
        .sum()
    )
    fig = px.line(
        driver_season,
        x="season",
        y="points",
        color="driver_name",
        markers=True,
        title="RQ1.1 — Driver Season Performance"
    )
    st.plotly_chart(fig, use_container_width=True)

    # RQ1.2 — Constructor Season Performance (Stacked Column)
    constructor_season = (
        df.groupby(["season", "constructor_name"], as_index=False)["points"]
        .sum()
    )
    fig = px.bar(
        constructor_season,
        x="season",
        y="points",
        color="constructor_name",
        title="RQ1.2 — Constructor Season Performance (Stacked)"
    )
    st.plotly_chart(fig, use_container_width=True)

    # RQ1.3 — Driver Consistency Index (Horizontal Bar)
    consistency = (
        df.groupby("driver_name", as_index=False)["final_position"]
        .std()
        .rename(columns={"final_position": "position_std"})
        .sort_values("position_std")
    )
    fig = px.bar(
        consistency,
        x="position_std",
        y="driver_name",
        orientation="h",
        title="RQ1.3 — Driver Consistency Index (Lower = More Consistent)"
    )
    st.plotly_chart(fig, use_container_width=True)

    # RQ1.4 — Driver Age vs Performance (Scatter)
    fig = px.scatter(
        df,
        x="age_at_race",
        y="points",
        color="driver_name",
        title="RQ1.4 — Driver Age vs Points",
        opacity=0.6
    )
    st.plotly_chart(fig, use_container_width=True)

    # RQ1.5 — Constructor Dominance (Standings View)
    standings = (
        df.groupby(["season", "constructor_name"], as_index=False)["points"]
        .sum()
        .sort_values(["season", "points"], ascending=[True, False])
    )
    st.markdown("**RQ1.5 — Constructor Dominance (Standings)**")
    st.dataframe(standings, use_container_width=True)
