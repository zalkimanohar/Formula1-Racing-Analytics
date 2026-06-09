import streamlit as st
import plotly.express as px
from utils import load_gold

st.title("🌍 Track & Region Insights")

races = load_gold("dim_races")
results = load_gold("fact_session_results")
drivers = load_gold("dim_drivers")
regions = load_gold("ref_nationality_region")

df = (
    results
    .merge(races, on=["season", "round"])
    .merge(drivers, on="driver_id")
    .merge(regions, on="nationality")
)


region = st.selectbox("Select Region", sorted(df["region"].unique()))

filtered = df[df["region"] == region]

fig = px.bar(
    filtered,
    x="race_name_y",          # FIXED
    y="points",
    color="driver_name",
    title=f"Points by Drivers from {region}"
)

st.plotly_chart(fig, use_container_width=True)
