import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from utils import f1_fig


def render_rq1(df):
    st.title("🏎️ RQ1 — Driver & Constructor Performance")

    if df.empty:
        st.warning("⚠️ No records match your current filter settings.")
        return

    df = df.copy()
    df["points"] = pd.to_numeric(df["points"], errors="coerce").fillna(0.0)

    # 1. Top Drivers by Total Points
    st.subheader("🏁 Top Drivers by Total Points")
    driver_points = (
        df.groupby(["driver_id", "driver_name"], as_index=False)["points"]
        .sum()
        .sort_values("points", ascending=False)
        .head(15)
    )
    x1 = [str(v) for v in driver_points["driver_name"].tolist()]
    y1 = [float(v) for v in driver_points["points"].tolist()]

    fig1 = f1_fig("Top 15 Drivers — Total Points")
    fig1.add_trace(go.Bar(
        x=x1, y=y1,
        text=[f"{v:,.0f}" for v in y1],
        textposition="outside",
        marker=dict(color=y1, colorscale="Reds")
    ))
    fig1.update_layout(xaxis_tickangle=-45, yaxis_title="Total Points", yaxis=dict(rangemode="tozero"))
    st.plotly_chart(fig1, use_container_width=True)

    # 2. Driver Consistency — Avg Points per Race
    st.subheader("📊 Driver Consistency — Avg Points per Race")
    driver_consistency = (
        df.groupby(["driver_id", "driver_name"], as_index=False)["points"]
        .mean()
        .rename(columns={"points": "avg_points"})
        .sort_values("avg_points", ascending=False)
        .head(15)
    )
    x2 = [str(v) for v in driver_consistency["driver_name"].tolist()]
    y2 = [round(float(v), 2) for v in driver_consistency["avg_points"].tolist()]

    fig2 = f1_fig("Top 15 Drivers — Average Points per Race")
    fig2.add_trace(go.Bar(
        x=x2, y=y2,
        text=[f"{v:.2f}" for v in y2],
        textposition="outside",
        marker=dict(color=y2, colorscale="Oranges")
    ))
    fig2.update_layout(xaxis_tickangle=-45, yaxis_title="Avg Points / Race", yaxis=dict(rangemode="tozero"))
    st.plotly_chart(fig2, use_container_width=True)

    # 3. Top Constructors by Total Points
    st.subheader("🏆 Top Constructors by Total Points")
    constructor_points = (
        df.groupby(["constructor_id", "constructor_name"], as_index=False)["points"]
        .sum()
        .sort_values("points", ascending=False)
        .head(15)
    )
    x3 = [str(v) for v in constructor_points["constructor_name"].tolist()]
    y3 = [float(v) for v in constructor_points["points"].tolist()]

    fig3 = f1_fig("Top 15 Constructors — Total Points")
    fig3.add_trace(go.Bar(
        x=x3, y=y3,
        text=[f"{v:,.0f}" for v in y3],
        textposition="outside",
        marker=dict(color=y3, colorscale="Blues")
    ))
    fig3.update_layout(xaxis_tickangle=-45, yaxis_title="Total Points", yaxis=dict(rangemode="tozero"))
    st.plotly_chart(fig3, use_container_width=True)

    # 4. Driver–Constructor Performance Matrix
    st.subheader("🔗 Driver–Constructor Performance Matrix")
    top_d = set(x1[:12])
    top_c = set(x3[:10])
    matrix = (
        df[df["driver_name"].isin(top_d) & df["constructor_name"].isin(top_c)]
        .groupby(["driver_name", "constructor_name"], as_index=False)["points"]
        .sum()
    )
    matrix = matrix[matrix["points"] > 0]

    if not matrix.empty:
        mx = [str(v) for v in matrix["constructor_name"].tolist()]
        my = [str(v) for v in matrix["driver_name"].tolist()]
        mz = [float(v) for v in matrix["points"].tolist()]
        max_z = max(mz) if mz else 1.0
        sizes = [max(10, (v / max_z) * 42) for v in mz]

        fig4 = f1_fig("Driver–Constructor Points Matrix", height=520)
        fig4.add_trace(go.Scatter(
            x=mx, y=my,
            mode="markers+text",
            text=[f"{v:,.0f}" for v in mz],
            textposition="middle center",
            marker=dict(size=sizes, color=mz, colorscale="Viridis", showscale=True)
        ))
        fig4.update_layout(xaxis_tickangle=-45, xaxis_title="Constructor", yaxis_title="Driver")
        st.plotly_chart(fig4, use_container_width=True)

    st.success("RQ1 analysis loaded successfully.")