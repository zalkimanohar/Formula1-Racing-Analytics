import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from utils import f1_fig


def render_rq5(data):
    st.title("🔗 RQ5 — Cross‑Dataset Insights")

    results = data["results"].copy()
    races = data.get("races", pd.DataFrame()).copy()
    nationality_ref = data.get("nationality", pd.DataFrame()).copy()

    if results.empty:
        st.warning("⚠️ No records match your current filter settings.")
        return

    df = results.copy()
    df["points"] = pd.to_numeric(df["points"], errors="coerce").fillna(0.0)
    final_col = "final_position" if "final_position" in df.columns else "position"
    df[final_col] = pd.to_numeric(df[final_col], errors="coerce")

    # Join circuit names from dim_races
    if not races.empty and "season" in df.columns and "round" in df.columns:
        r_sub = races.drop_duplicates(subset=["season", "round"]).copy()
        c_col = next((c for c in ["circuit_name", "name", "race_name"] if c in r_sub.columns), None)
        if c_col:
            r_sub["mapped_circuit"] = r_sub[c_col].fillna("Grand Prix Circuit").astype(str)
            df = df.merge(r_sub[["season", "round", "mapped_circuit"]], on=["season", "round"], how="left")

    df["circuit_label"] = df["mapped_circuit"].fillna("Grand Prix Circuit") if "mapped_circuit" in df.columns else "Grand Prix Circuit"

    # 1. Weighted Performance Index
    st.subheader("🔥 Weighted Performance Index (Points + Win/Podium Bonuses)")
    df["is_win"] = (df[final_col] == 1).astype(float)
    df["is_podium"] = ((df[final_col] >= 1) & (df[final_col] <= 3)).astype(float)
    df["performance_index"] = df["points"] + (df["is_win"] * 10.0) + (df["is_podium"] * 5.0)

    perf = (
        df.groupby("driver_name", as_index=False)["performance_index"]
        .sum()
        .sort_values("performance_index", ascending=False)
        .head(15)
    )
    px_vals = [str(v) for v in perf["driver_name"].tolist()]
    py_vals = [float(v) for v in perf["performance_index"].tolist()]

    fig1 = f1_fig("Top 15 Drivers — Weighted Performance Index")
    fig1.add_trace(go.Bar(
        x=px_vals, y=py_vals,
        text=[f"{v:,.0f}" for v in py_vals],
        textposition="outside",
        marker=dict(color=py_vals, colorscale="Teal")
    ))
    fig1.update_layout(xaxis_tickangle=-45, yaxis_title="Weighted Index Score", yaxis=dict(rangemode="tozero"))
    st.plotly_chart(fig1, use_container_width=True)

    # 2. Driver–Circuit Performance Heatmap
    st.subheader("🌍 Driver–Circuit Performance Matrix")
    top_d = px_vals[:12]
    top_c = df.groupby("circuit_label")["points"].sum().nlargest(12).index.tolist()
    sub_mat = df[df["driver_name"].isin(top_d) & df["circuit_label"].isin(top_c)]

    if not sub_mat.empty:
        piv = sub_mat.pivot_table(index="driver_name", columns="circuit_label", values="points", aggfunc="sum", fill_value=0.0)
        z_mat = [[float(val) for val in row] for row in piv.values.tolist()]
        x_circ = [str(c) for c in piv.columns.tolist()]
        y_driv = [str(d) for d in piv.index.tolist()]

        fig2 = f1_fig("Driver–Circuit Points Heatmap", height=500)
        fig2.add_trace(go.Heatmap(
            z=z_mat, x=x_circ, y=y_driv,
            colorscale="Magma",
            colorbar=dict(title="Points")
        ))
        fig2.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig2, use_container_width=True)

    # 3. Nationality Performance
    st.subheader("🌎 Nationality Performance")
    nat_col = "nationality" if "nationality" in df.columns else None
    if nat_col:
        nat_df = (
            df.groupby(nat_col, as_index=False)["points"]
            .sum()
            .sort_values("points", ascending=False)
            .head(15)
        )
        nx = [str(v) for v in nat_df[nat_col].tolist()]
        ny = [float(v) for v in nat_df["points"].tolist()]

        fig3 = f1_fig("Top 15 Driver Nationalities — Total Points")
        fig3.add_trace(go.Bar(
            x=nx, y=ny,
            text=[f"{v:,.0f}" for v in ny],
            textposition="outside",
            marker=dict(color=ny, colorscale="Inferno")
        ))
        fig3.update_layout(xaxis_tickangle=-45, yaxis_title="Total Points", yaxis=dict(rangemode="tozero"))
        st.plotly_chart(fig3, use_container_width=True)

    # 4. Season-Wise Points Trend
    st.subheader("📈 Season‑Wise Points Awarded Trend")
    if "season" in df.columns:
        s_trend = df.groupby("season", as_index=False)["points"].sum().sort_values("season")
        tx = [int(v) for v in s_trend["season"].tolist()]
        ty = [float(v) for v in s_trend["points"].tolist()]

        fig4 = f1_fig("Total Points Awarded per Season")
        fig4.add_trace(go.Scatter(
            x=tx, y=ty,
            mode="lines+markers",
            line=dict(color="#ff1e00", width=3),
            marker=dict(size=8)
        ))
        fig4.update_layout(xaxis_title="Season", yaxis_title="Total Points", yaxis=dict(rangemode="tozero"))
        st.plotly_chart(fig4, use_container_width=True)

    st.success("RQ5 analysis loaded successfully.")