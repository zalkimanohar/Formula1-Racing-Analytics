import streamlit as st
import plotly.express as px
from utils import load_gold

st.title("🏎️ Driver Performance Insights")

drivers = load_gold("dim_drivers")
results = load_gold("fact_session_results")
races = load_gold("dim_races")

df = (
    results
    .merge(drivers, on="driver_id")
    .merge(races, on=["season", "round"])
)

driver = st.selectbox("Select Driver", sorted(df["driver_name"].unique()))

filtered = df[df["driver_name"] == driver]

col1, col2 = st.columns(2)

with col1:
    fig = px.line(filtered, x="season", y="points")
    st.plotly_chart(fig, use_container_width=True)

with col2:
    fig = px.bar(
    filtered,
    x="race_name_y",          # FIXED
    y="final_position",       # FIXED
    title="Race Positions"
    )

    st.plotly_chart(fig, use_container_width=True)

st.subheader("Career Summary")
st.dataframe(filtered[["season", "race_name_y", "final_position", "points"]])
