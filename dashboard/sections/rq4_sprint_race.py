import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from utils import f1_fig


def render_rq4(df, full_results=None):
    st.title("⚡ RQ4 — Sprint Race Analysis")

    if df.empty:
        st.warning("⚠️ No sprint records available for the selected seasons (Sprint format introduced in 2021).")
        return

    sprint_df = df.copy()
    if "session_type" in sprint_df.columns:
        sprint_only = sprint_df[sprint_df["session_type"].str.upper() == "SPRINT"]
        if not sprint_only.empty:
            sprint_df = sprint_only.copy()

    sprint_df["points"] = pd.to_numeric(sprint_df["points"], errors="coerce").fillna(0.0)
    grid_col = "grid_position" if "grid_position" in sprint_df.columns else "grid"
    final_col = "final_position" if "final_position" in sprint_df.columns else "position"

    # 1. Sprint Grid vs Final Position
    st.subheader("📉 Sprint: Grid Position vs Final Position")
    if grid_col in sprint_df.columns and final_col in sprint_df.columns:
        sprint_df[grid_col] = pd.to_numeric(sprint_df[grid_col], errors="coerce")
        sprint_df[final_col] = pd.to_numeric(sprint_df[final_col], errors="coerce")
        valid_s = sprint_df.dropna(subset=[grid_col, final_col])
        valid_s = valid_s[(valid_s[grid_col] > 0) & (valid_s[final_col] > 0)]

        if not valid_s.empty:
            agg_s = valid_s.groupby([grid_col, final_col], as_index=False).agg(cnt=("points", "count"), pts=("points", "mean"))
            gx = [float(v) for v in agg_s[grid_col].tolist()]
            fy = [float(v) for v in agg_s[final_col].tolist()]
            sz = [max(9, int(v) * 4) for v in agg_s["cnt"].tolist()]
            cl = [round(float(v), 2) for v in agg_s["pts"].tolist()]

            fig1 = f1_fig("Sprint — Starting Grid vs Final Position")
            fig1.add_trace(go.Scatter(
                x=gx, y=fy,
                mode="markers",
                marker=dict(size=sz, color=cl, colorscale="Turbo", showscale=True, colorbar=dict(title="Avg Sprint Pts"))
            ))
            fig1.update_yaxes(autorange="reversed", title="Final Position")
            fig1.update_xaxes(title="Grid Position")
            st.plotly_chart(fig1, use_container_width=True)

    # 2. Top Drivers — Sprint Points
    st.subheader("🔥 Sprint Points Distribution")
    sprint_pts = (
        sprint_df.groupby("driver_name", as_index=False)["points"]
        .sum()
        .sort_values("points", ascending=False)
        .head(15)
    )
    sx = [str(v) for v in sprint_pts["driver_name"].tolist()]
    sy = [float(v) for v in sprint_pts["points"].tolist()]

    fig2 = f1_fig("Top 15 Drivers — Sprint Points")
    fig2.add_trace(go.Bar(
        x=sx, y=sy,
        text=[f"{v:,.0f}" for v in sy],
        textposition="outside",
        marker=dict(color=sy, colorscale="Reds")
    ))
    fig2.update_layout(xaxis_tickangle=-45, yaxis_title="Sprint Points", yaxis=dict(rangemode="tozero"))
    st.plotly_chart(fig2, use_container_width=True)

    # 3. Sprint vs Grand Prix Points Correlation
    if full_results is not None and not full_results.empty:
        st.subheader("🔗 Sprint vs Grand Prix Race Points")
        race_only = full_results[full_results["session_type"].str.upper() == "RACE"] if "session_type" in full_results.columns else full_results
        race_pts = race_only.groupby("driver_name", as_index=False)["points"].sum().rename(columns={"points": "race_points"})
        all_sprint_pts = sprint_df.groupby("driver_name", as_index=False)["points"].sum().rename(columns={"points": "sprint_points"})
        comp = all_sprint_pts.merge(race_pts, on="driver_name", how="inner")
        comp = comp[(comp["sprint_points"] > 0) | (comp["race_points"] > 0)]

        if not comp.empty:
            cx = [float(v) for v in comp["sprint_points"].tolist()]
            cy = [float(v) for v in comp["race_points"].tolist()]
            names = [str(v) for v in comp["driver_name"].tolist()]

            fig3 = f1_fig("Sprint Points vs Grand Prix Points")
            fig3.add_trace(go.Scatter(
                x=cx, y=cy,
                mode="markers+text",
                text=names,
                textposition="top center",
                marker=dict(size=12, color=cy, colorscale="Viridis", showscale=True)
            ))
            fig3.update_layout(xaxis_title="Total Sprint Points", yaxis_title="Total Grand Prix Points")
            st.plotly_chart(fig3, use_container_width=True)

    # 4. Constructor Sprint Performance
    st.subheader("🏆 Constructor Sprint Performance")
    c_sprint = (
        sprint_df.groupby("constructor_name", as_index=False)["points"]
        .sum()
        .sort_values("points", ascending=False)
        .head(15)
    )
    csx = [str(v) for v in c_sprint["constructor_name"].tolist()]
    csy = [float(v) for v in c_sprint["points"].tolist()]

    fig4 = f1_fig("Top Constructors — Sprint Points")
    fig4.add_trace(go.Bar(
        x=csx, y=csy,
        text=[f"{v:,.0f}" for v in csy],
        textposition="outside",
        marker=dict(color=csy, colorscale="Blues")
    ))
    fig4.update_layout(xaxis_tickangle=-45, yaxis_title="Sprint Points", yaxis=dict(rangemode="tozero"))
    st.plotly_chart(fig4, use_container_width=True)

    st.success("RQ4 analysis loaded successfully.")