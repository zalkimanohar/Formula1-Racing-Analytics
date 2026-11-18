import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from utils import f1_fig


def render_executive_summary(data):
    st.title("📘 Executive Summary")

    drivers = data["drivers"]
    constructors = data["constructors"]
    races = data["races"]
    results = data["results"].copy()

    if results.empty:
        st.warning("⚠️ No records match your current filter settings. Please broaden your slider or season selections.")
        return

    results["points"] = pd.to_numeric(results["points"], errors="coerce").fillna(0.0)

    # ---------------------------------------------------------
    # KEY METRICS
    # ---------------------------------------------------------
    st.subheader("🏎️ Key Metrics Overview")

    total_drivers = int(results["driver_id"].nunique()) if "driver_id" in results.columns else int(drivers["driver_id"].nunique())
    total_constructors = int(results["constructor_id"].nunique()) if "constructor_id" in results.columns else int(constructors["constructor_id"].nunique())

    if "season" in results.columns and "round" in results.columns:
        total_races = int(results[["season", "round"]].drop_duplicates().shape[0])
    else:
        total_races = int(races[["season", "round"]].drop_duplicates().shape[0])

    total_points = float(results["points"].sum())

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Drivers", total_drivers)
    col2.metric("Constructors", total_constructors)
    col3.metric("Races", total_races)
    col4.metric("Total Points Awarded", f"{total_points:,.0f}")

    # ---------------------------------------------------------
    # TOP DRIVER
    # ---------------------------------------------------------
    st.subheader("🏁 Top Driver")
    driver_perf = pd.DataFrame()

    if "driver_id" in results.columns:
        driver_perf = (
            results.groupby("driver_id", as_index=False)["points"]
            .sum()
        )
        if not drivers.empty and "driver_id" in drivers.columns:
            d_cols = [c for c in ["driver_id", "driver_name", "given_name", "family_name"] if c in drivers.columns]
            driver_perf = driver_perf.merge(drivers[d_cols].drop_duplicates("driver_id"), on="driver_id", how="left")

        if "driver_name" not in driver_perf.columns or driver_perf["driver_name"].isna().all():
            if "given_name" in driver_perf.columns and "family_name" in driver_perf.columns:
                driver_perf["driver_name"] = (driver_perf["given_name"].fillna("") + " " + driver_perf["family_name"].fillna("")).str.strip()
            else:
                driver_perf["driver_name"] = "Driver " + driver_perf["driver_id"].astype(str)

        driver_perf["driver_name"] = driver_perf["driver_name"].fillna("Unknown Driver").astype(str).str.strip()
        driver_perf["points"] = driver_perf["points"].astype(float)
        driver_perf = driver_perf.sort_values("points", ascending=False).reset_index(drop=True)

        if not driver_perf.empty:
            top_driver = driver_perf.iloc[0]
            st.success(
                f"🏎️ **{top_driver['driver_name']}** leads with **{top_driver['points']:,.1f} points**."
            )

    # ---------------------------------------------------------
    # TOP CONSTRUCTOR
    # ---------------------------------------------------------
    st.subheader("🏆 Top Constructor")

    if "constructor_id" in results.columns:
        constructor_perf = (
            results.groupby("constructor_id", as_index=False)["points"]
            .sum()
        )
        if not constructors.empty and "constructor_id" in constructors.columns and "constructor_name" in constructors.columns:
            constructor_perf = constructor_perf.merge(
                constructors[["constructor_id", "constructor_name"]].drop_duplicates("constructor_id"),
                on="constructor_id",
                how="left"
            )
        if "constructor_name" not in constructor_perf.columns:
            constructor_perf["constructor_name"] = "Constructor " + constructor_perf["constructor_id"].astype(str)

        constructor_perf["constructor_name"] = constructor_perf["constructor_name"].fillna("Unknown").astype(str)
        constructor_perf["points"] = constructor_perf["points"].astype(float)
        constructor_perf = constructor_perf.sort_values("points", ascending=False).reset_index(drop=True)

        if not constructor_perf.empty:
            top_constructor = constructor_perf.iloc[0]
            st.info(
                f"🏆 **{top_constructor['constructor_name']}** leads constructors with **{top_constructor['points']:,.1f} points**."
            )

    # ---------------------------------------------------------
    # POINTS DISTRIBUTION ACROSS DRIVERS
    # ---------------------------------------------------------
    st.subheader("📊 Points Distribution Across Drivers")

    if not driver_perf.empty:
        top15 = driver_perf.head(15)
        fig = f1_fig("Top 15 Drivers — Points Distribution")
        fig.add_trace(
            go.Bar(
                x=top15["driver_name"].tolist(),
                y=top15["points"].tolist(),
                text=[f"{v:,.0f}" for v in top15["points"].tolist()],
                textposition="outside",
                marker_color="#ff1e00",
                orientation="v"
            )
        )
        fig.update_layout(
            xaxis_title="Driver",
            yaxis_title="Total Points",
            xaxis_tickangle=-45,
            yaxis=dict(rangemode="tozero")
        )
        st.plotly_chart(fig, use_container_width=True)

    st.caption("📌 *This chart highlights the most dominant drivers in the filtered dataset.*")
    st.success("Executive Summary loaded successfully.")