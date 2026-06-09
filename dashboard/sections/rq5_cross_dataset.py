import streamlit as st
import plotly.express as px

def render_rq5(df):
    st.markdown("## 🟧 RQ5 — ADVANCED CROSS‑DATASET INSIGHTS")

    # RQ5.1 — Driver × Constructor × Circuit Heatmap (Avg Points)
    heat = (
        df.groupby(["driver_name", "constructor_name", "circuit_name"], as_index=False)["points"]
        .mean()
    )
    if not heat.empty:
        fig = px.density_heatmap(
            heat,
            x="constructor_name",
            y="driver_name",
            z="points",
            title="RQ5.1 — Driver × Constructor × Circuit (Avg Points)"
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data available for heatmap under current filters.")

    # RQ5.2 — Season Trend Lines (Constructor Points)
    season_trend = (
        df.groupby(["season", "constructor_name"], as_index=False)["points"]
        .sum()
    )
    if not season_trend.empty:
        fig = px.line(
            season_trend,
            x="season",
            y="points",
            color="constructor_name",
            title="RQ5.2 — Season Trend Lines (Constructor Points)"
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No season trend data available for current filters.")
