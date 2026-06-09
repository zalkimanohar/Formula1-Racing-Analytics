import streamlit as st
import plotly.express as px
from utils import load_gold

st.title("📊 Season Analytics")

results = load_gold("fact_session_results")
races = load_gold("dim_races")
drivers = load_gold("dim_drivers")
constructors = load_gold("dim_constructors")   # ADD THIS

df = (
    results
    .merge(races, on=["season", "round"])
    .merge(drivers, on="driver_id")
    .merge(constructors, on="constructor_id")   # FIXED
)

season = st.slider(
    "Select Season",
    int(df["season"].min()),
    int(df["season"].max())
)

filtered = df[df["season"] == season]

fig = px.bar(
    filtered,
    x="driver_name",
    y="points",
    title=f"Driver Points — {season}"   # FIXED
)
st.plotly_chart(fig, use_container_width=True)


fig = px.box(
    filtered,
    x="constructor_name",         # NOW VALID
    y="final_position",
    title=f"Constructor Performance — {season}"
)
st.plotly_chart(fig, use_container_width=True)