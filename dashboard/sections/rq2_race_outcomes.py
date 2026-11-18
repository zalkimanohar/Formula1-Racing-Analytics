import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from utils import f1_fig


def render_rq2(data):
    st.title("🏁 RQ2 — Race Outcomes & Competitiveness")

    results = data["results"].copy()
    if results.empty:
        st.warning("⚠️ No records match your current filter settings.")
        return

    grid_col = "grid_position" if "grid_position" in results.columns else "grid"
    final_col = "final_position" if "final_position" in results.columns else "position"

    results[grid_col] = pd.to_numeric(results[grid_col], errors="coerce")
    results[final_col] = pd.to_numeric(results[final_col], errors="coerce")
    results["points"] = pd.to_numeric(results["points"], errors="coerce").fillna(0.0)

    # 1. Grid Position vs Final Position
    st.subheader("📉 Grid Position vs Final Position")
    valid = results.dropna(subset=[grid_col, final_col]).copy()
    valid = valid[(valid[grid_col] > 0) & (valid[final_col] > 0)]

    if not valid.empty:
        # Aggregate frequency & average points per (grid, finish) pair for crisp rendering
        agg_pos = (
            valid.groupby([grid_col, final_col], as_index=False)
            .agg(count=("points", "count"), avg_pts=("points", "mean"))
        )
        gx = [float(v) for v in agg_pos[grid_col].tolist()]
        fy = [float(v) for v in agg_pos[final_col].tolist()]
        cnt = [int(v) for v in agg_pos["count"].tolist()]
        pts = [round(float(v), 1) for v in agg_pos["avg_pts"].tolist()]
        max_c = max(cnt) if cnt else 1

        fig1 = f1_fig("Grid Position vs Final Position (Bubble Size = Race Frequency)")
        fig1.add_trace(go.Scatter(
            x=gx,
            y=fy,
            mode="markers",
            text=[f"Grid P{int(g)} → Finish P{int(f)}<br>Occurrences: {c}<br>Avg Points: {p}" for g, f, c, p in zip(gx, fy, cnt, pts)],
            hoverinfo="text",
            marker=dict(
                size=[max(8, (c / max_c) * 32) for c in cnt],
                color=pts,
                colorscale="Turbo",
                showscale=True,
                colorbar=dict(title="Avg Points")
            )
        ))
        # Diagonal reference line (Grid == Finish)
        max_axis = max(max(gx), max(fy))
        fig1.add_trace(go.Scatter(
            x=[1, max_axis], y=[1, max_axis],
            mode="lines",
            name="No Position Change",
            line=dict(color="#888888", dash="dash")
        ))
        fig1.update_yaxes(autorange="reversed", title="Final Position (P1 at Top)")
        fig1.update_xaxes(title="Starting Grid Position")
        st.plotly_chart(fig1, use_container_width=True)

    # 2. DNF Rate by Season
    st.subheader("💥 DNF Rate by Season")
    if "status" in results.columns and "season" in results.columns:
        results["is_dnf"] = ~results["status"].astype(str).str.contains("Finished|\\+1 Lap|\\+2 Laps|\\+3 Laps|\\+4 Laps", case=False, na=False)
        dnf_rate = (
            results.groupby("season", as_index=False)["is_dnf"]
            .mean()
            .sort_values("season")
        )
        sx = [int(v) for v in dnf_rate["season"].tolist()]
        sy = [round(float(v) * 100, 2) for v in dnf_rate["is_dnf"].tolist()]

        fig2 = f1_fig("DNF Rate (%) Over Seasons")
        fig2.add_trace(go.Scatter(
            x=sx, y=sy,
            mode="lines+markers",
            fill="tozeroy",
            line=dict(color="#ff6600", width=3),
            marker=dict(size=8)
        ))
        fig2.update_layout(xaxis_title="Season", yaxis_title="DNF Rate (%)", yaxis=dict(rangemode="tozero"))
        st.plotly_chart(fig2, use_container_width=True)

        # 3. Constructor Reliability Index
        st.subheader("🏆 Constructor Reliability Index")
        rel = (
            results.groupby(["constructor_id", "constructor_name"], as_index=False)
            .agg(races=("is_dnf", "count"), dnfs=("is_dnf", "sum"))
        )
        rel = rel[rel["races"] >= 5]
        rel["reliability"] = ((1.0 - rel["dnfs"] / rel["races"]) * 100).round(2)
        rel = rel.sort_values("reliability", ascending=False).head(15)

        rx = [str(v) for v in rel["constructor_name"].tolist()]
        ry = [float(v) for v in rel["reliability"].tolist()]

        fig3 = f1_fig("Top 15 Constructors — Finish Reliability (%)")
        fig3.add_trace(go.Bar(
            x=rx, y=ry,
            text=[f"{v:.1f}%" for v in ry],
            textposition="outside",
            marker=dict(color=ry, colorscale="Greens")
        ))
        fig3.update_layout(xaxis_tickangle=-45, yaxis_title="Finish Rate (%)", yaxis=dict(range=[0, 110]))
        st.plotly_chart(fig3, use_container_width=True)

    st.success("RQ2 analysis loaded successfully.")