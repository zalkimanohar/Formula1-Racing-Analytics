import streamlit as st
import plotly.express as px

def render_rq2(df):
    st.markdown("## 🟦 RQ2 — RACE EXECUTION & OUTCOME DRIVERS")

    # RQ2.1 — Grid vs Final Position (Scatter)
    fig = px.scatter(
        df,
        x="grid_position",
        y="final_position",
        color="driver_name",
        title="RQ2.1 — Grid vs Final Position",
        opacity=0.6
    )
    fig.update_layout(yaxis_autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)

    # RQ2.2 — Constructor DNF Rate (Bar)
    dnf_mask = df["status"].str.contains("DNF", case=False, na=False)
    dnf_rate = (
        df.assign(is_dnf=dnf_mask)
        .groupby("constructor_name", as_index=False)["is_dnf"]
        .mean()
        .rename(columns={"is_dnf": "dnf_rate"})
        .sort_values("dnf_rate", ascending=False)
    )
    fig = px.bar(
        dnf_rate,
        x="constructor_name",
        y="dnf_rate",
        title="RQ2.2 — Constructor DNF Rate"
    )
    st.plotly_chart(fig, use_container_width=True)

    # RQ2.3 — Driver Recovery Index (Bar)
    recovery = (
        df.groupby("driver_name", as_index=False)["positions_gained"]
        .mean()
        .sort_values("positions_gained", ascending=False)
    )
    fig = px.bar(
        recovery,
        x="driver_name",
        y="positions_gained",
        title="RQ2.3 — Driver Recovery Index (Avg Positions Gained)"
    )
    st.plotly_chart(fig, use_container_width=True)
