import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from utils import f1_fig


def render_rq3(df: pd.DataFrame):
    st.header("🌎 RQ3 — Circuit Geography & Regional Performance")

    if df.empty:
        st.warning("⚠️ No data available matching the current filter criteria.")
        return

    df = df.copy()
    df["points"] = pd.to_numeric(df["points"], errors="coerce").fillna(0.0)

    country_col = next((c for c in ["circuit_country", "country", "location_country"] if c in df.columns), "circuit_country")
    circuit_col = next((c for c in ["circuit_name", "name", "race_name"] if c in df.columns), "circuit_name")

    df[country_col] = df[country_col].fillna("International").astype(str)
    df[circuit_col] = df[circuit_col].fillna("Grand Prix Circuit").astype(str)

    # Normalize UK / USA for Plotly country choropleth matching
    country_map_fix = {"UK": "United Kingdom", "USA": "United States", "UAE": "United Arab Emirates"}
    df["geo_country"] = df[country_col].replace(country_map_fix)

    # 1. Geographic Choropleth & Top Countries Bar
    st.subheader("🗺️ Circuit Performance by Country")
    country_df = (
        df.groupby("geo_country", as_index=False)["points"]
        .sum()
        .sort_values("points", ascending=False)
    )

    col1, col2 = st.columns([1, 1])
    with col1:
        locs = [str(v) for v in country_df["geo_country"].tolist()]
        z_pts = [float(v) for v in country_df["points"].tolist()]

        fig_map = f1_fig("Points Awarded by Host Country", height=430)
        fig_map.add_trace(go.Choropleth(
            locations=locs,
            locationmode="country names",
            z=z_pts,
            colorscale="Viridis",
            colorbar_title="Points"
        ))
        fig_map.update_geos(bgcolor="#0d0d0d", lakecolor="#0d0d0d", landcolor="#1c1c1c", showframe=False)
        st.plotly_chart(fig_map, use_container_width=True)

    with col2:
        top_c = country_df.head(15)
        cx = [str(v) for v in top_c["geo_country"].tolist()]
        cy = [float(v) for v in top_c["points"].tolist()]

        fig_bar = f1_fig("Top 15 Host Countries — Total Points", height=430)
        fig_bar.add_trace(go.Bar(
            x=cx, y=cy,
            text=[f"{v:,.0f}" for v in cy],
            textposition="outside",
            marker=dict(color=cy, colorscale="Plasma")
        ))
        fig_bar.update_layout(xaxis_tickangle=-45, yaxis_title="Total Points", yaxis=dict(rangemode="tozero"))
        st.plotly_chart(fig_bar, use_container_width=True)

    # 2. Circuit Competitiveness Index (Mean Position Delta)
    st.subheader("🔥 Circuit Competitiveness Index (Avg Position Changes)")
    g_col = "grid_position" if "grid_position" in df.columns else "grid"
    p_col = "final_position" if "final_position" in df.columns else "position"

    if g_col in df.columns and p_col in df.columns:
        df[g_col] = pd.to_numeric(df[g_col], errors="coerce")
        df[p_col] = pd.to_numeric(df[p_col], errors="coerce")
        valid_c = df.dropna(subset=[g_col, p_col]).copy()
        valid_c["pos_delta"] = (valid_c[g_col] - valid_c[p_col]).abs()

        cci_df = (
            valid_c.groupby(circuit_col, as_index=False)["pos_delta"]
            .mean()
            .rename(columns={"pos_delta": "avg_delta"})
            .sort_values("avg_delta", ascending=False)
            .head(15)
        )
        ccx = [str(v) for v in cci_df[circuit_col].tolist()]
        ccy = [round(float(v), 2) for v in cci_df["avg_delta"].tolist()]

        fig_cci = f1_fig("Top 15 Most Overtake-Heavy Circuits (Avg Positions Gained/Lost)")
        fig_cci.add_trace(go.Bar(
            x=ccx, y=ccy,
            text=[f"{v:.2f}" for v in ccy],
            textposition="outside",
            marker=dict(color=ccy, colorscale="Turbo")
        ))
        fig_cci.update_layout(xaxis_tickangle=-45, yaxis_title="Avg Position Change", yaxis=dict(rangemode="tozero"))
        st.plotly_chart(fig_cci, use_container_width=True)

    st.success("RQ3 analysis loaded successfully.")