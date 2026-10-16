import streamlit as st
import plotly.express as px
import pandas as pd

def render_rq3(data):
    st.title("🌍 RQ3 — Circuit Geography & Regional Performance")

    # Extract tables
    results = data["results"].copy()      # fact_session_results (already denormalized with circuit info)
    circuits = data["circuits"].copy()    # Silver/Gold circuits table if needed

    # ---------------------------------------------------------
    # VALIDATION
    # ---------------------------------------------------------
    if results.empty:
        st.error("❌ Missing fact_session_results table. Please run the full pipeline first.")
        return

    df = results.copy()

    # Ensure circuit_id and circuit_name exist
    if "circuit_id" not in df.columns:
        st.error("❌ 'circuit_id' column is missing from fact table. Check Gold build script.")
        return

    # Fallback or normalize country column name
    country_col = "circuit_country" if "circuit_country" in df.columns else ("country" if "country" in df.columns else None)

    # ---------------------------------------------------------
    # 1) COUNTRY‑LEVEL GEO PERFORMANCE MAP
    # ---------------------------------------------------------
    st.subheader("🗺️ Circuit Performance by Country")

    if country_col:
        country_points = (
            df.groupby(country_col, dropna=False)["points"]
            .sum()
            .reset_index()
        )
        fig = px.choropleth(
            country_points,
            locations=country_col,
            locationmode="country names",
            color="points",
            title="Circuit Performance — Points by Host Country",
            color_continuous_scale="Viridis",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("⚠ No country column found — cannot render geo map.")

    # ---------------------------------------------------------
    # 2) CIRCUIT COMPETITIVENESS INDEX (CCI)
    # ---------------------------------------------------------
    st.subheader("🔥 Circuit Competitiveness Index (CCI)")

    circuit_comp = (
        df.groupby(["circuit_id", "circuit_name"], dropna=False)["final_position"]
        .std()
        .reset_index()
        .rename(columns={"final_position": "competitiveness"})
    )

    circuit_comp["competitiveness"] = circuit_comp["competitiveness"].fillna(0)

    fig2 = px.bar(
        circuit_comp.sort_values("competitiveness"),
        x="circuit_name",
        y="competitiveness",
        title="Circuit Competitiveness Index (Lower = Tighter Racing)",
        color="competitiveness",
        color_continuous_scale="Plasma",
    )
    st.plotly_chart(fig2, use_container_width=True)

    # ---------------------------------------------------------
    # 3) COUNTRY‑WISE PERFORMANCE
    # ---------------------------------------------------------
    st.subheader("🌎 Country‑Wise Performance")

    if country_col:
        region_perf = (
            df.groupby(country_col, dropna=False)["points"]
            .sum()
            .reset_index()
            .sort_values("points", ascending=False)
        )

        fig3 = px.bar(
            region_perf,
            x=country_col,
            y="points",
            title="Total Points Awarded by Country",
            color="points",
            color_continuous_scale="Inferno",
        )
        st.plotly_chart(fig3, use_container_width=True)

    # ---------------------------------------------------------
    # 4) DRIVER–CIRCUIT AFFINITY MAP
    # ---------------------------------------------------------
    st.subheader("🔗 Driver–Circuit Affinity")

    driver_affinity = (
        df.groupby(["driver_name", "circuit_name"], dropna=False)["points"]
        .sum()
        .reset_index()
    )

    fig4 = px.density_heatmap(
        driver_affinity,
        x="circuit_name",
        y="driver_name",
        z="points",
        title="Driver–Circuit Affinity Heatmap",
        color_continuous_scale="Magma",
    )
    st.plotly_chart(fig4, use_container_width=True)

    st.success("RQ3 analysis loaded successfully.")